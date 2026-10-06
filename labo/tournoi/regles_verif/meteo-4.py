"""meteo-4 — Saison froide : suivre les achats d'initiés de novembre à janvier, revendre fin avril, S&P 500 de mai à
octobre.

Programmée par le VÉRIFICATEUR, d'après labo/tournoi/regles_preenregistrees.json, sans voir labo/tournoi/regles/.
- Calendrier : nouvelles positions seulement si le jour d'entrée tombe entre le 1er jour de bourse de novembre et le
  dernier jour de bourse de janvier (inclusivement).
- Sortie : toutes les positions à la clôture SEC du dernier jour de bourse d'avril. De mai à octobre : 100 % SPY.
- Panier : achat P d'un administrateur ou dirigeant, non routinier, pas de plan 10b5-1 « oui », montant >= 100 000 $,
  valeur_m >= 100 M$.
"""
from datetime import date, timedelta

ID = "meteo-4"

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
    # --- Entrée, taille (réglages et comportement du banc) ---
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (clôture SEC du 1er jour de bourse après le dépôt ; sans prix, la "
    "1re clôture des 5 jours de bourse suivants ; sinon l'événement passe).",
    "Plusieurs événements le même jour : priorite = montant (le plus gros d'abord). Le banc classe ensemble les signaux du "
    "jour et ceux qui attendent encore un prix.",
    "Taille (comportement du banc) : 10 cases (MAX_POSITIONS = 10) ; le banc vise 10 % de la valeur du portefeuille à la "
    "clôture du JOUR d'achat (pas de la veille), les 10 $ de frais de l'achat pris dans ces 10 % ; s'il reste moins "
    "d'argent, il achète avec ce qui reste (pas d'achat sous 50 $ : MONTANT_MIN du banc).",
    "Argent qui attend : SPY ; l'argent d'une vente retourne dans SPY le jour même (ARGENT_QUI_ATTEND = 'SPY', "
    "LIQUIDE_JOURS = 0). Frais du banc : 10 $ par transaction, SPY compris, plus le demi-écart.",
    # --- La saison (météo dans le banc) ---
    "Météo (comportement du banc) : investir(veille, ctx) décide le soir de la veille si l'on peut acheter le jour de bourse "
    "suivant (le jour d'entrée). ctx ne montre pas les jours de bourse à venir : la règle calcule ce jour = le prochain jour "
    "de semaine qui n'est pas un congé de la Bourse de New York (calendrier public connu d'avance : jour de l'An, Martin "
    "Luther King, Presidents' Day, Vendredi saint, Memorial Day, Juneteenth dès 2022, 4 juillet, fête du Travail, "
    "Thanksgiving, Noël ; fermetures exceptionnelles non comptées).",
    "Période d'achat : le 1er jour de bourse après le dépôt (vérifié dans garder) ET le jour d'entrée (vérifié dans "
    "investir) tombent en novembre, décembre ou janvier (du 1er jour de bourse de novembre au dernier jour de bourse de "
    "janvier).",
    "Sans prix le 1er jour : le banc réessaie les 5 jours de bourse suivants et n'achète que si le jour où il y a un prix "
    "est encore dans la période ; c'est ce jour-là qui est le jour d'entrée (un événement dont le 1er jour tombe fin "
    "octobre est laissé, même s'il trouve un prix en novembre).",
    # --- La sortie ---
    "Sortie : sortir_avant vend chaque position à la clôture du dernier jour de bourse d'avril qui suit son entrée "
    "(le dernier jour de semaine d'avril qui n'est pas un congé de la Bourse de New York).",
    "Pas de prix ce jour-là : le banc ne peut pas vendre à un prix passé ; la règle ne prend donc PAS « la dernière clôture "
    "SEC disponible des 5 jours de bourse avant » : le banc vend à la 1re clôture SEC disponible après (la solution "
    "suivante du texte).",
    "Compagnie disparue (aucun prix après la fin d'avril) : le banc garde la position jusqu'à sa sortie prévue (DUREE = 129 "
    "jours de bourse après l'entrée), attend encore TOLERANCE_SORTIE = 21 jours de bourse (le texte ne donne pas de "
    "délai ; donc jusqu'au 150e jour de bourse après l'entrée, comme le testeur), puis prend la dernière clôture connue. "
    "Le « signalement » est laissé au labo.",
    "DUREE = 129 n'est qu'un filet de sécurité (le texte n'a pas de durée de garde fixe) : c'est le plus grand nombre de "
    "jours de bourse possible du 1er jour de bourse de novembre au dernier jour de bourse d'avril (tous les jours de semaine "
    "comptés), pour que la sortie prévue du banc ne tombe jamais avant la fin d'avril.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 2 écarts, corrigés DANS CE FICHIER selon le texte. 1) Entrée : le "
    "texte dit « clôture SEC du 1er jour de bourse après le dépôt, si ce jour tombe dans la période novembre-janvier » et, "
    "sans prix, « à condition qu'elle tombe ENCORE dans la période » : le 1er jour de bourse après le dépôt doit déjà être "
    "dans la période. Avant, ce fichier achetait le 1er novembre 2023 un dépôt du 30 octobre (1er jour, le 31 octobre, "
    "sans prix) ; le testeur le laissait, avec raison ; garder le vérifie maintenant. 2) Sans prix après la fin d'avril : "
    "le texte ne donne aucun délai (« sinon, la première clôture SEC disponible après » ; compagnie disparue : dernière "
    "clôture connue). Ce fichier abandonnait au 139e jour de bourse après l'entrée (129 + 10), le testeur au 150e ; on "
    "garde le plus long, plus proche de « la première clôture disponible après » (une compagnie qui retrouve un prix "
    "entre les deux n'avait pas disparu) : TOLERANCE_SORTIE = 21.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 129
TOLERANCE_SORTIE = 21  # sans prix après la fin d'avril : jusqu'au 150e jour de bourse après l'entrée (comparaison)
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0

MOIS_D_ACHAT = ("11", "12", "01")


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
    # le 1er jour de bourse après le dépôt doit déjà tomber de novembre à janvier (comparaison du 6 oct. 2026)
    return _panier(e) and _prochain_jour_de_bourse(e["depot"])[5:7] in MOIS_D_ACHAT


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


def _jour_de_bourse(d):
    return d.weekday() < 5 and d not in _conges(d.year)


def _prochain_jour_de_bourse(jour):
    d = date.fromisoformat(jour) + timedelta(days=1)
    while not _jour_de_bourse(d):
        d += timedelta(days=1)
    return d.isoformat()


def _dernier_jour_de_bourse_avril(a):
    d = date(a, 4, 30)
    while not _jour_de_bourse(d):
        d -= timedelta(days=1)
    return d.isoformat()


# ---------------------------------------------------------------------------------------------- la saison
def investir(veille, ctx):
    """Le jour d'entrée (le jour de bourse après `veille`) tombe-t-il de novembre à janvier ?"""
    return _prochain_jour_de_bourse(veille)[5:7] in MOIS_D_ACHAT


def sortir_avant(pos, veille, ctx):
    """Vendre au dernier jour de bourse d'avril qui suit l'entrée (ou à la 1re clôture après, s'il n'y a pas de prix)."""
    entree = pos["entree"][0]
    annee = int(entree[:4]) + (1 if int(entree[5:7]) > 4 else 0)
    return _prochain_jour_de_bourse(veille) >= _dernier_jour_de_bourse_avril(annee)
