"""groupes-4 (programmation du VÉRIFICATEUR) : 13D et achat d'un dirigeant ou administrateur sur la même compagnie à 90
jours ou moins d'écart, garder 6 mois.

Programmée à partir du texte pré-enregistré seulement (regles_preenregistrees.json), sans voir celle du testeur.
"""
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

ID = "groupes-4"

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] (B) achat : sens = achat ; au moins un déclarant du formulaire avec le rôle administrateur ou dirigeant ; montant ≥ "
    "25 000 $ (vide : non) ; champ routinier du formulaire faux (vide = non routinier) ; plan_10b5_1 false ou vide. "
    "« Actions ordinaires » : le champ titres n'est pas filtré.",
    "(A) 13D initial = forme « 13D » du jeu (SC 13D ou SCHEDULE 13D, sans /A) ; le jeu distingue initial et amendement, "
    "donc pas de solution de repli. Les 13G sont ignorés. Écart entre les deux dates de dépôt : 90 jours civils ou moins, "
    "dans un sens ou dans l'autre.",
    "Le signal est le jour de dépôt du plus récent des deux (un seul signal par jour et par compagnie). Cas 1 (le 13D "
    "d'abord, ou le même jour) : un achat (B) déposé ce jour-là et un 13D initial du jour moins 90 jours au jour même ; le "
    "signal est porté par le PREMIER formulaire d'achat (B) avec symbole de ce jour-là (dans l'ordre du banc).",
    "LIMITE DU BANC, cas 2 (l'achat d'abord, puis le 13D) : un 13D initial ce jour-là et un achat (B) déposé du jour "
    "moins 90 jours au jour même ; le banc n'achète qu'à la suite d'un formulaire 4 : le signal est porté par le PREMIER "
    "formulaire 4 (achat ou vente, avec symbole) de la compagnie déposé le même jour que le 13D. Sans formulaire 4 ce "
    "jour-là, pas d'achat possible (écart avec le texte), mais le signal compte quand même pour la règle des 365 jours.",
    "Valeur en bourse : la plus récente valeur_m non vide (ordre du banc) des formulaires 4 de la compagnie déposés du "
    "jour du signal moins 30 jours au jour même, comme groupes-3 le permet ; à défaut, « calculée comme dans groupes-3 » "
    "(le texte le demande) : actions en circulation XBRL du dernier formulaire 4 (avec symbole) qui en a (fait déjà "
    "déposé) × dernière clôture SEC connue au plus tard le jour du signal. La condition « fin de période d'au moins 45 "
    "jours » ne peut pas s'appliquer : le jeu ne donne pas la fin de période des actions XBRL, seulement leur date de "
    "dépôt (un fait déjà déposé ne vient pas du futur). Aucune valeur : pas un signal. ≥ 100 M$.",
    "365 jours : pas d'autre signal sur la même compagnie (même cik de l'émetteur) dont le jour est à 365 jours civils ou "
    "moins avant. Un signal = tout jour qui remplit les conditions du texte (cas 1 ou 2), acheté ou non (places pleines, "
    "pas de prix, sans porteur, période de contexte). Avant la période de contexte (1 an), aucun formulaire 4 n'est connu.",
    "Priorité (trop de signaux le même jour) : le plus gros montant parmi les achats (B) de TOUTES les paires du jour du "
    "signal : cas 1 : les achats (B) déposés ce jour-là ; cas 2 : les achats (B) déposés du jour du 13D moins 90 jours "
    "au jour même (les deux si les deux cas tombent le même jour). Le banc applique cet ordre à tous les signaux qui "
    "attendent un achat ce jour-là.",
    "Le jeu ne dit pas qui dépose le 13D : un initié qui dépose lui-même le 13D crée un faux double signal (risque connu "
    "du texte, pas corrigé).",
    "Entrée : JOURS_ENTREE = 1 (après le jour du signal) ; TOLERANCE_ENTREE = 5 (pas de prix : 1re clôture des 5 jours de "
    "bourse suivants, sinon pas d'achat).",
    "Sortie : DUREE = 126 jours de bourse après l'achat. Le texte ne dit pas combien de temps chercher un prix de vente : "
    "comportement du banc (TOLERANCE_SORTIE = 10) : 1re clôture des 10 jours de bourse suivants, sinon la dernière "
    "clôture connue (compagnie disparue).",
    "Taille (comportement du banc) : 10 places ; montant = valeur du portefeuille ÷ 10, frais de 10 $ pris dedans ; une "
    "position de moins de 50 $ n'est pas achetée (MONTANT_MIN).",
    "Argent en attente dans SPY (LIQUIDE_JOURS = 0), 10 $ par transaction SPY : comportement du banc.",
    "Une seule position par compagnie : le banc le fait par symbole ; un signal sur un symbole déjà en portefeuille est "
    "ignoré.",
    "Frais et calculs du banc que le texte ne précise pas : demi-écart achat-vente selon la valeur en bourse (en plus des 10 $ par "
    "transaction), à l'achat et à la vente ; rendement enchaîné si le CUSIP change pendant la détention.",
    "CONCILIATION avec le testeur (6 octobre 2026, selon le texte ; mêmes choix dans les deux fichiers) : (a) porteur : "
    "quand un achat (B) est déposé le jour du signal, c'est lui qui porte le signal (le formulaire 4 de la paire est le "
    "plus récent des deux) ; le testeur, qui prenait le 1er formulaire 4 du jour (même une vente), est corrigé. "
    "(b) valeur en bourse : le texte dit « valeur_m (ou, À DÉFAUT, la valeur en bourse calculée comme dans groupes-3) » : "
    "sans valeur_m dans les 30 jours, la valeur est calculée (actions XBRL × dernière clôture SEC) au lieu de manquer ; "
    "corrigé ici (avant : pas de signal), et la valeur_m prise est la plus récente des 30 jours (avant : celle du "
    "porteur d'abord ; même valeur sauf pour deux catégories d'actions déposées le même jour). (c) priorité : « le plus "
    "gros montant d'achat d'initié » = le plus gros des achats (B) de toutes les paires du jour ; corrigé ici (avant : "
    "le montant du porteur dans le cas 1).",
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
MIN_MONTANT = 25_000  # $
ECART_MAX = 90  # jours civils entre le 13D et l'achat
MIN_VALEUR_M = 100  # M$
VALEUR_M_JOURS = 30  # valeur_m d'un formulaire 4 des 30 derniers jours (méthode de groupes-3)
BLOCAGE = 365  # jours civils sans autre signal

# Cache de CALCULS seulement : le résultat d'un jour ne dépend que des dépôts faits au plus tard ce jour-là
_memo_jour = {}  # (cik, jour) → None, ou (id du porteur ou None, priorité)
_memo_donnees = {}  # (cik, jour de la décision) → formulaires et 13D de la compagnie connus ce jour-là


def _moins(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _jours_entre(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _achat_b(x):
    m = x.get("montant")
    return (x.get("sens") == "achat"
            and any(r in ROLES for i in (x.get("inities") or []) for r in (i.get("roles") or []))
            and m is not None and m >= MIN_MONTANT and not x.get("routinier") and x.get("plan_10b5_1") is not True)


def _candidat(cik, jour, evs, depots, treize, ctx):
    """Le jour `jour` est-il un signal du texte (sans la règle des 365 jours) ? evs : formulaires 4 de la compagnie dans
    l'ordre (dépôt, numéro), depots : leurs dates, treize : dates des 13D initiaux (triées). N'utilise que ce qui était
    déposé au plus tard `jour`. → None, ou (id du porteur, ou None s'il n'y en a pas, priorité)."""
    cle = (cik, jour)
    if cle in _memo_jour:
        return _memo_jour[cle]
    debut = _moins(jour, ECART_MAX)
    du_jour = evs[bisect_left(depots, jour):bisect_right(depots, jour)]
    fenetre = evs[bisect_left(depots, debut):bisect_right(depots, jour)]
    achats_jour = [x for x in du_jour if _achat_b(x)]
    achats_fenetre = [x for x in fenetre if _achat_b(x)]
    t_fenetre = treize[bisect_left(treize, debut):bisect_right(treize, jour)]
    cas1 = bool(achats_jour) and bool(t_fenetre)
    cas2 = jour in t_fenetre and bool(achats_fenetre)
    r = None
    if cas1 or cas2:
        b_porteurs = [x for x in achats_jour if x.get("symbole")] if cas1 else []
        porteur = b_porteurs[0] if b_porteurs else next((x for x in du_jour if x.get("symbole")), None)
        v = None  # la plus récente non vide des 30 derniers jours (jour compris)
        for x in evs[bisect_left(depots, _moins(jour, VALEUR_M_JOURS)):bisect_right(depots, jour)]:
            if x.get("valeur_m") is not None:
                v = x["valeur_m"]
        if v is None:  # à défaut, comme groupes-3 : actions XBRL (dernier formulaire 4 qui en a) × dernière clôture SEC
            a = next((x for x in reversed(evs[:bisect_right(depots, jour)])
                      if x.get("actions_circulation") and x.get("symbole")), None)
            c = ctx.cloture(a["symbole"], jour, tolerance_jours=10 ** 6) if a else None
            v = a["actions_circulation"] * c[1] / 1e6 if c else None
        if v is not None and v >= MIN_VALEUR_M:
            prio = max(x["montant"] for x in (achats_fenetre if cas2 else achats_jour))  # toutes les paires du jour
            r = (porteur["id"] if porteur else None, prio)
    _memo_jour[cle] = r
    return r


def _donnees(cik, ctx):
    """Formulaires 4 de la compagnie (ordre (dépôt, numéro)), leurs dates, dates des 13D initiaux, jours d'achats (B) :
    tout ce qui est déposé au plus tard le jour de la décision (gardé en mémoire pour ce jour-là seulement)."""
    cle = (cik, ctx.jour)
    if cle not in _memo_donnees:
        if len(_memo_donnees) > 64:
            _memo_donnees.clear()
        evs = ctx.evenements_avant(cik, "0000-00-00")
        treize = sorted({j for j, f in ctx.depots_13(cik, "0000-00-00") if f == "13D"})
        jours_b = sorted({x["depot"] for x in evs if _achat_b(x)})
        _memo_donnees[cle] = (evs, [x["depot"] for x in evs], treize, jours_b)
    return _memo_donnees[cle]


def _est_jour_signal(cik, jour, evs, depots, treize, jours_b, ctx):
    """Tous les jours candidats de la compagnie jusqu'à `jour`, dans l'ordre : un signal s'il n'y a pas d'autre signal
    à 365 jours ou moins avant."""
    jours = sorted(set(jours_b[:bisect_right(jours_b, jour)]) | set(treize[:bisect_right(treize, jour)]))
    dernier = None
    for j in jours:
        if _candidat(cik, j, evs, depots, treize, ctx) is None:
            continue
        if dernier is None or _jours_entre(dernier, j) > BLOCAGE:
            dernier = j
    return dernier == jour


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not e.get("symbole"):
        return False
    jour, cik = e["depot"], e["cik"]
    t90 = [j for j, f in ctx.depots_13(cik, _moins(jour, ECART_MAX)) if f == "13D" and j <= jour]
    if not t90:
        return False  # aucun 13D initial dans les 90 jours : ni cas 1 ni cas 2 ce jour-là
    if not _achat_b(e) and jour not in t90 and not any(
            x["cik"] == cik and x["depot"] == jour and not x.get("symbole") and _achat_b(x)
            for x in ctx.evenements_marche(jour)):
        return False  # test rapide : ce formulaire ne peut pas porter le signal du jour (voir _candidat)
    evs, depots, treize, jours_b = _donnees(cik, ctx)
    c = _candidat(cik, jour, evs, depots, treize, ctx)
    if c is None or c[0] != e["id"]:
        return False
    # « D'actions ordinaires » : vérifié si le formulaire gardé est un achat (porteur du cas 2 : parfois une vente)
    return (_est_jour_signal(cik, jour, evs, depots, treize, jours_b, ctx)
            and (e.get("sens") != "achat" or _actions_ordinaires(e)))


def priorite(e, ctx):
    evs, depots, treize, _ = _donnees(e["cik"], ctx)
    c = _candidat(e["cik"], e["depot"], evs, depots, treize, ctx)
    return c[1] if c else 0.0
