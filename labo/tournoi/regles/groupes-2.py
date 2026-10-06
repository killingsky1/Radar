"""groupes-2 — Le PDG et le directeur financier achètent tous les deux en 10 jours, garder 3 mois.

Programmé tel qu'écrit dans labo/tournoi/regles_preenregistrees.json (piste « groupes »).
Filtre (formulaire 4, achat en bourse) : (1) le titre du déposant contient « CEO » ou « Chief Executive » (et pas
« CFO »), et un autre initié (cik différent) dont le titre contient « CFO » ou « Chief Financial » a déposé un achat sur
la même action ; ou l'inverse (sans tenir compte des majuscules) ; (2) jour_premier des deux achats à 10 jours civils ou
moins l'un de l'autre, l'autre dépôt déjà fait à la date de décision ; (3) chacun des deux achats >= 25 000 $ ;
(4) aucun des deux n'est routinier ; (5) plan_10b5_1 = non ou vide pour les deux ; (6) valeur_m >= 100 M$ ; (7) pas
d'autre signal groupes-2 sur ce symbole dans les 90 jours civils avant.
Entrée : clôture SEC du 1er jour de bourse après le dépôt du 2e des deux formulaires, sinon la 1re des 5 jours de bourse
suivants. Sortie : 63e jour de bourse après l'achat. 10 places de 10 % ; le même jour, la plus grosse somme achetée par
les deux d'abord ; argent qui attend dans SPY.
"""
from datetime import date, timedelta

ID = "groupes-2"

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] Seulement les formulaires d'achat (sens = achat : code P, titres non dérivés), pour les deux achats. « D'actions "
    "ordinaires » : le champ titres n'est pas filtré (le texte ne donne pas de liste de titres).",
    "(1) Titres, sans tenir compte des majuscules, dans le champ titre de chaque déclarant : PDG = contient « ceo » ou "
    "« chief executive » ET ne contient pas « cfo » ; directeur financier = contient « cfo » ou « chief financial » (le "
    "texte n'exclut « CFO » que du côté PDG). Simple recherche de texte : « Co-CEO » compte ; « Principal Executive "
    "Officer » ou « Principal Financial Officer » ne comptent pas (comme le dit le texte).",
    "(1) L'autre achat = un AUTRE formulaire 4 d'achat de la même compagnie (cik de l'émetteur, avec ou sans symbole "
    "lisible), avec un déclarant de cik différent ; un seul formulaire qui aurait les deux déclarants ne suffit pas (le "
    "texte parle de deux formulaires 4). Le dépôt actuel peut être celui du PDG ou celui du directeur financier (« ou "
    "l'inverse »). Plusieurs déclarants : il suffit d'un déclarant PDG dans un formulaire et d'un déclarant directeur "
    "financier (autre cik) dans l'autre.",
    "(2) « Déjà fait à la date de décision » : l'autre formulaire est déposé au plus tard le jour du dépôt actuel (le "
    "même jour compris). Le dépôt actuel est donc le 2e des deux, et l'achat se fait au 1er jour de bourse après lui.",
    "(2) Écart de 10 jours civils ou moins entre les jour_premier des deux formulaires, dans un sens ou dans l'autre ; "
    "jour_premier absent : pas de paire.",
    "(3) à (5), pour les deux formulaires : montant >= 25 000 $ (absent = écarté) ; champ routinier faux (vrai si un des "
    "déclarants est routinier ; un initié sans historique y est déjà non routinier) ; plan_10b5_1 différent de vrai "
    "(faux et vide passent, quelle que soit la date).",
    "(6) valeur_m >= 100 M$ : celle du dépôt actuel (le 2e, à la date de décision) ; absente = écarté.",
    "(7) Un « signal » = un dépôt qui remplit (1) à (6) sans autre signal sur le même symbole déposé du jour J-90 au "
    "dépôt actuel ; calculé de proche en proche depuis le début des données, parmi les achats qui ont le même symbole, "
    "TOUTES compagnies (cik) : « sur ce symbole ». Deux dépôts le même jour : l'ordre de lecture du banc (date, puis "
    "numéro) décide, seul le premier est un signal. Un signal compte même s'il n'est pas acheté (places pleines, pas de "
    "prix, dépôt du contexte d'avant la période).",
    "CONCILIATION avec le vérificateur (6 octobre 2026, selon le texte ; même choix dans les deux fichiers) : (7) « pas "
    "d'autre signal groupes-2 SUR CE SYMBOLE » = même symbole, quelle que soit la compagnie (cik) ; cette programmation "
    "se limitait aux achats de la même compagnie et est corrigée (cas rare : deux cik avec le même symbole, ex. "
    "réorganisation en société de portefeuille). Le reste était déjà identique (jeu ciblé : paires, titres, limites).",
    "Priorité : somme des montants des deux formulaires de la paire ; si le dépôt actuel forme plusieurs paires valides, "
    "la plus grosse somme. Le banc classe ainsi tous les signaux achetables ce jour-là (ceux du jour et ceux qui "
    "attendent encore un prix).",
    "Entrée (banc) : clôture SEC du 1er jour de bourse après le dépôt (JOURS_ENTREE = 1) ; sans prix ce jour-là, le banc "
    "réessaie les 5 jours de bourse suivants (TOLERANCE_ENTREE = 5), sinon pas d'achat.",
    "Sortie (banc) : clôture du 63e jour de bourse après le jour d'achat (DUREE = 63) ; sans prix ce jour-là, 1re clôture "
    "des 10 jours de bourse suivants, sinon la dernière clôture connue (TOLERANCE_SORTIE = 10, défaut du banc : le texte "
    "ne dit pas après combien de jours la compagnie « n'a plus de prix »).",
    "Taille (banc) : MAX_POSITIONS = 10, chaque achat = valeur du portefeuille ÷ 10 (frais compris) ; places pleines : "
    "signal ignoré ; une position de moins de 50 $ n'est pas achetée (MONTANT_MIN du banc, laissé par défaut).",
    "Une seule position par compagnie : le banc l'applique par symbole (garder ne voit pas le portefeuille).",
    "Argent qui attend : SPY, 10 $ par transaction SPY. Le banc ajoute aussi, pour toutes les règles, le demi-écart "
    "achat-vente selon la valeur en bourse.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 63
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"

_ECART_JOURS = 10           # jours civils entre les jour_premier
_MIN_MONTANT = 25_000       # $ par formulaire
_VALEUR_MIN_M = 100         # M$
_SANS_NOUVEAU_SIGNAL = 90   # jours civils

# Caches de calculs (permis) : chaque valeur ne dépend que des dépôts faits au plus tard le jour du dépôt concerné.
_paire_de = {}   # id → plus grosse somme d'une paire valide où ce dépôt est le 2e (None : aucune paire)
_signal_de = {}  # id → signal groupes-2 ? (conditions 1 à 7)


def _jours_avant(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _titre(i):
    return (i.get("titre") or "").lower()


def _pdg(t):
    return ("ceo" in t or "chief executive" in t) and "cfo" not in t


def _dfo(t):
    return "cfo" in t or "chief financial" in t


def _un_titre_utile(x):
    return any(_pdg(_titre(i)) or _dfo(_titre(i)) for i in x.get("inities") or [])


def _pdg_et_dfo(x, y):
    """(1) Un déclarant de x et un déclarant de y, de cik différents : l'un PDG et l'autre directeur financier."""
    for a in x.get("inities") or []:
        for b in y.get("inities") or []:
            if a.get("cik") != b.get("cik") and ((_pdg(_titre(a)) and _dfo(_titre(b)))
                                                  or (_dfo(_titre(a)) and _pdg(_titre(b)))):
                return True
    return False


def _achat_valable(x):
    """(3), (4), (5) pour un des deux formulaires (et un jour_premier pour mesurer l'écart)."""
    return (x.get("sens") == "achat" and (x.get("montant") or 0) >= _MIN_MONTANT and x.get("routinier") is False
            and x.get("plan_10b5_1") is not True and bool(x.get("jour_premier")))


def _filtre_du_formulaire(x):
    """Ce qui ne regarde que le dépôt actuel : achat valable, (6), et un titre de PDG ou de directeur financier."""
    return (_achat_valable(x) and x.get("valeur_m") is not None and x["valeur_m"] >= _VALEUR_MIN_M
            and _un_titre_utile(x))


def _paire(x, evs):
    """Plus grosse somme des montants d'une paire valide où x est le 2e dépôt, sinon None. `evs` : dépôts de la
    compagnie triés (date, numéro), au moins jusqu'au jour du dépôt de x."""
    if x["id"] in _paire_de:
        return _paire_de[x["id"]]
    meilleure = None
    if _filtre_du_formulaire(x):
        jx = date.fromisoformat(x["jour_premier"])
        for y in evs:
            if y["depot"] > x["depot"]:  # l'autre dépôt doit être déjà fait (le même jour compris)
                break
            if y["id"] == x["id"] or not _achat_valable(y):
                continue
            if abs((date.fromisoformat(y["jour_premier"]) - jx).days) > _ECART_JOURS:
                continue
            if _pdg_et_dfo(x, y):
                s = x["montant"] + y["montant"]
                meilleure = s if meilleure is None else max(meilleure, s)
    _paire_de[x["id"]] = meilleure
    return meilleure


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
    par_cik = {}  # dépôts de chaque compagnie (triés (date de dépôt, numéro), jusqu'au jour de décision), pour les paires
    dernier = None  # date de dépôt du dernier signal
    for x in _achats_du_symbole(e["symbole"], ctx):
        if (x["depot"], x["id"]) > cle_e:
            break
        s = _signal_de.get(x["id"])
        if s is None:
            if x["cik"] not in par_cik:
                par_cik[x["cik"]] = ctx.evenements_avant(x["cik"], "0000-00-00")
            s = _paire(x, par_cik[x["cik"]]) is not None and (
                dernier is None or dernier < _jours_avant(x["depot"], _SANS_NOUVEAU_SIGNAL))
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
    """La somme achetée par les deux (la plus grosse paire valide)."""
    return _paire(e, ctx.evenements_avant(e["cik"], "0000-00-00")) or 0.0
