"""temoin-meteo — Témoin de la météo : le même panier que meteo-1 à meteo-5, TOUJOURS allumé.

Programmé par le VÉRIFICATEUR, d'après labo/tournoi/regles_preenregistrees.json (partie « temoins »), sans voir
labo/tournoi/regles/. Sert seulement à juger si un interrupteur « météo » aide ; ne peut pas être finaliste.
- Panier : achat P d'un administrateur ou dirigeant, non routinier, pas de plan 10b5-1 « oui », montant >= 100 000 $,
  valeur_m >= 100 M$. Aucun interrupteur. Garde de 126 jours de bourse.
"""

ID = "temoin-meteo"
TEMOIN = True

CHOIX = [
    # --- Le panier (copié de meteo-1 à meteo-5) ---
    "Panier : l'événement doit être un achat (sens = « achat », code P).",
    "Rôles : il suffit qu'UN des déclarants du formulaire ait le rôle « administrateur » ou « dirigeant » (un formulaire "
    "peut avoir plusieurs déclarants) ; un actionnaire de 10 % ou « autre » sans l'un de ces deux rôles est exclu.",
    "routinier = non : exclu si e['routinier'] est vrai. plan_10b5_1 : exclu seulement s'il vaut true (false ou vide "
    "acceptés).",
    "montant ou valeur_m inconnu (None) : l'événement est exclu, car on ne peut pas vérifier le seuil (100 000 $ ; "
    "100 M$).",
    "« On ne possède pas déjà cette compagnie » : fait par le banc, par SYMBOLE (deux catégories d'actions d'une même "
    "compagnie ont deux symboles).",
    # --- Entrée, sortie, taille (réglages et comportement du banc) ---
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (clôture SEC du 1er jour de bourse après le dépôt ; sans prix, la "
    "1re clôture des 5 jours de bourse suivants ; sinon l'événement passe).",
    "Sortie : DUREE = 126 (le banc vend à la 1re clôture SEC à partir du 126e jour de bourse après l'entrée) et "
    "TOLERANCE_SORTIE = 20 (aucun prix pendant les 20 jours de bourse suivants : la dernière clôture connue).",
    "Plusieurs événements le même jour : priorite = montant (le plus gros d'abord). Le banc classe ensemble les signaux du "
    "jour et ceux qui attendent encore un prix.",
    "Taille (comportement du banc) : 10 cases (MAX_POSITIONS = 10) ; le banc vise 10 % de la valeur du portefeuille à la "
    "clôture du jour d'achat, les 10 $ de frais de l'achat pris dans ces 10 % ; s'il reste moins d'argent, il achète avec "
    "ce qui reste (pas d'achat sous 50 $ : MONTANT_MIN du banc).",
    "Argent qui attend : SPY ; l'argent d'une vente retourne dans SPY le jour même (ARGENT_QUI_ATTEND = 'SPY', "
    "LIQUIDE_JOURS = 0). Frais du banc : 10 $ par transaction, SPY compris, plus le demi-écart.",
    # --- Le témoin ---
    "Aucun interrupteur : pas de fonction investir (toujours allumé ; le banc peut donc acheter dès le 1er jour de la "
    "période). TEMOIN = True : le juge ne peut pas le faire passer.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0


def _panier(e):
    """Achat P ; un déclarant administrateur ou dirigeant ; non routinier ; plan 10b5-1 pas « oui » ;
    montant >= 100 000 $ ; valeur_m >= 100 M$."""
    if e.get("sens") != "achat":
        return False
    if not any(r in ("administrateur", "dirigeant") for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant, valeur = e.get("montant"), e.get("valeur_m")
    return montant is not None and montant >= 100_000 and valeur is not None and valeur >= 100


def garder(e, ctx):
    return _panier(e)


def priorite(e, ctx):
    return e.get("montant") or 0.0
