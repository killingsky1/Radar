"""gestion-3 : cœur + satellite 70/30 : S&P 500 (SPY) et 3 meilleures idées gardées 12 mois (252 jours de bourse).

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (labo/tournoi/regles_preenregistrees.json),
sans voir labo/tournoi/regles/.
- Signal : signal S de gestion-1, PLUS montant >= 100 000 $, PLUS (a) le titre contient CEO, Chief Executive,
  President, CFO ou Chief Financial, ou (b) au moins 2 AUTRES initiés ont acheté dans les 30 jours (groupe).
- Entrée : clôture SEC du 1er jour de bourse après le dépôt (sinon 1re clôture des 5 jours de bourse suivants).
- Sortie : clôture du 252e jour de bourse après l'achat (sinon 1re clôture disponible ensuite).
- Taille : 3 places de 10 % du portefeuille chacune (minimum 1 000 $), payées en vendant du SPY ; le reste dans SPY.
"""
from datetime import date

ID = "gestion-3"

CHOIX = [
    # --- Le signal S (voir gestion-1) ---
    "« Formulaire 4 avec au moins un achat code P d'actions ordinaires » : on garde les événements sens = « achat » "
    "(code P, titres non dérivés, en bourse) dont au moins un titre déclaré (champ titres, texte libre) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; un formulaire qui n'achète que d'autres titres "
    "(actions privilégiées, parts, « Shares » seul, etc.) est écarté.",
    "Rôles : il suffit qu'UN des déclarants du formulaire (e['inities']) ait « administrateur » ou « dirigeant » dans "
    "ses rôles ; un formulaire dont les déclarants sont seulement « actionnaire de 10 % » ou « autre » est exclu.",
    "routinier = non : gardé seulement si e['routinier'] vaut False.",
    "plan_10b5_1 différent de « oui » : exclu seulement s'il vaut True ; False et vide (None) sont acceptés, à toutes "
    "les dates (pas seulement avant avril 2023), car vide est « différent de oui ».",
    "montant ou valeur_m inconnu (None) : exclu, car on ne peut pas vérifier le seuil (100 000 $ ; 100 M$).",
    "Dépôt en retard : gardé si (depot - jour_dernier) <= 10 jours civils ; jour_dernier inconnu : exclu (on ne peut pas "
    "vérifier).",
    # --- Les conditions de plus ---
    "Montant : le seuil du signal S (50 000 $) est remplacé par le plus strict, montant >= 100 000 $.",
    "(a) Titre : au moins UN déclarant du formulaire a un titre (e['inities'][i]['titre']) qui CONTIENT « CEO », "
    "« Chief Executive », « President », « CFO » ou « Chief Financial », sans tenir compte des majuscules, quel que soit "
    "son rôle (ce champ est le titre de dirigeant du formulaire 4). « Contient » pris à la lettre : « Vice President » "
    "compte (il contient « President »).",
    "(b) « groupe >= 2 (au moins 2 autres initiés ont acheté la même action dans les 30 jours avant) » : le champ "
    "groupe_30j compte AUSSI l'initié du dépôt (dictionnaire), alors que le texte explique « groupe >= 2 » par 2 AUTRES "
    "initiés. On exige donc au moins 2 initiés autres que les déclarants de ce formulaire : groupe_30j - (nombre de "
    "déclarants différents du formulaire) >= 2, soit groupe_30j >= 3 pour un seul déclarant. groupe_30j ne compte que "
    "les dépôts déjà faits (30 jours civils avant le dépôt, celui-ci compris) : rien du futur.",
    "« Une position par compagnie » : fait par le banc, qui compare les SYMBOLES ; une compagnie à deux symboles (deux "
    "catégories d'actions) pourrait avoir deux positions (rare). Une règle ne voit pas son portefeuille, elle ne peut "
    "pas le faire par cik.",
    "Plus de candidats que de places le même jour : priorite = montant (le plus gros d'abord). Le banc classe ensemble "
    "les signaux du jour et ceux qui attendent encore un prix ; un signal sans place est abandonné.",
    # --- Entrée et sortie ---
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (pas de prix SEC le 1er jour de bourse après le dépôt : la 1re "
    "clôture des 5 jours de bourse suivants, sinon le signal est abandonné).",
    "Sortie du satellite : DUREE = 252. « Ou à la première clôture disponible ensuite » n'a pas de limite dans le "
    "texte de gestion-3, qui ne renvoie pas à gestion-1 pour la sortie : délai du banc, TOLERANCE_SORTIE = 10 (1re "
    "clôture des 10 jours de bourse suivants, sinon la dernière clôture connue).",
    "Positions achetées moins de 252 jours de bourse avant la fin des prix : elles restent ouvertes à la fin "
    "(comportement standard du banc, qui les compte comme achats « en attente »).",
    # --- Cœur et satellite ---
    "Satellite de 3 places de 10 % : MAX_POSITIONS = 3 et poids = 0,3 (le banc vise valeur du portefeuille / 3 x 0,3 = "
    "10 % de la valeur totale, à la clôture du jour d'achat ; les 10 $ de frais de l'achat sont pris dans ces 10 %).",
    "Cœur : ARGENT_QUI_ATTEND = 'SPY' et LIQUIDE_JOURS = 0 : au départ 100 % dans SPY (le banc place les 10 000 $ dans "
    "SPY à la clôture du 1er jour du test), chaque achat est payé en vendant du SPY, et l'argent d'une place vide ou "
    "d'une vente retourne dans SPY. Le banc compte 10 $ de SPY à chaque achat et à chaque vente d'une position.",
    "« Minimum 1 000 $ » : lu comme un plancher (achat = le plus grand de 10 % et de 1 000 $), pas programmable : une "
    "règle ne voit pas la valeur de son portefeuille. Chaque achat reste donc à 10 %, un peu sous 1 000 $ quand le "
    "portefeuille vaut moins de 10 000 $. MONTANT_MIN reste celui du banc (50 $) : MONTANT_MIN = 1000 ferait autre "
    "chose (ne pas acheter du tout) et, comme le banc compare 1 000 $ au montant APRÈS les 10 $ de frais, il "
    "refuserait même les premiers achats d'un portefeuille de 10 000 $ (990 $ investis).",
    "Rééquilibrage annuel (au 1er jour de bourse de juillet, si le satellite dépasse 40 % du total, plus de nouvelle "
    "position jusqu'à ce qu'il redescende sous 30 %) : PAS programmé. Une règle du banc ne voit pas son portefeuille "
    "(ni la valeur de ses positions ni celle du SPY), elle ne peut donc pas calculer la part du satellite. Avec 3 places "
    "de 10 %, ce plafond ne joue que si les positions ont beaucoup monté par rapport au S&P 500 (d'environ la moitié). "
    "Les positions ouvertes ne sont jamais vendues avant terme (pas de sortir_avant), comme le dit le texte.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 3 écarts, tranchés selon le texte ; le vérificateur est "
    "corrigé, le testeur ne change pas. 1) « d'actions ordinaires » est une condition écrite du signal S : filtre sur "
    "le champ titres (« common » ou « ordinary »), comme pour vitesse-1 ; le vérificateur ne filtrait pas. 2) « 10 % "
    "du portefeuille, minimum 1 000 $ » : le sens le plus simple est un plancher (le plus grand de 10 % et de "
    "1 000 $), pas programmable ; MONTANT_MIN = 1000 en changeait le sens (ne pas acheter) et, le banc retirant les "
    "10 $ de frais du montant, empêchait même les premiers achats d'un portefeuille de 10 000 $ (le cas du texte : "
    "des positions de 1 000 $) ; donc MONTANT_MIN = 50 du banc, comme le testeur. 3) Sortie : le texte de gestion-3 "
    "ne donne pas de délai (« ou à la première clôture disponible ensuite ») et ne renvoie pas à gestion-1 pour la "
    "sortie : délai du banc, TOLERANCE_SORTIE = 10, comme le testeur (le vérificateur reprenait les 20 jours écrits "
    "dans gestion-1). "
    "Après correction : mêmes achats et ventes sur le faux jeu et sur un jeu ciblé (cas limites du signal, trous de "
    "prix au jour de vente).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 3
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

ROLES_SIGNAL = ("administrateur", "dirigeant")
MOTS_TITRE = ("ceo", "chief executive", "president", "cfo", "chief financial")


def signal_s(e):
    """Le signal S commun à gestion-1, 2, 4 et 5 (et base de gestion-3)."""
    if e.get("sens") != "achat":
        return False
    if not any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or []):
        return False
    if not any(r in ROLES_SIGNAL for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant = e.get("montant")
    if montant is None or montant < 50_000:
        return False
    valeur_m = e.get("valeur_m")
    if valeur_m is None or valeur_m < 100:
        return False
    try:
        retard = (date.fromisoformat(e["depot"]) - date.fromisoformat(e["jour_dernier"])).days
    except (KeyError, TypeError, ValueError):
        return False
    return retard <= 10


def garder(e, ctx):
    if not signal_s(e):
        return False
    if e["montant"] < 100_000:
        return False
    inities = e.get("inities") or []
    titre_ok = any(mot in (i.get("titre") or "").lower() for i in inities for mot in MOTS_TITRE)
    autres = (e.get("groupe_30j") or 0) - len({i.get("cik") for i in inities})
    return titre_ok or autres >= 2


def poids(e, ctx):
    return 0.3


def priorite(e, ctx):
    return float(e.get("montant") or 0.0)
