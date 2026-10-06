"""initie-1-pdg-dfo : achat non routinier du PDG ou du directeur financier (programmation du VÉRIFICATEUR).

Texte pré-enregistré (regles_preenregistrees.json) : achat P d'actions ordinaires ; le titre contient (majuscules
ignorées) CEO, Chief Executive ou Principal Executive, ou bien CFO, Chief Financial ou Principal Financial ;
« President » seul ne compte pas ; routinier = non ; plan_10b5_1 différent de oui ; montant ≥ 25 000 $ ; valeur_m entre
100 et 2 000 M$ ; pas d'action déjà en portefeuille ; le même jour : directeur financier d'abord, puis le plus gros
montant. Entrée : 1er jour de bourse après le dépôt, sinon 1er prix des 5 jours de bourse suivants. Sortie : 126e jour
de bourse après l'achat, sinon 1er prix des 10 jours suivants, sinon dernier prix connu. 5 positions de 20 %, argent
qui attend dans SPY, 10 $ par transaction (SPY compris).
"""

ID = "initie-1-pdg-dfo"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu (code P, titres non dérivés). Le champ « titres » "
    "n'est pas filtré : il n'est pas dans les champs de la règle.",
    "Titre : un déclarant (e['inities'][i]['titre']) dont le texte contient, sans tenir compte des majuscules, « ceo », "
    "« chief executive », « principal executive », « cfo », « chief financial » ou « principal financial ». Simple "
    "recherche de texte, sans autre nettoyage. « President » seul ne contient aucun de ces mots, donc ne compte pas.",
    "Le champ « roles » n'est pas vérifié à part : le filtre de cette règle ne demande que le titre (un titre de PDG ou "
    "de directeur financier fait déjà de l'initié un dirigeant).",
    "Plusieurs déclarants sur le formulaire : il suffit qu'UN déclarant ait un titre de PDG ou de directeur financier.",
    "routinier = non : e['routinier'] faux. plan_10b5_1 différent de oui : true refusé ; false et vide (null) acceptés à "
    "TOUTES les dates (« vide accepté avant avril 2023 » est lu comme une précision, pas comme un refus du vide après).",
    "montant ≥ 25 000 $ et 100 ≤ valeur_m ≤ 2 000 (M$), bornes comprises ; montant ou valeur_m absent = refusé.",
    "Priorité le même jour : directeur financier d'abord (un déclarant dont le titre contient cfo, chief financial ou "
    "principal financial ; un « CEO and CFO » compte donc comme directeur financier), puis le plus gros montant. Calcul : "
    "10^12 si directeur financier, plus le montant (plafonné à 10^12 − 1 dans ce calcul). Égalité : ordre du banc "
    "(dépôt, puis numéro).",
    "Entrée : JOURS_ENTREE = 1 (clôture du 1er jour de bourse après le dépôt) ; TOLERANCE_ENTREE = 5 (sans prix, le banc "
    "réessaie les 5 jours de bourse suivants, sinon le signal tombe).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat réel ; TOLERANCE_SORTIE = 10 (1er prix des 10 jours de "
    "bourse suivants, sinon dernier prix connu, comme le texte). Pas de sortir_avant (pas de vente anticipée).",
    "Taille : MAX_POSITIONS = 5 (20 % de la valeur du portefeuille, actions + SPY) ; ARGENT_QUI_ATTEND = « SPY » ; "
    "LIQUIDE_JOURS = 0 (le produit d'une vente retourne dans SPY le jour même) ; UNE_ENTREE_PAR_SYMBOLE_JOURS = 0.",
    "Places pleines : le banc laisse tomber le signal (« ignoré »). Action déjà en portefeuille : le banc ne l'achète pas.",
    "Banc, différent du texte : il ajoute un demi-écart achat-vente selon la valeur en bourse (1 % à 0,05 %) à l'achat "
    "et à la vente, en plus des 10 $.",
    "Banc, différent du texte : la position vaut 20 % de la valeur du portefeuille moins 10 $ de frais ; s'il reste moins "
    "d'argent que 20 %, il achète plus petit ; sous MONTANT_MIN = 50 $ (défaut du banc), pas d'achat.",
    "Banc, différent du texte : la priorité du même jour classe aussi les signaux qui attendent encore un prix depuis les "
    "jours d'avant (le banc les trie tous ensemble) ; un changement de CUSIP pendant la détention donne un rendement "
    "enchaîné.",
    "Comparaison des deux programmations (jeu ciblé : 7 achats de 110 à 170 G$ le même jour, 5 places) : le testeur "
    "plafonnait le montant de la priorité à 100 G$, le vérificateur à 10^12 − 1 $ ; au-dessus de 100 G$, les signaux "
    "du même jour étaient donc classés autrement. Le texte dit « le plus gros montant » : on garde le plafond le plus "
    "haut, 10^12 − 1 $, dans les deux (testeur corrigé). Au-delà, deux montants comptent comme égaux (ordre du banc).",
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

MOTS_PDG = ("ceo", "chief executive", "principal executive")
MOTS_DFO = ("cfo", "chief financial", "principal financial")


def _titre_contient(initie, mots):
    t = (initie.get("titre") or "").lower()
    return any(m in t for m in mots)


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


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e, 25_000):
        return False
    return (any(_titre_contient(i, MOTS_PDG) or _titre_contient(i, MOTS_DFO) for i in e.get("inities") or [])
            and _actions_ordinaires(e))


def priorite(e, ctx):
    dfo = any(_titre_contient(i, MOTS_DFO) for i in e.get("inities") or [])
    return (1e12 if dfo else 0.0) + min(float(e.get("montant") or 0.0), 1e12 - 1)
