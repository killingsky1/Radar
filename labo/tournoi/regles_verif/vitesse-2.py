"""vitesse-2 : achat d'initié loin sous le plus haut de 52 semaines, garder 2 jours de bourse après l'entrée.

Programmée par le VÉRIFICATEUR, sans voir le programme du testeur, d'après regles_preenregistrees.json (texte des
chercheurs : filtre, entrée, sortie, taille). Les choix faits quand le texte est ambigu, ou quand le banc fait autrement
que le texte, sont dans CHOIX.
"""
from datetime import date, timedelta

ID = "vitesse-2"
IMPOSSIBLE = None

CHOIX = [
    "« Achat code P d'actions ordinaires » : un événement « achat » (code P) dont au moins un des titres déclarés "
    "(champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules (ex. « Common Stock », "
    "« Class A Common Stock », « Ordinary Shares »). Un titre sans ces mots (privilégiées, unités, « Shares » seul, "
    "etc.) est refusé.",
    "« Par un administrateur ou un dirigeant (pas un simple actionnaire de 10 %) » : au moins UN des déclarants du "
    "formulaire a le rôle administrateur ou dirigeant.",
    "Montant ≥ 50 000 $ (montant du formulaire ; inconnu = écarté). routinier = non : routinier faux. "
    "plan_10b5_1 ≠ oui : vrai = écarté ; faux et vide acceptés.",
    "valeur_m entre 100 et 1 000 M$ : bornes comprises. Valeur inconnue = écarté.",
    "« Plus haut » : la plus haute clôture SEC du symbole de l'événement, du jour_premier moins 365 jours au "
    "jour_premier moins 1 jour (365 jours civils, bornes comprises). Toutes les clôtures de cette période comptent, "
    "même si le CUSIP a changé (le texte ne parle pas des regroupements d'actions).",
    "Au moins 20 clôtures SEC dans cette période (même compte, tous CUSIP), sinon écarté. prix_moyen ou jour_premier "
    "inconnu = écarté.",
    "Rapport prix_moyen ÷ plus haut ≤ 0,60 (0,60 compris).",
    "jour_premier plus d'un jour après le dépôt (erreur de date) : écarté, car la période du plus haut finirait après "
    "le dépôt (des prix pas encore connus au moment de décider).",
    "« Une seule entrée par symbole sur 30 jours civils » : réglage du banc UNE_ENTREE_PAR_SYMBOLE_JOURS = 30, compté "
    "depuis le jour d'achat (un signal qui n'a pas été acheté ne bloque rien).",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt ; pas de prix ce jour-là = pas d'achat "
    "(TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 2e jour de bourse après l'entrée (DUREE = 2). Pas de prix ce jour-là : le banc prend la 1re "
    "clôture des 10 jours de bourse suivants, sinon la dernière clôture connue (compagnie « disparue ») : réglage "
    "standard du banc (TOLERANCE_SORTIE = 10), le texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc met la valeur du portefeuille ÷ 2 dans chaque position "
    "(5 000 $ au départ, puis selon la valeur du portefeuille), pas 5 000 $ fixes.",
    "Argent en attente dans SPY, sans garder de liquide (LIQUIDE_JOURS = 0) : 4 transactions de 10 $ par aller-retour. "
    "Le banc compte aussi le demi-écart achat-vente selon la valeur en bourse, comme pour toutes les règles.",
    "Priorité : le rapport prix_moyen ÷ plus haut le plus bas d'abord (priorite = − rapport) ; à égalité, l'ordre du "
    "banc (dépôt, puis numéro). Signaux sans place : abandonnés (le banc ne les garde pas pour plus tard).",
    "Une seule position par symbole à la fois : fait par le banc. Formulaire sans symbole : jamais gardé.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus "
    "(« common » ou « ordinary »). Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
]

JOURS_ENTREE = 1
DUREE = 2
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
TOLERANCE_ENTREE = 0
TOLERANCE_SORTIE = 10
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 30

MONTANT_MINIMUM = 50_000
VALEUR_MIN, VALEUR_MAX = 100, 1000
RAPPORT_MAX = 0.60
CLOTURES_MIN = 20
JOURS_CIVILS = 365


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _role_ok(e):
    return any(r in ("administrateur", "dirigeant") for i in e.get("inities") or [] for r in i.get("roles") or [])


def _rapport(e, ctx):
    """prix_moyen ÷ la plus haute clôture SEC des 365 jours civils qui finissent la veille du jour_premier ; None si
    ce n'est pas calculable (prix ou date inconnus, moins de 20 clôtures, période qui finit après le dépôt)."""
    premier, prix_moyen = e.get("jour_premier"), e.get("prix_moyen")
    if not premier or prix_moyen is None:
        return None
    j = date.fromisoformat(premier)
    debut = (j - timedelta(days=JOURS_CIVILS)).isoformat()
    fin = (j - timedelta(days=1)).isoformat()
    if fin > ctx.jour:
        return None
    clotures = ctx.clotures(e["symbole"], debut, fin)
    if len(clotures) < CLOTURES_MIN:
        return None
    haut = max(p for _, p, _ in clotures)
    if not haut or haut <= 0:
        return None
    return prix_moyen / haut


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e) or not _role_ok(e):
        return False
    montant = e.get("montant")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    valeur = e.get("valeur_m")
    if valeur is None or not (VALEUR_MIN <= valeur <= VALEUR_MAX):
        return False
    rapport = _rapport(e, ctx)
    return rapport is not None and rapport <= RAPPORT_MAX


def priorite(e, ctx):
    rapport = _rapport(e, ctx)
    return -rapport if rapport is not None else float("-inf")
