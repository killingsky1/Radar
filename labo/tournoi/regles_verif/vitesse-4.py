"""vitesse-4 : initié qui augmente fortement sa participation, garder 10 jours de bourse.

Programmée par le VÉRIFICATEUR, sans voir le programme du testeur, d'après regles_preenregistrees.json (texte des
chercheurs : filtre, entrée, sortie, taille). Les choix faits quand le texte est ambigu, ou quand le banc fait autrement
que le texte, sont dans CHOIX.
"""

ID = "vitesse-4"
IMPOSSIBLE = None

CHOIX = [
    "« Achat code P d'actions ordinaires » : un événement « achat » (code P) dont au moins un des titres déclarés "
    "(champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules (ex. « Common Stock », "
    "« Class A Common Stock », « Ordinary Shares »). Un titre sans ces mots (privilégiées, unités, « Shares » seul, "
    "etc.) est refusé.",
    "« Par un dirigeant ou un administrateur » : au moins UN des déclarants du formulaire a le rôle dirigeant ou "
    "administrateur.",
    "direct = oui : le champ direct est vrai (au moins une ligne d'achat détenue directement).",
    "part_ajoutee = le champ part (actions achetées ÷ détenues avant, dans le plus gros groupe de lignes) ; il faut "
    "part ≥ 0,25 (0,25 compris). part inconnue (rien détenu avant, ou déclaration incohérente) = écarté, comme le dit "
    "la note de testabilité.",
    "Montant ≥ 50 000 $ (montant du formulaire ; inconnu = écarté). routinier = non : routinier faux. "
    "plan_10b5_1 ≠ oui : vrai = écarté ; faux et vide acceptés.",
    "valeur_m entre 100 et 2 000 M$ : bornes comprises. Valeur inconnue = écarté.",
    "« Une seule entrée par symbole sur 30 jours civils » : réglage du banc UNE_ENTREE_PAR_SYMBOLE_JOURS = 30, compté "
    "depuis le jour d'achat (un signal qui n'a pas été acheté ne bloque rien).",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt ; pas de prix ce jour-là = pas d'achat "
    "(TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 10e jour de bourse après l'entrée (DUREE = 10). Pas de prix ce jour-là : le banc prend la 1re "
    "clôture des 10 jours de bourse suivants, sinon la dernière clôture connue (compagnie « disparue ») : réglage "
    "standard du banc (TOLERANCE_SORTIE = 10), le texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc met la valeur du portefeuille ÷ 2 dans chaque position "
    "(5 000 $ au départ, puis selon la valeur du portefeuille), pas 5 000 $ fixes.",
    "Argent en attente dans SPY, sans garder de liquide (LIQUIDE_JOURS = 0) : 4 transactions de 10 $ par aller-retour. "
    "Le banc compte aussi le demi-écart achat-vente selon la valeur en bourse, comme pour toutes les règles.",
    "Priorité : la plus forte part_ajoutee d'abord (priorite = part) ; à égalité, l'ordre du banc (dépôt, puis "
    "numéro). Signaux sans place : abandonnés (le banc ne les garde pas pour plus tard).",
    "Une seule position par symbole à la fois : fait par le banc. Formulaire sans symbole : jamais gardé.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus "
    "(« common » ou « ordinary »). Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
]

JOURS_ENTREE = 1
DUREE = 10
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
TOLERANCE_ENTREE = 0
TOLERANCE_SORTIE = 10
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 30

PART_MIN = 0.25
MONTANT_MINIMUM = 50_000
VALEUR_MIN, VALEUR_MAX = 100, 2000


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _role_ok(e):
    return any(r in ("dirigeant", "administrateur") for i in e.get("inities") or [] for r in i.get("roles") or [])


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e) or not _role_ok(e):
        return False
    if e.get("direct") is not True:
        return False
    part = e.get("part")
    if part is None or part < PART_MIN:
        return False
    montant = e.get("montant")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    valeur = e.get("valeur_m")
    return valeur is not None and VALEUR_MIN <= valeur <= VALEUR_MAX


def priorite(e, ctx):
    part = e.get("part")
    return part if part is not None else float("-inf")
