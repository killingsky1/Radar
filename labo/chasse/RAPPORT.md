# La grande chasse — résultat (9 octobre 2026)

Plan gelé AVANT tout calcul : labo/chasse/PLAN.md. Course : workflow labo90, run n° 1
(https://github.com/killingsky1/Radar/actions/runs/37943145319). Chiffres bruts : resultats/resultats.json et
resultats/journal.txt.

## Verdict : NON, aucune durée ne réussit

| Durée | Portefeuille sur 9 ans | S&P 500 (SPY) | Années gagnées | t mensuel | Réussi |
|---|---|---|---|---|---|
| 63 jours de bourse (3 mois) | −27,3 % | +207,9 % | 3 sur 9 | −1,31 | NON |
| 126 jours (6 mois) | +121,7 % | +207,9 % | 4 sur 9 | 0,16 | NON |
| 252 jours (12 mois) | +50,4 % | +207,9 % | 4 sur 9 | −0,92 | NON |

Critère gelé : battre SPY sur 9 ans après les frais, au moins 6 années sur 9, t ≥ 2,4. Comme prévu au plan : on le
dit, chiffres à l'appui, et Radar ne change pas.

## Vrai résultat, pas une erreur du moteur
- Essai sur un faux jeu (essai_chasse.py), refait dans le workflow juste avant la course : 17 sur 17. Un signal caché
  est trouvé chaque année ; le critère est atteignable quand un vrai signal existe (t 8,19) ; sans signal, rien ne
  réussit et aucune fuite du futur.
- Le S&P 500 du banc suit la réalité, année par année : 2020-2021 +37,9 %, 2021-2022 −12,4 %, 2023-2024 +22,6 %.
- 157 064 achats réels (121 610 au coffre-fort, 35 454 en découverte). Les modèles apprennent sur 7 518 à 98 157 achats
  selon l'année et la durée.
- Une seule colonne vide retirée : « plan 10b5-1 », avant 2023-2024 (la case n'existe sur le formulaire 4 que depuis
  avril 2023).

## Pourquoi ça perd (mesuré)
1. L'achat médian d'un dirigeant perd contre le S&P 500, après l'écart achat-vente : 27 cas sur 27 (9 années × 3
   durées), de −2,4 % à −27,8 %. Le S&P 500 a fait +208 % en 9 ans ; les compagnies où les dirigeants achètent (surtout
   des petites) n'ont pas suivi.
2. Le modèle classe mieux que le hasard : corrélation de rang positive 26 fois sur 27, de 0,12 à 0,26 sur les 3
   dernières années. Il repère surtout les mauvais achats : ses achats gardés ont encore une médiane négative contre
   le S&P 500 dans 24 cas sur 27.
3. Le portefeuille (10 places, 10 $ par transaction, comme le banc du tournoi) n'achète qu'une petite partie des choix
   du modèle. Les places sont pleines la plupart du temps, et 16 à 45 % des choix n'ont aucun prix de la SEC autour du
   dépôt. Il a acheté 1 à 8 % des achats gardés : 70 à 308 transactions en 9 ans selon la durée.

## Par année (pour comprendre, pas pour juger)
Rendement NET contre le S&P 500 : médiane des achats gardés par le modèle / médiane de tous les achats (achats déjà
vendus à la date de la mesure), et corrélation de rang entre le score et le résultat.

| Année | 63 j : corr. | 63 j : médiane gardés / tous | 126 j : corr. | 126 j : médiane gardés / tous | 252 j : corr. | 252 j : médiane gardés / tous |
|---|---|---|---|---|---|---|
| 2017-2018 | 0,01 | −3,4 % / −2,4 % | 0,07 | −2,3 % / −5,6 % | 0,11 | −5,7 % / −13,2 % |
| 2018-2019 | 0,08 | −8,1 % / −4,0 % | 0,07 | −8,8 % / −10,2 % | 0,06 | −18,6 % / −21,9 % |
| 2019-2020 | 0,12 | +6,2 % / −5,5 % | 0,00 | −10,0 % / −9,5 % | 0,05 | +44,2 % / −2,8 % |
| 2020-2021 | −0,05 | −8,6 % / −2,7 % | 0,03 | −8,8 % / −5,4 % | 0,15 | −13,1 % / −11,2 % |
| 2021-2022 | 0,01 | −10,0 % / −5,7 % | 0,04 | −25,0 % / −8,9 % | 0,02 | −25,9 % / −15,4 % |
| 2022-2023 | 0,13 | −9,0 % / −6,6 % | 0,15 | −10,2 % / −13,3 % | 0,09 | −32,2 % / −27,8 % |
| 2023-2024 | 0,16 | −5,7 % / −6,6 % | 0,16 | −3,7 % / −11,1 % | 0,23 | −10,6 % / −19,2 % |
| 2024-2025 | 0,13 | −5,8 % / −5,7 % | 0,12 | −8,3 % / −11,2 % | 0,17 | −2,2 % / −16,9 % |
| 2025-2026 | 0,13 | −7,7 % / −6,3 % | 0,13 | −7,9 % / −8,1 % | 0,26 | +18,0 % / −17,4 % |

2025-2026 à 252 jours : seulement 835 achats déjà vendus (ceux de juillet à septembre 2025).

## Ce qui reste permis
Toute nouvelle idée tirée de ces chiffres a été vue sur 2017-2026 : elle ne pourrait être jugée honnêtement que sur des
années jamais utilisées (2009-2015, données à bâtir), avec un nouveau plan gelé avant le calcul.
