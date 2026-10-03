"""Achats d'initiés et premiers 13D : lesquels se font lors d'une émission (entrée en bourse, placement) ?

Relit les vrais documents SEC (notes de bas de page des achats ; points 3 et 4 des 13D) des infos publiées.
Lecture seule, 4 requêtes par seconde au plus, identifiée comme le robot (courriel seulement pour la SEC).
"""
import glob
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, "principal/robot")
from radar.collecteurs.sec import xml_du_depot  # noqa: E402

UA = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com", "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-emissions")
SORTIE.mkdir(parents=True, exist_ok=True)
evs = [json.loads(l) for f in sorted(glob.glob("principal/data/evenements/*.jsonl")) for l in open(f, encoding="utf-8") if l.strip()]
choisis = [e for e in evs if e["kind"] == "achat_initie"] + [
    e for e in evs if e["source"] == "sec_13dg" and e["data"].get("type") == "SCHEDULE 13D"]


def propre(t):
    return " ".join((t or "").split())


resultats, erreurs = [], []
for e in choisis:
    m = re.search(r"/data/(\d+)/(\d+)/([\d-]+)-index", e["official_url"])
    url = f"https://www.sec.gov/Archives/edgar/data/{m.group(1)}/{m.group(2)}/{m.group(3)}.txt"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        time.sleep(0.25)
        r.raise_for_status()
        racine = xml_du_depot(r.text)
    except Exception as exc:  # noqa: BLE001
        erreurs.append(f"{e['id']} : {exc}")
        continue
    base = {"id": e["id"], "symbole": e["tickers"][:1], "titre": e["title"][:160], "publie": e["published_on"]}
    if e["source"] == "sec_form4":
        notes = {f.get("id"): propre(f.text) for f in racine.findall("footnotes/footnote")}
        lignes = []
        for tr in racine.findall("nonDerivativeTable/nonDerivativeTransaction"):
            if (tr.findtext("transactionCoding/transactionCode") or "").strip() != "P":
                continue
            ids = sorted({x.get("id") for x in tr.iter("footnoteId")})
            lignes.append({"date": tr.findtext("transactionDate/value"),
                           "prix": tr.findtext("transactionAmounts/transactionPricePerShare/value"),
                           "notes": [notes.get(i) for i in ids]})
        resultats.append({**base, "sorte": "form4", "lignes": lignes, "remarques": propre(racine.findtext("remarks"))})
    else:
        items = racine.find("formData/items1To7")
        txt = {c.tag: propre(" ".join(c.itertext()))[:2500] for c in items} if items is not None else {}
        resultats.append({**base, "sorte": "13d", "types": e["data"].get("types_declarants"),
                          "item3": txt.get("item3"), "item4": txt.get("item4")})

(SORTIE / "emissions.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
MOTS = re.compile(r"initial public offering|\bIPO\b|public offering|private placement|underwrit|offering price|"
                  r"subscription|purchase agreement|registered direct|at-the-market", re.I)
lignes = [f"# Émissions : {len(resultats)} documents relus ({len(erreurs)} erreurs)", ""]
for x in resultats:
    textes = ([n for l in x.get("lignes", []) for n in l["notes"] if n] + [x.get("remarques") or ""]
              if x["sorte"] == "form4" else [x.get("item3") or "", x.get("item4") or ""])
    trouve = sorted({m.group(0).lower() for t in textes for m in MOTS.finditer(t)})
    lignes.append(f"- {x['sorte']} {x['symbole']} {x['publie']} : {', '.join(trouve) or '—'} · {x['titre'][:90]}")
lignes += ["", "## Erreurs", *erreurs]
(SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
print("\n".join(lignes[:5]))
