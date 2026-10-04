# Lot K : recherche avant le plan de match (santé financière, F-score de Piotroski 2000)

## A. L'étude
- https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf : lue (876917 octets, SHA-256 901d713553ddaf5b…, 42 pages)
- extraits autour des 9 critères : etude-extraits.txt (7 passages)

## B. Couverture des données officielles de la SEC (exercice 2025, comparé à 2024)
- SalesRevenueNet CY2025 : réponse 404
- SalesRevenueNet CY2024 : réponse 404
- CostOfGoodsSold CY2025 : réponse 404
- CostOfGoodsSold CY2024 : réponse 404

### Compagnies que Radar connaît (fiches SEC lues) : 512
- Règle stricte (chaque donnée publiée) : score complet 51/512 (10 %) · aucune donnée us-gaap : 47 · critères qui manquent le plus : EQ_OFFER 321, ΔLEVER 259, ΔMARGIN 243, ΔTURN 130, ΔLIQUID 118 · scores 0 à 9 : {1: 2, 3: 13, 4: 6, 5: 11, 6: 7, 7: 11, 8: 1}
- Règle souple (dette absente = 0, émission absente = aucune) : score complet 242/512 (47 %) · aucune donnée us-gaap : 32 · critères qui manquent le plus : ΔMARGIN 243, ΔTURN 130, ΔLIQUID 118, ΔROA 87, ΔLEVER 82 · scores 0 à 9 : {1: 3, 2: 6, 3: 36, 4: 34, 5: 55, 6: 38, 7: 43, 8: 21, 9: 6}

### Compagnies des listes du jour : 16
- Règle stricte (chaque donnée publiée) : score complet 1/16 (6 %) · aucune donnée us-gaap : 5 · critères qui manquent le plus : ΔMARGIN 12, EQ_OFFER 11, ΔLEVER 11, ΔLIQUID 8, ΔTURN 7 · scores 0 à 9 : {7: 1}
- Règle souple (dette absente = 0, émission absente = aucune) : score complet 4/16 (25 %) · aucune donnée us-gaap : 5 · critères qui manquent le plus : ΔMARGIN 12, ΔLIQUID 8, ΔTURN 7, ROA 6, ΔROA 6 · scores 0 à 9 : {3: 1, 5: 1, 7: 2}

### Les compagnies des listes du jour, une par une (règle souple)
- GME (CIK 1326380) : F-score 7/9
- PRHI (CIK 1502292) : incomplet, manque ΔLIQUID, ΔMARGIN
- XENE (CIK 1582313) : incomplet, manque ΔMARGIN
- CPHC (CIK 1672909) : incomplet, manque ΔMARGIN
- SAMG (CIK 1549966) : incomplet, manque ΔLIQUID, ΔMARGIN
- PAM (CIK 1469395) : incomplet, manque ROA, CFO, ΔROA, ACCRUAL, ΔLEVER, ΔLIQUID, EQ_OFFER, ΔMARGIN, ΔTURN
- FUL (CIK 39368) : F-score 7/9
- NYAX (CIK 1901279) : incomplet, manque ROA, CFO, ΔROA, ACCRUAL, ΔLEVER, ΔLIQUID, EQ_OFFER, ΔMARGIN, ΔTURN
- CRESY (CIK 1034957) : incomplet, manque ROA, CFO, ΔROA, ACCRUAL, ΔLEVER, ΔLIQUID, EQ_OFFER, ΔMARGIN, ΔTURN
- FLNA (CIK 1069530) : incomplet, manque ΔMARGIN, ΔTURN
- GPUS (CIK 896493) : F-score 5/9
- HELP (CIK 1833141) : incomplet, manque ROA, CFO, ΔROA, ACCRUAL, ΔLEVER, ΔLIQUID, EQ_OFFER, ΔMARGIN, ΔTURN
- TKLF (CIK 1836242) : incomplet, manque ROA, ΔROA, ACCRUAL, ΔLEVER, ΔLIQUID, EQ_OFFER, ΔMARGIN, ΔTURN
- MNSO (CIK 1815846) : incomplet, manque ROA, CFO, ΔROA, ACCRUAL, ΔLEVER, ΔLIQUID, EQ_OFFER, ΔMARGIN, ΔTURN
- QTEX (CIK 1837493) : incomplet, manque ΔMARGIN
- LESL (CIK 1821806) : F-score 3/9

Robots.txt lus : www.ivey.uwo.ca (200), data.sec.gov (404)
