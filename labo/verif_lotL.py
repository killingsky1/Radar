"""Contre-vérification INDÉPENDANTE du lot L : initiés routiniers (0 point) et taille en bourse (×1,5 petites compagnies).

1. Routiniers : le labo télécharge lui-même, sur la page officielle de la SEC, les 12 fichiers trimestriels des jeux de
   données sur les formulaires 3, 4 et 5 des 3 années avant chaque classement gardé par le robot, et refait les paires
   routinières avec son propre code (règle publiée : achat ou vente en bourse, codes P et S, par date de transaction,
   dans le même mois de l'année chacune des 3 années ; un initié = même CIK, ou même nom dans la même compagnie). Elles
   doivent être identiques à celles du robot (data/sec/inities_routiniers.json).
2. Dans le score publié : aucune info comptée n'est celle d'un initié routinier selon le labo ; une info routinière d'une
   compagnie des listes est dans « Autres infos (0 point) », avec la raison et les mêmes mois.
3. Taille de chaque compagnie des listes : le labo relit les seuils du NYSE (fichier de Kenneth French), la fiche de la
   SEC (rapports déposés), les fichiers « frames » des actions en circulation (dei, 5 derniers trimestres, le fait le
   plus récent : il doit être exactement celui du robot), le dossier companyfacts de la compagnie (recoupement : le même
   nombre d'actions doit y être) et les 2 derniers fichiers d'échecs de livraison (prix), refait la valeur et la taille,
   et les compare à la fiche (aujourdhui.json). Mesuré le 5 octobre 2026 (sonde_lotL.py) : les deux API de la SEC ne
   concordent pas toujours (FLNA : un 10-Q d'août dans les frames, absent de companyfacts ; ASPI : un fait du 14 août
   dans companyfacts, dans aucun fichier frames) ; une date différente pour le même nombre d'actions est notée, pas un
   écart.
4. Résultats : chaque entrée du lot L a ses raisons, et le résumé par signal est refait ici.
Mêmes règles d'accès : robots.txt lu d'abord, 1,5 s entre deux requêtes ; le courriel est envoyé seulement à la SEC.
"""
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import acces  # labo/acces.py : un site qui ne répond pas = « non vérifiable », jamais un plantage

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lotL.txt")
UA, UA_SEC = "Radar projet personnel", "Radar projet personnel math-veronneau1@hotmail.com"
ecarts, notes, sortie, dernier, robots = [], [], [], [0.0], {}
acces.installer(sortie, SORTIE)


def dire(t=""):
    print(t, flush=True)
    sortie.append(t)


def ua(hote):
    return UA_SEC if hote == "sec.gov" or hote.endswith(".sec.gov") else UA


def lire(url):
    hote = url.split("/")[2]
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with acces.ouvrir(urllib.request.Request(f"https://{hote}/robots.txt", headers={"User-Agent": ua(hote)}),
                              timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) or e.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True  # 404 : pas de robots.txt, tout est permis
        robots[hote] = rp
    if not robots[hote].can_fetch(ua(hote), url):
        raise acces.NonVerifiable(f"robots.txt ne permet pas {url}")
    attente = 1.5 - (time.monotonic() - dernier[0])
    if attente > 0:
        time.sleep(attente)
    try:
        with acces.ouvrir(urllib.request.Request(url, headers={"User-Agent": ua(hote)}), timeout=300) as r:
            return r.read()
    finally:
        dernier[0] = time.monotonic()


def json_de(url):
    return json.loads(lire(url))


MOIS_EN = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
           "décembre"]


def normal(nom):
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", (nom or "").upper()).split())


def colonnes_de(z, nom):
    """[[valeurs des colonnes demandées], …] d'une table TSV du fichier (code du labo)."""
    fichier = [n for n in z.namelist() if n.split("/")[-1].upper() == nom + ".TSV"][0]
    texte = z.read(fichier).decode("utf-8", "replace").replace("\r", "").split("\n")
    entete = texte[0].split("\t")
    return entete, [l.split("\t") for l in texte[1:] if l]


def paires(contenus, annees):
    """{"cik": {(compagnie, initié) : mois communs}, "noms": {(compagnie, nom) : mois communs}} (routinières)."""
    par_cik, par_nom = defaultdict(lambda: defaultdict(set)), defaultdict(lambda: defaultdict(set))
    for contenu in contenus:
        z = zipfile.ZipFile(io.BytesIO(contenu))
        h, lignes = colonnes_de(z, "SUBMISSION")
        a, c = h.index("ACCESSION_NUMBER"), h.index("ISSUERCIK")
        emetteur = {l[a]: str(int(l[c])) for l in lignes if len(l) > c and l[c].strip().isdigit()}
        h, lignes = colonnes_de(z, "REPORTINGOWNER")
        a, c, n = h.index("ACCESSION_NUMBER"), h.index("RPTOWNERCIK"), h.index("RPTOWNERNAME")
        qui = defaultdict(list)
        for l in lignes:
            if len(l) > max(c, n) and l[c].strip().isdigit():
                qui[l[a]].append((str(int(l[c])), normal(l[n])))
        h, lignes = colonnes_de(z, "NONDERIV_TRANS")
        a, d, k = h.index("ACCESSION_NUMBER"), h.index("TRANS_DATE"), h.index("TRANS_CODE")
        for l in lignes:
            if len(l) <= max(d, k) or l[k].strip() not in ("P", "S") or l[a] not in emetteur:
                continue
            m = re.fullmatch(r"(\d{2})-([A-Z]{3})-(\d{4})", l[d].strip().upper())
            if not m or m.group(2) not in MOIS_EN or int(m.group(3)) not in annees:
                continue
            an, mois = int(m.group(3)), MOIS_EN.index(m.group(2)) + 1
            try:
                date(an, mois, int(m.group(1)))  # une date impossible ne compte pas
            except ValueError:
                continue
            for cik, nom in qui[l[a]]:
                par_cik[(emetteur[l[a]], cik)][an].add(mois)
                if nom:
                    par_nom[(emetteur[l[a]], nom)][an].add(mois)
    sortie_ = {}
    for cle, table in (("cik", par_cik), ("noms", par_nom)):
        sortie_[cle] = {}
        for k, h in table.items():
            if all(h.get(x) for x in annees):
                communs = sorted(set.intersection(*(h[x] for x in annees)))
                if communs:
                    sortie_[cle][k] = communs
    return sortie_


def mots_mois(mois, annees):
    t = "chaque mois" if len(mois) == 12 else MOIS_FR[mois[0] - 1] if len(mois) == 1 else \
        ", ".join(MOIS_FR[m - 1] for m in mois[:-1]) + " et " + MOIS_FR[mois[-1] - 1]
    return f"{t} ({', '.join(str(a) for a in annees[:-1])} et {annees[-1]})"


pub = json.loads((racine / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
jour = date.fromisoformat(pub["jour"])
listes = [x for nom in ("hausse", "baisse") for x in pub[nom]]
fichier_r = racine / "sec" / "inities_routiniers.json"
robot_r = json.loads(fichier_r.read_text(encoding="utf-8")) if fichier_r.exists() else {}
dire(f"# Lot L contre-vérifié ({pub['genere_a']}, version du score {pub['version']})\n")
if pub["version"] != "score-8":
    ecarts.append(f"version du score publiée : {pub['version']} (attendu : score-8)")
LABO = {}  # année -> paires routinières refaites par le labo

# ---------- 1. Les paires routinières, refaites aux fichiers de la SEC ----------
with acces.section("Initiés routiniers (jeux de données de la SEC, 12 fichiers trimestriels)"):
    PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
    page = lire(PAGE).decode("utf-8", "replace")
    liens = {f"{m.group(2)}q{m.group(3)}": urljoin(PAGE, m.group(1))
             for m in re.finditer(r"""href=["']([^"']*?(\d{4})q([1-4])_form345\.zip)["']""", page, re.I)}
    dire(f"- page officielle : {len(liens)} fichiers trimestriels, le plus récent {max(liens)}")
    an = jour.year
    besoin = [f"{a}q{q}" for a in range(an - 3, an) for q in (1, 2, 3, 4)]
    if all(t in liens for t in besoin) and str(an) not in (robot_r.get("annees") or {}):
        ecarts.append(f"les 12 fichiers de {an - 3} à {an - 1} sont publiés, mais le robot n'a pas de classement pour {an}")
    for annee, c in sorted((robot_r.get("annees") or {}).items()):
        annees = [int(annee) - 3, int(annee) - 2, int(annee) - 1]
        if c.get("depuis") != annees:
            ecarts.append(f"classement {annee} : années {c.get('depuis')} (attendu {annees})")
        contenus = [lire(liens[f"{a}q{q}"]) for a in annees for q in (1, 2, 3, 4)]
        LABO[annee] = labo = paires(contenus, set(annees))
        for cle in ("cik", "noms"):
            robot = {(e, q): m for e, d in c[cle].items() for q, m in d.items()}
            if robot != labo[cle]:
                manque = sorted(set(labo[cle]) - set(robot))[:5]
                de_trop = sorted(set(robot) - set(labo[cle]))[:5]
                autres = sorted(k for k in set(robot) & set(labo[cle]) if robot[k] != labo[cle][k])[:5]
                ecarts.append(f"classement {annee} par {cle} : robot {len(robot)} paires, labo {len(labo[cle])} · manquent "
                              f"{manque} · de trop {de_trop} · mois différents {autres}")
            dire(f"- {annee} (avec {annees}) par {cle} : robot {len(robot):,} paires routinières · labo {len(labo[cle]):,} · "
                 f"identiques : {'OUI' if robot == labo[cle] else 'NON'}")


def routinier_labo(ev):
    """(mois, années) si un déclarant est routinier selon le classement du LABO, sinon None."""
    annee = (ev.get("occurred_on") or "")[:4]
    p, d = LABO.get(annee), ev.get("data") or {}
    cik = str(d.get("cik_emetteur") or "").strip()
    if not p or not cik.isdigit():
        return None
    e = str(int(cik))
    for o in d.get("proprietaires_cik") or []:
        if str(o).isdigit() and (e, str(int(o))) in p["cik"]:
            return p["cik"][(e, str(int(o)))], [int(annee) - 3, int(annee) - 2, int(annee) - 1]
    for n in (ev.get("entities") or [])[:-1]:
        if (e, normal(n)) in p["noms"]:
            return p["noms"][(e, normal(n))], [int(annee) - 3, int(annee) - 2, int(annee) - 1]
    return None


# ---------- 2. Le score publié : rien de routinier ne compte ----------
with acces.section("Score publié : infos routinières à 0 point"):
    if not LABO:
        raise acces.NonVerifiable("pas de classement refait par le labo (section 1)")
    fichiers = sorted((racine / "evenements").glob("*.jsonl"))[-4:]
    infos = [json.loads(l) for f in fichiers for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    routinieres = {e["id"]: routinier_labo(e) for e in infos if e["source"] == "sec_form4"
                   and e.get("badge") in ("officiel", "confirme") and (jour - date.fromisoformat(e["published_on"])).days <= 90
                   and routinier_labo(e)}
    dire(f"- formulaires 4 des 90 derniers jours d'un initié routinier (selon le labo) : {len(routinieres)}")
    for i, (m, a) in sorted(routinieres.items())[:10]:
        e = next(x for x in infos if x["id"] == i)
        dire(f"  - {e['tickers'][0]} · {', '.join(e['entities'][:-1])} · {e['occurred_on']} · mois : {mots_mois(m, a)}")
    for x in listes:
        for g in x["groupes"]:
            for i in g["infos"]:
                if i["id"] in routinieres:
                    ecarts.append(f"{x['symbole']} : l'info {i['id']} d'un initié routinier compte dans la note")
        for c in x["contexte"]:
            r = routinieres.get(c["id"])
            dit_routinier = c["pourquoi"].startswith("Initié « routinier »")
            if dit_routinier and not r:
                ecarts.append(f"{x['symbole']} : {c['id']} dite routinière, pas selon le labo")
            elif dit_routinier and not c["pourquoi"].endswith(f"Mois : {mots_mois(*r)}."):
                ecarts.append(f"{x['symbole']} : {c['id']} : mois écrits « {c['pourquoi'][-60:]} », labo {mots_mois(*r)}")
            elif dit_routinier:
                dire(f"- {x['symbole']} : {c['id']} en contexte, raison et mois identiques au labo")

# ---------- 3. La taille de chaque compagnie des listes ----------
with acces.section("Taille des compagnies des listes (Kenneth French, fiches et dossiers de la SEC, prix de la SEC)"):
    z = zipfile.ZipFile(io.BytesIO(lire("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/ME_Breakpoints_CSV.zip")))
    rangees = [[v.strip() for v in l.split(",")] for l in z.read(z.namelist()[0]).decode("latin-1").splitlines()
               if re.match(r"\s*\d{6}\s*,", l)]
    seuils = {"mois": rangees[-1][0], "p30": float(rangees[-1][7]), "p70": float(rangees[-1][15])}
    dire(f"- seuils du NYSE (labo) : {seuils}")
    PAGE_FTD = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
    ftd = {m.group(2) + m.group(3).lower(): urljoin(PAGE_FTD, m.group(1)) for m in re.finditer(
        r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", lire(PAGE_FTD).decode("utf-8", "replace"), re.I)}
    prix = {}
    for cle in sorted(ftd)[-2:]:
        zz = zipfile.ZipFile(io.BytesIO(lire(ftd[cle])))
        for l in zz.read(zz.namelist()[0]).decode("latin-1").splitlines()[1:]:
            p = l.split("|")
            if len(p) == 6 and re.fullmatch(r"\d{8}", p[0]) and re.fullmatch(r"\d+(\.\d+)?", p[5].strip()):
                if p[2].strip() not in prix or p[0] > prix[p[2].strip()][0]:
                    prix[p[2].strip()] = [p[0], float(p[5])]
    dire(f"- prix (labo) : fichiers {sorted(ftd)[-2:]} · {len(prix):,} symboles")
    tickers = {x["ticker"].upper(): int(x["cik_str"])
               for x in json_de("https://www.sec.gov/files/company_tickers.json").values()}
    # Les fichiers frames, relus ici : le fait le plus récent de chaque compagnie (code du labo)
    a_, q_ = jour.year, (jour.month - 1) // 3 + 1
    frames = {}
    for _ in range(5):
        try:
            for r in json_de(f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/"
                             f"CY{a_}Q{q_}I.json")["data"]:
                if r["val"] > 0 and (r["cik"] not in frames or r["end"] > frames[r["cik"]]["end"]):
                    frames[r["cik"]] = r
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        a_, q_ = (a_, q_ - 1) if q_ > 1 else (a_ - 1, 4)
    dire(f"- frames (labo) : {len(frames):,} compagnies avec des actions déclarées")
    for x in listes:
        t, s = x.get("taille"), x["symbole"]
        if t is None:
            dire(f"- {s} : pas de fiche SEC chez le robot (pas de taille, pas de bonus)")
            continue
        if t.get("seuils") != seuils:
            ecarts.append(f"{s} : seuils {t.get('seuils')} ≠ labo {seuils}")
        cik = tickers.get(s)
        if cik is None:
            ecarts.append(f"{s} : absent du fichier des symboles de la SEC")
            continue
        formes = {f.split("/")[0] for f in json_de(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")["filings"]["recent"]["form"]}
        etrangere = bool(formes & {"20-F", "40-F", "6-K"}) or not formes & {"10-K", "10-Q", "10-KT", "10-QT"}
        faits = []
        try:
            cf = json_de(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
            faits = cf.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        recent = max(faits, key=lambda f: (f["end"], f["filed"]), default=None)
        fr_ = frames.get(cik)
        fait_frames = {"val": fr_["val"], "end": fr_["end"]} if fr_ else None
        pr = prix.get(s)

        def classe(fait):
            """La taille selon les règles publiées, avec ce fait du dossier de la SEC : (taille, raison si inconnue)."""
            if etrangere:
                return None, "étrangère"
            if not fait or date.fromisoformat(fait["end"]) < jour - timedelta(days=200) or fait["val"] < 500_000:
                return None, "actions"
            if not pr or datetime.strptime(pr[0], "%Y%m%d").date() < jour - timedelta(days=60):
                return None, "prix"
            v = fait["val"] * pr[1] / 1e6
            return ("petite" if v < seuils["p30"] else "grande" if v >= seuils["p70"] else "moyenne"), None

        labo_t, raison = classe(fait_frames)  # la règle publiée : le fait le plus récent des fichiers frames
        if t["taille"] != labo_t:
            ecarts.append(f"{s} : taille {t['taille']} ({t.get('raison')}) ≠ labo {labo_t} ({raison})")
        if recent and labo_t and classe(recent)[0] != labo_t:
            notes.append(f"{s} : avec le fait le plus récent du dossier companyfacts ({recent['val']:,} au {recent['end']}), "
                         f"la taille serait {classe(recent)[0]} (frames : {labo_t})")
        flottant = max(cf.get("facts", {}).get("dei", {}).get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
                       if faits else [], key=lambda f: (f["end"], f["filed"]), default=None)
        if t["taille"] == "petite" and flottant and flottant["val"] / 1e6 >= seuils["p30"]:
            notes.append(f"{s} : petite selon actions × prix, mais flottant public de {flottant['val'] / 1e6:,.0f} M$ au "
                         f"{flottant['end']} (seuil {seuils['p30']:,} M$) : cours tombé depuis, ou une seule catégorie d'actions ?")
        if t["taille"]:
            robot_a = t["actions"]
            if not fait_frames or [fait_frames["val"], fait_frames["end"]] != robot_a:
                ecarts.append(f"{s} : actions du robot {robot_a} ≠ fait le plus récent des frames relus par le labo {fait_frames}")
            if any(f["end"] == robot_a[1] and f["val"] == robot_a[0] for f in faits):
                pass  # confirmé par le dossier companyfacts
            elif any(f["val"] == robot_a[0] for f in faits):
                notes.append(f"{s} : {robot_a[0]:,} actions au {robot_a[1]} selon les frames ; le dossier companyfacts a le "
                             f"même nombre à une autre date (dernier : {recent['end'] if recent else '—'}) : les 2 API de la "
                             f"SEC ne concordent pas sur la date")
            else:
                ecarts.append(f"{s} : {robot_a[0]:,} actions (frames) introuvables dans le dossier companyfacts de la SEC")
            if recent and [recent["val"], recent["end"]] != robot_a:
                notes.append(f"{s} : fait le plus récent du dossier companyfacts ({recent['val']:,} au {recent['end']}) ≠ "
                             f"frames ({robot_a[0]:,} au {robot_a[1]})")
            if t["prix"] != pr:
                ecarts.append(f"{s} : prix {t['prix']} ≠ labo {pr}")
            v = robot_a[0] * pr[1] / 1e6 if pr else None
            if v is None or abs(t["valeur_m"] - v) > 0.06:
                ecarts.append(f"{s} : valeur {t['valeur_m']} M$ ≠ labo {v}")
            facteur = any(f[0] == "Petite compagnie" for g in x["groupes"] for i in g["infos"] for f in i["facteurs"])
            achat = any(i["regle"] == "achat_dirigeant" for g in x["groupes"] for i in g["infos"])
            if facteur != (t["taille"] == "petite" and achat):
                ecarts.append(f"{s} : bonus de petite compagnie {'appliqué' if facteur else 'absent'} à tort")
        actions_sec = f"{recent['val']:,} au {recent['end']}" if recent else "aucune"
        dire(f"- {s} : robot {t['taille'] or 'inconnue'} ({t.get('valeur_m', '—')} M$) · labo {labo_t or 'inconnue'}"
             f"{' (' + raison + ')' if raison else ''} · actions du dossier SEC {actions_sec} · prix {pr} · rapports "
             f"{sorted(formes & {'10-K', '10-Q', '20-F', '40-F', '6-K'})}")

# ---------- 4. Résultats : raisons des entrées et résumé par signal ----------
with acces.section("Résultats : raisons des entrées et résumé par signal"):
    r = json.loads((racine / "app" / "resultats.json").read_text(encoding="utf-8"))
    hist = json.loads((racine / "resultats" / "suggestions.json").read_text(encoding="utf-8"))["entrees"]
    lot_l = [e for e in hist if e.get("methode") == "score-8"]
    sans = [e for e in lot_l if not isinstance(e.get("signaux"), list) or "taille" not in e]
    if sans:
        ecarts.append(f"entrées du lot L sans raisons : {[e['symbole'] for e in sans]}")
    dire(f"- entrées : {len(hist)} · du lot L (score-8) : {len(lot_l)} · sans raisons notées (avant) : "
         f"{sum('signaux' not in e for e in hist)}")
    rows = {(nom, x["symbole"]): x for nom in ("hausse", "baisse") for x in pub[nom]}
    for e in lot_l:
        x = rows.get((e["sens"], e["symbole"]))
        if x and x.get("depuis") == e["entree"]:  # toujours dans la liste depuis son entrée : mêmes raisons
            attendu = [{"famille": g["famille"], "sens": g["sens"], "regle": i["regle"], "facteurs": [f[0] for f in i["facteurs"]]}
                       for g in x["groupes"] for i in g["infos"] if i["compte"]]
            if e["signaux"] != attendu and x.get("note10") == e.get("note10"):
                notes.append(f"{e['symbole']} : raisons notées à l'entrée {e['signaux']}, aujourd'hui {attendu}")
    refait = {"hausse": {}, "baisse": {}, "sans_raisons": 0}
    for l in r["lignes"]:
        if "signaux" not in l:
            refait["sans_raisons"] += 1
            continue
        s = 1 if l["sens"] == "hausse" else -1
        memes = [x for x in l["signaux"] if x["sens"] == s]
        cles = {f"regle:{x['regle']}" for x in memes} | {f"facteur:{f}" for x in memes for f in x["facteurs"]
                                                         if f != "Petite compagnie"}
        cles |= {"plusieurs_familles"} if len(memes) >= 2 else set()
        cles |= {c for c in ("grace_au_bonus", "grace_a_la_taille") if l.get(c)}
        cles.add(f"taille:{l.get('taille') or 'inconnue'}")
        for c in cles:
            y = refait[l["sens"]].setdefault(c, {"entrees": 0, "7": [0, 0, []], "30": [0, 0, []]})
            y["entrees"] += 1
            for h in ("7", "30"):
                m = l["horizons"][h]
                if m["statut"] == "mesure" and m.get("battu") is not None:
                    y[h][0] += 1
                    y[h][1] += int(m["battu"])
                    y[h][2].append(m["ecart"])
    publie = r.get("par_signal") or {}
    if publie.get("sans_raisons") != refait["sans_raisons"]:
        ecarts.append(f"par signal : sans raisons {publie.get('sans_raisons')} ≠ labo {refait['sans_raisons']}")
    for sens in ("hausse", "baisse"):
        if set(publie.get(sens, {})) != set(refait[sens]):
            ecarts.append(f"par signal ({sens}) : signaux {sorted(publie.get(sens, {}))} ≠ labo {sorted(refait[sens])}")
            continue
        for c, y in refait[sens].items():
            p = publie[sens][c]
            for h in ("7", "30"):
                moy = round(sum(y[h][2]) / len(y[h][2]), 4) if y[h][2] else None
                if (p[h]["mesurees"], p[h]["battu"], p[h]["ecart_moyen"]) != (y[h][0], y[h][1], moy) or p["entrees"] != y["entrees"]:
                    ecarts.append(f"par signal ({sens}, {c}, {h} jours) : publié {p['entrees']} {p[h]} ≠ labo {y['entrees']} "
                                  f"{y[h][:2]} {moy}")
        dire(f"- par signal ({sens}) : {len(refait[sens])} signaux refaits · "
             + ", ".join(f"{c} {y['entrees']}" for c, y in sorted(refait[sens].items())))

for n in notes:
    dire(f"Note : {n}")
dire("\n".join(ecarts) if ecarts else ("AUCUN ÉCART dans ce qui a pu être relu." if acces.NON_VERIFIABLES else
                                       "AUCUN ÉCART : routiniers, tailles et raisons refaits aux sources officielles."))
for ligne in acces.lignes_non_verifiables():
    dire(ligne)
dire(acces.verdict(ecarts))
SORTIE.write_text("\n".join(sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
