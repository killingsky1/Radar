"""vitesse-1 : gros achat non routinier du PDG ou du directeur financier, garder 5 jours de bourse.

Programmée par le VÉRIFICATEUR, sans voir le programme du testeur, d'après regles_preenregistrees.json (texte des
chercheurs : filtre, entrée, sortie, taille). Les choix faits quand le texte est ambigu, ou quand le banc fait autrement
que le texte, sont dans CHOIX.
"""

ID = "vitesse-1"
IMPOSSIBLE = None

CHOIX = [
    "« Achat en bourse (code P) d'actions ordinaires » : un événement « achat » (code P) dont au moins un des titres "
    "déclarés (champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules (ex. « Common "
    "Stock », « Class A Common Stock », « Ordinary Shares »). Un titre sans ces mots (privilégiées, unités, « Shares » "
    "seul, etc.) est refusé.",
    "Titre : au moins UN des déclarants du formulaire a un titre qui contient « CEO », « Chief Executive », « CFO » ou "
    "« Chief Financial », sans tenir compte des majuscules, n'importe où dans le texte (ex. « Co-CEO » ou « Former "
    "CFO » comptent). Seul le titre est regardé : le rôle « dirigeant » n'est pas exigé en plus.",
    "Montant ≥ 100 000 $ : le montant de CHAQUE formulaire (« montant total du formulaire »), pas la somme des "
    "formulaires du même jour. Montant inconnu = écarté.",
    "routinier = non : routinier faux. plan_10b5_1 différent de « oui » : vrai = écarté ; faux et vide acceptés, à "
    "toutes les dates (« vide accepté avant avril 2023 » est lu comme une explication, pas comme un refus des vides "
    "après avril 2023 ; les paramètres fixes disent seulement « plan_10b5_1 ≠ oui »).",
    "valeur_m entre 100 et 3 000 M$ : bornes comprises. Valeur inconnue = écarté.",
    "« Au plus 2 jours de bourse entre jour_dernier_achat et depot » : on compte les jours de bourse APRÈS jour_dernier "
    "jusqu'au jour du dépôt compris (calendrier du jeu) ; il en faut 2 au plus (achat lundi, dépôt mercredi = 2 : "
    "gardé ; dépôt jeudi = 3 : écarté). jour_dernier inconnu = écarté. jour_dernier après le dépôt (erreur de date) "
    "= 0 jour : gardé.",
    "Plusieurs formulaires de la même compagnie (même CIK) déposés le même jour : ceux qui remplissent TOUTES les "
    "conditions ci-dessus forment un seul signal. Le banc achète celui qui vient en premier dans son ordre (dépôt, puis "
    "numéro) ; les autres sont écartés. Le montant du signal (pour la priorité) = la somme de leurs montants.",
    "Priorité : le plus gros montant (la somme ci-dessus) ; à égalité, l'ordre du banc (dépôt, puis numéro).",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt ; pas de prix ce jour-là = pas d'achat "
    "(TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 5e jour de bourse après l'entrée (DUREE = 5). Pas de prix ce jour-là : le banc prend la 1re "
    "clôture des 10 jours de bourse suivants, sinon la dernière clôture connue (compagnie « disparue ») : réglage "
    "standard du banc (TOLERANCE_SORTIE = 10), le texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc met la valeur du portefeuille ÷ 2 dans chaque position "
    "(5 000 $ au départ, puis selon la valeur du portefeuille), pas 5 000 $ fixes.",
    "Argent en attente dans SPY, sans garder de liquide (LIQUIDE_JOURS = 0) : 4 transactions de 10 $ par aller-retour. "
    "Le banc compte aussi le demi-écart achat-vente selon la valeur en bourse, comme pour toutes les règles.",
    "« Pas de position déjà ouverte sur ce symbole » et « signaux sans place abandonnés » : faits par le banc (une seule "
    "position par symbole ; un signal sans place n'est pas gardé pour plus tard). Aucune autre pause par symbole "
    "(UNE_ENTREE_PAR_SYMBOLE_JOURS = 0).",
    "Formulaire sans symbole : jamais gardé (le banc ne peut pas l'acheter).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus "
    "(« common » ou « ordinary »). Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
]

JOURS_ENTREE = 1
DUREE = 5
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
TOLERANCE_ENTREE = 0
TOLERANCE_SORTIE = 10
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

MOTS_DU_TITRE = ("ceo", "chief executive", "cfo", "chief financial")
MONTANT_MINIMUM = 100_000
VALEUR_MIN, VALEUR_MAX = 100, 3000
DELAI_MAX = 2  # jours de bourse entre la dernière transaction et le dépôt


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _titre_ok(e):
    for i in e.get("inities") or []:
        titre = (i.get("titre") or "").lower()
        if any(mot in titre for mot in MOTS_DU_TITRE):
            return True
    return False


def _jours_de_bourse_apres(jour, ctx):
    """Nombre de jours de bourse après `jour`, jusqu'au jour de la décision (le dépôt) compris."""
    return sum(1 for j in ctx.jours_de_bourse(jour) if j > jour)


def _remplit(e, ctx):
    """Toutes les conditions du filtre, pour UN formulaire (sans le regroupement du même jour)."""
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e) or not _titre_ok(e):
        return False
    montant = e.get("montant")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    valeur = e.get("valeur_m")
    if valeur is None or not (VALEUR_MIN <= valeur <= VALEUR_MAX):
        return False
    dernier = e.get("jour_dernier")
    if not dernier:
        return False
    return _jours_de_bourse_apres(dernier, ctx) <= DELAI_MAX


def _signal_du_jour(e, ctx):
    """Les formulaires de la même compagnie déposés le même jour qui remplissent tout, dans l'ordre du banc."""
    return [x for x in ctx.evenements_avant(e["cik"], e["depot"])
            if x["depot"] == e["depot"] and _remplit(x, ctx)]


def garder(e, ctx):
    if not _remplit(e, ctx):
        return False
    meme_jour = _signal_du_jour(e, ctx)
    return bool(meme_jour) and meme_jour[0]["id"] == e["id"]


def priorite(e, ctx):
    return sum(x["montant"] for x in _signal_du_jour(e, ctx))
