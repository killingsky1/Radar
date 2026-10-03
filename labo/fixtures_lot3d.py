"""Lot 3d, livraison 1 : les VRAIES données des tests (Trésor : Fiscal Data ; douane : CSMS). Mêmes règles : robots.txt
d'abord, lu avec notre identification ; 401/403 = interdit ; Crawl-delay respecté, sinon 1,5 s par site ; clés masquées.

Tout est gardé compressé (gzip) dans labo/fixtures-lot3d, avec pages.json : adresse -> fichier.
"""
import json
import re
import time
import urllib.robotparser
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/fixtures-lot3d")
SORTIE.mkdir(parents=True, exist_ok=True)
MAX_GARDE = 6_000_000
MAX_LU = 60_000_000
LIENS = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
INTERESSANTS = re.compile(r"\.(csv|json|xml|pdf|xlsx|atom|rss|zip)\b|rss|feed|api|export|download|terms|conditions"
                          r"|legal|copyright|policy|polic|exclu|holding|investments|press|news|bulletin|fails", re.I)
robots, resultats, dernier = {}, {}, {}
AUJ = date.today()
# Des pages publiques contiennent parfois des clés d'accès (ex. une clé Mapbox dans la page de NBIM) : on ne les garde
# jamais. Elles sont masquées avant tout enregistrement.
CLES = [re.compile(rb"\b(?:pk|sk|tk)\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"), re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
        re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        re.compile(rb"(?i)((?:access_?token|api_?key|apikey|secret|token)[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._~+/-]{16,}")]


def masquer(contenu, type_contenu):
    if not re.search(r"html|json|xml|javascript|text", type_contenu or ""):
        return contenu, 0
    n = 0
    for motif in CLES:
        contenu, k = motif.subn(lambda m: (m.group(1) if m.groups() else b"") + b"[cle masquee]", contenu)
        n += k
    return contenu, n


def ua(hote):
    return UA_SEC if hote.endswith("sec.gov") else UA


def entetes(hote):
    return {"User-Agent": ua(hote), "Accept-Encoding": "gzip, deflate"}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=entetes(hote), timeout=(20, 40), allow_redirects=True)
            robots[hote] = {"statut": r.status_code, "texte": r.text[:6000], "url_finale": r.url}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        delai = rp.crawl_delay(ua(hote)) if robots[hote].get("statut") == 200 else None
        robots[hote]["delai"] = float(delai) if delai else None
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
        print("robots.txt", hote, robots[hote].get("statut"), "délai", robots[hote]["delai"], flush=True)
    return robots[hote]["rp"]


def attendre(hote):
    reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)


def requete(url, corps=None):
    """Suit les redirections à la main : chaque nouveau site passe par son robots.txt et son délai."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not regles(hote).can_fetch(ua(hote), url):
            return None, url
        attendre(hote)
        if corps is None:
            r = requests.get(url, headers=entetes(hote), timeout=(20, 180), stream=True, allow_redirects=False)
        else:
            r = requests.post(url, headers={**entetes(hote), "Content-Type": "application/json"}, data=json.dumps(corps),
                              timeout=(20, 180), stream=True, allow_redirects=False)
        dernier[hote] = time.monotonic()
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            r.close()
            url = urljoin(url, r.headers["location"])
            corps = None
            continue
        return r, url
    raise RuntimeError("trop de redirections")


def visiter(nom, url, corps=None, garde=MAX_GARDE):
    res = {"url": url, "post": corps}
    try:
        r, finale = requete(url, corps)
        res["permis_robots_txt"] = r is not None
        res["url_finale"] = finale
        if r is not None:
            morceaux, taille = [], 0
            for m in r.iter_content(65536):
                taille += len(m)
                if taille - len(m) < garde:
                    morceaux.append(m)
                if taille > MAX_LU:
                    break
            r.close()
            contenu, masquees = masquer(b"".join(morceaux)[:garde], r.headers.get("content-type"))
            res["cles_masquees"] = masquees
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"), "taille": taille,
                        "complet": taille <= garde,
                        "entetes": {k: v for k, v in r.headers.items()
                                    if k.lower() in ("last-modified", "etag", "content-length", "cache-control", "retry-after",
                                                     "x-ratelimit-limit", "x-ratelimit-remaining", "content-encoding",
                                                     "server")},
                        "debut": contenu[:600].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(contenu)
            if "html" in (r.headers.get("content-type") or ""):
                texte = contenu.decode("utf-8", "replace")
                res["liens"] = sorted({urljoin(finale, h) for h in LIENS.findall(texte) if INTERESSANTS.search(h)})[:200]
    except Exception as exc:  # noqa: BLE001
        res["erreur"] = str(exc)[:300]
    resultats[nom] = res
    print(nom, "permis" if res.get("permis_robots_txt") else "INTERDIT/erreur", res.get("statut"), res.get("taille"),
          res.get("type"), res.get("erreur", ""), flush=True)
    return res




import gzip  # noqa: E402

pages = {}


def garder(nom, url, corps=None):
    r = visiter(nom, url, corps)
    f = SORTIE / f"{nom}.bin"
    if r.get("statut") == 200 and f.exists():
        (SORTIE / f"{nom}.gz").write_bytes(gzip.compress(f.read_bytes(), 9))
        pages[url] = f"{nom}.gz"
    f.unlink(missing_ok=True)
    return r


FD = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
# Adjudications : les plus récentes (tous types) et l'historique des obligations (Note, Bond) pour les comparaisons
garder("fd_adjudications_recentes", FD + "v1/accounting/od/auctions_query?sort=-auction_date&page[size]=100")
garder("fd_obligations_historique", FD + "v1/accounting/od/auctions_query?filter=security_type:in:(Note,Bond)"
       "&sort=-auction_date&page[size]=300")
# Déficit mensuel (état mensuel du Trésor) et calendrier officiel des publications
garder("fd_etat_mensuel", FD + "v1/accounting/mts/mts_table_1?sort=-record_date&page[size]=60")
garder("fd_calendrier", "https://api.fiscaldata.treasury.gov/services/calendar/release")
garder("fd_metadonnees", "https://api.fiscaldata.treasury.gov/services/dtg/metadata/")
# Documents officiels des résultats (adresse donnée par la recherche : à vérifier) et page du jeu de données
for nom, url in (("fd_resultat_pdf", "https://fiscaldata.treasury.gov/static-data/published-reports/auctions-query/results/"
                  "R_20260924_3.pdf"),
                 ("fd_resultat_xml", "https://fiscaldata.treasury.gov/static-data/published-reports/auctions-query/results/"
                  "R_20260924_3.xml"),
                 ("fd_page_adjudications", "https://fiscaldata.treasury.gov/page-data/datasets/"
                  "treasury-securities-auctions-data/page-data.json"),
                 ("fd_page_etat_mensuel", "https://fiscaldata.treasury.gov/page-data/datasets/"
                  "monthly-treasury-statement/page-data.json")):
    garder(nom, url)

# Douane : le flux CSMS (100 derniers messages), 2 messages sur les surtaxes, la politique du site de la douane
csms = garder("csms_rss", "https://content.govdelivery.com/accounts/USDHSCBP/widgets/USDHSCBP_WIDGET_2.rss")
f = SORTIE / "csms_rss.gz"
if f.exists():
    t = gzip.decompress(f.read_bytes()).decode("utf-8", "replace")
    choisis = []
    for item in re.findall(r"<item>(.*?)</item>", t, re.S):
        titre = re.search(r"<title>(.*?)</title>", item, re.S).group(1)
        lien = re.search(r"<link>(.*?)</link>", item, re.S).group(1).strip()
        if re.search(r"Section 338|Section 232", titre) and len(choisis) < 2:
            choisis.append(lien)
    for i, lien in enumerate(choisis):
        garder(f"csms_message_{i}", lien)
for nom, url in (("cbp_politique", "https://www.cbp.gov/site-policy-notices"),
                 ("cbp_politique_vie_privee", "https://www.cbp.gov/site-policy-notices/privacy-policy")):
    garder(nom, url)

(SORTIE / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(
    {"pages": resultats, "robots": {h: {k: v for k, v in r.items() if k != "rp"} for h, r in robots.items()}},
    ensure_ascii=False, indent=1), encoding="utf-8")
print("fini")
