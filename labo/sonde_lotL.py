"""Sonde du lot L : les faits dei:EntityCommonStockSharesOutstanding de quelques compagnies, tels quels, dans les DEUX API
de la SEC (dossier companyfacts et fichiers frames), pour comprendre un écart de date (FLNA) et un fait plus récent
absent des frames (ASPI)."""
import json
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com"}
SORTIE = Path("labo/sonde-lotL")
SORTIE.mkdir(parents=True, exist_ok=True)
lignes = []


def dire(t=""):
    print(t, flush=True)
    lignes.append(t)
    (SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def lire(url):
    time.sleep(1.5)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.loads(r.read())


dire("# Sonde lot L : actions en circulation dans companyfacts et dans les frames\n")
CIKS = {"FLNA": 1069530, "ASPI": None, "GME": 1326380}
tickers = lire("https://www.sec.gov/files/company_tickers.json")
for x in tickers.values():
    if x["ticker"] in CIKS:
        CIKS[x["ticker"]] = int(x["cik_str"])
frames = {p: lire(f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{p}.json")
          for p in ("CY2026Q1I", "CY2026Q2I", "CY2026Q3I")}
for s, cik in CIKS.items():
    dire(f"## {s} (CIK {cik})")
    cf = lire(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    faits = cf["facts"].get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    for f in sorted(faits, key=lambda f: (f["end"], f["filed"]))[-8:]:
        dire(f"- companyfacts : fin {f['end']} · {f['val']:,} · {f.get('form')} {f.get('accn')} déposé {f.get('filed')} · "
             f"frame {f.get('frame')}")
    for p, d in frames.items():
        for r in d["data"]:
            if r["cik"] == cik:
                dire(f"- frames {p} : fin {r['end']} · {r['val']:,} · {r['accn']}")
dire("\nVERDICT : sonde faite")
