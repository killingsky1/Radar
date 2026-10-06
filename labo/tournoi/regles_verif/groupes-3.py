"""groupes-3 (programmation du VÉRIFICATEUR) : premier 13D sur une compagnie de 100 M$ à 10 G$, garder 12 mois.

Programmée à partir du texte pré-enregistré seulement (regles_preenregistrees.json), sans voir celle du testeur.
"""
from datetime import date, timedelta

ID = "groupes-3"

IMPOSSIBLE = ("Le banc n'achète qu'au lendemain d'un formulaire 4 : garder() ne reçoit que les formulaires 4 "
              "(evenements.jsonl.gz) et l'achat se fait au 1er jour de bourse après LEUR dépôt. L'événement de cette "
              "règle est le dépôt d'un 13D initial (achat au lendemain du 13D) : seuls les 13D qui tombent, par hasard, "
              "le même jour qu'un formulaire 4 de la compagnie pourraient être achetés au bon jour. Ne garder que ces "
              "coïncidences ajoute une condition absente du texte (et liée au 13D : initiés qui déposent les deux) : "
              "ce serait une autre règle. Écartée telle qu'écrite, pas modifiée (regles_du_jeu.md, partie 1) ; "
              "testable seulement si le banc lisait aussi les 13D comme événements.")

CHOIX = [
    "CONCILIATION avec le testeur (6 octobre 2026) : le testeur avait écarté la règle (IMPOSSIBLE), cette programmation "
    "la testait avec un « porteur » (voir plus bas). Décision selon le texte et regles_du_jeu.md (partie 1 : les règles "
    "impossibles à tester sont écartées, avec la raison, pas modifiées) : ÉCARTÉE dans les deux fichiers. Le texte dit "
    "« Événement = dépôt 13D initial » et achète au lendemain du 13D ; avec le banc commun, seuls les 13D déposés le même "
    "jour qu'un formulaire 4 de la compagnie seraient achetés : une condition de plus, choisie par une coïncidence liée "
    "au 13D, donc une autre règle. garder() refuse donc tout ; le code « porteur » ci-dessous reste pour mémoire, il "
    "n'est plus appelé. (groupes-4 garde un porteur pour son cas 2 seulement : son cas 1, 13D puis achat d'initié, est "
    "complet.)",
    "LIMITE DU BANC (écart important avec le texte) : garder() ne reçoit que des formulaires 4, et le banc achète le "
    "symbole d'un formulaire 4. Le 13D est donc « porté » par le PREMIER formulaire 4 (achat ou vente, avec un symbole, "
    "dans l'ordre du banc) de la compagnie déposé le MÊME JOUR que le 13D : achat à la clôture du 1er jour de bourse après "
    "ce jour, comme le texte. Un 13D sans formulaire 4 de la compagnie ce jour-là ne peut pas être acheté : seule une "
    "partie des 13D est testée.",
    "13D initial = forme « 13D » du jeu (SC 13D ou SCHEDULE 13D, sans /A) ; le jeu distingue initial et amendement, donc "
    "pas de solution de repli. Les 13G sont ignorés. Le jeu ne dit pas qui dépose : tous les 13D initiaux comptent.",
    "Condition (1) : aucun « 13D » ni « 13D/A » sur la compagnie déposé du jour moins 365 jours civils jusqu'à la veille ; "
    "un autre 13D du même jour ne compte pas.",
    "Condition (2) : les actions en circulation XBRL avec leur date de fin de période ne sont pas dans les données "
    "(ctx.finances n'a pas ce concept). On prend donc la valeur_m d'un formulaire 4 des 30 derniers jours, comme le texte "
    "le permet : celle du formulaire porteur ; si elle est vide, la plus récente non vide des formulaires 4 de la "
    "compagnie déposés du jour moins 30 jours au jour même. Aucune : pas gardé. 100 M$ ≤ valeur ≤ 10 000 M$ (bornes "
    "comprises).",
    "Condition (3) : le symbole du formulaire porteur ; au moins une clôture de ce symbole dans les 10 jours de bourse "
    "avant le jour du 13D (ce jour exclu).",
    "Priorité (trop de signaux le même jour) : la plus petite valeur en bourse d'abord (priorité = − valeur). Le banc "
    "applique cet ordre à tous les signaux qui attendent un achat ce jour-là.",
    "Entrée : JOURS_ENTREE = 1 ; TOLERANCE_ENTREE = 5 (pas de prix le jour prévu : 1re clôture des 5 jours de bourse "
    "suivants, sinon pas d'achat).",
    "Sortie : DUREE = 252 jours de bourse après l'achat. Le texte ne dit pas combien de temps chercher un prix de vente : "
    "comportement du banc (TOLERANCE_SORTIE = 10) : 1re clôture des 10 jours de bourse suivants, sinon la dernière "
    "clôture connue (compagnie disparue : rachat, faillite, radiation).",
    "Taille (comportement du banc) : 10 places ; montant = valeur du portefeuille ÷ 10, frais de 10 $ pris dedans ; une "
    "position de moins de 50 $ n'est pas achetée (MONTANT_MIN).",
    "Argent en attente dans SPY (LIQUIDE_JOURS = 0), 10 $ par transaction SPY : comportement du banc.",
    "Une seule position par compagnie : le banc le fait par symbole ; un signal sur un symbole déjà en portefeuille est "
    "ignoré.",
    "Frais et calculs du banc que le texte ne précise pas : demi-écart achat-vente selon la valeur en bourse (en plus des 10 $ par "
    "transaction), à l'achat et à la vente ; rendement enchaîné si le CUSIP change pendant la détention.",
]

# Réglages du banc (texte : 10 positions de 10 %, entrée au 1er jour de bourse + 5 jours, 252 jours de bourse, SPY)
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

# Seuils du texte
SANS_13D_AVANT = 365  # jours civils
VALEUR_MIN_M, VALEUR_MAX_M = 100, 10_000  # M$
VALEUR_M_JOURS = 30  # valeur_m d'un formulaire 4 des 30 derniers jours
JOURS_PRIX_AVANT = 10  # jours de bourse

# Cache de CALCULS seulement (ne dépend que des dépôts faits au plus tard le jour du formulaire concerné)
_memo = {}  # id → (gardé ?, valeur en bourse)


def _moins(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _valeur_recente(cik, jour, ctx):
    """La valeur_m non vide la plus récente des formulaires 4 de la compagnie déposés du jour − 30 jours au jour."""
    v = None
    for x in ctx.evenements_avant(cik, _moins(jour, VALEUR_M_JOURS)):  # dans l'ordre (dépôt, numéro)
        if x["depot"] <= jour and x.get("valeur_m") is not None:
            v = x["valeur_m"]
    return v


def _calcul(e, ctx):
    k = e["id"]
    if k in _memo:
        return _memo[k]
    jour, cik = e["depot"], e["cik"]
    treize = [(j, f) for j, f in ctx.depots_13(cik, _moins(jour, SANS_13D_AVANT)) if j <= jour]
    if not e.get("symbole") or not any(j == jour and f == "13D" for j, f in treize):
        return (False, None)  # pas de 13D initial ce jour-là (test rapide, pas gardé en mémoire)
    r = (False, None)
    # Le porteur : le 1er formulaire 4 (avec symbole) de la compagnie déposé ce jour-là, dans l'ordre du banc
    porteur = next((x for x in ctx.evenements_avant(cik, jour) if x["depot"] == jour and x.get("symbole")), None)
    if porteur is not None and porteur["id"] == k:
        autre_avant = any(j < jour and f in ("13D", "13D/A") for j, f in treize)  # (1)
        if not autre_avant:
            v = e.get("valeur_m")
            if v is None:
                v = _valeur_recente(cik, jour, ctx)
            if v is not None and VALEUR_MIN_M <= v <= VALEUR_MAX_M:  # (2)
                jours = [j for j in ctx.jours_de_bourse(_moins(jour, 30)) if j < jour][-JOURS_PRIX_AVANT:]
                if jours and ctx.clotures(e["symbole"], jours[0], jours[-1]):  # (3)
                    r = (True, v)
    _memo[k] = r
    return r


def garder(e, ctx):
    return False  # écartée (IMPOSSIBLE) : voir CHOIX ; l'ancienne version « porteur » était : _calcul(e, ctx)[0]


def priorite(e, ctx):
    v = _calcul(e, ctx)[1]
    return -v if v is not None else 0.0
