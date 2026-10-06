"""meteo-5 : tendance des petites, suivre les achats d'initiés seulement quand le Russell 2000 est au-dessus de sa moyenne
de 10 mois (règle pré-enregistrée, piste « meteo » ; contre-épreuve de meteo-2).

Texte (labo/tournoi/regles_preenregistrees.json) :
- MÉTÉO, dernier jour de bourse de chaque mois : moyenne = moyenne des clôtures de IWM aux 10 dernières fins de mois
  (mois en cours compris). ALLUMÉ pour le mois suivant si la clôture de IWM ce jour-là est strictement au-dessus de la
  moyenne. Avant d'avoir 10 fins de mois de prix IWM : ÉTEINT.
- PANIER : achat P ; roles contient administrateur ou dirigeant ; routinier = non ; plan_10b5_1 différent de « oui »
  (vide accepté) ; montant >= 100 000 $ ; valeur_m >= 100 M$ ; on ne possède pas déjà cette compagnie.
- Entrée : seulement si le signal est ALLUMÉ ; clôture SEC du 1er jour de bourse après le dépôt, sinon la 1re clôture
  des 5 jours de bourse suivants, sinon on laisse passer. Le même jour : plus gros montant d'abord.
- Sortie : 1re clôture SEC à partir du 126e jour de bourse après l'entrée, même si le signal s'est éteint ; aucun prix
  dans les 20 jours de bourse suivants : dernière clôture connue.
- Taille : 10 cases de 10 % de la valeur du portefeuille ; pleines : on laisse passer ; le reste dans SPY (10 $ par
  transaction).
"""
from datetime import date, timedelta

ID = "meteo-5"
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
    "« ALLUMÉ pour le mois suivant » : un achat fait le jour J utilise le signal calculé au dernier jour de bourse du "
    "mois d'avant J (calendrier du banc). Le banc ne montre pas les jours à venir : on sait que J commence un nouveau "
    "mois si le jour de semaine (lundi à vendredi) qui suit la veille, sans compter le Vendredi saint ni le Memorial "
    "Day, est dans un autre mois ; la veille est alors le dernier jour de bourse de son mois, et le signal est calculé "
    "ce soir-là, avec la clôture de ce jour. Ce sont les 2 seuls congés de la Bourse de New York qui peuvent tomber le "
    "dernier jour de semaine d'un mois (ex. Vendredi saint, 29 mars 2024 : le jeudi 28 est le dernier jour de bourse "
    "de mars).",
    "Dernier jour de bourse d'un mois passé : le dernier jour de ce mois dans le calendrier du banc.",
    "Moyenne d'une fin de mois J : moyenne simple des clôtures IWM aux 10 dernières fins de mois (celle de J et celles "
    "des 9 mois de calendrier d'avant). Clôture d'une fin de mois : la dernière clôture IWM connue au plus tard ce "
    "jour-là (10 jours civils au plus, ctx.cloture). Il faut les 10 clôtures, sinon ÉTEINT. ALLUMÉ si la clôture de J "
    "est strictement au-dessus de la moyenne.",
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
FINS_DE_MOIS = 10  # moyenne des clôtures IWM aux 10 dernières fins de mois (mois en cours compris)


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


# ---------- La météo ----------
# Cache de calculs : le signal d'une fin de mois ne dépend que des clôtures jusqu'à cette fin de mois.
_SIGNAL = {}  # dernier jour de bourse d'un mois → signal du mois suivant (True = ALLUMÉ)


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


def _signal(fin, ctx):
    """Le signal calculé au dernier jour de bourse `fin`, qui vaut pour tout le mois suivant."""
    if fin in _SIGNAL:
        return _SIGNAL[fin]
    mois = [_mois_avant(fin[:7], k) for k in range(FINS_DE_MOIS)]  # le mois de `fin`, puis les 9 d'avant
    fins = _derniers_jours(ctx, mois[-1] + "-01")
    fins[fin[:7]] = fin
    prix = []
    for m in mois:
        c = ctx.cloture("IWM", fins[m]) if m in fins else None  # dernière clôture au plus tard ce jour-là
        if c is None:
            break
        prix.append(c[1])
    allume = len(prix) == FINS_DE_MOIS and prix[0] > sum(prix) / FINS_DE_MOIS
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
