"""vitesse-2 : achat d'initié loin sous le plus haut de 52 semaines, garder 3 séances.

Programmée telle qu'écrite dans regles_preenregistrees.json (piste « vitesse »), sans rien corriger ni améliorer.
Les choix faits pour les passages ambigus, et les endroits où le banc fait un peu autrement que le texte, sont dans
CHOIX ci-dessous.
"""
from datetime import date, timedelta

ID = "vitesse-2"

CHOIX = [
    "« Achat code P d'actions ordinaires » : un événement « achat » (code P) dont au moins un des titres déclarés "
    "(champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules (ex. « Common Stock », "
    "« Class A Common Stock », « Ordinary Shares »). Un titre sans ces mots (privilégiées, unités, « Shares » seul, "
    "etc.) est refusé.",
    "« Par un administrateur ou un dirigeant (pas un simple actionnaire de 10 %) » : au moins un des déclarants du "
    "formulaire a le rôle « administrateur » ou « dirigeant » (un actionnaire de 10 % qui est aussi administrateur ou "
    "dirigeant compte).",
    "« Montant ≥ 50 000 $ » : le montant du formulaire ; montant inconnu = refusé.",
    "« routinier = non » : le champ routinier doit être faux.",
    "« plan_10b5_1 ≠ oui » : refusé seulement si la case vaut « oui » (true) ; le vide (null) est accepté.",
    "« valeur_m entre 100 et 1 000 M$ » : bornes comprises ; valeur inconnue = refusé.",
    "« Plus haut » : la plus haute clôture SEC du symbole entre jour_premier − 365 jours et jour_premier − 1 jour "
    "(bornes comprises : les 365 jours civils qui finissent la veille du premier achat). Toutes les clôtures de cette "
    "période comptent, même si le CUSIP change (regroupement d'actions) : le texte ne parle pas de CUSIP.",
    "« Au moins 20 clôtures SEC dans cette période » : au moins 20 clôtures dans la même fenêtre, sinon signal "
    "abandonné. prix_moyen ou jour_premier inconnu = abandonné.",
    "Si la fenêtre finissait après le jour du dépôt (jour_premier plus d'un jour après le dépôt : déclaration "
    "incohérente), il faudrait des prix du futur : signal abandonné.",
    "« Rapport prix_moyen ÷ plus haut ≤ 0,60 » : borne comprise ; prix_moyen = celui du formulaire (lignes avec un prix).",
    "« Une seule entrée par symbole sur 30 jours civils » : réglage du banc UNE_ENTREE_PAR_SYMBOLE_JOURS = 30 (aucun "
    "nouvel achat du symbole moins de 30 jours civils après un ACHAT fait ; un signal pas acheté ne bloque rien).",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt (JOURS_ENTREE = 1) ; pas de prix ce jour-là = signal "
    "abandonné (TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 2e jour de bourse après le jour d'achat (DUREE = 2, donc la 3e séance après le dépôt). Pas de "
    "prix ce jour-là : le banc vend au 1er prix SEC des 10 jours de bourse suivants, sinon au dernier prix connu "
    "(TOLERANCE_SORTIE = 10, valeur standard du banc) : c'est ainsi que « la compagnie disparaît » est reconnu ; le "
    "texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc place la valeur du portefeuille ÷ 2 par position "
    "(5 000 $ au départ), pas exactement 5 000 $ fixes.",
    "Argent qui attend dans SPY (ARGENT_QUI_ATTEND = « SPY », LIQUIDE_JOURS = 0) : 10 $ pour vendre du SPY et 10 $ pour "
    "acheter l'action, puis 10 $ pour la vendre et 10 $ pour racheter du SPY (les 4 transactions du texte). Le banc "
    "compte aussi, comme pour toutes les règles, le demi-écart achat-vente selon la valeur en bourse.",
    "Une seule position par symbole et signaux sans place perdus : faits par le banc.",
    "« Si trop de signaux : priorité au rapport le plus bas » : priorite = − rapport ; à égalité, l'ordre du banc "
    "(dépôt, numéro).",
    "Montant minimal d'une position : MONTANT_MIN = 50 $ (valeur standard du banc, le texte n'en parle pas).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus "
    "(« common » ou « ordinary »). Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 0
DUREE = 2
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 30
TOLERANCE_SORTIE = 10
MONTANT_MIN = 50

# Seuils du texte
ROLES = ("administrateur", "dirigeant")
MONTANT_SEUIL = 50_000
VALEUR_MIN, VALEUR_MAX = 100, 1000
RAPPORT_MAX = 0.60
FENETRE_JOURS = 365
CLOTURES_MIN = 20


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _administrateur_ou_dirigeant(e):
    return any(r in ROLES for i in e.get("inities") or [] for r in i.get("roles") or [])


def _rapport(e, ctx):
    """prix_moyen ÷ la plus haute clôture SEC des 365 jours civils qui finissent la veille de jour_premier (None si
    impossible à calculer : données manquantes ou moins de 20 clôtures)."""
    premier, prix, s = e.get("jour_premier"), e.get("prix_moyen"), e.get("symbole")
    if not premier or not prix or not s:
        return None
    j = date.fromisoformat(premier)
    debut, fin = (j - timedelta(days=FENETRE_JOURS)).isoformat(), (j - timedelta(days=1)).isoformat()
    if fin > ctx.jour:  # la fenêtre irait après le dépôt : prix du futur
        return None
    clotures = ctx.clotures(s, debut, fin)
    if len(clotures) < CLOTURES_MIN:
        return None
    haut = max(p for _, p, _ in clotures)
    return prix / haut if haut and haut > 0 else None


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e) or not _administrateur_ou_dirigeant(e):
        return False
    m = e.get("montant")
    if m is None or m < MONTANT_SEUIL:
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    v = e.get("valeur_m")
    if v is None or not (VALEUR_MIN <= v <= VALEUR_MAX):
        return False
    r = _rapport(e, ctx)
    return r is not None and r <= RAPPORT_MAX


def priorite(e, ctx):
    r = _rapport(e, ctx)
    return -r if r is not None else float("-inf")
