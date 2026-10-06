"""meteo-2 — Après la tempête : suivre les achats d'initiés seulement après une baisse de 10 % du S&P 500.

Programmée par le VÉRIFICATEUR, d'après labo/tournoi/regles_preenregistrees.json, sans voir labo/tournoi/regles/.
- Météo (chaque jour de bourse) : baisse = clôture SPY du jour / plus haute clôture SPY des 252 derniers jours de bourse
  (jour compris) − 1. FENÊTRE OUVERTE un jour donné si la baisse a été de -10 % ou pire au moins une fois dans les
  126 jours de bourse précédents (jour compris).
- Panier : achat P d'un administrateur ou dirigeant, non routinier, pas de plan 10b5-1 « oui », montant >= 100 000 $,
  valeur_m >= 100 M$. Entrée seulement si la fenêtre est ouverte le jour d'entrée. Garde de 126 jours de bourse.
"""
from datetime import date, timedelta

ID = "meteo-2"

CHOIX = [
    # --- Le panier (commun aux règles meteo-*) ---
    "Panier : l'événement doit être un achat (sens = « achat », code P).",
    "Rôles : il suffit qu'UN des déclarants du formulaire ait le rôle « administrateur » ou « dirigeant » (un formulaire "
    "peut avoir plusieurs déclarants) ; un actionnaire de 10 % ou « autre » sans l'un de ces deux rôles est exclu.",
    "routinier = non : exclu si e['routinier'] est vrai. plan_10b5_1 : exclu seulement s'il vaut true (false ou vide "
    "acceptés).",
    "montant ou valeur_m inconnu (None) : l'événement est exclu, car on ne peut pas vérifier le seuil (100 000 $ ; "
    "100 M$).",
    "« On ne possède pas déjà cette compagnie » : fait par le banc, par SYMBOLE (deux catégories d'actions d'une même "
    "compagnie ont deux symboles).",
    # --- Entrée, sortie, taille (réglages et comportement du banc) ---
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (clôture SEC du 1er jour de bourse après le dépôt ; sans prix, la "
    "1re clôture des 5 jours de bourse suivants ; sinon l'événement passe).",
    "Sortie : DUREE = 126 (le banc vend à la 1re clôture SEC à partir du 126e jour de bourse après l'entrée, même si la "
    "fenêtre s'est fermée) et TOLERANCE_SORTIE = 20 (aucun prix pendant les 20 jours de bourse après cette date : la "
    "dernière clôture connue). Le « signalement » d'une compagnie disparue est laissé au labo (la règle ne le fait pas).",
    "Plusieurs événements le même jour : priorite = montant (le plus gros d'abord). Le banc classe ensemble les signaux du "
    "jour et ceux qui attendent encore un prix.",
    "Taille (comportement du banc) : 10 cases (MAX_POSITIONS = 10) ; le banc vise 10 % de la valeur du portefeuille à la "
    "clôture du JOUR d'achat (pas de la veille), les 10 $ de frais de l'achat pris dans ces 10 % ; s'il reste moins "
    "d'argent, il achète avec ce qui reste (pas d'achat sous 50 $ : MONTANT_MIN du banc).",
    "Argent qui attend : SPY ; l'argent d'une vente retourne dans SPY le jour même (ARGENT_QUI_ATTEND = 'SPY', "
    "LIQUIDE_JOURS = 0). Frais du banc : 10 $ par transaction, SPY compris, plus le demi-écart.",
    # --- La météo dans le banc ---
    "Météo (comportement du banc) : investir(veille, ctx) décide le soir de la veille si l'on peut acheter le jour de bourse "
    "suivant (le jour d'entrée). Le 1er jour de la période, le banc n'achète rien (pas encore de veille).",
    "Fenêtre fermée le jour d'entrée : le banc laisse passer l'événement s'il a un prix ce jour-là ; sans prix, il attend "
    "(5 jours de bourse au plus) et c'est la fenêtre du jour où il y a un prix qui compte (ce jour-là est le jour "
    "d'entrée).",
    # --- La fenêtre ---
    "Jours de bourse : ceux du calendrier du banc. Baisse d'un jour = clôture SPY de ce jour / plus haute clôture SPY des "
    "252 jours de bourse finissant ce jour (compris) − 1. Jours sans prix SPY : sautés. Au début des données (moins de 252 "
    "jours de bourse d'historique) : la plus haute des clôtures disponibles.",
    "Fenêtre du jour d'entrée : ouverte si une baisse de -10 % ou pire (baisse <= -0,10) a eu lieu dans les 126 jours de "
    "bourse finissant le jour d'entrée (compris). Le banc décide la veille au soir : la baisse du jour d'entrée lui-même "
    "n'est pas encore connue ; on regarde donc les 125 autres jours de cette fenêtre (jusqu'à la veille). Si la toute 1re "
    "baisse de -10 % tombe le jour d'entrée, la fenêtre s'ouvre donc un jour plus tard que dans le texte.",
    "SPY : pas de contrôle de changement de CUSIP (aucun regroupement d'actions attendu pour ce fonds).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : écart corrigé dans le fichier du TESTEUR ; rien ne change ici. Le "
    "testeur prenait la fenêtre de la veille (126 jours finissant à la veille) et achetait encore le 126e jour de bourse "
    "après la dernière baisse ; ce fichier suit le filtre (« 126 jours de bourse précédents (jour compris) » appliqué au "
    "jour d'entrée, dont on ne connaît que les 125 jours jusqu'à la veille). Les paramètres fixes (« reste ouverte "
    "126 jours de bourse après le dernier jour sous ce seuil ») ne font que résumer ce 126 ; le filtre l'emporte.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0

SEUIL = -0.10
JOURS_HAUT = 252
JOURS_FENETRE = 126


# --------------------------------------------------------------------------------------------------- le panier
def _panier(e):
    """Achat P ; un déclarant administrateur ou dirigeant ; non routinier ; plan 10b5-1 pas « oui » ;
    montant >= 100 000 $ ; valeur_m >= 100 M$."""
    if e.get("sens") != "achat":
        return False
    if not any(r in ("administrateur", "dirigeant") for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant, valeur = e.get("montant"), e.get("valeur_m")
    return montant is not None and montant >= 100_000 and valeur is not None and valeur >= 100


def garder(e, ctx):
    return _panier(e)


def priorite(e, ctx):
    return e.get("montant") or 0.0


# ---------------------------------------------------------------------------------------------- la fenêtre
# Cache de calculs qui ne dépendent que du passé : la baisse d'un jour n'utilise que les clôtures SPY jusqu'à ce jour.
_BAISSE = {}


def _baisse(k, jours, spy):
    """Baisse du jour jours[k] sous la plus haute clôture des 252 jours de bourse finissant ce jour (None sans prix)."""
    p = spy.get(jours[k])
    if p is None:
        return None
    haut = max(spy[j] for j in jours[max(0, k - JOURS_HAUT + 1):k + 1] if j in spy)
    return p / haut - 1


def investir(veille, ctx):
    """Fenêtre ouverte le jour d'entrée (le jour de bourse après `veille`) ? Seuls les 125 jours de sa fenêtre qui vont
    jusqu'à la veille sont connus."""
    depuis = (date.fromisoformat(veille) - timedelta(days=800)).isoformat()  # ≈ 550 jours de bourse : assez pour 125 + 252
    jours = ctx.jours_de_bourse(depuis)
    n = len(jours)
    debut = max(0, n - (JOURS_FENETRE - 1))
    if any(jours[k] not in _BAISSE for k in range(debut, n)):
        spy = {j: p for j, p, _cusip in ctx.clotures("SPY", depuis)}
        for k in range(debut, n):
            if jours[k] not in _BAISSE:
                _BAISSE[jours[k]] = _baisse(k, jours, spy)
    return any(b is not None and b <= SEUIL for b in (_BAISSE[jours[k]] for k in range(debut, n)))
