# Chasse 2 — résultats (9 octobre 2026)

Plan figé AVANT tout calcul : labo/chasse2/PLAN.md (avec ses deux corrections de données, faites avant les calculs
qu'elles touchent). Chiffres bruts : resultats_c/, resultats_b/ (prix nettoyés) et resultats_*_sans_nettoyage/ (1er
jugement). 14 années jugées : juillet 2012 à juin 2026 ; examen : 2012-2017 (jamais vu). Critère : battre SPY au total
après les frais, gagner au moins 9 années sur 14 (C : 2 sur 3 parmi celles avec un pari), t ≥ 2,4 sur l'écart mensuel,
et battre SPY sur 2012-2017.

## Les données (mesurées)
1 246 508 achats et ventes d'initiés (2006 à juin 2026, 14 723 compagnies) ; finances XBRL de 16 738 compagnies ;
516 789 dépôts 13D et 13G ; prix de la SEC de juin 2009 à septembre 2026 (23,1 millions de clôtures, 57 024 symboles) ;
168 requêtes à la SEC. Prix bidons retirés (correction 2) : 99 581 prix de 0,01 $ et 8 593 écarts qui reviennent.
Fractionnements confirmés : 297 (AAPL 7 pour 1 en 2014 et 4 pour 1 en 2020, etc.).

## Verdict

| Chasse | 14 ans | SPY | Années | t mensuel | 2012-2017 | Réussi |
|---|---|---|---|---|---|---|
| C, météo des initiés (10 $) | +628,5 % | +447,2 % | 6 sur 8 avec un pari | 1,31 | +77,0 % contre +77,2 % | NON |
| C, météo des initiés (0 $) | +635,8 % | +447,2 % | 6 sur 8 avec un pari | 1,34 | +77,5 % contre +77,2 % | NON |
| B, tout le marché (0 $) | +57,7 % | +447,2 % | 5 sur 14 | −1,77 | −3,8 % contre +77,2 % | NON |
| B, tout le marché (10 $) | −100,1 % | +447,2 % | 1 sur 14 | −1,31 | −100,0 % | NON |
| A, lire les 10-K | en cours (lecture des 10-K) | | | | | |

### C — pourquoi non
Elle bat SPY au total surtout par le levier (SSO, 2 fois le S&P 500) dans un marché qui monte : l'essai sans signal
(essai_chasse_c.py) bat SPY au total lui aussi (+170 % contre +91 %) ; c'est pourquoi le plan exige t ≥ 2,4. Ici t = 1,31
(6 paris en 14 ans : trop peu pour conclure). Elle a tenu SSO pendant la chute de février 2020 et de mai à novembre 2022.
SSO réel n'avait une clôture de la SEC que 75 % des jours : le SSO calculé du plan a servi (4 fractionnements de SSO
repérés : 2015, 2020, 2022, 2025).

### B — pourquoi non
Le modèle ne trouve rien dans les 1 000 plus grosses compagnies : corrélation de rang moyenne 0,002 (de −0,05 à +0,07
selon l'année, 12 000 cas par année). Comme l'annonçait Avramov, Cheng et Metzker (Management Science 2023) : hors des
très petites compagnies, l'avantage des modèles disparaît. Et il change presque tout le portefeuille chaque mois (1 348
achats en 14 ans) : à 10 $ la transaction, le compte s'épuise (les frais pèsent de plus en plus lourd à mesure qu'il
fond ; il finit même un peu sous zéro parce qu'une commission dépasse ce qui reste d'une position, détail sans effet sur
le verdict).

## Les prix bidons de la SEC (trouvés ici, réparés partout)
La sonde (sonde_prix.json) : des prix de 0,01 $ (parfois 1,00 $) entre de vrais prix, souvent au 1er jour d'un nouveau
code du titre (AON 1er avril 2020, GMCR mars 2014, AVGO janvier 2016, PCYC mai 2015). B et C rejugées avec les prix
nettoyés (rien d'autre changé) : C identique, B +57,7 % au lieu de +63,1 % (0 $). Le banc du tournoi nettoie aussi
maintenant : le tournoi rejugé est identique au chiffre près ; la 1re chasse passe de +121,7 % à +2,0 % (6 mois), son
verdict ne change pas.
