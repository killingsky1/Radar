"""meteo-1 : baromètre des initiés (règle pré-enregistrée, piste « meteo »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- BAROMÈTRE, calculé le dernier jour de bourse de chaque mois : tous les événements déposés dans les 91 jours de
  calendrier qui finissent ce jour-là, avec valeur_m >= 100 M$ et routinier = non. A = paires différentes
  (initie_cik, cik_emetteur) avec au moins un achat P ; V = paires différentes avec au moins une vente S ;
  R = A / (A + V). ALLUMÉ pour tout le mois suivant si R est strictement plus grand que la médiane des R des 24 fins
  de mois précédentes (moins de 24 : toutes celles disponibles, au moins 6 ; sinon ÉTEINT). plan_10b5_1 pas utilisé.
- PANIER : achat P ; roles contient administrateur ou dirigeant ; routinier = non ; plan_10b5_1 différent de « oui »
  (vide accepté) ; montant >= 100 000 $ ; valeur_m >= 100 M$ ; on ne possède pas déjà cette compagnie.
- Entrée : seulement si le signal est ALLUMÉ le jour d'entrée ; clôture SEC du 1er jour de bourse après le dépôt,
  sinon la 1re clôture des 5 jours de bourse suivants, sinon on laisse passer. Le même jour : plus gros montant d'abord.
- Sortie : 1re clôture SEC à partir du 126e jour de bourse après l'entrée, même si le signal s'éteint ; aucun prix
  dans les 20 jours de bourse après : dernière clôture connue.
- Taille : 10 cases de 10 % de la valeur du portefeuille ; pleines : on laisse passer ; le reste dans SPY (10 $ par
  transaction, SPY compris).
"""
from datetime import date, timedelta

ID = "meteo-1"
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
    "tôt (pas de sortir_avant), même si le signal s'éteint.",
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
    "les données jusqu'à ce jour-là. Le signal est vérifié pour le jour où l'achat se fait vraiment (jour du prix, "
    "même après des jours sans prix). Un signal qui arrive quand la météo est ÉTEINTE (avec un prix ce jour-là) est "
    "laissé, pas gardé pour plus tard.",
    "« ALLUMÉ pour tout le mois suivant » : un achat fait le jour J utilise le signal calculé au dernier jour de bourse "
    "du mois d'avant J (calendrier du banc). Le banc ne montre pas les jours à venir : on sait que J commence un "
    "nouveau mois si le jour de semaine (lundi à vendredi) qui suit la veille, sans compter le Vendredi saint ni le "
    "Memorial Day, est dans un autre mois ; la veille est alors le dernier jour de bourse de son mois, et le baromètre "
    "est calculé ce soir-là, avec les dépôts de ce jour. Ce sont les 2 seuls congés de la Bourse de New York qui "
    "peuvent tomber le dernier jour de semaine d'un mois (ex. Vendredi saint, 29 mars 2024 : le jeudi 28 est le "
    "dernier jour de bourse de mars).",
    "Dernier jour de bourse d'un mois passé : le dernier jour de ce mois dans le calendrier du banc.",
    "Baromètre d'une fin de mois J : les événements déposés du jour J − 90 au jour J compris (91 jours civils), "
    "achats ET ventes, tous les rôles, toutes les compagnies (contexte d'avant la période compris), avec valeur_m >= "
    "100 M$ (absente = exclu ; note : les dépôts d'avant les premiers prix de la SEC, juillet 2015, n'ont pas de "
    "valeur_m) et routinier = false. montant et plan_10b5_1 ne sont pas utilisés.",
    "Paires : une paire (cik de l'initié, cik de la compagnie) pour CHAQUE déclarant du formulaire. A = paires avec "
    "au moins un achat, V = paires avec au moins une vente (une paire peut compter dans les deux). R = A ÷ (A + V) ; "
    "A + V = 0 : pas de valeur ce mois-là.",
    "Valeurs disponibles : une fin de mois a une valeur seulement si ses 91 jours sont tous couverts par les données "
    "(1er jour de la fenêtre au plus tôt le jour du 1er dépôt du jeu de données). Ainsi, avec des données dès "
    "janvier 2016, la 1re valeur est fin mars 2016 et le 1er signal possible en octobre 2016, comme l'écrivent les "
    "chercheurs.",
    "Médiane : des valeurs disponibles parmi les 24 fins de mois de calendrier qui précèdent la fin de mois en cours "
    "(celle-ci exclue) ; nombre pair de valeurs : moyenne des deux du milieu. Moins de 6 valeurs, ou pas de valeur R "
    "pour la fin de mois en cours : ÉTEINT. ALLUMÉ si R > médiane (strictement).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : écart corrigé DANS CE FICHIER. Avant, le jour de bourse qui suit "
    "la veille était le jour de semaine suivant : la bourse étant fermée le Vendredi saint 29 mars 2024 (pas de "
    "règlement, donc pas dans le calendrier des fichiers d'échecs), l'achat du lundi 1er avril 2024 utilisait encore le "
    "signal de fin février, alors que le texte veut celui du dernier jour de bourse de mars (le jeudi 28) ; le "
    "vérificateur, qui saute les congés de la Bourse de New York, suivait le texte (jeu ciblé avec un calendrier sans "
    "congés : achats du 1er avril 2024 différents). Même cas au coffre-fort (Vendredi saint 30 mars 2018, Memorial Day "
    "31 mai 2021). Limite commune aux 2 programmes : dans un calendrier qui compte ces congés comme jours de bourse (le "
    "faux jeu), l'achat du 29 mars 2024 utilise déjà le signal calculé le 28.",
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
FENETRE_JOURS = 91  # jours civils du baromètre, jour de calcul compris
FINS_DE_MOIS = 24  # médiane des 24 fins de mois précédentes
VALEURS_MINIMUM = 6


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


# ---------- Le baromètre ----------
# Caches de calculs : chaque valeur ne dépend que des données jusqu'à sa propre date (jamais plus récentes).
_R = {}  # dernier jour de bourse d'un mois → R (None : pas de valeur)
_SIGNAL = {}  # dernier jour de bourse d'un mois → signal du mois suivant (True = ALLUMÉ)
_PREMIER_DEPOT = []  # date du 1er dépôt du jeu de données


def _conges_fin_de_mois(a):
    """Vendredi saint et Memorial Day (dernier lundi de mai) : les seuls congés de la Bourse de New York qui peuvent
    tomber le dernier jour de semaine d'un mois (les autres ne changent jamais le mois du jour de bourse suivant)."""
    g, c = a % 19, a // 100  # dimanche de Pâques (calendrier grégorien)
    h = (c - c // 4 - (8 * c + 13) // 25 + 19 * g + 15) % 30
    i = h - (h // 28) * (1 - (29 // (h + 1)) * ((21 - g) // 11))
    j = (a + a // 4 + i + 2 - c + c // 4) % 7
    m = 3 + (i - j + 40) // 44
    fin_mai = date(a, 5, 31)
    return {date(a, m, i - j + 28 - 31 * (m // 4)) - timedelta(days=2), fin_mai - timedelta(days=fin_mai.weekday())}


def _jour_de_bourse_suivant(jour):
    d = date.fromisoformat(jour) + timedelta(days=1)
    while d.weekday() >= 5 or d in _conges_fin_de_mois(d.year):
        d += timedelta(days=1)
    return d.isoformat()


def _mois_avant(mois, k):
    """« AAAA-MM » moins k mois."""
    t = int(mois[:4]) * 12 + int(mois[5:7]) - 1 - k
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def _derniers_jours(ctx, depuis):
    """{« AAAA-MM » : dernier jour de bourse de ce mois} d'après le calendrier du banc, jusqu'à ctx.jour."""
    fins = {}
    for j in ctx.jours_de_bourse(depuis):
        fins[j[:7]] = j
    return fins


def _premier_depot(ctx):
    if not _PREMIER_DEPOT:
        evs = ctx.evenements_marche("0000-00-00")
        if not evs:
            return None
        _PREMIER_DEPOT.append(evs[0]["depot"])
    return _PREMIER_DEPOT[0]


def _mediane(valeurs):
    v = sorted(valeurs)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def _ratio(fin, ctx):
    """R au dernier jour de bourse `fin` : dépôts du jour fin − 90 au jour fin (91 jours civils)."""
    if fin in _R:
        return _R[fin]
    debut = (date.fromisoformat(fin) - timedelta(days=FENETRE_JOURS - 1)).isoformat()
    premier = _premier_depot(ctx)
    valeur = None
    if premier is not None and debut >= premier:  # fenêtre entièrement couverte par les données
        achats, ventes = set(), set()
        for e in ctx.evenements_marche(debut):  # dans l'ordre des dépôts
            if e["depot"] > fin:
                break
            v = e.get("valeur_m")
            if v is None or v < VALEUR_MINIMUM or e.get("routinier") is not False:
                continue
            paires = {(i.get("cik"), e.get("cik")) for i in (e.get("inities") or [])}
            if e.get("sens") == "achat":
                achats |= paires
            elif e.get("sens") == "vente":
                ventes |= paires
        n = len(achats) + len(ventes)
        valeur = len(achats) / n if n else None
    _R[fin] = valeur
    return valeur


def _signal(fin, ctx):
    """Le signal calculé au dernier jour de bourse `fin`, qui vaut pour tout le mois suivant."""
    if fin in _SIGNAL:
        return _SIGNAL[fin]
    r = _ratio(fin, ctx)
    mois = [_mois_avant(fin[:7], k) for k in range(1, FINS_DE_MOIS + 1)]
    fins = _derniers_jours(ctx, mois[-1] + "-01")
    valeurs = []
    for m in mois:
        if m in fins:
            v = _ratio(fins[m], ctx)
            if v is not None:
                valeurs.append(v)
    allume = r is not None and len(valeurs) >= VALEURS_MINIMUM and r > _mediane(valeurs)
    _SIGNAL[fin] = allume
    return allume


def _fin_de_mois_du_signal(jour, ctx):
    """`jour` = la veille du jour d'achat. Le dernier jour de bourse du mois d'avant le jour d'achat."""
    if _jour_de_bourse_suivant(jour)[:7] != jour[:7]:
        return jour  # le jour d'achat commence un nouveau mois : la veille est le dernier jour de bourse de son mois
    debut_mois = jour[:7] + "-01"
    avant = [j for j in ctx.jours_de_bourse((date.fromisoformat(debut_mois) - timedelta(days=40)).isoformat())
             if j < debut_mois]
    return avant[-1] if avant else None


def investir(jour, ctx):
    fin = _fin_de_mois_du_signal(jour, ctx)
    return fin is not None and _signal(fin, ctx)
