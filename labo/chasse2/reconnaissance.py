"""Chasse 2, étape 0 : reconnaissance. Mesure ce que la SEC offre VRAIMENT, avant de bâtir quoi que ce soit.

1. robots.txt de www.sec.gov : chaque adresse lue ici doit y être permise (404 = permis ; illisible = arrêt).
2. Prix (fichiers d'échecs de livraison) : la liste complète de la page officielle, le plus ancien fichier, et 3
   fichiers témoins (le plus ancien, janvier 2009, janvier 2012) : en-tête, lignes, symboles.
3. Rapports 10-K et 10-Q : submissions.zip (une requête, toutes les compagnies) : nombre de rapports originaux par année
   et taille totale déclarée ; puis 6 rapports témoins (3 de 2009, 3 de 2024) : taille du document principal et
   présence de la section « gestion » (MD&A, point 7 du 10-K, point 2 du 10-Q).
4. Fonds (13F) : la page officielle des jeux de données 13F et son plus ancien trimestre.
Déjà mesuré par le tournoi (labo/tournoi/donnees/journal.md) : formulaires 3-4-5 de 2006q1 à 2026q2 ; finances XBRL
(companyfacts.zip). Lecture polie : le client du robot (5 requêtes par seconde au plus à la SEC, courriel dans l'en-tête
comme la SEC le demande) ; 401 ou 403 = arrêt, on ne contourne jamais un refus.
"""
import html
import io
import json
import os
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin

ROBOT = Path(os.environ.get("TOURNOI_ROBOT", "principal/robot"))
sys.path.insert(0, str(ROBOT.resolve()))
from radar.collecteurs import inities, prix_sec  # noqa: E402
from radar.http import ErreurSource  # noqa: E402

CACHE = Path(os.environ.get("CHASSE2_CACHE", "cache2"))
SORTIE = Path("labo/chasse2")
SUBMISSIONS = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
PAGE_13F = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
ROBOTS = "https://www.sec.gov/robots.txt"
NOM = "Radar"
T0 = time.time()
journal, resultat = [], {}
CLIENT = None


def dire(t):
    t = f"[{(time.time() - T0) / 60:5.1f} min] {t}"
    print(t, flush=True)
    journal.append(t)


def client():
    global CLIENT
    if CLIENT is None:
        from radar.http import ClientPoli
        from radar.run import CONFIG, _charger_json
        CLIENT = ClientPoli(_charger_json(CONFIG).get("contact", ""), delai=600)
    return CLIENT


ROBOTS_OK = None


def permis(url):
    """robots.txt de la SEC : lu une fois. 404 = tout permis ; autre panne = arrêt (illisible = interdit)."""
    global ROBOTS_OK
    if ROBOTS_OK is None:
        try:
            texte = client().get(ROBOTS).contenu.decode("utf-8", "replace")
        except ErreurSource as exc:
            if "HTTP 404" in str(exc):
                texte = ""
            else:
                raise SystemExit(f"robots.txt de la SEC illisible ({exc}) : arrêt, rien n'est lu")
        ROBOTS_OK = robotparser.RobotFileParser()
        ROBOTS_OK.parse(texte.splitlines())
        resultat["robots_txt"] = {"lignes": len(texte.splitlines()), "texte": texte[:3000],
                                  "delai_demande": ROBOTS_OK.crawl_delay(NOM)}
        dire(f"robots.txt : {len(texte.splitlines())} lignes ; délai demandé : {ROBOTS_OK.crawl_delay(NOM)}")
    return ROBOTS_OK.can_fetch(NOM, url)


def lire(url, nom=None):
    """Contenu d'une adresse permise (gardé dans le cache si `nom`). 401 ou 403 : arrêt immédiat."""
    if not permis(url):
        raise SystemExit(f"INTERDIT par robots.txt : {url} : arrêt")
    if nom and (CACHE / nom).exists():
        return (CACHE / nom).read_bytes()
    try:
        t = client().get(url)
    except ErreurSource as exc:
        if re.search(r"HTTP 40[13]\b", str(exc)):
            raise SystemExit(f"INTERDIT par le site, arrêt sans contourner : {exc}")
        raise
    if nom:
        (CACHE / nom).parent.mkdir(parents=True, exist_ok=True)
        (CACHE / nom).write_bytes(t.contenu)
    return t.contenu


def ou_rien(url, nom=None):
    try:
        return lire(url, nom)
    except ErreurSource as exc:
        return f"ERREUR {exc}"


# ---------- 2. Les prix (fichiers d'échecs) ----------

LIEN_FTD = re.compile(r"""href=["']([^"']*cnsfails(\d{6})([ab])(?:_\d+)?\.zip)["']""", re.I)  # comme le tournoi


def prix():
    page = lire(prix_sec.PAGE).decode("utf-8", "replace")
    liens = {}
    for m in LIEN_FTD.finditer(page):
        cle = m.group(2) + m.group(3).lower()
        simple = not re.search(r"_\d+\.zip$", m.group(1), re.I)
        if cle not in liens or simple:
            liens[cle] = urljoin(prix_sec.PAGE, m.group(1))
    cles = sorted(liens)
    par_an = Counter(c[:4] for c in cles)
    attendu = {a: 24 for a in par_an}
    trous = {a: n for a, n in par_an.items() if n < attendu[a] and a not in (cles[0][:4], cles[-1][:4])}
    dire(f"fichiers d'échecs : {len(cles)} ({cles[0]} … {cles[-1]}) ; par année : {dict(sorted(par_an.items()))}")
    temoins = {}
    for cle in dict.fromkeys([cles[0], "200901a", "201201a"]):
        if cle not in liens:
            temoins[cle] = "absent de la page"
            continue
        contenu = lire(liens[cle], f"ftd/{cle}.zip")
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            lignes = z.read(z.namelist()[0]).decode("latin-1").splitlines()
        symboles = {l.split("|")[2] for l in lignes[1:] if l.count("|") >= 5}  # DATE|CUSIP|SYMBOL|QUANTITÉ|NOM|PRIX
        jours = sorted({l[:8] for l in lignes[1:] if l[:8].isdigit()})
        temoins[cle] = {"entete": lignes[0] if lignes else None, "entete_comme_aujourdhui": bool(lignes) and
                        lignes[0].strip() == prix_sec.ENTETE, "lignes": len(lignes) - 1, "symboles": len(symboles),
                        "jours": [jours[0], jours[-1]] if jours else None, "SPY": "SPY" in symboles,
                        "exemple": lignes[1:3]}
        dire(f"fichier {cle} : {temoins[cle]}")
    resultat["prix"] = {"fichiers": len(cles), "premier": cles[0], "dernier": cles[-1], "par_annee": dict(sorted(par_an.items())),
                        "annees_incompletes": trous, "temoins": temoins}


# ---------- 3. Les rapports 10-K et 10-Q ----------

FORMES = ("10-K", "10-Q")


def rapports():
    chemin = CACHE / "submissions.zip"
    if not chemin.exists():
        if not permis(SUBMISSIONS):
            raise SystemExit("INTERDIT par robots.txt : submissions.zip")
        lire(SUBMISSIONS, "submissions.zip")
    dire(f"submissions.zip : {chemin.stat().st_size / 1e9:.2f} Go")
    nombre, taille, cies = Counter(), Counter(), defaultdict(set)
    extensions, exemples = Counter(), defaultdict(list)
    with zipfile.ZipFile(chemin) as z:
        noms = z.namelist()
        dire(f"submissions.zip : {len(noms):,} fichiers")
        for i, nom in enumerate(noms):
            if not nom.endswith(".json"):
                continue
            try:
                d = json.loads(z.read(nom))
            except ValueError:
                continue
            r = d.get("filings", {}).get("recent", d) if "filings" in d else d
            formes = r.get("form") or []
            if not formes:
                continue
            cik = re.search(r"CIK(\d{10})", nom).group(1) if re.search(r"CIK(\d{10})", nom) else nom
            for k, f in enumerate(formes):
                if f not in FORMES:
                    continue
                an = (r["filingDate"][k] or "")[:4]
                nombre[(an, f)] += 1
                taille[(an, f)] += int((r.get("size") or [0] * len(formes))[k] or 0)
                cies[an].add(cik)
                doc = (r.get("primaryDocument") or [""] * len(formes))[k] or ""
                extensions[doc.rsplit(".", 1)[-1].lower() if "." in doc else "(aucun)"] += 1
                if an in ("2009", "2024") and len(exemples[(an, f)]) < 400:
                    exemples[(an, f)].append((cik, r["accessionNumber"][k], doc, r["filingDate"][k]))
            if i % 200000 == 0:
                dire(f"  {i:,}/{len(noms):,}")
    annees = sorted({a for a, _ in nombre})
    resultat["rapports"] = {
        "par_annee": {a: {"10-K": nombre[(a, "10-K")], "10-Q": nombre[(a, "10-Q")], "compagnies": len(cies[a]),
                          "taille_declaree_go": round((taille[(a, "10-K")] + taille[(a, "10-Q")]) / 1e9, 2)}
                      for a in annees},
        "documents_principaux": dict(extensions.most_common(8))}
    dire(f"rapports par année : {resultat['rapports']['par_annee']}")
    dire(f"documents principaux : {resultat['rapports']['documents_principaux']}")
    # 6 témoins : 3 de 2009 et 3 de 2024 (10-K et 10-Q), pris à intervalles réguliers dans la liste
    temoins = []
    for an, f, n in (("2009", "10-K", 2), ("2009", "10-Q", 1), ("2024", "10-K", 2), ("2024", "10-Q", 1)):
        liste = exemples[(an, f)]
        for j in range(n):
            cik, acc, doc, depot = liste[(j * 97 + 13) % len(liste)]
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
            b = ou_rien(url)
            if isinstance(b, str):
                temoins.append({"forme": f, "depot": depot, "url": url, "erreur": b})
                continue
            texte = html.unescape(re.sub(r"<[^>]+>", " ", b.decode("utf-8", "replace")))  # &#8217; → ’, &nbsp; → espace
            texte = re.sub(r"\s+", " ", texte)
            gestion = re.findall(r"management.{0,3}s discussion and analysis", texte, re.I)
            temoins.append({"forme": f, "depot": depot, "url": url, "octets": len(b), "mots": len(texte.split()),
                            "mentions_gestion": len(gestion)})
            dire(f"témoin {temoins[-1]}")
    resultat["rapports"]["temoins"] = temoins


# ---------- 4. Les fonds (13F) ----------

def fonds():
    b = ou_rien(PAGE_13F, None)
    if isinstance(b, str):
        resultat["fonds_13f"] = {"page": PAGE_13F, "erreur": b}
        dire(f"13F : {b}")
        return
    page = b.decode("utf-8", "replace")
    trimestres = sorted(set(re.findall(r"(\d{4})q([1-4])[^\"]*?form13f\.zip", page, re.I))
                        | set(re.findall(r"(\d{4})(?:-|_)?q([1-4])[^\"]*?13f[^\"]*?\.zip", page, re.I)))
    liens = re.findall(r'href="([^"]+\.zip)"', page, re.I)
    resultat["fonds_13f"] = {"page": PAGE_13F, "liens_zip": len(liens), "premiers_liens": sorted(liens)[:5],
                             "derniers_liens": sorted(liens)[-5:], "trimestres_lus": [f"{a}q{t}" for a, t in trimestres][:3]}
    dire(f"13F : {resultat['fonds_13f']}")


def main():
    dire("# Chasse 2, étape 0 : reconnaissance")
    for nom, faire in (("prix", prix), ("fonds_13f", fonds), ("rapports", rapports)):
        try:
            faire()
        except SystemExit as exc:  # refus (robots.txt, 401, 403) : plus AUCUNE lecture ; ce qui est mesuré est gardé
            resultat[nom] = {"arret": str(exc)}
            dire(f"{nom} : ARRÊT {exc}")
            break
        except Exception as exc:  # une partie qui casse ne cache pas les autres : notée telle quelle
            resultat[nom] = {"erreur": f"{type(exc).__name__}: {exc}"}
            dire(f"{nom} : ERREUR {type(exc).__name__}: {exc}")
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "reconnaissance.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (SORTIE / "reconnaissance_journal.md").write_text("\n".join(journal) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
