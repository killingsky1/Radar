"""gestion-5 — Sortie sur ventes d'initiés : 12 mois, ou plus tôt si les initiés vendent.

Entrée : signal S de gestion-1, comme gestion-2. Sortie : à la clôture du 1er jour de bourse après le dépôt d'un
formulaire 4 de vente (code S) qui remplit une condition : (a) le même initié qui a donné le signal vend des actions de
la compagnie ; (b) au moins 2 initiés différents de la compagnie ont déposé des ventes code S non routinières et hors
plan 10b5-1 dans les 30 jours civils avant ce dépôt. Sinon, vente au 252e jour de bourse. Pas de rachat d'une
compagnie sortie avant 126 jours de bourse. Taille : 10 % du portefeuille, 10 positions, argent qui attend dans SPY.
"""
from collections import Counter
from datetime import date, timedelta

ID = "gestion-5"

CHOIX = [
    "Signal S, entrée et taille : exactement comme gestion-1 et gestion-2 (mêmes choix) : achat code P d'actions "
    "ordinaires = au moins un titre déclaré contenant « common » ou « ordinary » ; montant du formulaire ≥ 50 000 $ et "
    "valeur en bourse ≥ 100 M$ (vides : écarté) ; au moins un déclarant « administrateur » ou « dirigeant » ; "
    "routinier faux ; plan_10b5_1 différent de true (vide accepté à toute date) ; dépôt au plus 10 jours civils après "
    "jour_dernier (inconnu : écarté) ; priorite = montant ; JOURS_ENTREE = 1, TOLERANCE_ENTREE = 5 ; MAX_POSITIONS = "
    "10 (10 % du portefeuille, frais de 10 $ payés à même ces 10 %) ; argent qui attend dans SPY, vente remise dans "
    "SPY le jour même (LIQUIDE_JOURS = 0).",
    "Une position par compagnie (cik) : le banc refuse un 2e achat par SYMBOLE (garder() ne voit pas le portefeuille).",
    "« Minimum 1 000 $ » lu comme un plancher (le plus grand de 10 % et de 1 000 $) : pas programmable, poids() ne "
    "voit pas la valeur du portefeuille ; chaque achat reste à 10 %. MONTANT_MIN n'est pas mis à 1 000 (il ferait "
    "autre chose : ne pas acheter, et il refuserait même les achats de 990 $ + 10 $ de frais d'un portefeuille de "
    "10 000 $) ; il reste celui du banc (50 $).",
    "« Au plus une transaction SPY par jour » : le banc compte 10 $ de SPY par achat et par vente, même le même jour.",
    "Dépôts de vente qui déclenchent : seulement ceux déposés à partir du jour d'achat (on ne détient pas l'action "
    "avant ; un dépôt de vente plus ancien, par exemple dans le même formulaire que l'achat du signal, ne fait pas "
    "vendre). Une vente = un événement de sens « vente » (lignes code S) sur la même compagnie (même cik), tous "
    "titres confondus.",
    "(a) Même initié : le dépôt de vente a parmi ses déclarants un des déclarants du dépôt du signal (s'il y en a "
    "plusieurs, n'importe lequel), sans filtre routinier ni plan 10b5-1 (« toute vente code S du même initié »).",
    "(b) À un dépôt de vente F (n'importe lequel) : au moins 2 initiés différents (cik différents, tous rôles) ont des "
    "ventes avec routinier faux et plan_10b5_1 différent de true (vide accepté), déposées dans les 30 jours civils "
    "avant F, jour de F compris (F compte lui-même s'il remplit ces conditions ; c'est le 2e vendeur qui déclenche). "
    "Les ventes de cette fenêtre comptent même si elles sont d'avant l'achat. Un dépôt fait par 2 déclarants compte "
    "pour 2 initiés.",
    "Moment de la vente : le banc décide avec les dépôts connus la veille (sortir_avant voit la veille), donc vente à "
    "la clôture du 1er jour de bourse après le dépôt ; pas de prix ce jour-là : la vente reste demandée jusqu'à la 1re "
    "clôture SEC disponible. Un dépôt fait un jour sans bourse (ex. Vendredi saint) n'est vu que le jour de bourse "
    "suivant, donc vente un jour de bourse plus tard que dans le texte.",
    "Garde maximale : DUREE = 252 jours de bourse après le jour d'achat ; pas de prix ce jour-là : 1re clôture "
    "suivante, jusqu'à 20 jours de bourse, puis dernier prix connu (TOLERANCE_SORTIE = 20, « reste identique à "
    "gestion-2 », elle-même « comme gestion-1 »), même si un prix revenait plus tard.",
    "Fin des données : comme gestion-2, le banc n'évalue pas les positions au 30 juin 2026 ; il vend au 252e jour de "
    "bourse tant qu'il y a des prix, les plus récentes restent ouvertes (« en attente »).",
    "« On ne rachète pas une compagnie sortie avant 126 jours de bourse » : appliqué à toute sortie. La règle ne sait "
    "pas quand elle est sortie d'une compagnie (garder() ne voit pas le portefeuille), et le réglage du banc compte "
    "depuis l'ACHAT, en jours civils, par symbole : UNE_ENTREE_PAR_SYMBOLE_JOURS = 548, soit 252 jours de bourse de "
    "garde + 126 jours de bourse sans rachat = 378 jours de bourse ≈ 548 jours civils (252 jours de bourse par an). "
    "C'est exact pour une sortie au 252e jour ; après une sortie plus tôt (ventes d'initiés), le rachat est refusé "
    "plus longtemps que dans le texte (jusqu'à environ 18 mois après l'achat au lieu de 126 jours de bourse après la "
    "sortie).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 3 écarts, tranchés selon le texte ; le vérificateur est "
    "corrigé, le testeur ne change pas. 1) « d'actions ordinaires » est une condition écrite du signal S : filtre sur "
    "le champ titres (« common » ou « ordinary »), comme pour vitesse-1 ; le vérificateur ne filtrait pas. 2) « 10 % "
    "du portefeuille, minimum 1 000 $ » : le sens le plus simple est un plancher (le plus grand de 10 % et de "
    "1 000 $), pas programmable ; MONTANT_MIN = 1000 en changeait le sens (ne pas acheter) et, le banc retirant les "
    "10 $ de frais du montant, empêchait même les premiers achats d'un portefeuille de 10 000 $ (le cas du texte : "
    "des positions de 1 000 $) ; donc MONTANT_MIN = 50 du banc, comme le testeur. 3) « On ne rachète pas une "
    "compagnie sortie avant 126 jours de bourse » : compté depuis la SORTIE, pour toute sortie ; le banc compte "
    "depuis l'achat : UNE_ENTREE_PAR_SYMBOLE_JOURS = 548 (252 + 126 jours de bourse), exact après une sortie au 252e "
    "jour, comme le testeur ; 183 (126 jours de bourse depuis l'achat) ne bloquait rien après une sortie normale. "
    "Après correction : mêmes achats et ventes sur le faux jeu (et sur le jeu ciblé de gestion-3).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 548

MONTANT_MIN_SIGNAL = 50_000      # $
VALEUR_MIN_M = 100               # M$
RETARD_MAX_JOURS = 10            # jours civils entre le dernier achat et le dépôt
ROLES_OK = ("administrateur", "dirigeant")
FENETRE_VENTES_JOURS = 30        # jours civils avant le dépôt de vente, condition (b)
VENDEURS_MIN = 2                 # initiés différents, condition (b)
RECHERCHE_SIGNAL_JOURS = 60      # pour retrouver le dépôt du signal (déposé au plus ~6 jours de bourse avant l'achat)


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


def _ciks(e):
    return {i.get("cik") for i in (e.get("inities") or [])}


def sortir_avant(pos, jour, ctx):
    """Vrai si un dépôt de vente code S sur la compagnie, fait du jour d'achat à `jour`, remplit (a) ou (b)."""
    entree = pos["entree"][0]
    d_entree = date.fromisoformat(entree)
    evs = ctx.evenements_avant(pos["cik"], (d_entree - timedelta(days=RECHERCHE_SIGNAL_JOURS)).isoformat())
    signal = next((x for x in evs if x.get("id") == pos["id"]), None)
    qui = _ciks(signal) if signal else set()
    debut = (d_entree - timedelta(days=FENETRE_VENTES_JOURS)).isoformat()
    ventes = [x for x in evs if x.get("sens") == "vente" and x["depot"] >= debut]  # dans l'ordre des dépôts
    # (a) le même initié vend
    if qui and any(f["depot"] >= entree and qui & _ciks(f) for f in ventes):
        return True
    # (b) au moins 2 initiés différents : ventes non routinières, hors plan 10b5-1, dans les 30 jours avant F (F compris)
    qualif = [x for x in ventes if x.get("routinier") is False and x.get("plan_10b5_1") is not True]
    compte, i_ajout, i_retrait = Counter(), 0, 0
    for f in ventes:
        if f["depot"] < entree:
            continue
        fin = f["depot"]
        depuis = (date.fromisoformat(fin) - timedelta(days=FENETRE_VENTES_JOURS)).isoformat()
        while i_ajout < len(qualif) and qualif[i_ajout]["depot"] <= fin:
            compte.update(_ciks(qualif[i_ajout]))
            i_ajout += 1
        while i_retrait < i_ajout and qualif[i_retrait]["depot"] < depuis:
            compte.subtract(_ciks(qualif[i_retrait]))
            i_retrait += 1
        if sum(1 for n in compte.values() if n > 0) >= VENDEURS_MIN:
            return True
    return False
