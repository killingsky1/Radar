"""Taux officiel USD → CAD de la Banque du Canada (API Valet), pour convertir un montant en dollars canadiens.

Règles : robots.txt lu d'abord (401/403 ou illisible = interdit, 404 = permis), identité « Radar projet personnel ».
Sortie : labo/taux/resume.md
"""
import json
import sys
import urllib.robotparser
from pathlib import Path

import requests

SORTIE = Path("labo/taux")
SORTIE.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Radar projet personnel"}
URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=10"
lignes = []


def dire(t=""):
    print(t, flush=True)
    lignes.append(t)
    (SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


r = requests.get("https://www.bankofcanada.ca/robots.txt", headers=UA, timeout=30)
dire(f"# Taux USD → CAD (Banque du Canada)\n\n- robots.txt : HTTP {r.status_code}")
if r.status_code == 404:
    permis = True
elif r.status_code == 200:
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    permis = rp.can_fetch("Radar projet personnel", URL)
    dire(f"- robots.txt permet /valet/ : {permis} · Crawl-delay : {rp.crawl_delay('Radar projet personnel')}")
else:
    permis = False
if not permis:
    dire("VERDICT : interdit, rien lu")
    sys.exit(0)
r = requests.get(URL, headers=UA, timeout=30)
dire(f"- {URL} : HTTP {r.status_code}")
d = r.json()
dire(f"- série : {json.dumps(d.get('seriesDetail', {}), ensure_ascii=False)}")
for o in d.get("observations", []):
    dire(f"- {o['d']} : {o['FXUSDCAD']['v']}")
dire("VERDICT : lu")
