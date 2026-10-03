"""Gazette du Canada : règlements liés à l'argent (Partie II) et projets d'intérêt national (Partie I et II).

Lu en français sur gazette.gc.ca (pas de robots.txt : tout est permis ; vérifié le 3 octobre 2026) :
- les 2 fils RSS officiels (Partie I : avis, chaque samedi ; Partie II : règlements, un mercredi sur deux) ;
- l'index de chaque numéro des 90 derniers jours, lu une seule fois (data/gazette/lus.json) ;
- la page de chaque texte retenu : titre officiel, numéro (DORS/TR), date d'enregistrement, loi, résumé « Enjeux ».

gazette_ca : seulement les textes pris en vertu de lois liées à l'argent (tarifs et surtaxes, sanctions, licences
d'importation et d'exportation, investissements étrangers, taxe d'accise, accords commerciaux…). Mesuré sur 7 numéros
(juillet à septembre 2026) : 32 textes retenus sur 87.
grands_projets_ca : les avis (Partie I) et décrets (Partie II) de la Loi visant à bâtir le Canada, et chaque projet
ajouté à la liste du Bureau des grands projets (canada.ca). La loi codifiée du site Justice n'est pas utilisée :
au 31 mars 2026, son annexe 1 était encore vide.

Droit : Décret sur la reproduction de la législation fédérale (TR/97-5) : reproduction permise si elle est exacte et
n'est pas présentée comme la version officielle. Pages canada.ca : usage non commercial (conditions de Canada.ca).
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

from ..models import Evenement
from ..store import Depot
from ..validate import controle_source
from .regulateurs import canonique

VERSION = "gazette-1"
FILS = {"p1": "https://gazette.gc.ca/rss/p1-fra.xml", "p2": "https://gazette.gc.ca/rss/p2-fra.xml"}
BGP_LISTE = "https://www.canada.ca/fr/conseil-prive/bureau-grands-projets/projets/national.html"
FENETRE_JOURS = 90
# Lien d'un numéro (index), d'une édition spéciale ou d'un texte publié seul dans une édition spéciale.
LIEN = re.compile(r"https://gazette\.gc\.ca/rp-pr/(p[12])/\d{4}/(\d{4}-\d\d-\d\d)(-?x\d+)?/html/([A-Za-z0-9-]+)-fra\.html")
NUMERO = re.compile(r"(DORS|TR)/(\d{4})-(\d+)")
MOIS = {m: i for i, m in enumerate(("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                                    "septembre", "octobre", "novembre", "décembre"), 1)}
# Lois liées à l'argent (mots cherchés dans le nom de la loi, en minuscules) : liste fixe, mesurée sur de vrais numéros.
ARGENT = re.compile(r"tarif des douanes|douanes|mesures économiques spéciales|licences d'exportation et d'importation"
                    r"|mesures spéciales d'importation|investir au canada|investissement canada|taxe d'accise"
                    r"|tribunal canadien du commerce extérieur|exécution du budget|libre-échange|transpacifique"
                    r"|accord de partenariat|accord de libre-échange|accord économique|concurrence|banques")
BATIR = re.compile(r"bâtir le canada")


def texte(fragment: str) -> str:
    """Texte lisible d'un bout de HTML : sans balises, entités décodées, espaces simples."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).replace("\xa0", " ")
    return " ".join(t.split())


def extrait(t: str, n: int = 900) -> str:
    """Le texte officiel tel quel ; s'il est long, coupé à la fin d'une phrase, avec « […] »."""
    if len(t) <= n:
        return t
    fin = t.rfind(". ", 0, n)
    return (t[: fin + 1] if fin > 0 else t[:n]) + " […]"


def norme(loi: str) -> str:
    return " ".join((loi or "").lower().replace("’", "'").split())


def date_fr(t: str) -> str | None:
    """« Le 4 septembre 2026 », « 1er août 2026 » -> 2026-09-04."""
    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zéû]+)\s+(\d{4})", (t or "").replace("\xa0", " ").lower())
    if not m or m.group(2) not in MOIS:
        return None
    try:
        return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return None


def contenu_principal(page: str) -> str | None:
    """Le contenu de la page, ou None si c'est une page « Erreur 404 » (renvoyée avec le code 200)."""
    debut, fin = page.find("<main"), page.find("</main>")
    principal = page[debut:fin] if debut >= 0 else page
    if "Erreur 404" in principal or "Error 404" in principal:
        return None
    return principal


def decoder(contenu: bytes) -> str:
    # Les pages sont en UTF-8, sauf un commentaire de l'en-tête écrit en Latin-1 : on le remplace sans erreur.
    return contenu.decode("utf-8", "replace")


# ---------- Fils RSS ----------

def liens_du_fil(contenu: bytes) -> list[dict]:
    """Chaque numéro (ou texte d'une édition spéciale) annoncé par le fil officiel, avec la date tirée du lien."""
    vus, liens = set(), []
    canal = ET.fromstring(contenu).find("channel")
    for it in canal.findall("item") if canal is not None else []:
        lien = (it.findtext("link") or "").strip()
        m = LIEN.fullmatch(lien)
        if not m or lien in vus:  # index codifiés trimestriels et listes annuelles : pas des numéros
            continue
        vus.add(lien)
        liens.append({"partie": m.group(1), "jour": m.group(2), "speciale": bool(m.group(3)), "page": m.group(4),
                      "lien": lien, "titre": " ".join((it.findtext("title") or "").split())})
    return liens


# ---------- Partie II : index d'un numéro et page d'un texte ----------

def lire_index_p2(page: str) -> list[dict]:
    """Les textes d'un numéro : titre (forme inversée de l'index), loi, numéro, date d'enregistrement, mentions."""
    principal = contenu_principal(page) or ""
    textes = []
    for li in re.findall(r"<li>(.*?)</li>", principal, re.S):
        m = re.search(r'<a href="([^"]+)">(.*?)</a>(.*)', li, re.S)
        if not m:
            continue
        morceaux = [texte(p) for p in re.split(r"<br\s*/?>", m.group(2))]
        bas = [b for b in (texte(p) for p in re.split(r"<br\s*/?>", m.group(3))) if b]
        numero = next((b for b in bas if NUMERO.fullmatch(b)), None)
        textes.append({"lien": m.group(1), "titre_index": " ".join(morceaux[:-1]), "loi": morceaux[-1],
                       "numero": numero, "enregistre": next((b for b in bas if re.fullmatch(r"\d\d/\d\d/\d\d", b)), None),
                       "nouveau": "nouveau" in bas, "erratum": "erratum" in bas})
    return textes


def lire_texte(page: str) -> dict | None:
    """La page officielle d'un texte réglementaire : titre, numéro, numéro de la Gazette, enregistrement, loi, C.P."""
    principal = contenu_principal(page)
    if principal is None:
        return None
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", principal, re.S)
    m = re.fullmatch(r"(.+?)\s*:\s*((?:DORS|TR)/\d{4}-\d+)", texte(h1.group(1)) if h1 else "")
    if not m:
        return None
    paragraphes = [texte(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", principal, re.S)]
    i = next((i for i, p in enumerate(paragraphes) if p.startswith("Enregistrement")), None)
    if i is None:
        return None
    loi = paragraphes[i + 1] if i + 1 < len(paragraphes) and paragraphes[i + 1] == paragraphes[i + 1].upper() else ""
    enjeux = re.search(r"<h3>Enjeux</h3>\s*<p[^>]*>(.*?)</p>", principal, re.S)
    return {
        "titre": m.group(1), "numero": m.group(2),
        "gazette": next((p for p in paragraphes if p.startswith("La Gazette du Canada, Partie II")), ""),
        "enregistrement": paragraphes[i], "enregistre_le": date_fr(paragraphes[i]),
        "loi_page": loi, "cp": next((p for p in paragraphes if p.startswith("C.P. ")), ""),
        "enjeux": extrait(texte(enjeux.group(1))) if enjeux else "",
    }


# ---------- Partie I : avis de la Loi visant à bâtir le Canada ----------

def avis_batir(page: str, lien_page: str) -> list[dict]:
    """Les avis de la Loi visant à bâtir le Canada dans un numéro de la Partie I.

    Index d'un numéro régulier : section (h3), loi (h4), puis un lien par avis (li).
    Édition spéciale : le texte lui-même ; la loi est un h3 en majuscules et le titre de l'avis, le h4 qui suit.
    """
    principal = contenu_principal(page) or ""
    avis, h2_id, h3, h4 = [], "", "", ""
    for m in re.finditer(r"<(h[234])([^>]*)>(.*?)</\1>|<li>(.*?)</li>", principal, re.S):
        if m.group(1) == "h2":
            ident = re.search(r'id="([^"]+)"', m.group(2))
            h2_id, h3, h4 = (ident.group(1) if ident else ""), "", ""
        elif m.group(1) == "h3":
            h3, h4 = texte(m.group(3)), ""
        elif m.group(1) == "h4":
            h4 = texte(m.group(3))
            if BATIR.search(norme(h3)) and h4.startswith("Avis"):  # édition spéciale ou supplément
                avis.append({"titre": h4, "lien": lien_page + (f"#{h2_id}" if h2_id else "")})
        elif m.group(4) and BATIR.search(norme(h4)):
            lien = re.search(r'<a href="([^"]+)"', m.group(4))
            if lien:
                avis.append({"titre": texte(m.group(4)), "lien": urljoin(lien_page, lien.group(1))})
    return avis


def lire_avis(page: str, ancre: str | None) -> dict | None:
    """Le texte officiel d'un avis : la 1re phrase (ce que le gouvernement peut faire), le nom et la description."""
    principal = contenu_principal(page)
    if principal is None:
        return None
    if ancre:
        debut = principal.find(f'id="{ancre}"')
    else:
        trouve = re.search(r"<h3>\s*LOI VISANT À BÂTIR LE CANADA\s*</h3>", principal)
        debut = trouve.start() if trouve else -1
    if debut < 0:
        return None
    suite = principal[debut:]
    fin = re.search(r"<h2[ >]", suite[10:])
    section = suite[: fin.start() + 10] if fin else suite
    h4 = re.search(r"<h4>(.*?)</h4>", section, re.S)
    premier = re.search(r"<p[^>]*>(.*?)</p>", section, re.S)
    nom = re.search(r"Nom du projet</cite></h4>\s*<p[^>]*>(.*?)</p>", section, re.S)
    desc = re.search(r"Description du projet et emplacement</cite></h4>\s*<p[^>]*>(.*?)</p>", section, re.S)
    return {"titre": texte(h4.group(1)) if h4 else "", "texte": texte(premier.group(1)) if premier else "",
            "projet": texte(nom.group(1)) if nom else "", "description": extrait(texte(desc.group(1))) if desc else ""}


# ---------- Bureau des grands projets : la liste des projets ----------

def lire_projets(page: str) -> dict[str, dict]:
    """Chaque projet de la page (affiché 3 fois selon la taille d'écran) : nom, promoteur, secteur, emplacement."""
    projets = {}
    for m in re.finditer(r'<h2 class="h3"[^>]*><a href="(/fr/conseil-prive/bureau-grands-projets/projets/national/'
                         r'[a-z0-9-]+\.html)"[^>]*>(.*?)</a></h2>(.*?)(?=<h2 class="h3"|</section>)', page, re.S):
        lien, nom, reste = m.group(1), texte(m.group(2)), m.group(3)
        champs = dict((texte(a), texte(b)) for a, b in re.findall(r"<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>", reste, re.S))
        if lien not in projets and nom:
            projets[lien] = {"nom": nom, "promoteur": champs.get("Promoteur", ""), "secteur": champs.get("Secteur", ""),
                             "emplacement": champs.get("Emplacement", "")}
    return projets


def date_modifiee(page: str) -> str | None:
    """La « Date de modification » officielle d'une page canada.ca."""
    m = re.search(r'<time[^>]*property="dateModified"[^>]*>\s*(\d{4}-\d\d-\d\d)', page)
    return m.group(1) if m else None


# ---------- Événements ----------

def details(*paires) -> list[list[str]]:
    return [[a, b] for a, b in paires if b]


def evenement_reglement(t: dict, source: str) -> Evenement:
    """Un texte de la Partie II (règlement, décret, arrêté) : `t` = index + page officielle."""
    loi = t.get("loi") or t["loi_page"]
    projet = source == "grands_projets_ca"
    d = {k: t.get(k) for k in ("numero", "titre", "gazette", "enregistrement", "enregistre_le", "loi_page", "cp",
                               "enjeux", "numero_index", "titre_index", "nouveau", "speciale", "jour", "index")}
    d["loi"] = loi
    d["resume"] = t.get("enjeux") or ""
    d["details"] = details(("Numéro", t["numero"]), ("Loi", loi), ("Enregistré le", t.get("enregistre_le") or ""),
                           ("Décret", t.get("cp") or ""), ("Publié dans", t.get("gazette") or ""))
    return Evenement(
        source=source, official_id=t["numero"], category="canada",
        kind="decret_projet" if projet else "reglement",
        title=(f"Projet d'intérêt national : {t['titre']} ({t['numero']})" if projet
               else f"Gazette du Canada : {t['titre']} ({t['numero']})"),
        occurred_on=t.get("enregistre_le") or t["jour"], published_on=t["jour"], official_url=t["url"],
        sha256=canonique({k: d[k] for k in ("numero", "titre", "gazette", "enregistrement", "loi_page", "cp", "enjeux")}),
        parser_version=VERSION, entities=[loi], currency="CAD", data=d,
    )


def evenement_avis(a: dict) -> Evenement:
    """Un avis de la Partie I : le gouvernement peut inscrire un projet à l'annexe 1 de la Loi visant à bâtir le Canada."""
    projet = a.get("projet") or re.sub(r"^Avis\s*—\s*", "", a["titre"])
    ancre = a["lien"].split("#")[1] if "#" in a["lien"] else a["page"]
    d = {"projet": projet, "titre": a["titre"], "texte": a.get("texte", ""), "description": a.get("description", ""),
         "jour": a["jour"], "loi": "Loi visant à bâtir le Canada", "resume": a.get("texte", ""),
         "details": details(("Projet", projet), ("Loi", "Loi visant à bâtir le Canada"),
                            ("Publié dans", f"Gazette du Canada, Partie I, {a['jour']}"),
                            ("Description", a.get("description", "")))}
    return Evenement(
        source="grands_projets_ca", official_id=f"avis:{a['jour']}:{ancre}", category="canada", kind="avis_projet",
        title=f"Projet d'intérêt national : avis d'inscription possible, {projet}",
        occurred_on=a["jour"], published_on=a["jour"], official_url=a["lien"],
        sha256=canonique({k: d[k] for k in ("projet", "titre", "texte", "description", "jour")}),
        parser_version=VERSION, entities=["Bureau des grands projets"], currency="CAD", data=d,
        notes=["Étape officielle : l'avis paraît au moins 30 jours avant que le projet puisse être inscrit."],
    )


def evenement_projet(lien: str, p: dict, jour: str) -> Evenement:
    url = urljoin(BGP_LISTE, lien)
    d = dict(p, lien=url, details=details(("Promoteur", p["promoteur"]), ("Secteur", p["secteur"]),
                                          ("Emplacement", p["emplacement"])))
    return Evenement(
        source="grands_projets_ca", official_id="bgp:" + lien.rsplit("/", 1)[1].removesuffix(".html"),
        category="canada", kind="projet_soutenu",
        title=f"Bureau des grands projets : nouveau projet soutenu, {p['nom']}",
        occurred_on=jour, published_on=jour, official_url=url,
        sha256=canonique({k: p[k] for k in ("nom", "promoteur", "secteur", "emplacement")}),
        parser_version=VERSION, entities=[x for x in (p["promoteur"],) if x], currency="CAD", data=d,
        notes=["Un projet soutenu par le Bureau n'est pas forcément inscrit comme projet d'intérêt national."],
    )


# ---------- Contrôles ----------

@controle_source("gazette_ca")
def controles_reglement(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    m = NUMERO.fullmatch(d.get("numero") or "")
    return {
        "numero_dors_ou_tr": bool(m) and ev.official_url.endswith(f"{'sor-dors' if m.group(1) == 'DORS' else 'si-tr'}"
                                                                f"{int(m.group(3))}-fra.html"),
        "loi_liee_a_l_argent": bool(ARGENT.search(norme(d.get("loi")))),
        "titre_officiel_lu": bool(d.get("titre")),
        "meme_numero_que_l_index": d.get("numero_index") in (None, d.get("numero")),
        "date_d_enregistrement_lue": bool(d.get("enregistre_le")),
    }


@controle_source("grands_projets_ca")
def controles_projet(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    c = {"projet_nomme": bool(d.get("projet") or d.get("nom") or d.get("titre"))}
    if ev.kind == "projet_soutenu":
        c["page_du_bureau_des_grands_projets"] = ev.official_url.startswith(
            "https://www.canada.ca/fr/conseil-prive/bureau-grands-projets/projets/national/")
    else:
        c["loi_visant_a_batir_le_canada"] = bool(BATIR.search(norme(d.get("loi"))))
        c["lien_de_la_gazette"] = ev.official_url.startswith("https://gazette.gc.ca/rp-pr/")
    if ev.kind == "avis_projet":
        c["texte_officiel_de_l_avis"] = "annexe" in (d.get("texte") or "") and "inscrire" in (d.get("texte") or "")
    return c


# ---------- Lecture (partagée par les 2 sources, une fois par passage) ----------

def chemin_lus(donnees) -> Path:
    return Path(donnees) / "gazette" / "lus.json"


def _page(ctx, url: str) -> str:
    pages = ctx.cache.setdefault("gazette_pages", {})
    if url not in pages:
        pages[url] = decoder(ctx.client.get(url).contenu)
    return pages[url]


def _lire_numero(ctx, n: dict, reglements: list, projets: list) -> int:
    """Lit un numéro (ou un texte seul d'une édition spéciale). Retourne le nombre de textes retenus."""
    page = _page(ctx, n["lien"])
    if contenu_principal(page) is None:
        return -1  # lien brisé dans le fil officiel (page « Erreur 404 ») : rien à lire
    retenus = 0
    if n["partie"] == "p1":
        for a in avis_batir(page, n["lien"]):
            lien = a["lien"]
            base, _, ancre = lien.partition("#")
            detail = lire_avis(_page(ctx, base), ancre or None)
            if detail is None:
                raise RuntimeError(f"avis illisible : {lien}")
            projets.append(evenement_avis(dict(detail, titre=detail["titre"] or a["titre"], lien=lien, jour=n["jour"],
                                               page=base.rsplit("/", 1)[1].removesuffix("-fra.html"))))
            retenus += 1
        return retenus
    if n["page"] == "index":
        a_lire = [dict(x, url=urljoin(n["lien"], x["lien"])) for x in lire_index_p2(page)
                  if not x["erratum"] and (ARGENT.search(norme(x["loi"])) or BATIR.search(norme(x["loi"])))]
    else:  # édition spéciale : le fil pointe directement vers le texte
        a_lire = [{"url": n["lien"], "loi": None, "numero": None, "titre_index": "", "nouveau": True}]
    for x in a_lire:
        t = lire_texte(_page(ctx, x["url"]))
        if t is None:
            raise RuntimeError(f"texte illisible : {x['url']}")
        loi = x["loi"] or t["loi_page"]
        if not (ARGENT.search(norme(loi)) or BATIR.search(norme(loi))):
            continue  # édition spéciale sans lien avec l'argent
        t.update(url=x["url"], loi=x["loi"], numero_index=x["numero"], titre_index=x["titre_index"],
                 nouveau=x["nouveau"], speciale=n["speciale"], jour=n["jour"], index=n["lien"])
        source = "grands_projets_ca" if BATIR.search(norme(loi)) else "gazette_ca"
        (projets if source == "grands_projets_ca" else reglements).append(evenement_reglement(t, source))
        retenus += 1
    return retenus


def _lire(ctx) -> dict:
    if "gazette" in ctx.cache:
        return ctx.cache["gazette"]
    chemin = chemin_lus(ctx.donnees)
    lus = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    reglements: list[Evenement] = []
    projets: list[Evenement] = []
    for partie, fil in FILS.items():
        numeros = liens_du_fil(ctx.client.get(fil).contenu)
        if not numeros:
            raise RuntimeError(f"fil de la Gazette vide : {fil}")
        for n in sorted(numeros, key=lambda n: n["jour"]):
            if n["jour"] < limite or n["lien"] in lus:
                continue
            retenus = _lire_numero(ctx, n, reglements, projets)
            lus[n["lien"]] = {"lu_le": ctx.maintenant.date().isoformat(), "retenus": max(retenus, 0),
                              **({"note": "page introuvable (lien brisé dans le fil officiel)"} if retenus < 0 else {})}
    # Bureau des grands projets : un projet ajouté à la liste depuis la dernière lecture
    page = _page(ctx, BGP_LISTE)
    liste = lire_projets(page)
    if not liste:
        raise RuntimeError("liste du Bureau des grands projets illisible")
    connus_chemin = Path(ctx.donnees) / "gazette" / "grands_projets.json"
    connus = json.loads(connus_chemin.read_text(encoding="utf-8")) if connus_chemin.exists() else None
    jour = date_modifiee(page) or ctx.maintenant.date().isoformat()  # la liste était à jour au plus tard ce jour-là
    if connus is not None:
        for lien, p in liste.items():
            if lien not in connus:
                projets.append(evenement_projet(lien, p, jour))
    ctx.cache["gazette"] = {"reglements": reglements, "projets": projets, "lus": lus, "liste": liste}
    return ctx.cache["gazette"]


def _sauver(ctx, donnees: dict) -> None:
    dossier = Path(ctx.donnees) / "gazette"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin_lus(ctx.donnees).write_text(json.dumps(donnees["lus"], ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                       encoding="utf-8")
    (dossier / "grands_projets.json").write_text(
        json.dumps(donnees["liste"], ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _remettre(ctx, source: str) -> list[Evenement]:
    """Les infos d'une des 2 sources. Les numéros sont notés « lus » seulement quand les 2 sources ont reçu les leurs
    (sinon, un passage qui ne lance qu'une des 2 sources ferait perdre les infos de l'autre)."""
    donnees = _lire(ctx)
    pris = ctx.cache.setdefault("gazette_pris", set())
    pris.add(source)
    if pris == {"gazette_ca", "grands_projets_ca"}:
        _sauver(ctx, donnees)
    evs = donnees["reglements" if source == "gazette_ca" else "projets"]
    deja = Depot(ctx.donnees).ids_enregistres({source}, mois_max=6)
    return [ev for ev in evs if ev.official_id not in deja]


def collecter_reglements(ctx) -> list[Evenement]:
    return _remettre(ctx, "gazette_ca")


def collecter_projets(ctx) -> list[Evenement]:
    return _remettre(ctx, "grands_projets_ca")
