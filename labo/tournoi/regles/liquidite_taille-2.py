"""liquidite_taille-2 : règle 1 + exclure les titres sous forte pression d'échecs de livraison.

ÉCARTÉE, pas modifiée (regles_du_jeu.md, partie « Changements », 5 octobre 2026 vers 21 h UTC, point 1 ; critique de
l'étape 1, partie « impossibles »). Telle qu'écrite, elle décide avec les quantités d'échecs de livraison des 20 jours de
bourse avant la date d'entrée. La SEC publie ces quantités par demi-mois, quelques semaines plus tard : le banc ne les
montre que 35 jours civils après. Au moment d'acheter, ces jours ne sont pas encore publiés : information du futur.
"""

ID = "liquidite_taille-2"

IMPOSSIBLE = ("Information du futur : le filtre utilise les quantités d'échecs de livraison des 20 jours de bourse avant "
              "la date d'entrée, que la SEC publie par demi-mois quelques semaines plus tard (le banc ne les montre que "
              "35 jours civils après). Écartée telle qu'écrite (regles_du_jeu.md, Changements, point 1), pas modifiée.")

CHOIX = [
    "Règle écartée telle qu'écrite (information du futur) : garder() refuse tout, et aucune version corrigée n'est "
    "programmée (les règles du jeu disent d'écarter une règle impossible, pas de la modifier ; la fenêtre décalée de "
    "35 jours proposée par le critique serait une autre règle).",
]


def garder(e, ctx):
    return False
