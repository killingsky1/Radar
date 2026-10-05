"""Reconnaissance 28 : les chiffres exacts par taille et la valeur en bourse de nos compagnies (sans rien deviner).

A. Lakonishok et Lee (2001) : titres des tableaux et lignes « Small / Medium / Large / All » avec leurs chiffres ;
   Cohen, Malloy et Pomorski (2012) : les lignes de leurs résultats par taille (grandes et petites compagnies).
B. Seuils de taille du NYSE (« ME Breakpoints », bibliothèque de données de Kenneth French, Dartmouth) : le dernier mois,
   30e et 70e centiles (petites = 3 premiers déciles du NYSE, grandes = 3 derniers, comme Lakonishok et Lee).
C. Valeur en bourse des compagnies des listes et de celles où un dirigeant a acheté depuis 30 jours : actions en
   circulation déclarées (dei:EntityCommonStockSharesOutstanding, fichiers « frames » de la SEC) × dernier prix des
   fichiers d'échecs de livraison de la SEC ; comparée au flottant public déclaré (dei:EntityPublicFloat).
Mêmes règles d'accès que le robot : robots.txt lu d'abord, 1,5 s entre deux requêtes, identification (courriel à la SEC).
"""
import csv
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.robotparser
import zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/recon28")
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

DONNEES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("principal/data")


def texte_pdf(url):
    statut, b = lire(url, 40_000_000)
    if statut != 200 or not b or b[:4] != b"%PDF":
        dire(f"- {url} : {statut}")
        return []
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(b)
        f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True).stdout.decode("utf-8", "replace").split("\f")


# ---------- A. Les tableaux par taille ----------
dire("# Reconnaissance 28\n\n## A. Lakonishok et Lee (2001) : tableaux par taille")
pages = texte_pdf("https://www.lsvasset.com/pdf/research-papers/Insider-Trades-Informative.pdf")
for n, p in enumerate(pages, 1):
    lignes = p.splitlines()
    for k, l in enumerate(lignes):
        s = " ".join(l.split())
        if re.match(r"^Table \d+", s):
            dire(f"- p. {n} TITRE : {s} {' '.join(' '.join(x.split()) for x in lignes[k + 1:k + 3])[:300]}")
        elif re.match(r"^(Small|Medium|Large|All|Total|Purchase|Sale|Quintile|Q[1-5]|1|5|Spread|Difference|High|Low)\b", s) \
                and len(re.findall(r"[−-]?\d+\.\d+", s)) >= 2:
            dire(f"- p. {n} : {s[:220]}")
dire("\n## A bis. Cohen, Malloy et Pomorski (2012) : résultats par taille")
pages = texte_pdf("https://www.nber.org/system/files/working_papers/w16454/w16454.pdf")
for n, p in enumerate(pages, 1):
    plat = " ".join(p.split())
    for m in re.finditer(r"(small(er)? (firms|stocks)|large(r)? (firms|stocks)|size (quintile|tercile|decile)|market cap)", plat, re.I):
        a, b = max(0, m.start() - 350), min(len(plat), m.end() + 350)
        if re.search(r"\d", plat[a:b]):
            dire(f"- p. {n} : « {plat[a:b]} »")
    for l in p.splitlines():
        s = " ".join(l.split())
        if re.match(r"^(Small|Large|Big|Micro|Size)\b", s) and len(re.findall(r"[−-]?\d+\.\d+", s)) >= 2:
            dire(f"- p. {n} LIGNE : {s[:220]}")

# ---------- B. Seuils du NYSE (Kenneth French) ----------
dire("\n## B. Seuils de taille du NYSE")
URL_ME = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/ME_Breakpoints_CSV.zip"
statut, b = lire(URL_ME, 20_000_000)
seuils = None
if statut == 200:
    z = zipfile.ZipFile(io.BytesIO(b))
    brut = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    rangs = [l for l in brut if re.match(r"^\s*\d{6}\s*,", l)]
    dire(f"- {URL_ME} : 200 · {len(rangs)} mois · en-tête : {' | '.join(brut[:4])[:400]}")
    dernier = [x.strip() for x in rangs[-1].split(",")]
    dire(f"- dernier mois : {dernier[0]} · nombre de compagnies du NYSE : {dernier[1]} · centiles 5 à 100 (M$) : {dernier[2:]}")
    seuils = {"mois": dernier[0], "p30": float(dernier[2 + 5]), "p70": float(dernier[2 + 13])}
    dire(f"- petites (sous le 30e centile) : moins de {seuils['p30']:,.1f} M$ · grandes (au-dessus du 70e) : plus de "
         f"{seuils['p70']:,.1f} M$")
else:
    dire(f"- {URL_ME} : {statut}")

# ---------- C. Valeur en bourse ----------
dire("\n## C. Valeur en bourse des compagnies (actions en circulation × dernier prix de la SEC)")
actions, flottant = {}, {}
for per in ("CY2025Q3I", "CY2025Q4I", "CY2026Q1I", "CY2026Q2I", "CY2026Q3I"):
    statut, b = lire(f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{per}.json")
    lignes = json.loads(b).get("data", []) if statut == 200 else []
    for r in lignes:
        if r["cik"] not in actions or r["end"] > actions[r["cik"]]["end"]:
            actions[r["cik"]] = r
    dire(f"- actions en circulation {per} : {statut} · {len(lignes)} compagnies")
for per in ("CY2024Q2I", "CY2024Q3I", "CY2024Q4I", "CY2025Q1I", "CY2025Q2I", "CY2025Q3I", "CY2025Q4I", "CY2026Q1I"):
    statut, b = lire(f"https://data.sec.gov/api/xbrl/frames/dei/EntityPublicFloat/USD/{per}.json")
    for r in (json.loads(b).get("data", []) if statut == 200 else []):
        if r["cik"] not in flottant or r["end"] > flottant[r["cik"]]["end"]:
            flottant[r["cik"]] = r
PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
statut, b = lire(PAGE)
liens = sorted({(m.group(2) + m.group(3).lower(), urljoin(PAGE, m.group(1)))
                for m in re.finditer(r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", (b or b"").decode("utf-8", "replace"), re.I)})
prix = {}
for cle, url in liens[-2:]:
    statut, b = lire(url, 100_000_000)
    z = zipfile.ZipFile(io.BytesIO(b))
    for l in z.read(z.namelist()[0]).decode("latin-1").splitlines()[1:]:
        p = l.split("|")
        if len(p) == 6 and re.fullmatch(r"\d{8}", p[0]) and re.fullmatch(r"\d+(\.\d+)?", p[5].strip()):
            if p[2] not in prix or p[0] > prix[p[2]][0]:
                prix[p[2]] = (p[0], float(p[5]))
    dire(f"- fichier d'échecs de livraison {cle} : lu · {len(prix)} symboles avec un prix jusqu'ici")
auj = json.loads((DONNEES / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
emet = json.loads((DONNEES / "sec" / "emetteurs.json").read_text(encoding="utf-8"))
evs = [json.loads(l) for f in sorted((DONNEES / "evenements").glob("*.jsonl"))[-2:]
       for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
recents = {e["tickers"][0] for e in evs if e["source"] == "sec_form4" and e.get("direction") == 1 and e.get("tickers")
           and e["occurred_on"] >= (date.today() - timedelta(days=30)).isoformat()}
listes = {x["symbole"] for s in ("hausse", "baisse") for x in auj[s]}
groupes = Counter()
for s in sorted(listes | recents):
    cik = (emet.get(s) or {}).get("cik")
    a = actions.get(int(cik)) if cik else None
    pr = prix.get(s)
    fl = flottant.get(int(cik)) if cik else None
    valeur = a["val"] * pr[1] if a and pr else None
    taille = None
    if valeur is not None and seuils:
        taille = "petite" if valeur < seuils["p30"] * 1e6 else ("grande" if valeur > seuils["p70"] * 1e6 else "moyenne")
    groupes[(s in listes, taille)] += 1
    t_actions = f"{a['val']:,.0f} au {a['end']}" if a else "aucune"
    t_prix = f"{pr[1]} $ le {pr[0]}" if pr else "aucun"
    t_valeur = f"{valeur / 1e6:,.0f} M$" if valeur is not None else "inconnue"
    t_flottant = f"{fl['val'] / 1e6:,.0f} M$ au {fl['end']}" if fl else "aucun"
    marque = " (liste)" if s in listes else ""
    dire(f"- {s}{marque} : actions {t_actions} · prix {t_prix} · valeur {t_valeur} · flottant {t_flottant} · taille : {taille}")
dire(f"- Résumé (dans les listes ?, taille) : {dict(groupes)}")
