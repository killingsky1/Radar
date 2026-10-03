"""Lot 3b, D et E : lobbying (LDA.gov) et rapports 278-T de l'OGE. robots.txt d'abord, lecture seule.

LDA.gov : robots.txt demande 4 secondes entre deux requêtes (15 par minute sans compte) : on attend 4,5 secondes.
OGE : seulement les pages publiques sans formulaire 201 (index, rapports par date, président et vice-président).
"""
import json
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-oge-api")
SORTIE.mkdir(parents=True, exist_ok=True)
F = "https://lda.gov/api/v1/filings/?filing_year=2026&filing_period=second_quarter&page_size=25&client_name="
CIBLES_1 = {
    "lda_tos": "https://lda.gov/api/tos/",
    "lda_tos_senat": "https://lda.senate.gov/api/tos/",
    "lda_racine": "https://lda.gov/api/v1/",
    "lda_sujets": "https://lda.gov/api/v1/constants/filing/lobbyingactivityissues/",
    "lda_types": "https://lda.gov/api/v1/constants/filing/filingtypes/",
    "lda_gamestop": F + "GameStop",
    "lda_dicks": F + "Dick%27s%20Sporting%20Goods",
    "lda_fuller": F + "Fuller",
    "lda_hbfuller": F + "H.B.%20Fuller",
    "lda_cbiz": F + "CBIZ",
    "lda_lockheed": F + "Lockheed%20Martin",
    "lda_lockheed_100": F.replace("page_size=25", "page_size=100") + "Lockheed%20Martin",
    "lda_clients_lockheed": "https://lda.gov/api/v1/clients/?page_size=25&client_name=Lockheed%20Martin",
    "lda_t3": "https://lda.gov/api/v1/filings/?filing_year=2026&filing_period=third_quarter&page_size=1",
    "oge_par_date": "https://extapps2.oge.gov/201/Presiden.nsf/PAS%20Filings%20by%20Date?OpenView",
    "oge_par_date_200": "https://extapps2.oge.gov/201/Presiden.nsf/PAS%20Filings%20by%20Date?OpenView&Count=200",
    "oge_president_vp": "https://www.oge.gov/web/OGE.nsf/Officials%20Individual%20Disclosures%20Search%20Collection",
    "oge_formulaire_201": "https://www.oge.gov/web/oge.nsf/Resources/OGE+Form+201:+Request+an+Individual%E2%80%99s+Ethics+Documents",
}
# 3e passage : l'adresse de données publique qu'appelle la page « Officials' Individual Disclosures » de l'OGE
API = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest?draw=1&order%5B0%5D%5Bcolumn%5D=0&order%5B0%5D%5Bdir%5D=desc"
for i, c in enumerate(("docDate", "title", "type", "name", "agency", "level")):
    API += f"&columns%5B{i}%5D%5Bdata%5D={c}&columns%5B{i}%5D%5Bsearchable%5D=true&columns%5B{i}%5D%5Borderable%5D=true"
CIBLES = {
    "oge_api_recents": API + "&start=0&length=25&search%5Bvalue%5D=",
    "oge_api_278t": API + "&start=0&length=25&search%5Bvalue%5D=278-T",
    "oge_api_colonne_type": API + "&start=0&length=25&search%5Bvalue%5D=&columns%5B2%5D%5Bsearch%5D%5Bvalue%5D=Transaction",
    "oge_api_president": API + "&start=0&length=25&search%5Bvalue%5D=&columns%5B3%5D%5Bsearch%5D%5Bvalue%5D=Trump",
}
CIBLES_2 = {
    "lda_guide": "https://lobbyingdisclosure.house.gov/ldaguidance.pdf",
    "oge_par_date": "https://extapps2.oge.gov/201/Presiden.nsf/PAS%20Filings%20by%20Date?OpenView",
    "oge_par_date_200": "https://extapps2.oge.gov/201/Presiden.nsf/PAS%20Filings%20by%20Date?OpenView&Count=200",
    "oge_president_vp": "https://www.oge.gov/web/OGE.nsf/Officials%20Individual%20Disclosures%20Search%20Collection",
    "oge_formulaire_201": "https://www.oge.gov/web/oge.nsf/Resources/OGE+Form+201:+Request+an+Individual%E2%80%99s+Ethics+Documents",
}
ATTENTE = {"lda.gov": 4.5, "lda.senate.gov": 4.5}
robots, resultats, dernier = {}, {}, {}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=(20, 40))
            robots[hote] = {"statut": r.status_code, "texte": r.text[:3000]}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
    return robots[hote]["rp"]


for nom, url in CIBLES.items():
    hote = urlparse(url).hostname
    permis = regles(hote).can_fetch(UA, url)
    res = {"url": url, "permis_robots_txt": permis}
    if permis:
        reste = ATTENTE.get(hote, 1.5) - (time.monotonic() - dernier.get(hote, 0))
        if reste > 0:
            time.sleep(reste)
        try:
            r = requests.get(url, headers=H, timeout=60)
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"), "taille": len(r.content),
                        "entetes": {k: v for k, v in r.headers.items() if k.lower().startswith(("x-", "retry", "ratelimit"))},
                        "debut": r.content[:400].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(r.content[:5_000_000])
        except Exception as exc:  # noqa: BLE001
            res["erreur"] = str(exc)[:300]
        dernier[hote] = time.monotonic()
    resultats[nom] = res
    print(nom, permis, res.get("statut"), res.get("taille"), res.get("type"))

for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
