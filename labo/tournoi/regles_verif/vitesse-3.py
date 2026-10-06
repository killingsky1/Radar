"""vitesse-3 : achats en groupe (3 initiés ou plus en 30 jours), garder 10 jours de bourse.

Programmée par le VÉRIFICATEUR, sans voir le programme du testeur, d'après regles_preenregistrees.json (texte des
chercheurs : filtre, entrée, sortie, taille). Les choix faits quand le texte est ambigu, ou quand le banc fait autrement
que le texte, sont dans CHOIX.
"""
from datetime import date, timedelta

ID = "vitesse-3"
IMPOSSIBLE = None

CHOIX = [
    "« Achat code P d'actions ordinaires » : le formulaire qui donne le signal est un événement « achat » (code P) dont "
    "au moins un des titres déclarés (champ titres) contient « common » ou « ordinary », sans tenir compte des "
    "majuscules (ex. « Common Stock », « Class A Common Stock », « Ordinary Shares ») ; un titre sans ces mots "
    "(privilégiées, unités, « Shares » seul, etc.) est refusé. Le groupe compte tous les formulaires d'achat de la "
    "compagnie, quel que soit le titre (comme groupe_30j).",
    "« groupe ≥ 2 (au moins 2 AUTRES initiés, donc 3 acheteurs ou plus) » : le champ groupe_30j compte l'initié du "
    "formulaire lui-même (dictionnaire : « celui-ci compris »), donc le seuil appliqué est groupe_30j ≥ 3, comme le "
    "prévoit la note de testabilité de la règle (« sinon utiliser groupe ≥ 3 »).",
    "« Le premier formulaire qui fait atteindre ce seuil » : un achat avec groupe_30j ≥ 3 dont l'achat précédent sur la "
    "même compagnie (ordre du banc : dépôt, puis numéro ; formulaires de tous les initiés), déposé dans les 30 jours "
    "civils avant (même jour compris), avait un groupe_30j de moins de 3 — ou qui n'a aucun achat précédent dans ces "
    "30 jours. Plusieurs formulaires le même jour ont tous groupe ≥ 3 : seul le premier dans l'ordre du banc compte.",
    "Les conditions sur « ce formulaire » (montant ≥ 25 000 $, routinier faux, plan_10b5_1 différent de vrai, "
    "valeur_m de 100 à 3 000 M$ bornes comprises ; montant ou valeur inconnus = écarté) sont vérifiées sur ce premier "
    "formulaire seulement : s'il ne les remplit pas, pas de signal pour ce groupe (on ne prend pas le formulaire suivant "
    "du même groupe, qui ne « fait » pas atteindre le seuil).",
    "« Au moins un des acheteurs du groupe (en comptant celui-ci) est dirigeant ou administrateur » : un déclarant d'un "
    "des achats de la même compagnie déposés dans les 30 jours civils avant (jour du dépôt compris, les mêmes "
    "formulaires que ceux comptés dans groupe_30j) a le rôle dirigeant ou administrateur.",
    "« Puis plus aucune entrée sur ce symbole pendant 60 jours civils » : réglage du banc "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 60, compté depuis le jour d'achat (un signal qui n'a pas été acheté ne bloque pas "
    "un nouveau passage du seuil).",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt du formulaire qui déclenche ; pas de prix ce jour-là = pas "
    "d'achat (TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 10e jour de bourse après l'entrée (DUREE = 10). Pas de prix ce jour-là : le banc prend la 1re "
    "clôture des 10 jours de bourse suivants, sinon la dernière clôture connue (compagnie « disparue ») : réglage "
    "standard du banc (TOLERANCE_SORTIE = 10), le texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc met la valeur du portefeuille ÷ 2 dans chaque position "
    "(5 000 $ au départ, puis selon la valeur du portefeuille), pas 5 000 $ fixes.",
    "Argent en attente dans SPY, sans garder de liquide (LIQUIDE_JOURS = 0) : 4 transactions de 10 $ par aller-retour. "
    "Le banc compte aussi le demi-écart achat-vente selon la valeur en bourse, comme pour toutes les règles.",
    "Priorité : le groupe_30j le plus grand, puis le plus gros montant du formulaire (priorite = groupe × 10^13 + "
    "montant) ; à égalité, l'ordre du banc. Signaux sans place : abandonnés (le banc ne les garde pas pour plus tard).",
    "Une seule position par symbole à la fois : fait par le banc. Formulaire sans symbole : jamais gardé.",
    "Comparaison testeur/vérificateur (6 oct. 2026), 1) « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus. "
    "Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
    "Comparaison testeur/vérificateur (6 oct. 2026), 2) « On prend seulement le premier formulaire qui fait atteindre "
    "ce seuil » : lecture retenue (la plus simple, celle du vérificateur) : UN seul formulaire par groupe, le premier "
    "dans l'ordre où le banc lit les dépôts (dépôt, puis numéro) dont le groupe atteint le seuil alors que l'achat "
    "précédent de la compagnie (déposé dans les 30 jours) ne l'atteignait pas. Le testeur prenait comme « premiers » "
    "tous les formulaires du même jour (le banc achetait alors le plus gros montant, même quand le premier n'avait pas "
    "25 000 $) et redonnait un signal quand un initié sortait de la fenêtre de 30 jours entre deux dépôts du même "
    "groupe : corrigé dans sa programmation.",
]

JOURS_ENTREE = 1
DUREE = 10
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
TOLERANCE_ENTREE = 0
TOLERANCE_SORTIE = 10
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 60

SEUIL_GROUPE = 3  # groupe_30j compte l'initié lui-même : 2 AUTRES initiés = 3 acheteurs
JOURS_GROUPE = 30
MONTANT_MINIMUM = 25_000
VALEUR_MIN, VALEUR_MAX = 100, 3000


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _achats_du_groupe(e, ctx):
    """Les achats de la même compagnie déposés dans les 30 jours civils avant le dépôt (jour du dépôt compris), dans
    l'ordre du banc : les formulaires comptés dans groupe_30j."""
    depuis = (date.fromisoformat(e["depot"]) - timedelta(days=JOURS_GROUPE)).isoformat()
    return [x for x in ctx.evenements_avant(e["cik"], depuis) if x.get("sens") == "achat"]


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e):
        return False
    if (e.get("groupe_30j") or 0) < SEUIL_GROUPE:
        return False
    groupe = _achats_du_groupe(e, ctx)
    precedents = [x for x in groupe if (x["depot"], x["id"]) < (e["depot"], e["id"])]
    if precedents and (precedents[-1].get("groupe_30j") or 0) >= SEUIL_GROUPE:
        return False  # le seuil était déjà atteint : ce n'est pas le premier formulaire
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
    return any(r in ("dirigeant", "administrateur")
               for x in groupe for i in x.get("inities") or [] for r in i.get("roles") or [])


def priorite(e, ctx):
    return (e.get("groupe_30j") or 0) * 1e13 + min(e.get("montant") or 0.0, 1e13 - 1)
