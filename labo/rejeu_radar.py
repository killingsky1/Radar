"""Rejeu d'un an de Radar : 10 000 $ qui suivent la liste « hausse », juillet 2025 → juin 2026.

Règles : celles du robot ACTUEL (branche main, score-8), appelées telles quelles (son lecteur du formulaire 4, son
lecteur des 13D, ses contrôles, son score, sa taille en bourse, sa page Résultats). Rien du futur : chaque jour
ouvrable à 23 h 17 (Toronto), le score voit seulement ce que la SEC avait publié ce jour-là.

Ce qui est rejoué : les 2 familles qui expliquent les 20 compagnies de la liste « hausse » d'aujourd'hui.
- Formulaires 4 (dirigeants) : refaits à partir des jeux de données officiels de la SEC (insider transactions data
  sets) en document XML, puis lus par le lecteur du robot (toutes ses règles : plan 10b5-1, émission, automatique,
  routinier, rôle, groupe d'achats, petite compagnie).
- 13D originaux (fonds activistes) : les vrais documents d'EDGAR, lus par le lecteur du robot.
Pas rejoué : grands fonds (13F), élus, FDA, SEC, rappels, 8-K.

Compagnies : celles cotées aujourd'hui au Nasdaq, au NYSE ou au CBOE, PLUS celles retirées de la bourse après l'info
(formulaire 25 ou 25-NSE dans leur fiche SEC) : sinon on oublierait les compagnies disparues (biais du survivant).
Symbole : celui écrit dans le formulaire à ce moment-là, sinon le dernier écrit avant, sinon celui d'aujourd'hui.

Argent : 10 000 $ / 12 = 833,33 $ par mois, divisés également entre les nouvelles entrées « hausse » du mois.
Achat et vente : règles de la page Résultats (prix officiels de la SEC ; achat à la clôture d'un jour de bourse APRÈS la
suggestion ; vente 30 jours plus tard). Pas de prix au départ : pas acheté (argent gardé). Pas de prix à l'arrivée :
1re date suivante avec un prix (jusqu'à 90 jours), sinon la dernière avant. Nouveau CUSIP : 0 %.
Saut anormal (« à vérifier ») : gardé, et une version à 0 % pour voir son effet.

Sortie : labo/rejeu/ (resume.md, positions.json, mensuel.json, listes.json, journal.md) ; rejeu/ (pour verif_rejeu.py).

Période réglable (variables d'environnement) : REJEU_DEBUT et REJEU_FIN (AAAA-MM-JJ), REJEU_SORTIE (dossier),
REJEU_ARGENT=0 pour ne pas faire le calcul d'argent d'un an (le rejeu de 3 ans le fait dans strategies.py), REJEU_VERIF
(jours des photos pour le recalcul, séparés par des virgules). Rodage : les 3 mois avant le début.
Toujours écrits : entrees.json (les nouvelles entrées « hausse » de la période) et rejeu/prix.json (prix pour l'analyse).
"""
import csv
import gzip
import os
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from bisect import bisect_left, bisect_right
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, datetime, time as heure, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from statistics import mean
from xml.sax.saxutils import escape, quoteattr
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path("principal/robot").resolve()))
from radar import emetteurs, resultats, score  # noqa: E402
from radar.collecteurs import inities, prix_sec, sec, taille  # noqa: E402
from radar.http import ClientPoli, ErreurSource  # noqa: E402
from radar.run import CONFIG, _charger_json  # noqa: E402
from radar.validate import SYMBOLE_RE, valider  # noqa: E402

csv.field_size_limit(sys.maxsize)
TORONTO = ZoneInfo("America/Toronto")
CACHE = Path("cache")
SORTIE = Path(os.environ.get("REJEU_SORTIE", "labo/rejeu"))
TRAVAIL = Path("rejeu")  # pour verif_rejeu.py (pas sauvegardé dans la branche)
DEBUT = date.fromisoformat(os.environ.get("REJEU_DEBUT", "2025-07-01"))
FIN = date.fromisoformat(os.environ.get("REJEU_FIN", "2026-06-30"))
ARGENT = os.environ.get("REJEU_ARGENT", "1") == "1"


def mois_avant(j, n):
    a, m = j.year, j.month - n
    while m <= 0:
        a, m = a - 1, m + 12
    return date(a, m, 1)


def trimestre(j):
    return f"{j.year}q{(j.month - 1) // 3 + 1}"


RODAGE = mois_avant(DEBUT, 3)
PREMIER_DEPOT = mois_avant(RODAGE, 2)  # au 1er jour du rodage, le robot voit les dépôts des 3 derniers mois
MENSUEL = 10_000 / 12
FRAIS = 10.0  # $ par transaction (achat ou vente), variante avec frais
HEURE = heure(23, 17)
# Classements des routiniers : le robot garde l'année en cours et la précédente
ANNEES_CLASSEMENT = tuple(range(RODAGE.year - 1, FIN.year + 1))
TOUS_LES_TRIMESTRES = [f"{a}q{q}" for a in range(2006, FIN.year + 1) for q in (1, 2, 3, 4)]
TRIMESTRES = [q for q in TOUS_LES_TRIMESTRES if f"{ANNEES_CLASSEMENT[0] - 3}q1" <= q <= trimestre(FIN)]
TRIMESTRES_EVENEMENTS = [q for q in TRIMESTRES if trimestre(PREMIER_DEPOT) <= q <= trimestre(FIN)]
JOURS_VERIF = tuple(date.fromisoformat(j) for j in os.environ.get(
    "REJEU_VERIF", "2025-08-15,2025-12-15,2026-04-15").split(","))
SYMBOLES_VIDES = {"NONE", "NA", "N-A", "NULL", "N", "TBD"}
FN = ("SECURITY_TITLE_FN", "TRANS_DATE_FN", "EQUITY_SWAP_TRANS_CD_FN", "TRANS_SHARES_FN", "TRANS_PRICEPERSHARE_FN",
      "TRANS_ACQUIRED_DISP_CD_FN")
RADIATION = {"25", "25-NSE"}
JOURS_APRES_RADIATION = 10  # le retrait prend effet 10 jours après le formulaire 25
SORTIE_MAX_JOURS = 90

SORTIE.mkdir(parents=True, exist_ok=True)
TRAVAIL.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
client = ClientPoli(_charger_json(CONFIG).get("contact", ""))
compte = Counter()
journal = []
T0 = time.time()


def dire(t=""):
    t = f"[{(time.time() - T0) / 60:5.1f} min] {t}" if t else t
    print(t, flush=True)
    journal.append(t)
    (SORTIE / "journal.md").write_text("\n".join(journal) + "\n", encoding="utf-8")


# ---------- Lecture polie avec cache (actions/cache garde cache/ d'un passage à l'autre) ----------

def brut(url, nom=None):
    """Le contenu d'une adresse. 401 ou 403 : arrêt immédiat (on ne contourne jamais un refus)."""
    if nom and (CACHE / nom).exists():
        return (CACHE / nom).read_bytes()
    try:
        t = client.get(url)
    except ErreurSource as exc:
        if re.search(r"HTTP 40[13]\b", str(exc)):
            raise SystemExit(f"INTERDIT par le site, arrêt sans contourner : {exc}")
        raise
    compte["requetes"] += 1
    if nom:
        (CACHE / nom).parent.mkdir(parents=True, exist_ok=True)
        (CACHE / nom).write_bytes(t.contenu)
    return t.contenu


def ou_rien(url):
    """404 = rien (pas de fiche, pas de fait). Autre panne : « ERREUR » (pas gardé, relu au prochain passage)."""
    try:
        return brut(url)
    except ErreurSource as exc:
        if "HTTP 404" in str(exc):
            return None
        compte["illisibles"] += 1
        return "ERREUR"


def garde(nom, faire):
    c = CACHE / nom
    if c.exists():
        return json.loads(gzip.decompress(c.read_bytes()))
    v = faire()
    if v != "ERREUR":
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_bytes(gzip.compress(json.dumps(v, separators=(",", ":")).encode()))
    return v


def publie_le(url):
    """Date de mise en ligne d'un fichier de la SEC (en-tête Last-Modified)."""
    client._attendre_son_tour("sec.gov")
    r = client.session.head(url, headers=client.entetes_sec, timeout=30, allow_redirects=True)
    if r.status_code in (401, 403):
        raise SystemExit(f"INTERDIT par le site : {url} HTTP {r.status_code}")
    lm = r.headers.get("Last-Modified")
    return parsedate_to_datetime(lm).date().isoformat() if lm else None


# ---------- 1. Jeux de données des initiés (formulaires 4) ----------

def jour_ds(texte):
    j = inities._jour(texte)
    return j.isoformat() if j else None


def table(z, nom):
    vrai = next(n for n in z.namelist() if n.rsplit("/", 1)[-1].upper() == f"{nom}.TSV")
    with z.open(vrai) as f:
        lecteur = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline=""), delimiter="\t")
        entete = next(lecteur)
        for p in lecteur:
            if len(p) == len(entete):
                yield dict(zip(entete, p))
            else:
                compte[f"lignes mal formées ({nom})"] += 1


def lire_trimestre(q, url):
    def faire():
        contenu = brut(url)
        sortie = {"routine": sorted({tuple(t) for t in inities.transactions(contenu, set(range(2018, 2027)))}),
                  "symboles": []}
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            soumis = {}
            for r in table(z, "SUBMISSION"):
                depose, cik = jour_ds(r["FILING_DATE"]), r["ISSUERCIK"].strip()
                if not depose or not cik.isdigit():
                    continue
                sortie["symboles"].append([str(int(cik)), depose, r["ISSUERTRADINGSYMBOL"].strip(), r["ISSUERNAME"].strip()])
                if q in TRIMESTRES_EVENEMENTS and r["DOCUMENT_TYPE"].strip() == "4":
                    soumis[r["ACCESSION_NUMBER"].strip()] = {
                        "depose": depose, "cik": str(int(cik)), "nom": r["ISSUERNAME"].strip(),
                        "symbole": r["ISSUERTRADINGSYMBOL"].strip(), "aff": r["AFF10B5ONE"].strip()}
            if q not in TRIMESTRES_EVENEMENTS:
                return sortie
            lignes = defaultdict(list)
            for r in table(z, "NONDERIV_TRANS"):
                acc, code = r["ACCESSION_NUMBER"].strip(), r["TRANS_CODE"].strip()
                if acc in soumis and code in ("P", "S"):
                    lignes[acc].append([int(r["NONDERIV_TRANS_SK"] or 0), code, jour_ds(r["TRANS_DATE"]) or "",
                                        r["TRANS_SHARES"].strip(), r["TRANS_PRICEPERSHARE"].strip(),
                                        r["TRANS_ACQUIRED_DISP_CD"].strip(), r["SHRS_OWND_FOLWNG_TRANS"].strip(),
                                        [re.findall(r"F\d+", r.get(c) or "") for c in FN]])
            proprios = defaultdict(list)
            for r in table(z, "REPORTINGOWNER"):
                acc = r["ACCESSION_NUMBER"].strip()
                if acc in lignes:
                    proprios[acc].append([r["RPTOWNERCIK"].strip(), r["RPTOWNERNAME"].strip(),
                                          r["RPTOWNER_RELATIONSHIP"].strip(), r["RPTOWNER_TITLE"].strip()])
            besoin = {(acc, i) for acc, ls in lignes.items() for l in ls for ids in l[7] for i in ids}
            notes = defaultdict(dict)
            for r in table(z, "FOOTNOTES"):
                cle = (r["ACCESSION_NUMBER"].strip(), r["FOOTNOTE_ID"].strip())
                if cle in besoin:
                    notes[cle[0]][cle[1]] = " ".join(r["FOOTNOTE_TXT"].split())
            sortie["depots"] = {acc: {**soumis[acc], "proprios": proprios[acc], "lignes": sorted(ls),
                                      "notes": notes.get(acc, {})} for acc, ls in lignes.items()}
        return sortie
    r = garde(f"inities/{q}.json.gz", faire)
    if q in TRIMESTRES_EVENEMENTS and "depots" not in r:
        # Gardé par un rejeu d'une autre période, sans les dépôts : on relit le fichier
        (CACHE / f"inities/{q}.json.gz").unlink()
        compte["jeux de données relus (gardés sans les dépôts)"] += 1
        r = garde(f"inities/{q}.json.gz", faire)
    return r


INTERDITS_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def x(texte):
    """Texte pour un document XML (les caractères de contrôle, interdits en XML, deviennent des espaces)."""
    return escape(INTERDITS_XML.sub(" ", texte or ""))


def xml_form4(acc, d):
    """Le formulaire 4 refait en document XML (mêmes éléments que l'original) pour le lecteur du robot."""
    def notes(ids):
        return "".join(f"<footnoteId id={quoteattr(i)}/>" for i in ids)

    def cik10(c):
        return f"{int(c):010d}" if c.isdigit() else x(c)

    proprios = ""
    for c, n, rel, titre in d["proprios"]:
        r = {x.strip() for x in rel.split(",")}
        proprios += (f"<reportingOwner><reportingOwnerId><rptOwnerCik>{cik10(c)}</rptOwnerCik><rptOwnerName>{x(n)}"
                     f"</rptOwnerName></reportingOwnerId><reportingOwnerRelationship><isDirector>{int('Director' in r)}"
                     f"</isDirector><isOfficer>{int('Officer' in r)}</isOfficer><isTenPercentOwner>"
                     f"{int('TenPercentOwner' in r)}</isTenPercentOwner><officerTitle>{x(titre)}</officerTitle>"
                     "</reportingOwnerRelationship></reportingOwner>")
    trans = ""
    for _, code, jour, actions, prix, ad, apres, (f_titre, f_date, f_code, f_actions, f_prix, f_ad) in d["lignes"]:
        trans += (f"<nonDerivativeTransaction><securityTitle><value>-</value>{notes(f_titre)}</securityTitle>"
                  f"<transactionDate><value>{jour}</value>{notes(f_date)}</transactionDate>"
                  f"<transactionCoding><transactionFormType>4</transactionFormType><transactionCode>{code}"
                  f"</transactionCode>{notes(f_code)}</transactionCoding><transactionAmounts>"
                  f"<transactionShares><value>{x(actions)}</value>{notes(f_actions)}</transactionShares>"
                  f"<transactionPricePerShare><value>{x(prix)}</value>{notes(f_prix)}</transactionPricePerShare>"
                  f"<transactionAcquiredDisposedCode><value>{x(ad)}</value>{notes(f_ad)}"
                  "</transactionAcquiredDisposedCode></transactionAmounts><postTransactionAmounts>"
                  f"<sharesOwnedFollowingTransaction><value>{x(apres)}</value></sharesOwnedFollowingTransaction>"
                  "</postTransactionAmounts></nonDerivativeTransaction>")
    pied = "".join(f"<footnote id={quoteattr(i)}>{x(t)}</footnote>" for i, t in d["notes"].items())
    xml = (f"<ownershipDocument><documentType>4</documentType><issuer><issuerCik>{cik10(d['cik'])}</issuerCik>"
           f"<issuerName>{x(d['nom'])}</issuerName><issuerTradingSymbol>{x(d['symbole'])}"
           f"</issuerTradingSymbol></issuer><aff10b5One>{x(d['aff'])}</aff10b5One>{proprios}"
           f"<nonDerivativeTable>{trans}</nonDerivativeTable><footnotes>{pied}</footnotes></ownershipDocument>")
    return (f"ACCESSION NUMBER: {acc}\nCONFORMED SUBMISSION TYPE: 4\nFILED AS OF DATE: {d['depose'].replace('-', '')}\n"
            f"<XML>\n{xml}\n</XML>\n")


# ---------- 2. Symboles et cotes à la date de l'info ----------

def symbole_utilisable(s):
    n = sec.normaliser_symbole(s)
    return n if n and n not in SYMBOLES_VIDES and SYMBOLE_RE.match(n) else None


class Cotes:
    """Comme sec.Symboles, mais à la date de l'info : la liste officielle d'aujourd'hui, plus les compagnies
    retirées de la bourse depuis (formulaire 25 ou 25-NSE après l'info)."""

    def __init__(self, actuelle, declares, fiches):
        self.actuelle, self.declares, self.fiches = actuelle, declares, fiches

    def dernier_declare(self, cik, jour):
        liste = self.declares.get(cik) or []
        i = bisect_right(liste, (jour, "￿"))
        for d, s in reversed(liste[:i]):
            if symbole_utilisable(s):
                return symbole_utilisable(s)
        return None

    def radiee_apres(self, cik, jour):
        f = self.fiches.get(cik) or {}
        limite = (date.fromisoformat(jour) - timedelta(days=JOURS_APRES_RADIATION)).isoformat()
        return next((d for d, forme in f.get("formes", []) if forme in RADIATION and d >= limite), None)

    def au_jour(self, jour, declare=None):
        moi = self

        class AuJour:
            def cote(self, cik):
                cik = str(int(cik))
                symbole = symbole_utilisable(declare) or moi.dernier_declare(cik, jour)
                actuel = moi.actuelle.cote(cik)
                if actuel:
                    return {**actuel, "ticker": symbole or actuel["ticker"]}
                radiation = moi.radiee_apres(cik, jour)
                if radiation and symbole:
                    nom = (moi.fiches.get(cik) or {}).get("nom") or moi.nom_declare(cik) or symbole
                    return {"cik": int(cik), "ticker": symbole, "name": nom, "exchange": f"retirée ({radiation})"}
                return None

            def tous(self, cik):
                c = self.cote(cik)
                return sorted({c["ticker"]} | set(moi.actuelle.tous(cik))) if c else moi.actuelle.tous(cik)

        return AuJour()

    def nom_declare(self, cik):
        return next((n for _, _, n in reversed(self.noms.get(cik, []))), None) if hasattr(self, "noms") else None


# ---------- 3. Fiches SEC, faits XBRL, prix, seuils ----------

def fiche(cik):
    def faire():
        b = ou_rien(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
        if b in (None, "ERREUR"):
            return b
        j = json.loads(b)
        r = j.get("filings", {}).get("recent", {})
        formes = list(zip(r.get("filingDate", []), r.get("form", [])))
        if formes and min(d for d, _ in formes) > "2024-01-01":
            for f in j.get("filings", {}).get("files", []):
                if f.get("filingTo", "") >= "2024-01-01":
                    b2 = ou_rien(f"https://data.sec.gov/submissions/{f['name']}")
                    if b2 == "ERREUR":
                        return "ERREUR"
                    if b2:
                        r2 = json.loads(b2)
                        formes += list(zip(r2.get("filingDate", []), r2.get("form", [])))
        return {"nom": j.get("name"), "bourses": j.get("exchanges"), "symboles": j.get("tickers"),
                "formes": sorted(formes)}
    return garde(f"fiches/{int(cik)}.json.gz", faire)


def faits(cik):
    def faire():
        b = ou_rien(taille.CONCEPT.format(int(cik)))
        if b in (None, "ERREUR"):
            return [] if b is None else b
        j = json.loads(b)
        return [[f.get("end"), f.get("val"), f.get("filed")] for f in j.get("units", {}).get("shares", [])]
    return garde(f"concept/{int(cik)}.json.gz", faire)


def seuils_tous(contenu):
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        texte = z.read(z.namelist()[0]).decode("latin-1")
    sortie = {}
    for l in texte.splitlines():
        if re.match(r"\s*\d{6}\s*,", l):
            m = [x.strip() for x in l.split(",")]
            if len(m) == 22:
                c = [float(x) for x in m[2:]]
                sortie[m[0]] = {"mois": m[0], "compagnies_nyse": int(m[1]), "p30": c[5], "p70": c[13]}
    return sortie


def plus_jours(aaaammjj, n):
    return resultats.plus_jours(aaaammjj, n)


def compact(j):
    return j.strftime("%Y%m%d")


def main():
    dire(f"# Rejeu de Radar du {DEBUT} au {FIN} (rodage dès le {RODAGE})")
    dire(f"Code du robot : {Path('principal/robot/radar/score.py').resolve()} · {score.VERSION}")

    # --- Liste officielle d'aujourd'hui ---
    actuelle = sec.Symboles(json.loads(brut("https://www.sec.gov/files/company_tickers_exchange.json",
                                            "symboles/company_tickers_exchange.json")))

    # --- Jeux de données des initiés ---
    liens = inities.fichiers_de_la_page(brut(inities.PAGE, "pages/inities.html").decode("utf-8", "replace"))
    manque = [q for q in TRIMESTRES if q not in liens]
    if manque:
        raise SystemExit(f"jeux de données absents de la page : {manque}")
    routine, declares, depots = {}, defaultdict(list), {}
    noms = defaultdict(list)
    for q in TRIMESTRES:
        r = lire_trimestre(q, liens[q])
        routine[q] = r["routine"]
        for cik, d, s, n in r["symboles"]:
            declares[cik].append((d, s))
            noms[cik].append((d, s, n))
        depots.update(r.get("depots", {}))
        dire(f"jeu de données {q} : {len(r['routine']):,} paires (initié, mois) en bourse · "
             f"{len(r.get('depots', {})):,} formulaires 4 avec un achat ou une vente")
    for cik in declares:
        declares[cik].sort()
        noms[cik].sort()
    publication = garde(f"inities/publication_{TRIMESTRES[0]}_{TRIMESTRES[-1]}.json.gz",
                        lambda: {q: publie_le(liens[q]) for q in TRIMESTRES})

    def fin_trimestre(q):
        a, m = int(q[:4]), 3 * int(q[5])
        return date(a, m, monthrange(a, m)[1])

    # Une date plus de 90 jours après la fin du trimestre est une remise en ligne (mesuré : les autres fichiers sont mis
    # en ligne de 5 à 49 jours après la fin du trimestre), pas la 1re mise en ligne.
    ecarts_jours = {q: (date.fromisoformat(d) - fin_trimestre(q)).days for q, d in publication.items() if d}
    delais = {q: n for q, n in ecarts_jours.items() if 0 <= n <= 90}
    blocs = sorted({publication[q] for q, n in ecarts_jours.items() if n > 90})
    delai_max = max(delais.values())
    dire(f"mise en ligne des jeux de données (en-tête Last-Modified) : {publication}")
    dire(f"remises en ligne (plus de 90 jours après la fin du trimestre) : {blocs} · délais des 1res mises en ligne "
         f"mesurées (jours après la fin du trimestre) : {delais} · le plus long : {delai_max}")
    classements, dispo = {}, {}
    for y in ANNEES_CLASSEMENT:
        annees = list(range(y - inities.ANNEES_D_HISTORIQUE, y))
        lignes = [tuple(t) for q in TRIMESTRES if int(q[:4]) in annees for t in routine[q] if t[3] in annees]
        classements[str(y)] = {**inities.classer(lignes, annees), "transactions": len(lignes)}
        q4 = f"{y - 1}q4"
        d4 = publication.get(q4)
        dispo[str(y)] = d4 if q4 in delais else (fin_trimestre(q4) + timedelta(days=delai_max)).isoformat()
        dire(f"classement des routiniers pour {y} (transactions de {annees[0]} à {annees[-1]}) : "
             f"{classements[str(y)]['compte']} · utilisable à partir du {dispo[str(y)]}")
    del routine

    # --- Formulaires 4 au-dessus des seuils du robot ---
    fenetre = [(acc, d) for acc, d in depots.items() if PREMIER_DEPOT.isoformat() <= d["depose"] <= FIN.isoformat()]

    def au_dessus(d):
        for code, seuil in (("P", sec.SEUIL_ACHAT), ("S", sec.SEUIL_VENTE)):
            v = sum((sec.nombre(l[3]) or 0) * (sec.nombre(l[4]) or 0) for l in d["lignes"] if l[1] == code)
            if v >= seuil:
                return True
        return False

    candidats = [(acc, d) for acc, d in fenetre if au_dessus(d)]
    dire(f"formulaires 4 déposés du {PREMIER_DEPOT} au {FIN} avec achat ou vente : {len(fenetre):,} · au-dessus des "
         f"seuils du robot (achats 25 000 $, ventes 1 M$) : {len(candidats):,}")

    # --- 13D originaux ---
    def index_13d():
        sortie = []
        for q in TRIMESTRES_EVENEMENTS:
            an, tr = int(q[:4]), int(q[5])
            texte = brut(f"{sec.ARCHIVES}/edgar/full-index/{an}/QTR{tr}/master.idx").decode("latin-1")
            for d in sec.lire_index(texte).values():
                if d.forme == "SCHEDULE 13D" and PREMIER_DEPOT.isoformat() <= d.depose <= FIN.isoformat():
                    sortie.append([d.acc, d.forme, d.depose, d.fichier, d.filers])
        return sortie

    liste_13d = garde(f"13d/index_{TRIMESTRES_EVENEMENTS[0]}_{TRIMESTRES_EVENEMENTS[-1]}.json.gz", index_13d)
    dire(f"13D originaux déposés du {PREMIER_DEPOT} au {FIN} (index EDGAR) : {len(liste_13d):,}")

    def texte_13d(acc, fichier):
        def faire():
            b = ou_rien(f"{sec.ARCHIVES}/{fichier}")
            if b in (None, "ERREUR"):
                return b
            t = b.decode("utf-8", "replace")
            fin = t.find("</SEC-HEADER>")
            m = re.search(r"<XML>\s*(.*?)\s*</XML>", t, re.S)
            return {"sha": hashlib.sha256(b).hexdigest(),
                    "texte": (t[:fin + 13] if fin > 0 else t[:20000]) + "\n<XML>\n" + (m.group(1) if m else "") + "\n</XML>\n"}
        return garde(f"13d/{acc}.json.gz", faire)

    lus_13d = []
    for i, (acc, forme, depose, fichier, filers) in enumerate(liste_13d):
        t = texte_13d(acc, fichier)
        if not isinstance(t, dict):
            compte["13D illisibles (téléchargement)"] += 1
            continue
        try:
            f = sec.lire_13dg(t["texte"])
        except Exception:  # noqa: BLE001 - le robot saute aussi un document illisible
            compte["13D illisibles (format)"] += 1
            continue
        lus_13d.append((acc, forme, depose, fichier, filers, t, f))
        if i % 500 == 0:
            dire(f"13D lus : {i:,}/{len(liste_13d):,}")

    # --- Fiches SEC des compagnies concernées ---
    ciks = sorted({d["cik"] for _, d in candidats} | {str(int(f["cik_emetteur"])) for *_, f in lus_13d
                                                       if (f["cik_emetteur"] or "").strip().isdigit()}, key=int)
    fiches = {}
    for i, cik in enumerate(ciks):
        f = fiche(cik)
        if isinstance(f, dict):
            fiches[cik] = f
        elif f == "ERREUR":
            compte["fiches SEC illisibles"] += 1
        if i % 1000 == 0:
            dire(f"fiches SEC : {i:,}/{len(ciks):,}")
    if compte["fiches SEC illisibles"] > 0.02 * len(ciks):
        raise SystemExit(f"trop de fiches SEC illisibles : {compte['fiches SEC illisibles']}")
    dire(f"fiches SEC lues : {len(fiches):,} sur {len(ciks):,} compagnies")

    cotes = Cotes(actuelle, declares, fiches)
    cotes.noms = noms

    # --- Les infos, par les lecteurs du robot ---
    evenements = []
    for acc, d in candidats:
        texte = xml_form4(acc, d)
        depot = sec.DepotSec(acc, "4", d["depose"], f"edgar/data/{int(d['cik'])}/{acc}.txt")
        try:
            evs = sec.evenements_form4(texte, hashlib.sha256(texte.encode()).hexdigest(), depot,
                                       cotes.au_jour(d["depose"], d["symbole"]))
        except Exception as exc:  # noqa: BLE001
            compte[f"formulaires 4 illisibles ({type(exc).__name__})"] += 1
            continue
        if not evs:
            compte["formulaires 4 de compagnies pas cotées à ce moment"] += 1
        for ev in evs:
            evenements.append(valider(ev, date.fromisoformat(ev.published_on)))
    for acc, forme, depose, fichier, filers, t, f in lus_13d:
        h = sec.entete(t["texte"])
        jour = sec.iso(h.get("depose")) or depose
        depot = sec.DepotSec(acc, forme, depose, fichier, [tuple(x) for x in filers])
        try:
            evs = sec.evenements_13dg(t["texte"], t["sha"], depot, cotes.au_jour(jour))
        except Exception as exc:  # noqa: BLE001
            compte[f"13D illisibles ({type(exc).__name__})"] += 1
            continue
        if not evs:
            compte["13D de compagnies pas cotées à ce moment"] += 1
        for ev in evs:
            evenements.append(valider(ev, date.fromisoformat(ev.published_on)))
    evenements = [e.to_dict() for e in evenements]
    badges = Counter((e["source"], e["kind"], e["badge"]) for e in evenements)
    dire(f"infos créées par les lecteurs du robot : {len(evenements):,} · {dict(sorted(badges.items()))}")
    # Contrôle de complétude : chaque mois de dépôt doit avoir des formulaires 4 (un trou = des données manquantes)
    par_mois_f4 = Counter(e["published_on"][:7] for e in evenements if e["source"] == "sec_form4")
    attendus, m = [], PREMIER_DEPOT
    while m <= FIN:
        attendus.append(m.isoformat()[:7])
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    # Référence : un mois « normal » (75e centile), pas la médiane (des trimestres entiers vides la mettraient à 0)
    nombres = sorted(par_mois_f4.get(x, 0) for x in attendus)
    reference = nombres[(3 * len(nombres)) // 4]
    dire(f"formulaires 4 au-dessus des seuils, par mois de dépôt : {dict((x, par_mois_f4.get(x, 0)) for x in attendus)}")
    trous = [x for x in attendus if par_mois_f4.get(x, 0) == 0 or par_mois_f4.get(x, 0) < 0.3 * reference]
    if trous and os.environ.get("REJEU_ESSAI_HORS_LIGNE") != "1":  # fausses données de l'essai hors ligne : peu d'infos
        raise SystemExit(f"TROU dans les données : mois avec moins de 30 % d'un mois normal ({reference}) : {trous}")
    rates = Counter(c for e in evenements if e["badge"] == "a_verifier" for c, ok in e["checks"].items() if not ok)
    dire(f"contrôles ratés (infos « à vérifier », 0 point) : {dict(rates.most_common())}")
    bons = sorted((e for e in evenements if e["badge"] in ("officiel", "confirme")), key=lambda e: (e["published_on"], e["id"]))
    compte["infos de compagnies retirées de la bourse depuis (comptent)"] = sum(
        str(e["data"].get("bourse", "")).startswith("retirée") for e in bons)

    # --- Symbole -> CIK (pour fonds, taille) ---
    cik_de = {}
    for e in bons:
        cik_de.setdefault(e["tickers"][0], str(int(str(e["data"]["cik_emetteur"]).strip())))

    # --- Faits XBRL (actions en circulation) des compagnies avec un achat de dirigeant ---
    achats_ciks = sorted({cik_de[e["tickers"][0]] for e in bons if e["kind"] == "achat_initie"}, key=int)
    faits_de = {}
    for i, cik in enumerate(achats_ciks):
        formes = {f for _, f in (fiches.get(cik) or {}).get("formes", [])}
        if not formes & taille.AMERICAINS:
            continue
        x = faits(cik)
        if x == "ERREUR":
            compte["faits XBRL illisibles"] += 1
            continue
        faits_de[cik] = sorted(({"end": a, "val": v, "filed": f} for a, v, f in x if a and f), key=lambda f: f["filed"])
        if i % 1000 == 0:
            dire(f"faits XBRL : {i:,}/{len(achats_ciks):,}")
    dire(f"actions en circulation (companyconcept) : {len(faits_de):,} compagnies américaines avec un achat")

    # --- Prix officiels de la SEC (échecs de livraison) ---
    liens_ftd = prix_sec.fichiers_de_la_page(brut(prix_sec.PAGE, "pages/ftd.html").decode("utf-8", "replace"))
    cles = sorted(c for c in liens_ftd if mois_avant(PREMIER_DEPOT, 12).strftime("%Y%m") + "a" <= c <= "202609a")
    voulus = {e["tickers"][0] for e in bons} | set(prix_sec.MARCHE)
    prix, calendrier, derniers = defaultdict(dict), set(), {}
    exacts = set()
    for c in cles:
        contenu = brut(liens_ftd[c], f"ftd/{c}.zip")
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            lignes = z.read(z.namelist()[0]).decode("latin-1").splitlines()
        if not lignes or lignes[0].strip() != prix_sec.ENTETE:
            raise SystemExit(f"en-tête inattendu dans {c}")
        dernier = {}
        for l in lignes[1:]:
            p = l.split("|")
            if len(p) != 6 or not re.fullmatch(r"\d{8}", p[0]):
                continue
            calendrier.add(p[0])
            brut_s = p[2].strip()
            s = sec.normaliser_symbole(brut_s).replace("/", "-")
            if s in voulus and re.fullmatch(r"\d+(?:\.\d+)?", p[5].strip()):
                prix[s][p[0]] = [float(p[5]), p[1].strip()]
                if brut_s == s:
                    exacts.add(s)
                if s not in dernier or p[0] >= dernier[s][0]:
                    dernier[s] = [p[0], float(p[5])]
        derniers[c] = dernier
    calendrier = sorted(calendrier)
    couvert = max(prix_sec.periode(c)[1] for c in cles)
    dire(f"fichiers d'échecs de livraison : {len(cles)} ({cles[0]} … {cles[-1]}) · prix jusqu'au {couvert} · "
         f"{len(prix):,} symboles avec au moins un prix sur {len(voulus):,} · trouvés seulement après avoir changé "
         f"« . » ou « / » en « - » : {len(set(prix) - exacts)}")
    publication_ftd = {c: prix_sec.mise_en_ligne_prevue(prix_sec.periode(c)[1]) for c in cles}

    # --- Seuils du NYSE (Kenneth French) ---
    seuils = seuils_tous(brut(taille.SEUILS, "french/ME_Breakpoints_CSV.zip"))
    dire(f"seuils du NYSE : {len(seuils)} mois, du {min(seuils)} au {max(seuils)}")

    def seuils_au(jour):
        a, m = jour.year, jour.month - 2
        if m <= 0:
            a, m = a - 1, m + 12
        cle = f"{a}{m:02d}"
        ok = [k for k in seuils if k <= cle]
        return seuils[max(ok)] if ok else None

    # --- État de chaque compagnie à une date (fonds, rapports, actions, prix) ---
    premiere = {}
    for cik, f in fiches.items():
        p = {}
        for d, forme in f.get("formes", []):
            if forme.split("/")[0] in emetteurs.RAPPORTS | emetteurs.FORMULAIRES_FONDS and (forme not in p or d < p[forme]):
                p[forme] = d
        premiere[cik] = p

    def fiche_au(cik, jour):
        j = jour.isoformat()
        formes = [f for f, d in premiere.get(cik, {}).items() if d <= j]
        return {"cik": int(cik), "rapports": sorted({f.split("/")[0] for f in formes} & emetteurs.RAPPORTS),
                "formulaires_fonds": sorted({f for f in formes if f.split("/")[0] in emetteurs.FORMULAIRES_FONDS})}

    def actions_au(cik, jour):
        j = jour.isoformat()
        return taille.fait_recent([f for f in faits_de.get(cik, []) if f["filed"] <= j])

    def prix_taille_au(symbole, publies):
        trouves = [derniers[c][symbole] for c in publies if symbole in derniers[c]]
        return max(trouves, default=None)

    # --- Le rejeu, jour par jour ---
    jours = [RODAGE + timedelta(days=i) for i in range((FIN - RODAGE).days + 1)]
    jours = [j for j in jours if j.weekday() < 5]
    publies = [e["published_on"] for e in bons]
    historique = {"entrees": []}
    precedent = None
    listes = {}
    instantanes = {}
    t_jour = time.time()
    for n, jour in enumerate(jours):
        maintenant = datetime.combine(jour, HEURE, tzinfo=TORONTO)
        a, m = jour.year, jour.month - 2
        if m <= 0:
            a, m = a - 1, m + 12
        debut = f"{a}-{m:02d}-01"
        visibles = bons[bisect_left(publies, debut):bisect_right(publies, jour.isoformat())]
        symboles_vus = {e["tickers"][0] for e in visibles}
        fonds = {s for s in symboles_vus if fiche_au(cik_de[s], jour)["formulaires_fonds"]}
        annees = {y: c for y, c in classements.items() if dispo[y] and dispo[y] <= jour.isoformat()
                  and int(y) >= jour.year - 1}
        routiniers = {"version": inities.VERSION, "annees": annees}
        s_jour = seuils_au(jour)
        achats = {e["tickers"][0] for e in visibles if e["kind"] == "achat_initie"}
        fichiers_publies = [c for c in cles if publication_ftd[c] <= jour][-taille.FICHIERS_PRIX:]
        etat_taille = {"seuils": s_jour, "actions": {},
                       "actions_concept": {cik_de[s]: actions_au(cik_de[s], jour) for s in achats},
                       "prix": {s: prix_taille_au(s, fichiers_publies) for s in achats}}
        etat_taille["actions_concept"] = {k: v for k, v in etat_taille["actions_concept"].items() if v}
        etat_taille["prix"] = {k: v for k, v in etat_taille["prix"].items() if v}
        tailles = {s: taille.classer(fiche_au(cik_de[s], jour), etat_taille, s, jour) for s in achats}
        res = score.calculer(visibles, maintenant, precedent, None, fonds=fonds, chefs=frozenset(),
                             routiniers=routiniers, tailles=tailles)
        nouvelles = resultats.noter_entrees(historique, res, maintenant)
        if nouvelles:
            lignes_score = {r["symbole"]: r for r in res["hausse"]}
            for e in nouvelles:
                r = lignes_score.get(e["symbole"])
                if e["sens"] == "hausse" and r:
                    e["infos"] = [[i["id"], i["regle"], i["compte"]] for g in r["groupes"] for i in g["infos"]]
                    e["valeur_m"] = (r.get("taille") or {}).get("valeur_m")
        listes[jour.isoformat()] = {
            "hausse": [[r["symbole"], r["note10"], (r.get("taille") or {}).get("taille")] for r in res["hausse"]],
            "baisse": [[r["symbole"], r["note10"]] for r in res["baisse"]],
            "nouvelles": [[e["symbole"], e["sens"]] for e in nouvelles], "infos": len(visibles),
            "notees": res["compagnies_notees"]}
        if jour in JOURS_VERIF:
            instantanes[jour.isoformat()] = (res, visibles, routiniers, etat_taille,
                                             {s: fiche_au(cik_de[s], jour) for s in symboles_vus})
        precedent = {"version": res["version"], "hausse": res["hausse"], "baisse": res["baisse"]}
        if n % 20 == 0:
            dire(f"jour {jour} : {len(visibles):,} infos vues · {res['compagnies_notees']} compagnies notées · "
                 f"hausse {len(res['hausse'])} · baisse {len(res['baisse'])} · "
                 f"{(time.time() - t_jour) / (n + 1):.1f} s par jour")

    # --- Photos pour le recalcul indépendant (labo/recalcul_score.py) ---
    for j, (res, visibles, routiniers, etat_taille, fiches_j) in instantanes.items():
        racine = TRAVAIL / "instantanes" / j
        (racine / "app").mkdir(parents=True, exist_ok=True)
        (racine / "app" / "aujourdhui.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        par_mois = defaultdict(list)
        for e in visibles:
            par_mois[e["published_on"][:7]].append(e)
        (racine / "evenements").mkdir(parents=True, exist_ok=True)
        for mois, evs in par_mois.items():
            (racine / "evenements" / f"{mois}.jsonl").write_text(
                "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs), encoding="utf-8")
        (racine / "sec").mkdir(parents=True, exist_ok=True)
        (racine / "sec" / "inities_routiniers.json").write_text(json.dumps(routiniers), encoding="utf-8")
        (racine / "sec" / "emetteurs.json").write_text(json.dumps(fiches_j), encoding="utf-8")
        (racine / "prix").mkdir(parents=True, exist_ok=True)
        (racine / "prix" / "taille.json").write_text(json.dumps(etat_taille), encoding="utf-8")

    # --- Les nouvelles entrées « hausse » de la période, et leurs prix (pour strategies.py) ---
    entrees = []
    for e in sorted(historique["entrees"], key=lambda x: (x["entree"], x["symbole"])):
        j = datetime.fromisoformat(e["entree"]).astimezone(TORONTO).date()
        if e["sens"] == "hausse" and DEBUT <= j <= FIN:
            entrees.append({**e, "jour": j.isoformat(), "mois": j.isoformat()[:7]})
    (SORTIE / "entrees.json").write_text(json.dumps(entrees, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    debut_prix = mois_avant(PREMIER_DEPOT, 12).strftime("%Y%m%d")  # un an avant : pour facteurs.py
    garder = {e["symbole"] for e in entrees} | set(prix_sec.MARCHE)
    (TRAVAIL / "prix.json").write_text(json.dumps({
        "calendrier": [j for j in calendrier if j >= debut_prix], "couvert": couvert,
        "prix": {s: {j: v for j, v in prix.get(s, {}).items() if j >= debut_prix} for s in sorted(garder)}},
        separators=(",", ":")), encoding="utf-8")
    (TRAVAIL / "ftd.json").write_text(json.dumps({"cles": cles, "liens": {c: liens_ftd[c] for c in cles}}),
                                      encoding="utf-8")
    (TRAVAIL / "evenements.json").write_text(json.dumps(bons, ensure_ascii=False), encoding="utf-8")
    (SORTIE / "listes.json").write_text(json.dumps(listes, ensure_ascii=False, separators=(",", ":")) + "\n",
                                        encoding="utf-8")
    par_mois = Counter(e["mois"] for e in entrees)
    dire(f"nouvelles entrées « hausse » du {DEBUT} au {FIN} : {len(entrees)} · par mois : {dict(sorted(par_mois.items()))}")
    if not ARGENT:
        dire("rejeu fini · entrées et prix écrits (l'argent est calculé par strategies.py)")
        return

    # --- Les positions : chaque nouvelle entrée « hausse » de la période ---
    marche = {f: prix.get(f, {}) for f in prix_sec.MARCHE}

    def marche_entre(d1, d2):
        for f in prix_sec.MARCHE:
            if d1 in marche[f] and d2 in marche[f]:
                return f, round(marche[f][d2][0] / marche[f][d1][0] - 1, 4)
        spy = sorted(marche["SPY"])
        a = [x for x in spy if plus_jours(d1, -5) <= x <= d1]
        b = [x for x in spy if plus_jours(d2, -5) <= x <= d2]
        if a and b:
            compte["marché : SPY d'un jour proche (pas de prix ce jour-là)"] += 1
            return "SPY~", round(marche["SPY"][b[-1]][0] / marche["SPY"][a[-1]][0] - 1, 4)
        return None, None

    def secours(d, p):
        """Pas de prix à l'arrivée : 1re date suivante avec un prix (jusqu'à 90 jours), sinon la dernière avant."""
        cible, limite = plus_jours(d["date"], 30), plus_jours(d["date"], 30 + resultats.TOLERANCE_ARRIVEE)
        apres = [j for j in calendrier if limite < j <= plus_jours(d["date"], SORTIE_MAX_JOURS) and j in p]
        avant = [j for j in calendrier if d["date"] < j < cible and j in p]
        if apres:
            j, genre = apres[0], "vendue plus tard (pas de prix le 30e jour)"
        elif avant:
            j, genre = avant[-1], "vendue plus tôt (plus aucun prix après)"
        else:
            return None
        a, b = p[d["date"]], p[j]
        r = {"date": j, "prix": b[0], "variation": round(b[0] / a[0] - 1, 4), "genre": genre}
        if a[1] != b[1]:
            return {**r, "statut": "pas_comparable"}
        suite = [p[x][0] for x in calendrier if d["date"] <= x <= j and x in p]
        saut = max((max(x / y, y / x) for x, y in zip(suite, suite[1:])), default=1)
        hors = saut > resultats.SAUT_MAX or not resultats.VARIATION_MIN <= r["variation"] <= resultats.VARIATION_MAX
        return {**r, "statut": "a_verifier" if hors else "mesure"}

    def depart_large(e, p):
        """Variante : le 1er prix de la SEC parmi les 10 dates de règlement après la 1re (au lieu de 3)."""
        jour = resultats.jour_toronto(e["entree"])
        for j in [x for x in calendrier if x > jour][1:11]:
            if j in p:
                return {"statut": "ok", "date": j, "prix": p[j][0], "cusip": p[j][1]}
        return {"statut": "pas_de_prix"}

    def faire_positions(depart):
        positions = []
        for e in sorted(historique["entrees"], key=lambda x: (x["entree"], x["symbole"])):
            if e["sens"] != "hausse":
                continue
            j = datetime.fromisoformat(e["entree"]).astimezone(TORONTO).date()
            if not DEBUT <= j <= FIN:
                continue
            p = prix.get(e["symbole"], {})
            d = depart(e, p)
            pos = {"symbole": e["symbole"], "nom": e["nom"], "entree": e["entree"], "jour": j.isoformat(),
                   "mois": j.isoformat()[:7], "note10": e["note10"], "signaux": e.get("signaux"),
                   "taille": e.get("taille"), "depart": d}
            if d["statut"] != "ok":
                pos.update(achetee=False, pourquoi="pas de prix officiel de la SEC au départ : pas acheté")
                positions.append(pos)
                continue
            m = resultats.mesurer(e, d, p, marche, calendrier, couvert, 30)
            pos["arrivee_robot"] = m
            if m["statut"] == "pas_de_prix":
                s = secours(d, p)
                if s is None:
                    pos.update(achetee=True, statut="aucun_prix_apres", rendement=0.0, rendement_pire=-1.0,
                               sortie=None, pourquoi="aucun prix après l'achat (0 % ; pire cas −100 %)")
                else:
                    pos.update(achetee=True, statut=s["statut"], sortie=s["date"], prix_sortie=s["prix"],
                               variation=s["variation"], pourquoi=s["genre"],
                               rendement=0.0 if s["statut"] == "pas_comparable" else s["variation"])
            elif m["statut"] == "en_attente":
                raise SystemExit(f"prix pas encore publiés pour {e['symbole']} ({m})")
            else:
                pos.update(achetee=True, statut=m["statut"], sortie=m["date"], prix_sortie=m["prix"],
                           variation=m["variation"], rendement=0.0 if m["statut"] == "pas_comparable" else m["variation"],
                           pourquoi=m.get("pourquoi"))
            pos["prix_achat"] = d["prix"]
            if pos.get("sortie"):
                f, r = marche_entre(d["date"], pos["sortie"])
                pos.update(fonds_marche=f, marche=r)
            else:
                pos.update(fonds_marche=None, marche=None)
            pos.setdefault("rendement_pire", pos["rendement"])
            pos["rendement_sans_sauts"] = 0.0 if pos["statut"] == "a_verifier" else pos["rendement"]
            if pos.get("sortie"):
                pos["jours_tenus"] = (datetime.strptime(pos["sortie"], "%Y%m%d") - datetime.strptime(d["date"], "%Y%m%d")).days
            positions.append(pos)
        return positions

    positions = faire_positions(lambda e, p: resultats.depart(e, p, calendrier, couvert))
    positions_large = faire_positions(depart_large)

    # --- L'argent ---
    mois = []
    m = DEBUT
    while m <= FIN:
        mois.append(m.isoformat()[:7])
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    achetees = [p for p in positions if p["achetee"]]
    sans_marche = [p for p in achetees if p["marche"] is None]
    if sans_marche:
        dire(f"ATTENTION : {len(sans_marche)} positions sans prix du marché aux mêmes dates : "
             f"{[p['symbole'] for p in sans_marche]}")

    def valeur_position(alloc, r, frais):
        return max(0.0, (alloc - frais) * (1 + r) - frais) if frais else alloc * (1 + r)

    def portefeuille(cle, frais=0.0, achetees=achetees):
        etale, reinvesti, chemin = 0.0, 0.0, []
        for mo in mois:
            ps = [p for p in achetees if p["mois"] == mo and p[cle] is not None]
            reinvesti += MENSUEL
            if ps:
                etale += sum(valeur_position(MENSUEL / len(ps), p[cle], frais) for p in ps)
                reinvesti = sum(valeur_position(reinvesti / len(ps), p[cle], frais) for p in ps)
            else:
                etale += MENSUEL
            chemin.append(round(reinvesti, 2))
        return round(etale, 2), round(reinvesti, 2), chemin

    versions = {
        "Radar": portefeuille("rendement"),
        "Radar, frais de 10 $ par transaction": portefeuille("rendement", FRAIS),
        "Radar, sauts anormaux à 0 %": portefeuille("rendement_sans_sauts"),
        "Radar, pire cas (sans prix après l'achat = −100 %)": portefeuille("rendement_pire"),
        "S&P 500 (SPY) aux mêmes dates": portefeuille("marche"),
        "Variante : achat jusqu'à 10 jours de bourse plus tard": portefeuille(
            "rendement", achetees=[p for p in positions_large if p["achetee"]]),
        "Variante : S&P 500 aux mêmes dates que la variante": portefeuille(
            "marche", achetees=[p for p in positions_large if p["achetee"]]),
    }
    # S&P 500 acheté chaque mois et gardé jusqu'à la dernière vente de Radar
    fin_tout = max([p["sortie"] for p in achetees if p.get("sortie")] + [plus_jours(compact(FIN), 30)])
    spy = marche["SPY"]
    jours_spy = sorted(spy)
    prix_fin = spy[max(x for x in jours_spy if x <= fin_tout)][0]
    garde_spy, chemin_spy = 0.0, []
    parts = 0.0
    for mo in mois:
        premier = next(x for x in jours_spy if x >= mo.replace("-", "") + "01")
        parts += MENSUEL / spy[premier][0]
        chemin_spy.append(premier)
    garde_spy = round(parts * prix_fin, 2)

    def detail_mois(mo):
        ps = [p for p in positions if p["mois"] == mo]
        a = [p for p in ps if p["achetee"]]
        return {"mois": mo, "entrees": len(ps), "achetees": len(a), "pas_de_prix": len(ps) - len(a),
                "rendement_moyen": round(mean(p["rendement"] for p in a), 4) if a else None,
                "marche_moyen": round(mean(p["marche"] for p in a if p["marche"] is not None), 4)
                if any(p["marche"] is not None for p in a) else None,
                "gagnantes": sum(p["rendement"] > 0 for p in a),
                "battent_le_marche": sum(p["marche"] is not None and p["rendement"] > p["marche"] for p in a),
                "symboles": [p["symbole"] for p in ps]}

    mensuel = [detail_mois(mo) for mo in mois]
    rendements = [p["rendement"] for p in achetees]
    meilleure = max(achetees, key=lambda p: p["rendement"], default=None)
    pire = min(achetees, key=lambda p: p["rendement"], default=None)
    chemin = versions["Radar"][2]
    investi = [MENSUEL * (i + 1) for i in range(len(mois))]
    def pire_baisse(cle):
        indice, sommet, baisse = 1.0, 1.0, 0.0
        for x in mensuel:
            indice *= 1 + (x[cle] or 0)
            sommet = max(sommet, indice)
            baisse = min(baisse, indice / sommet - 1)
        return round(baisse, 4)

    baisse_max, baisse_max_spy = pire_baisse("rendement_moyen"), pire_baisse("marche_moyen")
    avec = [x for x in mensuel if x["rendement_moyen"] is not None]
    pire_mois = min(avec, key=lambda x: x["rendement_moyen"]) if avec else None
    tenus = sorted(p["jours_tenus"] for p in achetees if p.get("jours_tenus") is not None)
    large = [p for p in positions_large if p["achetee"]]

    bilan = {
        "periode": [DEBUT.isoformat(), FIN.isoformat()], "derniere_vente": fin_tout,
        "versions": {k: {"etale": v[0], "reinvesti": v[1], "chemin_reinvesti": v[2]} for k, v in versions.items()},
        "spy_garde": {"valeur": garde_spy, "achats": chemin_spy, "vente": fin_tout},
        "investi_par_mois": investi, "mois": mois,
        "positions": len(positions), "achetees": len(achetees),
        "pas_achetees": len(positions) - len(achetees),
        "gagnantes": sum(r > 0 for r in rendements),
        "battent_le_marche": sum(p["marche"] is not None and p["rendement"] > p["marche"] for p in achetees),
        "rendement_moyen": round(mean(rendements), 4) if rendements else None,
        "marche_moyen": round(mean(p["marche"] for p in achetees if p["marche"] is not None), 4) if achetees else None,
        "meilleure": meilleure and {k: meilleure[k] for k in ("symbole", "nom", "jour", "rendement", "marche")},
        "pire": pire and {k: pire[k] for k in ("symbole", "nom", "jour", "rendement", "marche")},
        "pire_baisse_indice": baisse_max, "pire_baisse_indice_spy": baisse_max_spy,
        "pire_mois": pire_mois and {k: pire_mois[k] for k in ("mois", "rendement_moyen", "marche_moyen")},
        "jours_tenus": {"mediane": tenus[len(tenus) // 2] if tenus else None, "max": max(tenus, default=None),
                        "plus_de_33": sum(t > 33 for t in tenus)},
        "variante_large": {"positions": len(positions_large), "achetees": len(large)},
        "dispo_classements": dispo, "publication_jeux": publication, "remises_en_ligne": blocs, "delais": delais,
        "statuts": dict(Counter(p.get("statut", "pas_achetee") for p in positions)),
        "compteurs": dict(compte),
    }
    (SORTIE / "positions.json").write_text(json.dumps(positions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (SORTIE / "positions_variante.json").write_text(json.dumps(positions_large, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")
    (SORTIE / "mensuel.json").write_text(json.dumps({"bilan": bilan, "mois": mensuel}, ensure_ascii=False, indent=1)
                                         + "\n", encoding="utf-8")
    (SORTIE / "listes.json").write_text(json.dumps(listes, ensure_ascii=False, separators=(",", ":")) + "\n",
                                        encoding="utf-8")
    (TRAVAIL / "evenements.json").write_text(json.dumps([e for e in bons], ensure_ascii=False), encoding="utf-8")
    (TRAVAIL / "ftd.json").write_text(json.dumps({"cles": cles, "liens": {c: liens_ftd[c] for c in cles}}),
                                      encoding="utf-8")

    # --- Le résumé ---
    def argent(x):
        return f"{x:,.0f} $".replace(",", " ")

    def pc(x):
        return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",")

    l = ["# Rejeu d'un an de Radar : 10 000 $ de juillet 2025 à juin 2026", "",
         f"Règles : le robot actuel ({score.VERSION}), appelé tel quel. Rodage du {RODAGE} au {DEBUT - timedelta(days=1)}.",
         f"Dernière vente : {resultats.iso(fin_tout)}. Montants en dollars américains, sans impôt ni change.", "",
         "## Résultat", "", "| Version | Étalé (833 $ par mois, pas réinvesti) | Réinvesti chaque mois |", "|---|---|---|"]
    for k, v in versions.items():
        l.append(f"| {k} | {argent(v[0])} ({pc(v[0] / 10_000 - 1)}) | {argent(v[1])} ({pc(v[1] / 10_000 - 1)}) |")
    l.append(f"| S&P 500 (SPY) acheté chaque mois et gardé jusqu'au {resultats.iso(fin_tout)} | {argent(garde_spy)} "
             f"({pc(garde_spy / 10_000 - 1)}) | — |")
    l += ["", "## Les positions", "",
          f"- Nouvelles entrées « hausse » : {len(positions)} · achetées : {len(achetees)} · pas de prix au départ : "
          f"{len(positions) - len(achetees)}",
          f"- Gagnantes : {bilan['gagnantes']} sur {len(achetees)} · font mieux que le S&P 500 aux mêmes dates : "
          f"{bilan['battent_le_marche']}",
          f"- Rendement moyen en 1 mois : {pc(bilan['rendement_moyen'])} · S&P 500 aux mêmes dates : "
          f"{pc(bilan['marche_moyen'])}",
          f"- Meilleure : {meilleure and meilleure['symbole']} {pc(meilleure and meilleure['rendement'])} · pire : "
          f"{pire and pire['symbole']} {pc(pire and pire['rendement'])}",
          f"- Pire baisse (rendement mis bout à bout, d'un sommet mensuel au creux suivant) : Radar {pc(baisse_max)} · "
          f"S&P 500 mêmes dates {pc(baisse_max_spy)} · pire mois : {pire_mois and pire_mois['mois']} "
          f"{pc(pire_mois and pire_mois['rendement_moyen'])}",
          f"- Durée réelle des positions : médiane {bilan['jours_tenus']['mediane']} jours · max {bilan['jours_tenus']['max']} · "
          f"vendues après le 33e jour faute de prix : {bilan['jours_tenus']['plus_de_33']}",
          f"- Variante achat jusqu'à 10 jours de bourse plus tard : {len(large)} achetées sur {len(positions_large)}",
          f"- Routiniers : classement {', '.join(f'{y} dès le {d}' for y, d in dispo.items())} (fichier du 4e trimestre remis en "
          f"ligne plus tard : fin du trimestre + {delai_max} jours, le plus long délai mesuré d'une 1re mise en ligne)",
          f"- Statuts : {bilan['statuts']}", "", "## Mois par mois", "",
          "| Mois | Entrées | Achetées | Rendement moyen | S&P 500 mêmes dates | Gagnantes | Mieux que le S&P | "
          "Réinvesti (fin du mois) |", "|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(mensuel):
        l.append(f"| {x['mois']} | {x['entrees']} | {x['achetees']} | {pc(x['rendement_moyen'])} | "
                 f"{pc(x['marche_moyen'])} | {x['gagnantes']} | {x['battent_le_marche']} | {argent(chemin[i])} |")
    l += ["", "## Compteurs", ""] + [f"- {k} : {v}" for k, v in sorted(compte.items())]
    l += ["", "VERDICT : rejeu fait"]
    (SORTIE / "resume.md").write_text("\n".join(l) + "\n", encoding="utf-8")
    dire("rejeu fini · voir resume.md")


if __name__ == "__main__":
    main()
