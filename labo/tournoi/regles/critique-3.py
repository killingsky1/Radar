"""critique-3 : achat d'initié dans une compagnie qui rachète vraiment ses actions, garder 12 mois.

Texte pré-enregistré : labo/tournoi/regles_preenregistrees.json, partie « regles », id « critique-3 ».
Programmée telle qu'écrite (seuils du texte) ; chaque choix est dans CHOIX.

Avant le 6 octobre 2026, cette règle était écartée (IMPOSSIBLE) : le jeu n'avait pas les actions en circulation à
chaque fin de période. Elles y sont maintenant (ctx.actions_par_periode, règles du jeu, partie « Changements »).

Rachats réels (XBRL), avec CommonStockSharesOutstanding (au bilan, à la date de fin de chaque période) :
- A = le nombre à la fin de période la plus récente déjà connue au dépôt : chiffre déposé au plus tard le jour du
  dépôt, et fin datant d'au moins 60 jours civils (trimestre, 10-Q) ou 120 jours civils (exercice, 10-K) ;
- B = le nombre à la fin de période située de 330 à 400 jours civils avant celle de A, la plus proche de 365 jours ;
- gardé si 0,80 <= A / B <= 0,98 ; écarté si A ou B manque, ou si le CUSIP du titre a changé dans les 450 jours
  civils avant le dépôt.
"""
import math
from datetime import date, timedelta
from fractions import Fraction

ID = "critique-3"
IMPOSSIBLE = None

CHOIX = [
    "« Achat en bourse (code P) d'actions ordinaires » = un événement dont le sens est « achat » (code P, titres non "
    "dérivés) dont au moins un des titres déclarés (champ titres) contient « common » ou « ordinary », sans tenir compte "
    "des majuscules (ex. « Common Stock », « Class A Common Stock », « Ordinary Shares ») ; actions privilégiées, "
    "« Units », « Shares » seul, etc. : écarté (décision de la comparaison du 6 oct. 2026, voir la fin de la liste).",
    "Plusieurs déclarants sur le formulaire : les rôles du formulaire sont ceux de tous ses déclarants réunis ; il faut "
    "« administrateur » ou « dirigeant » chez au moins un déclarant (un formulaire avec seulement des « actionnaire de "
    "10 % » ou « autre » est exclu).",
    "routinier = non : gardé seulement si routinier vaut False.",
    "plan_10b5_1 différent de « oui » : gardé si False ou vide (None), à toutes les dates (« vide accepté »).",
    "montant ou valeur_m inconnu (None) : écarté, le seuil ne peut pas être vérifié. Bornes comprises : montant ≥ "
    "25 000 $ et valeur_m ≥ 100 M$.",
    "Actions en circulation : le concept CommonStockSharesOutstanding (au bilan, à la date de FIN de la période, "
    "trimestre ou exercice). C'est le seul des deux qui donne le nombre « à la fin de période » avec sa date de fin, "
    "comme le texte le demande (A, B et l'écart de 330 à 400 jours sont comptés entre des fins de période). "
    "EntityCommonStockSharesOutstanding (page couverture) n'est pas pris : sa date est proche du dépôt du rapport, pas "
    "une fin de période. Pas de repli sur ce 2e concept quand le 1er manque (le texte veut le même champ XBRL pour A et "
    "B) : une compagnie sans CommonStockSharesOutstanding n'a ni A ni B, et l'événement est écarté (« On l'écarte si A "
    "ou B manque »).",
    "Fin de trimestre ou fin d'exercice annuel : selon la forme du rapport qui a donné le chiffre (le jeu garde la 1re "
    "version déposée de chaque fin de période). 10-Q ou 10-Q/A = fin de trimestre, elle compte si elle date d'au moins "
    "60 jours civils au jour du dépôt ; 10-K, 10-K/A, 10-KT ou 10-KT/A = fin d'exercice annuel, au moins 120 jours "
    "civils. Le rapport de transition (10-KT) est compté comme un rapport annuel.",
    "« Déjà connue au dépôt » = les deux conditions à la fois : (1) le chiffre est déposé au plus tard le jour du dépôt "
    "du formulaire 4 (ctx.actions_par_periode ne montre que ceux-là ; le banc décide le soir du dépôt) ; (2) sa fin "
    "date d'au moins 60 jours (trimestre) ou 120 jours (exercice) au jour du dépôt, même si le rapport a été déposé "
    "plus tôt : ce sont des seuils du texte, gardés tels quels.",
    "A = la fin de période la plus récente qui remplit ces deux conditions. Si cette A n'a pas de B, l'événement est "
    "écarté : on ne cherche pas une A plus ancienne.",
    "B = parmi les CommonStockSharesOutstanding déposés au plus tard le jour du dépôt, la fin de période située de 330 "
    "à 400 jours civils avant celle de A (bornes comprises), la plus proche de 365 jours ; à égalité (ex. 360 et 370 "
    "jours), la plus ancienne. Sa fin date d'au moins 390 jours au dépôt : le délai de 60 ou 120 jours est donc "
    "toujours rempli pour B.",
    "Rachat réel : gardé si 0,80 ≤ A ÷ B ≤ 0,98, bornes comprises, calcul exact (fractions, sans arrondi). B égal à 0 "
    "ou négatif, ou nombre illisible : écarté (A ÷ B ne se calcule pas, comme si A ou B manquait).",
    "CUSIP : les clôtures SEC du symbole de l'événement datées du jour du dépôt moins 450 jours civils jusqu'à la "
    "veille du dépôt (les 450 jours AVANT le dépôt, le jour du dépôt exclu ; ctx.clotures). Plus d'un CUSIP différent "
    "parmi elles = le CUSIP a changé : écarté. Aucune clôture, "
    "ou un seul CUSIP, dans cette fenêtre : pas de changement vu, gardé. Un changement entre la dernière clôture "
    "d'avant la fenêtre et la 1re de la fenêtre n'est pas compté (sa date est inconnue entre les deux). Les prix du jeu "
    "commencent à une date fixe (découverte : 1er juillet 2022) : au début de la période, la fenêtre a moins de 450 "
    "jours de prix.",
    "« Pas de position déjà ouverte sur cette compagnie » et « une seule position par compagnie » : fait par le banc, "
    "qui vérifie le SYMBOLE, pas le cik (garder() ne voit pas le portefeuille). Une compagnie avec deux symboles "
    "pourrait avoir deux positions (rare).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (clôture SEC du 1er jour de bourse après le dépôt, sinon la 1re "
    "clôture SEC des 5 jours de bourse suivants, sinon l'événement est laissé tomber et la place reste libre).",
    "Sortie : DUREE = 252 et TOLERANCE_SORTIE = 20 (1re clôture SEC à partir du 252e jour de bourse après l'achat ; "
    "aucun prix pendant les 20 jours de bourse suivants : dernière clôture SEC connue). Pas de sortir_avant() : pas de "
    "vente anticipée ni de seuil de perte.",
    "Taille : MAX_POSITIONS = 5, donc 20 % de la valeur du portefeuille (actions + SPY + liquide), calculée par le banc "
    "le jour de l'achat après les ventes du jour ; le banc prend les 10 $ de frais dans ces 20 %. S'il manque d'argent "
    "(les autres positions ont monté), le banc achète avec ce qui reste. Les 5 places prises : le signal est ignoré "
    "(pas réessayé le lendemain).",
    "« Chaque achat vaut 20 % ..., au minimum 1 000 $ » : un plancher (le plus grand de 20 % et de 1 000 $), pas "
    "programmable (une règle ne voit pas la valeur de son portefeuille ; il ne jouerait que sous 5 000 $). MONTANT_MIN "
    "reste celui du banc (50 $) : MONTANT_MIN = 1000 ferait autre chose (ne pas acheter). S'il reste moins d'argent que "
    "20 % (places presque toutes prises), le banc achète avec ce qui reste, si c'est au moins 50 $.",
    "Liquide : LIQUIDE_JOURS = 10 et ARGENT_QUI_ATTEND = « SPY » (au départ 100 % dans SPY ; l'argent d'une vente "
    "attend 10 jours de bourse, sert d'abord à payer, puis va dans SPY ; 10 $ par transaction, SPY compris).",
    "Priorité : le plus gros montant d'abord. Le banc applique cet ordre à tous les signaux du jour, y compris ceux qui "
    "attendent un prix depuis un jour précédent ; à égalité : date de dépôt, puis numéro.",
    "Comportements standard du banc, pas dans le texte : demi-écart achat-vente selon la valeur en bourse (à l'achat et à "
    "la vente) en plus des 10 $ ; le premier placement dans SPY au départ se fait sans frais de 10 $ ; changement de "
    "CUSIP pendant la détention : rendement enchaîné.",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 3 écarts, tranchés selon le texte ; corrigés DANS CE FICHIER, le "
    "vérificateur ne change pas. 1) « d'actions ordinaires » est une condition écrite du filtre : filtre sur le champ "
    "titres (« common » ou « ordinary »), comme pour vitesse-1 à 4 et gestion-1 à 5 (et regles_du_jeu.md, « Changements », "
    "6 oct. vers 12 h 30 : même filtre partout où le texte le dit) ; ce programme ne filtrait pas. "
    "2) « au minimum 1 000 $ » : le sens le plus simple est un plancher (le plus grand de 20 % et de 1 000 $), pas "
    "programmable ; MONTANT_MIN = 1000 en changeait le sens (ne pas acheter quand il reste moins de 1 000 $) : "
    "MONTANT_MIN = 50 du banc, comme pour gestion-1 à 5 (même tournure). 3) CUSIP « changé dans les 450 jours civils "
    "avant le dépôt » : les clôtures des 450 jours AVANT le dépôt, le jour du dépôt exclu (même lecture de « N jours "
    "avant » que prix_bas-1 et initie-3) ; ce programme comptait aussi la clôture du jour du dépôt. Jeu ciblé "
    "(compagnies inventées : rachats, CUSIP, titres, délais, reste d'argent sous 1 000 $) : 24 décisions et des "
    "transactions différentes avant ; après : mêmes décisions, même ordre de priorité, mêmes achats et ventes (et sur "
    "le faux jeu).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 20
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 10
MONTANT_MIN = 50  # celui du banc : « au minimum 1 000 $ » est un plancher, pas programmable (voir CHOIX)
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

MONTANT_MINIMUM = 25_000  # $
VALEUR_MINIMUM = 100  # M$
ROLES_ACCEPTES = {"administrateur", "dirigeant"}
CONCEPT = "CommonStockSharesOutstanding"  # au bilan, à la date de fin de la période
DELAI_TRIMESTRE = 60  # jours civils : une fin de trimestre compte si elle date d'au moins 60 jours au dépôt
DELAI_EXERCICE = 120  # jours civils : une fin d'exercice annuel compte si elle date d'au moins 120 jours au dépôt
ECART_B_MIN, ECART_B_MAX, ECART_B_CIBLE = 330, 400, 365  # jours civils entre la fin de B et celle de A
RAPPORT_MIN, RAPPORT_MAX = Fraction(80, 100), Fraction(98, 100)  # 0,80 <= A / B <= 0,98
CUSIP_JOURS = 450  # jours civils avant le dépôt sans changement de CUSIP


def _jours(debut, fin):
    """Jours civils de la date `debut` à la date `fin` (AAAA-MM-JJ)."""
    return (date.fromisoformat(fin) - date.fromisoformat(debut)).days


def _delai(forme):
    """Délai du texte selon le rapport qui a donné le chiffre : 10-Q (et 10-Q/A) = fin de trimestre, 60 jours ;
    10-K (et 10-K/A, 10-KT, 10-KT/A) = fin d'exercice annuel, 120 jours ; autre forme (absente du jeu) : None."""
    f = (forme or "").upper()
    if f.startswith("10-Q"):
        return DELAI_TRIMESTRE
    if f.startswith("10-K"):
        return DELAI_EXERCICE
    return None


def _nombre(x):
    """Un nombre d'actions utilisable (fraction exacte), ou None."""
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return Fraction(x)


def _a_et_b(e, ctx):
    """(A, B) en fractions exactes : actions en circulation aux deux fins de période du texte ; None si A ou B manque."""
    faits = ctx.actions_par_periode(e["cik"]).get(CONCEPT) or []  # déposés au plus tard le jour du dépôt
    depot = e["depot"]
    connus = [f for f in faits
              if f[1] and (d := _delai(f[3])) is not None and _jours(f[1], depot) >= d]
    if not connus:
        return None
    fait_a = max(connus, key=lambda f: f[1])  # la fin de période la plus récente déjà connue
    candidats = [f for f in faits if f[1] and ECART_B_MIN <= _jours(f[1], fait_a[1]) <= ECART_B_MAX]
    if not candidats:
        return None
    # la plus proche de 365 jours ; à égalité, la plus ancienne
    fait_b = min(candidats, key=lambda f: (abs(_jours(f[1], fait_a[1]) - ECART_B_CIBLE), f[1]))
    a, b = _nombre(fait_a[2]), _nombre(fait_b[2])
    if a is None or b is None:
        return None
    return a, b


def _cusip_a_change(e, ctx):
    """Plus d'un CUSIP parmi les clôtures SEC du symbole, du dépôt moins 450 jours civils à la veille du dépôt."""
    depuis = (date.fromisoformat(e["depot"]) - timedelta(days=CUSIP_JOURS)).isoformat()
    veille = (date.fromisoformat(e["depot"]) - timedelta(days=1)).isoformat()
    return len({c for _, _, c in ctx.clotures(e["symbole"], depuis, veille)}) > 1


def _actions_ordinaires(e):
    """Au moins un titre déclaré contient « common » ou « ordinary » (sans tenir compte des majuscules)."""
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if e.get("sens") != "achat" or not _actions_ordinaires(e):
        return False
    roles = {r for i in (e.get("inities") or []) for r in (i.get("roles") or [])}
    if not roles & ROLES_ACCEPTES:
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant = e.get("montant")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    valeur = e.get("valeur_m")
    if valeur is None or valeur < VALEUR_MINIMUM:
        return False
    ab = _a_et_b(e, ctx)
    if ab is None:
        return False
    a, b = ab
    if b <= 0 or not (RAPPORT_MIN <= a / b <= RAPPORT_MAX):
        return False
    if _cusip_a_change(e, ctx):
        return False
    return True


def priorite(e, ctx):
    """Plusieurs signaux le même jour : le plus gros montant d'abord."""
    return float(e.get("montant") or 0.0)
