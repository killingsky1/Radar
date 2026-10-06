"""initie-4-engagement : gros engagement, l'initié augmente beaucoup ce qu'il détient (programmation du VÉRIFICATEUR).

Texte pré-enregistré (regles_preenregistrees.json) : achat P d'actions ordinaires ; roles contient dirigeant ou
administrateur (pas un actionnaire de 10 % seul) ; routinier = non ; plan_10b5_1 différent de oui ; montant ≥ 100 000 $ ;
part_ajoutee ≥ 0,20 (un achat sans actions détenues avant compte comme rempli) ; valeur_m entre 100 et 2 000 M$ ; pas
d'action déjà en portefeuille ; le même jour : part_ajoutee la plus élevée d'abord. Entrée, sortie, taille : comme
initie-1 (126 jours de bourse, 5 positions de 20 %, SPY).
"""

ID = "initie-4-engagement"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu (code P, titres non dérivés). Le champ « titres » "
    "n'est pas filtré : il n'est pas dans les champs de la règle.",
    "roles contient « dirigeant » ou « administrateur » chez au moins un déclarant (un actionnaire de 10 % seul ou "
    "« autre » seul est exclu).",
    "routinier = non : e['routinier'] faux. plan_10b5_1 différent de oui : true refusé ; false et vide (null) acceptés.",
    "montant ≥ 100 000 $ et 100 ≤ valeur_m ≤ 2 000 (M$), bornes comprises ; montant ou valeur_m absent = refusé.",
    "part_ajoutee = e['part'] (actions achetées ÷ détenues avant) ≥ 0,20 ; ou bien e['nouvelle_position'] vrai (aucune "
    "action détenue avant : critère rempli, comme le texte). Détenues avant inconnues (e['avant'] absent, donc part "
    "vide sans nouvelle position) : critère pas rempli, refusé.",
    "Le champ « apres » est dans la liste des champs mais aucun seuil du texte ne s'en sert : pas utilisé.",
    "Priorité le même jour : la plus grande part_ajoutee ; une nouvelle position (rien avant) compte comme la plus grande "
    "part (division par zéro = infinie). Calcul : l'infini pour une nouvelle position, sinon la part (sans plafond). "
    "Égalité : ordre du banc (dépôt, numéro).",
    "Entrée : JOURS_ENTREE = 1 ; TOLERANCE_ENTREE = 5 (sans prix, 5 jours de bourse de plus, sinon le signal tombe).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat réel ; TOLERANCE_SORTIE = 10 (puis dernier prix connu).",
    "Taille : MAX_POSITIONS = 5 (20 %) ; ARGENT_QUI_ATTEND = « SPY » ; LIQUIDE_JOURS = 0 ; "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0. Places pleines : signal laissé tomber. Déjà en portefeuille : pas acheté.",
    "Banc, différent du texte : demi-écart achat-vente selon la valeur en bourse, à l'achat et à la vente, en plus des "
    "10 $ ; position = 20 % moins 10 $, plus petite s'il manque d'argent (sous MONTANT_MIN = 50 $, défaut du banc : pas "
    "d'achat) ; la priorité classe aussi les signaux qui attendent encore un prix ; rendement enchaîné si le CUSIP change.",
    "Comparaison des deux programmations (jeu ciblé : 7 achats le même jour, parts de 2 à 8 millions, 5 places) : le "
    "vérificateur plafonnait la part de la priorité à 999 999 (nouvelle position : 10^6), donc ces signaux étaient à "
    "égalité chez lui (ordre du banc) et classés par part chez le testeur. Le texte dit « part_ajoutee la plus élevée "
    "d'abord » : pas de plafond, et une nouvelle position compte comme une part infinie. Vérificateur corrigé.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

JOURS_ENTREE = 1
DUREE = 126
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
TOLERANCE_ENTREE = 5
TOLERANCE_SORTIE = 10
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

PART_MIN = 0.20


def _base(e, montant_min):
    """La base commune de la piste : achat P, non routinier, hors plan 10b5-1, montant, taille de la compagnie."""
    if e.get("sens") != "achat":
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    m = e.get("montant")
    if m is None or m < montant_min:
        return False
    v = e.get("valeur_m")
    if v is None or v < 100 or v > 2000:
        return False
    return True


def _dirigeant_ou_administrateur(initie):
    roles = initie.get("roles") or []
    return "dirigeant" in roles or "administrateur" in roles


def _part(e):
    """part_ajoutee pour le filtre et la priorité : l'infini pour une nouvelle position (rien avant), None si inconnue."""
    if e.get("part") is not None:
        return float(e["part"])
    if e.get("nouvelle_position"):
        return float("inf")
    return None


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e, 100_000):
        return False
    if not any(_dirigeant_ou_administrateur(i) for i in e.get("inities") or []):
        return False
    p = _part(e)
    return p is not None and p >= PART_MIN and _actions_ordinaires(e)


def priorite(e, ctx):
    return _part(e) or 0.0
