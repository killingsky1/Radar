"""gestion-3 — Cœur + satellite 70/30 : S&P 500 et 3 meilleures idées gardées 12 mois.

Signal : le signal S de gestion-1 (formulaire 4 d'achat code P d'actions ordinaires, administrateur ou dirigeant, non
routinier, pas dans un plan 10b5-1, montant d'au moins 50 000 $, valeur en bourse d'au moins 100 M$, déposé au plus 10
jours civils après le dernier achat), PLUS montant d'au moins 100 000 $, PLUS (a) un titre de PDG ou de chef des
finances, OU (b) au moins 2 AUTRES initiés qui ont acheté la même action dans les 30 jours avant.
Entrée : clôture du 1er jour de bourse après le dépôt (sinon la 1re clôture des 5 jours de bourse suivants, sinon
abandon). Sortie : 252e jour de bourse après l'achat. Taille : 3 places de 10 % du portefeuille ; tout le reste dans
SPY (le cœur), dès le 1er jour.
"""
from datetime import date

ID = "gestion-3"

CHOIX = [
    "« Achat code P d'actions ordinaires » : un événement « achat » (lignes code P, actions acquises) dont au moins un "
    "titre déclaré (champ titres, texte libre) contient « common » ou « ordinary », sans tenir compte des majuscules. "
    "Un formulaire qui n'achète que d'autres titres (actions privilégiées, parts, « Shares of Beneficial Interest », "
    "« Class A Shares », etc.) est écarté.",
    "Montant : le champ montant du formulaire (toutes ses lignes d'achat code P qui ont un prix, tous titres "
    "confondus), au moins 100 000 $ (ce qui comprend les 50 000 $ du signal S). Montant ou valeur en bourse inconnus "
    "(vides) : écarté.",
    "Rôles avec plusieurs déclarants : le dépôt passe si AU MOINS UN déclarant a le rôle « administrateur » ou "
    "« dirigeant ».",
    "routinier = non : le champ routinier doit être faux. plan_10b5_1 différent de « oui » : seul true est écarté ; "
    "false et vide (null) sont acceptés à toute date (le texte ne dit pas de refuser un vide après avril 2023).",
    "Dépôt en retard : écarté si (dépôt − jour_dernier) > 10 jours civils ; jour_dernier inconnu : écarté.",
    "(a) Titre : au moins un déclarant dont le titre (texte libre) contient « CEO », « Chief Executive », "
    "« President », « CFO » ou « Chief Financial », sans tenir compte des majuscules. Simple recherche du texte, comme "
    "écrit : « Vice President » contient « President » et compte. Le déclarant au bon titre n'a pas besoin d'être "
    "celui qui a le rôle « dirigeant ».",
    "(b) « groupe ≥ 2 (au moins 2 AUTRES initiés ont acheté dans les 30 jours avant) » : le champ groupe_30j compte "
    "aussi les déclarants du dépôt lui-même (« celui-ci compris », dictionnaire). Les autres initiés = groupe_30j moins "
    "le nombre de déclarants différents du dépôt ; il en faut au moins 2 (avec un seul déclarant : groupe_30j ≥ 3). "
    "La fenêtre est celle du champ : achats DÉPOSÉS dans les 30 jours civils avant le dépôt, jour même compris "
    "(seulement des dépôts déjà faits, comme le demande le critique).",
    "Une position par compagnie (cik) : garder() ne voit pas le portefeuille, c'est le banc qui refuse un 2e achat, et "
    "il le fait par SYMBOLE. Une compagnie qui aurait deux symboles pourrait avoir deux positions (rare).",
    "Départage : priorite = montant (le plus gros d'abord). Le banc l'applique à tous les signaux qui ont un prix ce "
    "jour-là, y compris ceux qui attendaient un prix depuis les jours d'avant ; les signaux sans place sont perdus.",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le jour prévu, puis les 5 jours de bourse suivants).",
    "Sortie : DUREE = 252 jours de bourse après le jour d'achat. Le texte dit « ou à la première clôture disponible "
    "ensuite » sans donner de délai : délai du banc (TOLERANCE_SORTIE = 10 jours de bourse), puis dernier prix connu.",
    "3 places de 10 % : MAX_POSITIONS = 3 (3 positions au plus) et poids = 0,3 pour chaque achat (valeur du "
    "portefeuille ÷ 3 × 0,3 = 10 % de la valeur totale le jour de l'achat). Comme pour toutes les règles, le banc paie "
    "les 10 $ de frais à même ces 10 %.",
    "« Minimum 1 000 $ » est lu comme un plancher (achat = le plus grand de 10 % et de 1 000 $). Pas programmable : "
    "poids() ne voit pas la valeur du portefeuille. Chaque achat reste donc à 10 %, un peu sous 1 000 $ quand le "
    "portefeuille vaut moins de 10 000 $. MONTANT_MIN n'est pas mis à 1 000 : il ferait autre chose (ne pas acheter "
    "du tout) et, comme le banc retire les 10 $ de frais du montant, il refuserait même les premiers achats d'un "
    "portefeuille de 10 000 $ (990 $ investis). MONTANT_MIN reste celui du banc (50 $).",
    "Cœur : ARGENT_QUI_ATTEND = \"SPY\" ; au départ tout va dans SPY (le soir du 1er jour, sans frais, comme pour "
    "toutes les règles) ; chaque achat du satellite est payé en vendant du SPY (10 $) et chaque vente est remise dans "
    "SPY le jour même (10 $, LIQUIDE_JOURS = 0). Le texte ne limite pas ici les transactions SPY à une par jour.",
    "Rééquilibrage annuel (au 1er jour de bourse de juillet, si le satellite dépasse 40 % du total, plus de nouvelles "
    "positions jusqu'à ce qu'il redescende sous 30 %) : NON APPLIQUÉ, pas programmable avec le banc. Pour le décider, "
    "il faut la valeur du portefeuille et celle des positions ouvertes ; garder() et investir() ne les reçoivent pas, "
    "et la règle ne peut pas refaire le portefeuille elle-même (elle ne connaît pas le 1er jour du test). Avec 3 "
    "places de 10 %, ce frein ne joue que si le satellite a monté d'environ 56 % de plus que SPY. Les positions "
    "ouvertes ne sont jamais vendues avant terme (pas de sortir_avant).",
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

MONTANT_MIN_SIGNAL = 50_000      # $ (signal S)
MONTANT_MIN_GESTION_3 = 100_000  # $ (en plus du signal S) ; pas le réglage MONTANT_MIN du banc
VALEUR_MIN_M = 100               # M$
RETARD_MAX_JOURS = 10            # jours civils entre le dernier achat et le dépôt
ROLES_OK = ("administrateur", "dirigeant")
MOTS_TITRE = ("ceo", "chief executive", "president", "cfo", "chief financial")
AUTRES_INITIES_MIN = 2
POIDS_PLACE = 0.3                # valeur ÷ MAX_POSITIONS (3) × 0,3 = 10 %


def _actions_ordinaires(e):
    for t in e.get("titres") or []:
        t = (t or "").lower()
        if "common" in t or "ordinary" in t:
            return True
    return False


def signal_s(e):
    """Le signal S de gestion-1."""
    if e.get("sens") != "achat" or not _actions_ordinaires(e):
        return False
    if not any(r in (i.get("roles") or []) for i in (e.get("inities") or []) for r in ROLES_OK):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant, valeur = e.get("montant"), e.get("valeur_m")
    if montant is None or montant < MONTANT_MIN_SIGNAL:
        return False
    if valeur is None or valeur < VALEUR_MIN_M:
        return False
    if not e.get("jour_dernier"):
        return False
    return (date.fromisoformat(e["depot"]) - date.fromisoformat(e["jour_dernier"])).days <= RETARD_MAX_JOURS


def _titre_pdg_dfo(e):
    for i in e.get("inities") or []:
        titre = (i.get("titre") or "").lower()
        if any(m in titre for m in MOTS_TITRE):
            return True
    return False


def _autres_inities(e):
    groupe = e.get("groupe_30j")
    if groupe is None:
        return 0
    return groupe - len({i.get("cik") for i in (e.get("inities") or [])})


def garder(e, ctx):
    if not signal_s(e):
        return False
    if e["montant"] < MONTANT_MIN_GESTION_3:
        return False
    return _titre_pdg_dfo(e) or _autres_inities(e) >= AUTRES_INITIES_MIN


def priorite(e, ctx):
    return e.get("montant") or 0.0


def poids(e, ctx):
    return POIDS_PLACE
