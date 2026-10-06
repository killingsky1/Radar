"""gestion-4 : témoin, gestion-1 avec un seuil de perte de 20 %.

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (labo/tournoi/regles_preenregistrees.json),
sans voir labo/tournoi/regles/.
- Signal, entrée, taille : identiques à gestion-1 (signal S ; 10 places de 10 %, minimum 1 000 $ ; attente dans SPY).
- Sortie : dès qu'une clôture SEC est au moins 20 % sous le prix d'achat, vente (à la clôture suivante, règle du
  banc) ; sinon au 126e jour de bourse comme gestion-1. Pas d'objectif de profit.
- Pas de rachat de la même compagnie avant 126 jours de bourse (pause du banc, comptée depuis
  l'achat : 126 + 126 jours de bourse ≈ 365 jours civils).
"""
from datetime import date

ID = "gestion-4"

CHOIX = [
    # --- Le signal S (identique à gestion-1) ---
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
    "« Une seule position par compagnie » : fait par le banc, qui compare les SYMBOLES ; une compagnie à deux symboles "
    "(deux catégories d'actions) pourrait avoir deux positions (rare). Une règle ne voit pas son portefeuille, elle ne "
    "peut pas le faire par cik.",
    "Plus de candidats que de places le même jour : priorite = montant (le plus gros d'abord). Le banc classe ensemble "
    "les signaux du jour et ceux qui attendent encore un prix ; un signal sans place est abandonné.",
    # --- Entrée ---
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (pas de prix SEC le 1er jour de bourse après le dépôt : la 1re "
    "clôture des 5 jours de bourse suivants, sinon le signal est abandonné).",
    # --- Le seuil de perte ---
    "Seuil de perte : vérifié sur chaque clôture SEC disponible depuis l'achat ; déclenché si la clôture vaut au plus "
    "80 % du prix d'achat (la clôture d'entrée du banc), c.-à-d. au moins 20 % dessous (-20 % pile compte ; petite "
    "marge de 1e-9 pour les arrondis des nombres à virgule).",
    "Changement de CUSIP (regroupement d'actions) entre l'achat et la clôture : la baisse est mesurée en enchaînant les "
    "prix de part et d'autre du changement, comme le banc mesure le rendement (on ne compare jamais deux prix de CUSIP "
    "différents).",
    "Moment de la vente (comportement standard du banc) : le seuil est vu à la clôture d'un jour (sortir_avant voit la "
    "veille) et le banc vend à la clôture du jour de bourse SUIVANT qui a un prix SEC, pas à la clôture même qui "
    "franchit le seuil (au moment de vendre, on ne connaît pas encore ce prix-là). Le prix réel de sortie est noté.",
    "Sans seuil touché : DUREE = 126 et TOLERANCE_SORTIE = 20, comme gestion-1 (1re clôture des 20 jours de bourse "
    "suivants, sinon la dernière clôture connue). Une vente par le seuil sans prix SEC attend le 1er jour qui a un prix "
    "(le banc n'a pas de limite pour une vente anticipée ; au 126e jour, la règle normale reprend).",
    "« On ne rachète pas une compagnie sortie avant 126 jours de bourse » (paramètres) : 126 jours de bourse comptés "
    "depuis la SORTIE, pour toute sortie. Le banc ne sait compter qu'à partir de l'ACHAT précédent du même symbole, "
    "en jours civils : UNE_ENTREE_PAR_SYMBOLE_JOURS = 365 (126 jours de bourse de garde + 126 jours de bourse sans "
    "rachat = 252 jours de bourse ≈ 365 jours civils). Exact après une sortie au 126e jour ; après une sortie au "
    "seuil de perte (plus tôt), le rachat est refusé plus longtemps que dans le texte (jusqu'à environ 1 an après "
    "l'achat).",
    # --- Taille et argent qui attend (identiques à gestion-1) ---
    "Taille : MAX_POSITIONS = 10 ; le banc vise valeur du portefeuille (positions + SPY + comptant) / 10 = 10 %, à la "
    "clôture du jour d'achat ; les 10 $ de frais de l'achat sont pris dans ces 10 %. S'il reste moins d'argent (places "
    "presque toutes prises), le banc achète avec ce qui reste, si c'est au moins MONTANT_MIN. Une place libérée par le "
    "seuil sert au prochain signal.",
    "« Minimum 1 000 $ » : lu comme un plancher (achat = le plus grand de 10 % et de 1 000 $), pas programmable : une "
    "règle ne voit pas la valeur de son portefeuille. Chaque achat reste donc à 10 %, un peu sous 1 000 $ quand le "
    "portefeuille vaut moins de 10 000 $. MONTANT_MIN reste celui du banc (50 $) : MONTANT_MIN = 1000 ferait autre "
    "chose (ne pas acheter du tout) et, comme le banc compare 1 000 $ au montant APRÈS les 10 $ de frais, il "
    "refuserait même les premiers achats d'un portefeuille de 10 000 $ (990 $ investis).",
    "Argent qui attend : ARGENT_QUI_ATTEND = 'SPY' et LIQUIDE_JOURS = 0 (le produit d'une vente retourne dans SPY le "
    "jour même, comme gestion-1). Le banc compte 10 $ de SPY à chaque achat et à chaque vente d'une position (pas de "
    "regroupement « une transaction SPY par jour »).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 3 écarts, tranchés selon le texte ; le vérificateur est "
    "corrigé, le testeur ne change pas. 1) « d'actions ordinaires » est une condition écrite du signal S : filtre sur "
    "le champ titres (« common » ou « ordinary »), comme pour vitesse-1 ; le vérificateur ne filtrait pas. 2) « 10 % "
    "du portefeuille, minimum 1 000 $ » : le sens le plus simple est un plancher (le plus grand de 10 % et de "
    "1 000 $), pas programmable ; MONTANT_MIN = 1000 en changeait le sens (ne pas acheter) et, le banc retirant les "
    "10 $ de frais du montant, empêchait même les premiers achats d'un portefeuille de 10 000 $ (le cas du texte : "
    "des positions de 1 000 $) ; donc MONTANT_MIN = 50 du banc, comme le testeur. 3) « On ne rachète pas une "
    "compagnie sortie avant 126 jours de bourse » : compté depuis la SORTIE, pour toute sortie (« une compagnie "
    "sortie ») ; le banc compte depuis l'achat : UNE_ENTREE_PAR_SYMBOLE_JOURS = 365 (126 + 126 jours de bourse), "
    "exact après une sortie au 126e jour, comme le testeur ; 183 (126 jours de bourse depuis l'achat) ne bloquait "
    "presque rien après une sortie normale. "
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
UNE_ENTREE_PAR_SYMBOLE_JOURS = 365

ROLES_SIGNAL = ("administrateur", "dirigeant")
SEUIL_PERTE = 0.80  # clôture / prix d'achat


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


def sortir_avant(pos, jour, ctx):
    """Vrai si une clôture SEC connue au plus tard `jour`, depuis l'achat, vaut au plus 80 % du prix d'achat
    (prix enchaînés de part et d'autre d'un changement de CUSIP, comme le banc)."""
    clotures = ctx.clotures(pos["s"], pos["entree"][0], jour)
    if not clotures:
        return False
    facteur, base = 1.0, clotures[0][1]
    for k in range(1, len(clotures)):
        prix, cusip = clotures[k][1], clotures[k][2]
        if cusip != clotures[k - 1][2]:
            if not base or base <= 0:  # prix nul : impossible d'enchaîner (le banc non plus)
                return False
            facteur *= clotures[k - 1][1] / base
            base = prix
        if base and base > 0 and facteur * prix / base <= SEUIL_PERTE + 1e-9:
            return True
    return False
