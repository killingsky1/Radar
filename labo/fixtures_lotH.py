"""Lot H : vrais dépôts (8-K de rachats d'actions) pour les tests du robot, rachats réels en XBRL (API officielle de la
SEC, « frames ») et résumés des études, lus de façon permise (robots.txt d'abord ; aucun compte, aucun courriel envoyé)."""
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
SORTIE = Path("labo/resultats-lotH")
SORTIE.mkdir(parents=True, exist_ok=True)
DONNEES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("principal/data")
DEBUT = time.monotonic()
LIMITE_S = 70 * 60  # le travail E s'arrête proprement avant la fin du temps permis
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


BLOC = re.compile(r"</?(?:p|div|td|th|tr|br|li|h\d|table|center|font\s+size)\b[^>]*>", re.I)


def texte_html(raw: str) -> str:
    raw = BLOC.sub(" ", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return " ".join(html.unescape(raw).replace("​", " ").replace("\xa0", " ").split())


def phrases_cles(texte, mots, n=30):
    out = []
    for p in re.split(r"(?<=[.!?;])\s+", texte):
        if any(re.search(m, p, re.I) for m in mots) and len(p) < 1500:
            out.append(p.strip())
        if len(out) >= n:
            break
    return out




SORTIE = Path("labo/fixtures-lotH")
SORTIE.mkdir(parents=True, exist_ok=True)
resume.clear()
dire("# Lot H : vrais dépôts pour les tests, rachats réels en XBRL, résumés des études")
ARCH = "https://www.sec.gov/Archives"
statut, contenu = lire("https://www.sec.gov/files/company_tickers_exchange.json")
cotes = {int(l[0]): l[2] for l in json.loads(contenu)["data"]}
filers = {}
for jour in ("20260930", "20261001", "20261002"):
    statut, contenu = lire(f"{ARCH}/edgar/daily-index/2026/QTR{4 if jour >= '20261001' else 3}/master.{jour}.idx")
    for l in contenu.decode("latin-1").splitlines():
        p = l.split("|")
        if len(p) == 5 and p[0].strip().isdigit():
            filers.setdefault(p[4].rsplit("/", 1)[1].removesuffix(".txt"), []).append((int(p[0]), p[1].strip(), p[2], jour))
ACCS = {"acn": "0001467373-26-000037", "nbhc": "0001104659-26-112856", "aout": "0001808997-26-000052",
        "nws": "0001564708-26-000213", "avax": "0001493152-26-045263"}
pages = {}


def garder(cle, url, contenu):
    nom = f"{cle}.gz"
    (SORTIE / nom).write_bytes(gzip.compress(contenu, 9))
    pages[url] = nom


for cle, acc in ACCS.items():
    fs = filers.get(acc)
    if not fs:
        dire(f"- {cle} {acc} : absent des index du 30 septembre au 2 octobre")
        continue
    cik = next((c for c, *_ in fs if c in cotes), fs[0][0])
    dossier = f"{ARCH}/edgar/data/{cik}/{acc.replace('-', '')}"
    s1, entete = lire(f"{dossier}/{acc}-index-headers.html")
    s2, index = lire(f"{dossier}/{acc}-index.htm")
    garder(f"{cle}_entete", f"{dossier}/{acc}-index-headers.html", entete)
    garder(f"{cle}_index", f"{dossier}/{acc}-index.htm", index)
    docs = []
    for ligne in re.findall(r"<tr[^>]*>(.*?)</tr>", index.decode("utf-8", "replace"), re.S):
        lien = re.search(r'href="(?:/ix\?doc=)?(/Archives/edgar/data/[^"]+\.htm)"', ligne)
        cellules = re.findall(r"<td[^>]*>([^<]*)</td>", ligne)
        if lien and len(cellules) >= 2:
            sorte = cellules[-2].strip()
            if sorte in ("8-K", "8-K/A") or sorte.startswith("EX-99"):
                docs.append(("https://www.sec.gov" + lien.group(1), sorte))
    for i, (url, sorte) in enumerate(docs[:4]):
        s3, doc = lire(url)
        garder(f"{cle}_doc_{i}", url, doc)
    dire(f"- {cle} : {fs[0][1]} · CIK {cik} ({cotes.get(cik, 'non coté')}) · déposé {fs[0][3]} · en-tête {s1} · index {s2}"
         f" · documents {[s for _, s in docs[:4]]}")
(SORTIE / "pages.json").write_text(json.dumps(pages, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# ---------- Rachats réels en XBRL : API officielle data.sec.gov (frames et companyconcept) ----------
dire()
dire("## Rachats réels en XBRL (data.sec.gov)")
FRAME = "https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2025.json"
statut, contenu = lire(FRAME, 60_000_000)
dire(f"- robots.txt de data.sec.gov : HTTP {robots['data.sec.gov']['statut']} · frames CY2025 : HTTP {statut}, {len(contenu)} octets")
if statut == 200:
    (SORTIE / "frames_CY2025.json.gz").write_bytes(gzip.compress(contenu, 9))
    f = json.loads(contenu)
    d = f["data"]
    dire(f"- {len(d)} compagnies · champs : {sorted(d[0])} · entête : { {k: v for k, v in f.items() if k != 'data'} }")
    from collections import Counter
    dire(f"- périodes (fin) les plus fréquentes : {Counter(x['end'] for x in d).most_common(6)}")
    dire(f"- périodes (début) : {Counter(x['start'] for x in d).most_common(6)}")
    longs = Counter((date.fromisoformat(x['end']) - date.fromisoformat(x['start'])).days for x in d)
    dire(f"- durées (jours) : {sorted(longs.items())[:3]} … {sorted(longs.items())[-3:]}")
    dire(f"- valeurs nulles ou négatives : {sum(1 for x in d if x['val'] <= 0)} · CIK en double : {len(d) - len({x['cik'] for x in d})}")
    for cik in (1467373, 320193, 1475841, 1808997, 1564708):
        x = next((x for x in d if x["cik"] == cik), None)
        dire(f"  - CIK {cik} ({cotes.get(cik)}) : {x}")
    cotees = [x for x in d if x["cik"] in cotes]
    dire(f"- dont compagnies cotées (liste de la SEC) : {len(cotees)}")
for cik in (1467373, 320193):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/PaymentsForRepurchaseOfCommonStock.json"
    statut, contenu = lire(url, 20_000_000)
    if statut != 200:
        dire(f"- companyconcept {cik} : HTTP {statut}")
        continue
    (SORTIE / f"concept_{cik}.json.gz").write_bytes(gzip.compress(contenu, 9))
    faits = json.loads(contenu)["units"]["USD"]
    for x in faits:
        if x.get("frame") in ("CY2025", "CY2024"):
            dire(f"  - {cik} {x['frame']} : {x}")

# ---------- Résumés des études (lecture permise seulement) ----------
dire()
dire("## Résumés des études (API Crossref et OpenAlex, page NBER) : lus seulement si robots.txt le permet")
ETUDES = {"fu_huang_2016": "10.1287/mnsc.2014.2165", "ikenberry_1995": "10.1016/0304-405X(95)00826-Z",
          "peyer_vermaelen_2009": "10.1093/rfs/hhn024"}
etudes = {}
for cle, doi in ETUDES.items():
    e = etudes[cle] = {"doi": doi}
    statut, contenu = lire(f"https://api.crossref.org/works/{doi}")
    e["crossref"] = statut
    if statut == 200:
        m = json.loads(contenu)["message"]
        e["titre"] = (m.get("title") or [""])[0]
        e["revue"] = (m.get("container-title") or [""])[0]
        e["auteurs"] = [a.get("family") for a in m.get("author", [])]
        e["annee"] = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
        e["resume_crossref"] = m.get("abstract")
    statut, contenu = lire(f"https://api.openalex.org/works/doi:{doi}")
    e["openalex"] = statut
    if statut == 200:
        m = json.loads(contenu)
        inv = m.get("abstract_inverted_index") or {}
        mots = sorted((i, w) for w, ii in inv.items() for i in ii)
        e["resume_openalex"] = " ".join(w for _, w in mots) or None
    dire(f"- {cle} ({doi}) : Crossref {e['crossref']} · OpenAlex {e['openalex']} · « {e.get('titre')} » "
         f"({e.get('revue')}, {e.get('annee')}, {e.get('auteurs')})")
    dire(f"  - résumé Crossref : {(e.get('resume_crossref') or '(aucun)')[:1500]}")
    dire(f"  - résumé OpenAlex : {(e.get('resume_openalex') or '(aucun)')[:1500]}")
statut, contenu = lire("https://www.nber.org/papers/w4965")
if statut == 200:
    t = texte_html(contenu.decode("utf-8", "replace"))
    titre = re.search(r"<title>(.*?)</title>", contenu.decode("utf-8", "replace"), re.S)
    i = t.find("We ")
    etudes["nber_w4965"] = {"statut": statut, "titre": titre.group(1).strip() if titre else None, "texte": t[i:i + 2000]}
    dire(f"- NBER w4965 : « {etudes['nber_w4965']['titre']} » · {t[i:i + 1500]}")
else:
    dire(f"- NBER w4965 : HTTP {statut}")
(SORTIE / "etudes.json").write_text(json.dumps(etudes, ensure_ascii=False, indent=1), encoding="utf-8")
dire()
dire("## robots.txt lus")
for h, r in robots.items():
    dire(f"- {h} : HTTP {r['statut']} · délai {r.get('delai')}")
