"""critique-1 : achat d'un administrateur externe dans une compagnie d'au moins 1 G$, garder 12 mois.

Programmée par le VÉRIFICATEUR, sans voir labo/tournoi/regles/, d'après le texte de regles_preenregistrees.json.
"""
ID = "critique-1"

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat en bourse (code P) d'actions ordinaires » : un événement « achat » du jeu (code P, titres non dérivés). "
    "Le texte du champ « titres » n'est pas filtré : ce champ n'est pas dans la liste des champs de la règle.",
    "Plusieurs déclarants sur le formulaire : « roles » veut dire les rôles de TOUS les déclarants mis ensemble. Il faut "
    "« administrateur », et aucun déclarant ne doit être « dirigeant », « actionnaire de 10 % » ou « autre ».",
    "« Le champ titre du dirigeant est vide » : le titre de CHAQUE déclarant est vide (texte vide ou absent). Un titre "
    "comme « Chairman of the Board » ou « N/A » n'est pas vide : écarté.",
    "plan_10b5_1 : écarté seulement si « oui » (vrai). « Vide accepté avant avril 2023 » est lu comme une explication "
    "(la case n'existait pas avant) ; parametres_fixes dit seulement « plan_10b5_1 ≠ oui ». Donc vide accepté à toute date.",
    "routinier = oui : écarté. montant ou valeur_m inconnus : écarté (on ne peut pas savoir s'ils atteignent le seuil).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 : le 1er jour de bourse après le dépôt, sinon la 1re clôture "
    "des 5 jours de bourse suivants, sinon le signal est abandonné.",
    "Sortie : DUREE = 252 jours de bourse après l'achat et TOLERANCE_SORTIE = 20 : 1re clôture du 252e au 272e jour ; "
    "aucune : vente au dernier prix connu, faite le 272e jour.",
    "5 places (MAX_POSITIONS = 5) : la cible de 20 % est calculée par le banc sur la valeur (actions + SPY + liquide) "
    "du jour de l'achat, après les ventes du jour, une seule fois pour tous les achats du jour ; les frais (10 $, et "
    "10 $ si on vend du SPY) sont pris dans ces 20 %.",
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Au minimum 1 000 $ » : MONTANT_MIN = 1000, une position plus petite (pas assez d'argent) n'est pas achetée. "
    "Le banc ne peut pas acheter plus que l'argent disponible.",
    "« Pas de position déjà ouverte sur cette compagnie (cik_emetteur) » : le banc compare le SYMBOLE, pas le cik ; "
    "garder() ne voit pas le portefeuille. Une compagnie avec 2 symboles pourrait avoir 2 positions (rare).",
    "Places pleines le jour où le prix existe : signal ignoré (banc). Priorité au plus gros montant pour tous les "
    "signaux à acheter ce jour-là (le banc y met aussi ceux qui attendaient un prix) ; égalité : dépôt, puis numéro.",
    "Argent : ARGENT_QUI_ATTEND = « SPY » dès le départ ; LIQUIDE_JOURS = 10 (l'argent d'une vente attend 10 jours "
    "de bourse, puis va dans SPY) ; on paie avec le liquide d'abord, puis en vendant du SPY.",
    "Frais : le banc ajoute aussi le demi-écart achat-vente selon la taille (pareil pour toutes les règles) ; le texte "
    "ne parle que des 10 $ par transaction.",
    "Pas de vente anticipée, pas de seuil de perte, pas de météo : ni sortir_avant ni investir. "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0 (le texte ne demande pas de pause).",
    "Harmonisation (6 oct. 2026, avant tout résultat ; regles_du_jeu.md, « Changements », vers 12 h 30) : « d'actions "
    "ordinaires » est une condition du texte, appliquée comme dans vitesse-*, gestion-* et critique-3 : au moins un des "
    "titres déclarés (champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules ; seulement "
    "pour le formulaire qui donne le signal (l'historique de l'initié ne change pas). Testeur et vérificateur "
    "changés de la même façon (comparaison de la piste critique).",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « au minimum 1 000 $ » est lu comme un PLANCHER (le plus grand de 20 % et de 1 000 $), comme dans gestion-1 à 5 et critique-3 qui ont la même phrase ; un plancher ne se programme pas (une règle ne voit pas la valeur de son portefeuille) : MONTANT_MIN = 50, la valeur du banc. Effet seulement quand il reste moins de 1 000 $ pour une place.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 10
MONTANT_MIN = 50  # « au minimum 1 000 $ » = un plancher : voir CHOIX (harmonisation)
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

MONTANT_ACHAT_MIN = 25_000   # $
VALEUR_MIN_M = 1_000         # M$ (1 G$)
ROLES_EXCLUS = {"dirigeant", "actionnaire de 10 %", "autre"}


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    inities = e.get("inities") or []
    roles = set()
    for i in inities:
        roles.update(i.get("roles") or [])
    if "administrateur" not in roles or roles & ROLES_EXCLUS:
        return False
    if any((i.get("titre") or "").strip() for i in inities):
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant = e.get("montant")
    if montant is None or montant < MONTANT_ACHAT_MIN:
        return False
    valeur = e.get("valeur_m")
    if valeur is None or valeur < VALEUR_MIN_M:
        return False
    return _actions_ordinaires(e)


def priorite(e, ctx):
    """Plusieurs signaux le même jour : le plus gros montant d'abord."""
    return e.get("montant") or 0.0
