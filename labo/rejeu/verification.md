# Vérification indépendante du rejeu d'un an

## 1. Prix et rendements refaits aux fichiers bruts de la SEC
- positions : 522 · achetées : 325 · refaites identiques (départ, arrivée, prix, rendement, marché) : 325

## 2. L'argent refait à partir des rendements
- Radar : rejeu 10,301.14 / 11,011.75 · refait 10,301.14 / 11,011.75 · identique
- Radar, frais de 10 $ par transaction : rejeu 3,758.55 / 4,012.35 · refait 3,758.55 / 4,012.35 · identique
- S&P 500 (SPY) aux mêmes dates : rejeu 10,152.95 / 11,034.01 · refait 10,152.95 / 11,034.01 · identique

## 3. Formulaires 4 du rejeu contre le document officiel d'EDGAR (XML)
- formulaires 4 comparés : 40 (20 liés aux entrées, 10 autres achats, 10 ventes) · identiques : 24 · identiques sauf l'arrondi à 2 décimales des jeux de données (prix ou actions) : 16 · écart maximal sur le montant à cause de l'arrondi : 0.288 %

## 4. Score du rejeu contre le recalcul indépendant (labo/recalcul_score.py)
- 2025-08-15 : Jour du calcul : 2025-08-15 · infos lues : 3573 · compagnies notées : 874 (publié : 874) · fonds mis à part : 32 · Hausse (7/10 et plus) : 20 · Baisse (3/10 et moins) : 0 → AUCUN ÉCART : le recalcul indépendant donne exactement le score publié.
- 2025-12-15 : Jour du calcul : 2025-12-15 · infos lues : 4159 · compagnies notées : 998 (publié : 998) · fonds mis à part : 45 · Hausse (7/10 et plus) : 20 · Baisse (3/10 et moins) : 0 → AUCUN ÉCART : le recalcul indépendant donne exactement le score publié.
- 2026-04-15 : Jour du calcul : 2026-04-15 · infos lues : 4406 · compagnies notées : 1107 (publié : 1107) · fonds mis à part : 44 · Hausse (7/10 et plus) : 20 · Baisse (3/10 et moins) : 0 → AUCUN ÉCART : le recalcul indépendant donne exactement le score publié.

VERDICT : tout concorde
