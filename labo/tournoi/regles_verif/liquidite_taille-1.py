"""liquidite_taille-1 : compagnies moyennes, gros achat d'un dirigeant ou administrateur, garder 6 mois, 5 positions.

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (regles_preenregistrees.json), sans voir
labo/tournoi/regles/. Chaque choix d'interprétation est dans CHOIX.
"""
from datetime import date

ID = "liquidite_taille-1"

CHOIX = [
    "Formulaire avec plusieurs déclarants : « roles contient dirigeant ou administrateur » est vrai si AU MOINS UN "
    "déclarant a l'un de ces deux rôles (un actionnaire de 10 % seul, ou « autre » seul, est exclu).",
    "« valeur_m entre 300 M$ et 3 000 M$ » : bornes comprises. Une donnée absente (valeur_m, prix_moyen, montant ou "
    "jour_dernier vide) : l'événement n'est pas gardé (la condition ne peut pas être vraie).",
    "« plan_10b5_1 différent de oui » : seul true est exclu ; false et vide (null) sont gardés. « routinier = non » : "
    "un événement routinier (true) est exclu.",
    "« depot au plus 4 jours civils après jour_dernier_achat » : (dépôt − jour_dernier) ≤ 4 jours civils, avec "
    "jour_dernier = la dernière date d'achat du formulaire. Un délai négatif (erreur de date dans le formulaire) passe.",
    "« Aucune autre entrée de cette règle sur le même cik dans les 90 jours civils avant » : réglage du banc "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 90, donc compté d'un jour d'ACHAT à l'autre, par SYMBOLE (pas par cik), bloqué si "
    "moins de 90 jours. En pratique sans effet : une position est gardée au moins 126 jours de bourse et le banc "
    "n'achète jamais un symbole déjà détenu (« on ne rachète pas »).",
    "Entrée : TOLERANCE_ENTREE = 5 (pas de prix SEC le 1er jour de bourse après le dépôt : 1re clôture des 5 jours de "
    "bourse suivants, sinon l'événement est abandonné).",
    "Places pleines : le signal est ignoré (banc). Ordre des signaux (priorite) : la date de dépôt la plus ancienne "
    "d'abord (« premier arrivé, premier servi »), puis, à date égale, le montant le plus gros ; ensuite l'ordre du banc.",
    "Sortie : DUREE = 252 (le plafond « sans dépasser 252 jours de bourse après l'entrée initiale ») et sortir_avant "
    "fait la sortie normale : vente à la 1re clôture SEC disponible à partir du 126e jour de bourse après le jour "
    "d'achat.",
    "Prolongation : un nouvel événement sur la même compagnie (même cik), déposé à partir du jour d'achat (donc pendant "
    "qu'on la détient) et vu au plus tard la veille de la vente, qui passe TOUT le filtre, repousse la vente au 126e "
    "jour de bourse après SON DÉPÔT (« 126 jours de bourse après ce nouvel événement »), jamais après le 252e jour "
    "après l'achat. S'il y en a plusieurs, le plus tardif compte. Un dépôt n'est connu que le soir (règle du banc) : "
    "un événement déposé le jour même de la vente ne la retarde pas, et le banc peut l'acheter comme une nouvelle "
    "entrée.",
    "« Passe le filtre » comprend la condition « aucune autre entrée de cette règle dans les 90 jours civils avant » : "
    "les 90 jours sont comptés avant le DÉPÔT du nouvel événement (la date de l'événement, comme pour « 126 jours de "
    "bourse après ce nouvel événement »), et notre achat de la position est une autre entrée : un événement déposé 90 "
    "jours civils ou moins après notre jour d'achat ne prolonge pas (à 90 jours pile, notre achat est encore dans les "
    "90 jours civils avant). Une prolongation n'est pas une « entrée » : seul l'achat de la position compte.",
    "Comparaison testeur / vérificateur (6 octobre 2026) : les deux programmes comptaient différemment ces 90 jours. "
    "Ce programme-ci les comptait depuis l'achat PRÉVU du nouvel événement (1er jour de bourse après son dépôt) et "
    "laissait passer un écart de 90 jours pile (compte du banc, « < 90 ») ; le testeur depuis son DÉPÔT, 90e jour "
    "compris. Un nouvel achat déposé 86 à 90 jours après le nôtre prolongeait la garde ici seulement (jeu ciblé : 13 "
    "cas, transactions différentes). Décision : la lecture du testeur, le sens le plus simple du texte : « avant » se "
    "rapporte à l'événement filtré, connu le jour de son dépôt (aucune date d'achat hypothétique à calculer), et un "
    "achat fait 90 jours avant est « dans les 90 jours civils avant ». Corrigé ici, dans sortir_avant().",
    "Titre disparu : TOLERANCE_SORTIE = 60 (aucun prix dans les 60 jours de bourse après la date de sortie : vente au "
    "dernier prix connu). Le banc ne peut PAS appliquer le « × 0,70 » : la vente se fait au dernier prix connu, sans la "
    "baisse de 30 %.",
    "Quand la vente vient de sortir_avant (sortie à 126 jours ou prolongée), le banc ne vend qu'un jour où il y a un "
    "prix : sans prix pendant 60 jours de bourse, la position reste jusqu'au prochain prix ou jusqu'au plafond de 252 "
    "jours (puis les 60 jours de TOLERANCE_SORTIE), au lieu d'être vendue au dernier prix × 0,70 après 60 jours.",
    "Taille (banc) : MAX_POSITIONS = 5, chaque achat vaut la valeur du portefeuille ÷ 5 = 20 % (valeur calculée par le "
    "banc avant les achats du jour, positions + argent qui attend), moins les 10 $ de frais. Argent qui attend dans "
    "SPY, vente de SPY pour acheter et rachat de SPY après chaque vente (LIQUIDE_JOURS = 0), 10 $ par opération SPY. "
    "Écart achat-vente du banc selon la valeur en bourse. MONTANT_MIN = 50 $ (réglage par défaut du banc ; le texte "
    "n'a pas de minimum).",
    "Le banc refuse un symbole déjà en portefeuille (par symbole) : deux symboles d'un même cik pourraient être détenus "
    "en même temps (cas rare, le texte dit « même cik_emetteur »).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252                     # plafond ; la sortie normale (126 jours de bourse) est faite par sortir_avant
TOLERANCE_SORTIE = 60
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 90

GARDE = 126                     # jours de bourse de détention (et après un nouvel événement)
DOUBLON_JOURS = 90              # « aucune autre entrée ... dans les 90 jours civils avant »


def _jour(x):
    return date.fromisoformat(x)


def _passe_filtre(e):
    """Le filtre du texte, sans la condition « aucune autre entrée dans les 90 jours » (faite ailleurs)."""
    if e.get("sens") != "achat":
        return False
    v = e.get("valeur_m")
    if v is None or not (300 <= v <= 3000):
        return False
    p = e.get("prix_moyen")
    if p is None or p < 5:
        return False
    m = e.get("montant")
    if m is None or m < 50000:
        return False
    if not any({"dirigeant", "administrateur"} & set(i.get("roles") or []) for i in (e.get("inities") or [])):
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    jd = e.get("jour_dernier")
    if not jd or (_jour(e["depot"]) - _jour(jd)).days > 4:
        return False
    return True


def garder(e, ctx):
    return _passe_filtre(e)


def priorite(e, ctx):
    # le plus haut d'abord : dépôt le plus ancien, puis montant le plus gros (entier : comparaison exacte)
    return -_jour(e["depot"]).toordinal() * 10 ** 20 + int(round((e.get("montant") or 0) * 100))


def _jours_apres(ctx, depuis):
    """Nombre de jours de bourse strictement après `depuis`, jusqu'au jour de la décision (compris)."""
    return sum(1 for j in ctx.jours_de_bourse(depuis) if j > depuis)


def sortir_avant(pos, jour, ctx):
    """`jour` = la veille : vendre à la clôture du jour de bourse suivant, qui est le (n + 1)-e après `depuis`."""
    achat = pos["entree"][0]
    if _jours_apres(ctx, achat) + 1 < GARDE:
        return False
    for x in ctx.evenements_avant(pos["cik"], achat):  # dépôts de la compagnie depuis le jour d'achat, jusqu'à `jour`
        if not _passe_filtre(x):
            continue
        if (_jour(x["depot"]) - _jour(achat)).days <= DOUBLON_JOURS:
            continue  # notre achat est dans les 90 jours civils avant ce dépôt : ne passe pas le filtre
        if _jours_apres(ctx, x["depot"]) + 1 < GARDE:
            return False  # sortie repoussée à 126 jours de bourse après ce nouvel événement
    return True
