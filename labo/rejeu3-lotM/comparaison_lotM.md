# Lot M : rejeu de 3 ans avant et après la règle des 100 M$

Avant : score-8 (rejeu du labo, labo/rejeu3). Après : score-9, le robot de la branche travail appelé tel quel. Mêmes jours, mêmes infos, mêmes prix de la SEC, même analyse (strategies.py). Écart = rendement (CUSIP estimé) moins le S&P 500 aux mêmes dates, sans frais ; « bat » = part des achetées qui battent le S&P 500.

## Entrées dans la liste « hausse »

| Année | Avant | Après | Retirées | dont moins de 100 M$ | Ajoutées |
|---|---|---|---|---|---|
| 2023-2024 | 547 | 523 | 105 | 92 | 81 |
| 2024-2025 | 530 | 518 | 121 | 100 | 109 |
| 2025-2026 | 520 | 512 | 79 | 67 | 71 |

Entrées d'après sous 100 M$ (devrait être 0) : 0

## Garder 1 mois (départ strict, sans frais)

| Année | Achetées avant → après | Écart moyen avant → après | Écart médian avant → après | Bat le S&P avant → après |
|---|---|---|---|---|
| 2023-2024 | 398 → 377 | −1,7 % → −0,3 % | −2,7 % → −1,1 % | 39 % → 44 % |
| 2024-2025 | 342 → 326 | −1,4 % → −0,9 % | −3,8 % → −3,5 % | 38 % → 39 % |
| 2025-2026 | 323 → 309 | +1,5 % → +1,6 % | −0,4 % → +0,7 % | 48 % → 50 % |

## Garder 3 mois (départ strict, sans frais)

| Année | Achetées avant → après | Écart moyen avant → après | Écart médian avant → après | Bat le S&P avant → après |
|---|---|---|---|---|
| 2023-2024 | 398 → 377 | −3,4 % → −1,6 % | −7,6 % → −5,7 % | 34 % → 36 % |
| 2024-2025 | 342 → 326 | +1,0 % → −1,0 % | −6,7 % → −6,2 % | 38 % → 36 % |
| 2025-2026 | pas encore mesurable | | | |

## Argent : 833 $ par mois répartis sur les nouvelles entrées du mois, garder 1 mois

| Année | Sans frais avant → après | 10 $ par transaction avant → après |
|---|---|---|
| 2023-2024 | 10 017 $ (S&P 10 182 $) → 10 176 $ (S&P 10 180 $) | 2 835 $ (S&P 10 182 $) → 3 189 $ (S&P 10 180 $) |
| 2024-2025 | 9 941 $ (S&P 10 107 $) → 9 979 $ (S&P 10 092 $) | 3 208 $ (S&P 10 107 $) → 3 602 $ (S&P 10 092 $) |
| 2025-2026 | 10 301 $ (S&P 10 152 $) → 10 342 $ (S&P 10 141 $) | 3 798 $ (S&P 10 152 $) → 4 086 $ (S&P 10 141 $) |

## Les compagnies qui entrent à la place des écartées

| Année | Garder 1 mois : n · écart médian · bat le S&P | Garder 3 mois : n · écart médian · bat le S&P |
|---|---|---|
| 2023-2024 | 60 · +2,5 % · 61 % | 59 · −6,6 % · 35 % |
| 2024-2025 | 62 · −3,3 % · 37 % | 62 · −5,2 % · 32 % |
| 2025-2026 | 40 · +3,1 % · 62 % | 36 · −3,6 % · 41 % |

Les écartées elles-mêmes (moins de 100 M$) sont mesurées dans facteurs.md du rejeu d'avant (« Valeur en bourse = moins de 100 M$ »).
