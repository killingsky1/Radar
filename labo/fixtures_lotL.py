"""Lot L : vraies données officielles RÉDUITES pour les tests du robot, et attendus refaits ici (code du labo, sur les
fichiers COMPLETS).

1. Jeux de données de la SEC sur les formulaires 3, 4 et 5, 2023 à 2025 (12 trimestres) : seules les lignes des paires
   initié-compagnie choisies sont gardées (mêmes fichiers, mêmes colonnes). Paires : Milton C. Ault III et Ault & Company
   chez GPUS, Daniel L. Florness chez FUL, Ryan Cohen chez GME, puis 3 routinières, 3 inhabituelles et 3 sans
   historique choisies ici (initiés avec 100 transactions en bourse ou moins, pour des extraits petits), et une paire où
   le même nom a 2 numéros CIK.
   attendus_inities.json : la classe de chaque paire (par CIK et par nom), refaite ici sur les fichiers complets.
2. Les 2 derniers fichiers d'échecs de livraison de la SEC (prix), réduits aux symboles choisis.
3. Les fichiers « frames » dei:EntityCommonStockSharesOutstanding des 5 derniers trimestres, réduits aux mêmes compagnies.
4. Les seuils de taille du NYSE (Kenneth French), fichier complet.
5. Les fiches de la SEC (submissions) des compagnies choisies, réduites à la liste des formulaires déposés.
attendus_taille.json : actions, prix, valeur en bourse et taille de chaque compagnie, refaits ici sur les fichiers complets.
"""
import io
import json
import re
import sys
import time
import urllib.robotparser
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/fixtures-lotL")
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

MOIS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
SYMBOLES = ["GPUS", "FUL", "GME", "FLNA", "PRHI", "XENE", "LESL", "CRBG", "ORCL", "AAPL", "PAM", "CRESY", "MNSO", "NYAX",
            "TKLF", "QTEX", "HELP", "SAMG", "CPHC"]
AUJOURDHUI = datetime.now(timezone.utc).date()
ANNEES = (2023, 2024, 2025)
MAX_TRANSACTIONS = 100
ACTIONS_MAX_JOURS, PRIX_MAX_JOURS = 200, 60
AMERICAINS, ETRANGERS = {"10-K", "10-Q", "10-KT", "10-QT"}, {"20-F", "40-F", "6-K"}


def nom_normal(n):
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", (n or "").upper()).split())


def jour_de(s):
    m = re.fullmatch(r"(\d{2})-([A-Z]{3})-(\d{4})", (s or "").strip().upper())
    return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1))) if m else None


def tsv(z, fin):
    vrai = next(n for n in z.namelist() if n.upper().endswith(fin))
    texte = z.read(vrai).decode("utf-8", "replace").split("\n")
    entete = texte[0].rstrip("\r")
    return vrai, entete, [l.rstrip("\r") for l in texte[1:] if l.strip()]


def colonnes(entete):
    return {c: i for i, c in enumerate(entete.split("\t"))}


def ok(statut, b, quoi):
    if statut != 200 or not b:
        dire(f"- ARRÊT : {quoi} : {statut}")
        sys.exit(1)
    return b


dire(f"# Extraits du lot L ({AUJOURDHUI})\n")
(SORTIE / "capture.json").write_text(json.dumps({"date": AUJOURDHUI.isoformat()}) + "\n", encoding="utf-8")

# ---------- 0. Symboles → CIK (liste officielle de la SEC) ----------
liste = json.loads(ok(*lire("https://www.sec.gov/files/company_tickers.json"), "company_tickers.json"))
CIKS = {}
for x in liste.values():
    if x["ticker"] in SYMBOLES and x["ticker"] not in CIKS:
        CIKS[x["ticker"]] = int(x["cik_str"])
dire(f"- symboles → CIK : {CIKS} · absents : {sorted(set(SYMBOLES) - set(CIKS))}")

# ---------- 1. Jeux de données des formulaires 3, 4, 5 ----------
PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
page = ok(*lire(PAGE), "page des jeux de données").decode("utf-8", "replace")
liens = {}
for h in re.findall(r'href="([^"]+form345\.zip)"', page, re.I):
    m = re.match(r"(\d{4})q([1-4])_form345\.zip", h.rsplit("/", 1)[-1], re.I)
    if m:
        liens[f"{m.group(1)}q{m.group(2)}"] = urljoin(PAGE, h)
dire(f"- page des jeux de données : {len(liens)} fichiers trimestriels · du {min(liens)} au {max(liens)}")
trimestres = [f"{a}q{q}" for a in ANNEES for q in (1, 2, 3, 4)]
bruts = {}
par_cik = defaultdict(lambda: defaultdict(set))  # (proprio, émetteur) -> année -> mois
par_nom = defaultdict(lambda: defaultdict(set))  # (nom normalisé, émetteur) -> année -> mois
noms_de = defaultdict(set)  # (proprio, émetteur) -> noms tels quels
nb_transactions = defaultdict(int)  # proprio -> transactions P ou S
for t in trimestres:
    b = ok(*lire(liens[t], 300_000_000), t)
    z = zipfile.ZipFile(io.BytesIO(b))
    fichiers = {fin: tsv(z, fin) for fin in ("SUBMISSION.TSV", "REPORTINGOWNER.TSV", "NONDERIV_TRANS.TSV")}
    bruts[t] = fichiers
    (_, sh, sub), (_, oh, own), (_, th, tr) = (fichiers[f] for f in ("SUBMISSION.TSV", "REPORTINGOWNER.TSV",
                                                                   "NONDERIV_TRANS.TSV"))
    cs, co, ct = colonnes(sh), colonnes(oh), colonnes(th)
    emetteur = {}
    for l in sub:
        p = l.split("\t")
        if len(p) > cs["ISSUERCIK"] and p[cs["ISSUERCIK"]].strip().isdigit():
            emetteur[p[cs["ACCESSION_NUMBER"]]] = str(int(p[cs["ISSUERCIK"]]))
    proprios = defaultdict(list)
    for l in own:
        p = l.split("\t")
        if len(p) > co["RPTOWNERNAME"] and p[co["RPTOWNERCIK"]].strip().isdigit():
            proprios[p[co["ACCESSION_NUMBER"]]].append((str(int(p[co["RPTOWNERCIK"]])), p[co["RPTOWNERNAME"]]))
    n = 0
    for l in tr:
        p = l.split("\t")
        if len(p) <= ct["TRANS_CODE"] or p[ct["TRANS_CODE"]].strip() not in ("P", "S"):
            continue
        j, acc = jour_de(p[ct["TRANS_DATE"]]), p[ct["ACCESSION_NUMBER"]]
        if not j or j.year not in ANNEES or acc not in emetteur:
            continue
        n += 1
        for o, nom in proprios.get(acc, []):
            par_cik[(o, emetteur[acc])][j.year].add(j.month)
            par_nom[(nom_normal(nom), emetteur[acc])][j.year].add(j.month)
            noms_de[(o, emetteur[acc])].add(nom)
            nb_transactions[o] += 1
    dire(f"- {t} : {len(b):,} octets · {n:,} transactions en bourse (P ou S) de {min(ANNEES)} à {max(ANNEES)}")


def classe(h):
    if not all(h.get(a) for a in ANNEES):
        return "sans historique", []
    commun = sorted(set.intersection(*(h[a] for a in ANNEES)))
    return ("routinier" if commun else "inhabituel"), commun


compte = defaultdict(int)
for h in par_cik.values():
    compte[classe(h)[0]] += 1
compte_noms = defaultdict(int)
for h in par_nom.values():
    compte_noms[classe(h)[0]] += 1
dire(f"- paires initié-compagnie (par CIK) : {len(par_cik):,} · {dict(compte)}")
dire(f"- paires nom-compagnie : {len(par_nom):,} · {dict(compte_noms)}")

# Les paires gardées
gardees = set()
for (o, e) in par_cik:
    if o in ("1212502", "1734770") and e == str(CIKS.get("GPUS")) or o == "1017427" and e == str(CIKS.get("FUL")) or \
            e == str(CIKS.get("GME")) and any("COHEN RYAN" in nom_normal(n) for n in noms_de[(o, e)]):
        gardees.add((o, e))
petites = defaultdict(list)
for cle in sorted(par_cik):
    if nb_transactions[cle[0]] <= MAX_TRANSACTIONS:
        petites[classe(par_cik[cle])[0]].append(cle)
for c in ("routinier", "inhabituel", "sans historique"):
    gardees |= set(petites[c][:: max(1, len(petites[c]) // 3)][:3])
# Le même nom avec 2 CIK ou plus dans la même compagnie : routinier par le nom, pas par chacun de ses CIK
ciks_du_nom = defaultdict(set)
for (o, e), ns in noms_de.items():
    for n in ns:
        ciks_du_nom[(nom_normal(n), e)].add(o)
fusion = sorted(k for k, os_ in ciks_du_nom.items() if len(os_) > 1 and classe(par_nom[k])[0] == "routinier"
                and all(classe(par_cik[(o, k[1])])[0] != "routinier" for o in os_)
                and all(nb_transactions[o] <= MAX_TRANSACTIONS * 3 for o in os_))
dire(f"- noms avec 2 CIK ou plus, routiniers seulement par le nom : {len(fusion)}")
if fusion:
    k = fusion[len(fusion) // 2]
    gardees |= {(o, k[1]) for o in ciks_du_nom[k]}
noms_gardes = {(nom_normal(n), e) for (o, e) in gardees for n in noms_de[(o, e)]}
attendus = {"annees": list(ANNEES), "par_cik": {}, "par_nom": {}}
for o, e in sorted(gardees):
    c, m = classe(par_cik[(o, e)])
    attendus["par_cik"][f"{o}:{e}"] = {"classe": c, "mois_communs": m, "noms": sorted(noms_de[(o, e)]),
                                       "mois": {str(a): sorted(par_cik[(o, e)].get(a, [])) for a in ANNEES}}
    dire(f"- CIK {o} chez {e} {sorted(noms_de[(o, e)])} : {c} · mois communs {m} · "
         f"{ {a: sorted(par_cik[(o, e)].get(a, [])) for a in ANNEES} }")
for n, e in sorted(noms_gardes):
    c, m = classe(par_nom[(n, e)])
    attendus["par_nom"][f"{e}|{n}"] = {"classe": c, "mois_communs": m, "ciks": sorted(ciks_du_nom[(n, e)])}
    dire(f"- nom « {n} » chez {e} (CIK {sorted(ciks_du_nom[(n, e)])}) : {c} · mois communs {m}")
(SORTIE / "attendus_inities.json").write_text(json.dumps(attendus, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                              encoding="utf-8")
(SORTIE / "jeux").mkdir(exist_ok=True)
pages = []
for t, fichiers in bruts.items():
    (_, sh, sub), (_, oh, own) = fichiers["SUBMISSION.TSV"], fichiers["REPORTINGOWNER.TSV"]
    cs, co = colonnes(sh), colonnes(oh)
    emetteur = {l.split("\t")[cs["ACCESSION_NUMBER"]]: l.split("\t")[cs["ISSUERCIK"]].strip() for l in sub
                if len(l.split("\t")) > cs["ISSUERCIK"]}
    accs = set()
    for l in own:
        p = l.split("\t")
        if len(p) <= co["RPTOWNERNAME"] or not p[co["RPTOWNERCIK"]].strip().isdigit():
            continue
        e = emetteur.get(p[co["ACCESSION_NUMBER"]], "")
        e = str(int(e)) if e.isdigit() else e
        if (str(int(p[co["RPTOWNERCIK"]])), e) in gardees or (nom_normal(p[co["RPTOWNERNAME"]]), e) in noms_gardes:
            accs.add(p[co["ACCESSION_NUMBER"]])
    with zipfile.ZipFile(SORTIE / "jeux" / f"{t}_form345.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for fin, (vrai, h, ls) in fichiers.items():
            z.writestr(vrai, "\n".join([h] + [l for l in ls if l.split("\t")[0] in accs]) + "\n")
    pages.append(f'<a href="{urlparse(liens[t]).path}">{t}</a>')
    dire(f"- extrait {t} : {len(accs)} dépôts gardés")
# La page : les liens tels quels (chemins de la SEC), pour que le robot trouve ses fichiers
(SORTIE / "page_jeux_de_donnees.html").write_text("\n".join(pages) + "\n", encoding="utf-8")

# ---------- 2. Prix : les 2 derniers fichiers d'échecs de livraison ----------
PAGE_FTD = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
page_ftd = ok(*lire(PAGE_FTD), "page des échecs de livraison").decode("utf-8", "replace")
liens_ftd = {m.group(2) + m.group(3).lower(): urljoin(PAGE_FTD, m.group(1))
             for m in re.finditer(r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", page_ftd, re.I)}
derniers = sorted(liens_ftd)[-2:]
prix = {}
for cle in derniers:
    b = ok(*lire(liens_ftd[cle], 100_000_000), cle)
    z = zipfile.ZipFile(io.BytesIO(b))
    brut = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    for l in brut[1:]:
        p = l.split("|")
        if len(p) == 6 and re.fullmatch(r"\d{8}", p[0]) and re.fullmatch(r"\d+(?:\.\d+)?", p[5].strip()):
            s = p[2].strip()
            if s not in prix or p[0] > prix[s][0]:
                prix[s] = [p[0], float(p[5])]
    garde = [brut[0]] + [l for l in brut[1:] if len(l.split("|")) == 6 and l.split("|")[2].strip() in SYMBOLES]
    with zipfile.ZipFile(SORTIE / f"cnsfails{cle}.zip", "w", zipfile.ZIP_DEFLATED) as zz:
        zz.writestr(z.namelist()[0], "\n".join(garde) + "\n")
    dire(f"- échecs de livraison {cle} : {len(brut):,} lignes · gardées {len(garde) - 1}")
(SORTIE / "page_echecs.html").write_text(
    "\n".join(f'<a href="{urlparse(liens_ftd[c]).path}">{c}</a>' for c in derniers) + "\n", encoding="utf-8")
dire(f"- symboles avec un prix (2 derniers fichiers) : {len(prix):,}")

# ---------- 3. Actions en circulation (frames dei des 5 derniers trimestres) ----------
trim = (AUJOURDHUI.month - 1) // 3 + 1
periodes = []
a, q = AUJOURDHUI.year, trim
for _ in range(5):
    periodes.append(f"CY{a}Q{q}I")
    a, q = (a, q - 1) if q > 1 else (a - 1, 4)
actions, frames = {}, {}
for per in periodes:
    statut, b = lire(f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{per}.json")
    frames[per] = statut
    if statut == 200:
        f = json.loads(b)
        for r in f["data"]:
            if str(r["cik"]) not in actions or r["end"] > actions[str(r["cik"])][1]:
                actions[str(r["cik"])] = [r["val"], r["end"], r["accn"]]
        f["data"] = [r for r in f["data"] if r["cik"] in CIKS.values()]
        (SORTIE / f"frames_{per}.json").write_text(json.dumps(f, ensure_ascii=False) + "\n", encoding="utf-8")
    dire(f"- actions {per} : {statut}")
dire(f"- compagnies avec des actions déclarées : {len(actions):,}")

# ---------- 4. Seuils du NYSE (Kenneth French) ----------
URL_ME = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/ME_Breakpoints_CSV.zip"
b = ok(*lire(URL_ME, 20_000_000), "seuils du NYSE")
(SORTIE / "ME_Breakpoints_CSV.zip").write_bytes(b)
z = zipfile.ZipFile(io.BytesIO(b))
texte = z.read(z.namelist()[0]).decode("latin-1")
mois = [l.split(",") for l in texte.splitlines() if re.match(r"\s*\d{6}\s*,", l)]
dernier_mois = mois[-1]
p30, p70 = float(dernier_mois[2 + 5]), float(dernier_mois[2 + 13])
dire(f"- seuils du NYSE : mois {dernier_mois[0].strip()} · {dernier_mois[1].strip()} compagnies · 30e centile {p30} M$ · "
     f"70e {p70} M$")

# ---------- 5. Fiches de la SEC (formulaires déposés) ----------
fiches = {}
for s, cik in sorted(CIKS.items()):
    b = ok(*lire(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"), f"fiche {s}")
    d = json.loads(b)
    reduite = {"cik": d.get("cik"), "name": d.get("name"), "tickers": d.get("tickers"),
               "filings": {"recent": {"form": d["filings"]["recent"]["form"]}}}
    (SORTIE / "fiches").mkdir(exist_ok=True)
    (SORTIE / "fiches" / f"CIK{cik:010d}.json").write_text(json.dumps(reduite, ensure_ascii=False) + "\n",
                                                          encoding="utf-8")
    formes = {f.split("/")[0] for f in d["filings"]["recent"]["form"]}
    fiches[s] = sorted(formes & (AMERICAINS | ETRANGERS))

# ---------- Attendus de taille (fichiers complets) ----------
attendus_t = {"seuils": {"mois": dernier_mois[0].strip(), "p30": p30, "p70": p70}, "compagnies": {}}
for s in SYMBOLES:
    cik = CIKS.get(s)
    x = {"cik": cik, "rapports": fiches.get(s)}
    ac = actions.get(str(cik)) if cik else None
    pr = prix.get(s)
    x["actions"], x["prix"] = ac, pr
    if not cik:
        x["taille"], x["raison"] = None, "symbole absent de la liste de la SEC"
    elif not (set(fiches.get(s) or []) & AMERICAINS) or set(fiches.get(s) or []) & ETRANGERS:
        x["taille"], x["raison"] = None, "pas de rapports américains (10-K, 10-Q) ou rapports d'émetteur étranger"
    elif not ac or date.fromisoformat(ac[1]) < AUJOURDHUI - timedelta(days=ACTIONS_MAX_JOURS):
        x["taille"], x["raison"] = None, "actions en circulation absentes ou trop vieilles"
    elif not pr or datetime.strptime(pr[0], "%Y%m%d").date() < AUJOURDHUI - timedelta(days=PRIX_MAX_JOURS):
        x["taille"], x["raison"] = None, "pas de prix récent"
    else:
        v = ac[0] * pr[1] / 1e6
        x["valeur_m"] = round(v, 2)
        x["taille"] = "petite" if v < p30 else "grande" if v >= p70 else "moyenne"
    attendus_t["compagnies"][s] = x
    dire(f"- {s} : CIK {cik} · rapports {fiches.get(s)} · actions {ac} · prix {pr} · valeur {x.get('valeur_m')} M$ · "
         f"taille {x['taille']} {x.get('raison', '')}")
(SORTIE / "attendus_taille.json").write_text(json.dumps(attendus_t, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                             encoding="utf-8")
dire("\nVERDICT : extraits écrits")
