"""Télécharge 4 vraies fiches SEC (data.sec.gov/submissions) pour les tests : un fonds fermé (SWZ), une compagnie
(GME), une BDC (KBDC) et une compagnie qui dépose des N-PX (AFL). Lecture seule, 4 requêtes par seconde au plus."""
import gzip
import time
from pathlib import Path

import requests

UA = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com", "Accept-Encoding": "gzip, deflate"}
sortie = Path("labo/fixtures-emetteurs")
sortie.mkdir(parents=True, exist_ok=True)
for cik in (813623, 1326380, 1747172, 4977):
    r = requests.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=UA, timeout=30)
    r.raise_for_status()
    (sortie / f"submissions_{cik}.json.gz").write_bytes(gzip.compress(r.content, 9))
    print(cik, len(r.content))
    time.sleep(0.3)
