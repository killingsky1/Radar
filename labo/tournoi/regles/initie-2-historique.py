"""initie-2-historique : initié qui a déjà bien acheté (majorité de réussites passées) (règle pré-enregistrée, piste « initie »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- Filtre : achat P d'actions ordinaires. roles contient dirigeant ou administrateur (un actionnaire de 10 % seul est
  exclu). routinier = non. plan_10b5_1 différent de oui. montant ≥ 25 000 $. valeur_m entre 100 et 2 000 M$.
  HISTORIQUE : les achats passés en bourse de cet initié (initie_cik), dans toutes ses compagnies, déposés au moins 190
  jours civils avant le dépôt actuel. Deux dépôts dans la même compagnie à moins de 30 jours d'écart comptent pour un
  seul, le premier. Un achat passé est « évaluable » s'il a un prix SEC d'entrée (clôture du 1er jour de bourse après son
  dépôt, ou premier prix dans les 5 jours suivants) et un prix 126 jours de bourse plus tard (ou premier prix dans les 10
  jours suivants). Il « réussit » si son rendement dépasse celui de SPY sur les mêmes dates. Condition : au moins 2
  achats évaluables, et STRICTEMENT plus de la moitié ont réussi. Pas d'action déjà en portefeuille. Le même jour : plus
  haut taux de réussite d'abord, puis le plus gros montant.
- Changement 3 de regles_du_jeu.md (après le critique) : un achat passé ne compte que si sa mesure était finie avant la
  décision (le banc l'impose).
- Entrée : clôture du 1er jour de bourse après le dépôt ; sinon 1er prix dans les 5 jours de bourse suivants ; sinon rien.
- Sortie : clôture du 126e jour de bourse après l'achat ; sinon 1er prix dans les 10 jours suivants ; compagnie
  disparue : dernier prix connu.
- Taille : 20 % du portefeuille, 5 positions au plus, signaux ignorés quand c'est plein, argent qui attend dans SPY.
"""
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

ID = "initie-2-historique"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu de données (code P, titres non dérivés). Le champ "
    "« titres » n'est pas filtré : il n'est pas dans la liste des champs de la règle.",
    "Plusieurs déclarants sur le formulaire : l'événement est gardé si AU MOINS UN déclarant a le rôle dirigeant ou "
    "administrateur ET remplit la condition d'historique (son propre historique, ctx.historique_initie(son cik)). Le "
    "taux de la priorité est le meilleur taux parmi ces déclarants.",
    "Changement 3 de regles_du_jeu.md : un achat passé ne compte que si sa mesure est finie au moment de la décision, "
    "c'est-à-dire si la date de son prix de sortie est au plus tard le jour du dépôt actuel (garder décide le soir du "
    "dépôt, après la clôture ; le banc refuse toute donnée plus récente). Une mesure pas encore finie ne compte pas. "
    "Le critique la disait « impossible telle qu'écrite » (petite fuite du futur) ; avec ce changement, elle est "
    "testable : IMPOSSIBLE = None.",
    "190 jours : date de dépôt de l'achat passé ≤ date du dépôt actuel − 190 jours civils.",
    "Achats passés : toutes les lignes « achat » de l'historique de l'initié (toutes compagnies, la compagnie actuelle "
    "comprise), sans autre filtre (rôle, montant, routinier, plan 10b5-1 : non vérifiés pour les achats passés). Les "
    "ventes ne servent pas.",
    "Regroupement 30 jours (même compagnie = même cik de compagnie) : en ordre de dépôt, un achat passé ne compte pas si "
    "l'initié a un autre achat dans la même compagnie déposé moins de 30 jours civils avant lui. Une suite de dépôts "
    "espacés chacun de moins de 30 jours compte donc pour un seul, le premier (lecture littérale : chaque paire à moins "
    "de 30 jours compte pour une). Le regroupement se fait avant de savoir si l'achat est évaluable.",
    "Mesure d'un achat passé (comme le banc pour ses propres positions) : entrée = 1re clôture SEC du symbole écrit dans "
    "ce dépôt passé, du 1er jour de bourse après son dépôt jusqu'aux 5 jours de bourse suivants ; sortie = 1re clôture "
    "du 126e jour de bourse après le jour d'entrée jusqu'aux 10 jours de bourse suivants. « Jours suivants » = jours de "
    "bourse, comme l'entrée et la sortie de la règle. Sans prix dans l'une des fenêtres : pas évaluable (pas de repli "
    "sur le dernier prix connu, le texte n'en parle pas pour les achats passés).",
    "Rendement d'un achat passé : sortie ÷ entrée − 1, enchaîné de part et d'autre d'un changement de CUSIP (même calcul "
    "que le banc, car le dictionnaire interdit de comparer deux prix de CUSIP différents). SPY : dernière clôture au "
    "plus tard à la date d'entrée et à la date de sortie (10 jours au plus, comme le banc). « Réussit » = rendement "
    "STRICTEMENT plus grand que celui de SPY.",
    "Pas évaluable : symbole absent ; dépôt passé avant le début du calendrier des prix (juillet 2015 dans le vrai jeu : "
    "le 1er jour de bourse après le dépôt ne peut pas être situé) ; un prix d'entrée ≤ 0 (ou le 1er prix après un "
    "changement de CUSIP) ; SPY sans prix.",
    "Condition : au moins 2 achats passés évaluables et réussis × 2 > évaluables (strictement plus de la moitié).",
    "plan_10b5_1 : refusé seulement si « oui » (true) ; vide (null) accepté. routinier doit valoir false. montant ≥ "
    "25 000 $ (absent = refusé). valeur_m entre 100 et 2 000 M$, bornes comprises (absente = refusée).",
    "Priorité le même jour (fonction priorite, un seul nombre) : taux de réussite arrondi au millionième, puis le plus "
    "gros montant (plafonné à 999 999 999 $ pour garder l'ordre ; deux montants à moins de 0,13 $ l'un de l'autre "
    "peuvent compter comme égaux). Égalité : le banc prend le dépôt le plus ancien, puis le numéro. Le banc trie "
    "ensemble les signaux du jour et ceux qui attendent encore un prix.",
    "Un petit cache garde les mesures FINIES des achats passés (symbole, dépôt) avec leur date de fin ; il ne sert que si "
    "cette date est au plus tard le jour de la décision : le résultat est le même que sans cache.",
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
JOURS_AVANT = 190          # achat passé déposé au moins 190 jours civils avant le dépôt actuel
REGROUPEMENT = 30          # deux dépôts dans la même compagnie à moins de 30 jours : un seul, le premier
PASSE_TOL_ENTREE = 5       # prix d'entrée d'un achat passé : 1er jour de bourse après son dépôt + 5 jours de bourse
PASSE_DUREE = 126          # prix de sortie : 126 jours de bourse après l'entrée
PASSE_TOL_SORTIE = 10      # ... + 10 jours de bourse
MIN_EVALUABLES = 2

_MESURES = {}  # (symbole, dépôt passé) → mesure FINIE (statut, réussi, date de fin) : ne dépend que du passé


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


def _calculer(ctx, symbole, depot):
    """Mesure d'un achat passé avec ce qui est connu le jour de ctx : ("ok", réussi, date du prix de sortie) ou
    ("non", None, date où l'on sait qu'il n'est pas évaluable) ; ("pas_fini", None, None) si la mesure n'est pas finie."""
    if not symbole:
        return ("non", None, depot)
    cal = ctx.jours_de_bourse("0000-00-00")  # tous les jours de bourse jusqu'à aujourd'hui (un trou n'efface rien)
    if not cal or cal[0] > depot:  # le calendrier des prix commence après ce dépôt : 1er jour de bourse inconnu
        return ("non", None, depot)
    k = bisect_right(cal, depot)  # le 1er jour de bourse APRÈS le dépôt passé
    fenetre = cal[k:k + 1 + PASSE_TOL_ENTREE]
    if not fenetre:
        return ("pas_fini", None, None)
    px = ctx.clotures(symbole, fenetre[0], fenetre[-1])
    if not px:
        if len(fenetre) < 1 + PASSE_TOL_ENTREE:  # la fenêtre d'entrée n'est pas finie
            return ("pas_fini", None, None)
        return ("non", None, fenetre[-1])
    entree = px[0]
    i = bisect_left(cal, entree[0])
    fenetre = cal[i + PASSE_DUREE:i + PASSE_DUREE + 1 + PASSE_TOL_SORTIE]
    if not fenetre:
        return ("pas_fini", None, None)
    px = ctx.clotures(symbole, fenetre[0], fenetre[-1])
    if not px:
        if len(fenetre) < 1 + PASSE_TOL_SORTIE:  # la fenêtre de sortie n'est pas finie
            return ("pas_fini", None, None)
        return ("non", None, fenetre[-1])
    sortie = px[0]
    # Rendement enchaîné de part et d'autre d'un changement de CUSIP (comme le banc)
    serie = ctx.clotures(symbole, entree[0], sortie[0])
    r, base = 1.0, serie[0][1]
    if base <= 0:
        return ("non", None, sortie[0])
    for j in range(1, len(serie)):
        if serie[j][2] != serie[j - 1][2]:
            r *= serie[j - 1][1] / base
            base = serie[j][1]
            if base <= 0:
                return ("non", None, sortie[0])
    rendement = r * serie[-1][1] / base - 1
    a, b = ctx.cloture("SPY", entree[0]), ctx.cloture("SPY", sortie[0])
    if not a or not b or a[1] <= 0:
        return ("non", None, sortie[0])
    marche = b[1] / a[1] - 1
    return ("ok", rendement > marche, sortie[0])


def _mesure(ctx, symbole, depot):
    cle = (symbole, depot)
    m = _MESURES.get(cle)
    if m is not None and m[2] <= ctx.jour:  # finie au plus tard aujourd'hui : même résultat que recalculée
        return m
    m = _calculer(ctx, symbole, depot)
    if m[0] != "pas_fini":
        _MESURES.setdefault(cle, m)
    return m


def _taux(ctx, cik_initie, depot):
    """Taux de réussite des achats passés de l'initié, ou None si la condition n'est pas remplie."""
    limite = _jour(depot, -JOURS_AVANT)
    precedent, comptes = {}, []
    for r in ctx.historique_initie(cik_initie):  # en ordre de dépôt
        if r[3] != "achat" or r[0] > limite:
            continue
        p = precedent.get(r[1])
        if p is None or (date.fromisoformat(r[0]) - date.fromisoformat(p)).days >= REGROUPEMENT:
            comptes.append(r)
        precedent[r[1]] = r[0]
    evaluables = reussis = 0
    for r in comptes:
        statut, reussi, _ = _mesure(ctx, r[2], r[0])
        if statut == "ok":
            evaluables += 1
            reussis += 1 if reussi else 0
    if evaluables >= MIN_EVALUABLES and 2 * reussis > evaluables:
        return reussis / evaluables
    return None


def _meilleur_taux(e, ctx):
    meilleur = None
    for i in e.get("inities") or []:
        if not _role_ok(i):
            continue
        t = _taux(ctx, i.get("cik"), e["depot"])
        if t is not None and (meilleur is None or t > meilleur):
            meilleur = t
    return meilleur


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e):
        return False
    return _meilleur_taux(e, ctx) is not None and _actions_ordinaires(e)


def priorite(e, ctx):
    t = _meilleur_taux(e, ctx) or 0.0
    return round(t, 6) * 1e15 + min(float(e.get("montant") or 0.0), 999_999_999.0)
