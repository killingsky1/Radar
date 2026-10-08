# Tournoi : débat, 2e tour (données corrigées) et décision du juge — 8 octobre 2026

## Pourquoi un 2e tour
Le 1er tour (dossier `tour1/`, 9 agents indépendants : avocat, sceptique « hasard », sceptique « biais et coûts » pour
groupes-4, liquidite_taille-3 et sante_valeur-2) n'a trouvé aucune faille fatale, mais les sceptiques ont trouvé 2
défauts de DONNÉES : 2 fichiers d'échecs de la SEC jamais lus (nom en « _0 ») et des 13D attribués au déposant. Corrigés
(regles_du_jeu.md, « Changements », 6 octobre vers 14 h 45), toutes les règles rejugées (3e jugement) : toujours aucune
règle ne passe, et les 3 meilleures selon le t ont changé : liquidite_taille-4, gestion-3, liquidite_taille-3.

## Écart à la procédure (dit franchement)
Les 9 agents du 2e tour se sont arrêtés au début : limite hebdomadaire des agents atteinte (jusqu'au 11 octobre). Les
analyses ci-dessous ont été faites par l'orchestrateur, avec les mêmes questions que le 1er tour, sur les fichiers de
`resultats/decouverte/` (3e jugement). Le juge (même orchestrateur) a appliqué la règle la moins discrétionnaire :
toutes les règles sans faille fatale prouvée vont à l'examen (au plus 3).

## Chiffres (découverte, juillet 2023 à juin 2026, après tous les frais)
| Règle | t | Total / S&P 500 | Années gagnées | Achats | Ventes qui battent le S&P 500 | Écart net médian | Sans la meilleure | Frais par aller-retour |
|---|---|---|---|---|---|---|---|---|
| liquidite_taille-4 | 1,03 | +117,9 % / +68,3 % | 2 sur 3 | 12 | 7 sur 12 | +3,0 pts | +3,4 pts (CNC +120) | 1,8 pt |
| gestion-3 | 0,53 | +81,2 % / +68,3 % | 2 sur 3 | 9 | 4 sur 9 | −3,2 pts | −4,4 pts (DYN +158) | 5,7 pts |
| liquidite_taille-3 | 0,44 | +85,2 % / +68,3 % | 1 sur 3 | 15 | 3 sur 11 | −15,4 pts | −20,6 pts (NUTX +250) | 4,2 pts |

- Deux programmations identiques, positions encore ouvertes comprises (comparées depuis le 2e jugement).
- Information du futur : impossible par construction (le banc arrête une règle qui demande une date future ; une règle
  ne lit aucun fichier) ; les sceptiques du 1er tour n'en ont trouvé dans aucun programme lu.
- Fragilité : chaque avance tient à 1 à 3 transactions ; t loin de 3 ; peu d'achats (9 à 15).
- Coïncidence vérifiée : liquidite_taille-3 et -4 ont le même écart mensuel moyen arrondi (0,00952), mais des totaux et
  des t différents : séries différentes, pas un défaut du juge.

## Décision du juge
Aucune faille fatale prouvée : les 3 règles vont à l'examen final (coffre-fort, janvier 2016 à juin 2023), une seule
fois chacune. Attente honnête : avec un écart mensuel aussi agité, même un vrai petit avantage n'aurait que quelques
chances sur 100 d'atteindre t ≥ 2 ; une réussite serait une vraie surprise, et un échec ne surprendrait personne.
Limite connue qui reste : les fractionnements d'actions ne sont pas corrigés dans la valeur en bourse.
