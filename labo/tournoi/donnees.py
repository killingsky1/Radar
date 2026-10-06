"""Tournoi Radar, étape 0 : le jeu de recherche, tiré de sources officielles gratuites de la SEC. Rien du futur.

- Événements : chaque formulaire 4 ORIGINAL (les 4/A sont laissés de côté) avec au moins un achat en bourse (code P,
  actions acquises) ou une vente en bourse (code S, actions cédées) de titres non dérivés, déposé du 1er janvier 2016 au
  30 juin 2026, d'après les jeux de données trimestriels de la SEC (« insider transactions data sets »). Compagnies
  disparues incluses : le symbole est celui écrit dans le formulaire au moment du dépôt.
- Prix : clôtures des fichiers d'échecs de livraison de la SEC. Pour une date de règlement, la SEC donne la clôture du
  jour ouvrable d'avant : la date de clôture gardée ici est la date de règlement précédente du calendrier des fichiers
  (peut être décalée d'un jour autour des congés des banques où la bourse est ouverte). Un titre a un prix seulement les
  jours où il a des échecs de livraison.
- Faits XBRL : le fichier complet de la SEC (companyfacts.zip, une seule requête), avec la date de DÉPÔT de chaque
  chiffre. Valeur en bourse : actions en circulation (le fait DÉPOSÉ le plus récent avant le dépôt du formulaire 4) ×
  dernière clôture de la SEC dans les 30 jours avant le dépôt. Finances (10-K et 10-Q) : pour chaque période, la
  PREMIÈRE version déposée, utilisable à partir de sa date de dépôt (pas les chiffres corrigés plus tard).
- 13D et 13G : index trimestriels officiels d'EDGAR ; une compagnie « visée » = un CIK du dépôt qui est aussi une
  compagnie des formulaires 4 (un déposant qui est lui-même une compagnie cotée est donc compté aussi : rare).

- Historique de chaque initié : tous ses dépôts avec un achat ou une vente en bourse, toutes compagnies, depuis le plus
  ancien jeu de données offert par la SEC (2006 si disponible ; 2012 au moins).

Deux sorties séparées, dans le cache du labo (trop grosses pour la branche) :
- DÉCOUVERTE (formulaires 4 déposés du 1er juillet 2023 au 30 juin 2026) → cache/decouverte/ ; son résumé et le journal
  du calcul → labo/tournoi/donnees/ (branche labo) ;
- COFFRE-FORT (déposés du 1er janvier 2016 au 30 juin 2023) → cache/coffre/ (personne ne le voit avant l'examen final).
Lecture polie : le client du robot (5 requêtes par seconde au plus à la SEC, courriel dans l'en-tête comme la SEC le
demande) ; 401 ou 403 = arrêt, on ne contourne jamais un refus.
"""
import csv
import gzip
import io
import json
import math
import os
import re
import resource
import sys
import time
import zipfile
from array import array
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROBOT = Path(os.environ.get("TOURNOI_ROBOT", "principal/robot"))
sys.path.insert(0, str(ROBOT.resolve()))
from radar.collecteurs import inities, prix_sec, sec  # noqa: E402
from radar.http import ErreurSource  # noqa: E402

csv.field_size_limit(sys.maxsize)
CACHE = Path(os.environ.get("TOURNOI_CACHE", "cache"))
SORTIE = Path(os.environ.get("TOURNOI_SORTIE", "labo/tournoi/donnees"))
COFFRE = CACHE / "coffre"
DECOUVERTE_DOSSIER = CACHE / "decouverte"

DEBUT, DECOUVERTE, FIN = date(2016, 1, 1), date(2023, 7, 1), date(2026, 6, 30)
HISTOIRE_MIN = "2006q1"  # historique des initiés : depuis le plus ancien jeu de données offert, au plus tôt 2006
HISTOIRE = "2012q1"  # obligatoire : 3 ans avant 2016 pour les initiés routiniers (un trou ici = arrêt)
EVENEMENTS_DEPUIS = "2014-10-01"  # infos complètes (dictionnaires) : 90 jours avant le contexte du coffre-fort (2015)
PRIX_DEBUT = "201507a"  # fichiers d'échecs de livraison : 2e moitié de juin 2015 → prix dès juillet 2015
MARCHE = ("SPY", "IVV", "VOO", "IWM")
FORMES_13 = {"SC 13D": "13D", "SCHEDULE 13D": "13D", "SC 13D/A": "13D/A", "SCHEDULE 13D/A": "13D/A",
             "SC 13G": "13G", "SCHEDULE 13G": "13G", "SC 13G/A": "13G/A", "SCHEDULE 13G/A": "13G/A"}
FAITS_ZIP = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
CONCEPTS = ["Assets", "Liabilities", "StockholdersEquity", "AssetsCurrent", "LiabilitiesCurrent", "LongTermDebtNoncurrent",
            "NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities", "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "GrossProfit"]
# Actions en circulation (nombre d'actions, pas des $) : au bilan, à la fin de la période (us-gaap), et sur la page
# couverture du rapport, à une date proche du dépôt (dei). Demandées par critique-3, sante_valeur-1 et sante_valeur-4.
CONCEPTS_ACTIONS = [("us-gaap", "CommonStockSharesOutstanding"), ("dei", "EntityCommonStockSharesOutstanding")]
FORMES_FINANCES = {"10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A"}
HISTOIRE_FINANCES = 2 * 365 + 31  # finances gardées : périodes finies jusqu'à 2 ans (et 1 mois) avant le début
VIDES = {"NONE", "NA", "N-A", "NULL", "N", "TBD", ""}

compte = Counter()
journal = []
T0 = time.time()


def dire(t=""):
    memoire = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024  # Go (Linux : en Ko)
    t = f"[{(time.time() - T0) / 60:6.1f} min · {memoire:4.1f} Go] {t}" if t else t
    print(t, flush=True)
    journal.append(t)


# ---------- Lecture polie avec cache ----------

CLIENT = None


def client():
    global CLIENT
    if CLIENT is None:
        from radar.http import ClientPoli
        from radar.run import CONFIG, _charger_json
        CLIENT = ClientPoli(_charger_json(CONFIG).get("contact", ""))
    return CLIENT


def brut(url, nom=None):
    """Le contenu d'une adresse (gardé dans le cache si `nom`). 401 ou 403 : arrêt immédiat."""
    if nom and (CACHE / nom).exists():
        return (CACHE / nom).read_bytes()
    try:
        t = client().get(url)
    except ErreurSource as exc:
        if re.search(r"HTTP 40[13]\b", str(exc)):
            raise SystemExit(f"INTERDIT par le site, arrêt sans contourner : {exc}")
        raise
    compte["requêtes"] += 1
    if nom:
        (CACHE / nom).parent.mkdir(parents=True, exist_ok=True)
        (CACHE / nom).write_bytes(t.contenu)
    return t.contenu


def fichier(url, nom):
    """Un gros fichier gardé dans le cache : téléchargé une fois, puis lu sur le disque (pas en mémoire)."""
    if not (CACHE / nom).exists():
        brut(url, nom)
    return CACHE / nom


def ou_rien(url):
    """404 = None. Autre panne : « ERREUR » (pas gardé : relu au prochain passage)."""
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


# ---------- Outils ----------

def jour_ds(texte):
    j = inities._jour(texte)
    return j.isoformat() if j else ""


def nombre(t):
    try:
        x = float((t or "").replace(",", "").strip())
        return x if x == x else None  # NaN
    except ValueError:
        return None


def symbole(s):
    """Le symbole écrit dans le formulaire, au format des fichiers d'échecs (« BRK.B » → « BRK-B »), sinon None."""
    s = (s or "").strip().upper()
    s = re.split(r"[\s,;]+", s)[0] if s else ""
    s = s.replace(".", "-").replace("/", "-")
    return s if s not in VIDES and re.fullmatch(r"[A-Z][A-Z0-9-]{0,9}", s) else None


def iso(aaaammjj):
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:]}"


def jours(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def trimestres(depuis, jusqu_a):
    sortie, a, q = [], int(depuis[:4]), int(depuis[5])
    while f"{a}q{q}" <= jusqu_a:
        sortie.append(f"{a}q{q}")
        a, q = (a + 1, 1) if q == 4 else (a, q + 1)
    return sortie


# ---------- 1. Jeux de données des initiés : formulaires 4 originaux avec achat (P) ou vente (S) en bourse ----------

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


def lire_ds(contenu):
    """Un fichier trimestriel → {acc: {s: [dépôt, cik, symbole écrit, nom, 10b5-1], l: [lignes P/S], p: [déclarants]}}.
    Ligne : [n° de ligne, code, date, actions, prix, A/D, détenues après, D/I, titre du titre]."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        soumis = {}
        for r in table(z, "SUBMISSION"):
            depose, cik = jour_ds(r["FILING_DATE"]), r["ISSUERCIK"].strip()
            if r["DOCUMENT_TYPE"].strip() != "4" or not depose or not cik.isdigit():
                continue
            aff = (r.get("AFF10B5ONE") or "").strip().lower()
            soumis[r["ACCESSION_NUMBER"].strip()] = [depose, str(int(cik)), r["ISSUERTRADINGSYMBOL"].strip(),
                                                     r["ISSUERNAME"].strip(),
                                                     True if aff in ("1", "true") else False if aff in ("0", "false") else None]
        lignes = defaultdict(list)
        for r in table(z, "NONDERIV_TRANS"):
            acc, code = r["ACCESSION_NUMBER"].strip(), r["TRANS_CODE"].strip()
            if acc in soumis and code in ("P", "S"):
                lignes[acc].append([int(r["NONDERIV_TRANS_SK"] or 0), code, jour_ds(r["TRANS_DATE"]),
                                    nombre(r["TRANS_SHARES"]), nombre(r["TRANS_PRICEPERSHARE"]),
                                    r["TRANS_ACQUIRED_DISP_CD"].strip(), nombre(r["SHRS_OWND_FOLWNG_TRANS"]),
                                    r["DIRECT_INDIRECT_OWNERSHIP"].strip(), r["SECURITY_TITLE"].strip()[:60]])
        proprios = defaultdict(list)
        for r in table(z, "REPORTINGOWNER"):
            acc, cik = r["ACCESSION_NUMBER"].strip(), r["RPTOWNERCIK"].strip()
            if acc in lignes and cik.isdigit():
                proprios[acc].append([str(int(cik)), r["RPTOWNERNAME"].strip(), r["RPTOWNER_RELATIONSHIP"].strip(),
                                      r["RPTOWNER_TITLE"].strip()])
    return {acc: {"s": soumis[acc], "l": sorted(ls), "p": proprios[acc]} for acc, ls in lignes.items() if proprios[acc]}


ROLES = {"director": "administrateur", "officer": "dirigeant", "tenpercentowner": "actionnaire de 10 %", "other": "autre"}


def faire_evenements(depots):
    """Une info par formulaire et par sens : « achat » (P, acquises) et « vente » (S, cédées)."""
    sortie = []
    for acc, d in depots.items():
        depose, cik, ecrit, nom, aff = d["s"]
        for sens, code, ad in (("achat", "P", "A"), ("vente", "S", "D")):
            ls = [l for l in d["l"] if l[1] == code and l[5] == ad and l[3] and l[3] > 0]
            if not ls:
                continue
            actions = sum(l[3] for l in ls)
            avec_prix = [l for l in ls if l[4] and l[4] > 0]
            montant = sum(l[3] * l[4] for l in avec_prix)
            # Détenues avant : dans le groupe de lignes (direct ou indirect, même titre) le plus gros, « détenues
            # après » de sa dernière ligne moins (ou plus) ce groupe ; un résultat négatif = déclaration incohérente
            groupes = defaultdict(list)
            for l in ls:
                groupes[(l[7], l[8])].append(l)
            g = max(groupes.values(), key=lambda g: sum(x[3] for x in g))
            apres, somme = g[-1][6], sum(x[3] for x in g)
            avant = None if apres is None else (apres - somme if sens == "achat" else apres + somme)
            if avant is not None and avant < -0.5:
                avant = None
            dates = sorted(l[2] for l in ls if l[2])
            inities_ = [{"cik": p[0], "nom": p[1],
                         "roles": [ROLES.get(x.strip().lower(), x.strip().lower()) for x in p[2].split(",") if x.strip()],
                         "titre": p[3]} for p in d["p"]]
            sortie.append({
                "id": f"{acc}:{sens}", "sens": sens, "depot": depose, "jour_premier": dates[0] if dates else None,
                "jour_dernier": dates[-1] if dates else None, "cik": cik, "symbole": symbole(ecrit),
                "symbole_ecrit": ecrit, "nom": nom, "inities": inities_,
                "actions": round(actions, 4), "montant": round(montant, 2) if avec_prix else None,
                "prix_moyen": round(montant / sum(l[3] for l in avec_prix), 4) if avec_prix else None,
                "apres": apres, "avant": avant,
                "part": (round(somme / avant, 6) if avant and avant > 0.5 else None),
                "nouvelle_position": bool(sens == "achat" and avant is not None and abs(avant) <= 0.5),
                "direct": any(l[7] == "D" for l in ls), "plan_10b5_1": aff,
                "titres": sorted({l[8] for l in ls}), "lignes": len(ls)})
    return sortie


def lignes_historique(depots):
    """Historique des initiés : (initié, dépôt, cik, symbole, sens, jour_premier, jour_dernier, actions, prix_moyen), un par
    formulaire, par sens et par déclarant (mêmes lignes P ou S que les infos)."""
    for d in depots.values():
        depose, cik, ecrit, _nom, _aff = d["s"]
        for sens, code, ad in (("achat", "P", "A"), ("vente", "S", "D")):
            ls = [l for l in d["l"] if l[1] == code and l[5] == ad and l[3] and l[3] > 0]
            if not ls:
                continue
            dates = sorted(l[2] for l in ls if l[2])
            avec_prix = [l for l in ls if l[4] and l[4] > 0]
            prix_moyen = round(sum(l[3] * l[4] for l in avec_prix) / sum(l[3] for l in avec_prix), 4) if avec_prix else None
            for p in d["p"]:
                yield (p[0], depose, cik, symbole(ecrit), sens, dates[0] if dates else None, dates[-1] if dates else None,
                       round(sum(l[3] for l in ls), 4), prix_moyen)


def cle_historique(r):
    """Ordre de l'historique d'un initié : dépôt, compagnie, sens ; une case vide (symbole, date) passe avant le texte."""
    return (r[0], r[1], r[3], r[2] or "", r[4] or "", r[5] or "")


def trimestre_de(jour):
    return f"{jour[:4]}q{(int(jour[5:7]) - 1) // 3 + 1}"


def transactions_hist(depots):
    """(initié, compagnie, année, mois, dépôt) de chaque ligne P ou S, pour le classement des routiniers."""
    for d in depots.values():
        depose, cik = d["s"][0], d["s"][1]
        for l in d["l"]:
            if l[2]:
                for p in d["p"]:
                    yield p[0], cik, int(l[2][:4]), int(l[2][5:7]), depose


def ajouter_routiniers(evs, hist):
    """Routinier (règle de Radar, d'après Cohen, Malloy et Pomorski 2012) : l'initié a acheté ou vendu en bourse des
    actions de cette compagnie dans un même mois, chacune des 3 années civiles avant celle de l'info — d'après les
    seuls formulaires DÉPOSÉS avant celui de l'info."""
    par_paire = defaultdict(lambda: defaultdict(list))  # (initié, compagnie) → année → [(dépôt, mois)]
    for qui, cik, annee, mois, depose in hist:
        par_paire[(qui, cik)][annee].append((depose, mois))
    for ev in evs:
        an = int((ev["jour_premier"] or ev["depot"])[:4])
        trouves = {}
        for i in ev["inities"]:
            h = par_paire.get((i["cik"], ev["cik"]))
            if not h:
                continue
            mois = [{m for d, m in h.get(a, []) if d < ev["depot"]} for a in (an - 3, an - 2, an - 1)]
            communs = set.intersection(*mois) if all(mois) else set()
            if communs:
                trouves[i["cik"]] = sorted(communs)
        ev["routinier"] = bool(trouves)
        ev["mois_routine"] = sorted({m for x in trouves.values() for m in x})


def ajouter_contexte(evs, historiques):
    """Groupe, historique de l'initié et activité récente sur la compagnie (seulement ce qui était déposé avant)."""
    par_cie = defaultdict(list)
    for e in evs:
        par_cie[e["cik"]].append(e)
    for liste in par_cie.values():
        liste.sort(key=lambda e: (e["depot"], e["id"]))
    for cik, liste in par_cie.items():
        depots = [e["depot"] for e in liste]
        for e in liste:
            j = date.fromisoformat(e["depot"])
            d30, d90 = (j - timedelta(days=30)).isoformat(), (j - timedelta(days=90)).isoformat()
            fen30 = liste[bisect_left(depots, d30):bisect_right(depots, e["depot"])]
            avant90 = liste[bisect_left(depots, d90):bisect_left(depots, e["depot"])]
            if e["sens"] == "achat":
                e["groupe_30j"] = len({i["cik"] for x in fen30 if x["sens"] == "achat" for i in x["inities"]})
            e["achats_90j"] = sum(x["sens"] == "achat" for x in avant90)
            e["ventes_90j"] = sum(x["sens"] == "vente" for x in avant90)
    # Achats passés de l'initié : d'après son historique complet (depuis le plus ancien jeu de données), déposés AVANT
    depots_initie = {c: [r[0] for r in v if r[3] == "achat"] for c, v in historiques.items()}
    par_paire = defaultdict(list)  # (initié, compagnie) → dépôts de ses achats
    for c, v in historiques.items():
        for r in v:
            if r[3] == "achat":
                par_paire[(c, r[1])].append(r[0])
    for e in evs:
        if e["sens"] != "achat":
            continue
        meilleur = None
        for i in e["inities"]:
            n = bisect_left(depots_initie.get(i["cik"], []), e["depot"])
            meme = par_paire.get((i["cik"], e["cik"]), [])
            k = bisect_left(meme, e["depot"])
            r = {"cik": i["cik"], "achats_avant": n,
                 "jours_depuis_achat_meme_cie": jours(meme[k - 1], e["depot"]) if k else None}
            if meilleur is None or r["achats_avant"] > meilleur["achats_avant"]:
                meilleur = r
        e["historique"] = meilleur


# ---------- 2. Prix de la SEC (fichiers d'échecs de livraison) ----------

class Prix:
    """Clôtures par symbole : dates (AAAAMMJJ, date de clôture), prix, CUSIP, quantité d'échecs."""

    def __init__(self):
        self.d, self.p, self.q, self.c = defaultdict(lambda: array("i")), defaultdict(lambda: array("f")), \
            defaultdict(lambda: array("q")), defaultdict(list)
        self.calendrier = []

    def ajouter_fichier(self, lignes, voulus, cloture_de):
        n = 0
        for l in lignes:
            p = l.split("|")
            if len(p) != 6 or not re.fullmatch(r"\d{8}", p[0]) or p[0] not in cloture_de:
                continue
            s = symbole(sec.normaliser_symbole(p[2]))
            if s is None or (voulus is not None and s not in voulus) or not re.fullmatch(r"\d+(?:\.\d+)?", p[5].strip()):
                continue
            self.d[s].append(int(cloture_de[p[0]]))
            self.p[s].append(float(p[5]))
            self.q[s].append(int(p[3]) if p[3].strip().isdigit() else -1)
            self.c[s].append(sys.intern(p[1].strip()))
            n += 1
        return n

    def trier(self):
        for s in list(self.d):
            ordre = sorted(range(len(self.d[s])), key=lambda i: self.d[s][i])
            vus, garder = set(), []
            for i in ordre:  # une date de clôture : la 1re ligne lue (même titre dans 2 fichiers qui se chevauchent)
                if self.d[s][i] not in vus:
                    vus.add(self.d[s][i])
                    garder.append(i)
            self.d[s] = array("i", (self.d[s][i] for i in garder))
            self.p[s] = array("f", (self.p[s][i] for i in garder))
            self.q[s] = array("q", (self.q[s][i] for i in garder))
            self.c[s] = [self.c[s][i] for i in garder]

    def dernier(self, s, jour, tol):
        """La dernière clôture au plus tard le `jour` (AAAA-MM-JJ), à `tol` jours au plus : (date, prix, cusip)."""
        if s not in self.d:
            return None
        j = int(jour.replace("-", ""))
        i = bisect_right(self.d[s], j) - 1
        if i < 0:
            return None
        x = str(self.d[s][i])
        return (iso(x), float(self.p[s][i]), self.c[s][i]) if jours(iso(x), jour) <= tol else None

    def premier(self, s, jour, tol):
        """La 1re clôture au plus tôt le `jour`, à `tol` jours au plus."""
        if s not in self.d:
            return None
        j = int(jour.replace("-", ""))
        i = bisect_left(self.d[s], j)
        if i >= len(self.d[s]):
            return None
        x = str(self.d[s][i])
        return (iso(x), float(self.p[s][i]), self.c[s][i]) if jours(jour, iso(x)) <= tol else None

    def lignes(self, symboles, depuis):
        j = int(depuis.replace("-", ""))
        for s in sorted(symboles):
            if s not in self.d:
                continue
            i = bisect_left(self.d[s], j)
            if i < len(self.d[s]):
                yield {"s": s, "d": list(self.d[s][i:]), "p": [round(x, 4) for x in self.p[s][i:]],
                       "q": list(self.q[s][i:]), "c": self.c[s][i:]}


def calendrier_clotures(dates_reglement):
    """Dates de règlement de tous les fichiers → {date de règlement : date de clôture (la date de règlement d'avant)}."""
    toutes = sorted(dates_reglement)
    return {r: toutes[i - 1] for i, r in enumerate(toutes) if i > 0}


def lignes_ftd(contenu, cle):
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        lignes = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    if not lignes or lignes[0].strip() != prix_sec.ENTETE:
        raise SystemExit(f"en-tête inattendu dans le fichier d'échecs {cle}")
    return lignes[1:]


def ajouter_marche_et_valeur(evs, prix, faits_de):
    """Clôture de la veille et valeur en bourse au moment du dépôt."""
    for e in evs:
        s = e["symbole"]
        veille = prix.dernier(s, (date.fromisoformat(e["depot"]) - timedelta(days=1)).isoformat(), 30) if s else None
        e["cloture_avant"] = [veille[0], round(veille[1], 4), veille[2]] if veille else None
        faits = faits_de.get(e["cik"]) or []
        connus = [f for f in faits if f[2] and f[2] <= e["depot"] and f[0] and f[1]]
        actions = max(connus, key=lambda f: (f[2], f[0]))[1] if connus else None
        e["actions_circulation"] = actions
        e["valeur_m"] = round(actions * veille[1] / 1e6, 2) if actions and veille else None


def verifier_dates_prix(evs, prix, calendrier):
    """Les dates des prix de la SEC sont-elles les bonnes ? (vérification interne, sans autre site) Un achat en bourse fait
    en un seul jour doit être plus proche, en médiane, de la clôture de CE jour que de celle du jour de bourse d'avant ou
    d'après. Si les dates étaient décalées d'un jour, une règle rapide aurait l'air gagnante par erreur."""
    cal = [iso(str(x)) for x in calendrier]
    ecarts = {-1: [], 0: [], 1: []}
    for e in evs:
        if e["sens"] != "achat" or not e["symbole"] or not e.get("prix_moyen") or e["jour_premier"] != e["jour_dernier"]:
            continue
        k = bisect_left(cal, e["jour_premier"] or "")
        if not (0 < k < len(cal) - 1) or cal[k] != e["jour_premier"]:
            continue
        c = [prix.dernier(e["symbole"], cal[k + lag], 0) for lag in (-1, 0, 1)]
        if all(c) and all(x[1] > 0 for x in c):
            for lag, x in zip((-1, 0, 1), c):
                ecarts[lag].append(abs(math.log(e["prix_moyen"] / x[1])))
    med = {str(lag): round(sorted(v)[len(v) // 2], 5) for lag, v in ecarts.items() if v}
    return {"achats_compares": len(ecarts[0]), "ecart_median_veille_jour_lendemain": med,
            "bon_alignement": bool(med) and min(med, key=med.get) == "0"}


def ajouter_bilan_initie(evs, prix):
    """Bilan de l'initié AVANT l'info : ses achats en bourse passés (dépôt ≥ 60 jours avant, prix de la SEC dès juillet
    2015), chacun mesuré 1 mois : achat à la 1re clôture au moins 1 jour après son dépôt (≤ 10 jours), vente à la 1re
    clôture au moins 30 jours plus tard (≤ 10 jours), même CUSIP, moins le S&P 500 (SPY) aux mêmes dates. Plusieurs
    déclarants sur le formulaire : celui qui a le plus d'achats mesurés."""
    memo = {}

    def ecart(e):
        if e["id"] in memo:
            return memo[e["id"]]
        r = None
        s = e["symbole"]
        if s:
            a = prix.premier(s, (date.fromisoformat(e["depot"]) + timedelta(days=1)).isoformat(), 10)
            if a:
                b = prix.premier(s, (date.fromisoformat(a[0]) + timedelta(days=30)).isoformat(), 10)
                ma, mb = prix.premier("SPY", a[0], 3), prix.premier("SPY", b[0], 3) if b else None
                if b and a[2] == b[2] and ma and mb and a[1] > 0 and ma[1] > 0:
                    r = round((b[1] / a[1] - 1) - (mb[1] / ma[1] - 1), 4)
        memo[e["id"]] = r
        return r

    par_initie = defaultdict(list)
    for e in evs:
        if e["sens"] == "achat" and e["depot"] >= "2015-07-01":
            for i in e["inities"]:
                par_initie[i["cik"]].append(e)
    cumuls = {}  # initié → (dépôts, nombre cumulé, somme cumulée, gagnants cumulés) de ses achats mesurables
    for c, liste in par_initie.items():
        liste.sort(key=lambda e: (e["depot"], e["id"]))
        d, n, t, g = [], [0], [0.0], [0]
        for x in liste:
            v = ecart(x)
            if v is not None:
                d.append(x["depot"])
                n.append(n[-1] + 1)
                t.append(t[-1] + v)
                g.append(g[-1] + (v > 0))
        cumuls[c] = (d, n, t, g)
    for e in evs:
        if e["sens"] != "achat":
            continue
        limite = (date.fromisoformat(e["depot"]) - timedelta(days=60)).isoformat()
        meilleur = (0, 0.0, 0)
        for i in e["inities"]:
            if i["cik"] not in cumuls:
                continue
            d, n, t, g = cumuls[i["cik"]]
            k = bisect_right(d, limite)
            if n[k] > meilleur[0]:
                meilleur = (n[k], t[k], g[k])
        m, total, gagnants = meilleur
        e["bilan_initie"] = {"mesures": m, "ecart_moyen": round(total / m, 4) if m else None,
                             "part_gagnante": round(gagnants / m, 4) if m else None}


# ---------- 3. 13D et 13G ----------

def lire_13(texte, garder):
    """master.idx → [[date, forme courte, [CIK de compagnies des formulaires 4 nommés dans le dépôt]]]."""
    sortie = []
    for d in sec.lire_index(texte).values():
        if d.forme in FORMES_13:
            ciks = sorted({str(int(c)) for c, _ in d.filers if c.isdigit() and (garder is None or str(int(c)) in garder)})
            if ciks:
                sortie.append([d.depose, FORMES_13[d.forme], ciks])
    return sortie


def ajouter_13(evs, treize):
    par_cie = defaultdict(list)
    for jour, forme, ciks in treize:
        for c in ciks:
            par_cie[c].append((jour, forme))
    for c in par_cie:
        par_cie[c].sort()
    for e in evs:
        liste = par_cie.get(e["cik"], [])
        d90 = (date.fromisoformat(e["depot"]) - timedelta(days=90)).isoformat()
        fen = [f for j, f in liste[bisect_left(liste, (d90, "")):bisect_right(liste, (e["depot"], "~"))]]
        e["13d_90j"] = fen.count("13D")
        e["13g_90j"] = fen.count("13G")
    return par_cie


# ---------- 4. Faits XBRL (companyfacts.zip) ----------

def extraire_faits(contenu):
    """companyfacts d'une compagnie → (actions [[fin, valeur, déposé]], finances {concept: [[début, fin, valeur, numéro,
    déposé, forme]]}). Pour chaque période d'un concept : la PREMIÈRE version déposée dans un 10-K ou un 10-Q (une
    correction déposée plus tard n'était pas connue avant). Durées gardées : un trimestre (80 à 100 jours) ou un
    exercice (350 à 380 jours) ; les bilans (sans début) tous. Les actions en circulation (CONCEPTS_ACTIONS) aussi, en
    nombre d'actions."""
    faits = json.loads(contenu).get("facts", {})
    actions = [[f.get("end"), f.get("val"), f.get("filed")] for f in
               faits.get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])]
    finances = {}
    for taxo, concept, unite in [("us-gaap", c, "USD") for c in CONCEPTS] + [(t, c, "shares") for t, c in CONCEPTS_ACTIONS]:
        premiers = {}
        for f in faits.get(taxo, {}).get(concept, {}).get("units", {}).get(unite, []):
            if f.get("form") not in FORMES_FINANCES or not f.get("end") or not f.get("filed") or f.get("val") is None:
                continue
            debut = f.get("start")
            if debut:
                n = (date.fromisoformat(f["end"]) - date.fromisoformat(debut)).days
                if not (80 <= n <= 100 or 350 <= n <= 380):
                    continue
            x = [debut, f["end"], f["val"], f.get("accn"), f["filed"], f["form"]]
            cle = (debut, f["end"])
            if cle not in premiers or (x[4], x[3] or "") < (premiers[cle][4], premiers[cle][3] or ""):
                premiers[cle] = x
        if premiers:
            finances[concept] = sorted(premiers.values(), key=lambda x: (x[1], x[0] or ""))
    return actions, finances


# ---------- Écriture ----------

def ecrire_jsonl(chemin, lignes):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with gzip.open(chemin, "wt", encoding="utf-8") as f:
        for x in lignes:
            f.write(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n")
            n += 1
    return n


CONTEXTE_JOURS = 365  # dépôts d'avant le début gardés comme contexte (météo des initiés, ventes récentes) : jamais achetés


def ecrire_periode(dossier, evs, prix, finances, treize_par_cie, debut, fin, prix_depuis, calendrier, historiques):
    contexte = (debut - timedelta(days=CONTEXTE_JOURS)).isoformat()
    choisis = [e for e in evs if contexte <= e["depot"] <= fin.isoformat()]
    periode = [e for e in choisis if e["depot"] >= debut.isoformat()]
    achats = {e["symbole"] for e in periode if e["sens"] == "achat" and e["symbole"]}
    ciks = {e["cik"] for e in choisis}
    n_ev = ecrire_jsonl(dossier / "evenements.jsonl.gz", sorted(choisis, key=lambda e: (e["depot"], e["id"])))
    # Historique complet des initiés qui achètent dans la période (dépôts jusqu'à la fin de la période), et les prix des
    # compagnies de leurs achats passés (pour juger s'ils ont « bien acheté »)
    acheteurs = sorted({i["cik"] for e in periode if e["sens"] == "achat" for i in e["inities"]}, key=int)
    hist_p = {c: [r for r in historiques.get(c, []) if r[0] <= fin.isoformat()] for c in acheteurs}
    n_hi = ecrire_jsonl(dossier / "historiques.jsonl.gz", ({"initie": c, "depots": v} for c, v in hist_p.items()))
    passes = {r[2] for v in hist_p.values() for r in v if r[3] == "achat" and r[2] and r[0] >= prix_depuis}
    n_px = ecrire_jsonl(dossier / "prix.jsonl.gz", prix.lignes(achats | passes | set(MARCHE), prix_depuis))
    depuis_fi = (debut - timedelta(days=HISTOIRE_FINANCES)).isoformat()
    noms_actions = {c for _, c in CONCEPTS_ACTIONS}
    n_fi = ecrire_jsonl(dossier / "finances.jsonl.gz", (
        {"cik": c, "faits": {k: [f for f in fs if f[1] >= depuis_fi] for k, fs in v.items() if k not in noms_actions},
         "actions": {k: [f for f in fs if f[1] >= depuis_fi] for k, fs in v.items() if k in noms_actions}}
        for c, v in sorted(finances.items()) if c in ciks))
    n_13 = ecrire_jsonl(dossier / "13d13g.jsonl.gz",
                        ({"cik": c, "depots": [x for x in v if x[0] >= prix_depuis]} for c, v in sorted(treize_par_cie.items())
                         if c in ciks))
    (dossier / "calendrier.json").write_text(json.dumps([iso(x) for x in calendrier if iso(x) >= prix_depuis]),
                                             encoding="utf-8")
    (dossier / "periode.json").write_text(json.dumps({"debut": debut.isoformat(), "fin": fin.isoformat(),
                                                      "contexte_depuis": contexte}), encoding="utf-8")
    return {"evenements": n_ev, "evenements_contexte": n_ev - len(periode), "inities_avec_historique": n_hi,
            "achats": sum(e["sens"] == "achat" for e in periode), "symboles_prix": n_px,
            "compagnies_finances": n_fi, "compagnies_13": n_13}


def couverture(evs):
    """Ce qu'on sait de chaque achat : part avec symbole, prix la veille, valeur en bourse, prix pour acheter."""
    a = [e for e in evs if e["sens"] == "achat"]
    if not a:
        return {}
    return {"achats": len(a), "avec_symbole": sum(bool(e["symbole"]) for e in a) / len(a),
            "avec_cloture_avant": sum(bool(e["cloture_avant"]) for e in a) / len(a),
            "avec_valeur_m": sum(e["valeur_m"] is not None for e in a) / len(a),
            "routiniers": sum(e["routinier"] for e in a) / len(a),
            "avec_bilan_initie": sum(e["bilan_initie"]["mesures"] > 0 for e in a) / len(a)}


def main():
    dire("# Tournoi Radar, étape 0 : le jeu de recherche")
    # --- Jeux de données des initiés ---
    liens = inities.fichiers_de_la_page(brut(inities.PAGE, "tournoi/pages/inities.html").decode("utf-8", "replace"))
    voulus = [q for q in trimestres(HISTOIRE_MIN, "2026q2") if q >= HISTOIRE or q in liens]
    manque = [q for q in voulus if q not in liens]
    if manque:
        raise SystemExit(f"jeux de données absents de la page officielle : {manque}")
    dire(f"jeux de données des initiés : {voulus[0]} à {voulus[-1]} ({len(voulus)} trimestres)")
    evs_tous, hist, hist_initie = [], [], []
    for q in voulus:  # un trimestre à la fois : seules les lignes utiles restent en mémoire
        r = garde(f"tournoi/ds/{q}.json.gz", lambda: lire_ds(brut(liens[q])))
        hist.extend(transactions_hist(r))
        hist_initie.extend(lignes_historique(r))
        if q >= trimestre_de(EVENEMENTS_DEPUIS):
            evs_tous.extend(e for e in faire_evenements(r) if e["depot"] >= EVENEMENTS_DEPUIS)
        dire(f"jeu de données {q} : {len(r):,} formulaires 4 originaux avec achat ou vente en bourse")
        del r
    dire(f"infos (achats et ventes) depuis {EVENEMENTS_DEPUIS} : {len(evs_tous):,} · lignes d'historique : {len(hist):,} "
         f"· dépôts dans l'historique des initiés : {len(hist_initie):,}")
    # Contrôle de complétude : chaque mois de 2016 à juin 2026 doit avoir des achats (un trou = données manquantes)
    par_mois = Counter(e["depot"][:7] for e in evs_tous if e["sens"] == "achat")
    mois_voulus = sorted({f"{a}-{m:02d}" for a in range(DEBUT.year, FIN.year + 1) for m in range(1, 13)
                          if f"{a}-{m:02d}" <= FIN.isoformat()[:7]})
    normal = sorted(par_mois.get(m, 0) for m in mois_voulus)[(3 * len(mois_voulus)) // 4]
    trous = [m for m in mois_voulus if par_mois.get(m, 0) < 0.3 * normal]
    dire(f"achats par mois de dépôt : {dict((m, par_mois.get(m, 0)) for m in mois_voulus)}")
    if trous and os.environ.get("TOURNOI_ESSAI") != "1":
        raise SystemExit(f"TROU dans les données : mois avec moins de 30 % d'un mois normal ({normal}) : {trous}")
    ajouter_routiniers(evs_tous, hist)
    del hist
    historiques = defaultdict(list)  # initié → [[dépôt, cik, symbole, sens, jour_premier, jour_dernier, actions, prix]]
    for x in hist_initie:
        historiques[x[0]].append(list(x[1:]))
    del hist_initie
    for v in historiques.values():
        v.sort(key=cle_historique)
    ajouter_contexte(evs_tous, historiques)
    evs = [e for e in evs_tous if e["depot"] >= "2015-01-01"]
    del evs_tous
    dire(f"infos gardées (dépôts dès 2015 : contexte du coffre-fort, bilan des initiés dès juillet) : {len(evs):,}")

    # --- Prix de la SEC ---
    liens_ftd = prix_sec.fichiers_de_la_page(brut(prix_sec.PAGE, "tournoi/pages/ftd.html").decode("utf-8", "replace"))
    cles = sorted(c for c in liens_ftd if c >= PRIX_DEBUT)
    reglements = set()
    for c in cles:  # 1er passage : le calendrier des dates de règlement (pour la date de clôture de chaque prix)
        reglements.update(l[:8] for l in lignes_ftd(brut(liens_ftd[c], f"ftd/{c}.zip"), c)
                          if len(l) > 8 and l[8] == "|" and l[:8].isdigit())
    cloture_de = calendrier_clotures(reglements)
    voulus_px = {e["symbole"] for e in evs if e["symbole"]} | set(MARCHE)
    prix = Prix()
    for c in cles:  # 2e passage : les prix
        compte["lignes de prix"] += prix.ajouter_fichier(lignes_ftd(brut(liens_ftd[c], f"ftd/{c}.zip"), c),
                                                         voulus_px, cloture_de)
    prix.trier()
    calendrier = sorted(set(cloture_de.values()))  # dates de clôture (AAAAMMJJ)
    dire(f"fichiers d'échecs : {len(cles)} ({cles[0]} … {cles[-1]}) · symboles avec prix : {len(prix.d):,} sur "
         f"{len(voulus_px):,} · lignes : {compte['lignes de prix']:,} · clôtures du {calendrier[0]} au {calendrier[-1]}")
    for m in MARCHE:
        if m not in prix.d:
            raise SystemExit(f"pas de prix pour {m} : le banc d'essai ne peut pas comparer au marché")

    # --- Faits XBRL (actions en circulation, finances) des compagnies avec un achat : companyfacts.zip, une requête ---
    ciks_achat = sorted({e["cik"] for e in evs if e["sens"] == "achat" and e["depot"] >= DEBUT.isoformat()}, key=int)
    faits_de, finances = {}, {}
    with zipfile.ZipFile(fichier(FAITS_ZIP, "tournoi/companyfacts.zip")) as z:
        noms = set(z.namelist())
        for i, cik in enumerate(ciks_achat):
            nom = f"CIK{int(cik):010d}.json"
            if nom not in noms:
                compte["compagnies sans faits XBRL"] += 1
                continue
            try:
                faits_de[cik], fi = extraire_faits(z.read(nom))
            except (ValueError, KeyError, TypeError):
                compte["faits XBRL illisibles"] += 1
                continue
            if fi:
                finances[cik] = fi
            if i % 2000 == 0:
                dire(f"faits XBRL : {i:,}/{len(ciks_achat):,}")
    dire(f"faits XBRL : {len(faits_de):,} compagnies sur {len(ciks_achat):,} · avec finances : {len(finances):,} · "
         f"sans faits : {compte['compagnies sans faits XBRL']} · illisibles : {compte['faits XBRL illisibles']}")
    ajouter_marche_et_valeur(evs, prix, faits_de)
    ajouter_bilan_initie(evs, prix)
    alignement = verifier_dates_prix(evs, prix, calendrier)
    dire(f"dates des prix : {alignement}")
    if not alignement["bon_alignement"]:
        dire("ALERTE : les achats sont plus proches de la clôture d'un AUTRE jour : dates des prix à revoir avant les tests")
    dire("valeur en bourse et bilan des initiés calculés")

    # --- 13D et 13G ---
    garder = {e["cik"] for e in evs}
    treize = []
    for q in trimestres("2015q2", "2026q2"):
        an, tr = q[:4], q[5]
        def faire(an=an, tr=tr):
            b = ou_rien(f"{sec.ARCHIVES}/edgar/full-index/{an}/QTR{tr}/master.idx")
            if b in (None, "ERREUR"):
                return "ERREUR"
            return lire_13(b.decode("latin-1"), None)
        x = garde(f"tournoi/13/{q}.json.gz", faire)
        if x == "ERREUR":
            raise SystemExit(f"index EDGAR illisible : {q}")
        treize += [[d, f, [c for c in ciks if c in garder]] for d, f, ciks in x]
    treize = [t for t in treize if t[2]]
    treize_par_cie = ajouter_13(evs, treize)
    dire(f"13D et 13G sur des compagnies des formulaires 4 : {len(treize):,}")

    # --- Sorties : découverte (branche labo) et coffre-fort (cache seulement) ---
    resume = {
        "decouverte": ecrire_periode(DECOUVERTE_DOSSIER, evs, prix, finances, treize_par_cie, DECOUVERTE, FIN, "2015-07-01",
                                     calendrier, historiques),
        "coffre": ecrire_periode(COFFRE, evs, prix, finances, treize_par_cie, DEBUT, DECOUVERTE - timedelta(days=1),
                                 "2015-07-01", calendrier, historiques),
        "couverture_decouverte": couverture([e for e in evs if e["depot"] >= DECOUVERTE.isoformat()]),
        "alignement_des_prix": alignement,
        "compte": dict(compte)}
    SORTIE.mkdir(parents=True, exist_ok=True)
    for dossier in (SORTIE, DECOUVERTE_DOSSIER):
        (dossier / "resume.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # Le résumé du coffre-fort ne dit QUE les nombres de lignes (rien sur les rendements)
    dire(f"découverte : {resume['decouverte']} · coffre-fort (nombres seulement) : {resume['coffre']}")
    dire(f"couverture des achats de la découverte : {resume['couverture_decouverte']}")
    for dossier in (SORTIE, DECOUVERTE_DOSSIER):
        (dossier / "journal.md").write_text("\n".join(journal) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    finally:  # même en cas d'arrêt : le journal du calcul est gardé, pour voir où et pourquoi
        if journal:
            SORTIE.mkdir(parents=True, exist_ok=True)
            (SORTIE / "journal.md").write_text("\n".join(journal) + "\n", encoding="utf-8")
