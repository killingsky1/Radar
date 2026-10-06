"""prix_bas-1 : achat près du plus haut de 52 semaines (contre l'ancrage).

Programmation du VÉRIFICATEUR, faite sans voir celle du testeur (labo/tournoi/regles/), d'après le texte
pré-enregistré dans labo/tournoi/regles_preenregistrees.json.
"""
from bisect import bisect_left
from datetime import date, timedelta

ID = "prix_bas-1"

CHOIX = [
    "Seulement les achats (sens = « achat ») : la règle parle d'un dirigeant qui achète ; les ventes ne sont jamais gardées.",
    "Rôle dirigeant ou administrateur : au moins un des déclarants du formulaire (e['inities']) a le rôle « dirigeant » "
    "ou « administrateur ».",
    "routinier = non : e['routinier'] doit être faux. plan_10b5_1 différent de oui : seul « vrai » est exclu ; « faux » "
    "et « inconnu » (null) passent.",
    "Un montant, une valeur_m, un prix_moyen ou un jour_premier inconnu : l'événement n'est pas gardé (la condition ne "
    "peut pas être vérifiée).",
    "jour_premier_achat = e['jour_premier']. Fenêtre = les 365 jours civils AVANT ce jour, sans le jour même : de "
    "jour_premier − 365 jours à jour_premier − 1 jour, bornes comprises.",
    "jour_premier plus d'un jour après le jour du dépôt (erreur de date) : pas gardé, car la fenêtre, qui finit la "
    "veille de jour_premier, demanderait des prix pas encore connus ; elle n'est pas coupée au jour du dépôt (ce ne "
    "serait plus la mesure du texte). jour_premier le lendemain du dépôt : la fenêtre finit le jour du dépôt, déjà "
    "connu, et l'événement est mesuré normalement. (Décision de la comparaison avec le testeur, comme vitesse-2.)",
    "Clôtures SEC lues avec ctx.clotures, comme le banc les montre (connues le soir de leur jour ; seules les "
    "quantités d'échecs ont un délai de 35 jours). Qu'une clôture existe ou non un jour donné dépend des échecs "
    "de livraison (biais signalé par le critique, point 2c) : rien n'est corrigé ici.",
    "Les 4 trimestres de la fenêtre : 4 parts égales comptées depuis le début de la fenêtre (jour n° 0 à 364 ; "
    "trimestre = n° × 4 ÷ 365, arrondi vers le bas), donc 92, 91, 91 et 91 jours, du plus ancien au plus récent. "
    "Il faut au moins 1 clôture dans chacun, et au moins 20 clôtures en tout.",
    "PLUS_HAUT = la 2e valeur des clôtures de la fenêtre triées de la plus haute à la plus basse (si les deux plus "
    "hautes sont égales, PLUS_HAUT est cette valeur).",
    "Prix actuel = prix_moyen du formulaire 4 ; gardé si prix_moyen >= 0,90 × PLUS_HAUT.",
    "CUSIP changé dans la fenêtre : plus d'un CUSIP différent parmi les clôtures de la fenêtre.",
    "Sauts : deux clôtures SEC qui se suivent dans la fenêtre, à moins de 10 jours de bourse l'une de l'autre (écart "
    "de rang < 10 dans le calendrier des jours de bourse du banc) ; baisse de plus de 45 % = prix2 / prix1 − 1 < −0,45 ; "
    "hausse de plus de 80 % = prix2 / prix1 − 1 > 0,80. Une clôture à 0 suivie d'un prix positif compte comme une "
    "hausse de plus de 80 %.",
    "Entrée : le banc achète à la clôture SEC du 1er jour de bourse après le dépôt (JOURS_ENTREE = 1) ; sans prix ce "
    "jour-là, il réessaie jusqu'à 5 jours de bourse plus tard (TOLERANCE_ENTREE = 5), sinon le signal est passé.",
    "Sortie : DUREE = 126 jours de bourse après l'entrée ; sans prix ce jour-là, 1re clôture des 10 jours de bourse "
    "suivants, sinon la dernière connue (TOLERANCE_SORTIE = 10). « Compagnie disparue : prix de rachat » : le banc "
    "n'a pas de prix de rachat, il prend la dernière clôture SEC connue.",
    "Taille : MAX_POSITIONS = 5 ; le banc fait chaque position = valeur du portefeuille ÷ 5 (20 %), frais de 10 $ "
    "compris dans ce montant.",
    "Une seule position par compagnie : le banc le fait par symbole (un 2e signal du même symbole est ignoré tant "
    "que la position est ouverte).",
    "Places pleines : le signal est ignoré (comportement du banc).",
    "Le même jour, le plus gros montant d'abord : priorite = montant du formulaire. Le banc applique cet ordre à "
    "tous les signaux qui attendent ce jour-là, y compris ceux qui attendent un prix depuis un jour précédent.",
    "L'argent qui attend : dans SPY au lieu de VOO (le banc ne connaît que SPY ; les deux suivent le S&P 500), "
    "avec 10 $ par mouvement comme dans le texte.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"

MONTANT_MINIMUM = 25_000
VALEUR_M_MINIMUM = 100
SEUIL = 0.90


def _jour(texte, decalage):
    return (date.fromisoformat(texte) + timedelta(days=decalage)).isoformat()


def _filtre_de_base(e, montant_minimum):
    if e.get("sens") != "achat":
        return False
    if not any(r in ("dirigeant", "administrateur") for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    if e.get("montant") is None or e["montant"] < montant_minimum:
        return False
    if e.get("valeur_m") is None or e["valeur_m"] < VALEUR_M_MINIMUM:
        return False
    if e.get("prix_moyen") is None or not e.get("jour_premier") or not e.get("symbole"):
        return False
    return _jour(e["jour_premier"], -1) <= e["depot"]  # la fenêtre finit au plus tard le jour du dépôt


def _saut(p1, p2):
    """Baisse de plus de 45 % ou hausse de plus de 80 % d'une clôture à la suivante."""
    if p1 <= 0:
        return p2 > 0
    r = p2 / p1 - 1
    return r < -0.45 or r > 0.80


def _plus_haut(e, ctx):
    """PLUS_HAUT de la fenêtre de 365 jours avant jour_premier, ou None si la mesure manque ou si l'événement est exclu
    (trop peu de clôtures, un trimestre vide, CUSIP changé, saut)."""
    jp = e["jour_premier"]
    debut = _jour(jp, -365)
    fin = min(_jour(jp, -1), ctx.jour)
    if fin < debut:
        return None
    cl = ctx.clotures(e["symbole"], debut, fin)
    if len(cl) < 20:
        return None
    d0 = date.fromisoformat(debut)
    if {(date.fromisoformat(d) - d0).days * 4 // 365 for d, _, _ in cl} != {0, 1, 2, 3}:
        return None
    if len({c for _, _, c in cl}) > 1:
        return None
    cal = ctx.jours_de_bourse(debut)
    for (d1, p1, _), (d2, p2, _) in zip(cl, cl[1:]):
        if bisect_left(cal, d2) - bisect_left(cal, d1) < 10 and _saut(p1, p2):
            return None
    return sorted((p for _, p, _ in cl), reverse=True)[1]


def garder(e, ctx):
    if not _filtre_de_base(e, MONTANT_MINIMUM):
        return False
    plus_haut = _plus_haut(e, ctx)
    if plus_haut is None:
        return False
    return e["prix_moyen"] >= SEUIL * plus_haut


def priorite(e, ctx):
    return e.get("montant") or 0.0
