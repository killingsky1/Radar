# La grande chasse — plan figé AVANT de voir les résultats (9 octobre 2026)

Le défi de Mathieu : « trouve un moyen », avec ce qu'un système peut faire et un humain non. Ce plan est écrit et
enregistré sur GitHub AVANT le premier calcul sur les vraies données : rien n'y sera changé après coup pour « trouver »
un gagnant (la même discipline que le tournoi, labo/tournoi/RAPPORT.md).

## L'idée
Au lieu de 38 règles écrites à la main, un modèle apprend tout seul, sur des dizaines d'indices à la fois, ce qui
distingue les achats de dirigeants suivis d'une hausse de ceux suivis d'une baisse. Il n'apprend QUE du passé :
chaque année, il est réentraîné avec les années d'avant seulement, puis choisit ses achats de l'année suivante, comme
Radar l'aurait fait en vrai.

## Les données (celles du tournoi, sans rien changer)
Les achats en bourse de dirigeants (formulaire 4, code P) de janvier 2016 à juin 2026 (coffre-fort + découverte), les
prix officiels de la SEC (fichiers d'échecs de livraison), les finances XBRL à leur vraie date de dépôt, les 13D/13G.
Chaque indice est calculé avec ce qui était déposé au plus tard le jour du formulaire 4 (le Contexte du banc : une
demande du futur lève une erreur ; les finances, les actions et les quantités d'échecs sont lues de la même façon).

## Les indices (fixés ici)
1. Qui achète : PDG, chef des finances, président du conseil, président, chef de l'exploitation, administrateur,
   dirigeant, actionnaire de 10 %, nombre de déclarants.
2. Combien et comment : montant (log), part de ses actions, nouvelle position, détention directe, plan 10b5-1,
   initié routinier, délai entre l'achat et le dépôt, achat étalé sur plusieurs jours, prix payé contre la dernière
   clôture.
3. L'initié : ses achats passés (nombre), jours depuis son dernier achat de la même compagnie, son bilan passé
   (mesures, écart moyen, part gagnante).
4. Les autres initiés et les gros joueurs : nombre d'initiés qui achètent en 30 jours, achats et ventes en 90 jours,
   ventes en 365 jours, 13D et 13G en 90 jours.
5. Le prix (SEC, même code de titre) : rendement sur 1, 3, 6 et 12 mois avant, écart au plus haut et au plus bas de
   12 mois, volatilité, niveau du prix (log), présence dans les fichiers d'échecs (jours avec un prix sur 3 mois),
   échecs de livraison publiés ÷ actions en circulation.
6. La compagnie : valeur en bourse (log), rendement de l'actif, dette ÷ actif, liquidité courante, argent généré ÷
   actif, croissance des ventes, perte, valeur comptable ÷ valeur en bourse, émission d'actions sur 1 an, âge des
   derniers chiffres.
7. Le marché : S&P 500 sur 1 et 3 mois, petites contre grandes (IWM − SPY) sur 3 mois, « météo » des initiés (part des
   achats parmi les formulaires 4 de tout le marché sur 30 jours).

## Ce que le modèle apprend
- Cible : le rang (0 à 1) du rendement NET de l'achat contre le S&P 500 parmi les achats du même mois de dépôt.
  Rendement net = achat à la clôture SEC du 1er jour de bourse après le dépôt (3 jours de plus au plus), vente H jours
  de bourse plus tard (comme le banc : 10 jours de plus au plus, sinon le dernier prix), moins le demi-écart
  achat-vente du banc à l'achat et à la vente, moins le S&P 500 (SPY) aux mêmes dates.
- Modèle : arbres de décision boostés (scikit-learn HistGradientBoostingRegressor : 300 arbres, taux 0,05, 31 feuilles,
  au moins 200 achats par feuille, régularisation 1,0, graine 0). Les indices manquants restent manquants.
- Années de juillet à juin. Pour l'année qui commence le 1er juillet T : entraîné sur les achats de 2016 dont la vente
  (la cible) est terminée AVANT T. Années testées : 2017-2018 à 2025-2026 (9 ans).

## Comment on le juge : le banc du tournoi, tel quel
- Une « règle » : garder un achat si son score est dans les 10 % les plus hauts (le seuil vient des scores de
  l'entraînement, jamais de l'année testée) ; à places égales, le meilleur score d'abord. 10 positions au plus,
  garder H jours de bourse, l'argent qui attend dans SPY, frais du banc (10 $ par transaction + demi-écart selon la
  taille, à l'achat et à la vente).
- 3 durées, fixées ici : H = 63 (3 mois), 126 (6 mois), 252 (12 mois) jours de bourse.
- Passé sur le banc pour le coffre-fort (de juillet 2017 à juin 2023) et la découverte (juillet 2023 à juin 2026).

## Pour réussir (fixé ici, plus sévère que le tournoi : 3 durées essayées)
Sur les 9 ans (juillet 2017 à juin 2026), pour au moins une durée :
- battre le S&P 500 (10 000 $ gardés dans SPY) au total, après les frais ;
- gagner au moins 6 années sur 9 ;
- t ≥ 2,4 (écart moyen des transactions contre SPY ; 2,4 au lieu de 2 parce que 3 durées sont essayées).
Si une durée réussit : examen final sur des années jamais utilisées (2009-2015, données de la SEC à bâtir) AVANT toute
entrée dans Radar. Si aucune ne réussit : on le dit, chiffres à l'appui, et Radar ne change pas.

## Aussi mesuré (pour comprendre, pas pour juger)
Par année testée : rendement net moyen des 10 % les mieux notés contre tous les achats, corrélation de rang entre le
score et le résultat.
