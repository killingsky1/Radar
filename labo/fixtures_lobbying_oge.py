"""Fichiers de test (vrais documents) pour les lecteurs du lobbying (LDA.gov) et des rapports 278-T (OGE).

robots.txt vérifié pour chaque site ; 401/403 = interdit. LDA.gov : 4,5 secondes entre deux requêtes.
OGE : seulement les rapports à lien direct (sans formulaire 201) : président, vice-président, niveaux I et II.
"""
import gzip
import json
import re
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/fixtures-lobbying-oge")
SORTIE.mkdir(parents=True, exist_ok=True)
ATTENTE = {"lda.gov": 4.5}
robots, dernier, bilan = {}, {}, []


def lire(url):
    hote = urlparse(url).hostname
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=(20, 40))
        if r.status_code in (401, 403) or r.status_code >= 500:
            rp.disallow_all = True
        elif r.status_code >= 400:
            rp.allow_all = True
        else:
            rp.parse(r.text.splitlines())
        robots[hote] = rp
        dernier[hote] = time.monotonic()
    if not robots[hote].can_fetch(UA, url):
        raise SystemExit(f"robots.txt interdit {url}")
    reste = ATTENTE.get(hote, 1.5) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)
    r = requests.get(url, headers=H, timeout=(20, 90))
    dernier[hote] = time.monotonic()
    bilan.append({"url": url, "statut": r.status_code, "taille": len(r.content)})
    r.raise_for_status()
    return r.content


def garder(nom, contenu):
    (SORTIE / f"{nom}.gz").write_bytes(gzip.compress(contenu, mtime=0))


F = "https://lda.gov/api/v1/filings/?filing_year=2026&filing_period=second_quarter&page_size=25&client_name="
garder("lda_lockheed.json", lire(F + "LOCKHEED"))
garder("lda_gamestop.json", lire(F + "GAMESTOP"))
garder("lda_eagle.json", lire(F + "EAGLE"))
page = lire(F + "SOUTHWEST")
garder("lda_southwest_1.json", page)
suivante = json.loads(page)["next"]
garder("lda_southwest_2.json", lire(suivante))
bilan.append({"southwest_page_2": suivante})
garder("lda_sujets.json", lire("https://lda.gov/api/v1/constants/filing/lobbyingactivityissues/"))

API = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest?draw=1&order%5B0%5D%5Bcolumn%5D=0&order%5B0%5D%5Bdir%5D=desc"
for i, c in enumerate(("docDate", "title", "type", "name", "agency", "level")):
    API += f"&columns%5B{i}%5D%5Bdata%5D={c}&columns%5B{i}%5D%5Bsearchable%5D=true&columns%5B{i}%5D%5Borderable%5D=true"
API += "&search%5Bvalue%5D=&columns%5B2%5D%5Bsearch%5D%5Bvalue%5D=Transaction"
LIEN = re.compile(r"href='(https://extapps2\.oge\.gov/201/Presiden\.nsf/PAS\+Index/[0-9A-F]{32}/\$FILE/[^']+\.pdf)'>278 Transaction</a>")
pdfs = []
for nom, filtre in (("niveaux", "&columns%5B5%5D%5Bsearch%5D%5Bvalue%5D=Level"),
                    ("president", "&columns%5B1%5D%5Bsearch%5D%5Bvalue%5D=President")):
    contenu = lire(API + filtre + "&start=0&length=100")
    garder(f"oge_{nom}.json", contenu)
    for r in json.loads(contenu)["data"]:
        m = LIEN.search(r["type"])
        ok = r["title"] in ("President", "Vice President") or r["level"] in ("Level I", "Level II")
        if m and ok and r["docDate"] >= "2026-07-05":
            pdfs.append(m.group(1))
tailles = {}
for url in sorted(set(pdfs)):
    c = lire(url)
    tailles[url] = {"taille": len(c), "debut": c[:8].decode("latin-1")}
    if len(c) <= 300_000:
        garder("pdf_" + url.rsplit("/", 1)[1].replace("%20", "_").replace("(", "").replace(")", ""), c)
(SORTIE / "bilan.json").write_text(json.dumps({"requetes": bilan, "pdfs": tailles}, ensure_ascii=False, indent=1) + "\n",
                                   encoding="utf-8")
print(len(bilan), "requêtes ;", len(tailles), "PDF")
