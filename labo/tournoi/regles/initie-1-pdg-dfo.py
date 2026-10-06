"""initie-1-pdg-dfo : achat non routinier du PDG ou du directeur financier (règle pré-enregistrée, piste « initie »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- Filtre : formulaire 4 avec achat en bourse (code P) d'actions ordinaires. Le champ « titre » contient, sans tenir compte
  des majuscules, CEO, Chief Executive ou Principal Executive (PDG), ou bien CFO, Chief Financial ou Principal Financial
  (directeur financier). « President » seul ne compte pas. routinier = non. plan_10b5_1 différent de oui (vide accepté
  avant avril 2023). montant ≥ 25 000 $. valeur_m entre 100 M$ et 2 000 M$. On n'achète pas une action déjà en
  portefeuille. Si plusieurs signaux tombent le même jour : directeur financier d'abord, puis le plus gros montant.
- Entrée : clôture du 1er jour de bourse après le dépôt ; sans prix SEC, le 1er jour avec un prix dans les 5 jours de
  bourse suivants ; sinon on laisse tomber.
- Sortie : clôture du 126e jour de bourse après l'achat ; sans prix, 1er prix dans les 10 jours de bourse suivants ;
  compagnie disparue : dernier prix connu. Pas de vente anticipée, pas de limite de perte.
- Taille : 20 % de la valeur du portefeuille (actions + SPY), 5 positions au plus, signaux ignorés quand c'est plein,
  argent qui attend dans SPY (10 $ par opération sur SPY).
"""

ID = "initie-1-pdg-dfo"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat en bourse (code P) d'actions ordinaires » = un événement « achat » du jeu de données (code P, titres non "
    "dérivés). Le champ « titres » n'est pas filtré : il n'est pas dans la liste des champs de la règle.",
    "Titre : on cherche les mots comme des bouts de texte (« contient »), sans tenir compte des majuscules : ceo, "
    "chief executive, principal executive, cfo, chief financial, principal financial. Aucune autre correction du "
    "texte libre (espaces, abréviations ; un titre « See Remarks » ne compte pas). « President » seul ne contient "
    "aucun de ces mots : il ne compte pas.",
    "Plusieurs déclarants sur le formulaire : l'événement est gardé si le titre d'AU MOINS UN déclarant contient un de "
    "ces mots. Il est « directeur financier » (priorité) si le titre d'au moins un déclarant contient cfo, chief "
    "financial ou principal financial (même s'il contient aussi CEO).",
    "Le rôle (roles) n'est pas vérifié à part : le filtre écrit ne le demande pas ; le titre PDG ou directeur "
    "financier suffit.",
    "plan_10b5_1 : refusé seulement si « oui » (true). Vide (null) accepté à toutes les dates, aussi après avril 2023 : "
    "la condition écrite est « différent de oui » ; la parenthèse (vide accepté avant avril 2023) est lue comme une "
    "explication, pas comme une condition de plus.",
    "routinier = non : le champ routinier doit valoir false.",
    "montant ≥ 25 000 $ : le champ montant ; montant absent = refusé.",
    "valeur_m entre 100 et 2 000 M$ : bornes comprises (100 ≤ valeur_m ≤ 2 000) ; valeur_m absente = refusé.",
    "Priorité le même jour (fonction priorite, un seul nombre) : directeur financier d'abord (+1 000 000 000 000), puis "
    "le plus gros montant (plafonné à 10^12 − 1 $ pour garder l'ordre). Égalité : le banc prend le dépôt le plus ancien, "
    "puis le numéro du dépôt. Le banc trie ensemble les signaux du jour et ceux qui attendent encore un prix.",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le jour prévu, puis les 5 jours de bourse suivants).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat, TOLERANCE_SORTIE = 10. Banc : sans prix pendant ces "
    "10 jours, il prend la dernière clôture connue même si la compagnie n'a pas disparu (le texte ne parle que de la "
    "compagnie disparue).",
    "Banc (diffère du texte) : en plus des 10 $ par transaction (SPY compris), il compte un demi-écart achat-vente selon "
    "la valeur en bourse, à l'achat et à la vente.",
    "Banc (diffère du texte) : la position vaut 20 % de la valeur du portefeuille MOINS les 10 $ de frais ; s'il ne "
    "reste pas assez d'argent, il achète avec ce qui reste ; une position de moins de 50 $ n'est pas achetée "
    "(MONTANT_MIN = 50, réglage par défaut du banc, le texte n'en parle pas).",
    "Banc (le texte n'en parle pas) : changement de CUSIP pendant la détention = rendement enchaîné ; les ventes du jour "
    "passent avant les achats du jour ; une position encore ouverte à la fin des prix reste ouverte.",
    "Faits par le banc, comme le texte : pas d'achat d'une action déjà en portefeuille ; signal ignoré quand les 5 "
    "places sont prises (même s'il attendait un prix) ; argent qui attend dans SPY (LIQUIDE_JOURS = 0), 10 $ par "
    "vente ou achat de SPY ; aucune vente anticipée (pas de sortir_avant).",
    "Comparaison des deux programmations (jeu ciblé : 7 achats de 110 à 170 G$ le même jour, 5 places) : le testeur "
    "plafonnait le montant de la priorité à 100 G$, le vérificateur à 10^12 − 1 $ ; au-dessus de 100 G$, les signaux "
    "du même jour étaient donc classés autrement. Le texte dit « le plus gros montant » : on garde le plafond le plus "
    "haut, 10^12 − 1 $, dans les deux (testeur corrigé). Au-delà, deux montants comptent comme égaux (ordre du banc).",
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
MOTS_PDG = ("ceo", "chief executive", "principal executive")
MOTS_DFO = ("cfo", "chief financial", "principal financial")


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


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e):
        return False
    return any(_pdg_ou_dfo(i) for i in (e.get("inities") or [])) and _actions_ordinaires(e)


def priorite(e, ctx):
    dfo = any(_dfo(i) for i in (e.get("inities") or []))
    return (1e12 if dfo else 0.0) + min(float(e.get("montant") or 0.0), 1e12 - 1)
