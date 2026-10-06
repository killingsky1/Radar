"""liquidite_taille-3 : petites compagnies de qualité (100-500 M$), achat qui grossit vraiment la part de l'initié,
garder 12 mois.

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (regles_preenregistrees.json), sans voir
labo/tournoi/regles/. Chaque choix d'interprétation est dans CHOIX.
"""
from datetime import date, timedelta

ID = "liquidite_taille-3"

CHOIX = [
    "Formulaire avec plusieurs déclarants : « roles contient dirigeant ou administrateur » est vrai si AU MOINS UN "
    "déclarant a l'un de ces deux rôles.",
    "« valeur_m entre 100 M$ et 500 M$ » : bornes comprises. Une donnée absente (valeur_m, prix_moyen, montant, part "
    "ou jour_dernier vide) : l'événement n'est pas gardé.",
    "part_ajoutee = le champ part (actions achetées ÷ actions détenues avant) : gardé si part ≥ 0,10.",
    "« plan_10b5_1 différent de oui » : seul true est exclu ; false et vide (null) sont gardés. « routinier = non » : "
    "un événement routinier (true) est exclu.",
    "« depot au plus 4 jours civils après jour_dernier_achat » : (dépôt − jour_dernier) ≤ 4 jours civils, avec "
    "jour_dernier = la dernière date d'achat du formulaire. Un délai négatif (erreur de date dans le formulaire) passe.",
    "Qualité, « date d'entrée » : garder() est décidé le soir du dépôt et ne voit pas le calendrier de bourse après ce "
    "jour ; je prends l'entrée prévue = le 1er jour de semaine (lundi à vendredi) après le dépôt (les congés ne sont pas "
    "comptés). Si l'achat est retardé faute de prix, la décision déjà prise ne change pas.",
    "Qualité, « dernier rapport ANNUEL » : l'exercice (durée de 350 à 380 jours, comme le banc définit un exercice) le "
    "plus récent du flux de trésorerie d'exploitation (NetCashProvidedByUsedInOperatingActivities) dont la fin est au "
    "moins 120 jours civils avant l'entrée prévue ; capitaux propres = StockholdersEquity (bilan) à la date de fin de "
    "ce même exercice. Les deux doivent être strictement > 0. Un chiffre absent : pas gardé.",
    "Qualité : le banc ne montre un chiffre qu'à partir de son dépôt (première version déposée) ; un rapport annuel "
    "pas encore déposé le jour du dépôt du formulaire 4 est donc invisible, et c'est le dernier rapport annuel déjà "
    "déposé (qui respecte les 120 jours) qui sert.",
    "« Aucune autre entrée de cette règle sur le même cik dans les 180 jours civils avant » : réglage du banc "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 180, donc compté d'un jour d'ACHAT à l'autre, par SYMBOLE (pas par cik), bloqué si "
    "moins de 180 jours. En pratique sans effet : une position est gardée 252 jours de bourse et le banc n'achète "
    "jamais un symbole déjà détenu.",
    "Entrée : TOLERANCE_ENTREE = 5 (pas de prix SEC le 1er jour de bourse après le dépôt : 1re clôture des 5 jours de "
    "bourse suivants, sinon l'événement est abandonné).",
    "Places pleines : le signal est ignoré (banc). Ordre des signaux (priorite) : la date de dépôt la plus ancienne "
    "d'abord (« premier arrivé, premier servi »), puis, à date égale, la part_ajoutee la plus grande ; ensuite l'ordre "
    "du banc.",
    "Sortie : DUREE = 252, sans prolongation : 1re clôture SEC disponible à partir du 252e jour de bourse après le jour "
    "d'achat. Titre disparu : TOLERANCE_SORTIE = 60 (aucun prix dans les 60 jours de bourse après cette date : vente "
    "au dernier prix connu). Le banc ne peut PAS appliquer le « × 0,70 » : vente au dernier prix connu, sans la baisse "
    "de 30 %.",
    "Taille (banc) : MAX_POSITIONS = 5, chaque achat vaut la valeur du portefeuille ÷ 5 = 20 % (valeur calculée par le "
    "banc avant les achats du jour), moins les 10 $ de frais. Argent qui attend dans SPY, comme la règle 1 (vente de "
    "SPY pour acheter, rachat de SPY après chaque vente, LIQUIDE_JOURS = 0, 10 $ par opération SPY). Écart achat-vente "
    "du banc selon la valeur en bourse. MONTANT_MIN = 50 $ (réglage par défaut du banc ; le texte n'a pas de minimum).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 60
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 180

FLUX = "NetCashProvidedByUsedInOperatingActivities"
CAPITAUX = "StockholdersEquity"


def _jour(x):
    return date.fromisoformat(x)


def _entree_prevue(depot):
    j = _jour(depot) + timedelta(days=1)
    while j.weekday() >= 5:  # samedi, dimanche
        j += timedelta(days=1)
    return j


def _qualite(e, ctx):
    limite = (_entree_prevue(e["depot"]) - timedelta(days=120)).isoformat()
    f = ctx.finances(e["cik"])
    exercices = [x for x in f.get(FLUX, [])
                 if x[0] and x[1] <= limite and 350 <= (_jour(x[1]) - _jour(x[0])).days <= 380]
    if not exercices:
        return False
    dernier = max(exercices, key=lambda x: (x[1], x[0]))
    capitaux = [x for x in f.get(CAPITAUX, []) if x[0] is None and x[1] == dernier[1]]
    if not capitaux or dernier[2] is None or capitaux[-1][2] is None:
        return False
    return dernier[2] > 0 and capitaux[-1][2] > 0


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    v = e.get("valeur_m")
    if v is None or not (100 <= v <= 500):
        return False
    p = e.get("prix_moyen")
    if p is None or p < 5:
        return False
    m = e.get("montant")
    if m is None or m < 25000:
        return False
    part = e.get("part")
    if part is None or part < 0.10:
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
    return _qualite(e, ctx)


def priorite(e, ctx):
    # le plus haut d'abord : dépôt le plus ancien, puis part_ajoutee la plus grande (entier : comparaison exacte)
    part = min(max(e.get("part") or 0.0, 0.0), 1e12)
    return -_jour(e["depot"]).toordinal() * 10 ** 20 + int(round(part * 10 ** 6))
