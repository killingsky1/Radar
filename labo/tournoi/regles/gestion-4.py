"""gestion-4 — Témoin : gestion-1 avec un seuil de perte de 20 %.

Identique à gestion-1 (signal S, entrée, taille, garde maximale de 126 jours de bourse), plus un seuil de perte : on vend
dès qu'une clôture SEC est au moins 20 % sous le prix d'achat. Une position vendue libère sa place ; on ne rachète pas
une compagnie sortie avant 126 jours de bourse.
"""
from datetime import date

ID = "gestion-4"

CHOIX = [
    "Signal S, entrée et taille : exactement comme gestion-1 (mêmes choix) : achat code P d'actions ordinaires = au "
    "moins un titre déclaré contenant « common » ou « ordinary » ; montant du formulaire ≥ 50 000 $ et valeur en "
    "bourse ≥ 100 M$ (vides : écarté) ; au moins un déclarant « administrateur » ou « dirigeant » ; routinier faux ; "
    "plan_10b5_1 différent de true (vide accepté à toute date) ; dépôt au plus 10 jours civils après jour_dernier "
    "(inconnu : écarté) ; priorite = montant ; JOURS_ENTREE = 1, TOLERANCE_ENTREE = 5 ; MAX_POSITIONS = 10 (10 % du "
    "portefeuille, frais de 10 $ payés à même ces 10 %) ; argent qui attend dans SPY, vente remise dans SPY le jour même "
    "(LIQUIDE_JOURS = 0).",
    "Une position par compagnie (cik) : le banc refuse un 2e achat par SYMBOLE (garder() ne voit pas le portefeuille).",
    "« Minimum 1 000 $ » lu comme un plancher (le plus grand de 10 % et de 1 000 $) : pas programmable, poids() ne "
    "voit pas la valeur du portefeuille ; chaque achat reste à 10 %. MONTANT_MIN n'est pas mis à 1 000 (il ferait "
    "autre chose : ne pas acheter, et il refuserait même les achats de 990 $ + 10 $ de frais d'un portefeuille de "
    "10 000 $) ; il reste celui du banc (50 $).",
    "« Au plus une transaction SPY par jour » (taille de gestion-1) : le banc compte 10 $ de SPY par achat et par "
    "vente, même le même jour.",
    "Seuil de perte : vérifié sur chaque clôture SEC après le jour d'achat, jusqu'à la veille de la décision. Une "
    "clôture déclenche si le rendement depuis le prix d'achat est de −20 % ou pire (clôture ≤ 0,80 × prix d'achat). "
    "S'il y a un changement de CUSIP (regroupement d'actions), le rendement est enchaîné de part et d'autre du "
    "changement, comme le banc le fait pour toutes les positions (on ne compare pas deux prix de CUSIP différents).",
    "Moment de la vente au seuil : le banc décide avec la clôture de la veille (sortir_avant voit la veille) ; on vend "
    "donc à la clôture SEC SUIVANTE disponible (au plus tôt le jour de bourse d'après), pas à la clôture même qui "
    "franchit le seuil. Une fois le seuil franchi, la vente reste demandée chaque jour jusqu'à ce qu'un prix existe "
    "(même si ce prix est remonté au-dessus du seuil).",
    "Garde maximale : DUREE = 126 jours de bourse après le jour d'achat ; pas de prix ce jour-là : 1re clôture "
    "suivante, jusqu'à 20 jours de bourse (TOLERANCE_SORTIE = 20, « identique à gestion-1 »), puis dernier prix connu, "
    "même si un prix revenait plus tard (« il n'y en a plus jamais » demande le futur).",
    "« On ne rachète pas une compagnie sortie avant 126 jours de bourse » : appliqué à toute sortie (le texte des "
    "paramètres dit « une compagnie sortie »). La règle ne sait pas quand elle est sortie d'une compagnie (garder() "
    "ne voit pas le portefeuille), et le réglage du banc compte depuis l'ACHAT, en jours civils, par symbole : "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 365, soit 126 jours de bourse de garde + 126 jours de bourse sans rachat = 252 "
    "jours de bourse ≈ 365 jours civils. C'est exact pour une sortie au 126e jour ; après une sortie au seuil de perte "
    "(plus tôt), le rachat est refusé plus longtemps que dans le texte (jusqu'à environ 1 an après l'achat au lieu de "
    "126 jours de bourse après la sortie).",
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
UNE_ENTREE_PAR_SYMBOLE_JOURS = 365

MONTANT_MIN_SIGNAL = 50_000      # $
VALEUR_MIN_M = 100               # M$
RETARD_MAX_JOURS = 10            # jours civils entre le dernier achat et le dépôt
ROLES_OK = ("administrateur", "dirigeant")
SEUIL_PERTE = -0.20              # rendement depuis le prix d'achat


def _actions_ordinaires(e):
    for t in e.get("titres") or []:
        t = (t or "").lower()
        if "common" in t or "ordinary" in t:
            return True
    return False


def signal_s(e):
    """Le signal S de gestion-1."""
    if e.get("sens") != "achat" or not _actions_ordinaires(e):
        return False
    if not any(r in (i.get("roles") or []) for i in (e.get("inities") or []) for r in ROLES_OK):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant, valeur = e.get("montant"), e.get("valeur_m")
    if montant is None or montant < MONTANT_MIN_SIGNAL:
        return False
    if valeur is None or valeur < VALEUR_MIN_M:
        return False
    if not e.get("jour_dernier"):
        return False
    return (date.fromisoformat(e["depot"]) - date.fromisoformat(e["jour_dernier"])).days <= RETARD_MAX_JOURS


def garder(e, ctx):
    return signal_s(e)


def priorite(e, ctx):
    return e.get("montant") or 0.0


def sortir_avant(pos, jour, ctx):
    """Vrai si une clôture SEC après l'achat (jusqu'à `jour`) est à −20 % ou pire du prix d'achat (rendement enchaîné
    de part et d'autre d'un changement de CUSIP, comme le banc)."""
    entree = pos["entree"]  # (date, prix, cusip) de la clôture d'achat
    cl = [entree] + [c for c in ctx.clotures(pos["s"], entree[0], jour) if c[0] > entree[0]]
    r, base = 1.0, entree[1]
    for k in range(1, len(cl)):
        if cl[k][2] != cl[k - 1][2]:
            if base > 0:
                r *= cl[k - 1][1] / base
            base = cl[k][1]
        if base > 0 and r * cl[k][1] / base - 1 <= SEUIL_PERTE + 1e-9:
            return True
    return False
