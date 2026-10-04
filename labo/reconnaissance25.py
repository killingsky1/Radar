"""Lot G : vérification en direct des prix officiels de la SEC (fichiers d'échecs de livraison) : définition du prix, dates de mise en ligne, couverture des fonds qui suivent le S&P 500 (mêmes règles d'accès)."""
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



SORTIE = Path("labo/resultats-lotG")
SORTIE.mkdir(parents=True, exist_ok=True)
resume.clear()
dire("# Lot G : prix officiels de la SEC (fichiers d'échecs de livraison) — définition, dates de mise en ligne, couverture")
dire(f"Date : {datetime.utcnow():%Y-%m-%d %H:%M} UTC")
PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
statut, contenu = lire(PAGE, 5_000_000)
brut = contenu.decode("utf-8", "replace")
(SORTIE / "page_ftd.html").write_bytes(contenu)
t = texte_html(brut)
dire(f"## Page officielle : HTTP {statut} · {len(t)} caractères")
for p in phrases_cles(t, [r"price", r"previous", r"closing", r"settlement date", r"twice", r"monthly", r"posted",
                          r"first half", r"second half", r"fails to deliver", r"not necessarily", r"ETF", r"penny"], 40):
    dire(f"  > {p[:900]}")
liens = {}
for h in re.findall(r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", brut, re.I):
    liens[h[1] + h[2]] = urljoin(PAGE, h[0])
autres = sorted({urljoin(PAGE, h) for h in re.findall(r"""href=["']([^"']+\.(?:pdf|txt|htm|html))["']""", brut, re.I)
                 if re.search(r"fail|ftd|readme|descr|notes|layout", h, re.I)})
dire(f"- documents liés (description) : {autres[:10]}")
cles = sorted(liens)
dire(f"- {len(cles)} fichiers ; les 8 plus récents : {[c for c in cles[-8:]]}")
# Dates de mise en ligne : l'en-tête « Last-Modified » de chaque fichier (requête HEAD : rien n'est téléchargé)
for c in cles[-8:]:
    u = liens[c]
    if not permis(u):
        continue
    h = urlparse(u).hostname
    reste = max(1.5, robots[h]["delai"] or 0) - (time.monotonic() - dernier.get(h, 0))
    if reste > 0:
        time.sleep(reste)
    r = requests.head(u, headers={"User-Agent": ua(h)}, timeout=60, allow_redirects=True)
    dernier[h] = time.monotonic()
    dire(f"  - {c} : mis en ligne (Last-Modified) {r.headers.get('Last-Modified')} · {r.headers.get('Content-Length')} octets")
# Couverture : les 4 fichiers les plus récents
prix, jours_regl = {}, set()
for c in cles[-4:]:
    statut, contenu = lire(liens[c], 60_000_000)
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        nom = z.namelist()[0]
        brut_f = z.read(nom).decode("latin-1")
    lignes = [l.split("|") for l in brut_f.splitlines()[1:] if l.count("|") >= 5]
    for l in lignes:
        jours_regl.add(l[0])
        try:
            p = float(l[5])
        except ValueError:
            continue
        prix.setdefault(l[2].strip(), {})[l[0]] = p
    dire(f"- {c} ({nom}) : {len(lignes)} lignes · dernière ligne du fichier : {brut_f.splitlines()[-1][:120]!r}")
jours = sorted(jours_regl)
dire(f"- dates de règlement : {len(jours)} ({jours[0]} → {jours[-1]}) : {', '.join(jours)}")
from datetime import date as D
def d(s): return D(int(s[:4]), int(s[4:6]), int(s[6:8]))
manquants = [x for x in (d(jours[0]) + timedelta(days=i) for i in range((d(jours[-1]) - d(jours[0])).days + 1))
             if x.weekday() < 5 and x.strftime("%Y%m%d") not in jours_regl]
dire(f"- jours de semaine SANS date de règlement : {[str(x) for x in manquants]}")
for s in ("SPY", "IVV", "VOO", "VTI", "QQQ", "DIA", "IWM"):
    dire(f"  - {s} : prix {len(prix.get(s, {}))}/{len(jours)} jours")
# Paires (départ S, arrivée ≥ S + 30 jours, au plus 3 jours plus tard) : SPY, ou IVV, ou VOO, aux MÊMES dates
def paire(sym, s, cible):
    if s not in prix.get(sym, {}):
        return False
    return any(x in prix.get(sym, {}) for x in jours if cible <= x <= (d(cible) + timedelta(days=3)).strftime("%Y%m%d"))
for horizon in (7, 30):
    total = ok_spy = ok_un = 0
    for s in jours:
        cible = (d(s) + timedelta(days=horizon)).strftime("%Y%m%d")
        if cible > jours[-1]:
            continue
        total += 1
        ok_spy += paire("SPY", s, cible)
        ok_un += any(paire(x, s, cible) for x in ("SPY", "IVV", "VOO"))
    dire(f"- horizon {horizon} jours : {total} départs possibles · SPY aux 2 dates : {ok_spy} · SPY, IVV ou VOO : {ok_un}")
# Un exemple brut, pour la définition : les lignes de SPY
dire("- lignes brutes SPY (date de règlement | prix) : " + " · ".join(f"{k}|{v}" for k, v in sorted(prix.get("SPY", {}).items())[:12]))
