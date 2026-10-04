"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lot K : la santé financière (9 critères de Piotroski).

Pour chaque compagnie des listes du jour, le labo trouve lui-même son numéro SEC (fichier officiel company_tickers.json,
pas celui du robot), relit son dossier complet à la SEC (API « companyfacts » : une autre adresse que les fichiers
« frames » lus par le robot) et refait les 9 critères avec ce code :
- une compagnie montrée dans l'app (sante.json) doit avoir les mêmes 9 critères, le même total et le même rapport annuel ;
- son lien doit ouvrir ce rapport à la SEC, et ce doit être un rapport annuel (10-K, 20-F ou 40-F) ;
- une compagnie absente doit vraiment avoir un critère impossible à calculer (sinon : écart).
Définition de l'étude (Piotroski 2000, texte lu par le labo) : ROA et CFO divisés par l'actif du début de l'année, etc.
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
from datetime import date
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


DUREE = [("benefice", ["NetIncomeLoss", "ProfitLoss", "IncomeLossFromContinuingOperations"]),
         ("flux", ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]),
         ("ventes", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                     "RevenueFromContractWithCustomerIncludingAssessedTax"]),
         ("brute", ["GrossProfit"]), ("cout", ["CostOfRevenue", "CostOfGoodsAndServicesSold"]),
         ("emission", ["ProceedsFromIssuanceOfCommonStock", "StockIssuedDuringPeriodValueNewIssues"])]
INSTANT = [("actif", ["Assets"]), ("ac", ["AssetsCurrent"]), ("pc", ["LiabilitiesCurrent"]),
           ("dette", ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"])]
ORDRE = ["ROA", "CFO", "ΔROA", "ACCRUAL", "ΔLEVER", "ΔLIQUID", "EQ_OFFER", "ΔMARGIN", "ΔTURN"]
ANNUELS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A"}


def lire_dossier(dossier: dict, annee: int, s: str):
    """Les valeurs par exercice (t, t1, t2) : les faits que la SEC range dans la bonne période (champ « frame »)."""
    us = dossier.get("facts", {}).get("us-gaap", {})
    faits = {"t": {}, "t1": {}, "t2": {}}
    rapport = None
    for liste, periodes in ((DUREE, {"t": f"CY{annee}", "t1": f"CY{annee - 1}"}),
                            (INSTANT, {"t": f"CY{annee}Q4I", "t1": f"CY{annee - 1}Q4I", "t2": f"CY{annee - 2}Q4I"})):
        for nom, tags in liste:
            for cle, periode in periodes.items():
                for tag in tags:
                    trouve = [f for f in us.get(tag, {}).get("units", {}).get("USD", []) if f.get("frame") == periode]
                    if not trouve:
                        continue
                    if len({f["val"] for f in trouve}) > 1:
                        ecarts.append(f"{s} : {tag} {periode} a plusieurs valeurs au dossier de la SEC")
                    faits[cle][nom] = trouve[0]["val"]
                    if (nom, cle) == ("benefice", "t"):
                        rapport = trouve[0]
                    break
    return faits, rapport


def neuf(f):
    """Les 9 critères, refaits ici ; None si l'un ne se calcule pas."""
    t, a, b = f["t"], f["t1"], f["t2"]
    if not (t.get("actif") and a.get("actif") and b.get("actif")):
        return None
    actif0, actif1, actif2 = t["actif"], a["actif"], b["actif"]
    try:
        roa, roa_avant = t["benefice"] / actif1, a["benefice"] / actif2
        cfo = t["flux"] / actif1
        lev = t.get("dette", 0) / ((actif0 + actif1) / 2)
        lev_avant = a.get("dette", 0) / ((actif1 + actif2) / 2)
        liq, liq_avant = t["ac"] / t["pc"], a["ac"] / a["pc"]

        def marge(x):
            brute = x["brute"] if "brute" in x else x["ventes"] - x["cout"]
            return brute / x["ventes"]
        m, m_avant = marge(t), marge(a)
        rot, rot_avant = t["ventes"] / actif1, a["ventes"] / actif2
    except (KeyError, ZeroDivisionError):
        return None
    oui = [roa > 0, cfo > 0, roa > roa_avant, cfo > roa, lev < lev_avant, liq > liq_avant, t.get("emission", 0) <= 0,
           m > m_avant, rot > rot_avant]
    return dict(zip(ORDRE, [int(x) for x in oui]))


auj = json.loads((racine / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
chemin_app = racine / "app" / "sante.json"
app = json.loads(chemin_app.read_text(encoding="utf-8")) if chemin_app.exists() else {}
listes = [x["symbole"] for x in auj.get("hausse", []) + auj.get("baisse", [])]
montres = app.get("par_symbole", {})
jour = date.today()
annee = jour.year - 1 if jour.month >= 4 else jour.year - 2  # dernière année civile complète (10-K : 90 jours au plus)
dire(f"Santé financière : {len(montres)} compagnie(s) montrée(s) sur {len(listes)} des listes · "
     f"cadre de l'app {app.get('cadre')} · attendu le {jour} : CY{annee}")
if app.get("cadre") != f"CY{annee}":
    ecarts.append(f"cadre de l'app {app.get('cadre')} au lieu de CY{annee}")
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
    dossier = json.loads(lire(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"))
    faits, rapport = lire_dossier(dossier, annee, s)
    refait = neuf(faits)
    if x is None and refait is None:
        dire(f"- {s} : un critère impossible à calculer ici aussi · absente de l'app, comme il faut")
        continue
    if x is None:
        ecarts.append(f"{s} : le labo calcule {sum(refait.values())}/9, mais l'app ne montre rien")
        dire(f"- {s} : ÉCART, le labo calcule {sum(refait.values())}/9 ({refait})")
        continue
    if refait is None:
        ecarts.append(f"{s} : l'app montre {x['f_score']}/9, le labo ne peut pas le calculer")
        dire(f"- {s} : ÉCART, montrée {x['f_score']}/9 sans données complètes au dossier")
        continue
    pareil = refait == x["criteres"] and sum(refait.values()) == x["f_score"]
    meme_rapport = rapport is not None and (rapport.get("accn"), rapport.get("start"), rapport.get("end")) == (
        x["accn"], x["debut"], x["fin"])
    lien_attendu = f"https://www.sec.gov/Archives/edgar/data/{cik}/{x['accn'].replace('-', '')}/{x['accn']}-index.htm"
    page = lire(x["lien"]).decode("utf-8", "replace") if x["lien"] == lien_attendu else ""
    forme = re.search(r"Form ([0-9A-Z][0-9A-Z/\-]*)", page)
    forme = forme.group(1) if forme else None
    lien_ok = x["lien"] == lien_attendu and x["accn"] in page and forme in ANNUELS
    if not (pareil and meme_rapport and lien_ok):
        ecarts.append(f"{s} : app {x['f_score']}/9 {x['criteres']} · labo {sum(refait.values())}/9 {refait} · "
                      f"rapport {rapport and rapport.get('accn')} / {x['accn']} · lien {x['lien']} (formulaire {forme})")
    dire(f"- {s} : app {x['f_score']}/9 · labo {sum(refait.values())}/9 · 9 critères identiques : {'OUI' if pareil else 'NON'}"
         f" · même rapport ({x['accn']}, exercice {x['debut']} → {x['fin']}) : {'OUI' if meme_rapport else 'NON'}"
         f" · lien ouvert à la SEC : formulaire {forme} {'OK' if lien_ok else 'NON'}")
dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chaque score refait à partir du dossier officiel de la compagnie à la SEC.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
