"""gestion-5 : garder 12 mois (252 jours de bourse), ou sortir plus tôt si les initiés vendent.

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (labo/tournoi/regles_preenregistrees.json),
sans voir labo/tournoi/regles/.
- Entrée : signal S de gestion-1 ; clôture SEC du 1er jour de bourse après le dépôt (5 jours de bourse de tolérance).
- Sortie : à la clôture du 1er jour de bourse après le dépôt d'un formulaire 4 de vente (code S) sur la compagnie si
  (a) un initié qui a donné le signal vend, ou (b) au moins 2 initiés différents de la compagnie ont déposé des ventes
  non routinières hors plan 10b5-1 dans les 30 jours civils avant ce dépôt ; sinon au 252e jour de bourse.
- Taille : 10 % du portefeuille (10 places), minimum 1 000 $ ; attente dans SPY ; pas de rachat avant 126 jours de
  bourse (pause du banc, comptée depuis l'achat :
  252 + 126 jours de bourse ≈ 548 jours civils).
"""
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

ID = "gestion-5"

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
    "les dates (pas seulement avant avril 2023), car vide est « différent de oui ». Même lecture pour les ventes de la "
    "sortie (b).",
    "montant ou valeur_m inconnu (None) : exclu, car on ne peut pas vérifier le seuil (50 000 $ ; 100 M$).",
    "Dépôt en retard : gardé si (depot - jour_dernier) <= 10 jours civils ; jour_dernier inconnu : exclu (on ne peut pas "
    "vérifier).",
    "« Une seule position par compagnie » : fait par le banc, qui compare les SYMBOLES ; une compagnie à deux symboles "
    "(deux catégories d'actions) pourrait avoir deux positions (rare). Une règle ne voit pas son portefeuille, elle ne "
    "peut pas le faire par cik.",
    "Plus de candidats que de places le même jour : priorite = montant (le plus gros d'abord), comme gestion-1. Le banc "
    "classe ensemble les signaux du jour et ceux qui attendent encore un prix ; un signal sans place est abandonné.",
    # --- Entrée ---
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (pas de prix SEC le 1er jour de bourse après le dépôt : la 1re "
    "clôture des 5 jours de bourse suivants, sinon le signal est abandonné).",
    # --- Sortie sur ventes d'initiés ---
    "Ventes qui déclenchent : les formulaires 4 de vente (sens = « vente », code S) sur la même compagnie (cik de la "
    "position), déposés à partir du jour de l'achat (un dépôt du jour d'achat n'est connu que le soir, après l'achat à "
    "la clôture). Une vente déposée avant l'achat ne déclenche rien (le 1er jour de bourse après elle n'est pas après "
    "l'achat).",
    "(a) « Le même initié (initie_cik) qui a donné le signal » : un des déclarants du formulaire d'achat du signal (s'il "
    "y en a plusieurs, n'importe lequel) est aussi déclarant de la vente ; toute vente compte (routinière ou non, plan "
    "10b5-1 ou non : « toute vente code S du même initié »).",
    "(b) Pour un dépôt de vente D (n'importe quelle vente sur la compagnie) : on compte les initiés DIFFÉRENTS (cik des "
    "déclarants, quel que soit leur rôle) des ventes sur la compagnie avec routinier = False et plan_10b5_1 pas True, "
    "déposées du jour D - 30 jours civils au jour D compris (même convention que groupe_30j) ; 2 ou plus : sortie. Ces "
    "ventes comptées peuvent dater d'avant l'achat (le texte dit seulement « dans les 30 jours civils avant ce dépôt »). "
    "Un formulaire signé par plusieurs déclarants compte chacun d'eux.",
    "Moment de la vente (comportement standard du banc) : sortir_avant voit les dépôts faits au plus tard la veille ; "
    "le banc vend donc à la clôture du 1er jour de bourse après le dépôt de la vente, s'il y a un prix SEC ce jour-là, "
    "sinon au 1er jour suivant qui en a un (au 252e jour, la règle normale reprend). Un dépôt fait un jour sans bourse "
    "(ex. Vendredi saint) n'est vu qu'un jour de bourse plus tard.",
    "Sinon : DUREE = 252 et TOLERANCE_SORTIE = 20 (« reste identique à gestion-2 », elle-même comme gestion-1) : 1re "
    "clôture des 20 jours de bourse suivants, sinon la dernière clôture connue.",
    "Positions achetées moins de 252 jours de bourse avant la fin des prix et jamais vendues plus tôt : elles restent "
    "ouvertes à la fin (comportement standard du banc, qui les compte comme achats « en attente »).",
    "« On ne rachète pas une compagnie sortie avant 126 jours de bourse » : 126 jours de bourse comptés depuis la "
    "SORTIE, pour toute sortie. Le banc ne sait compter qu'à partir de l'ACHAT précédent du même symbole, en jours "
    "civils : UNE_ENTREE_PAR_SYMBOLE_JOURS = 548 (252 jours de bourse de garde + 126 jours de bourse sans rachat = "
    "378 jours de bourse ≈ 548 jours civils). Exact après une sortie au 252e jour ; après une sortie plus tôt (ventes "
    "d'initiés), le rachat est refusé plus longtemps que dans le texte (jusqu'à environ 18 mois après l'achat).",
    # --- Taille et argent qui attend ---
    "Taille : MAX_POSITIONS = 10 ; le banc vise valeur du portefeuille (positions + SPY + comptant) / 10 = 10 %, à la "
    "clôture du jour d'achat ; les 10 $ de frais de l'achat sont pris dans ces 10 %. S'il reste moins d'argent (places "
    "presque toutes prises), le banc achète avec ce qui reste, si c'est au moins MONTANT_MIN.",
    "« Minimum 1 000 $ » : lu comme un plancher (achat = le plus grand de 10 % et de 1 000 $), pas programmable : une "
    "règle ne voit pas la valeur de son portefeuille. Chaque achat reste donc à 10 %, un peu sous 1 000 $ quand le "
    "portefeuille vaut moins de 10 000 $. MONTANT_MIN reste celui du banc (50 $) : MONTANT_MIN = 1000 ferait autre "
    "chose (ne pas acheter du tout) et, comme le banc compare 1 000 $ au montant APRÈS les 10 $ de frais, il "
    "refuserait même les premiers achats d'un portefeuille de 10 000 $ (990 $ investis).",
    "Argent qui attend : ARGENT_QUI_ATTEND = 'SPY' et LIQUIDE_JOURS = 0 (le produit d'une vente retourne dans SPY le "
    "jour même). « Au plus une transaction SPY par jour » : le banc ne regroupe pas ; il compte 10 $ de SPY à chaque "
    "achat et à chaque vente d'une position (comportement standard du banc, un peu plus cher que le texte).",
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
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 548

ROLES_SIGNAL = ("administrateur", "dirigeant")
FENETRE_VENTES = 30  # jours civils avant le dépôt de la vente (celui-ci compris)


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


def _ciks(x):
    return {i.get("cik") for i in (x.get("inities") or []) if i.get("cik")}


def sortir_avant(pos, jour, ctx):
    """Vrai si, depuis le jour d'achat jusqu'à `jour` (la veille de la vente), un formulaire de vente sur la compagnie
    remplit (a) ou (b)."""
    entree = pos["entree"][0]
    # 60 jours avant l'achat : couvre le dépôt du signal (au plus 6 jours de bourse avant l'achat) et les 30 jours
    # avant la plus ancienne vente qui peut déclencher (déposée au plus tôt le jour d'achat).
    depuis = (date.fromisoformat(entree) - timedelta(days=60)).isoformat()
    evs = ctx.evenements_avant(pos["cik"], depuis)  # triés par (dépôt, numéro)
    signal = next((x for x in evs if x.get("id") == pos["id"]), None)
    initie_signal = _ciks(signal) if signal else set()
    ventes = [x for x in evs if x.get("sens") == "vente"]
    # (a) un initié qui a donné le signal vend des actions de cette compagnie (vente déposée depuis le jour d'achat)
    if initie_signal and any(v["depot"] >= entree and initie_signal & _ciks(v) for v in ventes):
        return True
    # (b) pour chaque jour D où une vente a été déposée depuis le jour d'achat : au moins 2 initiés différents ont déposé
    # des ventes non routinières, hors plan 10b5-1, du jour D - 30 jours civils au jour D compris
    non_routinieres = [x for x in ventes if x.get("routinier") is False and x.get("plan_10b5_1") is not True]
    dates_nr = [x["depot"] for x in non_routinieres]
    for jour_vente in sorted({v["depot"] for v in ventes if v["depot"] >= entree}):
        debut = (date.fromisoformat(jour_vente) - timedelta(days=FENETRE_VENTES)).isoformat()
        qui = set()
        for x in non_routinieres[bisect_left(dates_nr, debut):bisect_right(dates_nr, jour_vente)]:
            qui |= _ciks(x)
        if len(qui) >= 2:
            return True
    return False
