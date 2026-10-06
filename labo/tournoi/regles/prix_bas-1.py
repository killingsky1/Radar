"""prix_bas-1 — Achat près du plus haut de 52 semaines (contre l'ancrage).

Programmé tel qu'écrit dans labo/tournoi/regles_preenregistrees.json (piste « prix_bas »).
Filtre : dirigeant ou administrateur ; routinier = non ; plan_10b5_1 différent de oui ; montant >= 25 000 $ ;
valeur_m >= 100 M$. PLUS_HAUT = 2e plus haute clôture SEC des 365 jours avant jour_premier_achat (au moins 20 clôtures et
au moins 1 dans chacun des 4 trimestres) ; gardé si prix_moyen >= 0,90 x PLUS_HAUT. Exclusions : CUSIP changé dans la
fenêtre, ou deux clôtures consécutives (moins de 10 jours de bourse d'écart) avec une baisse de plus de 45 % ou une
hausse de plus de 80 %.
Entrée : clôture SEC du 1er jour de bourse après le dépôt, sinon dans les 5 jours de bourse suivants. Sortie : clôture du
126e jour de bourse après l'entrée. 5 places de 20 % ; le même jour, le plus gros montant d'abord ; argent qui attend
dans le S&P 500.
"""
from bisect import bisect_right
from datetime import date, timedelta

ID = "prix_bas-1"

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
    "Fenêtre de 365 jours AVANT jour_premier_achat (J) : clôtures SEC datées de J-365 à J-1 (le jour J n'est pas "
    "compris).",
    "Les 4 trimestres de la fenêtre : 4 parts égales de 91,25 jours (J-365 à J-274, J-273 à J-183, J-182 à J-92, "
    "J-91 à J-1).",
    "PLUS_HAUT = la 2e valeur de la liste des clôtures de la fenêtre triées de la plus haute à la plus basse (deux "
    "clôtures égales au sommet : PLUS_HAUT = ce sommet).",
    "CUSIP changé dans la fenêtre = les clôtures de la fenêtre n'ont pas toutes le même CUSIP.",
    "Sauts : deux clôtures SEC qui se suivent dans la fenêtre, à moins de 10 jours de bourse d'écart (compté dans le "
    "calendrier du banc : 1 = deux jours de bourse qui se suivent) ; baisse de plus de 45 % = rendement < -0,45 ; hausse "
    "de plus de 80 % = rendement > +0,80 (une clôture à 0 suivie d'une clôture positive compte comme une hausse).",
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

_MONTANT_FORMULAIRE = 25_000  # $ (montant du formulaire 4)
_VALEUR_MIN_M = 100  # M$
_SEUIL = 0.90  # prix_moyen >= 0,90 x PLUS_HAUT


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


def garder(e, ctx):
    if not _filtre_commun(e, _MONTANT_FORMULAIRE):
        return False
    plus_haut = _plus_haut(e, ctx)
    return plus_haut is not None and e["prix_moyen"] >= _SEUIL * plus_haut


def priorite(e, ctx):
    """Le même jour : le plus gros montant passe en premier."""
    return e.get("montant") or 0.0
