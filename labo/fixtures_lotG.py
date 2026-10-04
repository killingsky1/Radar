"""Lot G : vrais extraits des fichiers d'échecs de livraison de la SEC pour les tests du robot (mêmes règles d'accès)."""
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



SORTIE = Path("labo/fixtures-lotG")
SORTIE.mkdir(parents=True, exist_ok=True)
resume.clear()
dire("# Lot G : vrais extraits des fichiers d'échecs de livraison de la SEC, pour les tests du robot")
PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
statut, contenu = lire(PAGE, 5_000_000)
(SORTIE / "page_ftd.html.gz").write_bytes(gzip.compress(contenu, 9))
brut = contenu.decode("utf-8", "replace")
liens = {}
for h in re.findall(r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", brut, re.I):
    liens[h[1] + h[2]] = urljoin(PAGE, h[0])
GARDE = {"SPY", "IVV", "VOO", "AAPL", "MSFT", "GME", "PAM", "CRESY", "LESL", "NVDA"}
fichiers = {}
for c in ["202604a", "202607b", "202608a", "202608b", "202609a"]:
    statut, contenu = lire(liens[c], 60_000_000)
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        nom = z.namelist()[0]
        lignes = z.read(nom).decode("latin-1").splitlines()
    fichiers[c] = (nom, lignes)
    dire(f"- {c} : {nom} · {len(lignes)} lignes · Last-Modified gardé dans le manifeste")
# Changements de CUSIP pour un même symbole (regroupements d'actions) et sauts de prix avec le même CUSIP
par_sym = {}
for c, (nom, lignes) in fichiers.items():
    if c == "202604a":
        continue
    for l in lignes[1:]:
        p = l.split("|")
        if len(p) >= 6 and p[0].isdigit():
            par_sym.setdefault(p[2], []).append((p[0], p[1], p[5]))
cusip_change, sauts = [], []
for s, ls in par_sym.items():
    ls.sort()
    cus = [x[1] for x in ls]
    if len(set(cus)) > 1:
        cusip_change.append((s, len(ls), sorted(set(cus))))
    for a, b in zip(ls, ls[1:]):
        try:
            pa, pb = float(a[2]), float(b[2])
        except ValueError:
            continue
        if a[1] == b[1] and pa > 1 and pb > 1 and (pb / pa > 1.8 or pb / pa < 0.55):
            sauts.append((s, a[0], b[0], pa, pb, round(pb / pa, 3)))
dire(f"- symboles avec plusieurs CUSIP (juillet-septembre) : {len(cusip_change)} · ex. {cusip_change[:6]}")
dire(f"- sauts de prix d'un jour à l'autre (×1,8 ou ÷1,8) avec le même CUSIP : {len(sauts)} · ex. {sauts[:8]}")
exemple_cusip = next((s for s, n, cs in sorted(cusip_change, key=lambda x: -x[1]) if n >= 8), None)
exemple_saut = sauts[0][0] if sauts else None
GARDE |= {x for x in (exemple_cusip, exemple_saut) if x}
dire(f"- gardés aussi : changement de CUSIP {exemple_cusip} · saut de prix {exemple_saut}")
manifeste = {}
for c, (nom, lignes) in fichiers.items():
    entete, fin = lignes[0], [l for l in lignes[-3:] if l.startswith("Trailer")]
    premiere_par_jour, garde = {}, []
    for l in lignes[1:]:
        p = l.split("|")
        if len(p) < 6 or not p[0].isdigit():
            continue
        premiere_par_jour.setdefault(p[0], l)
        if p[2] in GARDE:
            garde.append(l)
    # Une vraie ligne de plus par date de règlement : le calendrier des dates reste complet dans l'extrait
    extrait = [entete] + sorted(set(garde) | set(premiere_par_jour.values())) + fin
    (SORTIE / f"cnsfails{c}.txt").write_text("\n".join(extrait) + "\n", encoding="latin-1")
    manifeste[c] = {"fichier": nom, "lignes_completes": len(lignes), "lignes_gardees": len(extrait),
                    "dates_de_reglement": len(premiere_par_jour), "symboles_gardes": sorted(GARDE)}
    dire(f"  - {c} : extrait {len(extrait)} lignes sur {len(lignes)} · {len(premiere_par_jour)} dates de règlement")
(SORTIE / "manifeste.json").write_text(json.dumps(manifeste, indent=1), encoding="utf-8")
