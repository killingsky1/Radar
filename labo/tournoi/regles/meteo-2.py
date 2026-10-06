"""meteo-2 : après la tempête, suivre les achats d'initiés seulement après une baisse de 10 % du S&P 500 (piste « meteo »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- MÉTÉO, chaque jour de bourse : baisse = clôture SPY du jour ÷ plus haute clôture SPY des 252 derniers jours de bourse
  (jour compris) − 1. La FENÊTRE est OUVERTE un jour donné si la baisse a été de −10 % ou pire au moins une fois dans
  les 126 jours de bourse précédents (jour compris) ; sinon fermée. (Paramètres fixes : « la fenêtre reste ouverte
  126 jours de bourse après le dernier jour sous ce seuil ».)
- PANIER : achat P ; roles contient administrateur ou dirigeant ; routinier = non ; plan_10b5_1 différent de « oui »
  (vide accepté) ; montant >= 100 000 $ ; valeur_m >= 100 M$ ; on ne possède pas déjà cette compagnie.
- Entrée : seulement si la FENÊTRE est OUVERTE le jour d'entrée ; clôture SEC du 1er jour de bourse après le dépôt,
  sinon la 1re clôture des 5 jours de bourse suivants, sinon on laisse passer. Le même jour : plus gros montant d'abord.
- Sortie : 1re clôture SEC à partir du 126e jour de bourse après l'entrée, même si la fenêtre s'est fermée ; aucun prix
  dans les 20 jours de bourse après : dernière clôture connue.
- Taille : 10 cases de 10 % de la valeur du portefeuille ; pleines : on laisse passer ; le reste dans SPY (10 $ par
  transaction, SPY compris).
"""
from datetime import date, timedelta

ID = "meteo-2"
IMPOSSIBLE = None

CHOIX = [
    # --- Le panier
    "« Achat P » = un événement « achat » du jeu de données (code P, titres non dérivés, en bourse).",
    "Rôles : l'événement est gardé si AU MOINS UN déclarant du formulaire a « administrateur » ou « dirigeant » dans "
    "ses rôles (un formulaire peut avoir plusieurs déclarants). Si tous les déclarants sont seulement actionnaires de "
    "10 % ou « autre », il est refusé.",
    "routinier = non : le champ routinier de l'événement doit valoir false (il vaut true si un des déclarants est "
    "routinier).",
    "plan_10b5_1 différent de « oui » : refusé seulement si true ; false et vide (null) acceptés.",
    "montant >= 100 000 $ et valeur_m >= 100 M$ : bornes comprises ; montant ou valeur_m absent (null) = refusé.",
    "« On ne possède pas déjà cette compagnie » : fait par le banc, qui refuse un SYMBOLE déjà en portefeuille (une "
    "compagnie qui aurait deux symboles, par exemple deux catégories d'actions, pourrait être achetée deux fois).",
    "Plusieurs événements le même jour : priorite = montant (le plus gros d'abord). Égalité : le banc prend le dépôt "
    "le plus ancien, puis le numéro du dépôt. Le banc trie ensemble les signaux du jour et ceux qui attendent encore "
    "un prix.",
    # --- Entrée, sortie, taille
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le 1er jour de bourse après le dépôt ; sans prix, le 1er prix "
    "des 5 jours de bourse suivants ; sinon abandon).",
    "Sortie : DUREE = 126 et TOLERANCE_SORTIE = 20 : vente à la 1re clôture SEC à partir du 126e jour de bourse après "
    "le jour d'achat, cherchée jusqu'au 20e jour de bourse après ce 126e jour ; aucun prix : dernière clôture connue "
    "(le banc ne « signale » pas le cas : on le voit à la date de vente plus ancienne que prévu). Pas de vente plus "
    "tôt (pas de sortir_avant), même si la fenêtre se ferme.",
    "Taille : MAX_POSITIONS = 10 (10 % chacune) ; ARGENT_QUI_ATTEND = « SPY » ; LIQUIDE_JOURS = 0 (l'argent d'une "
    "vente retourne dans SPY le jour même). Les 10 places prises : le signal est laissé, même s'il attendait un prix.",
    "Banc (diffère du texte) : le 10 % est calculé avec la valeur du portefeuille à la clôture du jour d'achat (après "
    "les ventes du jour), pas à la clôture de la veille ; la position vaut ce 10 % MOINS les 10 $ de frais ; s'il ne "
    "reste pas assez d'argent, il achète avec ce qui reste ; une position de moins de 50 $ n'est pas achetée "
    "(MONTANT_MIN = 50, réglage par défaut du banc).",
    "Banc (diffère du texte) : en plus des 10 $ par transaction (SPY compris), un demi-écart achat-vente selon la "
    "valeur en bourse, à l'achat et à la vente.",
    "Banc (le texte n'en parle pas) : changement de CUSIP pendant la détention = rendement enchaîné ; les ventes du "
    "jour passent avant les achats du jour ; une position encore ouverte à la fin des prix reste ouverte ; "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0 (un symbole vendu peut être racheté tout de suite).",
    # --- La météo
    "Le banc décide la veille : investir(jour, ctx) reçoit le jour de bourse d'AVANT le jour d'achat et ne voit que "
    "les données jusqu'à ce jour-là. La fenêtre est vérifiée pour le jour où l'achat se fait vraiment (jour du prix, "
    "même après des jours sans prix). Un signal qui arrive quand la fenêtre est FERMÉE (avec un prix ce jour-là) est "
    "laissé, pas gardé pour plus tard.",
    "Baisse d'un jour de bourse X (calendrier du banc) : clôture SPY de X ÷ plus haute clôture SPY des 252 jours de "
    "bourse du calendrier finissant à X (X compris) − 1. Un jour sans clôture SPY n'a pas de baisse et ne compte pas "
    "dans le plus haut. Au tout début des prix (juillet 2015), le plus haut est pris sur les clôtures disponibles.",
    "« −10 % ou pire » : baisse <= −0,10.",
    "Jour d'achat J : le texte compte J lui-même dans les 126 jours, mais sa clôture n'est pas connue quand on décide "
    "(le banc décide la veille). La fenêtre utilisée pour un achat le jour J est donc celle de J sans J : OUVERTE si une "
    "baisse <= −10 % a eu lieu dans les 125 autres jours de bourse de cette fenêtre (de J − 125 à la veille comprise). "
    "Elle s'ouvre le lendemain du 1er jour sous −10 % (un jour plus tard que le texte : forcé) et reste ouverte "
    "jusqu'au 125e jour de bourse après le dernier jour sous −10 %, comme « 126 jours précédents (jour compris) » "
    "appliqué au jour d'achat.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : écart corrigé DANS CE FICHIER. Avant, la fenêtre d'un achat le "
    "jour J était celle de la veille (les 126 jours finissant à la veille) : elle restait ouverte un jour de trop, le "
    "126e jour de bourse après la dernière baisse (jeu ciblé : achats du 20 février 2024 et du 26 janvier 2026 que le "
    "vérificateur ne faisait pas). Le filtre définit la fenêtre d'un jour par « les 126 jours de bourse précédents (jour "
    "compris) » et l'entrée veut la fenêtre OUVERTE « le jour d'entrée » : celle de J va de J − 125 à J, fermée si la "
    "dernière baisse date de J − 126. Les paramètres fixes (« reste ouverte 126 jours de bourse après le dernier jour "
    "sous ce seuil ») ne font que résumer ce 126 ; la définition précise du filtre l'emporte (sens le plus simple). On "
    "regarde donc les 125 jours connus de la fenêtre de J, comme le vérificateur ; le seuil (126 jours, −10 %) ne change "
    "pas.",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

# Seuils du texte
MONTANT_MINIMUM = 100_000  # $
VALEUR_MINIMUM = 100  # M$
JOURS_HAUT = 252  # plus haute clôture des 252 derniers jours de bourse (jour compris)
JOURS_FENETRE = 126  # baisse sous le seuil au moins une fois dans les 126 jours de bourse (jour compris)
SEUIL = -0.10


# ---------- Le panier ----------

def _panier(e):
    if e.get("sens") != "achat":
        return False
    if not any(r in ("administrateur", "dirigeant") for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant, valeur = e.get("montant"), e.get("valeur_m")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    if valeur is None or valeur < VALEUR_MINIMUM:
        return False
    return True


def garder(e, ctx):
    return _panier(e)


def priorite(e, ctx):
    return float(e.get("montant") or 0.0)


# ---------- La fenêtre ----------
# Cache de calculs : la baisse d'un jour X ne dépend que des clôtures SPY jusqu'à X.
_BAISSE = {}  # jour de bourse → baisse (None : pas de clôture SPY ce jour-là)


def investir(jour, ctx):
    """`jour` = la veille du jour d'achat J : la fenêtre de J (126 jours de bourse finissant à J) sans J lui-même, dont
    la clôture n'est pas encore connue : les 125 jours de bourse finissant à `jour`."""
    jours = ctx.jours_de_bourse((date.fromisoformat(jour) - timedelta(days=800)).isoformat())  # ~550 jours de bourse
    if not jours:
        return False
    n = len(jours)
    fenetre = range(max(0, n - (JOURS_FENETRE - 1)), n)
    a_calculer = [k for k in fenetre if jours[k] not in _BAISSE]
    if a_calculer:
        debut = jours[max(0, a_calculer[0] - JOURS_HAUT + 1)]
        spy = {d: p for d, p, _ in ctx.clotures("SPY", debut, jours[-1])}
        for k in a_calculer:
            x = jours[k]
            if x not in spy:
                _BAISSE[x] = None
                continue
            haut = max(spy[d] for d in jours[max(0, k - JOURS_HAUT + 1):k + 1] if d in spy)
            _BAISSE[x] = spy[x] / haut - 1
    return any(_BAISSE[jours[k]] is not None and _BAISSE[jours[k]] <= SEUIL for k in fenetre)
