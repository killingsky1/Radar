"""initie-4-engagement : gros engagement, l'initié augmente beaucoup ce qu'il détient (règle pré-enregistrée, piste « initie »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- Filtre : achat P d'actions ordinaires. roles contient dirigeant ou administrateur (pas un actionnaire de 10 % seul).
  routinier = non. plan_10b5_1 différent de oui. montant ≥ 100 000 $. part_ajoutee ≥ 0,20 (un achat sans actions
  détenues avant compte comme rempli). valeur_m entre 100 et 2 000 M$. Pas d'action déjà en portefeuille. Le même jour :
  part_ajoutee la plus élevée d'abord.
- Note de testabilité : si les actions détenues avant valent zéro (division impossible), le critère est rempli.
- Entrée : clôture du 1er jour de bourse après le dépôt (ou 1er prix SEC dans les 5 jours de bourse suivants, sinon rien).
- Sortie : clôture du 126e jour de bourse après l'achat (ou 1er prix dans les 10 jours suivants ; dernier prix connu si
  la compagnie disparaît).
- Taille : 20 % du portefeuille, 5 positions au plus, signaux ignorés quand c'est plein, argent qui attend dans SPY.
"""

ID = "initie-4-engagement"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu de données (code P, titres non dérivés). Le champ "
    "« titres » n'est pas filtré : il n'est pas dans la liste des champs de la règle.",
    "Rôle : AU MOINS UN déclarant du formulaire a le rôle dirigeant ou administrateur (un actionnaire de 10 % seul ou "
    "« autre » seul ne suffit pas).",
    "part_ajoutee = le champ part du jeu de données (achetées ÷ détenues avant, dans le plus gros groupe de lignes). "
    "Condition : part ≥ 0,20, OU nouvelle_position = vrai (rien détenu avant : « compte comme rempli »). Le champ "
    "apres n'est pas utilisé (part est déjà calculée).",
    "Détenues avant INCONNUES (part vide et nouvelle_position faux, ex. déclaration incohérente) : refusé, car la "
    "condition ne peut pas être vérifiée (ce n'est pas « sans actions détenues avant »).",
    "Priorité le même jour (fonction priorite) : la part la plus élevée ; une nouvelle position (rien détenu avant, part "
    "infinie) passe en premier. Égalité : le banc prend le dépôt le plus ancien, puis le numéro. Le banc trie ensemble "
    "les signaux du jour et ceux qui attendent encore un prix.",
    "plan_10b5_1 : refusé seulement si « oui » (true) ; vide (null) accepté. routinier doit valoir false. montant ≥ "
    "100 000 $ (absent = refusé). valeur_m entre 100 et 2 000 M$, bornes comprises (absente = refusée).",
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
    "Comparaison des deux programmations (jeu ciblé : 7 achats le même jour, parts de 2 à 8 millions, 5 places) : le "
    "vérificateur plafonnait la part de la priorité à 999 999 (nouvelle position : 10^6), donc ces signaux étaient à "
    "égalité chez lui (ordre du banc) et classés par part chez le testeur. Le texte dit « part_ajoutee la plus élevée "
    "d'abord » : pas de plafond, et une nouvelle position compte comme une part infinie. Vérificateur corrigé.",
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

MONTANT_MINIMUM = 100_000
VALEUR_MIN, VALEUR_MAX = 100, 2000
PART_MIN = 0.20


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


def _part_ok(e):
    if e.get("nouvelle_position") is True:  # rien détenu avant : compte comme rempli
        return True
    p = e.get("part")
    return p is not None and p >= PART_MIN


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e):
        return False
    if not any(_role_ok(i) for i in (e.get("inities") or [])):
        return False
    return _part_ok(e) and _actions_ordinaires(e)


def priorite(e, ctx):
    if e.get("nouvelle_position") is True:
        return float("inf")
    return float(e.get("part") or 0.0)
