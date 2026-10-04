"""Lot K : extraits des fichiers « frames » de la SEC pour les tests du robot (mêmes règles d'accès que le robot)."""
import csv
import gzip
import html
import io
import json
import re
import sys
import time
import urllib.robotparser
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/fixtures-lotK")
SORTIE.mkdir(parents=True, exist_ok=True)
DONNEES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("principal/data")
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





# Extraits des fichiers officiels « frames » de la SEC (XBRL) pour quelques compagnies : les tests du robot (lot K)
# rejouent ces vraies lignes. Les F-scores attendus viennent de la recherche du labo (resultats-fscore/details.json).
CIKS = {1326380: "GME", 39368: "FUL", 896493: "GPUS", 1821806: "LESL", 1582313: "XENE", 1502292: "PRHI",
        320193: "AAPL", 2488: "AMD"}
FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{periode}.json"
DUREE = ["NetIncomeLoss", "ProfitLoss", "IncomeLossFromContinuingOperations", "NetCashProvidedByUsedInOperatingActivities",
         "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "Revenues",
         "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
         "GrossProfit", "CostOfRevenue", "CostOfGoodsAndServicesSold", "ProceedsFromIssuanceOfCommonStock",
         "StockIssuedDuringPeriodValueNewIssues"]
INSTANT = ["Assets", "AssetsCurrent", "LiabilitiesCurrent", "LongTermDebtNoncurrent", "LongTermDebt",
           "LongTermDebtAndCapitalLeaseObligations"]
extraits = {}
for tags, periodes in ((DUREE, ["CY2025", "CY2024"]), (INSTANT, ["CY2025Q4I", "CY2024Q4I", "CY2023Q4I"])):
    for tag in tags:
        for periode in periodes:
            statut, octets = lire(FRAMES.format(tag=tag, periode=periode), 60_000_000)
            if statut != 200:
                dire(f"{tag} {periode} : réponse {statut}")
                continue
            d = json.loads(octets)
            extraits[f"{tag}|{periode}"] = {k: d.get(k) for k in ("taxonomy", "tag", "ccp", "uom", "label", "pts")} | {
                "data": [x for x in d.get("data", []) if x.get("cik") in CIKS]}
            dire(f"{tag} {periode} : {len(d.get('data', []))} compagnies, gardées {len(extraits[f'{tag}|{periode}']['data'])}")
(SORTIE / "frames_extraits.json").write_text(json.dumps(extraits, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
attendus = json.loads(Path("labo/resultats-fscore/details.json").read_text(encoding="utf-8"))
(SORTIE / "attendus.json").write_text(json.dumps({s: attendus.get(s) for s in CIKS.values()}, ensure_ascii=False, indent=1,
                                                   sort_keys=True), encoding="utf-8")
dire("Attendus (recherche du labo) : " + ", ".join(f"{s} {(attendus.get(s) or {}).get('f_score')}" for s in CIKS.values()))
