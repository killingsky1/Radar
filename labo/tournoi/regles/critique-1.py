"""critique-1 : achat d'un administrateur externe dans une compagnie d'au moins 1 G$, garder 12 mois.

Texte pré-enregistré : labo/tournoi/regles_preenregistrees.json, partie « regles », id « critique-1 ».
Programmée telle qu'écrite (seuils du texte) ; chaque choix est dans CHOIX.
"""
ID = "critique-1"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat en bourse (code P) d'actions ordinaires » = un événement dont le sens est « achat » (code P, titres non "
    "dérivés). Le champ « titres » n'est pas filtré : il n'est pas dans la liste des champs de la règle et le jeu ne "
    "classe pas les titres.",
    "Plusieurs déclarants sur le formulaire : les rôles du formulaire sont ceux de TOUS ses déclarants réunis. Il faut "
    "« administrateur » et aucun « dirigeant », « actionnaire de 10 % » ni « autre » chez aucun déclarant.",
    "« Le champ titre du dirigeant est vide » : le titre de CHAQUE déclarant doit être vide (absent ou seulement des "
    "espaces). Un titre écrit, même « Director » ou « N/A », n'est pas vide.",
    "routinier = non : gardé seulement si routinier vaut False.",
    "plan_10b5_1 différent de « oui » : gardé si False ou vide (None), à toutes les dates. « (vide accepté avant avril "
    "2023) » est lu comme une explication (la case existe depuis avril 2023), pas comme un refus des cases vides après "
    "avril 2023 ; les paramètres fixés disent seulement « plan_10b5_1 ≠ oui ».",
    "montant ou valeur_m inconnu (None) : écarté, le seuil ne peut pas être vérifié.",
    "« Pas de position déjà ouverte sur cette compagnie (cik_emetteur) » : fait par le banc, qui vérifie le SYMBOLE, pas "
    "le cik (garder() ne voit pas le portefeuille). Une compagnie avec deux symboles pourrait avoir deux positions (rare).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (clôture SEC du 1er jour de bourse après le dépôt, sinon la 1re "
    "clôture SEC des 5 jours de bourse suivants, sinon l'événement est laissé tomber).",
    "Sortie : DUREE = 252 et TOLERANCE_SORTIE = 20 (1re clôture SEC à partir du 252e jour de bourse après l'achat ; "
    "aucun prix pendant les 20 jours de bourse suivants : dernière clôture SEC connue). Pas de sortir_avant().",
    "Taille : MAX_POSITIONS = 5, donc 20 % de la valeur du portefeuille (actions + SPY + liquide), calculée par le banc "
    "le jour de l'achat après les ventes du jour ; le banc prend les 10 $ de frais dans ces 20 %. S'il manque d'argent "
    "(les autres positions ont monté), le banc achète avec ce qui reste.",
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « au minimum 1 000 $ » : MONTANT_MIN = 1000, une position de moins de 1 000 $ n'est pas achetée (le banc ne peut "
    "pas monter un achat jusqu'à 1 000 $).",
    "Liquide : LIQUIDE_JOURS = 10 et ARGENT_QUI_ATTEND = « SPY » (l'argent d'une vente attend 10 jours de bourse, "
    "sert d'abord à payer, puis va dans SPY).",
    "Priorité : le plus gros montant d'abord. Le banc applique cet ordre à tous les signaux du jour, y compris ceux qui "
    "attendent un prix depuis un jour précédent ; à égalité : date de dépôt, puis numéro.",
    "Comportements standard du banc, pas dans le texte : demi-écart achat-vente selon la valeur en bourse (à l'achat et à "
    "la vente) en plus des 10 $ ; le premier placement dans SPY au départ se fait sans frais de 10 $ ; changement de "
    "CUSIP pendant la détention : rendement enchaîné.",
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

MONTANT_MINIMUM = 25_000  # $
VALEUR_MINIMUM = 1_000  # M$
ROLES_EXCLUS = {"dirigeant", "actionnaire de 10 %", "autre"}


def _vide(texte):
    return not (texte or "").strip()


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    inities = e.get("inities") or []
    if not inities:
        return False
    roles = {r for i in inities for r in (i.get("roles") or [])}
    if "administrateur" not in roles or roles & ROLES_EXCLUS:
        return False
    if not all(_vide(i.get("titre")) for i in inities):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant = e.get("montant")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    valeur = e.get("valeur_m")
    if valeur is None or valeur < VALEUR_MINIMUM:
        return False
    return _actions_ordinaires(e)


def priorite(e, ctx):
    """Plusieurs signaux le même jour : le plus gros montant d'abord."""
    return float(e.get("montant") or 0.0)
