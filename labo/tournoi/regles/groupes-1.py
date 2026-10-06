"""groupes-1 — Groupe de 3 initiés ou plus qui achètent en 30 jours, garder 6 mois.

Programmé tel qu'écrit dans labo/tournoi/regles_preenregistrees.json (piste « groupes »).
Filtre (formulaire 4, achat en bourse) : (1) le déposant est dirigeant ou administrateur ; (2) au moins 3 initiés
DIFFÉRENTS, dirigeants ou administrateurs, ont acheté la même compagnie dans les 30 jours civils qui finissent au dépôt
(le déposant compris) ; (3) la somme de leurs achats dans ces 30 jours est d'au moins 100 000 $ (dépôts déjà faits
seulement) ; (4) routinier = non ; (5) plan_10b5_1 = non ou vide ; (6) valeur_m >= 100 M$ ; (7) aucun autre signal
groupes-1 sur ce symbole dans les 90 jours civils avant (seul le 1er dépôt qui fait franchir le seuil est pris).
Entrée : clôture SEC du 1er jour de bourse après le dépôt, sinon la 1re des 5 jours de bourse suivants. Sortie : 126e jour
de bourse après l'achat. 10 places de 10 % ; le même jour, la plus grosse somme du groupe d'abord ; argent qui attend
dans SPY.
"""
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

ID = "groupes-1"

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] Seulement les formulaires d'achat (sens = achat : code P, titres non dérivés). « D'actions ordinaires » : le champ "
    "titres n'est pas filtré (le texte ne donne pas de liste de titres).",
    "(1) Rôle : au moins un des déclarants du formulaire a le rôle « dirigeant » ou « administrateur ».",
    "(2) « Cette action » = la même compagnie (cik de l'émetteur), comme le champ groupe_30j du jeu ; les formulaires "
    "sans symbole lisible de cette compagnie comptent aussi. Fenêtre de 30 jours civils = achats DÉPOSÉS du jour J-30 "
    "au jour J compris (J = date du dépôt), comme groupe_30j : on compte selon la date de dépôt, donc seulement les "
    "dépôts déjà faits à la date de décision (ceux du jour J compris).",
    "(2) Le groupe est recompté au lieu de prendre groupe_30j, car groupe_30j compte aussi les actionnaires de 10 % et "
    "les « autres » : seuls les déclarants qui ont le rôle dirigeant ou administrateur dans un formulaire d'achat de la "
    "fenêtre comptent, chaque cik une fois. Le déposant actuel est compté (son dépôt est dans la fenêtre) : le cas « le "
    "champ groupe exclut le déposant » du texte ne s'applique pas.",
    "(3) Somme = montants des formulaires d'achat de la fenêtre qui ont au moins un déclarant dirigeant ou "
    "administrateur ; un formulaire compte une fois, même avec plusieurs déclarants ; montant absent = 0.",
    "(4) routinier = non : le champ routinier du formulaire doit être faux (il est vrai si un des déclarants est "
    "routinier ; un initié sans 3 ans d'historique y est déjà non routinier).",
    "(5) plan_10b5_1 : vrai est exclu ; faux et vide (case pas remplie) passent, quelle que soit la date.",
    "(6) valeur_m absente : événement écarté (la condition ne peut pas être vérifiée).",
    "(7) Un « signal » = un dépôt qui remplit (1) à (6) sans autre signal sur le même symbole déposé du jour J-90 au "
    "dépôt actuel ; calculé de proche en proche depuis le début des données, parmi les achats qui ont le même symbole, "
    "TOUTES compagnies (cik) : « sur ce symbole ». Deux dépôts le même jour : l'ordre de lecture du banc (date, puis "
    "numéro) décide, seul le premier est un signal. Un signal compte même s'il n'est pas acheté (places pleines, pas de "
    "prix, dépôt du contexte d'avant la période).",
    "CONCILIATION avec le vérificateur (6 octobre 2026, selon le texte ; même choix dans les deux fichiers) : (7) « aucun "
    "autre signal groupes-1 SUR CE SYMBOLE » = même symbole, quelle que soit la compagnie (cik) ; cette programmation se "
    "limitait aux achats de la même compagnie et est corrigée (cas rare : deux cik avec le même symbole, ex. "
    "réorganisation en société de portefeuille). Le groupe des conditions (2) et (3) reste compté par compagnie (cik), "
    "dans les deux programmations.",
    "(7) « On ne prend que le premier dépôt qui fait franchir le seuil » est lu comme l'explication de (7), pas comme une "
    "condition de plus : les conditions (2) et (3) sont des niveaux (« au moins »). Si le seuil a été atteint plus tôt "
    "par un dépôt qui n'était pas un signal (ex. routinier, plan 10b5-1 ou valeur_m absente), le 1er dépôt suivant qui "
    "remplit tout devient le signal.",
    "Entrée (banc) : clôture SEC du 1er jour de bourse après le dépôt (JOURS_ENTREE = 1) ; sans prix ce jour-là, le banc "
    "réessaie les 5 jours de bourse suivants (TOLERANCE_ENTREE = 5), sinon pas d'achat.",
    "Sortie (banc) : clôture du 126e jour de bourse après le jour d'achat (DUREE = 126) ; sans prix ce jour-là, 1re "
    "clôture des 10 jours de bourse suivants, sinon la dernière clôture connue (TOLERANCE_SORTIE = 10, défaut du banc : "
    "le texte ne dit pas après combien de jours l'action « n'a plus de prix »). Le banc ne prolonge jamais une position : "
    "un nouveau signal sur un symbole déjà en portefeuille est ignoré.",
    "Taille (banc) : MAX_POSITIONS = 10, chaque achat = valeur du portefeuille ÷ 10 (frais compris) ; places pleines : "
    "signal ignoré ; une position de moins de 50 $ n'est pas achetée (MONTANT_MIN du banc, laissé par défaut).",
    "Priorité : la plus grosse somme du groupe (condition 3) d'abord ; le banc classe ainsi tous les signaux achetables "
    "ce jour-là (ceux du jour et ceux qui attendent encore un prix).",
    "Une seule position par compagnie : le banc l'applique par symbole (garder ne voit pas le portefeuille).",
    "Argent qui attend : SPY, 10 $ par transaction SPY ; le produit d'une vente retourne dans SPY le jour même "
    "(LIQUIDE_JOURS = 0). Le banc ajoute aussi, pour toutes les règles, le demi-écart achat-vente selon la valeur en "
    "bourse.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0

_FENETRE_GROUPE = 30        # jours civils : dépôts de J-30 à J
_MIN_INITIES = 3
_MIN_SOMME = 100_000        # $
_VALEUR_MIN_M = 100         # M$
_SANS_NOUVEAU_SIGNAL = 90   # jours civils

# Caches de calculs (permis) : chaque valeur ne dépend que des dépôts faits au plus tard le jour du dépôt concerné.
_conditions_de = {}  # id → (conditions 1 à 6 vraies ?, somme achetée par le groupe)
_signal_de = {}      # id → signal groupes-1 ? (conditions 1 à 7)


def _jours_avant(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _dirigeants_admins(x):
    """Les cik des déclarants du formulaire qui ont le rôle dirigeant ou administrateur."""
    return {i.get("cik") for i in x.get("inities") or []
            if "dirigeant" in (i.get("roles") or []) or "administrateur" in (i.get("roles") or [])}


def _filtre_du_formulaire(x):
    """Ce qui ne regarde que le formulaire lui-même : achat, (1), (4), (5), (6)."""
    return (x.get("sens") == "achat" and bool(_dirigeants_admins(x)) and x.get("routinier") is False
            and x.get("plan_10b5_1") is not True and x.get("valeur_m") is not None
            and x["valeur_m"] >= _VALEUR_MIN_M)


def _groupe(x, evs, depots):
    """(2) et (3) : (nombre d'initiés dirigeants ou administrateurs distincts, somme de leurs achats) d'après les achats
    de la compagnie DÉPOSÉS de J-30 à J (J = dépôt de x). `evs` : dépôts de la compagnie triés (date, numéro)."""
    i = bisect_left(depots, _jours_avant(x["depot"], _FENETRE_GROUPE))
    j = bisect_right(depots, x["depot"])
    qui, somme = set(), 0.0
    for y in evs[i:j]:
        if y.get("sens") != "achat":
            continue
        d = _dirigeants_admins(y)
        if d:
            qui |= d
            somme += y.get("montant") or 0.0
    return len(qui), somme


def _conditions(x, evs, depots):
    """(conditions 1 à 6 vraies ?, somme du groupe) pour le dépôt x."""
    r = _conditions_de.get(x["id"])
    if r is None:
        if _filtre_du_formulaire(x):
            n, somme = _groupe(x, evs, depots)
            r = (n >= _MIN_INITIES and somme >= _MIN_SOMME, somme)
        else:
            r = (False, 0.0)
        _conditions_de[x["id"]] = r
    return r


_achats_par_symbole = {}  # symbole → achats déjà lus, TOUTES compagnies, dans l'ordre du banc (dépôts déjà vus)
_lu_jusqu_a = []          # le dernier jour déjà lu


def _achats_du_symbole(symbole, ctx):
    """(7) « Sur ce symbole » : les achats de ce symbole, toutes compagnies (cik), déposés au plus tard le jour de ctx,
    dans l'ordre de lecture du banc (lus au fil des jours avec ctx.evenements_marche : rien du futur)."""
    if not _lu_jusqu_a or _lu_jusqu_a[0] < ctx.jour:
        depuis = (date.fromisoformat(_lu_jusqu_a[0]) + timedelta(days=1)).isoformat() if _lu_jusqu_a else "0000-00-00"
        for x in ctx.evenements_marche(depuis):
            if x.get("sens") == "achat" and x.get("symbole"):
                _achats_par_symbole.setdefault(x["symbole"], []).append(x)
        _lu_jusqu_a[:] = [ctx.jour]
    return _achats_par_symbole.get(symbole, [])


def _est_signal(e, ctx):
    """(7), de proche en proche : les achats sur le même symbole (toutes compagnies), dans l'ordre de lecture du banc ;
    un dépôt est un signal s'il remplit (1) à (6) et qu'aucun signal n'a été déposé du jour J-90 jusqu'à lui."""
    if e["id"] in _signal_de:
        return _signal_de[e["id"]]
    cle_e = (e["depot"], e["id"])
    par_cik = {}  # dépôts de chaque compagnie (triés (date de dépôt, numéro), jusqu'au jour de décision) et leurs dates
    dernier = None  # date de dépôt du dernier signal
    for x in _achats_du_symbole(e["symbole"], ctx):
        if (x["depot"], x["id"]) > cle_e:
            break
        s = _signal_de.get(x["id"])
        if s is None:
            if x["cik"] not in par_cik:
                evs = ctx.evenements_avant(x["cik"], "0000-00-00")
                par_cik[x["cik"]] = (evs, [y["depot"] for y in evs])
            ok, _ = _conditions(x, *par_cik[x["cik"]])
            s = ok and (dernier is None or dernier < _jours_avant(x["depot"], _SANS_NOUVEAU_SIGNAL))
            _signal_de[x["id"]] = s
        if s:
            dernier = x["depot"]
    return _signal_de.get(e["id"], False)


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _filtre_du_formulaire(e):
        return False
    return _est_signal(e, ctx) and _actions_ordinaires(e)


def priorite(e, ctx):
    """La somme achetée par le groupe (condition 3)."""
    evs = ctx.evenements_avant(e["cik"], _jours_avant(e["depot"], _FENETRE_GROUPE))
    return _groupe(e, evs, [y["depot"] for y in evs])[1]
