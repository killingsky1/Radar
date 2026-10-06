"""meteo-1 — Baromètre des initiés : suivre les achats seulement quand les initiés achètent plus que d'habitude.

Programmée par le VÉRIFICATEUR, d'après labo/tournoi/regles_preenregistrees.json, sans voir labo/tournoi/regles/.
- Baromètre (dernier jour de bourse F de chaque mois) : événements déposés dans les 91 jours civils finissant à F, avec
  valeur_m >= 100 M$ et routinier = non. A = paires (initié, compagnie) avec un achat, V = paires avec une vente,
  R = A / (A + V). ALLUMÉ tout le mois suivant si R > médiane des R des 24 fins de mois précédentes (au moins 6).
- Panier : achat P d'un administrateur ou dirigeant, non routinier, pas de plan 10b5-1 « oui », montant >= 100 000 $,
  valeur_m >= 100 M$. Entrée seulement si le signal est allumé le jour d'entrée. Garde de 126 jours de bourse.
"""
from datetime import date, timedelta
from statistics import median

ID = "meteo-1"

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
    "signal s'est éteint) et TOLERANCE_SORTIE = 20 (aucun prix pendant les 20 jours de bourse après cette date : la "
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
    "Signal éteint le jour d'entrée : le banc laisse passer l'événement s'il a un prix ce jour-là ; sans prix, il attend "
    "(5 jours de bourse au plus) et c'est la météo du jour où il y a un prix qui compte (ce jour-là est le jour d'entrée).",
    "Fin de mois = le dernier jour du calendrier du banc dans ce mois. Le signal qui vaut pour le jour d'entrée est celui "
    "calculé à la fin du mois PRÉCÉDANT le mois du jour d'entrée (le 1er jour de bourse d'un mois utilise donc le "
    "baromètre calculé la veille, dernier jour de bourse du mois d'avant).",
    "ctx ne montre pas les jours de bourse à venir : pour savoir si la veille est le dernier jour de bourse de son mois, la "
    "règle calcule le prochain jour de bourse = le prochain jour de semaine qui n'est pas un congé de la Bourse de New York "
    "(calendrier public connu d'avance : jour de l'An, Martin Luther King, Presidents' Day, Vendredi saint, Memorial Day, "
    "Juneteenth dès 2022, 4 juillet, fête du Travail, Thanksgiving, Noël). Les fermetures exceptionnelles (deuils "
    "nationaux) ne sont pas comptées : aucune ne tombe un dernier jour de mois.",
    # --- Le baromètre ---
    "Baromètre au jour F : événements DÉPOSÉS du jour F − 90 au jour F compris (91 jours civils), achats ET ventes de "
    "toutes les compagnies (ctx.evenements_marche), avec valeur_m >= 100 et routinier = non ; valeur_m inconnue : exclu. "
    "Pas de filtre de rôle, de montant ni de plan 10b5-1 dans le baromètre (le texte n'en met pas).",
    "Paires : chaque déclarant d'un formulaire fait une paire (cik de l'initié, cik de la compagnie). A = paires avec au "
    "moins un achat ; V = paires avec au moins une vente (une paire peut compter dans les deux). R = A / (A + V).",
    "Une valeur de R n'est « disponible » que si les données couvrent ses 91 jours en entier (1er dépôt des données au plus "
    "tard le jour F − 90) et si A + V > 0. Raison : les chercheurs attendaient un 1er signal vers octobre 2016 avec des "
    "données commençant en janvier 2016, ce qui suppose des fenêtres complètes.",
    "Médiane : celle des valeurs disponibles aux fins des 24 mois civils précédents (le mois du calcul exclu) ; nombre pair "
    "de valeurs : moyenne des deux du milieu. Moins de 6 valeurs, ou R du mois non disponible : ÉTEINT. ALLUMÉ si R est "
    "strictement plus grand que la médiane.",
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


# --------------------------------------------------------------------------------------------- le baromètre
# Caches de calculs qui ne dépendent que du passé (une valeur de R à la fin de mois F n'utilise que les dépôts <= F).
_R = {}
_SIGNAL = {}
_PREMIER_DEPOT = []


def _premier_depot(ctx):
    """La date du 1er dépôt des données (pour savoir si une fenêtre de 91 jours est couverte en entier)."""
    if not _PREMIER_DEPOT:
        tous = ctx.evenements_marche("0000-00-00")
        if not tous:
            return None
        _PREMIER_DEPOT.append(tous[0]["depot"])
    return _PREMIER_DEPOT[0]


def _barometre(fin, ctx):
    """R = A / (A + V) à la fin de mois `fin`, ou None s'il n'est pas disponible."""
    if fin not in _R:
        debut = (date.fromisoformat(fin) - timedelta(days=90)).isoformat()
        premier = _premier_depot(ctx)
        r = None
        if premier is not None and premier <= debut:
            achats, ventes = set(), set()
            for e in ctx.evenements_marche(debut):  # triés par date de dépôt
                if e["depot"] > fin:
                    break
                valeur = e.get("valeur_m")
                if e.get("routinier") or valeur is None or valeur < 100:
                    continue
                paires = {(i.get("cik"), e.get("cik")) for i in (e.get("inities") or [])}
                if e.get("sens") == "achat":
                    achats |= paires
                elif e.get("sens") == "vente":
                    ventes |= paires
            n = len(achats) + len(ventes)
            r = len(achats) / n if n else None
        _R[fin] = r
    return _R[fin]


def _signal(fin, ctx):
    """ALLUMÉ pour le mois qui suit `fin` ?"""
    if fin not in _SIGNAL:
        r = _barometre(fin, ctx)
        a, m = int(fin[:4]), int(fin[5:7]) - 24
        while m <= 0:
            a, m = a - 1, m + 12
        fins = {}  # les fins des 24 mois civils précédents (dernier jour du calendrier du banc dans chaque mois)
        for j in ctx.jours_de_bourse(f"{a:04d}-{m:02d}-01"):
            if j[:7] < fin[:7]:
                fins[j[:7]] = j
        valeurs = [x for x in (_barometre(f, ctx) for f in fins.values()) if x is not None]
        _SIGNAL[fin] = r is not None and len(valeurs) >= 6 and r > median(valeurs)
    return _SIGNAL[fin]


def investir(veille, ctx):
    fin = _fin_de_mois_du_signal(veille, ctx)
    return fin is not None and _signal(fin, ctx)
