"""vitesse-1 : gros achat non routinier du PDG ou du directeur financier, garder 5 jours.

Programmée telle qu'écrite dans regles_preenregistrees.json (piste « vitesse »), sans rien corriger ni améliorer.
Les choix faits pour les passages ambigus, et les endroits où le banc fait un peu autrement que le texte, sont dans
CHOIX ci-dessous.
"""
from datetime import date

ID = "vitesse-1"

CHOIX = [
    "« Achat en bourse (code P) d'actions ordinaires » : un événement « achat » (code P) dont au moins un des titres "
    "déclarés (champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules (ex. « Common "
    "Stock », « Class A Common Stock », « Ordinary Shares »). Un titre sans ces mots (privilégiées, unités, « Shares » "
    "seul, etc.) est refusé.",
    "« Le titre du dirigeant contient CEO, Chief Executive, CFO ou Chief Financial » : au moins un des déclarants du "
    "formulaire a un titre (champ titre) qui contient un de ces 4 textes, sans tenir compte des majuscules (simple "
    "recherche de texte, ex. « EVP, CFO » ou « Former CEO » comptent) ; le rôle coché n'est pas vérifié en plus.",
    "« Montant total du formulaire ≥ 100 000 $ » : le montant de CHAQUE formulaire, seul (pas la somme des formulaires "
    "du même jour). Montant inconnu = refusé.",
    "« Plusieurs formulaires de la même compagnie le même jour = un seul signal (montants additionnés) » : parmi les "
    "formulaires de la même compagnie (même cik) déposés le même jour qui passent TOUS les filtres, seul le premier "
    "dans l'ordre du banc (dépôt, numéro) est gardé ; sa priorité est la somme de leurs montants. Les formulaires du "
    "même jour qui ne passent pas les filtres ne sont pas additionnés.",
    "« routinier = non » : le champ routinier doit être faux.",
    "« plan_10b5_1 différent de oui (vide accepté avant avril 2023) » : refusé seulement si la case vaut « oui » (true). "
    "Le vide (null) est accepté à toute date, aussi après avril 2023 : la condition écrite est « différent de oui » "
    "(paramètres fixes : « plan_10b5_1 ≠ oui ») ; la parenthèse est lue comme une précision, pas comme un refus du vide.",
    "« valeur_m entre 100 et 3 000 M$ » : bornes comprises ; valeur inconnue = refusé.",
    "« Au plus 2 jours de bourse entre jour_dernier_achat et depot » : on compte les jours de bourse du calendrier du "
    "banc (calendrier.json) APRÈS jour_dernier jusqu'au jour du dépôt compris ; il en faut 2 au plus (le dépôt est fait "
    "au plus tard le 2e jour de bourse après le dernier achat, comme le délai légal ; ex. achat un lundi, dépôt le "
    "mercredi au plus tard). jour_dernier inconnu = refusé. Garde-fou technique : "
    "plus de 14 jours civils d'écart = refusé d'office (au cas où le calendrier ne couvrirait pas la date). Un "
    "jour_dernier après le dépôt (déclaration incohérente) donne 0 jour : accepté.",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt (JOURS_ENTREE = 1) ; pas de prix ce jour-là = signal "
    "abandonné (TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 5e jour de bourse après le jour d'achat (DUREE = 5). Pas de prix ce jour-là : le banc vend au "
    "1er prix SEC des 10 jours de bourse suivants, sinon au dernier prix connu (TOLERANCE_SORTIE = 10, valeur standard "
    "du banc) : c'est ainsi que « la compagnie disparaît » est reconnu ; le texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc place la valeur du portefeuille ÷ 2 par position "
    "(5 000 $ au départ), pas exactement 5 000 $ fixes.",
    "Argent qui attend dans SPY (ARGENT_QUI_ATTEND = « SPY », LIQUIDE_JOURS = 0) : 10 $ pour vendre du SPY et 10 $ pour "
    "acheter l'action, puis 10 $ pour la vendre et 10 $ pour racheter du SPY (les 4 transactions du texte). Le banc "
    "compte aussi, comme pour toutes les règles, le demi-écart achat-vente selon la valeur en bourse.",
    "« Pas de position déjà ouverte sur ce symbole » et « les signaux sans place sont abandonnés » : faits par le banc "
    "(une seule position par symbole ; places pleines = signal perdu, pas d'achat plus tard).",
    "« Priorité au plus gros montant » : priorite = montant du signal (la somme du choix ci-dessus) ; à égalité, "
    "l'ordre du banc (dépôt, numéro).",
    "Montant minimal d'une position : MONTANT_MIN = 50 $ (valeur standard du banc, le texte n'en parle pas).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus "
    "(« common » ou « ordinary »). Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 0
DUREE = 5
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0
TOLERANCE_SORTIE = 10
MONTANT_MIN = 50

# Seuils du texte
MOTS_TITRE = ("ceo", "chief executive", "cfo", "chief financial")
MONTANT_SEUIL = 100_000
VALEUR_MIN, VALEUR_MAX = 100, 3000
JOURS_DE_BOURSE_MAX = 2
GARDE_FOU_JOURS_CIVILS = 14


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _titre_pdg_ou_dfo(e):
    return any(any(m in (i.get("titre") or "").lower() for m in MOTS_TITRE) for i in e.get("inities") or [])


def _depot_a_temps(e, ctx):
    dernier, depot = e.get("jour_dernier"), e["depot"]
    if not dernier:
        return False
    if (date.fromisoformat(depot) - date.fromisoformat(dernier)).days > GARDE_FOU_JOURS_CIVILS:
        return False
    if dernier > depot:  # déclaration incohérente : 0 jour de bourse entre les deux
        return True
    jours = [j for j in ctx.jours_de_bourse(dernier) if j > dernier]  # jours de bourse de ]dernier, dépôt]
    return len(jours) <= JOURS_DE_BOURSE_MAX


def _passe_filtres(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e) or not _titre_pdg_ou_dfo(e):
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
    return _depot_a_temps(e, ctx)


def _formulaires_du_jour(e, ctx):
    """Les formulaires de la même compagnie déposés le même jour qui passent tous les filtres (ordre : dépôt, numéro)."""
    return [x for x in ctx.evenements_avant(e["cik"], e["depot"]) if x["depot"] == e["depot"] and _passe_filtres(x, ctx)]


def garder(e, ctx):
    if not _passe_filtres(e, ctx):
        return False
    memes = _formulaires_du_jour(e, ctx)
    return bool(memes) and memes[0]["id"] == e["id"]


def priorite(e, ctx):
    return sum(x["montant"] for x in _formulaires_du_jour(e, ctx))
