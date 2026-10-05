"""Reconnaissance 27 : la recherche avant le plan de match sur la décision des robots (avec de vraies données).

A. Études (texte lu avec pdftotext ; seuls de courts passages autour des mots-clés sont gardés, avec la page) :
   Cohen, Malloy et Pomorski (2012), achats routiniers ou inhabituels ; Lakonishok et Lee (2001), taille des compagnies.
B. Jeux de données officiels de la SEC sur les formulaires 3, 4 et 5 (« Insider Transactions Data Sets ») : la page, les
   trimestres offerts, la taille des fichiers, les colonnes.
C. Mesure : chaque achat ou vente de dirigeant qui compte dans les listes d'aujourd'hui ; le numéro SEC de l'initié est lu
   dans le formulaire 4 lui-même ; son historique 2023-2025 vient des jeux de données. Routinier (même mois de l'année
   civile, 3 ans de suite), inhabituel (des transactions chacune des 3 années, sans mois commun) ou sans historique
   suffisant ; règle par initié (toutes compagnies) et par initié et compagnie ; achats et ventes en bourse (P, S).
D. Taille : flottant public déclaré par la compagnie (dei:EntityPublicFloat, fichiers « frames » de la SEC) des
   compagnies des listes et de celles où un dirigeant a acheté depuis 30 jours.
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
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/recon27")
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
csv.field_size_limit(10_000_000)


def passages(texte_pages, motif, n=6, rayon=450):
    """Les n premiers passages (avec la page) où le motif apparaît."""
    sortie = []
    for num, page in enumerate(texte_pages, 1):
        for m in re.finditer(motif, page, re.I):
            a, b = max(0, m.start() - rayon), min(len(page), m.end() + rayon)
            sortie.append(f"p. {num} : « {' '.join(page[a:b].split())} »")
            if len(sortie) >= n:
                return sortie
    return sortie


# ---------- A. Études ----------
ETUDES = {
    "Cohen, Malloy et Pomorski (2012), Decoding Inside Information": (
        ["https://www.nber.org/system/files/working_papers/w16454/w16454.pdf",
         "https://dash.harvard.edu/bitstream/handle/1/33785679/cohen,malloy,pomorski_decoding-inside-information.pdf"
         "?sequence=1&isAllowed=y"],
        [r"routine trader", r"opportunistic trader", r"same calendar month", r"three (consecutive|preceding) years",
         r"basis points", r"(small|smaller) (firms|stocks)", r"\bsize\b", r"value[- ]weight", r"equal[- ]weight",
         r"(open[- ]market|transaction code)", r"(percent|%) of (all )?(insiders|trades)"]),
    "Lakonishok et Lee (2001), Are Insider Trades Informative?": (
        ["https://www.lsvasset.com/pdf/research-papers/Insider-Trades-Informative.pdf"],
        [r"small firms", r"large firms", r"market capitalization", r"\bsize\b", r"net purchase ratio",
         r"(12|twelve) months"]),
}
dire("# Reconnaissance 27\n\n## A. Études")
for titre, (urls, motifs) in ETUDES.items():
    dire(f"\n### {titre}")
    for url in urls:
        statut, b = lire(url, 40_000_000)
        dire(f"- {url} : {statut} · {len(b or b'')} octets")
        if statut == 200 and b and b[:4] == b"%PDF":
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(b)
                f.flush()
                txt = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True).stdout.decode("utf-8", "replace")
            pages = txt.split("\f")
            dire(f"- texte lu : {len(pages)} pages")
            for motif in motifs:
                trouves = passages(pages, motif)
                dire(f"\n**{motif}** ({len(trouves)} passage(s) montrés)")
                for t in trouves:
                    dire(f"- {t}")
            # Lignes de tableaux qui parlent des routiniers / inhabituels ou des tailles (chiffres)
            lignes_tab = [f"p. {n} : {' '.join(l.split())}" for n, p in enumerate(pages, 1) for l in p.splitlines()
                          if re.search(r"(Opportunistic|Routine|Small|Medium|Large|Size)", l)
                          and len(re.findall(r"-?\d+\.\d+", l)) >= 2][:60]
            dire(f"\n**Lignes de tableaux avec des chiffres** ({len(lignes_tab)})")
            for l in lignes_tab:
                dire(f"- {l}")
            break

# ---------- B. Jeux de données de la SEC (formulaires 3, 4, 5) ----------
dire("\n## B. Jeux de données de la SEC sur les formulaires 3, 4 et 5")
PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
statut, b = lire(PAGE)
page = (b or b"").decode("utf-8", "replace")
liens = sorted({urljoin(PAGE, h) for h in re.findall(r'href="([^"]+form345\.zip)"', page, re.I)})
dire(f"- page {PAGE} : {statut} · {len(liens)} fichiers trimestriels · premier {liens[0] if liens else None} · dernier "
     f"{liens[-1] if liens else None}")
VOULUS = [f"{a}q{q}" for a in (2023, 2024, 2025) for q in (1, 2, 3, 4)]
choisis = {t: next((l for l in liens if l.lower().rsplit("/", 1)[-1].startswith(t)), None) for t in VOULUS}
dire(f"- trimestres 2023-2025 trouvés : {sum(1 for v in choisis.values() if v)}/12")
par_initie, par_paire, achats_par_annee = defaultdict(lambda: defaultdict(set)), defaultdict(lambda: defaultdict(set)), Counter()
achats_initie = defaultdict(lambda: defaultdict(set))  # seulement les achats (P)
MOIS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def jour_de(s):
    s = (s or "").strip()
    m = re.fullmatch(r"(\d{2})-([A-Z]{3})-(\d{4})", s.upper())
    if m:
        return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def table(z, nom):
    vrai = next(n for n in z.namelist() if n.upper().endswith(nom))
    with z.open(vrai) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t")


premier = True
for t, url in choisis.items():
    if not url:
        continue
    statut, b = lire(url, 600_000_000)
    if statut != 200:
        dire(f"- {t} : {statut}")
        continue
    z = zipfile.ZipFile(io.BytesIO(b))
    if premier:
        dire(f"- contenu de {t} : " + ", ".join(f"{i.filename} ({i.file_size:,} o)" for i in z.infolist()))
        for nom in ("SUBMISSION.TSV", "REPORTINGOWNER.TSV", "NONDERIV_TRANS.TSV"):
            with z.open(next(n for n in z.namelist() if n.upper().endswith(nom))) as f:
                dire(f"- colonnes de {nom} : {f.readline().decode('utf-8', 'replace').strip()}")
        premier = False
    emetteur = {r["ACCESSION_NUMBER"]: r.get("ISSUERCIK") for r in table(z, "SUBMISSION.TSV")}
    proprios = defaultdict(list)
    for r in table(z, "REPORTINGOWNER.TSV"):
        proprios[r["ACCESSION_NUMBER"]].append(r.get("RPTOWNERCIK"))
    n = 0
    for r in table(z, "NONDERIV_TRANS.TSV"):
        code = (r.get("TRANS_CODE") or "").strip()
        if code not in ("P", "S"):
            continue
        j = jour_de(r.get("TRANS_DATE"))
        if not j:
            continue
        n += 1
        acc = r["ACCESSION_NUMBER"]
        for o in proprios.get(acc, []):
            if not (o or "").strip().isdigit():
                continue
            par_initie[str(int(o))][j.year].add(j.month)
            par_paire[(str(int(o)), str(int(emetteur.get(acc) or 0)))][j.year].add(j.month)
            if code == "P":
                achats_initie[str(int(o))][j.year].add(j.month)
        if code == "P":
            achats_par_annee[j.year] += 1
    dire(f"- {t} : {len(b):,} octets · {n:,} transactions en bourse (P ou S)")
    del b, z
dire(f"- initiés avec des transactions en bourse : {len(par_initie):,} · paires initié-compagnie : {len(par_paire):,} · "
     f"achats par année : {dict(sorted(achats_par_annee.items()))}")


def classe(hist, annees=(2023, 2024, 2025)):
    if not all(hist.get(a) for a in annees):
        return "sans historique"
    commun = set.intersection(*(hist[a] for a in annees))
    return "routinier" if commun else "inhabituel"


# ---------- C. Les achats et ventes de dirigeants qui comptent aujourd'hui ----------
dire("\n## C. Achats et ventes de dirigeants dans les listes d'aujourd'hui")
auj = json.loads((DONNEES / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
evs = {}
for f in sorted((DONNEES / "evenements").glob("*.jsonl"))[-4:]:
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.strip():
            e = json.loads(l)
            evs[e["id"]] = e
resume_c = Counter()
for sens in ("hausse", "baisse"):
    for x in auj[sens]:
        for g in x.get("groupes", []):
            for i in g.get("infos", []):
                if i.get("regle") not in ("achat_dirigeant", "vente_dirigeant"):
                    continue
                e = evs.get(i["id"])
                if not e:
                    dire(f"- {x['symbole']} : info {i['id']} introuvable dans les événements")
                    continue
                acc = e["official_id"].split(":")[0]
                cik_em = int(e["data"]["cik_emetteur"])
                statut, b = lire(f"https://www.sec.gov/Archives/edgar/data/{cik_em}/{acc.replace('-', '')}/{acc}.txt")
                proprios = sorted(set(re.findall(r"<rptOwnerCik>\s*0*(\d+)\s*</rptOwnerCik>", (b or b"").decode("utf-8", "replace"))))
                for o in proprios:
                    c_i, c_p = classe(par_initie.get(o, {})), classe(par_paire.get((o, str(cik_em)), {}))
                    c_a = classe(achats_initie.get(o, {}))
                    resume_c[(i["regle"], c_i)] += 1
                    mois = {a: sorted(par_initie.get(o, {}).get(a, [])) for a in (2023, 2024, 2025)}
                    dire(f"- {sens} {x['symbole']} ({x['note10']}/10) · {i['regle']} · {e['entities'][0]} (CIK {o}) · "
                         f"{e['occurred_on']} · points {i.get('points')} · compte {i.get('compte')} · par initié : {c_i} · "
                         f"par initié et compagnie : {c_p} · achats seulement : {c_a} · mois 2023-2025 : {mois}")
dire(f"- Résumé (règle, classe par initié) : {dict(resume_c)}")

# ---------- D. Taille : flottant public déclaré (dei:EntityPublicFloat) ----------
dire("\n## D. Taille des compagnies (flottant public déclaré dans le rapport annuel)")
flottant = {}
for per in ("CY2024Q2I", "CY2024Q3I", "CY2024Q4I", "CY2025Q1I", "CY2025Q2I", "CY2025Q3I", "CY2025Q4I", "CY2026Q1I"):
    statut, b = lire(f"https://data.sec.gov/api/xbrl/frames/dei/EntityPublicFloat/USD/{per}.json")
    lignes = json.loads(b).get("data", []) if statut == 200 else []
    for r in lignes:
        if r["cik"] not in flottant or r["end"] > flottant[r["cik"]]["end"]:
            flottant[r["cik"]] = r
    dire(f"- {per} : {statut} · {len(lignes)} compagnies")
emet = json.loads((DONNEES / "sec" / "emetteurs.json").read_text(encoding="utf-8"))
recents = {s for e in evs.values() if e["source"] == "sec_form4" and e.get("direction") == 1
           and e["occurred_on"] >= (date.today() - timedelta(days=30)).isoformat() for s in e.get("tickers", [])[:1]}
listes = {x["symbole"] for s in ("hausse", "baisse") for x in auj[s]}
CLASSES = [(75e6, "moins de 75 M$"), (250e6, "75 à 250 M$"), (700e6, "250 à 700 M$"), (2e9, "700 M$ à 2 G$"),
           (10e9, "2 à 10 G$"), (float("inf"), "10 G$ et plus")]
for nom, groupe in (("listes", listes), ("achats de dirigeants depuis 30 jours", recents)):
    compte, sans = Counter(), []
    for s in sorted(groupe):
        cik = (emet.get(s) or {}).get("cik")
        r = flottant.get(int(cik)) if cik else None
        if not r:
            sans.append(s)
            continue
        compte[next(n for lim, n in CLASSES if r["val"] < lim)] += 1
        if nom == "listes":
            dire(f"- {s} : flottant {r['val']:,} $ au {r['end']}")
    dire(f"- {nom} : {len(groupe)} compagnies · par flottant : {dict(compte)} · sans flottant déclaré : {len(sans)} {sans[:20]}")
