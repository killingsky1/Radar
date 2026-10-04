"""Contre-vérification INDÉPENDANTE du lot K (refait) : la santé financière (9 critères de Piotroski).

Le robot lit le dossier « companyfacts » de la SEC. Le labo, lui, ne le lit pas : pour chaque compagnie des listes, il
trouve son numéro SEC (fichier officiel company_tickers.json), son dernier rapport annuel sur sa fiche officielle
(data.sec.gov/submissions), puis lit le fichier XBRL (instance) de ce rapport dans le dossier du dépôt à la SEC, et celui
du rapport annuel précédent pour le bilan de fin t-2. Il refait les 9 critères avec ce code, puis :
- une compagnie montrée dans l'app (sante.json) doit avoir les mêmes 9 critères, le même total, le même rapport annuel
  et le même exercice ;
- son lien doit ouvrir ce rapport à la SEC, et la page de la SEC doit dire que c'est un rapport annuel (10-K, 20-F, 40-F) ;
- une compagnie absente doit vraiment avoir un critère impossible à calculer (sinon : écart).
Même règle que le robot : dette à long terme non déclarée = 0, émission d'actions non déclarée = aucune.
Mêmes règles d'accès : robots.txt lu d'abord, 1,5 s entre deux requêtes, identification avec le courriel (SEC).
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lotK.txt")
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
ecarts, sortie, dernier, robots = [], [], [0.0], {}


def dire(t=""):
    print(t, flush=True)
    sortie.append(t)


def lire(url):
    hote = url.split("/")[2]
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with urllib.request.urlopen(urllib.request.Request(f"https://{hote}/robots.txt", headers={"User-Agent": UA_SEC}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) or e.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True  # 404 : pas de robots.txt, tout est permis
        robots[hote] = rp
    if not robots[hote].can_fetch(UA_SEC, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    attente = 1.5 - (time.monotonic() - dernier[0])
    if attente > 0:
        time.sleep(attente)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA_SEC}), timeout=180) as r:
            return r.read()
    finally:
        dernier[0] = time.monotonic()


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


def json_de(url):
    return json.loads(lire(url))


def instance(cik: int, accn: str):
    """Le fichier XBRL (instance) d'un dépôt : (nom, faits) ; faits = {(étiquette, début, fin): valeur} sans les axes."""
    dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}"
    noms = [x["name"] for x in json_de(f"{dossier}/index.json")["directory"]["item"]]
    candidats = [n for n in noms if n.endswith("_htm.xml")] or [
        n for n in noms if n.endswith(".xml") and n != "FilingSummary.xml" and not n.endswith(
            ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml"))]
    if len(candidats) != 1:
        raise RuntimeError(f"{accn} : instance introuvable ou ambiguë ({candidats[:5]})")
    racine = ET.fromstring(lire(f"{dossier}/{candidats[0]}"))
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



auj = json.loads((racine / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
chemin_app = racine / "app" / "sante.json"
app = json.loads(chemin_app.read_text(encoding="utf-8")) if chemin_app.exists() else {}
listes = [x["symbole"] for x in auj.get("hausse", []) + auj.get("baisse", [])]
montres = app.get("par_symbole", {})
dire(f"Santé financière : {len(montres)} compagnie(s) montrée(s) sur {len(listes)} des listes · calcul {app.get('version')}")
if app.get("version") != "sante-2":
    ecarts.append(f"sante.json : calcul {app.get('version')} au lieu de sante-2 (rapport annuel)")
if set(montres) - set(listes):
    ecarts.append(f"montrées sans être dans les listes : {sorted(set(montres) - set(listes))}")
tickers = {x["ticker"].upper(): int(x["cik_str"])
           for x in json.loads(lire("https://www.sec.gov/files/company_tickers.json")).values()}
for s in listes:
    cik = next((tickers[v] for v in (s, s.replace(".", "-"), s.replace("-", ".")) if v in tickers), None)
    x = montres.get(s)
    if cik is None:
        if x is not None:
            ecarts.append(f"{s} : montrée, mais absente du fichier des symboles de la SEC")
        dire(f"- {s} : pas dans le fichier des symboles de la SEC, pas de score")
        continue
    if x is not None and x.get("cik") != cik:
        ecarts.append(f"{s} : numéro SEC {x.get('cik')} dans l'app, {cik} selon la SEC")
    try:
        refait = calcul(cik)
    except Exception as exc:  # noqa: BLE001
        refait = {"f_score": None, "raison": f"le labo n'a pas pu lire : {type(exc).__name__}: {str(exc)[:150]}"}
        if x is not None:
            ecarts.append(f"{s} : montrée {x['f_score']}/9, le labo n'a pas pu la refaire ({refait['raison']})")
    if x is None and refait["f_score"] is None:
        dire(f"- {s} : pas de score ici non plus ({refait.get('raison')}) · absente de l'app, comme il faut")
        continue
    if x is None:
        ecarts.append(f"{s} : le labo calcule {refait['f_score']}/9 ({refait['forme']} {refait['accn']}), mais l'app ne montre rien")
        dire(f"- {s} : ÉCART, le labo calcule {refait['f_score']}/9 avec son {refait['forme']} {refait['accn']}")
        continue
    if refait["f_score"] is None:
        ecarts.append(f"{s} : l'app montre {x['f_score']}/9, le labo ne peut pas le calculer ({refait.get('raison')})")
        dire(f"- {s} : ÉCART, montrée {x['f_score']}/9 · labo : {refait.get('raison')}")
        continue
    pareil = refait["criteres"] == x["criteres"] and refait["f_score"] == x["f_score"]
    meme_rapport = (refait["accn"], refait["forme"], refait["debut"], refait["fin"]) == (x["accn"], x["forme"], x["debut"], x["fin"])
    lien_attendu = f"https://www.sec.gov/Archives/edgar/data/{cik}/{refait['accn'].replace('-', '')}/{refait['accn']}-index.htm"
    page = lire(x["lien"]).decode("utf-8", "replace") if x["lien"] == lien_attendu else ""
    forme = re.search(r"Form ([0-9A-Z][0-9A-Z/\-]*(?: \d+[A-Z]?)?)", page)
    forme = forme.group(1) if forme else None
    lien_ok = x["lien"] == lien_attendu and refait["accn"] in page and forme in ANNUELS
    if not (pareil and meme_rapport and lien_ok):
        ecarts.append(f"{s} : app {x['f_score']}/9 {x['criteres']} {x['forme']} {x['accn']} {x['debut']}→{x['fin']} · labo "
                      f"{refait['f_score']}/9 {refait['criteres']} {refait['forme']} {refait['accn']} {refait['debut']}→{refait['fin']}"
                      f" · lien {x['lien']} (page de la SEC : formulaire {forme})")
    dire(f"- {s} : app {x['f_score']}/9 · labo {refait['f_score']}/9 (fichier {refait['instance']}) · 9 critères identiques : "
         f"{'OUI' if pareil else 'NON'} · même rapport annuel ({refait['forme']} {refait['accn']}, exercice {refait['debut']} → "
         f"{refait['fin']}, bilan t-2 au {refait['fin2']}) : {'OUI' if meme_rapport else 'NON'} · lien ouvert à la SEC : "
         f"formulaire {forme} {'OK' if lien_ok else 'NON'}")
dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chaque score refait en lisant le fichier XBRL du rapport annuel de la compagnie.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
