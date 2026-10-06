# Tournoi : découverte (juillet 2023 à juin 2026)

Données : `cache/decouverte`. Par année : portefeuille / S&P 500 gardé, en % (achats). Période entière : portefeuille / S&P 500 / petites compagnies (IWM), en %. t = écart mensuel avec le S&P 500, sur les mois de la période. Sans prix : signaux jamais achetés faute de prix de la SEC.

| Règle | Années | Période entière | Années gagnées | Sans prix | t | Achats | 1. bat le S&P 500 chaque année | 2. t ≥ 3 | 3. achats | 2 programmations | Passe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| critique-1 | +7.6 / +22.6 (5) · +16.1 / +13.3 (5) · +20.4 / +20.9 (5) | +50.5 / +68.3 / +60.1 | 1 | 429 sur 2574 | -0.22 | 15 | non | non | non | identiques | non |
| critique-2 | -19.9 / +22.6 (10) · +3.1 / +13.3 (10) · +1.4 / +20.9 (10) | -13.3 / +68.3 / +60.1 | 0 | 112 sur 609 | -1.29 | 30 | non | non | oui | identiques | non |
| critique-3 | -9.5 / +22.6 (5) · +30.7 / +13.3 (5) · +7.9 / +20.9 (5) | +28.0 / +68.3 / +60.1 | 1 | 233 sur 1026 | -1.02 | 15 | non | non | non | identiques | non |
| gestion-1 | -25.9 / +22.6 (20) · -13.1 / +13.3 (20) · -7.0 / +20.9 (20) | -39.0 / +68.3 / +60.1 | 0 | 1358 sur 7195 | -2.94 | 60 | non | non | oui | identiques | non |
| gestion-2 | -10.8 / +22.6 (10) · +0.8 / +13.3 (10) · +25.9 / +20.9 (10) | +12.0 / +68.3 / +60.1 | 1 | 1358 sur 7195 | -1.41 | 30 | non | non | oui | identiques | non |
| gestion-3 | +19.7 / +22.6 (3) · +2.2 / +13.3 (3) · +18.7 / +20.9 (3) | +44.6 / +68.3 / +60.1 | 0 | 473 sur 2692 | -1.3 | 9 | non | non | non | identiques | non |
| gestion-4 | -25.9 / +22.6 (29) · -19.4 / +13.3 (27) · -21.6 / +20.9 (30) | -53.1 / +68.3 / +60.1 | 0 | 1358 sur 7195 | -3.47 | 86 | non | non | oui | identiques | non |
| gestion-5 | -4.0 / +22.6 (12) · -23.2 / +13.3 (17) · +6.1 / +20.9 (15) | -22.6 / +68.3 / +60.1 | 0 | 1358 sur 7195 | -2.34 | 44 | non | non | oui | identiques | non |
| groupes-1 | -23.9 / +22.6 (20) · +0.6 / +13.3 (20) · -6.3 / +20.9 (20) | -26.4 / +68.3 / +60.1 | 0 | 192 sur 989 | -2.4 | 60 | non | non | oui | identiques | non |
| groupes-2 | -30.9 / +22.6 (31) · -12.9 / +13.3 (32) · +9.4 / +20.9 (37) | -33.9 / +68.3 / +60.1 | 0 | 52 sur 254 | -2.4 | 100 | non | non | oui | identiques | non |
| groupes-3 | ÉCARTÉE : Le banc n'achète qu'au lendemain d'un formulaire 4 : garder() ne reçoit que les lignes d'evenements.jsonl.gz (formulaires 4) et l'achat se fait au 1er | | | | | | | | | | non |
| groupes-4 | +9.7 / +22.6 (16) · +26.8 / +13.3 (18) · +50.9 / +20.9 (19) | +111.7 / +68.3 / +60.1 | 2 | 23 sur 126 | 0.84 | 53 | non | non | oui | identiques | non |
| initie-1-pdg-dfo | -34.8 / +22.6 (10) · +26.1 / +13.3 (10) · +112.1 / +20.9 (10) | +76.8 / +68.3 / +60.1 | 2 | 329 sur 1637 | 0.31 | 30 | non | non | oui | identiques | non |
| initie-2-historique | -12.3 / +22.6 (10) · -36.5 / +13.3 (10) · +5.7 / +20.9 (10) | -41.5 / +68.3 / +60.1 | 0 | 123 sur 564 | -2.48 | 30 | non | non | oui | identiques | non |
| initie-3-premier-achat | -47.8 / +22.6 (10) · +26.3 / +13.3 (10) · +6.3 / +20.9 (10) | -29.2 / +68.3 / +60.1 | 1 | 402 sur 2076 | -1.38 | 30 | non | non | oui | identiques | non |
| initie-4-engagement | -51.2 / +22.6 (10) · +7.6 / +13.3 (10) · +10.2 / +20.9 (10) | -38.4 / +68.3 / +60.1 | 0 | 249 sur 1326 | -0.68 | 30 | non | non | oui | identiques | non |
| initie-5-combine | +15.0 / +22.6 (10) · +0.0 / +13.3 (10) · +9.1 / +20.9 (10) | +29.2 / +68.3 / +60.1 | 0 | 53 sur 342 | -0.26 | 30 | non | non | oui | identiques | non |
| liquidite_taille-1 | -8.8 / +22.6 (9) · +44.6 / +13.3 (8) · +9.2 / +20.9 (5) | +43.0 / +68.3 / +60.1 | 1 | 578 sur 2918 | -0.12 | 22 | non | non | non | identiques | non |
| liquidite_taille-2 | ÉCARTÉE : Information du futur : le filtre utilise les quantités d'échecs de livraison des 20 jours de bourse avant la date d'entrée, que la SEC publie par demi | | | | | | | | | | non |
| liquidite_taille-3 | +68.6 / +22.6 (5) · -0.8 / +13.3 (5) · +8.2 / +20.9 (5) | +81.0 / +68.3 / +60.1 | 1 | 158 sur 488 | 0.42 | 15 | non | non | non | identiques | non |
| liquidite_taille-4 | +9.7 / +22.6 (4) · +10.5 / +13.3 (4) · -0.5 / +20.9 (4) | +20.5 / +68.3 / +60.1 | 0 | 31 sur 236 | -0.87 | 12 | non | non | non | identiques | non |
| meteo-1 | -18.2 / +22.6 (10) · +22.6 / +13.3 (10) · +59.7 / +20.9 (20) | +60.5 / +68.3 / +60.1 | 2 | 970 sur 5370 | -0.01 | 40 | non | non | oui | identiques | non |
| meteo-2 | -36.2 / +22.6 (20) · +25.0 / +13.3 (10) · +15.8 / +20.9 (10) | -7.1 / +68.3 / +60.1 | 1 | 970 sur 5370 | -1.72 | 40 | non | non | oui | identiques | non |
| meteo-3 | +0.0 / +0.0 (0) · +2.2 / +13.3 (10) · -4.6 / +20.9 (20) | +19.8 / +68.3 / +60.1 | 0 | 970 sur 5370 | -1.8 | 30 | non | non | non | identiques | non |
| meteo-4 | +22.1 / +22.6 (10) · -0.6 / +13.3 (10) · +13.1 / +20.9 (10) | +37.5 / +68.3 / +60.1 | 0 | 249 sur 1252 | -1.0 | 30 | non | non | oui | identiques | non |
| meteo-5 | -36.2 / +22.6 (20) · -8.7 / +13.3 (18) · +9.8 / +20.9 (20) | -36.3 / +68.3 / +60.1 | 0 | 970 sur 5370 | -2.55 | 58 | non | non | oui | identiques | non |
| prix_bas-1 | -28.6 / +22.6 (10) · -0.6 / +13.3 (10) · +23.2 / +20.9 (10) | -10.5 / +68.3 / +60.1 | 1 | 332 sur 1349 | -1.55 | 30 | non | non | oui | identiques | non |
| prix_bas-2 | -35.7 / +22.6 (10) · +45.9 / +13.3 (10) · -27.1 / +20.9 (10) | -30.9 / +68.3 / +60.1 | 1 | 165 sur 1067 | -0.87 | 30 | non | non | oui | identiques | non |
| prix_bas-3 | -47.8 / +22.6 (10) · -4.8 / +13.3 (10) · -28.8 / +20.9 (10) | -64.0 / +68.3 / +60.1 | 0 | 146 sur 863 | -2.5 | 30 | non | non | oui | identiques | non |
| prix_bas-4 | -19.4 / +22.6 (10) · -24.5 / +13.3 (10) · +15.1 / +20.9 (10) | -31.6 / +68.3 / +60.1 | 0 | 91 sur 859 | -2.2 | 30 | non | non | oui | identiques | non |
| sante_valeur-1 | +1.1 / +22.6 (6) · -29.3 / +13.3 (6) · +23.2 / +20.9 (6) | -10.9 / +68.3 / +60.1 | 1 | 27 sur 118 | -1.46 | 18 | non | non | non | identiques | non |
| sante_valeur-2 | +0.5 / +22.6 (6) · +18.9 / +13.3 (6) · +49.2 / +20.9 (6) | +81.3 / +68.3 / +60.1 | 2 | 30 sur 93 | 0.35 | 18 | non | non | non | identiques | non |
| sante_valeur-3 | +1.8 / +22.6 (6) · -27.6 / +13.3 (6) · -11.1 / +20.9 (6) | -33.9 / +68.3 / +60.1 | 0 | 17 sur 109 | -2.72 | 18 | non | non | non | identiques | non |
| sante_valeur-4 | +6.8 / +22.6 (4) · +0.8 / +13.3 (4) · +24.9 / +20.9 (4) | +35.6 / +68.3 / +60.1 | 1 | 27 sur 87 | -1.06 | 12 | non | non | non | identiques | non |
| temoin-meteo | -36.2 / +22.6 (20) · -10.2 / +13.3 (20) · -8.0 / +20.9 (20) | -47.3 / +68.3 / +60.1 | 0 | 970 sur 5370 | -3.08 | 60 | non | non | oui | identiques | témoin |
| vitesse-1 | -48.8 / +22.6 (52) · -66.3 / +13.3 (49) · -95.4 / +20.9 (40) | -99.2 / +68.3 / +60.1 | 0 | 538 sur 883 | -5.37 | 141 | non | non | oui | identiques | non |
| vitesse-2 | -48.3 / +22.6 (70) · -97.7 / +13.3 (64) · -15.0 / +20.9 (1) | -99.0 / +68.3 / +60.1 | 0 | 790 sur 1355 | -3.79 | 135 | non | non | non | identiques | non |
| vitesse-3 | -19.2 / +22.6 (31) · +12.8 / +13.3 (29) · -30.9 / +20.9 (29) | -37.7 / +68.3 / +60.1 | 0 | 433 sur 691 | -1.52 | 89 | non | non | oui | identiques | non |
| vitesse-4 | -61.2 / +22.6 (30) · -41.9 / +13.3 (29) · -4.0 / +20.9 (31) | -78.2 / +68.3 / +60.1 | 0 | 611 sur 971 | -3.53 | 90 | non | non | oui | identiques | non |
