"""Lot K, calcul refait : vraies données officielles pour les tests du robot ET attendus indépendants.

1) Extraits des dossiers « companyfacts » de la SEC (data.sec.gov/api/xbrl/companyfacts), réduits aux étiquettes utiles :
   le robot les rejoue dans ses tests.
2) Attendus refaits SANS companyfacts : le labo trouve le dernier rapport annuel de chaque compagnie sur sa fiche officielle
   (data.sec.gov/submissions), lit son fichier XBRL (l'instance, dans le dossier du dépôt à la SEC) et en tire les chiffres
   de l'exercice et de l'exercice d'avant ; le bilan de fin t-2 vient du rapport annuel précédent. Puis les 9 critères
   de Piotroski (2000), avec ce code.
Mêmes règles d'accès que le robot : robots.txt lu d'abord, 1,5 s entre deux requêtes, identification (courriel à la SEC).
"""
import json
import sys
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/fixtures-lotK2")
SORTIE.mkdir(parents=True, exist_ok=True)
robots, dernier, resume = {}, {}, []


def dire(t=""):
    print(t, flush=True)
    resume.append(t)
    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")


def ua(hote):
    return UA_SEC if hote.endswith("sec.gov") else UA


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers={"User-Agent": ua(hote)}, timeout=(20, 40))
            robots[hote] = {"statut": r.status_code, "texte": r.text[:4000]}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        delai = rp.crawl_delay(ua(hote)) if robots[hote].get("statut") == 200 else None
        robots[hote]["delai"] = float(delai) if delai else None
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
    return robots[hote]["rp"]


def permis(url):
    hote = urlparse(url).hostname
    return regles(hote).can_fetch(ua(hote), url)


def lire(url, max_octets=20_000_000):
    """(statut, octets) ; (None, None) si robots.txt ne permet pas. Redirections suivies à la main (robots de chaque site)."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not permis(url):
            return None, None
        reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
        if reste > 0:
            time.sleep(reste)
        try:
            r = requests.get(url, headers={"User-Agent": ua(hote), "Accept-Encoding": "gzip, deflate"},
                             timeout=(20, 180), stream=True, allow_redirects=False)
        except Exception as exc:  # noqa: BLE001
            dernier[hote] = time.monotonic()
            return f"erreur {type(exc).__name__}", b""
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            dernier[hote] = time.monotonic()
            r.close()
            url = urljoin(url, r.headers["location"])
            continue
        morceaux, taille = [], 0
        for m in r.iter_content(1 << 16):
            morceaux.append(m)
            taille += len(m)
            if taille > max_octets:
                break
        r.close()
        dernier[hote] = time.monotonic()
        return r.status_code, b"".join(morceaux)
    return "trop de redirections", b""


CIKS = {1326380: "GME", 39368: "FUL", 896493: "GPUS", 1821806: "LESL", 1582313: "XENE", 1502292: "PRHI",
        320193: "AAPL", 2488: "AMD", 789019: "MSFT"}
ANNUELS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A"}
DUREE = {"benefice": ["NetIncomeLoss", "ProfitLoss", "IncomeLossFromContinuingOperations"],
         "flux": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
         "ventes": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "RevenueFromContractWithCustomerIncludingAssessedTax"],
         "brute": ["GrossProfit"], "cout": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
         "emission": ["ProceedsFromIssuanceOfCommonStock", "StockIssuedDuringPeriodValueNewIssues"]}
INSTANT = {"actif": ["Assets"], "ac": ["AssetsCurrent"], "pc": ["LiabilitiesCurrent"],
           "dette": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"]}
TAGS = sorted({t for g in (DUREE, INSTANT) for ts in g.values() for t in ts})
ORDRE = ["ROA", "CFO", "ΔROA", "ACCRUAL", "ΔLEVER", "ΔLIQUID", "EQ_OFFER", "ΔMARGIN", "ΔTURN"]
XBRLI = "{http://www.xbrl.org/2003/instance}"


def json_de(url, max_octets=20_000_000):
    statut, b = lire(url, max_octets)
    if statut != 200:
        raise RuntimeError(f"{url} : {statut}")
    return json.loads(b)


def instance(cik: int, accn: str):
    """Le fichier XBRL (instance) d'un dépôt : (nom, faits) ; faits = {(étiquette, début, fin): valeur} sans les axes."""
    dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}"
    noms = [x["name"] for x in json_de(f"{dossier}/index.json")["directory"]["item"]]
    candidats = [n for n in noms if n.endswith("_htm.xml")] or [
        n for n in noms if n.endswith(".xml") and n != "FilingSummary.xml" and not n.endswith(
            ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml"))]
    if len(candidats) != 1:
        raise RuntimeError(f"{accn} : instance introuvable ou ambiguë ({candidats[:5]})")
    statut, b = lire(f"{dossier}/{candidats[0]}", 200_000_000)
    if statut != 200:
        raise RuntimeError(f"{accn} : instance {statut}")
    racine = ET.fromstring(b)
    periodes = {}
    for c in racine.iter(f"{XBRLI}context"):
        if c.find(f"{XBRLI}entity/{XBRLI}segment") is not None or c.find(f"{XBRLI}scenario") is not None:
            continue  # chiffre d'une partie de la compagnie (axe) : pas le total
        p = c.find(f"{XBRLI}period")
        i = p.find(f"{XBRLI}instant")
        periodes[c.get("id")] = (None, i.text.strip()) if i is not None else (
            p.find(f"{XBRLI}startDate").text.strip(), p.find(f"{XBRLI}endDate").text.strip())
    usd = {u.get("id") for u in racine.iter(f"{XBRLI}unit")
           if [m.text.strip() for m in u.iter(f"{XBRLI}measure")] == ["iso4217:USD"]}
    faits, doubles = {}, []
    for el in racine:
        if not el.tag.startswith("{http://fasb.org/us-gaap/"):
            continue
        tag = el.tag.split("}", 1)[1]
        if tag not in TAGS or el.get("contextRef") not in periodes or el.get("unitRef") not in usd or el.text is None:
            continue
        v = float(el.text.strip())
        v = int(v) if v.is_integer() else v
        cle = (tag,) + periodes[el.get("contextRef")]
        if cle in faits and faits[cle] != v:
            doubles.append(cle)
        faits.setdefault(cle, v)
    return candidats[0], faits, doubles


def annee(d1: str, d2: str) -> int:
    return (date.fromisoformat(d2) - date.fromisoformat(d1)).days


def calcul(cik: int) -> dict:
    fiche = json_de(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    r = fiche["filings"]["recent"]
    depots = sorted(({"accn": a, "forme": f, "depose": d, "periode": p}
                     for a, f, d, p, x in zip(r["accessionNumber"], r["form"], r["filingDate"], r["reportDate"], r["isXBRL"])
                     if f in ANNUELS and x == 1), key=lambda z: z["depose"], reverse=True)
    if not depots:
        return {"f_score": None, "raison": "aucun rapport annuel avec XBRL sur la fiche"}
    lus = {}

    def faits_de(depot):
        if depot["accn"] not in lus:
            lus[depot["accn"]] = instance(cik, depot["accn"])
        return lus[depot["accn"]][1]

    # Le dernier rapport annuel qui contient le bénéfice de l'exercice qu'il couvre
    rapport = exercice = None
    for depot in depots:
        f = faits_de(depot)
        for tag in DUREE["benefice"]:
            ex = [(k[1], k[2]) for k in f if k[0] == tag and k[1] and k[2] == depot["periode"] and 350 <= annee(k[1], k[2]) <= 380]
            if ex:
                rapport, exercice = depot, ex[0]
                break
        if rapport:
            break
    if rapport is None:
        return {"f_score": None, "raison": "aucun rapport annuel avec le bénéfice de son exercice"}
    f = faits_de(rapport)
    debut, fin = exercice
    d0 = date.fromisoformat(debut)
    avant = sorted({(k[1], k[2]) for k in f if k[0] in DUREE["benefice"] and k[1] and 350 <= annee(k[1], k[2]) <= 380
                    and d0 - timedelta(days=7) <= date.fromisoformat(k[2]) < d0})
    if not avant:
        return {"f_score": None, "raison": "pas d'exercice précédent dans le rapport", "accn": rapport["accn"]}
    debut1, fin1 = avant[-1]
    d1 = date.fromisoformat(debut1)
    # Bilan de fin t-2 : dans ce rapport s'il y est, sinon dans le rapport annuel précédent
    fin2 = None
    sources_t2 = [rapport] + [d for d in depots if d["depose"] < rapport["depose"] and d["periode"] < fin]
    for depot in sources_t2:
        g = faits_de(depot)
        dates = sorted(k[2] for k in g if k[0] == "Assets" and k[1] is None
                       and d1 - timedelta(days=7) <= date.fromisoformat(k[2]) < d1)
        if dates:
            fin2, actif2, source_t2 = dates[-1], g[("Assets", None, dates[-1])], depot["accn"]
            break
    if fin2 is None:
        return {"f_score": None, "raison": "pas de bilan de fin t-2", "accn": rapport["accn"]}
    v = {"t": {}, "t1": {}, "t2": {"actif": actif2}}
    etiquettes = {}
    for concept, tags in DUREE.items():
        for tag in tags:
            if (tag, debut, fin) in f:
                etiquettes[concept] = tag
                v["t"][concept] = f[(tag, debut, fin)]
                if (tag, debut1, fin1) in f:
                    v["t1"][concept] = f[(tag, debut1, fin1)]
                break
    for concept, tags in INSTANT.items():
        for tag in tags:
            if (tag, None, fin) in f:
                etiquettes[concept] = tag
                v["t"][concept] = f[(tag, None, fin)]
                if (tag, None, fin1) in f:
                    v["t1"][concept] = f[(tag, None, fin1)]
                break
    t, a = v["t"], v["t1"]
    base = {"accn": rapport["accn"], "forme": rapport["forme"], "depose": rapport["depose"], "instance": lus[rapport["accn"]][0],
            "debut": debut, "fin": fin, "debut1": debut1, "fin1": fin1, "fin2": fin2, "source_t2": source_t2,
            "etiquettes": etiquettes, "valeurs": v, "doubles": [list(x) for x in lus[rapport["accn"]][2]]}
    try:
        actif0, actif1 = t["actif"], a["actif"]
        roa, roa_avant = t["benefice"] / actif1, a["benefice"] / actif2
        cfo = t["flux"] / actif1
        lev = t.get("dette", 0) / ((actif0 + actif1) / 2)
        lev_avant = a.get("dette", 0) / ((actif1 + actif2) / 2)
        liq, liq_avant = t["ac"] / t["pc"], a["ac"] / a["pc"]

        def marge(x):
            return (x["brute"] if "brute" in x else x["ventes"] - x["cout"]) / x["ventes"]
        m, m_avant = marge(t), marge(a)
        rot, rot_avant = t["ventes"] / actif1, a["ventes"] / actif2
    except (KeyError, ZeroDivisionError) as exc:
        return {**base, "f_score": None, "raison": f"donnée manquante : {exc}"}
    oui = [roa > 0, cfo > 0, roa > roa_avant, cfo > roa, lev < lev_avant, liq > liq_avant, t.get("emission", 0) <= 0,
           m > m_avant, rot > rot_avant]
    criteres = dict(zip(ORDRE, [int(x) for x in oui]))
    return {**base, "f_score": sum(criteres.values()), "criteres": criteres}


(SORTIE / "companyfacts").mkdir(parents=True, exist_ok=True)
attendus = {}
for cik, sym in CIKS.items():
    dire(f"## {sym} (CIK {cik})")
    statut, b = lire(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", 200_000_000)
    if statut == 200:
        d = json.loads(b)
        us = d.get("facts", {}).get("us-gaap", {})
        reduit = {"cik": d.get("cik"), "entityName": d.get("entityName"), "facts": {"us-gaap": {
            t: {"units": {"USD": us[t]["units"]["USD"]}} for t in TAGS if "USD" in us.get(t, {}).get("units", {})}}}
        (SORTIE / "companyfacts" / f"{cik}.json").write_text(json.dumps(reduit, ensure_ascii=False, separators=(",", ":")),
                                                               encoding="utf-8")
        dire(f"- companyfacts : {len(b):,} octets · réduit à {len(reduit['facts']['us-gaap'])} étiquettes")
    else:
        dire(f"- companyfacts : {statut}")
    try:
        attendus[sym] = {"cik": cik, **calcul(cik)}
    except Exception as exc:  # noqa: BLE001
        attendus[sym] = {"cik": cik, "f_score": None, "raison": f"erreur du labo : {type(exc).__name__}: {exc}"[:300]}
    x = attendus[sym]
    dire(f"- calcul indépendant (instance XBRL {x.get('instance')}) : {x.get('forme')} {x.get('accn')} · exercice "
         f"{x.get('debut')} → {x.get('fin')} · avant {x.get('debut1')} → {x.get('fin1')} · bilan t-2 {x.get('fin2')} "
         f"({x.get('source_t2')}) · F-score {x.get('f_score')} {x.get('criteres') or x.get('raison')}")
    (SORTIE / "attendus.json").write_text(json.dumps(attendus, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8")
dire("")
dire("robots.txt : " + json.dumps({h: {k: v for k, v in x.items() if k in ("statut", "delai")} for h, x in robots.items()}))
