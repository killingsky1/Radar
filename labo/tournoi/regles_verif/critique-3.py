"""critique-3 : achat d'initié dans une compagnie qui rachète vraiment ses actions (XBRL), garder 12 mois.

Programmée par le VÉRIFICATEUR, sans voir labo/tournoi/regles/, d'après le texte de regles_preenregistrees.json.
Reprogrammée au complet le 6 octobre 2026 avec ctx.actions_par_periode(cik) (actions en circulation à chaque fin de
période, ajoutées au jeu de recherche avant tout résultat) : la règle n'est plus écartée.
"""
import math
from datetime import date, timedelta
from fractions import Fraction

ID = "critique-3"

CHOIX = [
    "Actions en circulation : le concept CommonStockSharesOutstanding (us-gaap, au bilan, à la date de FIN du "
    "trimestre ou de l'exercice), le même pour A et pour B comme le demande la note de la règle. Pas "
    "EntityCommonStockSharesOutstanding (dei) : sa date est celle de la page couverture, quelques jours avant le dépôt "
    "du rapport, pas une fin de période ; or A, B, les délais de 60 et 120 jours et l'écart de 330 à 400 jours sont "
    "tous comptés à partir de fins de période. Pas de repli sur le dei quand le us-gaap manque : A ou B manque, donc "
    "l'événement est écarté (texte).",
    "« Déjà connue au dépôt » : ctx.actions_par_periode ne montre un chiffre qu'à partir de sa vraie date de dépôt (le "
    "jour même du formulaire 4 compris : garder() décide le soir du dépôt), ET les délais du texte s'ajoutent : une fin "
    "compte si elle date d'au moins 60 jours civils au dépôt du formulaire 4 pour un trimestre, d'au moins 120 jours "
    "pour un exercice annuel (bornes comprises).",
    "Trimestre ou exercice : selon la forme du rapport qui a publié le chiffre la 1re fois (le jeu garde la 1re "
    "version) : 10-K, 10-K/A, 10-KT ou 10-KT/A = fin d'exercice (120 jours) ; 10-Q ou 10-Q/A = fin de trimestre "
    "(60 jours). Le jeu ne dit pas autrement si une date de fin est un trimestre ou un exercice.",
    "A = le nombre d'actions à la fin la plus récente qui compte (le jeu n'a qu'un chiffre par date de fin et par "
    "concept). Une fin plus récente qui ne compte pas encore (ex. exercice fini il y a 90 jours, déjà déposé) est "
    "sautée : A vient alors de la fin précédente qui compte.",
    "B = parmi les chiffres du même concept connus au dépôt, ceux dont la fin est 330 à 400 jours civils avant la fin "
    "de A (bornes comprises) ; on prend celui dont l'écart est le plus proche de 365 jours. Égalité (ex. 360 et 370 "
    "jours) : le plus ancien (le premier dans l'ordre des dates). B peut être une fin de trimestre ou d'exercice, peu "
    "importe le type de A (le texte ne demande pas le même type). B respecte toujours le délai de 60 ou 120 jours (sa "
    "fin est au moins 390 jours avant le dépôt).",
    "A ÷ B calculé en fraction exacte (pas d'arrondi) ; gardé si 0,80 ≤ A ÷ B ≤ 0,98, bornes comprises. B nul ou "
    "négatif (donnée impossible) : traité comme manquant, écarté. Un chiffre qui n'est pas un nombre est ignoré "
    "(n'arrive pas : le jeu n'en garde pas).",
    "CUSIP : celui des prix SEC du symbole de l'événement (ctx.clotures). « Changé dans les 450 jours civils avant le "
    "dépôt » = plus d'un CUSIP différent parmi les clôtures datées de dépôt − 450 jours à dépôt − 1 jour (les 450 jours "
    "avant le dépôt, le jour du dépôt exclu). Seules les clôtures de cette fenêtre comptent : un changement entre la "
    "dernière clôture d'avant la fenêtre et la 1re de la fenêtre n'est pas vu. Aucune clôture dans la fenêtre : aucun "
    "changement vu, l'événement n'est pas écarté pour cela.",
    "« Achat en bourse (code P) d'actions ordinaires » : un événement « achat » du jeu (code P, titres non dérivés) "
    "dont au moins un des titres déclarés (champ titres) contient « common » ou « ordinary », sans tenir compte des "
    "majuscules (ex. « Common Stock », « Class A Common Stock », « Ordinary Shares ») ; un titre sans ces mots "
    "(actions privilégiées, « Units », « Shares » seul, etc.) est refusé. « D'actions ordinaires » est une condition du "
    "texte : même lecture que la décision de la comparaison testeur/vérificateur du 6 octobre 2026 pour vitesse-1 à 4 "
    "(même phrase). Le champ titres n'est pas dans la liste des champs de la règle, mais la condition est dans le filtre.",
    "Rôles : au moins un déclarant du formulaire est « administrateur » ou « dirigeant » (un formulaire avec seulement "
    "des « actionnaire de 10 % » ou « autre » est écarté).",
    "routinier = non : gardé seulement si routinier vaut faux (comme gestion-1 à 5 ; le jeu n'a jamais de vide). "
    "plan_10b5_1 : écarté seulement si « oui » (vrai) ; faux ou vide acceptés. montant ou valeur_m inconnus : écarté "
    "(on ne peut pas savoir s'ils atteignent le seuil). valeur_m = le champ du jeu.",
    "Priorité au plus gros montant : le banc range par priorité tous les signaux à acheter ce jour-là, y compris ceux "
    "qui attendaient un prix depuis un jour précédent ; égalité : dépôt, puis numéro.",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 : le 1er jour de bourse après le dépôt, sinon la 1re clôture "
    "des 5 jours de bourse suivants, sinon le signal est abandonné.",
    "Sortie : DUREE = 252 jours de bourse après l'achat et TOLERANCE_SORTIE = 20 : 1re clôture du 252e au 272e jour ; "
    "aucune : vente au dernier prix connu, faite le 272e jour.",
    "5 places (MAX_POSITIONS = 5) : la cible de 20 % est calculée par le banc sur la valeur (actions + SPY + liquide) "
    "du jour de l'achat, après les ventes du jour, une seule fois pour tous les achats du jour ; les 10 $ de l'achat "
    "sont pris dans ces 20 %, les 10 $ de la vente de SPY s'y ajoutent.",
    "« Chaque achat vaut 20 % ..., au minimum 1 000 $ » : le sens le plus simple est un plancher (le plus grand de 20 % "
    "et de 1 000 $), pas programmable : une règle ne voit pas la valeur de son portefeuille. Il ne jouerait que sous "
    "5 000 $ de portefeuille. MONTANT_MIN reste celui du banc (50 $) : MONTANT_MIN = 1000 ferait autre chose (ne pas "
    "acheter du tout). Même lecture que la décision de la comparaison testeur/vérificateur du 6 octobre 2026 pour "
    "gestion-1 à 5 (même tournure). S'il reste moins d'argent que 20 % (places presque toutes prises), le banc achète "
    "avec ce qui reste, si c'est au moins 50 $.",
    "« Pas de position déjà ouverte sur cette compagnie » et « une seule position par compagnie » : faits par le banc "
    "(consigne : ne pas refaire ce que le banc fait), qui compare le SYMBOLE, pas le cik ; garder() ne voit pas le "
    "portefeuille. Une compagnie avec 2 symboles pourrait avoir 2 positions (rare). Le banc vérifie au moment "
    "d'acheter, après les ventes du jour, pas le soir du dépôt : une position de la même compagnie vendue le jour même "
    "de l'achat n'empêche pas l'achat (rare). Places pleines le jour où le prix existe : signal ignoré (banc).",
    "Argent : ARGENT_QUI_ATTEND = « SPY » dès le départ ; LIQUIDE_JOURS = 10 (l'argent d'une vente attend 10 jours "
    "de bourse, puis va dans SPY) ; on paie avec le liquide d'abord, puis en vendant du SPY.",
    "Frais : le banc ajoute aussi le demi-écart achat-vente selon la taille (pareil pour toutes les règles) ; le texte "
    "ne parle que des 10 $ par transaction.",
    "Pas de vente anticipée, pas de seuil de perte, pas de météo : ni sortir_avant ni investir. "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0 (le texte ne demande pas de pause).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 3 écarts, tranchés selon le texte ; corrigés dans le fichier du "
    "TESTEUR, rien ne change ici. 1) Filtre « d'actions ordinaires » sur le champ titres (le testeur ne filtrait pas ; "
    "regles_du_jeu.md, « Changements », 6 oct. vers 12 h 30 : même filtre partout où le texte le dit). "
    "2) MONTANT_MIN = 50 du banc : « au minimum 1 000 $ » est un plancher, pas programmable (le testeur avait "
    "MONTANT_MIN = 1000 : pas d'achat quand il restait moins de 1 000 $). 3) Fenêtre CUSIP = les 450 jours AVANT le "
    "dépôt, le jour du dépôt exclu (le testeur comptait la clôture du jour du dépôt). Après correction : mêmes achats et "
    "ventes sur le faux jeu et sur le jeu ciblé.",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 10
MONTANT_MIN = 50                    # celui du banc : « au minimum 1 000 $ » est un plancher, pas programmable
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

ROLES_OK = {"administrateur", "dirigeant"}
MONTANT_ACHAT_MIN = 25_000          # $
VALEUR_MIN_M = 100                  # M$
CONCEPT = "CommonStockSharesOutstanding"
DELAI_TRIMESTRE = 60                # jours civils : une fin de trimestre compte si elle date d'au moins 60 jours
DELAI_EXERCICE = 120                # jours civils : une fin d'exercice annuel, d'au moins 120 jours
ECART_B_MIN, ECART_B_MAX, ECART_B_CIBLE = 330, 400, 365   # jours civils entre la fin de B et celle de A
RAPPORT_MIN, RAPPORT_MAX = Fraction(80, 100), Fraction(98, 100)
CUSIP_JOURS = 450                   # jours civils avant le dépôt


def _jours(a, b):
    """Jours civils de la date a à la date b (AAAA-MM-JJ)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _nombre(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _delai(forme):
    """Délai minimal (jours civils) entre une fin de période et le dépôt : 120 pour un exercice (10-K, 10-K/A, 10-KT,
    10-KT/A), 60 pour un trimestre (10-Q, 10-Q/A)."""
    return DELAI_EXERCICE if (forme or "").startswith("10-K") else DELAI_TRIMESTRE


def _a_et_b(e, ctx):
    """(A, B) : actions en circulation (CommonStockSharesOutstanding) à la fin de A et à celle de B ; None si l'un
    des deux manque."""
    depot = e["depot"]
    faits = [f for f in ctx.actions_par_periode(e["cik"]).get(CONCEPT, []) if f[1] and _nombre(f[2])]
    a = None
    for f in faits:  # fin la plus récente en dernier : on garde la dernière qui compte
        if _jours(f[1], depot) >= _delai(f[3]):
            a = f
    if a is None:
        return None
    b, meilleur = None, None
    for f in faits:  # dans l'ordre des dates : à égalité, le premier (le plus ancien) reste
        ecart = _jours(f[1], a[1])
        if ECART_B_MIN <= ecart <= ECART_B_MAX:
            k = abs(ecart - ECART_B_CIBLE)
            if meilleur is None or k < meilleur:
                b, meilleur = f, k
    if b is None:
        return None
    return a[2], b[2]


def _rapport(e, ctx):
    """A ÷ B en fraction exacte, ou None si A ou B manque (ou B ≤ 0)."""
    ab = _a_et_b(e, ctx)
    if ab is None or ab[1] <= 0:
        return None
    return Fraction(ab[0]) / Fraction(ab[1])


def _cusip_a_change(e, ctx):
    """Plus d'un CUSIP parmi les clôtures SEC du symbole datées de dépôt − 450 jours à dépôt − 1 jour."""
    depot = date.fromisoformat(e["depot"])
    de = (depot - timedelta(days=CUSIP_JOURS)).isoformat()
    a = (depot - timedelta(days=1)).isoformat()
    return len({c for _, _, c in ctx.clotures(e["symbole"], de, a)}) > 1


def _actions_ordinaires(e):
    """Au moins un titre déclaré contient « common » ou « ordinary » (sans tenir compte des majuscules)."""
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat" or not _actions_ordinaires(e):
        return False
    roles = set()
    for i in e.get("inities") or []:
        roles.update(i.get("roles") or [])
    if not roles & ROLES_OK:
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant = e.get("montant")
    if montant is None or montant < MONTANT_ACHAT_MIN:
        return False
    valeur = e.get("valeur_m")
    if valeur is None or valeur < VALEUR_MIN_M:
        return False
    r = _rapport(e, ctx)
    if r is None or not RAPPORT_MIN <= r <= RAPPORT_MAX:
        return False
    if _cusip_a_change(e, ctx):
        return False
    return True


def priorite(e, ctx):
    """Plusieurs signaux le même jour : le plus gros montant d'abord."""
    return e.get("montant") or 0.0
