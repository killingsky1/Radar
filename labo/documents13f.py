"""Vrais documents pour les tests du lecteur 13F (rien n'est modifié : on sauve les octets reçus)."""

import json
import re
import time
from pathlib import Path

import requests

SORTIE = Path("labo/resultats-13f")
UA = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com"}  # SEC seulement
FONDS = [1067983, 2026053, 1536411, 898286, 1166559]
s = requests.Session()
journal = []


def get(url):
    time.sleep(0.3)
    r = s.get(url, headers={**UA, "Accept-Encoding": "gzip, deflate"}, timeout=120)
    journal.append(f"- {r.status_code} · {len(r.content)} octets · {url}")
    r.raise_for_status()
    return r.content


SORTIE.mkdir(parents=True, exist_ok=True)
(SORTIE / "master.20260814.idx").write_bytes(get("https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260814.idx"))
for cik in FONDS:
    sub = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    (SORTIE / f"submissions_{cik}.json").write_bytes(sub)
    rec = json.loads(sub)["filings"]["recent"]
    vus = 0
    for forme, acc in zip(rec["form"], rec["accessionNumber"]):
        if forme != "13F-HR" or vus >= 2:
            continue
        vus += 1
        dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        idx = get(f"{dossier}/index.json")
        (SORTIE / f"{acc}.index.json").write_bytes(idx)
        for f in json.loads(idx)["directory"]["item"]:
            if f["name"].endswith(".xml"):
                (SORTIE / f"{acc}.{f['name']}").write_bytes(get(f"{dossier}/{f['name']}"))
page = get("https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data")
fichiers = sorted(set(re.findall(r"/files/data/fails-deliver-data/(cnsfails\d{6}[ab]\.zip)", page.decode("utf-8", "replace"))))
journal.append(f"- fichiers fails-to-deliver récents : {fichiers[-6:]}")
for f in fichiers[-2:]:
    (SORTIE / f).write_bytes(get(f"https://www.sec.gov/files/data/fails-deliver-data/{f}"))
(SORTIE / "journal.md").write_text("\n".join(journal) + "\n", encoding="utf-8")
print("\n".join(journal))
