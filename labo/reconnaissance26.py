"""Recherche avant le plan de match (lot K) : la santé financière (F-score de Piotroski, 2000) se calcule-t-elle avec les
données officielles de la SEC (XBRL, API « frames ») pour les compagnies que Radar suit ? Et l'étude : ses 9 critères lus
dans le texte, si son site permet les robots. Mêmes règles d'accès que le robot (robots.txt, délais, identification).
"""
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
SORTIE = Path("labo/resultats-fscore")
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




# ---------- A. L'étude : les 9 critères lus dans le texte (si le site permet les robots) ----------
ETUDE = ["https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf",
         "https://www.anderson.ucla.edu/documents/areas/prg/asam/2019/F-Score.pdf"]
dire("# Lot K : recherche avant le plan de match (santé financière, F-score de Piotroski 2000)")
dire("")
dire("## A. L'étude")
for url in ETUDE:
    statut, octets = lire(url, 15_000_000)
    if statut is None:
        dire(f"- {url} : robots.txt ne permet pas, non lue")
        continue
    if statut != 200 or not (octets or b"").startswith(b"%PDF"):
        dire(f"- {url} : réponse {statut}, pas un PDF")
        continue
    import hashlib, subprocess
    (SORTIE / "etude.pdf").write_bytes(octets)
    t = subprocess.run(["pdftotext", "-layout", str(SORTIE / "etude.pdf"), "-"], capture_output=True, text=True).stdout
    (SORTIE / "etude.pdf").unlink()
    dire(f"- {url} : lue ({len(octets)} octets, SHA-256 {hashlib.sha256(octets).hexdigest()[:16]}…, {t.count(chr(12)) + 1} pages)")
    morceaux = []
    for mot in ("ROA", "CFO", "ACCRUAL", "LEVER", "LIQUID", "EQ_OFFER", "MARGIN", "TURN", "F_SCORE"):
        i = t.find(mot)
        if i >= 0:
            morceaux.append(f"=== {mot} ===\n" + t[max(0, i - 300):i + 900])
    (SORTIE / "etude-extraits.txt").write_text("\n\n".join(morceaux), encoding="utf-8")
    dire(f"- extraits autour des 9 critères : etude-extraits.txt ({len(morceaux)} passages)")
    break

# ---------- B. Les données officielles de la SEC (XBRL, API « frames ») ----------
dire("")
dire("## B. Couverture des données officielles de la SEC (exercice 2025, comparé à 2024)")
FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{periode}.json"
DUREE = {"benefice": ["NetIncomeLoss", "ProfitLoss", "IncomeLossFromContinuingOperations"],
         "flux": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
         "ventes": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                    "RevenueFromContractWithCustomerIncludingAssessedTax"],
         "marge_brute": ["GrossProfit"],
         "cout_ventes": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
         "emission": ["ProceedsFromIssuanceOfCommonStock", "StockIssuedDuringPeriodValueNewIssues"]}
INSTANT = {"actif": ["Assets"], "actif_court": ["AssetsCurrent"], "passif_court": ["LiabilitiesCurrent"],
           "dette_lt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"]}
ANNEES = {"t": "CY2025", "t1": "CY2024"}
FINS = {"t": "CY2025Q4I", "t1": "CY2024Q4I", "t2": "CY2023Q4I"}
valeurs = {}  # (concept, période) -> {cik: val}
for groupe, periodes in ((DUREE, ANNEES), (INSTANT, FINS)):
    for concept, tags in groupe.items():
        for cle, periode in periodes.items():
            fusion = {}
            for tag in tags:  # premier tag trouvé pour la compagnie : gardé (ordre de préférence)
                statut, octets = lire(FRAMES.format(tag=tag, periode=periode), 60_000_000)
                if statut != 200:
                    dire(f"- {tag} {periode} : réponse {statut}")
                    continue
                d = json.loads(octets)
                for x in d.get("data", []):
                    fusion.setdefault(x["cik"], x["val"])
            valeurs[(concept, cle)] = fusion
            print(f"{concept} {cle} : {len(fusion)} compagnies", flush=True)

def v(concept, cle, cik):
    return valeurs.get((concept, cle), {}).get(cik)

def signaux(cik, souple):
    """Les 9 critères (1, 0 ou None si une donnée manque). souple : dette absente = 0, émission absente = aucune."""
    a0, a1, a2 = v("actif", "t", cik), v("actif", "t1", cik), v("actif", "t2", cik)
    ni0, ni1 = v("benefice", "t", cik), v("benefice", "t1", cik)
    cfo0 = v("flux", "t", cik)
    s0, s1 = v("ventes", "t", cik), v("ventes", "t1", cik)
    def marge(cle):
        gp = v("marge_brute", cle, cik)
        s = v("ventes", cle, cik)
        if gp is None and s is not None and v("cout_ventes", cle, cik) is not None:
            gp = s - v("cout_ventes", cle, cik)
        return gp / s if gp is not None and s else None
    def ratio(n, d):
        return n / d if n is not None and d else None
    roa0, roa1 = ratio(ni0, a1), ratio(ni1, a2)
    cfo_r = ratio(cfo0, a1)
    d0, d1 = v("dette_lt", "t", cik), v("dette_lt", "t1", cik)
    if souple:
        d0, d1 = (d0 or 0) if a0 else None, (d1 or 0) if a1 else None
    lev0 = d0 / ((a0 + a1) / 2) if d0 is not None and a0 and a1 else None
    lev1 = d1 / ((a1 + a2) / 2) if d1 is not None and a1 and a2 else None
    cr0, cr1 = ratio(v("actif_court", "t", cik), v("passif_court", "t", cik)), ratio(v("actif_court", "t1", cik), v("passif_court", "t1", cik))
    em = v("emission", "t", cik)
    if souple and em is None and a0:
        em = 0
    m0, m1 = marge("t"), marge("t1")
    tu0, tu1 = ratio(s0, a1), ratio(s1, a2)
    b = lambda c: None if c is None else int(bool(c))
    return {"ROA": b(roa0 is not None and roa0 > 0) if roa0 is not None else None,
            "CFO": b(cfo0 > 0) if cfo0 is not None else None,
            "ΔROA": b(roa0 > roa1) if roa0 is not None and roa1 is not None else None,
            "ACCRUAL": b(cfo_r > roa0) if cfo_r is not None and roa0 is not None else None,
            "ΔLEVER": b(lev0 < lev1) if lev0 is not None and lev1 is not None else None,
            "ΔLIQUID": b(cr0 > cr1) if cr0 is not None and cr1 is not None else None,
            "EQ_OFFER": b(em <= 0) if em is not None else None,
            "ΔMARGIN": b(m0 > m1) if m0 is not None and m1 is not None else None,
            "ΔTURN": b(tu0 > tu1) if tu0 is not None and tu1 is not None else None}

emetteurs = json.loads((DONNEES / "sec" / "emetteurs.json").read_text(encoding="utf-8"))
auj = json.loads((DONNEES / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
listes = [x["symbole"] for x in auj["hausse"] + auj["baisse"]]
univers = {s: e["cik"] for s, e in emetteurs.items() if e.get("cik") and e.get("type") == "compagnie"}
details = {}
for nom, symboles in (("Compagnies que Radar connaît (fiches SEC lues)", list(univers)), ("Compagnies des listes du jour", listes)):
    dire("")
    dire(f"### {nom} : {len(symboles)}")
    for souple in (False, True):
        complets, manques, sans_rien, scores = 0, {}, 0, {}
        for s in symboles:
            cik = univers.get(s) or (emetteurs.get(s) or {}).get("cik")
            if not cik:
                sans_rien += 1
                continue
            sig = signaux(cik, souple)
            if all(x is None for x in sig.values()):
                sans_rien += 1
            if all(x is not None for x in sig.values()):
                complets += 1
                f = sum(sig.values())
                scores[f] = scores.get(f, 0) + 1
            for k, x in sig.items():
                if x is None:
                    manques[k] = manques.get(k, 0) + 1
            if souple:
                details[s] = {"cik": cik, "signaux": sig, "f_score": sum(sig.values()) if all(x is not None for x in sig.values()) else None}
        regle = "souple (dette absente = 0, émission absente = aucune)" if souple else "stricte (chaque donnée publiée)"
        dire(f"- Règle {regle} : score complet {complets}/{len(symboles)} ({complets / max(1, len(symboles)) * 100:.0f} %) · "
             f"aucune donnée us-gaap : {sans_rien} · critères qui manquent le plus : "
             + ", ".join(f"{k} {n}" for k, n in sorted(manques.items(), key=lambda kv: -kv[1])[:5])
             + f" · scores 0 à 9 : {dict(sorted(scores.items()))}")
dire("")
dire("### Les compagnies des listes du jour, une par une (règle souple)")
for s in listes:
    d = details.get(s)
    if not d:
        dire(f"- {s} : pas de numéro SEC connu")
        continue
    manque = [k for k, x in d["signaux"].items() if x is None]
    dire(f"- {s} (CIK {d['cik']}) : " + (f"F-score {d['f_score']}/9" if d["f_score"] is not None else "incomplet, manque " + ", ".join(manque)))
(SORTIE / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
dire("")
dire("Robots.txt lus : " + ", ".join(f"{h} ({r.get('statut')})" for h, r in robots.items()))
