"""prix_bas-2 — Contre-courant solide : très loin du plus haut, mais compagnie qui fait de l'argent.

Programmé tel qu'écrit dans labo/tournoi/regles_preenregistrees.json (piste « prix_bas »).
Mêmes mesures et exclusions que prix_bas-1 (PLUS_HAUT, sauts, CUSIP ; au moins 20 clôtures et au moins 1 par trimestre).
Filtre : dirigeant ou administrateur ; routinier = non ; plan_10b5_1 différent de oui ; montant >= 50 000 $ ;
valeur_m >= 100 M$ ; gardé si prix_moyen <= 0,60 x PLUS_HAUT. Santé : dernier rapport annuel XBRL dont la fin de période
est au moins 90 jours avant jour_premier_achat : flux de trésorerie d'exploitation > 0 et capitaux propres > 0.
Entrée : clôture SEC du 1er jour de bourse après le dépôt, sinon dans les 5 jours de bourse suivants. Sortie : clôture du
126e jour de bourse après l'entrée. 5 places de 20 % ; le même jour, le plus gros montant d'abord ; argent qui attend
dans le S&P 500.
"""
from bisect import bisect_right
from datetime import date, timedelta

ID = "prix_bas-2"

CHOIX = [
    "Seulement les formulaires d'achat (sens = achat) : la règle porte sur les achats des initiés.",
    "Rôle : au moins un des déclarants du formulaire a le rôle « dirigeant » ou « administrateur ».",
    "routinier = non : gardé seulement si routinier est faux. plan_10b5_1 différent de oui : vrai est exclu ; faux et "
    "vide (case pas remplie) passent.",
    "montant, valeur_m, prix_moyen ou jour_premier_achat absent : événement écarté (la condition ne peut pas être "
    "vérifiée).",
    "jour_premier_achat plus d'un jour après la date du dépôt (date erronée) : événement écarté, car sa fenêtre, qui "
    "finit la veille de jour_premier_achat, demanderait des prix pas encore connus (elle n'est pas coupée au jour du "
    "dépôt : ce ne serait plus la mesure du texte). jour_premier_achat le lendemain du dépôt : la fenêtre finit le jour "
    "du dépôt, déjà connu, et l'événement est mesuré normalement. (Décision de la comparaison avec le vérificateur, "
    "comme vitesse-2.)",
    "Mêmes mesures et exclusions que prix_bas-1 : fenêtre de 365 jours AVANT jour_premier_achat (J), clôtures SEC "
    "datées de J-365 à J-1 (le jour J n'est pas compris) ; au moins 20 clôtures et au moins 1 dans chacun des 4 "
    "trimestres (4 parts égales de 91,25 jours : J-365 à J-274, J-273 à J-183, J-182 à J-92, J-91 à J-1).",
    "PLUS_HAUT = la 2e valeur de la liste des clôtures de la fenêtre triées de la plus haute à la plus basse (deux "
    "clôtures égales au sommet : PLUS_HAUT = ce sommet).",
    "CUSIP changé dans la fenêtre = les clôtures de la fenêtre n'ont pas toutes le même CUSIP.",
    "Sauts (comme prix_bas-1) : deux clôtures SEC qui se suivent dans la fenêtre, à moins de 10 jours de bourse "
    "d'écart (compté dans le calendrier du banc : 1 = deux jours de bourse qui se suivent) ; baisse de plus de 45 % = "
    "rendement < -0,45 ; hausse de plus de 80 % = rendement > +0,80 (une clôture à 0 suivie d'une clôture positive "
    "compte comme une hausse).",
    "Santé : « rapport annuel » = chiffres venant d'un 10-K ou d'un 10-K/A (forme du chiffre), comme le banc décrit les "
    "formes ; un rapport de transition (10-KT, après un changement de fin d'exercice) n'est pas compté comme rapport "
    "annuel. Seuls les chiffres DÉPOSÉS au plus tard le jour du dépôt du formulaire 4 sont vus (ctx.finances).",
    "Dernier rapport annuel = la date de fin la plus récente, au moins 90 jours avant jour_premier_achat (J - fin >= 90 "
    "jours), parmi les flux de trésorerie d'exploitation d'un exercice et les capitaux propres venant d'un 10-K ou d'un "
    "10-K/A.",
    "Flux de trésorerie d'exploitation = NetCashProvidedByUsedInOperatingActivities de l'exercice entier (durée de 350 "
    "à 380 jours) qui finit à cette date ; capitaux propres = StockholdersEquity au bilan de cette date. Gardé si les "
    "deux sont > 0.",
    "S'il manque l'un des deux chiffres pour ce dernier rapport annuel : événement écarté (on ne remonte pas à un "
    "rapport plus ancien).",
    "Comparaison avec le vérificateur : ces choix de santé sont gardés (10-KT pas compté comme rapport annuel ; dernier "
    "rapport = fin la plus récente parmi le flux d'un exercice et les capitaux propres d'un rapport annuel ; un chiffre "
    "qui manque dans ce rapport, même déposé plus tard dans un 10-K/A, écarte l'événement), car le texte dit « le "
    "dernier rapport annuel ». Le vérificateur prenait le dernier rapport qui avait un flux d'exploitation et comptait "
    "le 10-KT : corrigé chez lui.",
    "Le critique signalait une petite fuite (délai de 90 jours trop court pour les petites compagnies) : les règles du "
    "jeu (Changements, n° 2) la règlent par la vraie date de dépôt de chaque chiffre ; le délai de 90 jours du texte "
    "est gardé tel quel.",
    "Entrée (banc) : clôture SEC du 1er jour de bourse après le dépôt ; sans prix ce jour-là, le banc réessaie les 5 "
    "jours de bourse suivants (TOLERANCE_ENTREE = 5), sinon l'événement est passé.",
    "Sortie (banc) : clôture du 126e jour de bourse après le jour d'achat (DUREE = 126) ; sans prix, 1re clôture dans "
    "les 10 jours de bourse suivants, sinon la dernière clôture connue (TOLERANCE_SORTIE = 10). Compagnie disparue : "
    "dernier prix connu (le jeu de données n'a pas de prix de rachat).",
    "Taille (banc) : MAX_POSITIONS = 5, chaque position = valeur du portefeuille ÷ 5 (20 %). S'il reste moins de 20 % "
    "en argent, le banc achète avec ce qui reste ; une position de moins de 50 $ n'est pas achetée (MONTANT_MIN du banc, "
    "laissé par défaut).",
    "Une seule position par compagnie : le banc l'applique par symbole (garder ne voit pas le portefeuille).",
    "Le même jour, le plus gros montant d'abord : priorite = montant du formulaire 4 ; le banc classe ainsi tous les "
    "signaux achetables ce jour-là (ceux du jour et ceux qui attendent encore un prix).",
    "Argent qui attend : VOO remplacé par SPY (même indice S&P 500 ; le banc ne connaît que SPY), 10 $ par mouvement "
    "comme le texte. Le banc ajoute aussi, pour toutes les règles, le demi-écart achat-vente selon la valeur en bourse.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"

_MONTANT_FORMULAIRE = 50_000  # $ (montant du formulaire 4)
_VALEUR_MIN_M = 100  # M$
_SEUIL = 0.60  # prix_moyen <= 0,60 x PLUS_HAUT
_DELAI_RAPPORT = 90  # jours civils entre la fin de l'exercice et jour_premier_achat


def _moins(jour, n):
    """La date `n` jours civils avant `jour` (AAAA-MM-JJ)."""
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _filtre_commun(e, montant_min):
    """Achat ; dirigeant ou administrateur ; routinier = non ; plan_10b5_1 différent de oui ; montant ; valeur_m."""
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not any(r in ("dirigeant", "administrateur") for i in e.get("inities") or [] for r in i.get("roles") or []):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    if e.get("montant") is None or e["montant"] < montant_min:
        return False
    if e.get("valeur_m") is None or e["valeur_m"] < _VALEUR_MIN_M:
        return False
    if e.get("prix_moyen") is None:
        return False
    j = e.get("jour_premier")
    return bool(j) and _moins(j, 1) <= e["depot"]  # la fenêtre finit au plus tard le jour du dépôt


def _saut(p1, p2):
    """D'une clôture à la suivante : baisse de plus de 45 % ou hausse de plus de 80 %."""
    if p1 <= 0:
        return p2 > 0
    r = p2 / p1 - 1
    return r < -0.45 or r > 0.80


def _plus_haut(e, ctx):
    """PLUS_HAUT des 365 jours avant jour_premier_achat, ou None si l'événement est exclu (trop peu de clôtures, un
    trimestre vide, CUSIP changé, saut)."""
    j = e["jour_premier"]
    debut, fin = _moins(j, 365), _moins(j, 1)
    cl = ctx.clotures(e["symbole"], debut, fin)
    if len(cl) < 20:
        return None
    t0 = date.fromisoformat(debut)
    if len({(date.fromisoformat(d) - t0).days * 4 // 365 for d, _, _ in cl}) < 4:
        return None
    if len({c for _, _, c in cl}) > 1:
        return None
    cal = ctx.jours_de_bourse(debut)
    for (d1, p1, _), (d2, p2, _) in zip(cl, cl[1:]):
        if bisect_right(cal, d2) - bisect_right(cal, d1) < 10 and _saut(p1, p2):
            return None
    return sorted((p for _, p, _ in cl), reverse=True)[1]


def _annuel(forme):
    """Un chiffre de rapport annuel : forme 10-K ou sa modification 10-K/A (pas 10-Q, pas 10-KT)."""
    return forme in ("10-K", "10-K/A")


def _sante(e, ctx):
    """Dernier rapport annuel (10-K) fini au moins 90 jours avant jour_premier_achat : flux d'exploitation > 0 et
    capitaux propres > 0. Seuls les chiffres déposés au plus tard le jour du dépôt (ctx.finances)."""
    faits = ctx.finances(e["cik"])
    limite = _moins(e["jour_premier"], _DELAI_RAPPORT)
    flux = {}
    for debut, fin, valeur, forme in faits.get("NetCashProvidedByUsedInOperatingActivities", []):
        if debut and fin <= limite and _annuel(forme) and \
                350 <= (date.fromisoformat(fin) - date.fromisoformat(debut)).days <= 380:
            flux[fin] = valeur
    propres = {}
    for debut, fin, valeur, forme in faits.get("StockholdersEquity", []):
        if debut is None and fin <= limite and _annuel(forme):
            propres[fin] = valeur
    if not flux and not propres:
        return False
    fin = max(set(flux) | set(propres))
    if flux.get(fin) is None or propres.get(fin) is None:
        return False
    return flux[fin] > 0 and propres[fin] > 0


def garder(e, ctx):
    if not _filtre_commun(e, _MONTANT_FORMULAIRE):
        return False
    plus_haut = _plus_haut(e, ctx)
    if plus_haut is None or not e["prix_moyen"] <= _SEUIL * plus_haut:
        return False
    return _sante(e, ctx)


def priorite(e, ctx):
    """Le même jour : le plus gros montant passe en premier."""
    return e.get("montant") or 0.0
