"""Lot 3c (Canada) : les 9 sources. robots.txt d'abord (401/403 = interdit), lecture seule, petits échantillons.

Le délai demandé par chaque robots.txt (Crawl-delay) est respecté (open.canada.ca : 20 s), sinon 1,5 s par site.
Rien n'est contourné : une page refusée reste refusée. Les gros fichiers ne sont pas téléchargés (HEAD seulement).
"""
import json
import re
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-lot3c")
SORTIE.mkdir(parents=True, exist_ok=True)
CONTRATS = "d8f85d91-7dec-4fd1-8055-483b77225d8b"
RESSOURCE = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"
NOC = "https://health-products.canada.ca/api/notice-of-compliance/"
CIBLES = {
    # Santé Canada : avis de conformité (API officielle)
    "noc_doc": "https://health-products.canada.ca/api/documentation/noc-documentation-en.html",
    "noc_racine": NOC,
    "noc_main": NOC + "noticeofcompliancemain/?lang=en&type=json",
    "noc_produit": NOC + "drugproduct/?lang=en&type=json",
    "noc_page_db": "https://www.canada.ca/en/health-canada/services/drugs-health-products/drug-products/notice-compliance/database.html",
    # Corporation commerciale canadienne
    "ccc_transparence": "https://www.ccc.ca/en/about/transparency-and-disclosure/",
    "ccc_divulgation": "https://www.ccc.ca/en/about/disclosure/",
    "ccc_annonces": "https://www.ccc.ca/en/announcements/",
    "ccc_fil": "https://www.ccc.ca/feed/",
    # Statistique Canada : Le Quotidien
    "statcan_atom_fr": "https://www150.statcan.gc.ca/n1/fr/rss/dai-quo/0-fra.atom",
    "statcan_atom_en": "https://www150.statcan.gc.ca/n1/en/rss/dai-quo/0-eng.atom",
    "statcan_calendrier": "https://www150.statcan.gc.ca/n1/dai-quo/cal2-eng.htm",
    "statcan_licence": "https://www.statcan.gc.ca/en/terms-conditions/open-licence",
    # Gazette du Canada
    "gazette_p2_fr": "https://gazette.gc.ca/rss/p2-fra.xml",
    "gazette_p2_en": "https://gazette.gc.ca/rss/p2-eng.xml",
    "gazette_p1_en": "https://gazette.gc.ca/rss/p1-eng.xml",
    "gazette_2026": "https://gazette.gc.ca/rp-pr/p2/2026/index-eng.html",
    "gazette_surtaxe": "https://gazette.gc.ca/rp-pr/p2/2026/2026-07-01/html/sor-dors119-eng.html",
    # Bureau de la concurrence
    "concurrence_rapport": "https://competition-bureau.canada.ca/en/mergers-and-acquisitions/report-concluded-merger-reviews",
    "concurrence_rapport_fr": "https://bureau-concurrence.canada.ca/fr/fusions-et-acquisitions/rapport-sur-les-examens-de-fusion-termines",
    # Sanctions canadiennes
    "sanctions_page": "https://www.international.gc.ca/world-monde/international_relations-relations_internationales/"
                      "sanctions/consolidated-consolide.aspx?lang=eng",
    "sanctions_xml": "https://www.international.gc.ca/world-monde/assets/office_docs/international_relations-"
                     "relations_internationales/sanctions/sema-lmes.xml",
    # LEGISinfo
    "legisinfo_json_fr": "https://www.parl.ca/legisinfo/fr/projets-de-loi/json?parlsession=45-1",
    "legisinfo_json_en": "https://www.parl.ca/legisinfo/en/bills/json?parlsession=45-1",
    "legisinfo_c15": "https://www.parl.ca/legisinfo/en/bill/45-1/c-15/json",
    "legisinfo_aide": "https://www.parl.ca/legisinfo/en/help",
    "parl_avis": "https://www.parl.ca/ImportantNotices-e.html",
    "communes_avis": "https://www.ourcommons.ca/en/important-notices",
    # Grands projets d'intérêt national (Loi visant à bâtir le Canada, annexe 1)
    "projets_page": "https://www.canada.ca/en/one-canadian-economy/services/building-canada-act-projects-national-interest.html",
    "projets_bgp": "https://www.canada.ca/en/privy-council/major-projects-office.html",
    "loi_b989_index": "https://laws-lois.justice.gc.ca/eng/acts/B-9.89/",
    "loi_b989_xml": "https://laws-lois.justice.gc.ca/eng/XML/B-9.89.xml",
    "loi_b989_xml_fr": "https://laws-lois.justice.gc.ca/fra/XML/B-9.89.xml",
    "decret_reproduction": "https://laws-lois.justice.gc.ca/eng/regulations/SI-97-5/FullText.html",
    # Contrats de plus de 10 000 $ (portail du gouvernement ouvert : 20 s entre deux requêtes)
    "contrats_paquet": f"https://open.canada.ca/data/api/action/package_show?id={CONTRATS}",
    "contrats_datastore": f"https://open.canada.ca/data/api/action/datastore_search?resource_id={RESSOURCE}&limit=3"
                          "&sort=contract_date%20desc",
    "contrats_recherche": "https://search.open.canada.ca/contracts/",
    "licence_ouverte": "https://open.canada.ca/en/open-government-licence-canada",
    # Conditions générales de Canada.ca
    "canada_conditions": "https://www.canada.ca/en/transparency/terms.html",
}
HEAD_SEULEMENT = {
    "contrats_csv": f"https://open.canada.ca/data/dataset/{CONTRATS}/resource/{RESSOURCE}/download/contracts.csv",
}
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


def visiter(nom, url, tete=False):
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
                if taille - len(m) < MAX_GARDE:
                    morceaux.append(m)
                if taille > MAX_LU:
                    break
            r.close()
            corps = b"".join(morceaux)[:MAX_GARDE]
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"),
                        "taille": taille, "complet": taille <= MAX_GARDE, "lecture_arretee": taille > MAX_LU,
                        "entetes": {k: v for k, v in r.headers.items()
                                    if k.lower() in ("last-modified", "etag", "content-length", "cache-control",
                                                     "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining")},
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


for nom, url in CIBLES.items():
    visiter(nom, url)
for nom, url in HEAD_SEULEMENT.items():
    visiter(nom, url, tete=True)

for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
