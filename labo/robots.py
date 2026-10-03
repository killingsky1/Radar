"""Le robots.txt de CHAQUE site lu par le robot (ou par le lot 2/3) : nos adresses exactes sont-elles permises ?"""

import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

SORTIE = Path("labo/resultats-robots")
UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
ADRESSES = [
    "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.20261001.idx",
    "https://www.sec.gov/Archives/edgar/data/1067983/000119312526352200/56757.xml",
    "https://www.sec.gov/Archives/edgar/data/1067983/000119312526352200/index.json",
    "https://www.sec.gov/files/company_tickers_exchange.json",
    "https://www.sec.gov/files/data/fails-deliver-data/cnsfails202609a.zip",
    "https://data.sec.gov/submissions/CIK0001067983.json",
    "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
    "https://www.whitehouse.gov/presidential-actions/feed/",
    "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm",
    "https://www.bankofcanada.ca/content_type/press-releases/feed/",
    "https://www.bankofcanada.ca/2026/09/fad-press-release-2026-09-02/",
    "https://www.federalregister.gov/api/v1/public-inspection-documents/current.json",
    "https://www.federalregister.gov/api/v1/documents.json",
    "https://www.federalregister.gov/documents/full_text/text/2026/10/02/2026-19000.txt",
    "https://public-inspection.federalregister.gov/2026-19000.pdf",
    "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip",
    "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20033000.pdf",
    "https://efdsearch.senate.gov/search/home/",
    "https://efdsearch.senate.gov/search/report/data/",
    "https://efdsearch.senate.gov/search/view/ptr/00000000-0000-0000-0000-000000000000/",
    "https://api.io.canada.ca/io-server/gc/news/fr/v2",
    "https://www.canada.ca/fr/ministere-defense-nationale/nouvelles/2026/10/x.html",
    "https://api.fda.gov/drug/drugsfda.json",
    "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm",
    "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220605Orig1s000ltr.pdf",
    "https://canadabuys.canada.ca/opendata/pub/2026-2027-contractHistory-contratsOctroyes.csv",
    "https://open.canada.ca/data/api/action/package_show",
    "https://open.canada.ca/data/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b/resource/x/download/contracts.csv",
    "https://press.spglobal.com/index.php",
]

SORTIE.mkdir(parents=True, exist_ok=True)
lignes = ["# robots.txt de chaque site", ""]
lus = {}
for url in ADRESSES:
    p = urlparse(url)
    hote = f"{p.scheme}://{p.netloc}"
    ua = UA_SEC if p.netloc.endswith("sec.gov") else UA
    if hote not in lus:
        time.sleep(0.6)
        try:
            r = requests.get(f"{hote}/robots.txt", headers={"User-Agent": ua}, timeout=30)
            lus[hote] = (r.status_code, r.text if r.status_code == 200 else "")
            (SORTIE / f"{p.netloc}.txt").write_text(f"HTTP {r.status_code}\n\n{r.text}", encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            lus[hote] = (f"erreur {e}", "")
    statut, texte = lus[hote]
    if statut != 200:
        verdict = "PAS DE robots.txt (permis)" if statut == 404 else f"robots.txt illisible ({statut})"
    else:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(texte.splitlines())
        verdict = "PERMIS" if rp.can_fetch(ua, url) else "INTERDIT"
        delai = rp.crawl_delay(ua)
        if delai:
            verdict += f" (délai demandé : {delai} s)"
    lignes.append(f"- {verdict} · {url}")
(SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
print("\n".join(lignes))
