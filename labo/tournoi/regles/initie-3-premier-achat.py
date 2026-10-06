"""initie-3-premier-achat : premier achat de l'initié dans la compagnie depuis 2 ans (règle pré-enregistrée, piste « initie »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- Filtre : achat P d'actions ordinaires. roles contient dirigeant ou administrateur (pas un actionnaire de 10 % seul).
  routinier = non. plan_10b5_1 différent de oui. montant ≥ 25 000 $. valeur_m entre 100 et 2 000 M$. HISTORIQUE : aucun
  achat (P) ni vente (S) en bourse par cet initié (initie_cik) dans cette compagnie (cik_emetteur) pendant les 730 jours
  civils avant le jour_premier_achat de ce dépôt. Un tout premier achat compte aussi. Pas d'action déjà en portefeuille.
  Le même jour : le plus gros montant d'abord.
- Entrée : clôture du 1er jour de bourse après le dépôt (ou 1er prix SEC dans les 5 jours de bourse suivants, sinon rien).
- Sortie : clôture du 126e jour de bourse après l'achat (ou 1er prix dans les 10 jours suivants ; dernier prix connu si
  la compagnie disparaît).
- Taille : 20 % du portefeuille, 5 positions au plus, signaux ignorés quand c'est plein, argent qui attend dans SPY.
"""
from datetime import date, timedelta

ID = "initie-3-premier-achat"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu de données (code P, titres non dérivés). Le champ "
    "« titres » n'est pas filtré : il n'est pas dans la liste des champs de la règle.",
    "Plusieurs déclarants sur le formulaire : l'événement est gardé si AU MOINS UN déclarant a le rôle dirigeant ou "
    "administrateur ET n'a ni acheté ni vendu dans la compagnie pendant les 730 jours (son propre historique).",
    "Silence de 730 jours : fenêtre du jour_premier − 730 jours civils jusqu'à la veille du jour_premier (les 730 jours "
    "AVANT). On regarde les DATES DES OPÉRATIONS (pas les dates de dépôt) des lignes « achat » et « vente » de "
    "ctx.historique_initie(cik de l'initié) pour la même compagnie (même cik de compagnie). Un dépôt passé ne donne "
    "que la 1re et la dernière date de ses opérations : il casse le silence si cette période touche la fenêtre "
    "(jour_premier du dépôt passé ≤ veille du jour_premier actuel ET jour_dernier du dépôt passé ≥ début de la "
    "fenêtre). Une date d'opération absente est remplacée par la date de dépôt.",
    "Seuls les dépôts faits au plus tard le jour du dépôt actuel sont vus (le banc l'impose) : une opération déclarée "
    "plus tard ne compte pas.",
    "Le dépôt actuel lui-même ne casse pas le silence (ses achats sont au jour_premier ou après) ; mais une VENTE du même "
    "formulaire datée d'avant le jour_premier le casse (lecture littérale : « aucune vente pendant les 730 jours »).",
    "jour_premier absent dans l'événement : la date de dépôt le remplace.",
    "Un initié sans aucun historique dans la compagnie (tout premier achat) remplit la condition.",
    "plan_10b5_1 : refusé seulement si « oui » (true) ; vide (null) accepté. routinier doit valoir false. montant ≥ "
    "25 000 $ (absent = refusé). valeur_m entre 100 et 2 000 M$, bornes comprises (absente = refusée).",
    "Priorité le même jour : le plus gros montant (fonction priorite = montant). Égalité : le banc prend le dépôt le "
    "plus ancien, puis le numéro. Le banc trie ensemble les signaux du jour et ceux qui attendent encore un prix.",
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
SILENCE_JOURS = 730


def _jour(iso, n):
    return (date.fromisoformat(iso) + timedelta(days=n)).isoformat()


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


def _role_ok(i):
    roles = i.get("roles") or []
    return "dirigeant" in roles or "administrateur" in roles


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


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e):
        return False
    t = e.get("jour_premier") or e["depot"]
    return any(_role_ok(i) and _silencieux(ctx, i.get("cik"), e["cik"], t, SILENCE_JOURS)
               for i in (e.get("inities") or [])) and _actions_ordinaires(e)


def priorite(e, ctx):
    return float(e.get("montant") or 0.0)
