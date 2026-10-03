"""Suite des vrais fichiers de la livraison 2 (le 1er passage a planté après Santé Canada : nom de variable
réutilisé dans mon script). Mêmes règles. Mêmes règles : robots.txt d'abord (401/403 = interdit), Crawl-delay respecté, sinon 1,5 s par site.

Tout est enregistré compressé (gzip) dans labo/fixtures-canada3c, avec pages.json : adresse -> fichier.
"""
import gzip
import json
import re
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/fixtures-canada3c2")
SORTIE.mkdir(parents=True, exist_ok=True)
AUJOURDHUI = date.today()
LOIS = re.compile(r"^(Tarif des douanes|Mesures économiques spéciales|Licences d’exportation et d’importation"
                  r"|Mesures spéciales d’importation|Investir au Canada|Douanes \(Loi|Taxe d’accise"
                  r"|Tribunal canadien du commerce extérieur|Accord |Protocole d’adhésion|Exécution du budget|Libre-échange"
                  r"|Bâtir le Canada)")
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






pages = json.loads((SORTIE / "pages.json").read_text(encoding="utf-8")) if (SORTIE / "pages.json").exists() else {}


def garder(nom, url):
    """Télécharge (robots.txt respecté) et garde le contenu complet, compressé."""
    visiter(nom, url, garde=MAX_LU)
    f = SORTIE / f"{nom}.bin"
    if resultats[nom].get("statut") == 200 and f.exists():
        (SORTIE / f"{nom}.gz").write_bytes(gzip.compress(f.read_bytes(), mtime=0))
        pages[resultats[nom]["url"]] = f"{nom}.gz"
    if f.exists():
        f.unlink()
    return resultats[nom].get("statut") == 200


def contenu(nom):
    return gzip.decompress((SORTIE / f"{nom}.gz").read_bytes())


def date_du_lien(lien):
    m = re.search(r"/(\d{4}-\d\d-\d\d)", lien)
    return date.fromisoformat(m.group(1)) if m else None



NOC = "https://health-products.canada.ca/api/notice-of-compliance/"
CKAN = "https://open.canada.ca/data/api/action/"
RESSOURCE = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"

# La fiche publique d'un avis de conformité : quelle adresse répond ?
for nom, url in (("noc_fiche_1", "https://health-products.canada.ca/noc-ac/info.do?lang=fr&no=38368"),
                 ("noc_fiche_2", "https://health-products.canada.ca/noc-ac/info.do?no=38368&lang=fr"),
                 ("noc_fiche_3", "https://health-products.canada.ca/noc-ac/info.do?lang=fre&no=38368")):
    garder(nom, url)

# Contrats : une vraie page de l'API par trimestre suivi, et la page publique d'un contrat (2 langues)
CHAMPS = ("_id,reference_number,owner_org,owner_org_title,vendor_name,contract_date,contract_value,original_value,"
          "amendment_value,description_fr,instrument_type,reporting_period")
for periode in ("2026-2027-Q1", "2026-2027-Q2", "2026-2027-Q3"):
    garder(f"contrats_{periode}_page0", CKAN + "datastore_search?resource_id=" + RESSOURCE + "&filters="
           + quote(json.dumps({"reporting_period": periode})) + "&sort=" + quote("_id desc")
           + "&limit=1000&offset=0&fields=" + CHAMPS)
for nom, url in (("contrat_fiche_en", "https://search.open.canada.ca/contracts/record/cbsa-asfc,C-2025-2026-Q3-908"),
                 ("contrat_fiche_fr", "https://rechercher.ouvert.canada.ca/contrats/record/cbsa-asfc,C-2025-2026-Q3-908")):
    garder(nom, url)

# CCC : la page des rapports et les 2 derniers rapports des transactions signées
garder("ccc_rapports", "https://www.ccc.ca/en/about/corporate-reports/")
garder("ccc_td_2026_q1", "https://www.ccc.ca/wp-content/uploads/2026/07/TD-2026-2027-Q1.pdf")
garder("ccc_td_2025_q4", "https://www.ccc.ca/wp-content/uploads/2026/06/TD-2025-2026-Q4.pdf")

(SORTIE / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots_b.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats_b.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
