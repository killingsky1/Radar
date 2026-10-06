"""liquidite_taille-2 : règle 1 + exclure les titres sous forte pression d'échecs de livraison. ÉCARTÉE.

Reprogrammée par le VÉRIFICATEUR à partir du seul texte pré-enregistré (regles_preenregistrees.json), sans voir
labo/tournoi/regles/.
"""

ID = "liquidite_taille-2"

IMPOSSIBLE = (
    "Telle qu'écrite, elle exclut un achat selon les quantités d'échecs de livraison des 20 jours de bourse AVANT la "
    "date d'entrée. La SEC publie ces quantités par demi-mois, quelques semaines plus tard (le banc ne montre une "
    "quantité que 35 jours civils après) : au moment d'acheter, ces 20 jours ne sont pas encore publiés, c'est de "
    "l'information du futur. Écartée, pas modifiée (regles_du_jeu.md, Changements du 5 octobre 2026 vers 21 h UTC, "
    "point 1 ; critique, partie « impossibles »).")

CHOIX = [
    "Écartée comme décidé dans regles_du_jeu.md (Changements, point 1) : garder() retourne toujours False, aucun achat.",
    "La version « testable » évoquée par le critique (fenêtre finie au moins 35 jours avant l'achat, actions XBRL "
    "vieilles d'au moins 60 jours) n'est PAS programmée : ce serait modifier la règle.",
]


def garder(e, ctx):
    return False
