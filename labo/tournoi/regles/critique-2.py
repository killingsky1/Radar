"""critique-2 : achat d'un initié « à horizon court » (qui alterne achats et ventes), garder 6 mois.

Texte pré-enregistré : labo/tournoi/regles_preenregistrees.json, partie « regles », id « critique-2 ».
Programmée telle qu'écrite (seuils du texte) ; chaque choix est dans CHOIX.

Horizon H d'un initié : dans son historique (ctx.historique_initie), les dépôts de CETTE compagnie faits pendant les
10 années civiles avant l'année du dépôt. Pour chaque année avec au moins un dépôt d'achat (P) ou de vente (S) :
F = (dépôts avec achat − dépôts avec vente) ÷ (dépôts avec achat + dépôts avec vente). Au moins 3 années avec un F ;
H = |moyenne des F| ; gardé si H ≤ 0,5.
"""
import math
from fractions import Fraction

ID = "critique-2"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat en bourse (code P) d'actions ordinaires » = un événement dont le sens est « achat » (code P, titres non "
    "dérivés). Le champ « titres » n'est pas filtré : il n'est pas dans la liste des champs de la règle et le jeu ne "
    "classe pas les titres.",
    "Plusieurs déclarants sur le formulaire : les rôles du formulaire sont ceux de tous ses déclarants réunis ; il faut "
    "« administrateur » ou « dirigeant » chez au moins un déclarant (un formulaire avec seulement des « actionnaire de "
    "10 % » ou « autre » est exclu).",
    "Plusieurs déclarants : H est calculé pour chaque déclarant administrateur ou dirigeant (son cik) ; l'événement "
    "est gardé si au moins un d'eux a au moins 3 années avec un F et H ≤ 0,5. Le H de l'événement (pour la priorité) "
    "est le plus petit.",
    "Historique : ctx.historique_initie(cik du déclarant), lignes dont le cik de la compagnie est celui de l'événement "
    "(cik_emetteur). L'année d'une ligne est celle de sa date de DÉPÔT ; fenêtre = les 10 années civiles avant l'année "
    "du dépôt de l'événement (dépôt de 2019 : 2009 à 2018). Le dépôt de l'événement lui-même n'est donc jamais compté.",
    "Comptage : une ligne d'historique = un dépôt pour un sens ; un dépôt avec un achat ET une vente compte des deux "
    "côtés (une ligne « achat » et une ligne « vente »). Deux dépôts le même jour comptent pour deux.",
    "Calcul exact en fractions : H = 0,5 exactement est gardé (comme l'exemple du texte).",
    "Un déclarant sans historique dans cette compagnie (ou avec moins de 3 années) n'a pas de H ; si aucun déclarant n'a "
    "de H, l'événement est écarté.",
    "routinier = non : gardé seulement si routinier vaut False.",
    "plan_10b5_1 différent de « oui » : gardé si False ou vide (None), à toutes les dates (« vide accepté »).",
    "montant ou valeur_m inconnu (None) : écarté, le seuil ne peut pas être vérifié.",
    "« Pas de position déjà ouverte sur cette compagnie » : fait par le banc, qui vérifie le SYMBOLE, pas le cik "
    "(garder() ne voit pas le portefeuille). Une compagnie avec deux symboles pourrait avoir deux positions (rare).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (clôture SEC du 1er jour de bourse après le dépôt, sinon la 1re "
    "clôture SEC des 5 jours de bourse suivants, sinon l'événement est laissé tomber).",
    "Sortie : DUREE = 126 et TOLERANCE_SORTIE = 20 (1re clôture SEC à partir du 126e jour de bourse après l'achat ; "
    "aucun prix pendant les 20 jours de bourse suivants : dernière clôture SEC connue). Pas de sortir_avant().",
    "Taille : MAX_POSITIONS = 5, donc 20 % de la valeur du portefeuille (actions + SPY + liquide), calculée par le banc "
    "le jour de l'achat après les ventes du jour ; le banc prend les 10 $ de frais dans ces 20 %. S'il manque d'argent "
    "(les autres positions ont monté), le banc achète avec ce qui reste.",
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « au minimum 1 000 $ » : MONTANT_MIN = 1000, une position de moins de 1 000 $ n'est pas achetée (le banc ne peut "
    "pas monter un achat jusqu'à 1 000 $).",
    "Liquide : LIQUIDE_JOURS = 10 et ARGENT_QUI_ATTEND = « SPY » (l'argent d'une vente attend 10 jours de bourse, "
    "sert d'abord à payer, puis va dans SPY).",
    "Priorité : le plus petit H d'abord, puis le plus gros montant, en un seul nombre entier exact (H à 10⁻¹⁸ près, "
    "puis le montant en cents). Le banc applique cet ordre à tous les signaux du jour, y compris ceux qui attendent un "
    "prix depuis un jour précédent ; à égalité : date de dépôt, puis numéro.",
    "Comportements standard du banc, pas dans le texte : demi-écart achat-vente selon la valeur en bourse (à l'achat et à "
    "la vente) en plus des 10 $ ; le premier placement dans SPY au départ se fait sans frais de 10 $ ; changement de "
    "CUSIP pendant la détention : rendement enchaîné.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : écart corrigé DANS CE FICHIER. Avant, avec plusieurs déclarants, "
    "H était calculé pour CHAQUE déclarant, même un « actionnaire de 10 % » ou un « autre » : le formulaire d'un "
    "dirigeant qui vend chaque année (H = 1), déposé avec un actionnaire de 10 % qui alterne (H = 0), était gardé. Le "
    "texte parle de l'horizon de L'initié, celui dont le rôle (administrateur ou dirigeant) fait passer le filtre ; un "
    "actionnaire de 10 % seul ou « autre » seul est exclu, donc son horizon ne peut pas faire garder l'événement. H "
    "n'est donc calculé que pour les déclarants administrateurs ou dirigeants (aussi pour la priorité), comme le "
    "vérificateur. Jeu ciblé (formulaires à 2 déclarants, historiques choisis) : 59 décisions et des transactions "
    "différentes avant ; après : mêmes décisions, même ordre de priorité, mêmes achats et ventes (et sur le faux jeu).",
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

MONTANT_MINIMUM = 25_000  # $
VALEUR_MINIMUM = 100  # M$
ANNEES = 10
ANNEES_MIN = 3
H_MAX = Fraction(1, 2)
ROLES_ACCEPTES = {"administrateur", "dirigeant"}


def _horizon_initie(e, ctx, cik_initie):
    """H (fraction exacte) d'un déclarant dans la compagnie de l'événement, ou None (moins de 3 années avec un F)."""
    if not cik_initie:
        return None
    annee = int(e["depot"][:4])
    debut, fin = f"{annee - ANNEES}-01-01", f"{annee}-01-01"
    comptes = {}  # année → [dépôts avec achat, dépôts avec vente]
    for r in ctx.historique_initie(cik_initie, debut):
        depot, cik_cie, sens = r[0], r[1], r[3]
        if not (debut <= depot < fin) or cik_cie != e["cik"]:
            continue
        c = comptes.setdefault(depot[:4], [0, 0])
        if sens == "achat":
            c[0] += 1
        elif sens == "vente":
            c[1] += 1
    f = [Fraction(a - v, a + v) for a, v in comptes.values() if a + v > 0]
    if len(f) < ANNEES_MIN:
        return None
    return abs(sum(f) / len(f))


def _horizon(e, ctx):
    """Le plus petit H parmi les déclarants administrateurs ou dirigeants du formulaire (None si aucun n'en a)."""
    hs = [h for i in (e.get("inities") or []) if set(i.get("roles") or []) & ROLES_ACCEPTES
          and (h := _horizon_initie(e, ctx, i.get("cik"))) is not None]
    return min(hs) if hs else None


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    roles = {r for i in (e.get("inities") or []) for r in (i.get("roles") or [])}
    if not roles & ROLES_ACCEPTES:
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
    h = _horizon(e, ctx)
    return h is not None and h <= H_MAX and _actions_ordinaires(e)


def priorite(e, ctx):
    """Plusieurs signaux le même jour : le plus petit H d'abord, puis le plus gros montant (un entier exact : le banc
    trie du plus haut au plus bas)."""
    h = _horizon(e, ctx)
    if h is None:  # n'arrive pas pour un événement gardé
        h = Fraction(1)
    cents = min(max(round((e.get("montant") or 0.0) * 100), 0), 10 ** 20 - 1)
    return -math.floor(h * 10 ** 18) * 10 ** 20 + cents
