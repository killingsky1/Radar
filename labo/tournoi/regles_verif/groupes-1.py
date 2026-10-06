"""groupes-1 (programmation du VÉRIFICATEUR) : groupe de 3 initiés ou plus qui achètent en 30 jours, garder 6 mois.

Programmée à partir du texte pré-enregistré seulement (regles_preenregistrees.json), sans voir celle du testeur.
"""
from datetime import date, timedelta

ID = "groupes-1"

CHOIX = [
    "Fenêtre du groupe : les formulaires 4 d'achat de la compagnie DÉPOSÉS du jour du dépôt moins 30 jours civils "
    "jusqu'au jour du dépôt compris, comme le champ groupe_30j. Ils sont tous déjà déposés le soir du dépôt (ceux du "
    "même jour aussi : le banc les montre).",
    "Nombre d'initiés : le champ groupe_30j compte aussi les actionnaires de 10 % et « autre » ; il est donc recalculé : "
    "cik différents des déclarants qui ont le rôle administrateur ou dirigeant dans ces formulaires d'achat. Le déposant "
    "actuel est compté.",
    "« Cette action » = la même compagnie (même cik de l'émetteur), comme le champ groupe_30j.",
    "Somme d'au moins 100 000 $ : les montants des formulaires d'achat de la fenêtre qui ont au moins un déclarant "
    "administrateur ou dirigeant (un formulaire compte une seule fois, même avec plusieurs déclarants ; montant vide = 0).",
    "Condition (1), plusieurs déclarants sur le formulaire : il suffit qu'un déclarant ait le rôle administrateur ou "
    "dirigeant.",
    "Condition (4) : le champ routinier du formulaire (vrai si un de ses déclarants est routinier) doit être faux ; vide = "
    "non routinier.",
    "Condition (5) : plan_10b5_1 false ou vide (null) accepté ; true refusé.",
    "Condition (6) : valeur_m vide (inconnue) = pas gardé.",
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat en bourse (code P) d'actions ordinaires » : tout événement avec sens = achat ; le champ titres n'est pas "
    "filtré.",
    "Condition (7) : un « signal » = un dépôt qui remplit toutes les conditions (la 7 comprise), acheté ou non (places "
    "pleines, pas de prix, ou dépôt de la période de contexte, jamais acheté). « Sur ce symbole » = même symbole, toutes "
    "compagnies. « Dans les 90 jours civils avant » = déposé du jour moins 90 jours jusqu'au jour même ; le même jour, un "
    "dépôt lu avant par le banc (numéro plus petit) compte comme « avant » : seul le premier dépôt qui fait franchir le "
    "seuil est pris. Avant la période de contexte (1 an), aucun dépôt n'est connu.",
    "Priorité (trop de signaux le même jour) : la plus grosse somme achetée par le groupe (celle de la condition 3). Le "
    "banc applique cet ordre à tous les signaux qui attendent un achat ce jour-là (nouveaux et ceux qui réessaient faute "
    "de prix).",
    "Entrée : JOURS_ENTREE = 1 ; TOLERANCE_ENTREE = 5 (pas de prix le jour prévu : 1re clôture des 5 jours de bourse "
    "suivants, sinon pas d'achat).",
    "Sortie : DUREE = 126 jours de bourse après l'achat. Le texte ne dit pas combien de temps chercher un prix de vente : "
    "comportement du banc (TOLERANCE_SORTIE = 10) : 1re clôture des 10 jours de bourse suivants, sinon la dernière "
    "clôture connue (« compagnie disparue »).",
    "Taille (comportement du banc) : 10 places ; montant = valeur du portefeuille ÷ 10, frais de 10 $ pris dedans ; une "
    "position de moins de 50 $ n'est pas achetée (MONTANT_MIN).",
    "Argent en attente dans SPY, produit d'une vente remis dans SPY le jour même (LIQUIDE_JOURS = 0), 10 $ par "
    "transaction SPY : comportement du banc.",
    "Une seule position par compagnie : le banc le fait par symbole ; un signal sur un symbole déjà en portefeuille est "
    "ignoré (pas de prolongation).",
    "Frais et calculs du banc que le texte ne précise pas : demi-écart achat-vente selon la valeur en bourse (en plus des 10 $ par "
    "transaction), à l'achat et à la vente ; rendement enchaîné si le CUSIP change pendant la détention.",
    "CONCILIATION avec le testeur (6 octobre 2026, selon le texte ; même choix dans les deux fichiers) : (7) « aucun "
    "autre signal groupes-1 SUR CE SYMBOLE » = même symbole, quelle que soit la compagnie (cik), comme ici ; le "
    "testeur, qui se limitait aux achats de la même compagnie, est corrigé. Le groupe des conditions (2) et (3) reste "
    "compté par compagnie (cik). Aucun changement dans cette programmation.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

# Réglages du banc (texte : 10 positions de 10 %, entrée au 1er jour de bourse + 5 jours, 126 jours de bourse, SPY)
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

# Seuils du texte
ROLES = ("administrateur", "dirigeant")
FENETRE_GROUPE = 30  # jours civils
MIN_INITIES = 3
MIN_SOMME = 100_000  # $
MIN_VALEUR_M = 100  # M$
FENETRE_SIGNAL = 90  # jours civils

# Caches de CALCULS seulement : chaque valeur ne dépend que des dépôts faits au plus tard le jour du formulaire concerné
# (même résultat sans cache, juste plus lent).
_memo_conditions = {}  # id → (conditions 1 à 6 remplies ?, somme du groupe)
_memo_precedents = {}  # id → formulaires d'avant (même symbole, 90 jours) qui remplissent les conditions 1 à 6
_memo_signal = {}  # id → signal groupes-1 (conditions 1 à 7) ?
_memo_index = {}  # jour → {symbole: achats déposés du jour − 90 au jour}


def _moins(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _dir_ou_adm(i):
    return any(r in ROLES for r in (i.get("roles") or []))


def _conditions(x, ctx):
    """Conditions (1) à (6) pour le formulaire x, avec seulement les dépôts faits au plus tard le jour de x."""
    k = x["id"]
    if k in _memo_conditions:
        return _memo_conditions[k]
    r = (False, 0.0)
    v = x.get("valeur_m")
    if (x.get("sens") == "achat"
            and any(_dir_ou_adm(i) for i in x.get("inities") or [])  # (1)
            and not x.get("routinier")  # (4)
            and x.get("plan_10b5_1") is not True  # (5)
            and v is not None and v >= MIN_VALEUR_M):  # (6)
        jour = x["depot"]
        membres, somme = set(), 0.0
        for y in ctx.evenements_avant(x["cik"], _moins(jour, FENETRE_GROUPE)):
            if y["depot"] > jour or y.get("sens") != "achat":
                continue
            qui = {i["cik"] for i in (y.get("inities") or []) if _dir_ou_adm(i)}
            if qui:
                membres |= qui
                somme += y.get("montant") or 0.0
        r = (len(membres) >= MIN_INITIES and somme >= MIN_SOMME, somme)  # (2) et (3)
    _memo_conditions[k] = r
    return r


def _index(jour, ctx):
    """Achats avec symbole déposés du jour − 90 jours au jour, par symbole (toutes compagnies)."""
    if jour not in _memo_index:
        if len(_memo_index) > 8:
            _memo_index.clear()
        idx = {}
        for z in ctx.evenements_marche(_moins(jour, FENETRE_SIGNAL)):
            if z["depot"] <= jour and z.get("sens") == "achat" and z.get("symbole"):
                idx.setdefault(z["symbole"], []).append(z)
        _memo_index[jour] = idx
    return _memo_index[jour]


def _precedents(y, ctx):
    """Les formulaires du même symbole déposés dans les 90 jours avant y (même jour : lus avant y par le banc) qui
    remplissent les conditions (1) à (6)."""
    if y["id"] not in _memo_precedents:
        cle = (y["depot"], y["id"])
        _memo_precedents[y["id"]] = [z for z in _index(y["depot"], ctx).get(y["symbole"], [])
                                     if (z["depot"], z["id"]) < cle and _conditions(z, ctx)[0]]
    return _memo_precedents[y["id"]]


def _est_signal(x, ctx):
    """Conditions (1) à (7). Calcul sans récursion : les signaux d'avant sont trouvés d'abord."""
    if x["id"] in _memo_signal:
        return _memo_signal[x["id"]]
    if not x.get("symbole") or not _conditions(x, ctx)[0]:
        _memo_signal[x["id"]] = False
        return False
    pile = [x]
    while pile:
        y = pile[-1]
        if y["id"] in _memo_signal:
            pile.pop()
            continue
        avant = _precedents(y, ctx)
        manquants = [z for z in avant if z["id"] not in _memo_signal]
        if manquants:
            pile.extend(manquants)
            continue
        _memo_signal[y["id"]] = not any(_memo_signal[z["id"]] for z in avant)  # (7)
        pile.pop()
    return _memo_signal[x["id"]]


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    return _est_signal(e, ctx) and _actions_ordinaires(e)


def priorite(e, ctx):
    return _conditions(e, ctx)[1]
