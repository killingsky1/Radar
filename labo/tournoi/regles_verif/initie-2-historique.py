"""initie-2-historique : initié qui a déjà bien acheté (majorité de réussites passées) (programmation du VÉRIFICATEUR).

Texte pré-enregistré (regles_preenregistrees.json) : achat P d'actions ordinaires ; roles contient dirigeant ou
administrateur ; routinier = non ; plan_10b5_1 différent de oui ; montant ≥ 25 000 $ ; valeur_m entre 100 et 2 000 M$.
HISTORIQUE : les achats passés en bourse de cet initié, toutes ses compagnies, déposés au moins 190 jours civils avant
le dépôt actuel ; deux dépôts dans la même compagnie à moins de 30 jours d'écart comptent pour un seul, le premier.
Évaluable : prix SEC d'entrée (1er jour de bourse après son dépôt, ou 1er prix des 5 jours suivants) et prix 126 jours
de bourse plus tard (ou 1er prix des 10 jours suivants). Réussi : rendement > SPY sur les mêmes dates. Condition : au
moins 2 évaluables et STRICTEMENT plus de la moitié réussis. Même jour : plus haut taux, puis plus gros montant.
Changement du 5 octobre (regles_du_jeu.md, 3) : un achat passé ne compte que si sa mesure était finie avant la décision.
Entrée, sortie, taille : comme initie-1 (126 jours de bourse, 5 positions de 20 %, SPY).
"""
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

ID = "initie-2-historique"
IMPOSSIBLE = None  # la petite fuite signalée par le critique est fermée : seuls comptent les achats passés mesurés à temps

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu (code P, titres non dérivés). Le champ « titres » "
    "n'est pas filtré : il n'est pas dans les champs de la règle.",
    "roles contient « dirigeant » ou « administrateur » (un actionnaire de 10 % seul ou « autre » seul est exclu).",
    "Plusieurs déclarants : le formulaire est gardé si UN déclarant est à la fois dirigeant ou administrateur ET a "
    "l'historique demandé ; son taux (le meilleur s'il y en a plusieurs) sert à la priorité.",
    "routinier = non : e['routinier'] faux. plan_10b5_1 différent de oui : true refusé ; false et vide (null) acceptés.",
    "montant ≥ 25 000 $ et 100 ≤ valeur_m ≤ 2 000 (M$), bornes comprises ; montant ou valeur_m absent = refusé.",
    "Historique : ctx.historique_initie(cik du déclarant), lignes de sens « achat » seulement (achats en bourse), toutes "
    "compagnies, déposées au moins 190 jours civils avant le dépôt actuel (dépôt actuel − dépôt passé ≥ 190).",
    "Regroupement : dans une même compagnie (cik), en ordre de dépôt, un dépôt à moins de 30 jours civils du dépôt "
    "d'achat PRÉCÉDENT de cette compagnie ne compte pas (lecture « deux à deux » : une suite de dépôts espacés de moins "
    "de 30 jours compte pour un seul, le premier). Le regroupement se fait avant de savoir s'ils sont évaluables.",
    "Entrée d'un achat passé : clôture SEC du 1er jour de bourse après son dépôt, sinon 1re clôture des 5 jours de bourse "
    "suivants (6 jours en tout), sinon pas évaluable.",
    "Sortie d'un achat passé : 126 jours de bourse après le jour de son prix d'entrée, sinon 1re clôture des 10 jours de "
    "bourse suivants (11 jours en tout), sinon pas évaluable (pas de « dernier prix connu » pour un achat passé : le "
    "texte ne le donne pas).",
    "Mesure finie avant la décision (changement du 5 octobre) : la date du prix de sortie doit être au plus le jour du "
    "dépôt actuel (garder() décide le soir du dépôt : la clôture de ce jour est connue, le banc l'accepte). Si la fenêtre "
    "de sortie n'est pas finie ce jour-là et qu'aucun prix n'est encore trouvé, l'achat passé ne compte pas.",
    "Achat passé sans symbole, ou déposé avant le début du calendrier des prix SEC (juillet 2015 dans le vrai jeu) : pas "
    "évaluable (on ne peut pas savoir quel était son 1er jour de bourse ni son prix).",
    "Rendement d'un achat passé : de la clôture d'entrée à celle de sortie, enchaîné si le CUSIP change (comme le banc : "
    "on ne compare pas deux prix de CUSIP différents). SPY : dernière clôture au plus tard à ces deux mêmes dates. "
    "Réussi si le rendement est STRICTEMENT plus grand que celui de SPY. Sans frais.",
    "Condition : évaluables ≥ 2 et réussis × 2 > évaluables. Taux = réussis ÷ évaluables.",
    "Priorité le même jour : le plus haut taux, puis le plus gros montant. Calcul : taux × 10^15 + montant (plafonné à "
    "999 999 999 $ dans ce calcul, pour que le taux passe toujours avant le montant). Égalité : ordre du banc (dépôt, "
    "numéro).",
    "Entrée : JOURS_ENTREE = 1 ; TOLERANCE_ENTREE = 5 (sans prix, 5 jours de bourse de plus, sinon le signal tombe).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat réel ; TOLERANCE_SORTIE = 10 (puis dernier prix connu).",
    "Taille : MAX_POSITIONS = 5 (20 %) ; ARGENT_QUI_ATTEND = « SPY » ; LIQUIDE_JOURS = 0 ; "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0. Places pleines : signal laissé tomber. Déjà en portefeuille : pas acheté.",
    "Banc, différent du texte : demi-écart achat-vente selon la valeur en bourse, à l'achat et à la vente, en plus des "
    "10 $ ; position = 20 % moins 10 $, plus petite s'il manque d'argent (sous MONTANT_MIN = 50 $, défaut du banc : pas "
    "d'achat) ; la priorité classe aussi les signaux qui attendent encore un prix ; rendement enchaîné si le CUSIP change.",
    "Calculs gardés en mémoire (permis : ne dépendent que du passé) : le résultat final de chaque achat passé, et le "
    "bilan d'un initié à une date de décision.",
    "Comparaison des deux programmations (jeu ciblé : trous d'un mois dans le calendrier et les prix, comme un fichier "
    "d'échecs absent) : un achat passé déposé dans un trou du calendrier se mesure à partir du 1er jour de bourse du "
    "calendrier après son dépôt, comme le banc le fait pour ses propres achats ; il n'est « pas évaluable » faute de "
    "jour de bourse que s'il est déposé avant le début du calendrier. Le testeur ne regardait que les jours de bourse "
    "depuis 7 jours avant le dépôt passé : un dépôt fait plus de 7 jours dans un trou devenait « pas évaluable ». "
    "Testeur corrigé (calendrier entier).",
    "Comparaison (jeu ciblé : des prix à 0) : un prix à 0 ne rend un achat passé « pas évaluable » que s'il sert de base "
    "au rendement (prix d'entrée, ou 1er prix après un changement de CUSIP : division impossible). Un prix de sortie à 0 "
    "donne −100 % (pas réussi) ; un prix à 0 entre l'entrée et la sortie ne compte pas. Le texte ne demande qu'un prix "
    "d'entrée et un prix de sortie, et c'est le calcul du banc. Le vérificateur écartait l'achat passé dès qu'un prix de "
    "la série valait 0 : vérificateur corrigé.",
    "Comparaison (jeu ciblé : 7 achats du même initié le même jour, de 110 à 170 M$, 5 places) : le montant de la "
    "priorité est plafonné à 999 999 999 $ dans les deux. Le vérificateur plafonnait à 100 M$ : ces signaux étaient à "
    "égalité chez lui et classés par montant chez le testeur ; le texte dit « le plus gros montant ». Vérificateur "
    "corrigé.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

JOURS_ENTREE = 1
DUREE = 126
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
TOLERANCE_ENTREE = 5
TOLERANCE_SORTIE = 10
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

DELAI_HISTORIQUE = 190   # jours civils entre un achat passé et le dépôt actuel
REGROUPEMENT = 30        # jours civils : deux dépôts plus proches dans la même compagnie = un seul
JOURS_MESURE = 126       # jours de bourse de la mesure d'un achat passé
FENETRE_ENTREE = 5       # jours de bourse de plus pour trouver le prix d'entrée d'un achat passé
FENETRE_SORTIE = 10      # jours de bourse de plus pour trouver son prix de sortie

_RESULTAT = {}  # (symbole, dépôt passé) → None (jamais évaluable) ou (date du prix de sortie, réussi) : résultat final
_BILAN = {}     # (initié, dépôt actuel, jour de décision) → (évaluables, réussis)


def _base(e, montant_min):
    """La base commune de la piste : achat P, non routinier, hors plan 10b5-1, montant, taille de la compagnie."""
    if e.get("sens") != "achat":
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    m = e.get("montant")
    if m is None or m < montant_min:
        return False
    v = e.get("valeur_m")
    if v is None or v < 100 or v > 2000:
        return False
    return True


def _dirigeant_ou_administrateur(initie):
    roles = initie.get("roles") or []
    return "dirigeant" in roles or "administrateur" in roles


def _rendement(serie):
    """Rendement de la 1re à la dernière clôture [(date, prix, cusip)], enchaîné si le CUSIP change (comme le banc)."""
    r, base = 1.0, serie[0][1]
    for k in range(1, len(serie)):
        if serie[k][2] != serie[k - 1][2]:
            r *= serie[k - 1][1] / base
            base = serie[k][1]
    return r * serie[-1][1] / base - 1


def _evaluer(ctx, cal, symbole, depot):
    """Un achat passé : True (a battu SPY), False (n'a pas battu SPY), None (pas évaluable, ou mesure pas finie au jour
    de la décision). `cal` : les jours de bourse connus jusqu'au jour de la décision."""
    if not symbole or not cal or cal[0] > depot:
        return None
    cle = (symbole, depot)
    if cle in _RESULTAT:
        x = _RESULTAT[cle]
        return None if x is None or x[0] > ctx.jour else x[1]
    i = bisect_right(cal, depot)                      # le 1er jour de bourse APRÈS le dépôt
    fenetre = cal[i:i + 1 + FENETRE_ENTREE]
    if not fenetre:
        return None
    prix = ctx.clotures(symbole, fenetre[0], fenetre[-1])
    if not prix:
        if len(fenetre) == 1 + FENETRE_ENTREE:        # fenêtre finie sans prix : jamais évaluable
            _RESULTAT[cle] = None
        return None
    entree = prix[0]
    k = bisect_left(cal, entree[0]) + JOURS_MESURE    # 126 jours de bourse après le jour d'entrée
    fenetre = cal[k:k + 1 + FENETRE_SORTIE]
    if not fenetre:
        return None                                   # pas encore fini au jour de la décision
    prix = ctx.clotures(symbole, fenetre[0], fenetre[-1])
    if not prix:
        if len(fenetre) == 1 + FENETRE_SORTIE:        # fenêtre finie sans prix : jamais évaluable
            _RESULTAT[cle] = None
        return None                                   # sinon : pas encore fini au jour de la décision
    sortie = prix[0]
    serie = ctx.clotures(symbole, entree[0], sortie[0])
    spy_entree, spy_sortie = ctx.cloture("SPY", entree[0]), ctx.cloture("SPY", sortie[0])
    if not spy_entree or not spy_sortie or spy_entree[1] <= 0 or any(  # un prix de BASE à 0 : division impossible
            p[1] <= 0 for k, p in enumerate(serie) if k == 0 or p[2] != serie[k - 1][2]):
        _RESULTAT[cle] = None
        return None
    reussi = _rendement(serie) > spy_sortie[1] / spy_entree[1] - 1
    _RESULTAT[cle] = (sortie[0], reussi)
    return reussi


def _bilan(ctx, initie_cik, depot_actuel):
    """(évaluables, réussis) des achats passés de l'initié, tels que connus le jour de la décision."""
    cle = (initie_cik, depot_actuel, ctx.jour)
    if cle in _BILAN:
        return _BILAN[cle]
    limite = (date.fromisoformat(depot_actuel) - timedelta(days=DELAI_HISTORIQUE)).isoformat()
    cal = ctx.jours_de_bourse("0000-00-00")
    precedent = {}  # compagnie → date du dépôt d'achat précédent (compté ou non)
    evaluables = reussis = 0
    for r in ctx.historique_initie(initie_cik):       # en ordre de dépôt
        if r[3] != "achat" or r[0] > limite:
            continue
        avant = precedent.get(r[1])
        precedent[r[1]] = r[0]
        if avant is not None and (date.fromisoformat(r[0]) - date.fromisoformat(avant)).days < REGROUPEMENT:
            continue
        res = _evaluer(ctx, cal, r[2], r[0])
        if res is None:
            continue
        evaluables += 1
        reussis += 1 if res else 0
    _BILAN[cle] = (evaluables, reussis)
    return evaluables, reussis


def _taux(e, ctx):
    """Le meilleur taux de réussite parmi les déclarants qui remplissent la condition, sinon None."""
    meilleur = None
    for i in e.get("inities") or []:
        if not _dirigeant_ou_administrateur(i):
            continue
        n, ok = _bilan(ctx, i["cik"], e["depot"])
        if n >= 2 and 2 * ok > n:
            t = ok / n
            if meilleur is None or t > meilleur:
                meilleur = t
    return meilleur


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e, 25_000):
        return False
    return _taux(e, ctx) is not None and _actions_ordinaires(e)


def priorite(e, ctx):
    t = _taux(e, ctx) or 0.0
    return t * 1e15 + min(float(e.get("montant") or 0.0), 999_999_999.0)
