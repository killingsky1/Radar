"""critique-2 : achat d'un initié « à horizon court » (qui alterne achats et ventes), garder 6 mois.

Programmée par le VÉRIFICATEUR, sans voir labo/tournoi/regles/, d'après le texte de regles_preenregistrees.json.
"""
from fractions import Fraction

ID = "critique-2"

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat en bourse (code P) d'actions ordinaires » : un événement « achat » du jeu (code P, titres non dérivés). "
    "Le texte du champ « titres » n'est pas filtré : ce champ n'est pas dans la liste des champs de la règle.",
    "Rôles : au moins un déclarant du formulaire est « administrateur » ou « dirigeant » (un formulaire avec seulement "
    "des « actionnaire de 10 % » ou « autre » est écarté).",
    "Plusieurs déclarants : l'horizon H est calculé pour chaque déclarant qui est administrateur ou dirigeant. "
    "L'événement est gardé si au moins un d'eux a 3 années avec un F et H ≤ 0,5 ; s'il y en a plusieurs, c'est le plus "
    "petit H qui compte (aussi pour la priorité).",
    "Historique : ctx.historique_initie(cik de l'initié), seulement les lignes de la même compagnie (cik = e['cik']). "
    "L'année d'un dépôt passé = l'année de sa date de DÉPÔT ; on prend les 10 années civiles avant l'année du dépôt "
    "actuel (dépôt de 2024 : années 2014 à 2023).",
    "F d'une année = (lignes « achat » − lignes « vente ») ÷ (lignes « achat » + lignes « vente ») ; l'historique a une "
    "ligne par dépôt original et par sens, donc un dépôt avec achat et vente compte des deux côtés (comme le dit la note).",
    "H = valeur absolue de la moyenne des F, calculée en fractions exactes : H = 0,5 tout juste est gardé (ex. du texte).",
    "plan_10b5_1 : écarté seulement si « oui » (vrai) ; vide accepté. routinier = oui : écarté. montant ou valeur_m "
    "inconnus : écarté.",
    "Priorité : le plus petit H, puis le plus gros montant, mis dans un seul nombre entier exact (le banc trie sur un "
    "nombre) ; égalité complète : dépôt, puis numéro (banc).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 : le 1er jour de bourse après le dépôt, sinon la 1re clôture "
    "des 5 jours de bourse suivants, sinon le signal est abandonné.",
    "Sortie : DUREE = 126 jours de bourse après l'achat et TOLERANCE_SORTIE = 20 : 1re clôture du 126e au 146e jour ; "
    "aucune : vente au dernier prix connu, faite le 146e jour.",
    "5 places (MAX_POSITIONS = 5) : la cible de 20 % est calculée par le banc sur la valeur (actions + SPY + liquide) "
    "du jour de l'achat, après les ventes du jour, une seule fois pour tous les achats du jour ; les frais (10 $, et "
    "10 $ si on vend du SPY) sont pris dans ces 20 %.",
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Au minimum 1 000 $ » : MONTANT_MIN = 1000, une position plus petite (pas assez d'argent) n'est pas achetée. "
    "Le banc ne peut pas acheter plus que l'argent disponible.",
    "« Pas de position déjà ouverte sur cette compagnie » : le banc compare le SYMBOLE, pas le cik ; garder() ne voit "
    "pas le portefeuille. Une compagnie avec 2 symboles pourrait avoir 2 positions (rare).",
    "Places pleines le jour où le prix existe : signal ignoré (banc). Le banc range par priorité tous les signaux à "
    "acheter ce jour-là, y compris ceux qui attendaient un prix depuis un jour précédent.",
    "Argent : ARGENT_QUI_ATTEND = « SPY » dès le départ ; LIQUIDE_JOURS = 10 (l'argent d'une vente attend 10 jours "
    "de bourse, puis va dans SPY) ; on paie avec le liquide d'abord, puis en vendant du SPY.",
    "Frais : le banc ajoute aussi le demi-écart achat-vente selon la taille (pareil pour toutes les règles) ; le texte "
    "ne parle que des 10 $ par transaction.",
    "Pas de vente anticipée, pas de seuil de perte, pas de météo : ni sortir_avant ni investir. "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0 (le texte ne demande pas de pause).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : écart corrigé dans le fichier du TESTEUR ; rien ne change ici. "
    "Le testeur calculait H pour chaque déclarant, même un « actionnaire de 10 % » ou un « autre » (un dirigeant H = 1 "
    "déposant avec un actionnaire de 10 % H = 0 était gardé). Décision : seuls les déclarants administrateurs ou "
    "dirigeants comptent, comme ici (l'horizon de L'initié dont le rôle fait passer le filtre ; un actionnaire de 10 % "
    "seul ou « autre » seul est exclu). Après correction : mêmes achats et ventes sur le faux jeu et sur le jeu ciblé.",
    "Harmonisation (6 oct. 2026, avant tout résultat ; regles_du_jeu.md, « Changements », vers 12 h 30) : « d'actions "
    "ordinaires » est une condition du texte, appliquée comme dans vitesse-*, gestion-* et critique-3 : au moins un des "
    "titres déclarés (champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules ; seulement "
    "pour le formulaire qui donne le signal (l'historique de l'initié ne change pas). Testeur et vérificateur "
    "changés de la même façon (comparaison de la piste critique).",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « au minimum 1 000 $ » est lu comme un PLANCHER (le plus grand de 20 % et de 1 000 $), comme dans gestion-1 à 5 et critique-3 qui ont la même phrase ; un plancher ne se programme pas (une règle ne voit pas la valeur de son portefeuille) : MONTANT_MIN = 50, la valeur du banc. Effet seulement quand il reste moins de 1 000 $ pour une place.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 10
MONTANT_MIN = 50  # « au minimum 1 000 $ » = un plancher : voir CHOIX (harmonisation)
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

MONTANT_ACHAT_MIN = 25_000   # $
VALEUR_MIN_M = 100           # M$
ROLES_OK = {"administrateur", "dirigeant"}
ANNEES = 10                  # années civiles avant l'année du dépôt
ANNEES_MIN = 3               # années avec un F
H_MAX = Fraction(1, 2)


def _f_par_annee(ctx, initie, cie, annee):
    """Les F de l'initié dans cette compagnie, une par année civile (de annee-10 à annee-1) avec au moins un dépôt."""
    comptes = {}
    for r in ctx.historique_initie(initie, f"{annee - ANNEES:04d}-01-01"):
        an = int(r[0][:4])
        if not (annee - ANNEES <= an <= annee - 1) or r[1] != cie or r[3] not in ("achat", "vente"):
            continue
        a, v = comptes.get(an, (0, 0))
        comptes[an] = (a + 1, v) if r[3] == "achat" else (a, v + 1)
    return [Fraction(a - v, a + v) for a, v in comptes.values() if a + v]


def _horizon(e, ctx):
    """Le plus petit H des déclarants administrateurs ou dirigeants qui ont au moins 3 années avec un F ; sinon None."""
    annee = int(e["depot"][:4])
    meilleur = None
    for i in e.get("inities") or []:
        if not ROLES_OK & set(i.get("roles") or []):
            continue
        f = _f_par_annee(ctx, i["cik"], e["cik"], annee)
        if len(f) < ANNEES_MIN:
            continue
        h = abs(sum(f) / len(f))
        if meilleur is None or h < meilleur:
            meilleur = h
    return meilleur


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    roles = set()
    for i in e.get("inities") or []:
        roles.update(i.get("roles") or [])
    if not roles & ROLES_OK:
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
    h = _horizon(e, ctx)
    return h is not None and h <= H_MAX and _actions_ordinaires(e)


def priorite(e, ctx):
    """Le plus petit H d'abord, puis le plus gros montant : un entier exact (H à 10^-30 près, montant au cent)."""
    h = _horizon(e, ctx)
    if h is None:  # n'arrive pas : seuls les événements gardés sont rangés
        return -(10 ** 46)
    cle_h = (h.numerator * 10 ** 30) // h.denominator
    return -cle_h * 10 ** 15 + int(round((e.get("montant") or 0) * 100))
