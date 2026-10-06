"""meteo-3 — Petites en forme : suivre les achats d'initiés seulement quand le Russell 2000 bat le S&P 500 depuis 6 mois.

Programmée par le VÉRIFICATEUR, d'après labo/tournoi/regles_preenregistrees.json, sans voir labo/tournoi/regles/.
- Météo (dernier jour de bourse F de chaque mois) : M = rendement de IWM sur les 126 derniers jours de bourse − rendement
  de SPY sur la même période (clôtures, sans dividendes). ALLUMÉ pour tout le mois suivant si M > 0.
- Panier : achat P d'un administrateur ou dirigeant, non routinier, pas de plan 10b5-1 « oui », montant >= 100 000 $,
  valeur_m >= 100 M$. Entrée seulement si le signal est allumé. Garde de 126 jours de bourse.
"""
from datetime import date, timedelta

ID = "meteo-3"

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
    "Sortie : DUREE = 126 (le banc vend à la 1re clôture SEC à partir du 126e jour de bourse après l'entrée, même si le "
    "signal s'est éteint) et TOLERANCE_SORTIE = 20 (aucun prix pendant les 20 jours de bourse suivants : la dernière "
    "clôture connue). Le « signalement » d'une compagnie disparue est laissé au labo (la règle ne le fait pas).",
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
    "Signal éteint le jour d'entrée : le banc laisse passer l'événement s'il a un prix ce jour-là ; sans prix, il attend "
    "(5 jours de bourse au plus) et c'est la météo du jour où il y a un prix qui compte (ce jour-là est le jour d'entrée).",
    "Fin de mois = le dernier jour du calendrier du banc dans ce mois. Le signal qui vaut pour le jour d'entrée est celui "
    "calculé à la fin du mois PRÉCÉDANT le mois du jour d'entrée (le 1er jour de bourse d'un mois utilise donc le calcul "
    "fait la veille, dernier jour de bourse du mois d'avant).",
    "ctx ne montre pas les jours de bourse à venir : pour savoir si la veille est le dernier jour de bourse de son mois, la "
    "règle calcule le prochain jour de bourse = le prochain jour de semaine qui n'est pas un congé de la Bourse de New York "
    "(calendrier public connu d'avance : jour de l'An, Martin Luther King, Presidents' Day, Vendredi saint, Memorial Day, "
    "Juneteenth dès 2022, 4 juillet, fête du Travail, Thanksgiving, Noël). Les fermetures exceptionnelles (deuils "
    "nationaux) ne sont pas comptées : aucune ne tombe un dernier jour de mois.",
    # --- Le duel IWM contre SPY ---
    "M au jour F (fin de mois) = (clôture IWM du jour F / clôture IWM 126 jours de bourse plus tôt − 1) − (même calcul pour "
    "SPY) ; jours de bourse du calendrier du banc ; sans dividendes. Prix manquant l'un de ces jours : la dernière clôture "
    "connue avant (10 jours civils au plus). Moins de 126 jours de bourse d'historique, ou prix introuvable : ÉTEINT.",
    "ALLUMÉ si M > 0 (strictement) ; M = 0 : ÉTEINT.",
    "SPY et IWM : pas de contrôle de changement de CUSIP (aucun regroupement d'actions attendu pour ces fonds).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : écart corrigé dans le fichier du TESTEUR ; rien ne change ici. Le "
    "testeur prenait le jour de semaine suivant pour le jour de bourse suivant : la bourse étant fermée le Vendredi "
    "saint 29 mars 2024, l'achat du 1er avril 2024 utilisait encore le signal de fin février ; ce fichier (congés de la "
    "Bourse de New York) suit le texte, « dernier jour de bourse de chaque mois ». Limite commune : dans un calendrier "
    "qui compte ces congés comme jours de bourse (le faux jeu), l'achat du 29 mars 2024 utilise déjà le signal calculé "
    "le 28.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0

JOURS_DUEL = 126


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


# ------------------------------------------------------- le prochain jour de bourse (calendrier public de la NYSE)
def _paques(a):
    """Dimanche de Pâques (calendrier grégorien)."""
    g, c = a % 19, a // 100
    h = (c - c // 4 - (8 * c + 13) // 25 + 19 * g + 15) % 30
    i = h - (h // 28) * (1 - (29 // (h + 1)) * ((21 - g) // 11))
    j = (a + a // 4 + i + 2 - c + c // 4) % 7
    m = 3 + (i - j + 40) // 44
    return date(a, m, i - j + 28 - 31 * (m // 4))


def _nieme(a, mois, jour_semaine, n):
    """Le n-ième `jour_semaine` (0 = lundi) du mois ; n = -1 : le dernier."""
    if n > 0:
        d = date(a, mois, 1)
        return d + timedelta(days=(jour_semaine - d.weekday()) % 7 + 7 * (n - 1))
    d = date(a + (mois == 12), mois % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - jour_semaine) % 7)


def _observe(d):
    """Congé à date fixe : un samedi → le vendredi ; un dimanche → le lundi."""
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


_CONGES = {}  # année → congés de la NYSE (ne dépend que de l'année)


def _conges(a):
    if a not in _CONGES:
        j1 = date(a, 1, 1)  # jour de l'An un samedi : la NYSE ne ferme pas le vendredi 31 décembre
        f = {date(a, 1, 2)} if j1.weekday() == 6 else {j1} if j1.weekday() < 5 else set()
        f |= {_nieme(a, 1, 0, 3), _nieme(a, 2, 0, 3), _paques(a) - timedelta(days=2), _nieme(a, 5, 0, -1),
              _observe(date(a, 7, 4)), _nieme(a, 9, 0, 1), _nieme(a, 11, 3, 4), _observe(date(a, 12, 25))}
        if a >= 2022:
            f.add(_observe(date(a, 6, 19)))  # Juneteenth
        _CONGES[a] = f
    return _CONGES[a]


def _prochain_jour_de_bourse(jour):
    d = date.fromisoformat(jour) + timedelta(days=1)
    while d.weekday() >= 5 or d in _conges(d.year):
        d += timedelta(days=1)
    return d.isoformat()


def _fin_de_mois_du_signal(veille, ctx):
    """La fin de mois dont le signal vaut pour le jour d'entrée (le jour de bourse qui suit `veille`) : la veille si
    c'est le dernier jour de bourse de son mois, sinon le dernier jour de bourse (calendrier du banc) du mois d'avant."""
    if _prochain_jour_de_bourse(veille)[:7] != veille[:7]:
        return veille
    debut_mois = date.fromisoformat(veille[:8] + "01")
    mois_avant = (debut_mois - timedelta(days=1)).isoformat()[:7]
    jours = [j for j in ctx.jours_de_bourse((debut_mois - timedelta(days=40)).isoformat()) if j[:7] == mois_avant]
    return jours[-1] if jours else None


# ------------------------------------------------------------------------------------------ le duel IWM - SPY
# Cache de calculs qui ne dépendent que du passé : M à la fin de mois F n'utilise que les clôtures jusqu'à F.
_ECART = {}


def _ecart(fin, ctx):
    """M = rendement de IWM − rendement de SPY sur les 126 jours de bourse finissant à `fin` (None si incalculable)."""
    if fin not in _ECART:
        jours = [j for j in ctx.jours_de_bourse((date.fromisoformat(fin) - timedelta(days=400)).isoformat()) if j <= fin]
        m = None
        if len(jours) > JOURS_DUEL and jours[-1] == fin:
            avant = jours[-1 - JOURS_DUEL]
            iwm0, iwm1 = ctx.cloture("IWM", avant), ctx.cloture("IWM", fin)
            spy0, spy1 = ctx.cloture("SPY", avant), ctx.cloture("SPY", fin)
            if iwm0 and iwm1 and spy0 and spy1:
                m = (iwm1[1] / iwm0[1] - 1) - (spy1[1] / spy0[1] - 1)
        _ECART[fin] = m
    return _ECART[fin]


def investir(veille, ctx):
    fin = _fin_de_mois_du_signal(veille, ctx)
    if fin is None:
        return False
    m = _ecart(fin, ctx)
    return m is not None and m > 0
