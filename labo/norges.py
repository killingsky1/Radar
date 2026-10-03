"""Pourquoi Apple, NVIDIA… sont absentes du 13F de Norges Bank au 1er trimestre 2026 ?"""
import json, re, time
from pathlib import Path
import requests
UA = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com"}
S = Path("labo/resultats-norges"); S.mkdir(parents=True, exist_ok=True)
out = []
def get(u):
    time.sleep(0.3); r = requests.get(u, headers=UA, timeout=120); out.append(f"- {r.status_code} · {len(r.content)} · {u}"); return r
sub = get("https://data.sec.gov/submissions/CIK0001374170.json").json()["filings"]["recent"]
lignes = [(f, a, fd, rd) for f, a, fd, rd in zip(sub["form"], sub["accessionNumber"], sub["filingDate"], sub["reportDate"]) if f.startswith("13F")]
out.append(f"13F de Norges (récents) : {lignes[:8]}")
for f, acc, fd, rd in lignes[:5]:
    d = f"https://www.sec.gov/Archives/edgar/data/1374170/{acc.replace('-', '')}"
    items = [i["name"] for i in get(f"{d}/index.json").json()["directory"]["item"]]
    prim = get(f"{d}/primary_doc.xml").text
    champs = {k: (re.search(rf"<(?:\w+:)?{k}>([^<]*)<", prim) or [None, None])[1] for k in
              ("reportCalendarOrQuarter", "reportType", "isAmendment", "amendmentType", "tableEntryTotal", "tableValueTotal",
               "isConfidentialOmitted", "otherIncludedManagersCount")}
    out.append(f"## {f} {acc} déposé {fd} trimestre {rd} · fichiers {items}\n  couverture : {champs}")
    for x in items:
        if x.endswith(".xml") and x != "primary_doc.xml":
            t = get(f"{d}/{x}").text
            n = len(re.findall(r"<(?:\w+:)?infoTable>", t))
            out.append(f"  {x} : {n} lignes · Apple 037833100 : {'037833100' in t.upper()} · NVIDIA 67066G104 : {'67066G104' in t.upper()}")
(S / "resume.md").write_text("\n".join(out) + "\n", encoding="utf-8"); print("\n".join(out))
