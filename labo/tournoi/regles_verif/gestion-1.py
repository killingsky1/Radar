"""gestion-1 : signal strict (signal S), garder 6 mois (126 jours de bourse), 10 positions au maximum.

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (labo/tournoi/regles_preenregistrees.json),
sans voir labo/tournoi/regles/.
- Signal S : achat (code P) ; au moins un déclarant administrateur ou dirigeant ; routinier = non ; plan_10b5_1 pas
  « oui » ; montant >= 50 000 $ ; valeur_m >= 100 M$ ; dépôt au plus 10 jours civils après le dernier achat.
- Entrée : clôture SEC du 1er jour de bourse après le dépôt (sinon 1re clôture des 5 jours de bourse suivants).
- Sortie : clôture du 126e jour de bourse après l'achat (sinon 1re clôture des 20 jours de bourse suivants, sinon la
  dernière connue). Pas de seuil de perte, pas d'objectif.
- Taille : 10 % du portefeuille (10 places), au minimum 1 000 $ ; l'argent qui attend est dans SPY.
"""
from datetime import date

ID = "gestion-1"

CHOIX = [
    # --- Le signal S ---
    "« Formulaire 4 avec au moins un achat code P d'actions ordinaires » : on garde les événements sens = « achat » "
    "(code P, titres non dérivés, en bourse) dont au moins un titre déclaré (champ titres, texte libre) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; un formulaire qui n'achète que d'autres titres "
    "(actions privilégiées, parts, « Shares » seul, etc.) est écarté.",
    "Rôles : il suffit qu'UN des déclarants du formulaire (e['inities']) ait « administrateur » ou « dirigeant » dans "
    "ses rôles ; un formulaire dont les déclarants sont seulement « actionnaire de 10 % » ou « autre » est exclu.",
    "routinier = non : gardé seulement si e['routinier'] vaut False.",
    "plan_10b5_1 différent de « oui » : exclu seulement s'il vaut True ; False et vide (None) sont acceptés, à toutes "
    "les dates (pas seulement avant avril 2023), car vide est « différent de oui ».",
    "montant ou valeur_m inconnu (None) : exclu, car on ne peut pas vérifier le seuil (50 000 $ ; 100 M$).",
    "Dépôt en retard : gardé si (depot - jour_dernier) <= 10 jours civils ; jour_dernier inconnu : exclu (on ne peut pas "
    "vérifier).",
    "« Une seule position par compagnie (cik_emetteur) » : fait par le banc, qui compare les SYMBOLES ; une compagnie à "
    "deux symboles (deux catégories d'actions) pourrait avoir deux positions (rare). Une règle ne voit pas son "
    "portefeuille, elle ne peut pas le faire par cik.",
    "Plus de candidats que de places le même jour : priorite = montant (le plus gros d'abord). Le banc classe ensemble "
    "les signaux du jour et ceux qui attendent encore un prix ; un signal sans place est abandonné.",
    # --- Entrée et sortie ---
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (pas de prix SEC le 1er jour de bourse après le dépôt : la 1re "
    "clôture des 5 jours de bourse suivants, sinon le signal est abandonné).",
    "Sortie : DUREE = 126 et TOLERANCE_SORTIE = 20 : le banc vend à la clôture du 126e jour de bourse après l'achat, "
    "ou à la 1re clôture des 20 jours de bourse suivants ; sinon à la dernière clôture connue. Le texte ajoute « et "
    "qu'il n'y en a plus jamais » : le savoir serait de l'information du futur, donc (règle du banc, comme le dit le "
    "texte) on prend la dernière clôture connue après 20 jours de bourse sans prix, même si un prix revient plus tard.",
    # --- Taille et argent qui attend ---
    "Taille : MAX_POSITIONS = 10 ; le banc vise valeur du portefeuille (positions + SPY + comptant) / 10 = 10 %, à la "
    "clôture du jour d'achat ; les 10 $ de frais de l'achat sont pris dans ces 10 %. S'il reste moins d'argent (places "
    "presque toutes prises), le banc achète avec ce qui reste, si c'est au moins MONTANT_MIN.",
    "« Au minimum 1 000 $ » : lu comme un plancher (achat = le plus grand de 10 % et de 1 000 $), pas programmable : "
    "une règle ne voit pas la valeur de son portefeuille. Chaque achat reste donc à 10 %, un peu sous 1 000 $ quand "
    "le portefeuille vaut moins de 10 000 $. MONTANT_MIN reste celui du banc (50 $) : MONTANT_MIN = 1000 ferait autre "
    "chose (ne pas acheter du tout) et, comme le banc compare 1 000 $ au montant APRÈS les 10 $ de frais, il "
    "refuserait même les premiers achats d'un portefeuille de 10 000 $ (990 $ investis).",
    "Argent qui attend : ARGENT_QUI_ATTEND = 'SPY' et LIQUIDE_JOURS = 0 (le produit d'une vente retourne dans SPY le "
    "jour même, comme le dit le texte).",
    "« Au plus une transaction SPY par jour » : le banc ne regroupe pas les transactions SPY d'un même jour ; il compte "
    "10 $ de SPY à chaque achat et à chaque vente d'une position (comportement standard du banc, un peu plus cher que "
    "le texte).",
    "Pas de pause après une vente (UNE_ENTREE_PAR_SYMBOLE_JOURS = 0) : le texte n'interdit pas de racheter une "
    "compagnie après sa vente.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 2 écarts, tranchés selon le texte ; le vérificateur est "
    "corrigé, le testeur ne change pas. 1) « d'actions ordinaires » est une condition écrite du signal S : filtre sur "
    "le champ titres (« common » ou « ordinary »), comme pour vitesse-1 ; le vérificateur ne filtrait pas. 2) « 10 % "
    "du portefeuille, minimum 1 000 $ » : le sens le plus simple est un plancher (le plus grand de 10 % et de "
    "1 000 $), pas programmable ; MONTANT_MIN = 1000 en changeait le sens (ne pas acheter) et, le banc retirant les "
    "10 $ de frais du montant, empêchait même les premiers achats d'un portefeuille de 10 000 $ (le cas du texte : "
    "des positions de 1 000 $) ; donc MONTANT_MIN = 50 du banc, comme le testeur. "
    "Après correction : mêmes achats et ventes sur le faux jeu (et sur le jeu ciblé de gestion-3).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

ROLES_SIGNAL = ("administrateur", "dirigeant")


def signal_s(e):
    """Le signal S commun à gestion-1, 2, 4 et 5 (et base de gestion-3)."""
    if e.get("sens") != "achat":
        return False
    if not any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or []):
        return False
    if not any(r in ROLES_SIGNAL for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant = e.get("montant")
    if montant is None or montant < 50_000:
        return False
    valeur_m = e.get("valeur_m")
    if valeur_m is None or valeur_m < 100:
        return False
    try:
        retard = (date.fromisoformat(e["depot"]) - date.fromisoformat(e["jour_dernier"])).days
    except (KeyError, TypeError, ValueError):
        return False
    return retard <= 10


def garder(e, ctx):
    return signal_s(e)


def priorite(e, ctx):
    return float(e.get("montant") or 0.0)
