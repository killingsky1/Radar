"""initie-5-combine : PDG ou directeur financier, premier achat depuis 1 an, avec part ajoutée d'au moins 10 % (règle
pré-enregistrée, piste « initie »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- Filtre : achat P d'actions ordinaires. Le titre contient CEO, Chief Executive, Principal Executive, CFO, Chief
  Financial ou Principal Financial (sans tenir compte des majuscules). routinier = non. plan_10b5_1 différent de oui.
  montant ≥ 25 000 $. part_ajoutee ≥ 0,10 (rempli s'il ne détenait rien avant). valeur_m entre 100 et 2 000 M$. Aucun
  achat P ni vente S de cet initié dans cette compagnie pendant les 365 jours civils avant le jour_premier_achat. Pas
  d'action déjà en portefeuille. Le même jour : directeur financier d'abord, puis la plus grande part_ajoutee.
- Entrée : clôture du 1er jour de bourse après le dépôt (ou 1er prix SEC dans les 5 jours de bourse suivants, sinon rien).
- Sortie : clôture du 126e jour de bourse après l'achat (ou 1er prix dans les 10 jours suivants ; dernier prix connu si
  la compagnie disparaît).
- Taille : 20 % du portefeuille, 5 positions au plus, signaux ignorés quand c'est plein, argent qui attend dans SPY.
"""
from datetime import date, timedelta

ID = "initie-5-combine"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu de données (code P, titres non dérivés). Le champ "
    "« titres » n'est pas filtré : il n'est pas dans la liste des champs de la règle.",
    "Titre : on cherche les mots comme des bouts de texte (« contient »), sans tenir compte des majuscules : ceo, "
    "chief executive, principal executive, cfo, chief financial, principal financial (comme initie-1-pdg-dfo). Aucune "
    "autre correction du texte libre (un titre « See Remarks » ne compte pas ; « President » seul non plus).",
    "Le rôle (roles) n'est pas vérifié à part : le filtre écrit ne le demande pas (roles n'est pas dans ses champs).",
    "Plusieurs déclarants sur le formulaire : l'événement est gardé si AU MOINS UN déclarant a un titre PDG ou "
    "directeur financier ET n'a ni acheté ni vendu dans la compagnie pendant les 365 jours (son propre historique). "
    "« Directeur financier » (priorité) : au moins un de ces déclarants a cfo, chief financial ou principal financial "
    "dans son titre (même s'il contient aussi CEO).",
    "Silence de 365 jours : fenêtre du jour_premier − 365 jours civils jusqu'à la veille du jour_premier. On regarde les "
    "DATES DES OPÉRATIONS (pas les dates de dépôt) des lignes « achat » et « vente » de ctx.historique_initie(cik de "
    "l'initié) pour la même compagnie (même cik de compagnie). Un dépôt passé casse le silence si la période de ses "
    "opérations (jour_premier à jour_dernier) touche la fenêtre. Une date d'opération absente est remplacée par la date "
    "de dépôt. Seuls les dépôts faits au plus tard le jour du dépôt actuel sont vus (le banc l'impose).",
    "Le dépôt actuel lui-même ne casse pas le silence (ses achats sont au jour_premier ou après) ; mais une VENTE du même "
    "formulaire datée d'avant le jour_premier le casse (lecture littérale). jour_premier absent : la date de dépôt le "
    "remplace. Aucun historique dans la compagnie = condition remplie.",
    "part_ajoutee = le champ part du jeu de données. Condition : part ≥ 0,10, OU nouvelle_position = vrai (rien détenu "
    "avant : « rempli »). Détenues avant inconnues (part vide et nouvelle_position faux) : refusé.",
    "plan_10b5_1 : refusé seulement si « oui » (true) ; vide (null) accepté. routinier doit valoir false. montant ≥ "
    "25 000 $ (absent = refusé). valeur_m entre 100 et 2 000 M$, bornes comprises (absente = refusée).",
    "Priorité le même jour (fonction priorite, un seul nombre) : directeur financier d'abord (+1 000 000 000), puis la "
    "plus grande part (une nouvelle position = 200 000 000, au-dessus de toute part ; part plafonnée à 100 000 000 "
    "pour garder l'ordre). "
    "Égalité : le banc prend le dépôt le plus ancien, puis le numéro. Le banc trie ensemble les signaux du jour et ceux "
    "qui attendent encore un prix.",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le jour prévu, puis les 5 jours de bourse suivants).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat, TOLERANCE_SORTIE = 10. Banc : sans prix pendant ces "
    "10 jours, il prend la dernière clôture connue même si la compagnie n'a pas disparu.",
    "Banc (diffère du texte) : en plus des 10 $ par transaction (SPY compris), il compte un demi-écart achat-vente selon "
    "la valeur en bourse, à l'achat et à la vente.",
    "Banc (diffère du texte) : la position vaut 20 % de la valeur du portefeuille MOINS les 10 $ de frais ; s'il ne "
    "reste pas assez d'argent, il achète avec ce qui reste ; une position de moins de 50 $ n'est pas achetée "
    "(MONTANT_MIN = 50, réglage par défaut du banc).",
    "Banc (le texte n'en parle pas) : changement de CUSIP pendant la détention = rendement enchaîné ; les ventes du jour "
    "passent avant les achats du jour ; une position encore ouverte à la fin des prix reste ouverte.",
    "Faits par le banc, comme le texte : pas d'achat d'une action déjà en portefeuille ; signal ignoré quand les 5 "
    "places sont prises ; argent qui attend dans SPY (LIQUIDE_JOURS = 0), 10 $ par opération sur SPY.",
    "Comparaison des deux programmations (jeu ciblé, 5 places : le même jour, 7 achats de PDG, parts de 2 à 500 "
    "millions et une nouvelle position ; puis 6 achats de directeurs financiers, 5 parts de 150 à 550 millions et une "
    "nouvelle position) : le testeur donnait 10^8 à une nouvelle position, à égalité avec une part ≥ 10^8 ; le "
    "vérificateur plafonnait la part à 999 999, donc les parts plus grandes étaient à égalité. Le texte : « la plus "
    "grande part_ajoutee », et une nouvelle position (rien avant) compte comme la plus grande (part infinie). Calcul "
    "commun : 10^9 si directeur financier, plus 2 × 10^8 pour une nouvelle position, sinon la part plafonnée à 10^8 "
    "(les deux corrigés). Au-delà de 10^8, deux parts comptent comme égales (ordre du banc).",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

MONTANT_MINIMUM = 25_000
VALEUR_MIN, VALEUR_MAX = 100, 2000
PART_MIN = 0.10
SILENCE_JOURS = 365
MOTS_PDG = ("ceo", "chief executive", "principal executive")
MOTS_DFO = ("cfo", "chief financial", "principal financial")
PART_PLAFOND = 1e8


def _jour(iso, n):
    return (date.fromisoformat(iso) + timedelta(days=n)).isoformat()


def _titre(i):
    return (i.get("titre") or "").lower()


def _pdg_ou_dfo(i):
    t = _titre(i)
    return any(m in t for m in MOTS_PDG + MOTS_DFO)


def _dfo(i):
    t = _titre(i)
    return any(m in t for m in MOTS_DFO)


def _base(e):
    """Achat P, non routinier, hors plan 10b5-1 (oui seulement), montant et valeur en bourse dans les bornes."""
    if e.get("sens") != "achat":
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    m = e.get("montant")
    if m is None or m < MONTANT_MINIMUM:
        return False
    v = e.get("valeur_m")
    return v is not None and VALEUR_MIN <= v <= VALEUR_MAX


def _part_ok(e):
    if e.get("nouvelle_position") is True:  # rien détenu avant : rempli
        return True
    p = e.get("part")
    return p is not None and p >= PART_MIN


def _silencieux(ctx, cik_initie, cik_cie, jour_premier, jours):
    """Aucun achat ni vente de l'initié dans la compagnie, daté de jour_premier − jours à la veille de jour_premier."""
    debut = _jour(jour_premier, -jours)
    for r in ctx.historique_initie(cik_initie):  # tout l'historique déposé au plus tard aujourd'hui
        if r[1] != cik_cie or r[3] not in ("achat", "vente"):
            continue
        premier, dernier = r[4] or r[0], r[5] or r[0]
        if premier < jour_premier and dernier >= debut:
            return False
    return True


def _qualifies(e, ctx):
    """Les déclarants qui remplissent les conditions propres à l'initié : titre PDG ou DFO, et silence de 365 jours."""
    t = e.get("jour_premier") or e["depot"]
    return [i for i in (e.get("inities") or [])
            if _pdg_ou_dfo(i) and _silencieux(ctx, i.get("cik"), e["cik"], t, SILENCE_JOURS)]


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e) or not _part_ok(e):
        return False
    return bool(_qualifies(e, ctx)) and _actions_ordinaires(e)


def priorite(e, ctx):
    dfo = any(_dfo(i) for i in _qualifies(e, ctx))
    part = 2 * PART_PLAFOND if e.get("nouvelle_position") is True else min(float(e.get("part") or 0.0), PART_PLAFOND)
    return (1e9 if dfo else 0.0) + part
