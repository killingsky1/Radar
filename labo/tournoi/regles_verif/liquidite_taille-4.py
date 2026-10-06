"""liquidite_taille-4 : grandes compagnies (>= 10 G$), achat du PDG ou du chef des finances, garder 12 mois.

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (regles_preenregistrees.json), sans voir
labo/tournoi/regles/. Chaque choix d'interprétation est dans CHOIX.
"""
from datetime import date

ID = "liquidite_taille-4"

CHOIX = [
    "Titre : gardé si le titre (texte libre) d'AU MOINS UN déclarant contient, sans tenir compte des majuscules, "
    "« ceo », « chief executive », « cfo » ou « chief financial », comme simple bout de texte (ex. « Deputy CFO » ou "
    "« Former CEO » comptent). Le rôle déclaré n'est pas vérifié en plus : le texte ne demande que le titre.",
    "« valeur_m >= 10 000 M$ » et « montant >= 100 000 $ » : bornes comprises. Une donnée absente (valeur_m, montant "
    "ou jour_dernier vide) : l'événement n'est pas gardé. Pas de condition de prix minimum ni de rôle : le texte n'en "
    "met pas.",
    "« plan_10b5_1 différent de oui » : seul true est exclu ; false et vide (null) sont gardés. « routinier = non » : "
    "un événement routinier (true) est exclu.",
    "« depot au plus 4 jours civils après jour_dernier_achat » : (dépôt − jour_dernier) ≤ 4 jours civils, avec "
    "jour_dernier = la dernière date d'achat du formulaire. Un délai négatif (erreur de date dans le formulaire) passe.",
    "« Aucune autre entrée de cette règle sur le même cik dans les 180 jours civils avant » : réglage du banc "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 180, donc compté d'un jour d'ACHAT à l'autre, par SYMBOLE (pas par cik), bloqué si "
    "moins de 180 jours. En pratique sans effet : une position est gardée 252 jours de bourse et le banc n'achète "
    "jamais un symbole déjà détenu.",
    "Entrée : TOLERANCE_ENTREE = 5 (pas de prix SEC le 1er jour de bourse après le dépôt : 1re clôture des 5 jours de "
    "bourse suivants, sinon l'événement est abandonné).",
    "Places pleines : le signal est ignoré (banc). Ordre des signaux (priorite) : la date de dépôt la plus ancienne "
    "d'abord (« premier arrivé, premier servi »), puis, à date égale, le montant le plus gros ; ensuite l'ordre du banc.",
    "Sortie : DUREE = 252 : 1re clôture SEC disponible à partir du 252e jour de bourse après le jour d'achat.",
    "« Titre disparu » n'est pas défini dans cette règle : je prends la définition de liquidite_taille-1 (même piste, "
    "même mot) : aucun prix SEC dans les 60 jours de bourse après la date de sortie, donc TOLERANCE_SORTIE = 60 (vente "
    "au dernier prix connu). Le banc ne peut PAS appliquer le « × 0,70 » : vente au dernier prix connu, sans la baisse "
    "de 30 %.",
    "Taille (banc) : MAX_POSITIONS = 4, chaque achat vaut la valeur du portefeuille ÷ 4 = 25 % (valeur calculée par le "
    "banc avant les achats du jour), moins les 10 $ de frais. Argent qui attend dans SPY (vente de SPY pour acheter, "
    "rachat de SPY après chaque vente, LIQUIDE_JOURS = 0, 10 $ par opération SPY). Écart achat-vente du banc selon la "
    "valeur en bourse. MONTANT_MIN = 50 $ (réglage par défaut du banc ; le texte n'a pas de minimum).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 60
MAX_POSITIONS = 4
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 180

MOTS = ("ceo", "chief executive", "cfo", "chief financial")


def _jour(x):
    return date.fromisoformat(x)


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    v = e.get("valeur_m")
    if v is None or v < 10000:
        return False
    if not any(any(mot in (i.get("titre") or "").lower() for mot in MOTS) for i in (e.get("inities") or [])):
        return False
    m = e.get("montant")
    if m is None or m < 100000:
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    jd = e.get("jour_dernier")
    if not jd or (_jour(e["depot"]) - _jour(jd)).days > 4:
        return False
    return True


def priorite(e, ctx):
    # le plus haut d'abord : dépôt le plus ancien, puis montant le plus gros (entier : comparaison exacte)
    return -_jour(e["depot"]).toordinal() * 10 ** 20 + int(round((e.get("montant") or 0) * 100))
