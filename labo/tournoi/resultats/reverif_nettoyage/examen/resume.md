# Tournoi : EXAMEN FINAL (coffre-fort, janvier 2016 à juin 2023), une seule fois par règle

Données : `cache/coffre`. Par année : portefeuille / S&P 500 gardé, en % (achats). Période entière : portefeuille / S&P 500 / petites compagnies (IWM), en %. t = écart mensuel avec le S&P 500, sur les mois de la période. Sans prix : signaux jamais achetés faute de prix de la SEC.

| Règle | Années | Période entière | Années gagnées | Sans prix | t | Achats | 1. bat le S&P 500 sur 7,5 ans | 2. au moins 5 années sur 7 | 3. t ≥ 2 | 2 programmations | Passe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gestion-3 | +4.6 / +15.3 (3) · +8.2 / +11.8 (3) · -3.1 / +7.8 (3) · -5.2 / +4.3 (3) · +47.1 / +37.9 (3) · -10.8 / -12.4 (3) · +6.6 / +16.3 (3) | +90.9 / +120.5 / +70.4 | 2 | 693 sur 7827 | -0.18 | 21 | non | non | non | identiques | non |
| liquidite_taille-3 | +10.3 / +15.3 (5) · +33.8 / +11.8 (5) · -24.8 / +7.8 (5) · -8.9 / +4.3 (5) · +109.0 / +37.9 (5) · +18.0 / -12.4 (5) · +20.2 / +16.3 (5) | +195.8 / +120.5 / +70.4 | 4 | 409 sur 1972 | 0.63 | 35 | oui | non | non | identiques | non |
| liquidite_taille-4 | +37.5 / +15.3 (4) · +40.0 / +11.8 (4) · -19.9 / +7.8 (4) · +25.0 / +4.3 (4) · +96.5 / +37.9 (4) · -14.5 / -12.4 (4) · +33.3 / +16.3 (4) | +362.9 / +120.5 / +70.4 | 5 | 28 sur 471 | 1.89 | 28 | oui | oui | non | identiques | non |
