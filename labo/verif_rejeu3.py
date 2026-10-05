"""Vérification INDÉPENDANTE du rejeu de 3 ans et de l'analyse des règles (n'importe rien du robot, de rejeu_radar.py
ni de strategies.py).

1. Positions : chaque position (toutes les durées, les 2 règles d'achat) refaite à partir des fichiers bruts de la SEC
   (cache/ftd/*.zip) avec les règles écrites dans strategies.py.
2. Argent : des cases du tableau refaites à partir de ces positions (833 $ par mois ; 10 000 $ d'un coup en tranches).
3. Formulaires 4 : 40 infos tirées au hasard sur les 3 ans, comparées au document officiel d'EDGAR (XML).
4. Score : labo/recalcul_score.py (recalcul indépendant) sur 4 jours répartis sur les 3 ans.
Sortie : labo/rejeu3/verification.md
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
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

import requests

SORTIE = Path("labo/rejeu3")
TRAVAIL = Path("rejeu")
CACHE = Path("cache")
CONTACT = json.loads(Path("principal/robot/config.json").read_text(encoding="utf-8"))["contact"]
UA_SEC = {"User-Agent": f"Radar projet personnel {CONTACT}", "Accept-Encoding": "gzip, deflate"}
DUREES = {1: 30, 3: 91, 6: 182, 12: 365}
ESSAIS = {"strict": 3, "large": 10}
lignes, ecarts = [], []


def dire(t=""):
    print(t, flush=True)
    lignes.append(t)
    (SORTIE / "verification.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def ecart(t):
    ecarts.append(t)
    dire(f"- ÉCART : {t}")


def plus(j, n):
    return (date(int(j[:4]), int(j[4:6]), int(j[6:])) + timedelta(days=n)).strftime("%Y%m%d")


dire("# Vérification indépendante du rejeu de 3 ans\n")
entrees = json.loads((SORTIE / "entrees.json").read_text(encoding="utf-8"))
ftd = json.loads((TRAVAIL / "ftd.json").read_text(encoding="utf-8"))
strategies = json.loads((SORTIE / "strategies.json").read_text(encoding="utf-8"))

# ---------- 1. Positions ----------
dire("## 1. Positions refaites aux fichiers bruts de la SEC")
voulus = {e["symbole"] for e in entrees} | {"SPY", "IVV", "VOO"}
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
derniere = max(ftd["cles"])
a, m = int(derniere[:4]), int(derniere[4:6])
couvert = f"{derniere[:6]}14" if derniere[6] == "a" else f"{derniere[:6]}{monthrange(a, m)[1]:02d}"
spy = sorted(prix["SPY"])


def marche(d1, d2):
    for f in ("SPY", "IVV", "VOO"):
        if d1 in prix.get(f, {}) and d2 in prix.get(f, {}):
            return round(prix[f][d2][0] / prix[f][d1][0] - 1, 4)
    x = [j for j in spy if plus(d1, -5) <= j <= d1]
    y = [j for j in spy if plus(d2, -5) <= j <= d2]
    return round(prix["SPY"][y[-1]][0] / prix["SPY"][x[-1]][0] - 1, 4) if x and y else None


def refaire(e, essais, h):
    p = prix.get(e["symbole"], {})
    jour = e["jour"].replace("-", "")
    apres = [j for j in cal if j > jour]
    dep = next((j for j in apres[1:1 + essais] if j in p), None)
    if dep is None:
        return {"statut": "pas achetée"}
    cible, limite = plus(dep, DUREES[h]), plus(dep, DUREES[h] + 3)
    arr = next((j for j in cal if cible <= j <= limite and j in p), None)
    if arr is None:
        if limite > couvert:
            return {"statut": "en attente"}
        fin = plus(cible, 60)
        arr = next((j for j in cal if limite < j <= min(fin, couvert) and j in p), None)
        if arr is None:
            if fin > couvert:
                return {"statut": "en attente"}
            avant = [j for j in cal if dep < j < cible and j in p]
            arr = avant[-1] if avant else dep
    r = 0.0 if p[arr][1] != p[dep][1] else round(p[arr][0] / p[dep][0] - 1, 4)
    estime = round(p[arr][0] / p[dep][0] - 1, 4)
    if p[arr][1] != p[dep][1]:  # nouveau CUSIP : le saut de prix au changement est traité comme le regroupement
        jours = [j for j in cal if dep <= j <= arr and j in p]
        k = next(i for i, j in enumerate(jours) if p[j][1] != p[dep][1])
        estime = round(p[arr][0] / (p[jours[k]][0] / p[jours[k - 1]][0]) / p[dep][0] - 1, 4)
    return {"statut": "achetée", "depart": dep, "sortie": arr, "rendement": r, "estime": estime,
            "marche": marche(dep, arr)}


identiques, total = 0, 0
mes_positions = {}
for nom, essais in ESSAIS.items():
    for h in DUREES:
        leurs = json.loads((TRAVAIL / f"positions_{nom}_{h}.json").read_text(encoding="utf-8"))
        miennes = [refaire(e, essais, h) for e in entrees]
        mes_positions[(nom, h)] = miennes
        for e, x, y in zip(entrees, leurs, miennes):
            total += 1
            statut_x = "achetée" if x["statut"] == "achetée" else x["statut"].split(" (")[0]
            if statut_x != y["statut"]:
                ecart(f"{e['symbole']} {e['jour']} ({nom}, {h} mois) : statut {x['statut']} ≠ {y['statut']}")
                continue
            if y["statut"] == "achetée" and (x["depart"] != y["depart"] or x["sortie"] != y["sortie"]
                                            or abs(x["rendement"] - y["rendement"]) > 1e-4
                                            or abs(x["rendement_estime"] - y["estime"]) > 1e-4
                                            or (x["marche"] is None) != (y["marche"] is None)
                                            or (y["marche"] is not None and abs(x["marche"] - y["marche"]) > 1e-4)):
                ecart(f"{e['symbole']} {e['jour']} ({nom}, {h} mois) : {x.get('depart')}→{x.get('sortie')} "
                      f"{x.get('rendement')} / {x.get('marche')} ≠ {y['depart']}→{y['sortie']} {y['rendement']} / "
                      f"{y['marche']}")
                continue
            identiques += 1
dire(f"- positions comparées (8 jeux : 2 règles d'achat × 4 durées) : {total:,} · identiques : {identiques:,}")

# ---------- 2. Argent ----------
dire("\n## 2. Argent refait à partir des positions")
MENSUEL, CAPITAL = 10_000 / 12, 10_000.0
ANNEES = {"2023-2024": "2023-07", "2024-2025": "2024-07", "2025-2026": "2025-07"}
COUTS = {"aucun": (0.0, 0.0), "10 $ + écart 1 %": (10.0, 0.01), "aucun, CUSIP estimés": (0.0, 0.0)}


def mois_de(debut):
    a, m = int(debut[:4]), int(debut[5:])
    return [f"{a + (m + i - 1) // 12}-{(m + i - 1) % 12 + 1:02d}" for i in range(12)]


def val(alloc, r, frais, ecart_):
    return alloc * (1 + r) if not frais and not ecart_ else max(0.0, (alloc - frais) * (1 + r) * (1 - ecart_) - frais)


def selection(nom, e, rang):
    return {"toutes": True, "5 premières du mois": rang < 5, "petites compagnies": e.get("taille") == "petite"}[nom]


rangs = {}
for mo in {e["mois"] for e in entrees}:
    for i, e in enumerate(sorted((e for e in entrees if e["mois"] == mo), key=lambda e: (e["entree"], e["symbole"]))):
        rangs[id(e)] = i
comparees, pareilles = 0, 0
for annee, debut in ANNEES.items():
    mois = mois_de(debut)
    for h in DUREES:
        for nom_sel in ("toutes", "5 premières du mois", "petites compagnies"):
            theirs = next(c for c in strategies if c["annee"] == annee and c["selection"] == nom_sel
                          and c["duree"] == h and c["depart"] == "strict")
            if not theirs.get("mesurable") or "argent" not in theirs:
                continue
            ps = [(e, y) for e, y in zip(entrees, mes_positions[("strict", h)])
                  if e["mois"] in mois and selection(nom_sel, e, rangs[id(e)]) and y["statut"] == "achetée"]
            coh = {mo: [y for e, y in ps if e["mois"] == mo] for mo in mois}
            for nom_cout, (frais, ecart_) in COUTS.items():
                cle = "estime" if "CUSIP" in nom_cout else "rendement"
                etale = sum(sum(val(MENSUEL / len(coh[mo]), y[cle], frais, ecart_) for y in coh[mo])
                            if coh[mo] else MENSUEL for mo in mois)
                tranches = 0.0
                for k in range(h):
                    v = CAPITAL / h
                    for i in range(k, 12, h):
                        if coh[mois[i]]:
                            v = sum(val(v / len(coh[mois[i]]), y[cle], frais, ecart_) for y in coh[mois[i]])
                    tranches += v
                comparees += 1
                a1, a2 = theirs["argent"][nom_cout]["833_par_mois"], theirs["argent"][nom_cout]["10000_d_un_coup"]
                if abs(a1 - etale) < 0.02 and abs(a2 - tranches) < 0.02:
                    pareilles += 1
                else:
                    ecart(f"argent {annee} {nom_sel} {h} mois {nom_cout} : {a1} / {a2} ≠ {etale:.2f} / {tranches:.2f}")
dire(f"- cases d'argent refaites : {comparees} · identiques : {pareilles}")

# ---------- 3. Formulaires 4 contre le document officiel ----------
dire("\n## 3. Formulaires 4 du rejeu contre le document officiel d'EDGAR (XML)")
evs = json.loads((TRAVAIL / "evenements.json").read_text(encoding="utf-8"))
f4 = [e for e in evs if e["source"] == "sec_form4"]
syms = {e["symbole"] for e in entrees}
random.seed(2027)
lies = [e for e in f4 if e["tickers"][0] in syms and e["kind"] == "achat_initie"]
autres = [e for e in f4 if e["tickers"][0] not in syms and e["kind"] == "achat_initie"]
ventes = [e for e in f4 if e["kind"] == "vente_initie"]
choix = random.sample(lies, min(20, len(lies))) + random.sample(autres, min(10, len(autres))) + \
    random.sample(ventes, min(10, len(ventes)))
EMISSION = re.compile(r"initial public offering|\bIPO\b|public offering|private placement|privately negotiated|"
                      r"not effected on (a|any) (national )?securities exchange|registered direct offering|"
                      r"directed share program", re.I)
AUTO = re.compile(r"reinvest\w*\s+(of\s+)?(the\s+)?dividends?|dividends?\s+reinvest\w*|employee stock purchase plan",
                  re.I)


def memes(a, b, tol):
    if len(a) != len(b):
        return False
    libres = list(b)
    for d, x, px in a:
        k = next((i for i, (d2, x2, px2) in enumerate(libres) if d2 == d and abs(x2 - x) <= tol and abs(px2 - px) <= tol),
                 None)
        if k is None:
            return False
        libres.pop(k)
    return True


session = requests.Session()
dernier, ident, arrondis, ecart_montant = 0.0, 0, 0, 0.0
for e in choix:
    acc, code = e["official_id"].split(":")
    cik = int(e["data"]["cik_emetteur"])
    time.sleep(max(0.0, 0.25 - (time.time() - dernier)))
    dernier = time.time()
    r = session.get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}.txt", headers=UA_SEC,
                    timeout=60)
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
    vrai, emission, auto = [], False, False
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
    differences, arrondi = [], False
    if f"{depose[:4]}-{depose[4:6]}-{depose[6:]}" != e["published_on"]:
        differences.append(f"date de dépôt {depose} ≠ {e['published_on']}")
    if int(racine.findtext("issuer/issuerCik")) != cik:
        differences.append("compagnie")
    if not memes(vrai, rejeu, 1e-9):
        if memes(vrai, rejeu, 0.005 + 1e-9):
            arrondi = True
            m1, m2 = sum(x * px for _, x, px in vrai), sum(x * px for _, x, px in rejeu)
            ecart_montant = max(ecart_montant, abs(m2 / m1 - 1) if m1 else 0)
        else:
            differences.append(f"lignes {sorted(vrai)} ≠ {sorted(rejeu)}")
    proprios = sorted((p.findtext("reportingOwnerId/rptOwnerName") or "").strip() for p in racine.findall("reportingOwner"))
    if proprios != sorted(e["entities"][:-1]):
        differences.append(f"déclarants {proprios} ≠ {sorted(e['entities'][:-1])}")
    if ((racine.findtext("aff10b5One") or "").strip().lower() in ("1", "true")) != bool(e["data"]["plan_10b5_1"]):
        differences.append("plan 10b5-1")
    if emission != bool(e["data"].get("hors_bourse")) or auto != bool(e["data"].get("automatique")):
        differences.append("notes émission/automatique")
    if differences:
        ecart(f"{e['id']} ({e['tickers'][0]}, {e['published_on']}) : {' ; '.join(differences)}")
    elif arrondi:
        arrondis += 1
    else:
        ident += 1
dire(f"- formulaires 4 comparés : {len(choix)} · identiques : {ident} · identiques sauf l'arrondi à 2 décimales des "
     f"jeux de données : {arrondis} · écart maximal sur le montant à cause de l'arrondi : {ecart_montant * 100:.3f} %")

# ---------- 4. Score ----------
dire("\n## 4. Score du rejeu contre le recalcul indépendant (labo/recalcul_score.py)")
for d in sorted((TRAVAIL / "instantanes").iterdir()):
    r = subprocess.run([sys.executable, "labo/recalcul_score.py", str(d)], capture_output=True, text=True)
    sortie = (r.stdout + r.stderr).strip().splitlines()
    dire(f"- {d.name} : " + " · ".join(sortie[:2]) + f" → {sortie[-1] if sortie else '?'}")
    if r.returncode != 0:
        ecart(f"recalcul du {d.name} : " + " | ".join(sortie[-5:]))

dire(f"\nVERDICT : {'tout concorde' if not ecarts else f'{len(ecarts)} écart(s)'}")
