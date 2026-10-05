# Tournoi Radar — règles du jeu (fixées le 5 octobre 2026, AVANT de voir les données)

Ces règles ne changent plus. Si l'une d'elles est changée, le rapport final le dit, avec la raison.

## 1. Les règles candidates

- Écrites par les chercheurs de l'étape 1 à partir d'études, AVANT que le jeu de recherche existe, et enregistrées dans
  `labo/tournoi/regles_preenregistrees.json` (le commit Git en fait foi).
- Chaque seuil est celui écrit. Aucun réglage après avoir vu les chiffres. Une règle mal écrite (ambiguë) est appliquée
  selon le sens le plus simple ; le choix est noté.
- Les règles impossibles à tester avec les données sont écartées (avec la raison), pas modifiées.

## 2. Le banc d'essai

Le même pour toutes : `labo/tournoi/banc.py` (achat au plus tôt à la clôture du 1er jour de bourse après le dépôt,
10 $ par transaction, écart achat-vente selon la taille, argent qui attend dans le S&P 500 avec ses frais, comparaison
avec 10 000 $ gardés dans le S&P 500 aux mêmes dates, garde-fou contre le futur).

Chaque règle est programmée par un testeur, puis REPROGRAMMÉE par un vérificateur qui n'a pas vu le premier programme.
Les deux doivent donner les mêmes transactions ; sinon, la différence est expliquée et corrigée selon le texte de la règle.

## 3. Passer la découverte (juillet 2023 à juin 2026)

Une règle passe si les 3 conditions sont vraies :
1. Son portefeuille, après TOUS les frais, fait mieux que le S&P 500 gardé, **chacune** des 3 années (juillet à juin) ;
2. Son écart mensuel avec le S&P 500 a un **t de 3 ou plus** sur les 36 mois (seuil de Harvey, Liu et Zhu pour des
   recherches qui essaient beaucoup d'idées) ;
3. Au moins **30 achats sur les 3 ans**, dont au moins 5 dans chaque année (une position encore ouverte compte).

## 4. Le débat

Pour chaque règle qui passe (ou, si aucune ne passe, les 3 meilleures selon le t mensuel) : un avocat, deux sceptiques
(hasard, biais, frais, prix manquants), un juge. Le juge ne peut pas changer la règle : il peut seulement signaler une
faille qui la fait échouer (ex. un biais du futur), preuves à l'appui.

## 5. L'examen final (coffre-fort, janvier 2016 à juin 2023)

Au plus **3 règles**, choisies à la fin du débat, testées **une seule fois** chacune, avec le même banc.
Réussite = les 3 conditions :
1. Portefeuille après frais meilleur que le S&P 500 gardé sur l'ensemble des 7,5 ans ;
2. Meilleur que le S&P 500 gardé dans au moins **5 des 7** années complètes (juillet 2016 à juin 2023) ;
3. Écart mensuel avec un **t de 2 ou plus** (un seul essai par règle, 3 règles au plus).

Si aucune ne réussit, le rapport le dit franchement, chiffres à l'appui. Une règle qui réussit devient une proposition
pour Radar (un lot normal : code, tests, labo, photos), jamais une garantie de gain.

## Changements (avec la raison)

- 5 octobre 2026, 20 h UTC, AVANT que le jeu de recherche existe (l'étape 0 n'a pas encore tourné) : critère 3
  « 30 transactions par année » remplacé par « 30 achats sur les 3 ans, dont au moins 5 dans chaque année ».
  Raison : les chercheurs ne connaissaient pas ce critère, et il éliminait d'office, sans regarder leurs résultats, les
  règles qui gardent 6 à 12 mois (10 positions gardées 12 mois = 10 achats par an), alors que les études
  trouvent justement l'effet des achats d'initiés sur 6 à 12 mois. Le hasard reste contrôlé par les critères 1 et 2
  (battre le S&P 500 chacune des 3 années, et t de 3 ou plus).
  Un achat compte même si la position est encore ouverte à la fin des prix (sinon les règles de 12 mois n'auraient
  presque aucune transaction fermée dans la 3e année).
- 5 octobre 2026, 20 h 30 UTC, AVANT que le jeu de recherche existe : le banc lit les dépôts au fil des jours (une
  règle qui se souviendrait des dépôts vus ne peut plus voir le futur), donne `ctx.evenements_marche()` (tous les dépôts
  jusqu'au jour de la décision, pour la météo des initiés), et chaque période contient 1 an de dépôts de contexte, jamais
  achetés. Raison : sans cela, une règle « météo » aurait pu tricher sans que le garde-fou le voie, ou manquer de
  données pour ses premières décisions.
