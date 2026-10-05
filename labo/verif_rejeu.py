"""Vérification INDÉPENDANTE du rejeu d'un an (n'importe rien du robot ni de rejeu_radar.py).

1. Prix et rendements : chaque position refaite à partir des fichiers bruts de la SEC (cache/ftd/*.zip), avec les règles
   publiées de la page Résultats : départ = 2e date de règlement après le jour de la suggestion (2 de plus au plus s'il
   n'y a pas de prix) ; arrivée = 30 jours plus tard (jusqu'à 3 jours de plus) ; sinon 1re date suivante avec un prix
   (90 jours au plus), sinon la dernière avant ; nouveau CUSIP = 0 %. Marché : SPY, sinon IVV, sinon VOO aux mêmes dates.
2. L'argent : les montants finaux refaits à partir des rendements (étalé, réinvesti, frais, S&P 500).
3. Formulaires 4 : 40 infos tirées au hasard, comparées au document officiel d'EDGAR (XML), lu par un lecteur écrit ici.
4. Score : labo/recalcul_score.py (recalcul indépendant) sur 3 jours du rejeu.
Sortie : labo/rejeu/verification.md
"""
import io
import json
import random
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import requests

SORTIE = Path("labo/rejeu")
TRAVAIL = Path("rejeu")
CACHE = Path("cache")
CONTACT = json.loads(Path("principal/robot/config.json").read_text(encoding="utf-8"))["contact"]
UA_SEC = {"User-Agent": f"Radar projet personnel {CONTACT}", "Accept-Encoding": "gzip, deflate"}
MENSUEL, FRAIS = 10_000 / 12, 10.0
lignes, ecarts = [], []


def dire(t=""):
    print(t, flush=True)
    lignes.append(t)
    (SORTIE / "verification.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def ecart(t):
    ecarts.append(t)
    dire(f"- ÉCART : {t}")


def plus(aaaammjj, n):
    return (date(int(aaaammjj[:4]), int(aaaammjj[4:6]), int(aaaammjj[6:])) + timedelta(days=n)).strftime("%Y%m%d")


positions = json.loads((SORTIE / "positions.json").read_text(encoding="utf-8"))
mensuel = json.loads((SORTIE / "mensuel.json").read_text(encoding="utf-8"))
ftd = json.loads((TRAVAIL / "ftd.json").read_text(encoding="utf-8"))
dire("# Vérification indépendante du rejeu d'un an\n")

# ---------- 1. Prix et rendements ----------
dire("## 1. Prix et rendements refaits aux fichiers bruts de la SEC")
voulus = {p["symbole"] for p in positions} | {"SPY", "IVV", "VOO"}
prix, cal = {}, set()
for c in ftd["cles"]:
    with zipfile.ZipFile(io.BytesIO((CACHE / "ftd" / f"{c}.zip").read_bytes())) as z:
        for l in z.read(z.namelist()[0]).decode("latin-1").splitlines()[1:]:
            p = l.split("|")
            if len(p) != 6 or not re.fullmatch(r"\d{8}", p[0]):
                continue
            cal.add(p[0])
            s = p[2].strip().upper().replace(".", "-").replace("/", "-")
            if s in voulus and re.fullmatch(r"\d+(\.\d+)?", p[5].strip()):
                prix.setdefault(s, {})[p[0]] = (float(p[5]), p[1].strip())
cal = sorted(cal)


def marche(d1, d2):
    for f in ("SPY", "IVV", "VOO"):
        if d1 in prix.get(f, {}) and d2 in prix.get(f, {}):
            return round(prix[f][d2][0] / prix[f][d1][0] - 1, 4)
    a = [x for x in sorted(prix["SPY"]) if plus(d1, -5) <= x <= d1]
    b = [x for x in sorted(prix["SPY"]) if plus(d2, -5) <= x <= d2]
    return round(prix["SPY"][b[-1]][0] / prix["SPY"][a[-1]][0] - 1, 4) if a and b else None


verifiees = 0
for pos in positions:
    jour = datetime.fromisoformat(pos["entree"]).astimezone(ZoneInfo("America/Toronto")).strftime("%Y%m%d")
    p = prix.get(pos["symbole"], {})
    candidates = [j for j in cal if j > jour][1:4]
    dep = next((j for j in candidates if j in p), None)
    if dep is None:
        if pos["achetee"]:
            ecart(f"{pos['symbole']} {pos['jour']} : achetée dans le rejeu, mais aucun prix au départ ici")
        continue
    if not pos["achetee"] or pos["depart"].get("date") != dep or abs(pos["prix_achat"] - p[dep][0]) > 1e-9:
        ecart(f"{pos['symbole']} {pos['jour']} : départ {pos['depart']} ≠ {dep} {p[dep]}")
        continue
    cible, limite = plus(dep, 30), plus(dep, 33)
    arr = next((j for j in cal if cible <= j <= limite and j in p), None)
    if arr is None:
        arr = next((j for j in cal if limite < j <= plus(dep, 90) and j in p), None)
    if arr is None:
        avant = [j for j in cal if dep < j < cible and j in p]
        arr = avant[-1] if avant else None
    if arr is None:
        if pos.get("sortie") is not None:
            ecart(f"{pos['symbole']} {pos['jour']} : sortie {pos.get('sortie')} ≠ aucune")
        continue
    var = round(p[arr][0] / p[dep][0] - 1, 4)
    r = 0.0 if p[arr][1] != p[dep][1] else var
    if pos.get("sortie") != arr or abs(pos["rendement"] - r) > 1e-4:
        ecart(f"{pos['symbole']} {pos['jour']} : sortie {pos.get('sortie')} {pos['rendement']} ≠ {arr} {r}")
        continue
    m = marche(dep, arr)
    if m is None or pos["marche"] is None or abs(m - pos["marche"]) > 1e-4:
        ecart(f"{pos['symbole']} {pos['jour']} : marché {pos['marche']} ≠ {m}")
        continue
    verifiees += 1
achetees = [p for p in positions if p["achetee"]]
dire(f"- positions : {len(positions)} · achetées : {len(achetees)} · refaites identiques (départ, arrivée, prix, "
     f"rendement, marché) : {verifiees}")

# ---------- 2. L'argent ----------
dire("\n## 2. L'argent refait à partir des rendements")
mois = mensuel["bilan"]["mois"]


def refaire(cle, frais=0.0):
    etale, reinv = 0.0, 0.0
    for mo in mois:
        ps = [p for p in achetees if p["mois"] == mo and p[cle] is not None]
        reinv += MENSUEL
        if not ps:
            etale += MENSUEL
            continue

        def v(a, r):
            return max(0.0, (a - frais) * (1 + r) - frais) if frais else a * (1 + r)
        etale += sum(v(MENSUEL / len(ps), p[cle]) for p in ps)
        reinv = sum(v(reinv / len(ps), p[cle]) for p in ps)
    return round(etale, 2), round(reinv, 2)


for nom, cle, frais in (("Radar", "rendement", 0.0), ("Radar, frais de 10 $ par transaction", "rendement", FRAIS),
                        ("S&P 500 (SPY) aux mêmes dates", "marche", 0.0)):
    attendu = mensuel["bilan"]["versions"][nom]
    refait = refaire(cle, frais)
    ok = abs(refait[0] - attendu["etale"]) < 0.02 and abs(refait[1] - attendu["reinvesti"]) < 0.02
    dire(f"- {nom} : rejeu {attendu['etale']:,.2f} / {attendu['reinvesti']:,.2f} · refait {refait[0]:,.2f} / "
         f"{refait[1]:,.2f} · {'identique' if ok else 'DIFFÉRENT'}")
    if not ok:
        ecart(f"montants {nom}")

# ---------- 3. Formulaires 4 contre le document officiel ----------
dire("\n## 3. Formulaires 4 du rejeu contre le document officiel d'EDGAR (XML)")
evs = json.loads((TRAVAIL / "evenements.json").read_text(encoding="utf-8"))
f4 = [e for e in evs if e["source"] == "sec_form4"]
syms = {p["symbole"] for p in positions}
random.seed(2026)
lies = [e for e in f4 if e["tickers"][0] in syms and e["kind"] == "achat_initie"]
autres_a = [e for e in f4 if e not in lies and e["kind"] == "achat_initie"]
ventes = [e for e in f4 if e["kind"] == "vente_initie"]
choix = (random.sample(lies, min(20, len(lies))) + random.sample(autres_a, min(10, len(autres_a)))
         + random.sample(ventes, min(10, len(ventes))))
EMISSION = re.compile(r"initial public offering|\bIPO\b|public offering|private placement|privately negotiated|"
                      r"not effected on (a|any) (national )?securities exchange|registered direct offering|"
                      r"directed share program", re.I)
AUTO = re.compile(r"reinvest\w*\s+(of\s+)?(the\s+)?dividends?|dividends?\s+reinvest\w*|employee stock purchase plan",
                  re.I)
session = requests.Session()
dernier = 0.0
identiques = 0
for e in choix:
    acc, code = e["official_id"].split(":")
    cik = int(e["data"]["cik_emetteur"])
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}.txt"
    time.sleep(max(0.0, 0.25 - (time.time() - dernier)))
    dernier = time.time()
    r = session.get(url, headers=UA_SEC, timeout=60)
    if r.status_code in (401, 403):
        dire(f"- INTERDIT ({r.status_code}) : arrêt sans contourner")
        ecarts.append("SEC : accès refusé")
        break
    if r.status_code != 200:
        ecart(f"{acc} : HTTP {r.status_code}")
        continue
    t = r.text
    depose = re.search(r"FILED AS OF DATE:\s*(\d{8})", t).group(1)
    racine = ET.fromstring(re.search(r"<XML>\s*(.*?)\s*</XML>", t, re.S).group(1).strip())
    for el in racine.iter():
        el.tag = el.tag.split("}", 1)[-1]
    notes = {n.get("id"): " ".join((n.text or "").split()) for n in racine.findall("footnotes/footnote")}
    vrai = []
    emission = auto = False
    for tr in racine.findall("nonDerivativeTable/nonDerivativeTransaction"):
        if (tr.findtext("transactionCoding/transactionCode") or "").strip() != code:
            continue
        ids = {f.get("id") for part in ("securityTitle", "transactionDate", "transactionCoding", "transactionAmounts")
               for x in tr.findall(part) for f in x.iter("footnoteId")}
        emission |= any(EMISSION.search(notes.get(i, "")) for i in ids)
        auto |= any(AUTO.search(notes.get(i, "")) for i in ids)
        a = float((tr.findtext("transactionAmounts/transactionShares/value") or "0").replace(",", "") or 0)
        px = float((tr.findtext("transactionAmounts/transactionPricePerShare/value") or "0").replace(",", "") or 0)
        vrai.append(((tr.findtext("transactionDate/value") or "")[:10], round(a, 4), round(px, 4)))
    rejeu = [(x["date"], round(x["actions"] or 0, 4), round(x["prix"] or 0, 4)) for x in e["data"]["transactions"]]
    proprios = sorted((p.findtext("reportingOwnerId/rptOwnerName") or "").strip() for p in racine.findall("reportingOwner"))
    plan = (racine.findtext("aff10b5One") or "").strip().lower() in ("1", "true")
    differences = []
    if f"{depose[:4]}-{depose[4:6]}-{depose[6:]}" != e["published_on"]:
        differences.append(f"date de dépôt {depose} ≠ {e['published_on']}")
    if int(racine.findtext("issuer/issuerCik")) != cik:
        differences.append("compagnie")
    if sorted(vrai) != sorted(rejeu):
        differences.append(f"lignes {sorted(vrai)} ≠ {sorted(rejeu)}")
    if proprios != sorted(e["entities"][:-1]):
        differences.append(f"déclarants {proprios} ≠ {sorted(e['entities'][:-1])}")
    if plan != bool(e["data"]["plan_10b5_1"]):
        differences.append(f"plan 10b5-1 {plan} ≠ {e['data']['plan_10b5_1']}")
    if emission != bool(e["data"].get("hors_bourse")) or auto != bool(e["data"].get("automatique")):
        differences.append(f"notes émission/automatique {emission}/{auto} ≠ {bool(e['data'].get('hors_bourse'))}/"
                           f"{bool(e['data'].get('automatique'))}")
    if differences:
        ecart(f"{e['id']} ({e['tickers'][0]}) : {' ; '.join(differences)}")
    else:
        identiques += 1
dire(f"- formulaires 4 comparés : {len(choix)} (20 liés aux entrées, 10 autres achats, 10 ventes) · identiques : "
     f"{identiques}")

# ---------- 4. Score : recalcul indépendant sur 3 jours ----------
dire("\n## 4. Score du rejeu contre le recalcul indépendant (labo/recalcul_score.py)")
for d in sorted((TRAVAIL / "instantanes").iterdir()):
    r = subprocess.run([sys.executable, "labo/recalcul_score.py", str(d)], capture_output=True, text=True)
    sortie = (r.stdout + r.stderr).strip().splitlines()
    dire(f"- {d.name} : " + " · ".join(sortie[:2]) + f" → {sortie[-1] if sortie else '?'}")
    if r.returncode != 0:
        ecart(f"recalcul du {d.name} : " + " | ".join(sortie[-5:]))

dire(f"\nVERDICT : {'tout concorde' if not ecarts else f'{len(ecarts)} écart(s)'}")
