"""Reconnaissance 3 du lot 2 : existe-t-il une page officielle par contrat sur CanadaBuys ?"""

import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

SORTIE = Path("labo/resultats-lot2c")
UA = {"User-Agent": "Radar projet personnel"}
lignes = ["# Reconnaissance 3 du lot 2 (CanadaBuys)", ""]


def get(url):
    time.sleep(0.8)
    try:
        r = requests.get(url, headers=UA, timeout=60)
        lignes.append(f"- {r.status_code} · {len(r.content)} octets · {url}")
        return r
    except Exception as e:  # noqa: BLE001
        lignes.append(f"- ERREUR {e} · {url}")
        return None


def liens(r, base, motif):
    t = r.content.decode("utf-8", "replace")
    vus = []
    for href in re.findall(r'href="([^"]+)"', t):
        u = urljoin(base, href.replace("&amp;", "&"))
        if re.search(motif, u, re.I) and u not in vus:
            vus.append(u)
    return vus


SORTIE.mkdir(parents=True, exist_ok=True)
for i, url in enumerate(["https://canadabuys.canada.ca/en/procurement-and-contracting-data",
                         "https://canadabuys.canada.ca/en/tender-opportunities?search_filter=WS5672955639",
                         "https://canadabuys.canada.ca/en/tender-opportunities?search_filter=CW2451599",
                         "https://canadabuys.canada.ca/en/tender-opportunities?search_filter=CW2461613"]):
    r = get(url)
    if r is None:
        continue
    (SORTIE / f"page_{i}.html").write_bytes(r.content)
    for u in liens(r, url, r"contract|award|attribution|tender-notice|history|historique")[:25]:
        lignes.append(f"    - {u}")
        if i > 0 and ("tender-notice" in u or "award" in u):
            r2 = get(u)
            if r2 is not None and r2.ok:
                t = " ".join(re.sub(r"<[^>]+>", " ", r2.content.decode("utf-8", "replace")).split())
                for mot in ("Award", "Contract value", "Supplier", "Matawinie", "Commercial Truck"):
                    m = re.search(mot, t)
                    if m:
                        lignes.append(f"      - …{t[max(0, m.start() - 150):m.start() + 250]}…")
(SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
print("\n".join(lignes))
