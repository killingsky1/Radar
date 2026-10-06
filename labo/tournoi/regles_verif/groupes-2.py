"""groupes-2 (programmation du VÉRIFICATEUR) : le PDG et le directeur financier achètent tous les deux en 10 jours,
garder 3 mois.

Programmée à partir du texte pré-enregistré seulement (regles_preenregistrees.json), sans voir celle du testeur.
"""
from datetime import date, timedelta

ID = "groupes-2"

CHOIX = [
    "Type PDG : titre qui contient « ceo » ou « chief executive » et PAS « cfo » (majuscules ignorées). Type DFO : titre "
    "qui contient « cfo » ou « chief financial ». « Ou l'inverse » : le déposant est du type DFO et l'autre du type PDG, "
    "avec les mêmes définitions (un titre « CEO and Chief Financial Officer » est des deux types).",
    "Titre = le champ titre du déclarant dans son propre formulaire. Plusieurs déclarants : il suffit d'une paire (un "
    "déclarant de chaque formulaire) de cik différents, l'un du type PDG et l'autre du type DFO.",
    "L'autre achat = un AUTRE formulaire 4 d'achat (numéro différent) sur la même compagnie (même cik de l'émetteur), "
    "déposé au plus tard le jour de la décision (le même jour compris, même s'il est lu après par le banc).",
    "Écart : |jour_premier du formulaire − jour_premier de l'autre| ≤ 10 jours civils ; jour_premier vide : pas gardé.",
    "Montant vide : pas gardé (pas « au moins 25 000 $ »).",
    "Routinier : le champ routinier de chacun des deux formulaires doit être faux (vide = non routinier).",
    "plan_10b5_1 : false ou vide accepté pour les deux formulaires ; true refusé.",
    "valeur_m ≥ 100 M$ : celle du formulaire de la décision (le plus récent des deux, celui qui est gardé) ; vide : pas "
    "gardé.",
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat en bourse (code P) d'actions ordinaires » : tout événement avec sens = achat ; le champ titres n'est pas "
    "filtré.",
    "Priorité (trop de signaux le même jour) : la somme achetée par les deux = montant du formulaire + le plus gros "
    "montant parmi les autres formulaires qui font une paire valable. Le banc applique cet ordre à tous les signaux qui "
    "attendent un achat ce jour-là.",
    "Condition (7) : un « signal » = un dépôt qui remplit toutes les conditions (la 7 comprise), acheté ou non (places "
    "pleines, pas de prix, période de contexte). « Sur ce symbole » = même symbole, toutes compagnies. « Dans les 90 "
    "jours civils avant » = déposé du jour moins 90 jours jusqu'au jour même ; le même jour, un dépôt lu avant par le banc "
    "(numéro plus petit) compte comme « avant ». Avant la période de contexte (1 an), aucun dépôt n'est connu.",
    "Entrée : JOURS_ENTREE = 1 (après le dépôt du 2e formulaire, celui qui est gardé) ; TOLERANCE_ENTREE = 5.",
    "Sortie : DUREE = 63 jours de bourse après l'achat. Le texte ne dit pas combien de temps chercher un prix de vente : "
    "comportement du banc (TOLERANCE_SORTIE = 10) : 1re clôture des 10 jours de bourse suivants, sinon la dernière "
    "clôture connue (« compagnie disparue »).",
    "Taille (comportement du banc) : 10 places ; montant = valeur du portefeuille ÷ 10, frais de 10 $ pris dedans ; une "
    "position de moins de 50 $ n'est pas achetée (MONTANT_MIN).",
    "Argent en attente dans SPY (LIQUIDE_JOURS = 0), 10 $ par transaction SPY : comportement du banc.",
    "Une seule position par compagnie : le banc le fait par symbole ; un signal sur un symbole déjà en portefeuille est "
    "ignoré.",
    "Frais et calculs du banc que le texte ne précise pas : demi-écart achat-vente selon la valeur en bourse (en plus des 10 $ par "
    "transaction), à l'achat et à la vente ; rendement enchaîné si le CUSIP change pendant la détention.",
    "CONCILIATION avec le testeur (6 octobre 2026, selon le texte ; même choix dans les deux fichiers) : (7) « pas "
    "d'autre signal groupes-2 SUR CE SYMBOLE » = même symbole, quelle que soit la compagnie (cik), comme ici ; le "
    "testeur, qui se limitait aux achats de la même compagnie, est corrigé. Aucun changement dans cette programmation.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

# Réglages du banc (texte : 10 positions de 10 %, entrée au 1er jour de bourse + 5 jours, 63 jours de bourse, SPY)
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 63
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

# Seuils du texte
ECART_JOURS = 10  # jours civils entre les premiers jours d'achat
MIN_MONTANT = 25_000  # $ chacun
MIN_VALEUR_M = 100  # M$
FENETRE_SIGNAL = 90  # jours civils

# Caches de CALCULS seulement : chaque valeur ne dépend que des dépôts faits au plus tard le jour du formulaire concerné
_memo_conditions = {}  # id → (conditions 1 à 6 remplies ?, somme des deux)
_memo_precedents = {}
_memo_signal = {}
_memo_index = {}


def _moins(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _date(x):
    try:
        return date.fromisoformat(x) if x else None
    except (TypeError, ValueError):
        return None


def _type_pdg(titre):
    t = (titre or "").lower()
    return ("ceo" in t or "chief executive" in t) and "cfo" not in t


def _type_dfo(titre):
    t = (titre or "").lower()
    return "cfo" in t or "chief financial" in t


def _achat_ok(x):
    """(3), (4), (5) pour un des deux formulaires, et un jour_premier lisible."""
    m = x.get("montant")
    return (x.get("sens") == "achat" and m is not None and m >= MIN_MONTANT and not x.get("routinier")
            and x.get("plan_10b5_1") is not True and _date(x.get("jour_premier")) is not None)


def _paire(x, y):
    """(1) : un déclarant de x et un de y, de cik différents, l'un du type PDG et l'autre du type DFO."""
    for i in x.get("inities") or []:
        for j in y.get("inities") or []:
            if i.get("cik") == j.get("cik"):
                continue
            a, b = i.get("titre"), j.get("titre")
            if (_type_pdg(a) and _type_dfo(b)) or (_type_dfo(a) and _type_pdg(b)):
                return True
    return False


def _conditions(x, ctx):
    """Conditions (1) à (6) pour le formulaire x (le plus récent des deux), avec seulement les dépôts faits au plus tard
    le jour de x."""
    k = x["id"]
    if k in _memo_conditions:
        return _memo_conditions[k]
    r = (False, 0.0)
    v = x.get("valeur_m")
    if (_achat_ok(x) and v is not None and v >= MIN_VALEUR_M
            and any(_type_pdg(i.get("titre")) or _type_dfo(i.get("titre")) for i in x.get("inities") or [])):
        jour, jp = x["depot"], _date(x["jour_premier"])
        meilleur = None
        for y in ctx.evenements_avant(x["cik"], "0000-00-00"):
            if y["depot"] > jour or y["id"] == x["id"] or not _achat_ok(y):
                continue
            if abs((_date(y["jour_premier"]) - jp).days) > ECART_JOURS:  # (2)
                continue
            if _paire(x, y) and (meilleur is None or y["montant"] > meilleur):
                meilleur = y["montant"]
        if meilleur is not None:
            r = (True, x["montant"] + meilleur)
    _memo_conditions[k] = r
    return r


def _index(jour, ctx):
    """Achats avec symbole déposés du jour − 90 jours au jour, par symbole (toutes compagnies)."""
    if jour not in _memo_index:
        if len(_memo_index) > 8:
            _memo_index.clear()
        idx = {}
        for z in ctx.evenements_marche(_moins(jour, FENETRE_SIGNAL)):
            if z["depot"] <= jour and z.get("sens") == "achat" and z.get("symbole"):
                idx.setdefault(z["symbole"], []).append(z)
        _memo_index[jour] = idx
    return _memo_index[jour]


def _precedents(y, ctx):
    if y["id"] not in _memo_precedents:
        cle = (y["depot"], y["id"])
        _memo_precedents[y["id"]] = [z for z in _index(y["depot"], ctx).get(y["symbole"], [])
                                     if (z["depot"], z["id"]) < cle and _conditions(z, ctx)[0]]
    return _memo_precedents[y["id"]]


def _est_signal(x, ctx):
    """Conditions (1) à (7). Calcul sans récursion : les signaux d'avant sont trouvés d'abord."""
    if x["id"] in _memo_signal:
        return _memo_signal[x["id"]]
    if not x.get("symbole") or not _conditions(x, ctx)[0]:
        _memo_signal[x["id"]] = False
        return False
    pile = [x]
    while pile:
        y = pile[-1]
        if y["id"] in _memo_signal:
            pile.pop()
            continue
        avant = _precedents(y, ctx)
        manquants = [z for z in avant if z["id"] not in _memo_signal]
        if manquants:
            pile.extend(manquants)
            continue
        _memo_signal[y["id"]] = not any(_memo_signal[z["id"]] for z in avant)  # (7)
        pile.pop()
    return _memo_signal[x["id"]]


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    return _est_signal(e, ctx) and _actions_ordinaires(e)


def priorite(e, ctx):
    return _conditions(e, ctx)[1]
