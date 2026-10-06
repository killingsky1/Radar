"""temoin-meteo : témoin de la météo, le même panier que meteo-1 à meteo-5, TOUJOURS allumé (regles_preenregistrees.json,
partie « temoins » ; demandé par le critique). Il sert seulement à voir si un interrupteur « météo » aide ; il ne peut
pas être finaliste.

Texte :
- PANIER (copié de meteo-1 à meteo-5) : achat P ; roles contient administrateur ou dirigeant (un actionnaire de 10 %
  seul ou « autre » seul est exclu) ; routinier = non ; plan_10b5_1 différent de « oui » (vide accepté) ; montant
  >= 100 000 $ ; valeur_m >= 100 M$ ; on ne possède pas déjà cette compagnie. Aucun interrupteur : toujours allumé.
- Entrée : clôture SEC du 1er jour de bourse après le dépôt ; sans prix, la 1re clôture SEC des 5 jours de bourse
  suivants, sinon on laisse passer. Plusieurs événements le même jour : le plus gros montant d'abord.
- Sortie : 1re clôture SEC à partir du 126e jour de bourse après l'entrée ; aucun prix dans les 20 jours de bourse
  suivants : dernière clôture connue.
- Taille : 10 cases de 10 % de la valeur du portefeuille ; tout le reste dans SPY (10 $ par transaction, SPY compris).
"""

ID = "temoin-meteo"
IMPOSSIBLE = None
TEMOIN = True  # témoin : comparé aux règles meteo-*, il ne peut pas passer

CHOIX = [
    "Témoin (TEMOIN = True) : même panier, même entrée, même sortie et même taille que meteo-1 à meteo-5, sans "
    "interrupteur (pas de fonction investir : le banc achète tous les jours).",
    # --- Le panier
    "« Achat P » = un événement « achat » du jeu de données (code P, titres non dérivés, en bourse).",
    "Rôles : l'événement est gardé si AU MOINS UN déclarant du formulaire a « administrateur » ou « dirigeant » dans "
    "ses rôles (un formulaire peut avoir plusieurs déclarants). Si tous les déclarants sont seulement actionnaires de "
    "10 % ou « autre », il est refusé.",
    "routinier = non : le champ routinier de l'événement doit valoir false (il vaut true si un des déclarants est "
    "routinier).",
    "plan_10b5_1 différent de « oui » : refusé seulement si true ; false et vide (null) acceptés.",
    "montant >= 100 000 $ et valeur_m >= 100 M$ : bornes comprises ; montant ou valeur_m absent (null) = refusé.",
    "« On ne possède pas déjà cette compagnie » : fait par le banc, qui refuse un SYMBOLE déjà en portefeuille (une "
    "compagnie qui aurait deux symboles, par exemple deux catégories d'actions, pourrait être achetée deux fois).",
    "Plusieurs événements le même jour : priorite = montant (le plus gros d'abord). Égalité : le banc prend le dépôt "
    "le plus ancien, puis le numéro du dépôt. Le banc trie ensemble les signaux du jour et ceux qui attendent encore "
    "un prix.",
    # --- Entrée, sortie, taille
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le 1er jour de bourse après le dépôt ; sans prix, le 1er prix "
    "des 5 jours de bourse suivants ; sinon abandon).",
    "Sortie : DUREE = 126 et TOLERANCE_SORTIE = 20 : vente à la 1re clôture SEC à partir du 126e jour de bourse après "
    "le jour d'achat, cherchée jusqu'au 20e jour de bourse après ce 126e jour ; aucun prix : dernière clôture connue. "
    "Pas de vente plus tôt (pas de sortir_avant).",
    "Taille : MAX_POSITIONS = 10 (10 % chacune) ; ARGENT_QUI_ATTEND = « SPY » ; LIQUIDE_JOURS = 0 (l'argent d'une "
    "vente retourne dans SPY le jour même). Les 10 places prises : le signal est laissé, même s'il attendait un prix.",
    "Banc (diffère du texte) : le 10 % est calculé avec la valeur du portefeuille à la clôture du jour d'achat (après "
    "les ventes du jour) ; la position vaut ce 10 % MOINS les 10 $ de frais ; s'il ne reste pas assez d'argent, il "
    "achète avec ce qui reste ; une position de moins de 50 $ n'est pas achetée (MONTANT_MIN = 50, réglage par défaut "
    "du banc).",
    "Banc (diffère du texte) : en plus des 10 $ par transaction (SPY compris), un demi-écart achat-vente selon la "
    "valeur en bourse, à l'achat et à la vente.",
    "Banc (le texte n'en parle pas) : changement de CUSIP pendant la détention = rendement enchaîné ; les ventes du "
    "jour passent avant les achats du jour ; une position encore ouverte à la fin des prix reste ouverte ; "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0 (un symbole vendu peut être racheté tout de suite).",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

# Seuils du texte
MONTANT_MINIMUM = 100_000  # $
VALEUR_MINIMUM = 100  # M$


def _panier(e):
    if e.get("sens") != "achat":
        return False
    if not any(r in ("administrateur", "dirigeant") for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant, valeur = e.get("montant"), e.get("valeur_m")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    if valeur is None or valeur < VALEUR_MINIMUM:
        return False
    return True


def garder(e, ctx):
    return _panier(e)


def priorite(e, ctx):
    return float(e.get("montant") or 0.0)
