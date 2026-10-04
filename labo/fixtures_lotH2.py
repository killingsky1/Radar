"""Lot H, vérification de nouveauté : vraies fiches officielles de la SEC (data.sec.gov/submissions) et vrais 8-K
précédents (90 jours) de 4 compagnies, pour les tests du robot. Mêmes règles d'accès (robots.txt d'abord, 1,5 s)."""
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
SORTIE = Path("labo/fixtures-lotH2")
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





SORTIE = Path("labo/fixtures-lotH2")
SORTIE.mkdir(parents=True, exist_ok=True)
resume.clear()
dire("# Lot H : fiches officielles et 8-K précédents (90 jours), pour la vérification de nouveauté")
ARCH = "https://www.sec.gov/Archives"
POINTS = {"2.02", "7.01", "8.01"}
CAS = {"acn": (1467373, "2026-10-01", None), "nbhc": (1475841, "2026-10-01", None), "aout": (1808997, "2026-10-01", None),
       "cour": (1651562, "2026-07-29", "0001651562-26-000059")}
pages = {}


def garder(cle, url, contenu):
    nom = f"{cle}.gz"
    (SORTIE / nom).write_bytes(gzip.compress(contenu, 9))
    pages[url] = nom


def lire_8k(cle, cik, acc):
    dossier = f"{ARCH}/edgar/data/{cik}/{acc.replace('-', '')}"
    s2, index = lire(f"{dossier}/{acc}-index.htm")
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
    return s2, [s for _, s in docs[:4]]


for nom, (cik, jour, acc_courant) in CAS.items():
    url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    statut, contenu = lire(url, 30_000_000)
    f = json.loads(contenu)
    r = f["filings"]["recent"]
    # Seulement les 4 champs lus par le robot, et les 200 derniers dépôts (le fichier complet pèse trop pour les tests)
    reduit = {"cik": f.get("cik"), "name": f.get("name"), "filings": {"recent": {
        k: r[k][:200] for k in ("accessionNumber", "filingDate", "form", "items")}}}
    garder(f"{nom}_fiche", url, json.dumps(reduit).encode())
    j = date.fromisoformat(jour)
    precedents = [(a, d, it) for a, d, fo, it in zip(r["accessionNumber"], r["filingDate"], r["form"], r["items"])
                  if fo == "8-K" and 1 <= (j - date.fromisoformat(d)).days <= 90
                  and {x.strip() for x in (it or "").split(",")} & POINTS]
    dire(f"- {nom} (CIK {cik}) : fiche HTTP {statut}, {len(r['form'])} dépôts récents · 8-K des 90 jours avant le {jour} "
         f"(points 2.02/7.01/8.01) : {[(a, d, it) for a, d, it in precedents]}")
    for i, (a, d, it) in enumerate(precedents):
        s, sortes = lire_8k(f"{nom}_avant{i}", cik, a)
        dire(f"  - {a} ({d}, {it}) : index {s}, documents {sortes}")
    if acc_courant:
        dossier = f"{ARCH}/edgar/data/{cik}/{acc_courant.replace('-', '')}"
        s1, entete = lire(f"{dossier}/{acc_courant}-index-headers.html")
        garder(f"{nom}_entete", f"{dossier}/{acc_courant}-index-headers.html", entete)
        s, sortes = lire_8k(nom, cik, acc_courant)
        dire(f"  - dépôt du {jour} ({acc_courant}) : en-tête {s1}, index {s}, documents {sortes}")
(SORTIE / "pages.json").write_text(json.dumps(pages, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
dire()
dire("## robots.txt lus")
for h, x in robots.items():
    dire(f"- {h} : HTTP {x['statut']} · délai {x.get('delai')}")
