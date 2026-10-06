"""gestion-1 — Signal strict, garder 6 mois, 10 positions au maximum.

Signal S (commun à gestion-1, 2, 4 et 5) : formulaire 4 d'achat code P d'actions ordinaires, par un administrateur ou
un dirigeant, non routinier, pas fait dans un plan 10b5-1, montant d'au moins 50 000 $, valeur en bourse d'au moins
100 M$, déposé au plus 10 jours civils après le dernier achat. Une position par compagnie ; trop de candidats le même
jour : le plus gros montant d'abord.
Entrée : clôture du 1er jour de bourse après le dépôt (sinon la 1re clôture des 5 jours de bourse suivants, sinon
abandon). Sortie : clôture du 126e jour de bourse après l'achat. Taille : 10 % du portefeuille, 10 positions au plus,
l'argent qui attend dans SPY.
"""
from datetime import date

ID = "gestion-1"

CHOIX = [
    "« Achat code P d'actions ordinaires » : un événement « achat » (lignes code P, actions acquises) dont au moins un "
    "titre déclaré (champ titres, texte libre) contient « common » ou « ordinary », sans tenir compte des majuscules. "
    "Un formulaire qui n'achète que d'autres titres (actions privilégiées, parts, « Shares of Beneficial Interest », "
    "« Class A Shares », etc.) est écarté.",
    "Montant : le champ montant du formulaire (toutes ses lignes d'achat code P qui ont un prix, tous titres "
    "confondus). Montant ou valeur en bourse inconnus (vides) : écarté, le seuil ne peut pas être vérifié.",
    "Rôles avec plusieurs déclarants : le dépôt passe si AU MOINS UN déclarant a le rôle « administrateur » ou "
    "« dirigeant » (un dépôt fait seulement par des actionnaires de 10 % ou « autre » est écarté).",
    "routinier = non : le champ routinier doit être faux.",
    "plan_10b5_1 différent de « oui » : seul true est écarté ; false et vide (null) sont acceptés à toute date. Le "
    "texte dit « différent de oui » ; il ne dit pas de refuser un vide après avril 2023.",
    "Dépôt en retard : écarté si (dépôt − jour_dernier) > 10 jours civils ; jour_dernier inconnu : écarté (la "
    "condition ne peut pas être vérifiée).",
    "Une position par compagnie (cik) : garder() ne voit pas le portefeuille, c'est le banc qui refuse un 2e achat, et "
    "il le fait par SYMBOLE. Une compagnie qui aurait deux symboles pourrait avoir deux positions (rare).",
    "Départage : priorite = montant (le plus gros d'abord). Le banc l'applique à tous les signaux qui ont un prix ce "
    "jour-là, y compris ceux qui attendaient un prix depuis les jours d'avant ; les signaux sans place sont perdus.",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le jour prévu, puis les 5 jours de bourse suivants).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat ; pas de prix ce jour-là : 1re clôture suivante, "
    "jusqu'à 20 jours de bourse (TOLERANCE_SORTIE = 20), puis dernier prix connu. « Et qu'il n'y en a plus jamais » "
    "demande le futur : comme le banc, on vend au dernier prix connu après 20 jours de bourse sans prix, même si un "
    "prix revenait plus tard.",
    "Taille : MAX_POSITIONS = 10, donc 10 % de la valeur du portefeuille (actions + SPY + comptant) le jour de "
    "l'achat ; comme pour toutes les règles, le banc paie les 10 $ de frais à même ces 10 % (990 $ investis pour un "
    "achat de 1 000 $).",
    "« Au minimum 1 000 $ » est lu comme un plancher (achat = le plus grand de 10 % et de 1 000 $). Pas programmable : "
    "poids() ne voit pas la valeur du portefeuille. Chaque achat reste donc à 10 %, un peu sous 1 000 $ quand le "
    "portefeuille vaut moins de 10 000 $. MONTANT_MIN n'est pas mis à 1 000 : il ferait autre chose (ne pas acheter "
    "du tout) et, comme le banc retire les 10 $ de frais du montant, il refuserait même les premiers achats d'un "
    "portefeuille de 10 000 $ (990 $ investis). MONTANT_MIN reste celui du banc (50 $).",
    "Argent qui attend dans SPY (ARGENT_QUI_ATTEND = \"SPY\") et produit d'une vente remis dans SPY le jour même "
    "(LIQUIDE_JOURS = 0). « Au plus une transaction SPY par jour » : le banc compte 10 $ de SPY par achat et par vente, "
    "même s'il y en a plusieurs le même jour ; les frais peuvent donc être un peu plus élevés que dans le texte.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 2 écarts, tranchés selon le texte ; le vérificateur est "
    "corrigé, le testeur ne change pas. 1) « d'actions ordinaires » est une condition écrite du signal S : filtre sur "
    "le champ titres (« common » ou « ordinary »), comme pour vitesse-1 ; le vérificateur ne filtrait pas. 2) « 10 % "
    "du portefeuille, minimum 1 000 $ » : le sens le plus simple est un plancher (le plus grand de 10 % et de "
    "1 000 $), pas programmable ; MONTANT_MIN = 1000 en changeait le sens (ne pas acheter) et, le banc retirant les "
    "10 $ de frais du montant, empêchait même les premiers achats d'un portefeuille de 10 000 $ (le cas du texte : "
    "des positions de 1 000 $) ; donc MONTANT_MIN = 50 du banc, comme le testeur. "
    "Après correction : mêmes achats et ventes sur le faux jeu (et sur le jeu ciblé de gestion-3).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0

MONTANT_MIN_SIGNAL = 50_000      # $
VALEUR_MIN_M = 100               # M$
RETARD_MAX_JOURS = 10            # jours civils entre le dernier achat et le dépôt
ROLES_OK = ("administrateur", "dirigeant")


def _actions_ordinaires(e):
    for t in e.get("titres") or []:
        t = (t or "").lower()
        if "common" in t or "ordinary" in t:
            return True
    return False


def signal_s(e):
    """Le signal S de gestion-1 (aussi celui de gestion-2, 4 et 5)."""
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


def garder(e, ctx):
    return signal_s(e)


def priorite(e, ctx):
    return e.get("montant") or 0.0
