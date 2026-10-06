"""sante_valeur-4 (VÉRIFICATEUR) : S&P 500 par défaut + quelques paris rares sur le trio strict (B/M ≥ 0,70, F7 ≥ 6,
bénéfice et flux d'exploitation positifs, passif ÷ actif ≤ 0,70, achat d'initié ≥ 100 000 $) : au plus 4 satellites
de 15 %, gardés 12 mois.

Programmé d'après labo/tournoi/regles_preenregistrees.json, sans voir labo/tournoi/regles/.
Reprogrammé le 6 octobre 2026 : les actions en circulation à chaque fin de période existent maintenant
(ctx.actions_par_periode), donc l'élément 6 du F7 se calcule et la règle n'est plus écartée.
"""
import math
from datetime import date, timedelta

ID = "sante_valeur-4"
IMPOSSIBLE = None

JOURS_ENTREE = 1            # clôture du 1er jour de bourse APRÈS le dépôt
TOLERANCE_ENTREE = 5        # pas de prix ce jour-là : jusqu'à 5 jours de bourse de plus, sinon abandon
DUREE = 262                 # filet : la vente des 12 mois civils est faite par sortir_avant()
TOLERANCE_SORTIE = 0        # au 262e jour de bourse sans prix : la dernière clôture connue
MAX_POSITIONS = 4           # au plus 4 satellites
ARGENT_QUI_ATTEND = "SPY"   # base : 100 % SPY ; l'argent qui attend reste dans SPY
LIQUIDE_JOURS = 0           # l'argent d'une vente retourne dans SPY le jour même
MONTANT_MIN = 50            # montant minimal du banc (inchangé)
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

CHOIX = [
    "Comparaison testeur/vérificateur (6 oct. 2026) : les deux programmes ne donnaient pas les mêmes achats et ventes "
    "sur le faux jeu. Décision selon le texte : les lectures du testeur sont gardées, ce fichier est corrigé sur 5 "
    "points. (1) Vente 12 mois CIVILS après l'achat, à la 1re clôture SEC à cette date ou après (« à cette date ou "
    "après » : jamais avant), et non 252 jours de bourse. (2) (j) « compagnie pas déjà en portefeuille » fait partie "
    "du FILTRE : vérifié le soir du dépôt, par compagnie (cik, le texte dit « compagnie », pas « symbole »), avec le "
    "portefeuille refait par la règle ; le banc refuse aussi, le jour de l'achat, un symbole déjà détenu. (3) Un "
    "chiffre de 350 à 380 jours tiré d'un 10-Q (12 mois glissants) n'est pas un « exercice annuel ». (4) Plusieurs "
    "fins possibles pour t-1 (330 à 400 jours avant t, cas rare) : la plus proche de 365 jours, puis la plus récente "
    "(l'exercice d'un an avant t ; la plus récente pourrait chevaucher t de plusieurs mois). (5) Élément 7 du F7 : le "
    "même concept de revenus pour t et t-1 (le premier de la liste qui a les deux années), pour comparer la même "
    "mesure d'une année à l'autre. Mêmes décisions que pour sante_valeur-1 (F7 « exactement comme dans "
    "sante_valeur-1 ») et, pour les points 1 à 3, que pour sante_valeur-2 et sante_valeur-3. Vérifié ensuite identique "
    "sur le faux jeu et sur un jeu ciblé (comparaison/sante_valeur/jeu_sante_valeur-4).",
    "Actions en circulation (élément 6 du F7) : CommonStockSharesOutstanding (us-gaap, au bilan) de "
    "ctx.actions_par_periode, à la date de FIN de l'exercice t et à celle de l'exercice t-1. Pourquoi : le F7 de "
    "sante_valeur-1 compare les actions à la fin des exercices t et t-1 (champs « XBRL annuel et trimestriel : … "
    "actions en circulation, date de fin de période ») et ce concept est daté exactement à la fin de la période. "
    "EntityCommonStockSharesOutstanding (page couverture) est daté près du DÉPÔT du rapport, pas à la fin de "
    "l'exercice : pas utilisé, même en remplacement. Un des deux chiffres absent : l'élément 6 ne peut pas être "
    "calculé et l'événement est écarté (texte). Aucun ajustement pour un fractionnement ou un regroupement d'actions "
    "(la règle n'en prévoit pas).",
    "Seulement les achats (sens « achat », code P). (a) : au moins un des déclarants du formulaire a le rôle "
    "administrateur ou dirigeant (un formulaire peut avoir plusieurs déclarants).",
    "(b) routinier vrai : écarté. (c) plan_10b5_1 vrai : écarté ; faux ou vide : accepté (texte : « non (ou vide) », "
    "sans date).",
    "(d) montant = le champ montant du formulaire (lignes avec un prix), au moins 100 000 $. (e) valeur_m du "
    "formulaire, au moins 100 (M$). Champ absent : écarté.",
    "Délais comptables (« exactement comme dans sante_valeur-1 ») : en plus du banc (un chiffre n'est vu qu'à partir "
    "de sa vraie date de dépôt), les délais écrits, comptés en jours civils avant le dépôt du formulaire 4 : un "
    "exercice annuel compte si sa fin est au moins 120 jours avant ; un chiffre de bilan compte si sa fin est au moins "
    "60 jours avant quand il vient d'un rapport trimestriel (10-Q, 10-Q/A), 120 jours quand il vient d'un rapport "
    "annuel (10-K, 10-K/A, 10-KT).",
    "(f) Capitaux propres = StockholdersEquity à la date de bilan connue la plus récente (trimestre ou année, avec ces "
    "délais) ; B/M = capitaux propres ÷ (valeur_m × 1 000 000), valeur_m du formulaire 4. Capitaux propres absents : "
    "écarté.",
    "(g) F7 exactement comme dans sante_valeur-1. Exercice t : la fin la plus récente d'un chiffre annuel (durée de 350 "
    "à 380 jours, pas tiré d'un 10-Q ou 10-Q/A, n'importe quel concept de durée des finances) au moins 120 jours avant "
    "le dépôt ; exercice t-1 : la fin d'un chiffre annuel qui tombe 330 à 400 jours avant celle de t (s'il y en a "
    "plusieurs : la plus proche de 365 jours, puis la plus récente).",
    "F7 : bénéfice net = NetIncomeLoss ; flux d'exploitation = NetCashProvidedByUsedInOperatingActivities ; revenus = "
    "Revenues, sinon RevenueFromContractWithCustomerExcludingAssessedTax, sinon SalesRevenueNet (le même concept pour t "
    "et t-1 : le premier de cette liste qui a les deux exercices) ; chiffres annuels qui finissent exactement à la fin "
    "de l'exercice ; actif = Assets, passif = "
    "Liabilities et actions au bilan à la date de fin de l'exercice. Le passif n'est pas recalculé si Liabilities "
    "manque. Deux chiffres annuels du même concept avec la même fin (rare) : celui qui commence le plus tard.",
    "Un chiffre du F7 absent, ou un actif ≤ 0 (division impossible) : l'élément ne peut pas être calculé, l'événement "
    "est écarté (texte). Score = nombre de conditions vraies sur 7, gardé si au moins 6.",
    "(h) bénéfice net_t > 0 et flux d'exploitation_t > 0 : le même exercice t que le F7.",
    "(i) passif ÷ actif ≤ 0,70 : le texte ne donne pas la période (pas d'indice t, contrairement à (h)) ; pris comme "
    "les capitaux propres : Liabilities ÷ Assets à la date de bilan connue la plus récente (trimestre ou année) où les "
    "deux existent, avec les mêmes délais de 60 et 120 jours. Raisons : les champs de la règle demandent l'actif et le "
    "passif trimestriels, qui ne servent qu'ici, et la même condition de sante_valeur-3 dit « période connue la plus "
    "récente ». Absents ou actif ≤ 0 : écarté.",
    "Taille : 4 satellites de 15 % = MAX_POSITIONS = 4 et poids() = 0,6 (le banc achète valeur du portefeuille ÷ 4 × "
    "0,6 = 15 %). « Au plus 60 % en actions, au moins 40 % dans SPY » : conséquence des 4 places de 15 % au moment de "
    "l'achat ; pas de rééquilibrage ni de plafond si les satellites montent (le texte n'en prévoit pas).",
    "Pas de limite par mois. Ordre d'achat quand plusieurs signaux attendent le même jour : date de dépôt, puis le plus "
    "gros montant (priorite()), puis le numéro du dépôt (banc). Plus de place libre : le banc ignore le signal "
    "(« les nouveaux événements sont ignorés »).",
    "(j) « pas déjà en portefeuille » : le banc ne montre pas le portefeuille à la règle ; garder() le refait jour par "
    "jour pour SES événements gardés (mêmes règles que banc.simuler : ventes puis achats, prix du jour exact, 5 jours "
    "de réessai, 4 places, symbole déjà détenu, ordre de priorite() puis date de dépôt et numéro), avec les seuls jours "
    "passés (au plus tard le jour du dépôt) : la compagnie (cik) ne doit pas avoir de position le soir du dépôt. Le "
    "banc refuse aussi, le jour de l'achat, un symbole déjà détenu.",
    "Début de la période : la règle ne voit pas periode.json ; elle le déduit du 1er dépôt du jeu (1 an de contexte) : "
    "1er dépôt + 365 jours, ramené au 1er du mois. Les dépôts d'avant ne sont jamais achetés par le banc : garder() les "
    "écarte et ils n'entrent pas dans le portefeuille refait (hypothèse : le banc est lancé sans --debut).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le 1er jour de bourse après le dépôt, puis jusqu'à 5 jours de "
    "bourse de plus ; sinon abandon).",
    "Sortie « 12 mois après l'achat » : date cible = date d'achat + 12 mois civils (29 février → 28 février). "
    "sortir_avant() dit de vendre dès que le jour de semaine qui suit la veille atteint cette date ; le banc vend à la "
    "1re clôture SEC à cette date ou après (un congé juste avant la date cible peut retarder la vente d'un jour). "
    "Pas de vente anticipée.",
    "Sortie sans prix SEC : DUREE = 262 et TOLERANCE_SORTIE = 0 : au 262e jour de bourse après l'achat, la dernière "
    "clôture connue (aussi pour un titre disparu). Le banc ne permet qu'un délai fixe en jours de bourse depuis l'achat : "
    "avec environ 250 jours de bourse par an dans le vrai calendrier, c'est 10 à 12 jours de bourse après la date des "
    "12 mois (texte : 10) ; jamais avant cette date, même sur le faux jeu (environ 261 jours par an).",
    "Argent qui attend : SPY (100 % au départ), vendu pour payer un achat et racheté le jour d'une vente "
    "(LIQUIDE_JOURS = 0) ; frais et montant minimal (50 $) du banc.",
]

ROLES_OK = ("administrateur", "dirigeant")
REVENUS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
ACTIONS = "CommonStockSharesOutstanding"
B_M_MIN, F7_MIN, MONTANT_MINIMUM, VALEUR_M_MIN, PASSIF_ACTIF_MAX = 0.70, 6, 100_000, 100, 0.70
_AN_2000 = date(2000, 1, 1)


# ---------- Finances ----------

def _jours(a, b):
    """Jours civils de la date a à la date b (AAAA-MM-JJ)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _annuel(f):
    """Un chiffre de durée qui couvre un exercice entier (350 à 380 jours), pas tiré d'un 10-Q (12 mois glissants)."""
    return f[0] is not None and 350 <= _jours(f[0], f[1]) <= 380 and not (f[3] or "").startswith("10-Q")


def _exercices(fi, depot):
    """(fin de t, fin de t-1) : t = dernier exercice annuel connu (fin ≥ 120 jours avant le dépôt) ; t-1 = l'exercice
    annuel qui finit 330 à 400 jours avant t (s'il y en a plusieurs : le plus proche de 365 jours, puis le plus
    récent). None si l'un manque."""
    fins = sorted({f[1] for faits in fi.values() for f in faits if _annuel(f)})
    connues = [x for x in fins if _jours(x, depot) >= 120]
    if not connues:
        return None
    t = connues[-1]
    avant = [x for x in fins if 330 <= _jours(x, t) <= 400]
    return (t, min(reversed(avant), key=lambda x: abs(_jours(x, t) - 365))) if avant else None


def _annuel_a(fi, concept, fin):
    """Valeur annuelle d'un concept pour l'exercice qui finit à `fin` (None si absente)."""
    v = [f[2] for f in fi.get(concept, []) if f[1] == fin and _annuel(f)]
    return v[-1] if v else None


def _revenus(fi, t, t1):
    """(revenus de t, revenus de t-1) du même concept : le premier de REVENUS qui a les deux exercices."""
    for c in REVENUS:
        v, v1 = _annuel_a(fi, c, t), _annuel_a(fi, c, t1)
        if v is not None and v1 is not None:
            return v, v1
    return None, None


def _bilan_a(faits, fin):
    """Valeur de bilan (sans début) à la date `fin` (None si absente)."""
    v = [f[2] for f in faits if f[0] is None and f[1] == fin]
    return v[-1] if v else None


def _bilan_connu(f, depot):
    """Chiffre de bilan connu selon les délais de la règle : fin ≥ 120 jours avant le dépôt s'il vient d'un rapport
    annuel (10-K…), ≥ 60 jours s'il vient d'un rapport trimestriel (10-Q…)."""
    if f[0] is not None:
        return False
    annuel = (f[3] or "").upper().startswith("10-K")
    return _jours(f[1], depot) >= (120 if annuel else 60)


def _capitaux_propres(fi, depot):
    """StockholdersEquity de la période connue la plus récente (trimestre ou année)."""
    v = [f for f in fi.get("StockholdersEquity", []) if _bilan_connu(f, depot)]
    return v[-1][2] if v else None


def _passif_actif(fi, depot):
    """(passif, actif) à la date de bilan connue la plus récente où les deux existent (None sinon)."""
    par_fin = {}
    for c in ("Liabilities", "Assets"):
        for f in fi.get(c, []):
            if _bilan_connu(f, depot):
                par_fin.setdefault(f[1], {})[c] = f[2]
    complets = [x for x, v in par_fin.items() if len(v) == 2]
    if not complets:
        return None
    v = par_fin[max(complets)]
    return v["Liabilities"], v["Assets"]


def _f7(fi, ap, t, t1):
    """Score F7 (0 à 7), ou None si un des 7 éléments ne peut pas être calculé."""
    bn, bn1 = _annuel_a(fi, "NetIncomeLoss", t), _annuel_a(fi, "NetIncomeLoss", t1)
    flux = _annuel_a(fi, "NetCashProvidedByUsedInOperatingActivities", t)
    actif, actif1 = _bilan_a(fi.get("Assets", []), t), _bilan_a(fi.get("Assets", []), t1)
    passif, passif1 = _bilan_a(fi.get("Liabilities", []), t), _bilan_a(fi.get("Liabilities", []), t1)
    rev, rev1 = _revenus(fi, t, t1)
    act, act1 = _bilan_a(ap.get(ACTIONS, []), t), _bilan_a(ap.get(ACTIONS, []), t1)
    if any(v is None for v in (bn, bn1, flux, actif, actif1, passif, passif1, rev, rev1, act, act1)):
        return None
    if not (actif > 0 and actif1 > 0):
        return None
    points = [
        bn / actif > 0,                          # 1) bénéfice net_t ÷ actif_t > 0
        flux > 0,                                # 2) flux d'exploitation_t > 0
        bn / actif > bn1 / actif1,               # 3) bénéfice net_t/actif_t > bénéfice net_t-1/actif_t-1
        flux > bn,                               # 4) flux d'exploitation_t > bénéfice net_t
        passif / actif < passif1 / actif1,       # 5) passif_t/actif_t < passif_t-1/actif_t-1
        act <= 1.02 * act1,                      # 6) actions_t ≤ 1,02 × actions_t-1
        rev / actif > rev1 / actif1,             # 7) revenus_t/actif_t > revenus_t-1/actif_t-1
    ]
    return sum(points)


# ---------- Le filtre (a) à (i) ; (j) dans garder() ----------

def _filtre(e, ctx):
    if e.get("sens") != "achat":
        return False
    if not any(r in ROLES_OK for i in e.get("inities") or [] for r in i.get("roles") or []):  # (a)
        return False
    if e.get("routinier"):  # (b)
        return False
    if e.get("plan_10b5_1") is True:  # (c) non, ou vide
        return False
    if not (e.get("montant") or 0) >= MONTANT_MINIMUM:  # (d)
        return False
    vm = e.get("valeur_m")
    if vm is None or not vm >= VALEUR_M_MIN:  # (e)
        return False
    fi = ctx.finances(e["cik"])
    cp = _capitaux_propres(fi, e["depot"])
    if cp is None or not cp > 0 or not cp / (vm * 1_000_000) >= B_M_MIN:  # (f)
        return False
    ex = _exercices(fi, e["depot"])
    if ex is None:
        return False
    t, t1 = ex
    score = _f7(fi, ctx.actions_par_periode(e["cik"]), t, t1)
    if score is None or not score >= F7_MIN:  # (g)
        return False
    bn = _annuel_a(fi, "NetIncomeLoss", t)
    flux = _annuel_a(fi, "NetCashProvidedByUsedInOperatingActivities", t)
    if not (bn > 0 and flux > 0):  # (h) (déjà calculables : le F7 l'a vérifié)
        return False
    pa = _passif_actif(fi, e["depot"])
    if pa is None or not pa[1] > 0 or not pa[0] / pa[1] <= PASSIF_ACTIF_MAX:  # (i)
        return False
    return True


# ---------- Vente : 12 mois civils après l'achat ----------

def _douze_mois_apres(jour):
    """La date 12 mois civils après `jour` (le 29 février donne le 28 février)."""
    j = date.fromisoformat(jour)
    try:
        return j.replace(year=j.year + 1).isoformat()
    except ValueError:
        return j.replace(year=j.year + 1, day=28).isoformat()


def _a_vendre(achat, veille):
    """Vendre au jour de bourse qui suit `veille` ? Oui si ce jour atteint la date d'achat + 12 mois. Les jours de bourse
    à venir ne sont pas connus : ce jour est pris comme le jour de semaine qui suit la veille."""
    j = date.fromisoformat(veille) + timedelta(days=1)
    while j.weekday() >= 5:
        j += timedelta(days=1)
    return j.isoformat() >= _douze_mois_apres(achat)


def sortir_avant(pos, jour, ctx):
    return _a_vendre(pos["entree"][0], jour)


# ---------- Le portefeuille de la règle, refait jour par jour (pour (j)) ----------

_REJEU = {}  # le banc refait pour NOS événements gardés, avec les seuls jours passés (au plus tard ctx.jour)


def _rejeu(e, ctx):
    """Le rejeu avancé jusqu'au soir de ctx.jour (le jour du dépôt de e). Remis à zéro si une nouvelle simulation
    commence (les dépôts arrivent toujours dans l'ordre). Début de la période : 1er dépôt du jeu + 365 jours, ramené au
    1er du mois (le jeu commence par 1 an de contexte)."""
    r = _REJEU
    if r and e["depot"] < r["dernier_depot"]:
        r.clear()
    if not r:
        premier = date.fromisoformat(ctx.evenements_marche("0000-00-00")[0]["depot"])
        r.update(debut=(premier + timedelta(days=365)).replace(day=1).isoformat(), jour=None, positions=[],
                 attente=[], a_venir=[])
    r["dernier_depot"] = e["depot"]
    depuis = r["debut"] if r["jour"] is None else (date.fromisoformat(r["jour"]) + timedelta(days=1)).isoformat()
    for jour in ctx.jours_de_bourse(depuis):
        _jour_du_banc(ctx, r, jour)
    return r


def _jour_du_banc(ctx, r, jour):
    """Un jour de bourse du banc pour nos événements gardés : les ventes, puis les achats (comme banc.simuler)."""
    veille, restent = r["jour"], []
    for p in r["positions"]:
        p["n"] += 1  # jours de bourse depuis l'achat
        prevue = p["n"] >= DUREE
        tot = not prevue and veille is not None and jour > p["entree"] and _a_vendre(p["entree"], veille)
        vendue = ((prevue or tot) and ctx.clotures(p["s"], jour, jour)) or (prevue and p["n"] >= DUREE + TOLERANCE_SORTIE)
        if not vendue:
            restent.append(p)
    r["positions"] = restent
    attente = [(x, n + 1) for x, n in r["attente"] if n + 1 <= TOLERANCE_ENTREE]  # 6 jours sans prix : abandonné
    while r["a_venir"] and r["a_venir"][0]["depot"] < jour:
        attente.append((r["a_venir"].pop(0), 0))
    r["attente"] = []
    for x, n in sorted(attente, key=lambda y: (-priorite(y[0], None), y[0]["depot"], y[0]["id"])):  # ordre du banc
        if not ctx.clotures(x["symbole"], jour, jour):
            r["attente"].append((x, n))
        elif len(r["positions"]) < MAX_POSITIONS and not any(p["s"] == x["symbole"] for p in r["positions"]):
            r["positions"].append({"s": x["symbole"], "cik": x["cik"], "entree": jour, "n": 0})
        # sinon : 4 places prises ou symbole déjà détenu, pas acheté (ignoré)
    r["jour"] = jour


def garder(e, ctx):
    if IMPOSSIBLE or e.get("sens") != "achat" or not e.get("symbole"):
        return False
    r = _rejeu(e, ctx)
    if e["depot"] < r["debut"] or not _filtre(e, ctx):
        return False
    if e["cik"] in {p["cik"] for p in r["positions"]}:  # (j) compagnie déjà en portefeuille le soir du dépôt
        return False
    r["a_venir"].append(e)
    return True


def priorite(e, ctx):
    """Ordre du texte : date de dépôt d'abord, puis le plus gros montant (le banc achète la plus haute priorité d'abord).
    Un jour de dépôt plus ancien vaut 1 de plus ; le montant ajoute une fraction (0 à moins de 1) qui grandit avec lui.
    Montants égaux : le banc départage par date de dépôt puis numéro du dépôt."""
    m = max(e.get("montant") or 0.0, 0.0)
    return -(date.fromisoformat(e["depot"]) - _AN_2000).days + min(math.log10(1.0 + m) / 16.0, 0.999999)


def poids(e, ctx):
    """Chaque satellite vaut 15 % du portefeuille : valeur ÷ 4 places × 0,6."""
    return 0.6
