"""Documents officiels du Congrès pour les tests du lot 3b (chefs, comités, H.R. 7008 et ses votes).

robots.txt vérifié le 3 oct. 2026 (labo/resultats-lot3b) : tout est permis. Une requête par seconde au plus.
"""
import gzip
import re
import time
from pathlib import Path

import urllib.robotparser

import requests

H = {"User-Agent": "Radar projet personnel", "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/fixtures-congres")
SORTIE.mkdir(parents=True, exist_ok=True)


ROBOTS = urllib.robotparser.RobotFileParser("https://www.senate.gov/robots.txt")
ROBOTS.read()


def lire(url, nom):
    if "senate.gov" in url and not ROBOTS.can_fetch(H["User-Agent"], url):
        raise SystemExit(f"robots.txt interdit {url}")
    r = requests.get(url, headers=H, timeout=60)
    r.raise_for_status()
    (SORTIE / f"{nom}.gz").write_bytes(gzip.compress(r.content, 9))
    print(nom, r.status_code, len(r.content))
    time.sleep(1.1)
    return r.text


for url, nom in (
    ("https://clerk.house.gov/xml/lists/MemberData.xml", "MemberData.xml"),
    ("https://www.house.gov/leadership", "chambre_chefs.html"),
    ("https://www.senate.gov/senators/leadership.htm", "senat_chefs.html"),
    ("https://www.govinfo.gov/bulkdata/BILLSTATUS/119/hr/BILLSTATUS-119hr7008.xml", "BILLSTATUS-119hr7008.xml"),
    ("https://clerk.house.gov/evs/2026/roll280.xml", "roll280.xml"),
    ("https://clerk.house.gov/evs/2026/roll279.xml", "roll279.xml"),
    ("https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_00253.xml", "vote_119_2_00253.xml"),
):
    lire(url, nom)

accueil = lire("https://www.senate.gov/committees/index.htm", "senat_comites.html")
codes = sorted(set(re.findall(r"committee_memberships_([A-Z]{4})\.htm", accueil)))
print("comités du Sénat trouvés :", len(codes), codes)
for c in codes:
    lire(f"https://www.senate.gov/general/committee_membership/committee_memberships_{c}.xml", f"senat_{c}.xml")
