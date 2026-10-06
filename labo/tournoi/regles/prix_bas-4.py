"""prix_bas-4 — Grosse chute récente et au moins deux initiés qui achètent.

Programmé tel qu'écrit dans labo/tournoi/regles_preenregistrees.json (piste « prix_bas »).
Filtre : dirigeant ou administrateur ; routinier = non ; plan_10b5_1 différent de oui ; montant >= 25 000 $ ;
valeur_m >= 100 M$. Groupe : groupe >= 1, ou bien un autre initié (initie_cik différent) a déposé le même jour un
formulaire 4 avec achat sur la même action. Référence il y a 3 mois = médiane des clôtures SEC entre 105 et 75 jours
civils avant jour_premier_achat (au moins 2). Baisse = prix_moyen / référence - 1 ; gardé si <= -30 %. Exclusions :
CUSIP changé dans les 365 jours, ou saut entre clôtures consécutives (baisse de plus de 45 % ou hausse de plus de 80 %)
depuis la date de référence.
Entrée : clôture SEC du 1er jour de bourse après le dépôt, sinon dans les 5 jours de bourse suivants. Sortie : clôture du
126e jour de bourse après l'entrée. 5 places de 20 % ; le même jour, le plus gros montant d'abord ; argent qui attend
dans le S&P 500.
"""
from datetime import date, timedelta
from statistics import median

ID = "prix_bas-4"

CHOIX = [
    "Seulement les formulaires d'achat (sens = achat) : la règle porte sur les achats des initiés.",
    "Rôle : au moins un des déclarants du formulaire a le rôle « dirigeant » ou « administrateur ».",
    "routinier = non : gardé seulement si routinier est faux. plan_10b5_1 différent de oui : vrai est exclu ; faux et "
    "vide (case pas remplie) passent.",
    "montant, valeur_m, prix_moyen ou jour_premier_achat absent : événement écarté (la condition ne peut pas être "
    "vérifiée).",
    "jour_premier_achat plus d'un jour après la date du dépôt (date erronée) : événement écarté, car ses fenêtres, qui "
    "finissent au plus tard la veille de jour_premier_achat, demanderaient des prix pas encore connus (elles ne sont "
    "pas coupées au jour du dépôt : ce ne serait plus la mesure du texte). jour_premier_achat le lendemain du dépôt : "
    "les fenêtres finissent au plus tard le jour du dépôt, déjà connu, et l'événement est mesuré normalement. "
    "(Décision de la comparaison avec le vérificateur, comme vitesse-2.)",
    "Groupe : dans le texte, « groupe » compte les AUTRES initiés (titre « au moins deux initiés qui achètent », "
    "paramètres « groupe >= 1 ou un 2e initié le même jour » ; les autres pistes le définissent aussi ainsi). Le champ "
    "groupe_30j du jeu compte l'initié du dépôt lui-même (« celui-ci compris ») : « groupe >= 1 » devient donc "
    "groupe_30j >= 2. Lu à la lettre (groupe_30j >= 1), la condition serait toujours vraie pour un achat.",
    "Ou bien : un autre formulaire 4 avec achat (sens = achat), déposé le même jour (même date de dépôt) sur la même "
    "compagnie (même cik de l'émetteur), dont au moins un déclarant n'est pas un déclarant de ce formulaire ; le rôle "
    "et le montant de cet autre initié ne comptent pas. (groupe_30j compte déjà ces dépôts du même jour.)",
    "Prix de référence : médiane des clôtures SEC datées de J-105 à J-75, bornes comprises (J = jour_premier_achat) ; "
    "au moins 2 clôtures. Nombre pair de clôtures : moyenne des deux du milieu.",
    "Baisse = prix_moyen / référence - 1, comparée telle quelle à -0,30 (gardé si <= -0,30).",
    "CUSIP changé dans les 365 jours : les clôtures SEC datées de J-365 à J-1 n'ont pas toutes le même CUSIP.",
    "Sauts « depuis la date de référence » : entre deux clôtures SEC qui se suivent, toutes deux datées de J-105 (début "
    "de la fenêtre de référence) à J-1 ; baisse de plus de 45 % = rendement < -0,45 ; hausse de plus de 80 % = "
    "rendement > +0,80 (une clôture à 0 suivie d'une clôture positive compte comme une hausse).",
    "Le texte de prix_bas-4 ne reprend pas la condition « moins de 10 jours de bourse d'écart » de prix_bas-1 : ici, "
    "tout saut entre deux clôtures qui se suivent compte, peu importe l'écart entre leurs dates.",
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
_REF_LOIN, _REF_PRES = 105, 75  # fenêtre de référence, en jours civils avant jour_premier_achat
_BAISSE_MAX = -0.30
_GROUPE_30J_MIN = 2  # « groupe >= 1 » (autres initiés) = groupe_30j >= 2 (groupe_30j compte l'initié lui-même)


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
    return bool(j) and _moins(j, 1) <= e["depot"]  # les fenêtres finissent au plus tard le jour du dépôt


def _saut(p1, p2):
    """D'une clôture à la suivante : baisse de plus de 45 % ou hausse de plus de 80 %."""
    if p1 <= 0:
        return p2 > 0
    r = p2 / p1 - 1
    return r < -0.45 or r > 0.80


def _groupe(e, ctx):
    """groupe >= 1 (au moins un AUTRE initié : groupe_30j >= 2), ou un autre initié a déposé le même jour un
    formulaire 4 avec achat sur la même compagnie."""
    if (e.get("groupe_30j") or 0) >= _GROUPE_30J_MIN:
        return True
    moi = {i.get("cik") for i in e.get("inities") or []}
    for x in ctx.evenements_avant(e["cik"], e["depot"]):
        if x["depot"] == e["depot"] and x.get("sens") == "achat" and x["id"] != e["id"] and \
                any(i.get("cik") not in moi for i in x.get("inities") or []):
            return True
    return False


def _reference(e, ctx, loin, pres):
    """Médiane des clôtures de J-loin à J-pres (au moins 2), ou None si l'événement est exclu (CUSIP changé dans les
    365 jours, saut entre clôtures consécutives depuis le début de la fenêtre de référence)."""
    j, s = e["jour_premier"], e["symbole"]
    ref = ctx.clotures(s, _moins(j, loin), _moins(j, pres))
    if len(ref) < 2:
        return None
    if len({c for _, _, c in ctx.clotures(s, _moins(j, 365), _moins(j, 1))}) > 1:
        return None
    suite = ctx.clotures(s, _moins(j, loin), _moins(j, 1))
    if any(_saut(p1, p2) for (_, p1, _), (_, p2, _) in zip(suite, suite[1:])):
        return None
    return median(p for _, p, _ in ref)


def garder(e, ctx):
    if not _filtre_commun(e, _MONTANT_FORMULAIRE):
        return False
    if not _groupe(e, ctx):
        return False
    ref = _reference(e, ctx, _REF_LOIN, _REF_PRES)
    if ref is None or ref <= 0:
        return False
    return e["prix_moyen"] / ref - 1 <= _BAISSE_MAX


def priorite(e, ctx):
    """Le même jour : le plus gros montant passe en premier."""
    return e.get("montant") or 0.0
