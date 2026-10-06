"""prix_bas-4 : grosse chute récente et au moins deux initiés qui achètent.

Programmation du VÉRIFICATEUR, faite sans voir celle du testeur (labo/tournoi/regles/), d'après le texte
pré-enregistré dans labo/tournoi/regles_preenregistrees.json.
"""
from datetime import date, timedelta
from statistics import median

ID = "prix_bas-4"

CHOIX = [
    "Seulement les achats (sens = « achat ») : la règle parle d'initiés qui achètent ; les ventes ne sont jamais gardées.",
    "Rôle dirigeant ou administrateur : au moins un des déclarants du formulaire (e['inities']) a le rôle « dirigeant » "
    "ou « administrateur ».",
    "routinier = non : e['routinier'] doit être faux. plan_10b5_1 différent de oui : seul « vrai » est exclu ; « faux » "
    "et « inconnu » (null) passent.",
    "Un montant, une valeur_m, un prix_moyen ou un jour_premier inconnu : l'événement n'est pas gardé (la condition ne "
    "peut pas être vérifiée).",
    "Groupe : dans les données, groupe_30j compte AUSSI l'initié du dépôt (« celui-ci compris »), donc « groupe >= 1 » "
    "pris à la lettre serait toujours vrai. Le titre (« au moins deux initiés qui achètent »), « un 2e initié » des "
    "paramètres et les autres chercheurs (« groupe » = les AUTRES initiés) montrent que « groupe » ne compte pas "
    "l'initié du dépôt : groupe = groupe_30j − 1, et « groupe >= 1 » devient groupe_30j >= 2 (au moins 2 initiés de "
    "cik différents ont acheté la même compagnie dans les 30 jours avant le dépôt, ce dépôt et son jour compris).",
    "Un formulaire déposé par plusieurs déclarants de cik différents compte pour plusieurs initiés, comme dans "
    "groupe_30j : le texte ne demande qu'un « initie_cik différent ».",
    "« Ou bien un autre initié (cik différent) a déposé le même jour un formulaire 4 avec achat sur la même action » : "
    "déjà compris dans groupe_30j (sa fenêtre inclut le jour du dépôt) ; vérifié aussi directement avec "
    "ctx.evenements_avant(cik de la compagnie, jour du dépôt) : au moins 2 cik différents parmi les déclarants des "
    "achats déposés ce jour-là. « Même action » = même compagnie (cik de l'émetteur), comme groupe_30j.",
    "jour_premier_achat = e['jour_premier']. Référence = médiane des clôtures SEC datées de jour_premier − 105 jours à "
    "jour_premier − 75 jours (bornes comprises) ; il en faut au moins 2. Médiane habituelle : avec un nombre pair de "
    "clôtures, la moyenne des deux du milieu.",
    "Baisse = prix_moyen / référence − 1 ; gardé si baisse <= −0,30. Une référence à 0 (division impossible) : pas gardé.",
    "CUSIP changé dans les 365 jours : plus d'un CUSIP différent parmi les clôtures de jour_premier − 365 jours à "
    "jour_premier − 1 jour (la même fenêtre de 365 jours avant l'achat que prix_bas-1).",
    "Sauts « depuis la date de référence » : toutes les paires de clôtures SEC qui se suivent, du début de la fenêtre "
    "de référence (jour_premier − 105 jours) à jour_premier − 1 jour ; baisse de plus de 45 % = prix2 / prix1 − 1 < "
    "−0,45 ; hausse de plus de 80 % = prix2 / prix1 − 1 > 0,80. Sans limite d'écart entre les deux clôtures : la "
    "limite « moins de 10 jours de bourse » de prix_bas-1 n'est pas écrite dans cette règle. Une clôture à 0 suivie "
    "d'un prix positif compte comme une hausse de plus de 80 %.",
    "Clôtures SEC lues avec ctx.clotures, comme le banc les montre (connues le soir de leur jour ; seules les "
    "quantités d'échecs ont un délai de 35 jours). Qu'une clôture existe ou non un jour donné dépend des échecs "
    "de livraison (biais signalé par le critique, point 2c) : rien n'est corrigé ici.",
    "jour_premier plus d'un jour après le jour du dépôt (erreur de date) : pas gardé, car les fenêtres, qui finissent "
    "au plus tard la veille de jour_premier, demanderaient des prix pas encore connus ; elles ne sont pas coupées au "
    "jour du dépôt (ce ne serait plus la mesure du texte). jour_premier le lendemain du dépôt : les fenêtres finissent "
    "au plus tard le jour du dépôt, déjà connu, et l'événement est mesuré normalement. (Décision de la comparaison avec "
    "le testeur, comme vitesse-2.)",
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
REFERENCE_DE, REFERENCE_A = 105, 75  # jours civils avant jour_premier
BAISSE_MAXIMUM = -0.30


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
    return _jour(e["jour_premier"], -1) <= e["depot"]  # les fenêtres finissent au plus tard le jour du dépôt


def _saut(p1, p2):
    """Baisse de plus de 45 % ou hausse de plus de 80 % d'une clôture à la suivante."""
    if p1 <= 0:
        return p2 > 0
    r = p2 / p1 - 1
    return r < -0.45 or r > 0.80


def _clotures(ctx, symbole, de, a):
    a = min(a, ctx.jour)  # jamais au-delà du jour de la décision
    return ctx.clotures(symbole, de, a) if de <= a else []


def _groupe(e, ctx):
    """« groupe >= 1 » (groupe = les AUTRES initiés = groupe_30j − 1), ou bien un autre initié (cik différent) a déposé
    le même jour un formulaire 4 avec achat sur la même compagnie."""
    if (e.get("groupe_30j") or 0) - 1 >= 1:
        return True
    ciks_du_jour = {i["cik"] for x in ctx.evenements_avant(e["cik"], e["depot"]) if x.get("sens") == "achat"
                    for i in x.get("inities") or []}
    return len(ciks_du_jour | {i["cik"] for i in e.get("inities") or []}) >= 2


def garder(e, ctx):
    if not _filtre_de_base(e, MONTANT_MINIMUM):
        return False
    if not _groupe(e, ctx):
        return False
    jp, s = e["jour_premier"], e["symbole"]
    reference = _clotures(ctx, s, _jour(jp, -REFERENCE_DE), _jour(jp, -REFERENCE_A))
    if len(reference) < 2:
        return False
    ref = median(p for _, p, _ in reference)
    if ref <= 0:
        return False
    if not e["prix_moyen"] / ref - 1 <= BAISSE_MAXIMUM:
        return False
    if len({c for _, _, c in _clotures(ctx, s, _jour(jp, -365), _jour(jp, -1))}) > 1:
        return False
    depuis_reference = _clotures(ctx, s, _jour(jp, -REFERENCE_DE), _jour(jp, -1))
    if any(_saut(p1, p2) for (_, p1, _), (_, p2, _) in zip(depuis_reference, depuis_reference[1:])):
        return False
    return True


def priorite(e, ctx):
    return e.get("montant") or 0.0
