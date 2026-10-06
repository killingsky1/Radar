"""sante_valeur-3 (VÉRIFICATEUR) : argent réel et bénéfices de qualité — flux de trésorerie élevé par rapport au prix
+ achat d'un administrateur ou d'un dirigeant, gardé 12 mois.

Programmé d'après labo/tournoi/regles_preenregistrees.json, sans voir labo/tournoi/regles/.
"""
from datetime import date, timedelta

ID = "sante_valeur-3"
IMPOSSIBLE = None

JOURS_ENTREE = 1            # clôture du 1er jour de bourse APRÈS le dépôt
TOLERANCE_ENTREE = 5        # pas de prix ce jour-là : jusqu'à 5 jours de bourse de plus, sinon abandon
DUREE = 262                 # filet : la vente des 12 mois civils est faite par sortir_avant()
TOLERANCE_SORTIE = 0        # au 262e jour de bourse sans prix : la dernière clôture connue
MAX_POSITIONS = 6           # 6 places : chaque achat vaut 1/6 du portefeuille
ARGENT_QUI_ATTEND = "SPY"   # au départ 100 % SPY ; l'argent qui attend reste dans SPY
LIQUIDE_JOURS = 0           # l'argent d'une vente retourne dans SPY le jour même
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

CHOIX = [
    "DÉCISION DE LA COMPARAISON (testeur contre vérificateur), selon le texte : (1) vente 12 mois CIVILS après l'achat, "
    "à la 1re clôture SEC à cette date ou après (« à cette date ou après » : jamais avant), et non 252 jours de bourse ; "
    "(2) (k) « pas déjà en portefeuille » fait partie du FILTRE : vérifié le soir du dépôt avec le portefeuille de la "
    "règle, et un tel événement ne prend pas la place du mois ; (3) « au plus 1 nouvel ACHAT par mois » : la place n'est "
    "prise que par un achat (ou un événement gardé qui attend encore son achat) ; un événement gardé que le banc "
    "n'achète pas (pas de prix en 6 jours, 6 places prises, symbole déjà détenu) la laisse au suivant du mois ; (4) un "
    "chiffre de 350 à 380 jours tiré d'un 10-Q (12 mois glissants) n'est pas un « exercice annuel ». Les quatre "
    "lectures du testeur sont gardées ; ce fichier est corrigé.",
    "Seulement les achats (sens « achat », code P). Un formulaire avec plusieurs déclarants passe (a) si au moins un "
    "d'eux est administrateur ou dirigeant.",
    "(b) routinier : le champ routinier du jeu de données (vrai = écarté). (c) plan_10b5_1 vrai = écarté ; faux ou vide "
    "= accepté.",
    "(d) montant = le champ montant (lignes avec un prix). (e) valeur_m absente = écarté.",
    "Finances : ctx.finances (un chiffre n'est vu qu'à partir de sa vraie date de dépôt) ET, en plus, les délais écrits "
    "dans la règle : un exercice annuel compte si sa fin est au moins 120 jours avant le dépôt ; un bilan compte si sa "
    "fin est au moins 60 jours avant le dépôt s'il vient d'un 10-Q, 120 jours s'il vient d'un 10-K (10-K/A, 10-KT).",
    "Exercice t : la fin la plus récente parmi les chiffres annuels (durée de 350 à 380 jours, pas tirés d'un 10-Q ou "
    "10-Q/A, tous les concepts de durée des finances) qui respectent le délai de 120 jours. Bénéfice net = "
    "NetIncomeLoss et flux d'exploitation = NetCashProvidedByUsedInOperatingActivities de CET exercice (même date de "
    "fin).",
    "Deux chiffres annuels du même concept qui finissent le même jour (rare) : le dernier de la liste de "
    "ctx.finances (celui qui commence le plus tard).",
    "(f) flux d'exploitation_t ÷ (valeur_m × 1 000 000) ≥ 0,10, avec valeur_m du formulaire 4.",
    "(i) passif ÷ actif : concepts Liabilities et Assets à la date de bilan connue la plus récente où les deux existent. "
    "Le passif n'est pas recalculé (actif − capitaux propres) quand Liabilities manque.",
    "(j) capitaux propres : StockholdersEquity à la date de bilan connue la plus récente.",
    "Un chiffre nécessaire absent (ou un actif ≤ 0) : la condition ne peut pas être vérifiée et l'événement est écarté.",
    "Le banc ne montre pas le portefeuille à la règle : garder() le refait jour par jour pour SES événements gardés "
    "(mêmes règles que banc.simuler : ventes puis achats, prix du jour exact, 5 jours de réessai, 6 places, symbole déjà "
    "détenu, ordre date de dépôt puis numéro), avec les seuls jours passés (au plus tard le jour du dépôt).",
    "(k) « pas déjà en portefeuille » : la compagnie (cik) n'a pas de position le soir du dépôt, dans ce portefeuille "
    "refait. Le banc refuse aussi, le jour de l'achat, un symbole déjà détenu.",
    "Au plus 1 achat par mois civil, le mois étant celui de la date de DÉPÔT : un événement est gardé s'il passe le "
    "filtre et (k), si aucun événement gardé du même mois n'est acheté ou encore en attente de son achat, et si aucun "
    "autre achat du même jour, plus gros (puis numéro plus petit), ne passe le filtre et (k). Un événement gardé que le "
    "banc n'achète pas (aucun prix SEC en 6 jours de bourse, 6 places prises, symbole déjà détenu) laisse la place au "
    "suivant du mois. Pour un dépôt, c'est le filtre calculé le soir de SON dépôt (gardé en mémoire).",
    "Un événement gardé qui attend encore son prix bloque ceux qui le suivent dans le mois ; s'il est abandonné plus "
    "tard, ceux qui ont été écartés entre-temps ne sont pas repris (garder() ne décide qu'une fois par dépôt).",
    "Un dépôt de la fin d'un mois peut être acheté au début du mois suivant, en plus de l'achat de ce mois-là.",
    "Début de la période : la règle ne voit pas periode.json ; elle le déduit du 1er dépôt du jeu (1 an de contexte) : "
    "1er dépôt + 365 jours, ramené au 1er du mois. Les dépôts d'avant ne sont jamais achetés par le banc : garder() les "
    "écarte et ils n'entrent pas dans le portefeuille refait (hypothèse : le banc est lancé sans --debut).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le 1er jour de bourse après le dépôt, puis jusqu'à 5 jours de "
    "bourse de plus ; sinon abandon).",
    "Sortie « 12 mois après l'achat » : date cible = date d'achat + 12 mois civils (29 février → 28 février). "
    "sortir_avant() dit de vendre dès que le jour de semaine qui suit la veille atteint cette date ; le banc vend à la "
    "1re clôture SEC à cette date ou après (un congé juste avant la date cible peut retarder la vente d'un jour).",
    "Sortie sans prix SEC : DUREE = 262 et TOLERANCE_SORTIE = 0 : au 262e jour de bourse après l'achat, la dernière "
    "clôture connue (aussi pour un titre disparu). Le banc ne permet qu'un délai fixe en jours de bourse depuis l'achat : "
    "avec environ 250 jours de bourse par an dans le vrai calendrier, c'est 10 à 12 jours de bourse après la date des "
    "12 mois (texte : 10) ; jamais avant cette date, même sur le faux jeu (environ 261 jours par an).",
    "Argent qui attend : SPY, vendu pour payer un achat et racheté le jour d'une vente (LIQUIDE_JOURS = 0). Montant "
    "minimal du banc (50 $) gardé ; frais du banc (10 $ et demi-écart).",
]

ROLES_OK = ("administrateur", "dirigeant")
DUREES = ("NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities", "Revenues",
          "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "GrossProfit")

_FILTRE = {}  # id d'un dépôt → passe le filtre ? (calculé le soir de SON dépôt : ne dépend que du passé)


# ---------- Finances ----------

def _jours(a, b):
    """Jours civils de la date a à la date b (AAAA-MM-JJ)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _annuel(f):
    """Un chiffre de durée qui couvre un exercice entier (350 à 380 jours), pas tiré d'un 10-Q (12 mois glissants)."""
    return f[0] is not None and 350 <= _jours(f[0], f[1]) <= 380 and not (f[3] or "").startswith("10-Q")


def _fin_exercice_t(fi, depot):
    """Fin de l'exercice t : le dernier exercice annuel connu, fini au moins 120 jours avant le dépôt."""
    fins = [f[1] for c in DUREES for f in fi.get(c, []) if _annuel(f) and _jours(f[1], depot) >= 120]
    return max(fins) if fins else None


def _annuel_a(fi, concept, fin):
    """Valeur d'un concept pour l'exercice annuel qui finit à `fin` (None si absente)."""
    v = [f[2] for f in fi.get(concept, []) if f[1] == fin and _annuel(f)]
    return v[-1] if v else None


def _bilan_connu(f, depot):
    """Un chiffre de bilan connu : fin au moins 120 jours avant le dépôt (10-K) ou 60 jours (10-Q)."""
    if f[0] is not None:
        return False
    return _jours(f[1], depot) >= (120 if (f[3] or "").startswith("10-K") else 60)


def _dernier_bilan(fi, concepts, depot):
    """{concept: valeur} à la date de bilan connue la plus récente où tous ces concepts existent (None sinon)."""
    par_fin = {}
    for c in concepts:
        for f in fi.get(c, []):
            if _bilan_connu(f, depot):
                par_fin.setdefault(f[1], {})[c] = f[2]
    for fin in sorted(par_fin, reverse=True):
        if len(par_fin[fin]) == len(concepts):
            return par_fin[fin]
    return None


# ---------- Le filtre ----------

def _filtre(e, ctx):
    """Conditions (a) à (j) du texte ; (k) « pas déjà en portefeuille » est vérifiée par le banc."""
    if e.get("sens") != "achat":
        return False
    if not any(r in ROLES_OK for i in e.get("inities") or [] for r in i.get("roles") or []):  # (a)
        return False
    if e.get("routinier"):  # (b)
        return False
    if e.get("plan_10b5_1") is True:  # (c)
        return False
    if not (e.get("montant") or 0) >= 50_000:  # (d)
        return False
    vm = e.get("valeur_m")
    if vm is None or not vm >= 100:  # (e)
        return False
    fi = ctx.finances(e["cik"])
    t = _fin_exercice_t(fi, e["depot"])
    if t is None:
        return False
    flux = _annuel_a(fi, "NetCashProvidedByUsedInOperatingActivities", t)
    benefice = _annuel_a(fi, "NetIncomeLoss", t)
    if flux is None or benefice is None:
        return False
    if not flux / (vm * 1_000_000) >= 0.10:  # (f)
        return False
    if not flux >= benefice:  # (g)
        return False
    if not benefice > 0:  # (h)
        return False
    pa = _dernier_bilan(fi, ("Liabilities", "Assets"), e["depot"])
    if pa is None or not pa["Assets"] > 0 or not pa["Liabilities"] / pa["Assets"] <= 0.70:  # (i)
        return False
    cp = _dernier_bilan(fi, ("StockholdersEquity",), e["depot"])
    if cp is None or not cp["StockholdersEquity"] > 0:  # (j)
        return False
    return True


def _passe(e, ctx):
    """Le filtre de e tel que calculé le soir de son dépôt (gardé en mémoire)."""
    r = _FILTRE.get(e["id"])
    if r is None:
        r = _filtre(e, ctx)
        if ctx.jour == e["depot"]:
            _FILTRE[e["id"]] = r
    return r


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


# ---------- Le portefeuille de la règle, refait jour par jour (pour (k) et « 1 achat par mois ») ----------

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
                 attente=[], a_venir=[], sort={}, gardes={})
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
    attente = [(x, n + 1) for x, n in r["attente"]]
    while r["a_venir"] and r["a_venir"][0]["depot"] < jour:
        attente.append((r["a_venir"].pop(0), 0))
    r["attente"] = []
    for x, n in sorted(attente, key=lambda y: (y[0]["depot"], y[0]["id"])):  # ordre du banc sans priorite()
        if not ctx.clotures(x["symbole"], jour, jour):
            if n < TOLERANCE_ENTREE:
                r["attente"].append((x, n))
            else:
                r["sort"][x["id"]] = "perdu"  # 6e jour de bourse sans prix : abandonné
        elif len(r["positions"]) >= MAX_POSITIONS or any(p["s"] == x["symbole"] for p in r["positions"]):
            r["sort"][x["id"]] = "perdu"  # 6 places prises ou symbole déjà détenu : pas acheté
        else:
            r["positions"].append({"s": x["symbole"], "cik": x["cik"], "entree": jour, "n": 0})
            r["sort"][x["id"]] = "achete"
    r["jour"] = jour


# ---------- (k) pas déjà en portefeuille, et au plus 1 achat par mois civil ----------

def _premier_du_mois(e, ctx, r):
    """(k) la compagnie n'est pas en portefeuille le soir du dépôt ; la place du mois (mois du dépôt) est libre : aucun
    événement gardé du mois n'est acheté ni en attente de son achat ; et aucun autre achat du même jour, plus gros (puis
    numéro plus petit), ne passe le filtre avec une compagnie qui n'est pas en portefeuille."""
    detenues = {p["cik"] for p in r["positions"]}
    if e["cik"] in detenues:
        return False
    if any(r["sort"].get(i) != "perdu" for i in r["gardes"].get(e["depot"][:7], [])):
        return False
    rang = (-(e.get("montant") or 0.0), e["id"])
    for x in ctx.evenements_marche(e["depot"]):
        if (x["depot"] == e["depot"] and x["id"] != e["id"] and x.get("sens") == "achat" and x.get("symbole")
                and (-(x.get("montant") or 0.0), x["id"]) < rang and x["cik"] not in detenues and _passe(x, ctx)):
            return False
    return True


def garder(e, ctx):
    if IMPOSSIBLE or e.get("sens") != "achat" or not e.get("symbole"):
        return False
    r = _rejeu(e, ctx)
    if e["depot"] < r["debut"] or not _passe(e, ctx) or not _premier_du_mois(e, ctx, r):
        return False
    r["gardes"].setdefault(e["depot"][:7], []).append(e["id"])
    r["a_venir"].append(e)
    return True
