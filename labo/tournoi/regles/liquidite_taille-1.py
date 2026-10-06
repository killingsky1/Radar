"""liquidite_taille-1 : compagnies moyennes, gros achat d'un dirigeant ou administrateur, garder 6 mois, 5 positions.

Programmée d'après le texte pré-enregistré (labo/tournoi/regles_preenregistrees.json), sans rien corriger :
- filtre : achat en bourse (code P) ; valeur_m de 300 à 3 000 M$ ; prix_moyen >= 5 $ ; montant >= 50 000 $ ; roles
  contient « dirigeant » ou « administrateur » ; routinier = non ; plan_10b5_1 différent de « oui » ; dépôt au plus
  4 jours civils après jour_dernier_achat ; aucune autre entrée de cette règle sur la même compagnie dans les 90 jours
  civils avant ;
- entrée : clôture SEC du 1er jour de bourse après le dépôt, sinon la 1re des 5 jours de bourse suivants, sinon abandon ;
- sortie : 1re clôture SEC au moins 126 jours de bourse après l'entrée ; un nouvel événement qui passe le filtre et
  arrive pendant qu'on détient la compagnie repousse la sortie à 126 jours de bourse après lui, sans dépasser 252 jours
  de bourse après l'entrée initiale ; titre disparu (aucun prix dans les 60 jours de bourse) : dernier prix connu
  × 0,70 dans le texte (le banc ne peut pas faire la décote : voir CHOIX) ;
- taille : 5 positions de 20 % de la valeur du portefeuille ; places pleines : signal ignoré (premier arrivé, premier
  servi ; à égalité de date, le plus gros montant) ; l'argent qui attend est dans SPY.
"""
from bisect import bisect_right
from datetime import date

ID = "liquidite_taille-1"

CHOIX = [
    "« Aucune autre entrée de cette règle sur le même cik_emetteur dans les 90 jours civils avant » : une entrée = un "
    "ACHAT fait par la règle (le texte appelle « entrée » l'achat : « date d'entrée », « entrée initiale »). Un signal "
    "qui n'a pas été acheté (places pleines, pas de prix) ne compte pas. Fait par le banc : "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 90, compté en jours civils d'une date d'achat à l'autre. Comme une position est "
    "gardée au moins 126 jours de bourse (plus de 90 jours civils), cette condition ne bloque jamais un achat en pratique.",
    "Le banc compte par SYMBOLE et non par cik (une seule position par symbole, délai de 90 jours par symbole) : une "
    "compagnie écrite avec deux symboles différents dans ses formulaires pourrait être détenue deux fois (rare).",
    "Prolongation : « un nouvel événement qui passe le filtre » doit passer TOUT le filtre, y compris « aucune autre "
    "entrée de cette règle sur le même cik_emetteur dans les 90 jours civils avant ». Notre propre achat de la compagnie "
    "est une autre entrée : seul un événement déposé PLUS de 90 jours civils après la date de notre achat prolonge la "
    "garde (à 90 jours pile, il est encore dans les 90 jours : pas de prolongation).",
    "Comparaison testeur / vérificateur (6 octobre 2026) : les deux programmes comptaient différemment ces 90 jours. "
    "Le vérificateur les comptait depuis l'achat PRÉVU du nouvel événement (1er jour de bourse après son dépôt) et "
    "laissait passer un écart de 90 jours pile (compte du banc, « < 90 ») ; ce programme-ci depuis son DÉPÔT, 90e jour "
    "compris. Un nouvel achat déposé 86 à 90 jours après le nôtre prolongeait la garde chez le vérificateur seulement "
    "(jeu ciblé : 13 cas, transactions différentes). Décision : cette lecture-ci, le sens le plus simple du texte : "
    "« avant » se rapporte à l'événement filtré, connu le jour de son dépôt (aucune date d'achat hypothétique à "
    "calculer), et un achat fait 90 jours avant est « dans les 90 jours civils avant ». Le vérificateur est corrigé ; "
    "ce programme-ci ne change pas.",
    "Prolongation : la nouvelle date de sortie = le 126e jour de bourse après la date de DÉPÔT du nouvel événement (il "
    "n'est pas acheté, donc il n'a pas de date d'achat). Si elle tombe avant la date déjà prévue, rien ne change. Jamais "
    "après le 252e jour de bourse après l'achat initial : DUREE = 252, et le banc vend alors.",
    "Prolongation : même compagnie = même cik. L'événement compte s'il est déposé pendant qu'on détient la compagnie, "
    "y compris pendant qu'on attend un prix pour vendre. Il est connu le soir de son dépôt : il peut empêcher une vente "
    "à partir du jour de bourse suivant (le banc décide la vente avec ce qui est connu la veille).",
    "La vente au 126e jour de bourse (ou à la date repoussée) est faite par sortir_avant() : le banc vend à la 1re "
    "clôture SEC à partir de ce jour-là. DUREE = 252 sert seulement de limite (prolongation maximale).",
    "Titre disparu : le banc vend au dernier prix SEC connu SANS la décote × 0,70 (le banc ne permet pas de changer le "
    "prix de vente).",
    "Titre disparu : TOLERANCE_SORTIE = 60 ne joue qu'à la date de sortie du banc (252e jour). Pour une vente au 126e "
    "jour (ou repoussée) faite par sortir_avant(), le banc ne vend qu'un jour où il y a un prix : sans aucun prix, la "
    "position reste ouverte jusqu'au 252e jour + 60 jours de bourse, puis elle est vendue au dernier prix connu (pas "
    "60 jours de bourse après la date de sortie prévue).",
    "Le texte dit de ne pas racheter quand un nouvel événement arrive pendant qu'on détient la compagnie. Si cet "
    "événement arrive juste avant la vente forcée du 252e jour, le banc peut le racheter le jour même de la vente (la "
    "règle ne voit pas le portefeuille dans garder()) : cas très rare.",
    "Places pleines : premier arrivé = date de dépôt la plus ancienne ; à égalité de date de dépôt, le montant le plus "
    "gros d'abord (priorite()) ; encore à égalité : l'ordre du banc (numéro du dépôt).",
    "roles : au moins un des déclarants du formulaire a le rôle « dirigeant » ou « administrateur » (un actionnaire de "
    "10 % seul, ou « autre » seul, est exclu).",
    "« Entre 300 M$ et 3 000 M$ » : bornes comprises (300 <= valeur_m <= 3000).",
    "Un champ vide (valeur_m, prix_moyen, montant ou jour_dernier) : la condition ne peut pas être vérifiée, "
    "l'événement n'est pas gardé.",
    "plan_10b5_1 : seul true (« oui ») exclut ; false et vide sont acceptés, à toute date.",
    "Délai : (date du dépôt − jour_dernier) <= 4 jours civils ; jour_dernier = dernier jour des achats (code P) du "
    "formulaire.",
    "Taille : MAX_POSITIONS = 5, soit 20 % de la valeur du portefeuille (positions + SPY) calculée par le banc au début "
    "des achats du jour, après les ventes du jour ; s'il ne reste pas assez d'argent, le banc achète moins (règle du "
    "banc). Frais et écart achat-vente : ceux du banc.",
]

# --- Réglages du banc
JOURS_ENTREE = 1                    # clôture SEC du 1er jour de bourse après le dépôt
TOLERANCE_ENTREE = 5                # pas de prix : 1re clôture des 5 jours de bourse suivants, sinon abandon
DUREE = 252                         # prolongation maximale ; la vente au 126e jour se fait dans sortir_avant()
TOLERANCE_SORTIE = 60               # titre disparu : aucun prix SEC dans les 60 jours de bourse après la sortie
MAX_POSITIONS = 5                   # 5 positions de 20 %
ARGENT_QUI_ATTEND = "SPY"           # l'argent qui attend est dans SPY (10 $ par opération SPY)
LIQUIDE_JOURS = 0                   # l'argent d'une vente retourne dans SPY tout de suite
UNE_ENTREE_PAR_SYMBOLE_JOURS = 90   # aucune autre entrée (achat) sur la même compagnie dans les 90 jours civils avant

# --- Seuils du texte
SEUIL_VALEUR_MIN, SEUIL_VALEUR_MAX = 300.0, 3000.0   # M$
SEUIL_PRIX = 5.0                                      # $
SEUIL_MONTANT = 50_000.0                              # $
SEUIL_DELAI = 4                                       # jours civils entre le dernier achat et le dépôt
GARDE = 126                                           # jours de bourse
SANS_DOUBLON = 90                                     # jours civils
ROLES = ("dirigeant", "administrateur")


def _jours(a, b):
    """Jours civils de la date a à la date b (AAAA-MM-JJ)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _passe_filtre(e):
    """Les conditions du filtre qui portent sur le formulaire lui-même. La condition « aucune autre entrée dans les 90
    jours » porte sur les achats de la règle : le banc la fait pour les achats, et sortir_avant() pour les prolongations."""
    if e.get("sens") != "achat":
        return False
    v = e.get("valeur_m")
    if v is None or not (SEUIL_VALEUR_MIN <= v <= SEUIL_VALEUR_MAX):
        return False
    p = e.get("prix_moyen")
    if p is None or p < SEUIL_PRIX:
        return False
    m = e.get("montant")
    if m is None or m < SEUIL_MONTANT:
        return False
    roles = {r for i in (e.get("inities") or []) for r in (i.get("roles") or [])}
    if not any(r in roles for r in ROLES):
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    if not e.get("jour_dernier") or not e.get("depot") or _jours(e["jour_dernier"], e["depot"]) > SEUIL_DELAI:
        return False
    return True


def garder(e, ctx):
    return _passe_filtre(e)


def priorite(e, ctx):
    """Premier arrivé, premier servi (dépôt le plus ancien) ; à égalité de date, le plus gros montant. Le banc prend le
    plus haut d'abord : la date compte avant le montant (entier exact, montant en cents)."""
    return -date.fromisoformat(e["depot"]).toordinal() * 10 ** 18 + round((e.get("montant") or 0) * 100)


def sortir_avant(pos, jour, ctx):
    """Vente au 126e jour de bourse après l'achat, ou plus tard si un nouvel événement a repoussé la sortie.
    `jour` est la veille : le banc vendra au jour de bourse suivant s'il y a un prix SEC ce jour-là."""
    entree = pos["entree"][0]
    seances = ctx.jours_de_bourse(entree)        # de l'achat à `jour`, compris
    rang_vente = len(seances)                    # rang du jour de vente possible : n-ième jour de bourse après l'achat
    cible = GARDE
    for n in ctx.evenements_avant(pos["cik"], entree):     # même compagnie, déposés de l'achat à `jour`
        if _jours(entree, n["depot"]) > SANS_DOUBLON and _passe_filtre(n):
            # 126e jour de bourse après le dépôt du nouvel événement, compté en jours de bourse après l'achat
            cible = max(cible, bisect_right(seances, n["depot"]) - 1 + GARDE)
    return rang_vente >= cible   # au-delà de 252 : DUREE, le banc vend de lui-même
