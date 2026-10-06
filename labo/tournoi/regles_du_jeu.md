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
- 5 octobre 2026, vers 21 h UTC, AVANT que le jeu de recherche existe, après le critique de l'étape 1 :
  1. **Échecs de livraison** : publiés par demi-mois, quelques semaines plus tard. Le banc ne montre une quantité
     d'échecs que 35 jours civils après. `liquidite_taille-2`, telle qu'écrite, décide avec les échecs des 20 jours
     avant l'achat, pas encore publiés : **écartée** (règle impossible sans information du futur), pas modifiée.
  2. **Finances** : la PREMIÈRE version de chaque chiffre (10-K et 10-Q), utilisable à partir de sa vraie date de
     dépôt (companyfacts.zip de la SEC), au lieu des « frames » (dernière version, parfois corrigée plus tard) et d'un
     délai fixe de 90 jours. `prix_bas-2` est donc appliquée sans fuite : un rapport n'est vu qu'une fois déposé.
  3. **`initie-2-historique`** : un achat passé de l'initié ne compte que si sa mesure était finie avant la décision
     (les chercheurs devaient n'utiliser que l'information connue au moment de la décision ; le banc l'impose).
  4. **Doublons** signalés par le critique : testés quand même (ils sont pré-enregistrés), mais montrés comme
     doublons ; le choix des finalistes en tient compte (tests multiples).
  5. **Publié en plus** (les critères ne changent pas) : résultat sur toute la période contre le S&P 500 et contre les
     petites compagnies (IWM), nombre d'années gagnées, et signaux perdus faute de prix de la SEC (biais possible :
     un prix n'existe que les jours d'échecs).
  6. **Témoin de la météo** (`temoin-meteo`, dans `regles_preenregistrees.json`, partie `temoins`) : le panier des
     règles meteo-*, toujours allumé. Il sert seulement à voir si un interrupteur aide ; il ne peut pas être finaliste.
  7. **Banc** : options ajoutées pour toutes les règles, demandées par des règles pré-enregistrées : argent gardé en
     liquide N jours après une vente (`LIQUIDE_JOURS`, critique-1 à 3), montant minimal (`MONTANT_MIN`), délai de
     vente sans prix (`TOLERANCE_SORTIE`, meteo-*). Par défaut, rien ne change.
  8. **Dates des prix** : vérifiées à l'étape 0, sans autre site — un achat d'initié fait en un seul jour doit être
     plus proche de la clôture de CE jour que de celle de la veille ou du lendemain (médiane sur des milliers
     d'achats). Sinon : ALERTE, et aucun test avant d'avoir corrigé.
- 6 octobre 2026, vers 12 h 15 UTC, AVANT tout résultat (aucune règle n'a encore été jugée sur les vraies données) :
  **actions en circulation** ajoutées au jeu de recherche, à part des finances en dollars : `ctx.actions_par_periode(cik)`
  (au bilan à chaque fin de période, `CommonStockSharesOutstanding`, et sur la page couverture des rapports,
  `EntityCommonStockSharesOutstanding`), à partir de leur date de dépôt, 1re version seulement. Raison : trois règles
  pré-enregistrées les demandaient dans leurs champs (critique-3, sante_valeur-1 et sante_valeur-4) et avaient été
  écartées faute de cette donnée : un oubli du jeu de recherche, pas de la règle. Les règles ne changent pas ; elles
  sont reprogrammées 2 fois sans se voir. Les autres programmes donnent exactement les mêmes achats et ventes avec ou
  sans cette donnée (vérifié sur le faux jeu). Restent écartées : `liquidite_taille-2` (information du futur, voir
  plus haut) et `groupes-3` (achat au dépôt d'un 13D : le banc n'achète qu'après un formulaire 4 ; l'ajouter
  demanderait un 2e type de signal dans le banc, pas fait).
