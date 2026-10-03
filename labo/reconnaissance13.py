"""Lot 3b (politiciens) : robots.txt d'abord, puis un échantillon de chaque source SEULEMENT si c'est permis.

Chefs et comités (Chambre, Sénat), votes, suivi de H.R. 7008 (govinfo), lobbying (LDA.gov), OGE 278-T.
Lecture seule, une requête à la fois, au plus 1 par seconde par site. Le courriel n'est envoyé à personne.
"""
import json
import re
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-lot3b")
SORTIE.mkdir(parents=True, exist_ok=True)
CIBLES = {
    "chambre_membres": "https://clerk.house.gov/xml/lists/MemberData.xml",
    "senat_comite_banques": "https://www.senate.gov/general/committee_membership/committee_memberships_SSBK.xml",
    "senat_chefs": "https://www.senate.gov/senators/leadership.htm",
    "chambre_chefs": "https://www.house.gov/leadership",
    "hr7008_statut": "https://www.govinfo.gov/bulkdata/BILLSTATUS/119/hr/BILLSTATUS-119hr7008.xml",
    "vote_chambre_hr7008": "https://clerk.house.gov/evs/2026/roll280.xml",
    "votes_senat_liste": "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml",
    "lda_api": "https://lda.gov/api/v1/filings/?filing_year=2026&filing_period=second_quarter&page_size=3",
    "lda_ancien_api": "https://lda.senate.gov/api/v1/filings/?filing_year=2026&page_size=1",
    "oge_index_pas": "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index?OpenView",
    "oge_278t_president": "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/5326D3AF5BE7C25385258DF7002DD1B7/%24FILE/Trump%2C%20Donald%20J.-05.08.2026-278T.pdf",
    "maison_blanche_278t": "https://www.whitehouse.gov/wp-content/uploads/2026/01/President-Donald-J.-Trump-Periodic-Transaction-Report-1.14.2026-.pdf",
    "congress_gov_page": "https://www.congress.gov/bill/119th-congress/house-bill/7008/all-info",
}
robots, resultats = {}, {}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=30)
            robots[hote] = {"statut": r.status_code, "texte": r.text[:3000]}
            if r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        robots[hote]["rp"] = rp
        time.sleep(1)
    return robots[hote]["rp"]


for nom, url in CIBLES.items():
    hote = urlparse(url).hostname
    permis = regles(hote).can_fetch(UA, url)
    res = {"url": url, "permis_robots_txt": permis}
    if permis:
        try:
            r = requests.get(url, headers=H, timeout=60)
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"), "taille": len(r.content),
                        "limites": {k: v for k, v in r.headers.items() if "ratelimit" in k.lower() or k.lower() == "retry-after"},
                        "debut": r.content[:600].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(r.content[:3_000_000])
        except Exception as exc:  # noqa: BLE001
            res["erreur"] = str(exc)[:300]
        time.sleep(1.5)
    resultats[nom] = res
    print(nom, permis, res.get("statut"), res.get("taille"), res.get("type"))

for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
