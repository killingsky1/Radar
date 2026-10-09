# Tournoi Radar — rapport final (8 octobre 2026)

## Le verdict
**Aucune règle n'a réussi.** Sur 38 règles écrites d'avance par des chercheurs à partir d'études, aucune n'a battu le
S&P 500 de façon fiable après les frais : ni sur la découverte (juillet 2023 à juin 2026), ni à l'examen final
(janvier 2016 à juin 2023, données jamais vues). Une seule s'en est approchée (voir « La piste »).

## Comment on a testé (pour que le résultat soit vrai)
1. **Étape 1** : 8 chercheurs et 1 critique ont écrit 38 règles AVANT de voir les données (enregistrées sur GitHub).
   Les études citées ont été vérifiées : 116 sur 122 confirmées ; 4 erreurs de citation trouvées (voir plus bas).
2. **Étape 0** : un jeu de recherche tiré seulement de la SEC (achats d'initiés depuis 2006, prix des fichiers
   d'échecs, finances XBRL, 13D) : 37 574 achats d'initiés dans la découverte.
3. **Étape 2** : chaque règle programmée 2 fois par 2 agents qui ne se voient pas ; les 2 programmes donnent exactement
   les mêmes achats et ventes (37 règles), 2 règles écartées (information du futur ; achat au dépôt d'un 13D).
   Frais réels : 10 $ par transaction et l'écart achat-vente selon la taille.
4. **Étape 3** : débat (un avocat, deux sceptiques par règle) sur les 3 meilleures, puis un juge.
5. **Étape 4** : examen final, une seule fois, sur 7,5 ans jamais utilisés.

## Découverte (juillet 2023 à juin 2026)
Pour passer : battre le S&P 500 chacune des 3 années, t ≥ 3, et au moins 30 achats. **Aucune règle ne passe.**
Le meilleur t est 1,03 (il fallait 3). La plupart des règles font PIRE que le S&P 500 : les compagnies où les
dirigeants achètent (petites et moyennes) ont traîné derrière les géants de la techno pendant ces 3 ans.

## Examen final (janvier 2016 à juin 2023, une seule fois)
Pour réussir : battre le S&P 500 sur 7,5 ans, au moins 5 années sur 7, et t ≥ 2.

| Règle | Total | S&P 500 | Années gagnées | t | Réussit ? |
|---|---|---|---|---|---|
| liquidite_taille-4 (grandes compagnies ≥ 10 G$, achat du PDG ou du chef des finances, garder 12 mois) | +362,9 % | +120,5 % | 5 sur 7 | 1,89 | non (t < 2) |
| liquidite_taille-3 (petites compagnies de qualité, l'initié grossit vraiment sa part, 12 mois) | +195,8 % | +120,5 % | 4 sur 7 | 0,63 | non |
| gestion-3 (70 % S&P 500 + 3 meilleures idées, 12 mois) | +90,9 % | +120,5 % | 2 sur 7 | −0,18 | non |

## La piste (pas une preuve)
**liquidite_taille-4** est la seule règle qui bat le S&P 500 dans les DEUX périodes : +117,9 % contre +68,3 %
(2023-2026) et +362,9 % contre +120,5 % (2016-2023). Mais :
- son t (1,89) n'atteint pas 2 ; avec 3 règles examinées, un tel résultat peut encore venir du hasard ;
- son avance vient de quelques gros rebonds achetés après une chute (Freeport et LyondellBasell en mars 2020,
  Centene en août 2025) ; la transaction médiane est presque nulle et la moitié seulement battent le S&P 500 ;
- elle n'achète que 4 actions par année.
Bonne nouvelle quand même : c'est une idée simple et logique (un grand patron qui achète avec son argent après une
chute de son action), avec des frais faibles (grandes compagnies).

## Erreurs trouvées et corrigées en route (toutes avant l'examen)
- Les actions en circulation par fin de période manquaient au jeu (3 règles écartées à tort) : ajoutées.
- Environ 2 jours par an (Columbus Day, Veterans Day), un prix venait du lendemain : mesuré, corrigé, re-mesuré.
- 2 fichiers de la SEC jamais lus (nom en « _0 ») : un trou de 13 jours en août 2023 et d'octobre 2019 : corrigé.
- Des 13D comptés pour la compagnie qui les dépose (ex. Disney) : corrigé (9 % des 13D).
- Le juge ne comparait pas les positions encore ouvertes entre les 2 programmes : ajouté (toujours identiques).
- « d'actions ordinaires » et « au minimum 1 000 $ » lus de la même façon partout.
Limites qui restent : les fractionnements d'actions ne sont pas corrigés dans la valeur en bourse ; les prix de la SEC
ne comptent pas les dividendes ; un prix n'existe que les jours d'échecs de livraison ; le 2e tour du débat a été fait
par l'orchestrateur (limite hebdomadaire des agents).

## Erreurs de citation trouvées dans les études (étape 1)
- meteo-2 : une étude attribuée à Cziraki n'est pas de lui.
- gestion-2 : DOI 12877 au lieu de 12878.
- gestion-3 : Amenc, 443325 au lieu de 443322 ; Bettis, 2116 au lieu de 2118.
Références douteuses : un article de presse (Bloomberg) cité comme étude ; « Étude 2025 » trop vague (groupes-1) ;
un PDF de Kang, Kim et Wang sur un site non universitaire.

## Fichiers
Règles : regles_preenregistrees.json · règles du jeu et changements datés : regles_du_jeu.md · programmes : regles/
et regles_verif/ · résultats : resultats/decouverte/ et resultats/examen/ · débat : resultats/debat/.

## Contre-vérification avec les prix nettoyés (9 octobre 2026)
La chasse 2 a trouvé des prix bidons dans les fichiers de la SEC (0,01 $, parfois 1,00 $, souvent au 1er jour d'un
nouveau code du titre ; labo/chasse2/sonde_prix.json). Le banc les retire maintenant (banc.nettoyer_prix). Les 39 règles
(découverte) et les 3 finalistes (coffre-fort) ont été rejugés avec les prix nettoyés, sans rien changer d'autre
(labo96 ; resultats/reverif_nettoyage ; ce n'est pas un 2e examen). Résultat : identique au chiffre près (aucune règle
ne réussit ; liquidite_taille-4 : t 1,89 à l'examen). Les transactions et les fins de mois du tournoi n'ont jamais
touché un prix bidon ; le verdict et les chiffres du tournoi tiennent. (La 1re chasse, elle, en avait touché : voir
labo/chasse/RAPPORT.md.)
