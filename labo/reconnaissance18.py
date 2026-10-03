"""Lot 3c (Canada), 3e passage : ce qui manquait au 1er (mêmes règles : robots.txt d'abord, 401/403 = interdit,
Crawl-delay respecté, sinon 1,5 s par site ; rien n'est contourné).

- Santé Canada : la liste complète (une fois) → extrait compact des avis de 2026 + 3 fiches détaillées (?id=) ;
- Contrats : types des champs et comptes par trimestre (API du portail ouvert, 20 s entre deux requêtes) ;
- CCC : la page des rapports et le dernier rapport des transactions signées ;
- Statistique Canada, Gazette, Bureau de la concurrence (FR), Bureau des grands projets, LEGISinfo (une fiche).
"""
import json
import re
import subprocess
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-lot3c3")
SORTIE.mkdir(parents=True, exist_ok=True)
RESSOURCE = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"
CKAN = "https://open.canada.ca/data/api/action/"
NOC = "https://health-products.canada.ca/api/notice-of-compliance/"
BGP = "https://www.canada.ca/en/privy-council/major-projects-office/"
MAX_GARDE = 6_000_000
MAX_LU = 60_000_000  # au-delà, on arrête de lire (la taille exacte n'est alors pas connue)
LIENS = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
INTERESSANTS = re.compile(r"\.(csv|json|xml|pdf|xlsx|atom|rss|zip)\b|export|download|telecharg|terms|conditions|avis|notice"
                          r"|licen|disclosure|divulgation|transaction|feed", re.I)
robots, resultats, dernier = {}, {}, {}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=(20, 40))
            robots[hote] = {"statut": r.status_code, "texte": r.text[:4000]}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        delai = rp.crawl_delay(UA) if robots[hote]["statut"] == 200 else None
        robots[hote]["delai"] = float(delai) if delai else None
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
    return robots[hote]["rp"]


def attendre(hote):
    reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)


def requete(url, tete):
    """Suit les redirections à la main : chaque nouveau site passe par son robots.txt et son délai."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not regles(hote).can_fetch(UA, url):
            return None, url
        attendre(hote)
        r = (requests.head if tete else requests.get)(url, headers=H, timeout=(20, 180), stream=not tete,
                                                      allow_redirects=False)
        dernier[hote] = time.monotonic()
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            r.close()
            url = urljoin(url, r.headers["location"])
            continue
        return r, url
    raise RuntimeError("trop de redirections")


def visiter(nom, url, tete=False, garde=MAX_GARDE):
    res = {"url": url}
    try:
        r, finale = requete(url, tete)
        res["permis_robots_txt"] = r is not None
        res["url_finale"] = finale
        if r is not None and tete:
            res.update({"statut": r.status_code, "entetes": dict(r.headers)})
        elif r is not None:
            morceaux, taille = [], 0
            for m in r.iter_content(65536):
                taille += len(m)
                if taille - len(m) < garde:
                    morceaux.append(m)
                if taille > MAX_LU:
                    break
            r.close()
            corps = b"".join(morceaux)[:garde]
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"),
                        "taille": taille, "complet": taille <= garde, "lecture_arretee": taille > MAX_LU,
                        "entetes": {k: v for k, v in r.headers.items()
                                    if k.lower() in ("last-modified", "etag", "content-length", "cache-control",
                                                     "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "content-encoding")},
                        "debut": corps[:500].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(corps)
            if "html" in (r.headers.get("content-type") or ""):
                texte = corps.decode("utf-8", "replace")
                res["liens"] = sorted({urljoin(finale, h) for h in LIENS.findall(texte) if INTERESSANTS.search(h)})[:150]
    except Exception as exc:  # noqa: BLE001
        res["erreur"] = str(exc)[:300]
    resultats[nom] = res
    print(nom, "permis" if res.get("permis_robots_txt") else "INTERDIT/erreur", res.get("statut"), res.get("taille"),
          res.get("type"), res.get("erreur", ""), flush=True)





# ---------- CCC : les 2 derniers rapports trimestriels des transactions signées ----------
for k, d in enumerate(("https://www.ccc.ca/wp-content/uploads/2026/07/TD-2026-2027-Q1.pdf",
                       "https://www.ccc.ca/wp-content/uploads/2026/06/TD-2025-2026-Q4.pdf")):
    visiter(f"ccc_td_{k}", d)
    f = SORTIE / f"ccc_td_{k}.bin"
    if f.exists() and f.read_bytes()[:4] == b"%PDF":
        subprocess.run(["pdftotext", "-layout", str(f), str(SORTIE / f"ccc_td_{k}.txt")], check=False)

# ---------- Statistique Canada : la liste officielle des grands indicateurs, en français ----------
visiter("statcan_cal1_fr", "https://www150.statcan.gc.ca/n1/dai-quo/cal1-fra.htm")

# ---------- Gazette : 6 numéros de la Partie II et 4 de la Partie I (index en français) ----------
for jour in ("2026-09-09", "2026-08-26", "2026-08-12", "2026-07-29", "2026-07-15", "2026-07-01"):
    visiter(f"gazette_p2_{jour}", f"https://gazette.gc.ca/rp-pr/p2/2026/{jour}/html/index-fra.html")
for jour in ("2026-10-03", "2026-09-26", "2026-09-19", "2026-08-01"):
    visiter(f"gazette_p1_{jour}", f"https://gazette.gc.ca/rp-pr/p1/2026/{jour}/html/index-fra.html")
visiter("gazette_p1_liste", "https://gazette.gc.ca/rp-pr/p1/2026/index-fra.html")

# ---------- Contrats : les dernières lignes entrées (_id décroissant) et le total d'un trimestre ----------
CHAMPS = "_id,reference_number,owner_org,vendor_name,contract_date,contract_value,original_value,amendment_value,reporting_period"
visiter("contrats_derniers", CKAN + f"datastore_search?resource_id={RESSOURCE}&sort=" + quote("_id desc")
        + f"&limit=200&fields={CHAMPS}")
for periode in ("2026-2027-Q1", "2026-2027-Q2"):
    visiter(f"contrats_total_{periode}", CKAN + f"datastore_search?resource_id={RESSOURCE}&limit=0&filters="
            + quote(json.dumps({"reporting_period": periode})))

# ---------- Bureau des grands projets : les pages en français ----------
BGP_FR = "https://www.canada.ca/fr/conseil-prive/bureau-grands-projets/"
visiter("bgp_nationaux_fr", BGP_FR + "projets/national.html")
visiter("bgp_ouest_fr", BGP_FR + "projets/national/ouest.html")
visiter("bgp_nouvelles_fr", BGP_FR + "nouvelles.html")

for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
