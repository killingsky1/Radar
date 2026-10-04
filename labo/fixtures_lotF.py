"""Lot F : vrais prospectus 424B4 pour les tests du robot (mêmes règles : robots.txt d'abord, courriel seulement pour la SEC, rien n'est contourné)."""
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
SORTIE = Path("labo/resultats-plan-fgh")
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



SORTIE = Path("labo/fixtures-lotF")
SORTIE.mkdir(parents=True, exist_ok=True)
resume.clear()
DEPOTS = [  # (numéro, CIK, pourquoi)
    ("0001193125-26-328422", "1745648", "Apnimed : publiable, deux preuves de la date"),
    ("0001193125-26-403094", "1802369", "ADARx : publiable, date prouvée seulement par la phrase des 25 jours"),
    ("0001193125-26-316503", "1853921", "Scribe : publiable (« will expire 180 days from the date of this prospectus »)"),
    ("0001104659-26-079884", "2004711", "Bending Spoons : publiable, compagnie étrangère"),
    ("0001193125-26-326453", "2127043", "Jersey Mike's : publiable (phrase du programme d'actions réservées)"),
    ("0001213900-26-086641", "2104296", "Ticketplus : publiable, petite entrée en bourse"),
    ("0001193125-26-395670", "2088082", "Electra : publiable"),
    ("0001193125-26-299963", "2120882", "SK hynix : déjà cotée en Corée, doit être ignorée"),
    ("0001104659-26-088733", "1787117", "Reformation : clause de levée anticipée"),
    ("0001104659-26-084293", "2105398", "Csquare : clause de levée anticipée"),
    ("0001213900-26-078747", "2086716", "Standard Nuclear : plusieurs durées"),
    ("0001628280-26-062794", "2124472", "Orion180 : date du prospectus absente"),
    ("0001185185-26-004253", "2094989", "RUI Holdings : aucune durée"),
    ("0001104659-26-110065", "1834376", "InnovAge : offre secondaire (pas une entrée en bourse)"),
    ("0001193125-26-395319", "2111838", "Haymaker V : SPAC"),
    ("0001213900-26-104150", "2075335", "ROZE AI : inscription directe"),
]
dire("# Lot F : vrais prospectus 424B4 pour les tests (en-tête officiel + document 424B4 seulement, compressés)")
manifeste = []
for acc, cik, pourquoi in DEPOTS:
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}.txt"
    statut, contenu = lire(url, 40_000_000)
    if statut != 200:
        dire(f"- {acc} : HTTP {statut} · {url}")
        continue
    txt = contenu.decode("latin-1")
    entete = re.search(r"<SEC-HEADER>.*?</SEC-HEADER>", txt, re.S)
    doc = next((m.group(0) for m in re.finditer(r"<DOCUMENT>\s*<TYPE>([^\n<]+).*?</DOCUMENT>", txt, re.S)
                if m.group(1).strip().upper().startswith("424B4")), None)
    if not entete or not doc:
        dire(f"- {acc} : en-tête ou document 424B4 introuvable")
        continue
    reduit = (entete.group(0) + "\n" + doc + "\n").encode("latin-1")
    (SORTIE / f"{acc}.txt.gz").write_bytes(gzip.compress(reduit, 9))
    manifeste.append({"acc": acc, "cik": cik, "url": url, "pourquoi": pourquoi, "octets_complet": len(contenu),
                      "octets_garde": len(reduit)})
    dire(f"- {acc} · {pourquoi} · complet {len(contenu) / 1e6:.1f} Mo → gardé {len(reduit) / 1e6:.1f} Mo "
         f"({(SORTIE / f'{acc}.txt.gz').stat().st_size / 1e3:.0f} ko compressé)")
(SORTIE / "manifeste.json").write_text(json.dumps(manifeste, ensure_ascii=False, indent=1), encoding="utf-8")
for t in (2, 3):
    statut, contenu = lire(f"https://www.sec.gov/Archives/edgar/full-index/2026/QTR{t}/master.idx", 80_000_000)
    if statut != 200:
        dire(f"- index 2026 T{t} : HTTP {statut}")
        continue
    lignes = contenu.decode("latin-1").splitlines()
    garde = [l for l in lignes[:11]] + [l for l in lignes[11:] if l.count("|") == 4 and l.split("|")[2] == "424B4"]
    (SORTIE / f"master_424b4_2026T{t}.idx").write_text("\n".join(garde) + "\n", encoding="latin-1")
    dire(f"- index officiel 2026 T{t} : {len(lignes)} lignes, gardé l'en-tête et les {len(garde) - 11} lignes 424B4")
statut, contenu = lire("https://www.sec.gov/files/company_tickers_exchange.json", 20_000_000)
if statut == 200:
    s = json.loads(contenu)
    voulus = {int(c) for _, c, _ in DEPOTS}
    s["data"] = [r for r in s["data"] if int(r[0]) in voulus]
    (SORTIE / "symboles.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    dire(f"- symboles officiels (company_tickers_exchange.json) : {len(s['data'])} lignes pour nos {len(voulus)} CIK : "
         + " · ".join(f"{r[2]} {r[1][:20]} ({r[3]})" for r in s["data"]))
