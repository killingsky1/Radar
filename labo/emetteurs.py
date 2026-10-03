"""Type officiel de chaque émetteur noté (fiche « submissions » de la SEC) : compagnie, fonds, BDC, étranger.

Pour chaque symbole présent dans les infos publiées : CIK (liste officielle des symboles), puis la fiche
data.sec.gov/submissions : entityType, code SIC, et les formulaires déposés (N-CSR/NPORT = fonds enregistré,
N-54A = BDC, 10-K = compagnie américaine, 20-F/40-F = émetteur étranger). Lecture seule, 4 requêtes/s au plus.
"""
import glob
import json
import time
from collections import Counter
from pathlib import Path

import requests

UA = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com", "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-emetteurs")
SORTIE.mkdir(parents=True, exist_ok=True)
FONDS = {"N-CSR", "N-CSRS", "NPORT-P", "N-CEN", "N-2", "N-PX", "N-CSR/A", "NPORT-P/A", "N-30D", "N-Q"}

liste = requests.get("https://www.sec.gov/files/company_tickers_exchange.json", headers=UA, timeout=60).json()
cik_de = {}
for cik, nom, symbole, bourse in liste["data"]:
    cik_de.setdefault(symbole, (cik, nom, bourse))
evs = [json.loads(l) for f in sorted(glob.glob("principal/data/evenements/*.jsonl")) for l in open(f, encoding="utf-8") if l.strip()]
aujourdhui = json.load(open("principal/data/app/aujourdhui.json", encoding="utf-8"))
dans_listes = {x["symbole"] for n in ("hausse", "baisse") for x in aujourdhui[n]}
symboles = sorted({t for e in evs for t in e["tickers"]})
print(f"{len(symboles)} symboles dans les infos ; {len(dans_listes)} dans les listes du score")

fiches, absents = {}, []
for s in symboles:
    if s not in cik_de:
        absents.append(s)
        continue
    cik, nom, bourse = cik_de[s]
    if cik in fiches:
        fiches[cik]["symboles"].append(s)
        continue
    time.sleep(0.25)
    try:
        d = requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers=UA, timeout=30).json()
    except Exception as exc:  # noqa: BLE001
        fiches[cik] = {"symboles": [s], "erreur": str(exc)}
        continue
    formes = Counter(d.get("filings", {}).get("recent", {}).get("form", []))
    fiches[cik] = {
        "symboles": [s], "nom": d.get("name"), "bourse": bourse, "entityType": d.get("entityType"),
        "sic": d.get("sic"), "sicDescription": d.get("sicDescription"), "categorie": d.get("category"),
        "fonds_enregistre": sorted(f for f in formes if f in FONDS), "bdc": formes.get("N-54A", 0) > 0,
        "10k": formes.get("10-K", 0), "20f": formes.get("20-F", 0), "40f": formes.get("40-F", 0),
        "dans_listes": s in dans_listes,
    }
(SORTIE / "emetteurs.json").write_text(json.dumps(fiches, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
lignes = [f"# Émetteurs : {len(fiches)} fiches SEC lues ; symboles sans CIK : {', '.join(absents) or 'aucun'}", ""]
for cik, f in sorted(fiches.items(), key=lambda kv: (not kv[1].get("dans_listes"), kv[1].get("symboles"))):
    lignes.append(f"- {'**' if f.get('dans_listes') else ''}{'/'.join(f['symboles'])}{'**' if f.get('dans_listes') else ''} "
                  f"· {f.get('nom')} · type={f.get('entityType')} · SIC {f.get('sic')} {f.get('sicDescription')} "
                  f"· fonds={f.get('fonds_enregistre')} · BDC={f.get('bdc')} · 10-K={f.get('10k')} 20-F={f.get('20f')} 40-F={f.get('40f')}")
types = Counter(f.get("entityType") for f in fiches.values())
lignes += ["", f"entityType : {dict(types)}"]
(SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
print("\n".join(lignes[:3]))
