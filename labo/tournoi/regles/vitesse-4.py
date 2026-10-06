"""vitesse-4 : initié qui augmente fortement sa participation, garder 10 jours.

Programmée telle qu'écrite dans regles_preenregistrees.json (piste « vitesse »), sans rien corriger ni améliorer.
Les choix faits pour les passages ambigus, et les endroits où le banc fait un peu autrement que le texte, sont dans
CHOIX ci-dessous.
"""

ID = "vitesse-4"

CHOIX = [
    "« Achat code P d'actions ordinaires » : un événement « achat » (code P) dont au moins un des titres déclarés "
    "(champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules (ex. « Common Stock », "
    "« Class A Common Stock », « Ordinary Shares »). Un titre sans ces mots (privilégiées, unités, « Shares » seul, "
    "etc.) est refusé.",
    "« Par un dirigeant ou un administrateur » : au moins un des déclarants du formulaire a le rôle « dirigeant » ou "
    "« administrateur ».",
    "« direct = oui » : le champ direct est vrai (au moins une ligne d'achat détenue directement), tel quel.",
    "« part_ajoutee ≥ 0,25 » : le champ part (actions achetées ÷ détenues avant, dans le plus gros groupe de lignes), "
    "borne comprise ; part inconnue (0 action avant, ou déclaration incohérente) = refusé, comme le dit la note de "
    "testabilité.",
    "« Montant ≥ 50 000 $ » : le montant du formulaire ; montant inconnu = refusé.",
    "« routinier = non » : le champ routinier doit être faux.",
    "« plan_10b5_1 ≠ oui » : refusé seulement si la case vaut « oui » (true) ; le vide (null) est accepté.",
    "« valeur_m entre 100 et 2 000 M$ » : bornes comprises ; valeur inconnue = refusé.",
    "« Une seule entrée par symbole sur 30 jours civils » : réglage du banc UNE_ENTREE_PAR_SYMBOLE_JOURS = 30 (aucun "
    "nouvel achat du symbole moins de 30 jours civils après un ACHAT fait ; un signal pas acheté ne bloque rien).",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt (JOURS_ENTREE = 1) ; pas de prix ce jour-là = signal "
    "abandonné (TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 10e jour de bourse après le jour d'achat (DUREE = 10). Pas de prix ce jour-là : le banc vend "
    "au 1er prix SEC des 10 jours de bourse suivants, sinon au dernier prix connu (TOLERANCE_SORTIE = 10, valeur "
    "standard du banc) : c'est ainsi que « la compagnie disparaît » est reconnu ; le texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc place la valeur du portefeuille ÷ 2 par position "
    "(5 000 $ au départ), pas exactement 5 000 $ fixes.",
    "Argent qui attend dans SPY (ARGENT_QUI_ATTEND = « SPY », LIQUIDE_JOURS = 0) : 4 transactions de 10 $ par "
    "aller-retour (vendre du SPY, acheter l'action, la vendre, racheter du SPY). Le banc compte aussi, comme pour "
    "toutes les règles, le demi-écart achat-vente selon la valeur en bourse.",
    "Une seule position par symbole et signaux sans place perdus : faits par le banc.",
    "« Si trop de signaux : priorité à la plus forte part_ajoutee » : priorite = part ; à égalité, l'ordre du banc "
    "(dépôt, numéro).",
    "Montant minimal d'une position : MONTANT_MIN = 50 $ (valeur standard du banc, le texte n'en parle pas).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus "
    "(« common » ou « ordinary »). Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 0
DUREE = 10
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 30
TOLERANCE_SORTIE = 10
MONTANT_MIN = 50

# Seuils du texte
ROLES = ("dirigeant", "administrateur")
PART_MIN = 0.25
MONTANT_SEUIL = 50_000
VALEUR_MIN, VALEUR_MAX = 100, 2000


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _dirigeant_ou_administrateur(e):
    return any(r in ROLES for i in e.get("inities") or [] for r in i.get("roles") or [])


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e) or not _dirigeant_ou_administrateur(e):
        return False
    if e.get("direct") is not True:
        return False
    p = e.get("part")
    if p is None or p < PART_MIN:
        return False
    m = e.get("montant")
    if m is None or m < MONTANT_SEUIL:
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    v = e.get("valeur_m")
    return v is not None and VALEUR_MIN <= v <= VALEUR_MAX


def priorite(e, ctx):
    return e.get("part") or 0.0
