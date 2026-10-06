# Tournoi : découverte (juillet 2023 à juin 2026)

Données : `cache/decouverte`. Par année : portefeuille / S&P 500 gardé, en % (achats). Période entière : portefeuille / S&P 500 / petites compagnies (IWM), en %. t = écart mensuel avec le S&P 500, sur les mois de la période. Sans prix : signaux jamais achetés faute de prix de la SEC.

| Règle | Années | Période entière | Années gagnées | Sans prix | t | Achats | 1. bat le S&P 500 chaque année | 2. t ≥ 3 | 3. achats | 2 programmations | Passe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| critique-1 | +7.6 / +22.6 (5) · +3.2 / +13.3 (5) · +10.6 / +20.9 (5) | +22.7 / +68.3 / +60.1 | 0 | 433 sur 2580 | -0.87 | 15 | non | non | non | identiques | non |
| critique-2 | -19.3 / +22.6 (10) · -8.9 / +13.3 (10) · +106.3 / +20.9 (10) | +53.5 / +68.3 / +60.1 | 1 | 114 sur 614 | 0.04 | 30 | non | non | oui | identiques | non |
| critique-3 | -9.5 / +22.6 (5) · -6.1 / +13.3 (5) · +56.5 / +20.9 (5) | +36.3 / +68.3 / +60.1 | 1 | 236 sur 1028 | -0.55 | 15 | non | non | non | identiques | non |
| gestion-1 | -19.3 / +22.6 (20) · -0.2 / +13.3 (20) · -9.0 / +20.9 (20) | -26.8 / +68.3 / +60.1 | 0 | 1364 sur 7211 | -2.27 | 60 | non | non | oui | identiques | non |
| gestion-2 | -10.8 / +22.6 (10) · +1.1 / +13.3 (10) · +4.1 / +20.9 (10) | -9.1 / +68.3 / +60.1 | 0 | 1364 sur 7211 | -1.55 | 30 | non | non | oui | identiques | non |
| gestion-3 | +19.7 / +22.6 (3) · +15.0 / +13.3 (3) · +33.7 / +20.9 (3) | +81.2 / +68.3 / +60.1 | 2 | 475 sur 2698 | 0.53 | 9 | non | non | non | identiques | non |
| gestion-4 | -22.7 / +22.6 (30) · -22.5 / +13.3 (28) · -10.1 / +20.9 (29) | -46.7 / +68.3 / +60.1 | 0 | 1364 sur 7211 | -3.13 | 87 | non | non | oui | identiques | non |
| gestion-5 | -4.0 / +22.6 (12) · -33.1 / +13.3 (19) · +16.0 / +20.9 (15) | -26.7 / +68.3 / +60.1 | 0 | 1364 sur 7211 | -2.44 | 46 | non | non | oui | identiques | non |
| groupes-1 | -36.5 / +22.6 (20) · -0.5 / +13.3 (20) · -36.0 / +20.9 (20) | -59.6 / +68.3 / +60.1 | 0 | 191 sur 991 | -3.58 | 60 | non | non | oui | identiques | non |
| groupes-2 | -22.6 / +22.6 (34) · -15.7 / +13.3 (33) · +11.4 / +20.9 (37) | -27.2 / +68.3 / +60.1 | 0 | 52 sur 254 | -1.89 | 104 | non | non | oui | identiques | non |
| groupes-3 | ÉCARTÉE : Le banc n'achète qu'au lendemain d'un formulaire 4 : garder() ne reçoit que les lignes d'evenements.jsonl.gz (formulaires 4) et l'achat se fait au 1er | | | | | | | | | | non |
| groupes-4 | +16.5 / +22.6 (18) · -6.6 / +13.3 (18) · +50.6 / +20.9 (19) | +65.7 / +68.3 / +60.1 | 1 | 23 sur 121 | 0.2 | 55 | non | non | oui | identiques | non |
| initie-1-pdg-dfo | -33.0 / +22.6 (10) · -6.9 / +13.3 (10) · -2.4 / +20.9 (10) | -39.1 / +68.3 / +60.1 | 0 | 328 sur 1643 | -2.37 | 30 | non | non | oui | identiques | non |
| initie-2-historique | -26.9 / +22.6 (10) · -1.8 / +13.3 (10) · +15.3 / +20.9 (10) | -17.8 / +68.3 / +60.1 | 0 | 134 sur 576 | -1.42 | 30 | non | non | oui | identiques | non |
| initie-3-premier-achat | -38.6 / +22.6 (10) · -4.0 / +13.3 (10) · +47.1 / +20.9 (10) | -12.2 / +68.3 / +60.1 | 1 | 403 sur 2081 | -0.96 | 30 | non | non | oui | identiques | non |
| initie-4-engagement | -48.0 / +22.6 (10) · +30.8 / +13.3 (10) · +4.2 / +20.9 (10) | -29.8 / +68.3 / +60.1 | 1 | 251 sur 1331 | -0.64 | 30 | non | non | oui | identiques | non |
| initie-5-combine | -14.4 / +22.6 (10) · -7.5 / +13.3 (10) · +3.5 / +20.9 (10) | -18.1 / +68.3 / +60.1 | 0 | 52 sur 343 | -0.95 | 30 | non | non | oui | identiques | non |
| liquidite_taille-1 | -0.1 / +22.6 (9) · -7.5 / +13.3 (7) · -32.4 / +20.9 (9) | -37.1 / +68.3 / +60.1 | 0 | 582 sur 2925 | -2.0 | 25 | non | non | non | identiques | non |
| liquidite_taille-2 | ÉCARTÉE : Information du futur : le filtre utilise les quantités d'échecs de livraison des 20 jours de bourse avant la date d'entrée, que la SEC publie par demi | | | | | | | | | | non |
| liquidite_taille-3 | +6.5 / +22.6 (5) · +118.2 / +13.3 (5) · -20.6 / +20.9 (5) | +85.2 / +68.3 / +60.1 | 1 | 159 sur 491 | 0.44 | 15 | non | non | non | identiques | non |
| liquidite_taille-4 | +9.7 / +22.6 (4) · +22.5 / +13.3 (4) · +58.9 / +20.9 (4) | +117.9 / +68.3 / +60.1 | 2 | 30 sur 236 | 1.03 | 12 | non | non | non | identiques | non |
| meteo-1 | -16.0 / +22.6 (10) · +22.7 / +13.3 (10) · +59.9 / +20.9 (20) | +65.1 / +68.3 / +60.1 | 2 | 974 sur 5380 | 0.07 | 40 | non | non | oui | identiques | non |
| meteo-2 | -22.4 / +22.6 (20) · +20.4 / +13.3 (10) · +17.3 / +20.9 (10) | +10.2 / +68.3 / +60.1 | 1 | 974 sur 5380 | -1.58 | 40 | non | non | oui | identiques | non |
| meteo-3 | +0.0 / +0.0 (0) · +2.2 / +13.3 (10) · -4.6 / +20.9 (20) | +19.8 / +68.3 / +60.1 | 0 | 974 sur 5380 | -1.8 | 30 | non | non | non | identiques | non |
| meteo-4 | +22.1 / +22.6 (10) · -0.6 / +13.3 (10) · +13.1 / +20.9 (10) | +37.5 / +68.3 / +60.1 | 0 | 249 sur 1252 | -1.0 | 30 | non | non | oui | identiques | non |
| meteo-5 | -22.4 / +22.6 (20) · +0.8 / +13.3 (19) · -0.1 / +20.9 (20) | -22.8 / +68.3 / +60.1 | 0 | 974 sur 5380 | -2.21 | 59 | non | non | oui | identiques | non |
| prix_bas-1 | -8.2 / +22.6 (10) · -9.8 / +13.3 (10) · +2.5 / +20.9 (10) | -14.3 / +68.3 / +60.1 | 0 | 331 sur 1349 | -2.04 | 30 | non | non | oui | identiques | non |
| prix_bas-2 | -38.0 / +22.6 (10) · +72.8 / +13.3 (10) · -30.3 / +20.9 (10) | -23.9 / +68.3 / +60.1 | 1 | 165 sur 1071 | -0.68 | 30 | non | non | oui | identiques | non |
| prix_bas-3 | -37.9 / +22.6 (10) · +8.8 / +13.3 (10) · +14.7 / +20.9 (10) | -23.1 / +68.3 / +60.1 | 0 | 146 sur 866 | -0.76 | 30 | non | non | oui | identiques | non |
| prix_bas-4 | -4.8 / +22.6 (10) · -9.5 / +13.3 (10) · -9.9 / +20.9 (10) | -23.3 / +68.3 / +60.1 | 0 | 92 sur 859 | -1.69 | 30 | non | non | oui | identiques | non |
| sante_valeur-1 | +1.1 / +22.6 (6) · -32.1 / +13.3 (6) · +28.9 / +20.9 (6) | -10.4 / +68.3 / +60.1 | 1 | 28 sur 127 | -1.41 | 18 | non | non | non | identiques | non |
| sante_valeur-2 | +0.5 / +22.6 (6) · +18.9 / +13.3 (6) · +49.2 / +20.9 (6) | +81.3 / +68.3 / +60.1 | 2 | 30 sur 93 | 0.34 | 18 | non | non | non | identiques | non |
| sante_valeur-3 | +1.8 / +22.6 (6) · -27.6 / +13.3 (6) · -11.1 / +20.9 (6) | -33.9 / +68.3 / +60.1 | 0 | 17 sur 109 | -2.72 | 18 | non | non | non | identiques | non |
| sante_valeur-4 | +8.2 / +22.6 (4) · +25.9 / +13.3 (4) · +17.3 / +20.9 (4) | +59.3 / +68.3 / +60.1 | 1 | 25 sur 82 | -0.11 | 12 | non | non | non | identiques | non |
| temoin-meteo | -22.4 / +22.6 (20) · -0.9 / +13.3 (20) · -14.5 / +20.9 (20) | -35.0 / +68.3 / +60.1 | 0 | 974 sur 5380 | -2.54 | 60 | non | non | oui | identiques | témoin |
| vitesse-1 | -55.5 / +22.6 (58) · -72.5 / +13.3 (49) · -91.2 / +20.9 (25) | -99.0 / +68.3 / +60.1 | 0 | 532 sur 886 | -5.13 | 132 | non | non | oui | identiques | non |
| vitesse-2 | -55.0 / +22.6 (77) · -97.3 / +13.3 (58) · -13.8 / +20.9 (1) | -99.0 / +68.3 / +60.1 | 0 | 778 sur 1356 | -4.21 | 136 | non | non | non | identiques | non |
| vitesse-3 | -16.4 / +22.6 (33) · +13.3 / +13.3 (29) · -30.6 / +20.9 (29) | -35.0 / +68.3 / +60.1 | 0 | 433 sur 693 | -1.46 | 91 | non | non | oui | identiques | non |
| vitesse-4 | -43.8 / +22.6 (32) · -33.7 / +13.3 (29) · +21.9 / +20.9 (31) | -54.2 / +68.3 / +60.1 | 1 | 605 sur 973 | -2.14 | 92 | non | non | oui | identiques | non |
