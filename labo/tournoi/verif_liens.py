"""Tournoi, étape 1 : les études citées par les chercheurs existent-elles, et chaque lien mène-t-il à la bonne ?

Lit labo/tournoi/regles_preenregistrees.json (le fichier pré-enregistré : jamais modifié ici) et, pour chaque étude :
1. Crossref (api.crossref.org : le registre public des DOI, gratuit, sans compte) : recherche avec la référence écrite.
   L'étude est « trouvée » si une des 5 meilleures réponses a un titre qui ressemble (au moins 60 % des mots importants
   du titre cité) ET le nom du 1er auteur cité.
2. Le lien : lu seulement si le robots.txt du site le permet (robots.txt illisible = interdit ; absent, erreur 404 =
   permis), en respectant son Crawl-delay (3 s au moins entre deux requêtes au même site). Chaque redirection est
   vérifiée de la même façon avant d'être suivie. Un refus (401/403) est respecté : « non vérifiable », sans nouvel essai.
   Le titre de la page (citation_title, og:title ou <title> ; titre et 1re page pour un PDF) est comparé au titre cité.
Agent : « Radar projet personnel ». Aucun courriel, aucun compte.

Sortie : labo/tournoi/liens/verif_liens.json et resume.md (avec une ligne VERDICT).
Essais hors ligne : TOURNOI_REGLES (fichier des règles), TOURNOI_LIENS (dossier de sortie), TOURNOI_CROSSREF (adresse
de l'API) et TOURNOI_DELAI (secondes entre deux requêtes au même site).
"""
import html
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import acces  # noqa: E402

UA = "Radar projet personnel"
REGLES = Path(os.environ.get("TOURNOI_REGLES", ICI / "regles_preenregistrees.json"))
SORTIE = Path(os.environ.get("TOURNOI_LIENS", ICI / "liens"))
CROSSREF = os.environ.get("TOURNOI_CROSSREF", "https://api.crossref.org/works")
DELAI_MIN = float(os.environ.get("TOURNOI_DELAI", "3"))  # secondes entre deux requêtes au même site, au moins
DELAI_MAX = 60.0  # un Crawl-delay plus long : ce site n'est pas lu (non vérifiable)
SEUIL = 0.6
VIDES = set("""the and for with from that this into over than about does what when where which their there these those
are was were has have had not but its our your his her they them evidence journal review working paper papers abstract
ssrn nber repec ideas econpapers sciencedirect wiley online library article research university""".split())


class SansRedirection(urllib.request.HTTPRedirectHandler):
    """Une redirection revient comme une réponse 3xx : le robots.txt du nouveau site est vérifié avant de la suivre."""

    def redirect_request(self, *_):
        return None


urllib.request.install_opener(urllib.request.build_opener(SansRedirection()))
DERNIER: dict[str, float] = {}  # site → moment de la dernière requête
DELAI: dict[str, float] = {}  # site → secondes entre deux requêtes (Crawl-delay ou Request-rate, 3 s au moins)
ROBOTS: dict[str, object] = {}  # site → RobotFileParser, None (pas de robots.txt : permis) ou texte (interdit, raison)


def propre(url: str) -> str:
    return urllib.parse.quote(url.strip(), safe=":/?&=%#+,;@~!$'()*[]")


def requete(url: str):
    return urllib.request.Request(propre(url), headers={"User-Agent": UA})


def attendre(site: str):
    t = DERNIER.get(site)
    if t is not None:
        reste = t + DELAI.get(site, DELAI_MIN) - time.monotonic()
        if reste > 0:
            time.sleep(reste)
    DERNIER[site] = time.monotonic()


def robots(schema: str, site: str):
    """Le robots.txt du site, lu une fois. Illisible (erreur, refus, page HTML) = interdit ; absent (404, 410) = permis."""
    if site in ROBOTS:
        return ROBOTS[site]
    url = f"{schema}://{site}/robots.txt"
    for _ in range(5):  # redirections du robots.txt suivies, 5 au plus (RFC 9309)
        h = urllib.parse.urlsplit(url).netloc
        attendre(h)
        try:
            r = acces.ouvrir(requete(url), timeout=30)
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400 and exc.headers.get("Location"):
                url = urllib.parse.urljoin(url, exc.headers["Location"])
                continue
            ROBOTS[site] = None if exc.code in (404, 410) else f"robots.txt illisible (erreur {exc.code}) : site non lu"
            return ROBOTS[site]
        except acces.NonVerifiable as exc:
            ROBOTS[site] = f"robots.txt : {exc}"
            return ROBOTS[site]
        except (ValueError, UnicodeError) as exc:
            ROBOTS[site] = f"robots.txt illisible ({type(exc).__name__}) : site non lu"
            return ROBOTS[site]
        texte = r.read().decode("utf-8", "replace")
        if "html" in (r.headers.get("Content-Type") or "").lower() or texte.lstrip()[:1] == "<":
            ROBOTS[site] = "robots.txt illisible (une page web à la place) : site non lu"
            return ROBOTS[site]
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(texte.splitlines())
        taux = rp.request_rate(UA)
        d = max(DELAI_MIN, float(rp.crawl_delay(UA) or 0), taux.seconds / taux.requests if taux and taux.requests else 0)
        DELAI[site] = DELAI[h] = d
        ROBOTS[site] = rp if d <= DELAI_MAX else f"Crawl-delay de {d:g} s : trop long pour ce labo, site non lu"
        return ROBOTS[site]
    ROBOTS[site] = "robots.txt : trop de redirections, site non lu"
    return ROBOTS[site]


def lire(url: str):
    """("lu", url finale, type, contenu) ; ("erreur", url, code) ; ("non_verifiable", url, raison)."""
    for _ in range(8):
        p = urllib.parse.urlsplit(url)
        if p.scheme not in ("http", "https") or not p.netloc:
            return ("erreur", url, "adresse invalide")
        rb = robots(p.scheme, p.netloc)
        if isinstance(rb, str):
            return ("non_verifiable", url, f"{p.netloc} : {rb}")
        if rb is not None and not rb.can_fetch(UA, propre(url)):
            return ("non_verifiable", url, f"{p.netloc} : le robots.txt interdit cette adresse aux robots")
        attendre(p.netloc)
        try:
            r = acces.ouvrir(requete(url), timeout=60)
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400 and exc.headers.get("Location"):
                url = urllib.parse.urljoin(url, exc.headers["Location"])
                continue
            return ("erreur", url, exc.code)
        except acces.NonVerifiable as exc:
            return ("non_verifiable", url, str(exc))
        except (ValueError, UnicodeError) as exc:
            return ("erreur", url, f"adresse invalide ({type(exc).__name__})")
        return ("lu", url, r.headers.get("Content-Type") or "", r.read())
    return ("erreur", url, "trop de redirections")


def ascii_bas(t: str) -> str:
    """Minuscules sans accents ; tout signe (apostrophe ’ comprise) sépare les mots."""
    return unicodedata.normalize("NFKD", re.sub(r"[\W_]+", " ", t or "")).encode("ascii", "ignore").decode().lower()


def mots(t: str) -> set:
    return {m for m in re.findall(r"[a-z0-9]+", ascii_bas(t)) if len(m) >= 3 and m not in VIDES}


def part(cite: str, trouve: str) -> float:
    """Part des mots importants du titre cité qu'on retrouve dans le texte trouvé."""
    a = mots(cite)
    return round(len(a & mots(trouve)) / len(a), 2) if a else 0.0


def ressemblance(cite: str, reference: str, trouve: str, min_mots: int) -> float:
    """Les 2 sens : mots du titre cité dans le titre trouvé, ou mots du titre trouvé (au moins `min_mots`) dans toute la
    référence (le titre cité est parfois suivi d'autre texte : « … Equities. arXiv 2602… », « …, blogue … »)."""
    inverse = part(trouve, reference) if len(mots(trouve)) >= min_mots else 0.0
    return max(part(cite, trouve), inverse)


def annee_de(reference: str):
    m = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", reference)
    return int(m.group(1)) if m else None


def titre_cite(reference: str) -> str:
    m = re.search(r"\((?:\d{4}[a-z]?|n\.\s?d\.|s\.\s?d\.|forthcoming|à paraître)[^)]*\)[.,:]?\s*(.+)", reference, re.I)
    reste = (m.group(1) if m else reference).strip()
    q = re.match(r"[\"“«]\s*(.+?)\s*[\"”»]", reste)
    if q:
        return q.group(1).strip(" .,")
    return re.split(r"(?<=[.?!])\s+(?=[A-Z«\"“])", reste, maxsplit=1)[0].strip(" .")


def premier_auteur(reference: str) -> str:
    m = re.match(r"\s*([^,(&]+?)(?:,|\s+\(|\s+&|\s+and\b|\s+et\b)", reference)
    return (m.group(1) if m else reference.split()[0] if reference.split() else "").strip()


def noms(t: str) -> set:
    return {m for m in re.findall(r"[a-z]+", ascii_bas(t)) if len(m) >= 2}


def titre_html(texte: str):
    """(titre, d'où il vient) : citation_title, dc.title, og:title, twitter:title, puis <title>."""
    metas = {}
    for balise in re.findall(r"<meta\b[^>]*>", texte, re.I):
        att = {k.lower(): v1 or v2 for k, v1, v2 in re.findall(r'([\w:.-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', balise)}
        cle = (att.get("name") or att.get("property") or "").lower()
        if cle and att.get("content") and cle not in metas:
            metas[cle] = html.unescape(att["content"]).strip()
    for cle in ("citation_title", "dc.title", "og:title", "twitter:title"):
        if metas.get(cle):
            return metas[cle], cle
    m = re.search(r"<title[^>]*>(.*?)</title>", texte, re.I | re.S)
    return (html.unescape(re.sub(r"\s+", " ", m.group(1))).strip(), "title") if m else ("", "")


def titre_pdf(contenu: bytes):
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "pdf (pypdf absent : titre non lu)"
    try:
        lecteur = PdfReader(io.BytesIO(contenu))
        meta = (lecteur.metadata.title or "") if lecteur.metadata else ""
        page = (lecteur.pages[0].extract_text() or "") if len(lecteur.pages) else ""
        return re.sub(r"\s+", " ", f"{meta} | {page[:1500]}").strip(" |"), "pdf"
    except Exception as exc:  # noqa: BLE001 — un PDF abîmé : titre non lu, on le dit
        return "", f"pdf illisible ({type(exc).__name__})"


def verifier_lien(lien: str, cite: str, reference: str = "") -> dict:
    etat = lire(lien)
    if etat[0] == "non_verifiable":
        return {"lien": "non_verifiable", "raison": etat[2], "url_finale": etat[1]}
    if etat[0] == "erreur":
        mort = etat[2] in (404, 410)
        return {"lien": "mort" if mort else "erreur", "raison": f"erreur {etat[2]}", "url_finale": etat[1]}
    _, finale, typ, contenu = etat
    if contenu[:5] == b"%PDF-" or "pdf" in typ.lower():
        titre, source = titre_pdf(contenu)
        texte = ""
    else:
        page = contenu[:2_000_000].decode("utf-8", "replace")
        titre, source = titre_html(page)
        texte = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page)))
    s_titre, s_texte = ressemblance(cite, reference or cite, titre, 3), part(cite, texte)
    verdict = "bon" if s_titre >= SEUIL else "probable" if s_texte >= 0.8 else "autre_page"
    return {"lien": verdict, "url_finale": finale, "titre_page": titre[:300], "source_titre": source,
            "score_titre": s_titre, "score_texte": s_texte}


def crossref(reference: str, cite: str) -> dict:
    q = urllib.parse.urlencode({"query.bibliographic": reference[:400], "rows": 5,
                                "select": "DOI,title,author,issued,container-title"})
    etat = lire(f"{CROSSREF}?{q}")
    if etat[0] != "lu":
        return {"etat": "non_verifiable" if etat[0] == "non_verifiable" else "erreur", "raison": str(etat[2])}
    try:
        items = json.loads(etat[3])["message"]["items"]
    except (ValueError, KeyError, TypeError):
        return {"etat": "erreur", "raison": "réponse illisible"}
    auteur = noms(premier_auteur(reference))
    an_ref = annee_de(reference)
    meilleur = None
    for it in items:
        titre = " ".join(it.get("title") or [])
        familles = " ".join((a.get("family") or a.get("name") or "") for a in it.get("author") or [])
        annee = (((it.get("issued") or {}).get("date-parts") or [[None]])[0] or [None])[0]
        revue = " ".join(it.get("container-title") or [])[:120]
        c = {"doi": it.get("DOI"), "titre": titre[:300], "auteurs": familles[:200], "annee": annee, "revue": revue,
             "score": ressemblance(cite, reference, titre, 2), "auteur": bool(auteur & noms(familles)),
             # référence sans titre (ex. « Alldredge et Blank (2019), Journal of Financial Research ») : la revue et l'année
             "revue_annee": bool(mots(revue)) and part(revue, reference) >= SEUIL and an_ref is not None
             and annee is not None and abs(annee - an_ref) <= 1}
        bon = c["auteur"] and (c["score"] >= SEUIL or c["revue_annee"])
        if meilleur is None or (bon, c["score"], c["auteur"]) > (meilleur["_bon"], meilleur["score"], meilleur["auteur"]):
            meilleur = dict(c, _bon=bon)
    ok = bool(meilleur and meilleur.pop("_bon"))
    return {"etat": "trouvee" if ok else "pas_trouvee", "meilleur": meilleur}


def tige_doi(doi: str) -> str:
    """Le DOI sans son dernier numéro : « 10.1111/jofi.12877 » → « 10.1111/jofi. » (même revue, autre article)."""
    return re.sub(r"\d+[a-z]?$", "", doi.lower().rstrip("/"))


def alertes(x: dict) -> list:
    """Erreurs de citation que Crossref révèle :
    - le titre cité existe (6 mots importants au moins), mais avec d'autres auteurs (auteur mal attribué) ;
    - le lien mène à un AUTRE article de la même revue (même début de DOI, autre numéro, ex. 12877 au lieu de 12878).
    Pas d'alerte pour une référence sans auteur, ni pour la version « document de travail » (DOI SSRN, NBER…) d'une
    étude publiée : c'est la même étude."""
    sortie = []
    m = x["crossref"].get("meilleur") or {}
    auteur = premier_auteur(x["reference"])
    if m and not m.get("auteur") and 1 <= len(auteur.split()) <= 3 and len(mots(m.get("titre", ""))) >= 6 \
            and part(m.get("titre", ""), x["reference"]) >= 0.9:
        sortie.append(f"auteur cité ≠ auteurs de l'étude trouvée ({m.get('auteurs', '')}, {m.get('annee')})")
    d = re.search(r"10\.\d{4,9}/[^\s?#]+", x.get("adresse") or "")
    if d and x["crossref"].get("etat") == "trouvee" and m.get("doi"):
        lien, vrai = d.group(0).lower().rstrip("/"), m["doi"].lower()
        if lien != vrai and tige_doi(lien) == tige_doi(vrai):
            sortie.append(f"le lien mène au DOI {d.group(0)}, mais l'étude a le DOI {m['doi']}")
    return sortie


def cellule(t) -> str:
    return str(t).replace("|", "/").replace("\n", " ")[:160]


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    lignes = []
    acces.installer(lignes, SORTIE / "resume.md")
    regles = json.loads(REGLES.read_text(encoding="utf-8"))["regles"]
    etudes = {}  # (référence, lien) → étude
    for g in regles:
        for e in g.get("etudes") or []:
            cle = (e.get("reference", "").strip(), e.get("lien", "").strip())
            etudes.setdefault(cle, {"reference": cle[0], "adresse": cle[1], "regles": []})["regles"].append(g["id"])
    resultats, par_crossref = [], {}
    for i, e in enumerate(etudes.values(), 1):
        cite = titre_cite(e["reference"])
        if e["reference"] not in par_crossref:  # une seule recherche par référence
            par_crossref[e["reference"]] = crossref(e["reference"], cite)
        x = dict(e, titre_cite=cite, crossref=par_crossref[e["reference"]])
        x.update(verifier_lien(e["adresse"], cite, e["reference"]) if e["adresse"] else {"lien": "absent"})
        resultats.append(x)
        print(f"{i}/{len(etudes)} Crossref {x['crossref']['etat']} · lien {x['lien']} · {e['reference'][:70]}", flush=True)
    # L'existence est celle de la référence : Crossref, sinon au moins un de ses liens qui mène à elle
    existe = {}
    for x in resultats:
        if x["crossref"]["etat"] == "trouvee":
            existe[x["reference"]] = "oui (Crossref)"
        elif x["lien"] in ("bon", "probable") and existe.get(x["reference"]) != "oui (Crossref)":
            existe[x["reference"]] = "oui (lien)"
        else:
            existe.setdefault(x["reference"], "non confirmée")
    for x in resultats:
        x["existe"] = existe[x["reference"]]
        x["alertes"] = alertes(x)
    (SORTIE / "verif_liens.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    liens = {}
    for x in resultats:
        liens[x["lien"]] = liens.get(x["lien"], 0) + 1
    sites_nv = sorted({urllib.parse.urlsplit(x.get("url_finale") or x["adresse"]).netloc
                       for x in resultats if x["lien"] == "non_verifiable"})
    non = sorted(r for r, v in existe.items() if v == "non confirmée")
    lignes += [
        "# Études citées par les chercheurs (étape 1) : vérification",
        "",
        f"Fait le {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC par `labo/tournoi/verif_liens.py`, à partir de "
        f"`{REGLES.name}`. Robots.txt respectés (illisible = site non lu), agent « {UA} », aucun courriel, aucun compte.",
        "",
        f"- Études différentes : {len(existe)} (dans {len(regles)} règles), avec {len(resultats)} liens",
        f"- Existence confirmée : {len(existe) - len(non)} — par Crossref : "
        f"{sum(v == 'oui (Crossref)' for v in existe.values())} ; par un lien seulement : "
        f"{sum(v == 'oui (lien)' for v in existe.values())}",
        f"- Non confirmée : {len(non)}",
        "- Liens : " + " · ".join(f"{k} {v}" for k, v in sorted(liens.items())),
        f"- Sites non lus (robots.txt, refus ou panne) : {', '.join(sites_nv) or 'aucun'}",
        "",
        "Crossref « trouvée » = une des 5 meilleures réponses a le nom du 1er auteur cité, et soit au moins 60 % des "
        "mots importants du titre cité (ou tous ses mots dans la référence), soit, pour une référence sans titre, la "
        "même revue et la même année (à 1 an près). Lien « bon » = même règle pour le titre de la page (3 mots au "
        "moins dans l'autre sens) ; « probable » = la page contient au moins 80 % des mots du titre cité ; "
        "« autre_page » = ni l'un ni l'autre (page générique, autre étude…).",
        "",
        "## Non confirmées (à regarder)",
        "",
        "| Règle(s) | Référence | Lien | Crossref : meilleure réponse | Lien : résultat |",
        "|---|---|---|---|---|",
    ]
    for x in resultats:
        if x["existe"] != "non confirmée":
            continue
        m = x["crossref"].get("meilleur") or {}
        cr = f"{m.get('titre', '')} ({m.get('auteurs', '')}, {m.get('annee')}) score {m.get('score')}" if m \
            else x["crossref"].get("raison", "")
        lignes.append(f"| {', '.join(x['regles'])} | {cellule(x['reference'])} | {cellule(x['adresse'])} | {cellule(cr)} | "
                      f"{x['lien']} : {cellule(x.get('titre_page') or x.get('raison', ''))} |")
    if not non:
        lignes.append("| — | aucune | | | |")
    avec_alerte = [x for x in resultats if x["alertes"]]
    lignes += ["", f"## Erreurs de citation trouvées ({len(avec_alerte)})", "", "| Règle(s) | Référence | Alerte |", "|---|---|---|"]
    lignes += [f"| {', '.join(x['regles'])} | {cellule(x['reference'])} | {cellule(' ; '.join(x['alertes']))} |"
               for x in avec_alerte] or ["| — | aucune | |"]
    lignes += ["", "## Toutes les études", "", "| # | Règle(s) | Existe | Lien | Titre de la page (ou raison) |",
               "|---|---|---|---|---|"]
    for i, x in enumerate(resultats, 1):
        lignes.append(f"| {i} | {', '.join(x['regles'])} | {x['existe']} | {x['lien']} | "
                      f"{cellule(x.get('titre_page') or x.get('raison', ''))} |")
    lignes += ["", "VERDICT : OK" if not non and not avec_alerte else
               f"VERDICT : À REGARDER — {len(non)} étude(s) non confirmée(s) (ni Crossref ni un lien), "
               f"{len(avec_alerte)} erreur(s) de citation"]
    (SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(lignes[-1])


if __name__ == "__main__":
    main()
