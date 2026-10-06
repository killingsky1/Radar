"""groupes-3 — Premier 13D sur une compagnie de 100 M$ à 10 G$, garder 12 mois.

ÉCARTÉE telle qu'écrite, pas modifiée. L'événement de cette règle est un dépôt 13D initial : on achète à la clôture du
1er jour de bourse après le dépôt du 13D. Or le banc (le même pour toutes les règles) n'appelle garder() que pour les
lignes d'evenements.jsonl.gz, c'est-à-dire des formulaires 4, et achète au 1er jour de bourse après le dépôt de CE
formulaire 4. Les dates des 13D sont bien dans les données (ctx.depots_13), mais elles ne peuvent pas déclencher un
achat : sauf si un formulaire 4 de la même compagnie est déposé par hasard le jour même du 13D, aucune entrée « au
lendemain du 13D » n'est possible avec ce banc.
"""

ID = "groupes-3"

IMPOSSIBLE = ("Le banc n'achète qu'au lendemain d'un formulaire 4 : garder() ne reçoit que les lignes "
              "d'evenements.jsonl.gz (formulaires 4) et l'achat se fait au 1er jour de bourse après LEUR dépôt. "
              "L'événement de cette règle est un dépôt 13D initial, qui n'est pas une de ces lignes : les dates des 13D "
              "sont dans les données (ctx.depots_13), mais l'entrée « clôture du 1er jour de bourse après le 13D » est "
              "impossible, sauf si un formulaire 4 de la même compagnie est déposé par hasard le jour même. Garder "
              "seulement ces coïncidences, ou acheter au lendemain du formulaire 4 suivant, testerait une autre règle. "
              "Écartée telle qu'écrite, pas modifiée ; testable seulement si le banc lisait aussi les 13D comme "
              "événements.")

CHOIX = [
    "Règle écartée telle qu'écrite : garder() refuse tout, et aucune version modifiée n'est programmée (les règles du "
    "jeu disent d'écarter une règle impossible à tester, pas de la modifier).",
    "Version « porteur » non retenue : acheter seulement quand un formulaire 4 de la même compagnie est déposé le jour "
    "même du 13D donnerait le bon jour d'entrée, mais pour une petite partie des 13D seulement, choisie par une "
    "coïncidence (un initié qui dépose ce jour-là) : ce serait une autre règle (« 13D + formulaire 4 le même jour »).",
    "Version « en retard » non retenue : acheter au lendemain du 1er formulaire 4 de la compagnie qui suit le 13D "
    "changerait la date d'entrée (parfois des semaines ou des mois plus tard) : ce serait aussi une autre règle.",
    "Autre manque, secondaire : ctx.finances ne contient pas les actions en circulation XBRL ni leur fin de période "
    "(condition 2) ; seuls les formulaires 4 les donnent (champ actions_circulation, fait déjà déposé, et valeur_m, que "
    "le texte permet aussi d'utiliser).",
    "Réglages notés pour mémoire (sans effet, aucun signal) : entrée au 1er jour de bourse après le dépôt, 5 jours de "
    "bourse pour trouver un prix, garde de 252 jours de bourse, 10 places de 10 %, argent qui attend dans SPY.",
    "CONCILIATION avec le vérificateur (6 octobre 2026) : le vérificateur testait la version « porteur » (13D gardé sur "
    "le 1er formulaire 4 de la compagnie déposé le même jour). Décision selon le texte et regles_du_jeu.md (partie 1 : "
    "les règles impossibles à tester sont écartées, avec la raison, pas modifiées) : ÉCARTÉE dans les deux fichiers ; "
    "garder seulement les 13D qui coïncident avec un formulaire 4 ajouterait une condition absente du texte, liée au "
    "13D (initiés qui déposent les deux). Le vérificateur a maintenant le même IMPOSSIBLE et refuse tout. (groupes-4 "
    "garde un porteur pour son cas 2 seulement : son cas 1, 13D puis achat d'initié, est complet.)",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 252
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"


def garder(e, ctx):
    return False
