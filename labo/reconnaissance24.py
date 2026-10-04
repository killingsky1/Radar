"""(Reprise de la partie B, corrigée : les fichiers les plus récents sont choisis par leur date, pas par leur adresse.)
Recherche avant le plan de match (fins de blocage, prix, rachats d'actions, FINRA) : vérifié EN DIRECT, avec les
règles du robot (robots.txt lu d'abord avec notre identification ; 401/403 ou robots.txt illisible = interdit ;
Crawl-delay respecté, sinon au moins 1,5 s entre deux requêtes au même site ; une seule requête à la fois ; rien n'est
contourné ; courriel seulement pour la SEC ; aucun formulaire, aucun compte, aucun courriel envoyé).

A. robots.txt et conditions d'utilisation : FINRA (ventes à découvert), IEX (prix HIST), Nasdaq Trader, data.sec.gov.
   Aucune donnée de FINRA n'est téléchargée (seulement robots.txt et la page des conditions).
B. Prix publiés par la SEC dans les fichiers d'échecs de livraison : quelle part de nos compagnies y a un prix, et
   combien de jours.
C. API officielle data.sec.gov (frames) : combien de compagnies déclarent des rachats d'actions en XBRL.
D. Fins de blocage : TOUS les prospectus 424B4 de juillet à septembre 2026, règle stricte mesurée.
E. Rachats d'actions annoncés : tous les 8-K du 1er et du 2 octobre 2026 (points 2.02, 7.01, 8.01), phrases trouvées.
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
SORTIE = Path("labo/resultats-plan-fgh2")
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



# ---------------------------------------------------------------- B. prix des fichiers d'échecs de livraison (SEC)
dire("# Prix publiés par la SEC (fichiers d'échecs de livraison) — reprise corrigée")
dire(f"Date : {datetime.utcnow():%Y-%m-%d %H:%M} UTC")
PAGE_FTD = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
statut, contenu = lire(PAGE_FTD, 5_000_000)
liens = {}
if statut is not None and contenu:
    for h in re.findall(r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", contenu.decode("utf-8", "replace"), re.I):
        liens[h[1] + h[2]] = urljoin(PAGE_FTD, h[0])
cles = sorted(liens)
dire(f"- page : HTTP {statut} · {len(cles)} fichiers · les 4 plus récents (par date) : {[liens[c].rsplit('/', 1)[1] for c in cles[-4:]]}")
dire(f"- adresses : {[liens[c] for c in cles[-2:]]}")
prix = {}
for c in cles[-2:]:
    statut, contenu = lire(liens[c], 40_000_000)
    if statut != 200:
        dire(f"- {liens[c]} : HTTP {statut}")
        continue
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        brut = z.read(z.namelist()[0]).decode("latin-1")
    lignes = [l.split("|") for l in brut.splitlines()[1:] if l.count("|") >= 5]
    jours = sorted({l[0] for l in lignes})
    for l in lignes:
        try:
            p = float(l[5])
        except ValueError:
            continue
        prix.setdefault(l[2].strip(), {})[l[0]] = p
    dire(f"- {liens[c].rsplit('/', 1)[1]} : {len(lignes)} lignes · {len({l[2] for l in lignes})} symboles · "
         f"{len(jours)} jours ({jours[0] if jours else '?'} → {jours[-1] if jours else '?'}) · en-tête : {brut.splitlines()[0][:90]}")
tous = sorted({j for d in prix.values() for j in d})
auj = json.loads((DONNEES / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
argent = json.loads((DONNEES / "app" / "argent.json").read_text(encoding="utf-8"))
groupes = {
    "listes du jour (hausse et baisse)": sorted({x["symbole"] for x in auj["hausse"] + auj["baisse"]}),
    "section Argent (30 jours)": sorted({l["symbole"] for l in argent["lignes"] if l.get("symbole")}),
}
def pres(s, i, marge=2):
    return any(tous[k] in prix.get(s, {}) for k in range(max(0, i - marge), min(len(tous), i + marge + 1)))
for nom, syms in groupes.items():
    if not tous:
        break
    avec = [s for s in syms if s in prix]
    part = [len(prix[s]) / len(tous) for s in avec]
    debut_fin = [s for s in syms if pres(s, 0) and pres(s, len(tous) - 1)]
    dire(f"- {nom} : {len(avec)}/{len(syms)} symboles ont au moins un prix · en moyenne "
         f"{(sum(part) / len(part) * 100 if part else 0):.0f} % des {len(tous)} jours · prix au début ET à la fin "
         f"(± 2 jours) : {len(debut_fin)}/{len(syms)}")
    if nom.startswith("listes"):
        dire("  " + " · ".join(f"{s} {len(prix.get(s, {}))}/{len(tous)}" for s in syms))
gros = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "XOM", "WMT"]
dire("- 10 très grosses compagnies : " + " · ".join(f"{s} {len(prix.get(s, {}))}/{len(tous)}" for s in gros))
