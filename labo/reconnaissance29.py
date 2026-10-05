"""Reconnaissance 29 : le Trésor est-il vraiment en pause ? Et le nombre d'actions le plus récent : frames, companyfacts
ou companyconcept ?"""
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/recon29")
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

import json
from datetime import date, datetime, timedelta

DONNEES = Path(sys.argv[1])
(SORTIE / "fixtures").mkdir(exist_ok=True)


def json_de(url):
    statut, b = lire(url, 50_000_000)
    if statut != 200:
        raise RuntimeError(f"{url} : {statut}")
    return json.loads(b)


dire("# Reconnaissance 29 : Trésor « en pause » et actions en circulation les plus récentes\n")

# ---------- A. Trésor : écarts normaux entre deux publications ----------
dire("## A. Trésor américain (Fiscal Data)")
API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
dates = set()
page = 1
while True:
    d = json_de(API + "v1/accounting/od/auctions_query?filter=security_type:in:(Note,Bond),auction_date:gte:2023-01-01"
                f"&fields=auction_date,security_type,security_term,cusip&sort=-auction_date&page[size]=1000&page[number]={page}")
    for r in d["data"]:
        dates.add(r["auction_date"])
    if page >= d["meta"]["total-pages"]:
        break
    page += 1
dates = sorted(dates)
dire(f"- adjudications d'obligations (notes et bonds, TIPS compris) depuis 2023 : {len(dates)} dates · dernière {dates[-1]}")
ecarts = sorted(((date.fromisoformat(b) - date.fromisoformat(a)).days, a, b) for a, b in zip(dates, dates[1:]))
dire(f"- 10 plus grands écarts entre 2 adjudications : {ecarts[-10:]}")
mts = json_de(API + "v1/accounting/mts/mts_table_1?fields=record_date&sort=-record_date&page[size]=40")["data"]
dire(f"- état mensuel (MTS) : derniers mois {[r['record_date'] for r in mts[:6]]}")
try:
    cal = json_de("https://api.fiscaldata.treasury.gov/services/calendar/release")
    rel = [r for r in cal if r.get("datasetId") == "015-BFS-2014Q1-13"]
    dire(f"- calendrier officiel, état mensuel : {sorted((r.get('date'), r.get('time')) for r in rel)[-6:]}")
except Exception as exc:  # noqa: BLE001
    dire(f"- calendrier officiel : {type(exc).__name__}: {exc}")
try:
    up = json_de(API + "v1/accounting/od/upcoming_auctions?sort=auction_date&page[size]=50")["data"]
    dire(f"- prochaines adjudications annoncées : {[(r['auction_date'], r['security_type'], r['security_term']) for r in up]}")
except Exception as exc:  # noqa: BLE001
    dire(f"- prochaines adjudications : {type(exc).__name__}: {exc}")
etat = json.loads((DONNEES / "etat_sources.json").read_text(encoding="utf-8")).get("tresor", {})
dire(f"- état du robot : dernier contenu {etat.get('dernier_contenu')} · dernière lecture réussie {etat.get('dernier_succes')}")

# ---------- B. Actions en circulation : frames, companyfacts et companyconcept ----------
dire("\n## B. Actions en circulation : le fait le plus récent selon 3 API de la SEC")
evs = [json.loads(l) for f in sorted((DONNEES / "evenements").glob("*.jsonl"))[-4:]
       for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
jour = date(2026, 10, 5)
achats = sorted({e["tickers"][0] for e in evs if e["source"] == "sec_form4" and e["kind"] == "achat_initie" and e.get("tickers")
                 and (jour - date.fromisoformat(e["published_on"])).days <= 90})
em = json.loads((DONNEES / "sec" / "emetteurs.json").read_text(encoding="utf-8"))
taille = json.loads((DONNEES / "prix" / "taille.json").read_text(encoding="utf-8"))
p30, p70 = taille["seuils"]["p30"], taille["seuils"]["p70"]
dire(f"- compagnies avec un achat de dirigeant depuis 90 jours : {len(achats)}")


def classe(val, prix):
    v = val * prix / 1e6
    return "petite" if v < p30 else "grande" if v >= p70 else "moyenne"


resume = {"concept plus récent": 0, "frames plus récent": 0, "pareil": 0, "sans fait": 0, "classe change": 0}
garder = {"ASPI", "FLNA", "GME", "PRHI", "FUL", "QVCG"}
for s in achats:
    f = em.get(s)
    if not f or not f.get("cik"):
        continue
    cik = f["cik"]
    statut, b = lire(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/dei/EntityCommonStockSharesOutstanding.json")
    faits = json.loads(b)["units"].get("shares", []) if statut == 200 else []
    if s in garder and statut == 200:
        (SORTIE / "fixtures" / f"concept_CIK{cik:010d}.json").write_bytes(b)
    concept = max(faits, key=lambda x: (x["end"], x["filed"]), default=None)
    frames = taille["actions"].get(str(cik))
    prix = taille["prix"].get(s)
    if not concept and not frames:
        resume["sans fait"] += 1
        quoi = "aucun fait"
    elif concept and (not frames or concept["end"] > frames[1]):
        resume["concept plus récent"] += 1
        quoi = "companyconcept plus récent"
    elif frames and (not concept or frames[1] > concept["end"]):
        resume["frames plus récent"] += 1
        quoi = "frames plus récent"
    else:
        resume["pareil"] += 1
        quoi = "même date"
    change = ""
    if concept and frames and prix and concept["val"] >= 500_000 and frames[0] >= 500_000:
        a, n = classe(frames[0], prix[1]), classe(concept["val"], prix[1])
        if a != n:
            resume["classe change"] += 1
            change = f" · CLASSE {a} → {n}"
    dire(f"- {s} (CIK {cik}) : companyconcept {statut} {(concept['val'], concept['end'], concept.get('form')) if concept else None} · "
         f"frames {frames} · {quoi}{change}")
dire(f"- résumé : {resume}")
dire("\nVERDICT : recherche faite")
