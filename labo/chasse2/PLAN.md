# Chasse 2 — plan figé AVANT tout calcul sur les rendements (9 octobre 2026)

La 1re chasse (labo/chasse/RAPPORT.md) a cherché là où les humains cherchent : suivre les achats des dirigeants, surtout
dans de petites compagnies où les frais et l'écart achat-vente mangent tout. Ici, on cherche là où une machine a un vrai
avantage : (A) lire tous les rapports annuels, (B) regarder tout le marché liquide à la fois, (C) la météo des initiés de
toute la bourse. Rien ici ne sera changé après coup pour « trouver » un gagnant.

## Les données (labo/chasse2/donnees2.py, sources officielles gratuites de la SEC)
Prix : clôtures des fichiers d'échecs de livraison, tous les symboles, de fin juin 2009 (le plus ancien fichier offert)
à septembre 2026. Initiés : formulaires 4 originaux avec achat (P) ou vente (S) en bourse, 2006 à 2026. Finances et
actions en circulation : XBRL (companyfacts), PREMIÈRE version déposée, utilisable dès sa date de dépôt. 13D et 13G :
index d'EDGAR, 2009 à 2026. Rapports annuels (chasse A) : le document principal de chaque 10-K, sur EDGAR.
Rien n'est utilisé avant sa date de dépôt (ou avant la clôture où il est connu).

## Les années jugées
Années de juillet à juin, de 2012-2013 à 2025-2026 (14 ans). Pour chaque année, un modèle n'apprend QUE des mois dont
le résultat est connu avant le 1er juillet. 2012-2017 n'a jamais servi à rien (examen) ; 2017-2026 a servi aux autres
chasses, mais pour d'autres règles.

## L'univers (B et A) : les 1 000 plus grosses compagnies
À chaque fin de mois : symboles avec une clôture de la SEC dans les 5 derniers jours de bourse, prix ≥ 5 $, reliés à une
compagnie (le symbole écrit dans ses formulaires 4 des 24 derniers mois ; s'il y en a plusieurs, celle qui en a le plus),
avec des actions en circulation déposées (fin de période dans les 400 jours). Valeur en bourse = prix × actions. Les
1 000 plus grosses. Frais minimes et prix presque tous les jours.

## Chasse B — tout le marché
- Chaque fin de mois, chaque compagnie de l'univers reçoit un score d'un modèle (scikit-learn
  HistGradientBoostingRegressor, mêmes réglages que la 1re chasse : 300 arbres, taux 0,05, 31 feuilles, 200 au moins par
  feuille, régularisation 1,0, graine 0 ; les indices manquants restent manquants).
- Cible apprise : le rang (0 à 1), dans le mois, du rendement du mois suivant moins SPY (clôtures de la SEC, enchaînées
  si le code du titre change ; une compagnie qui disparaît : sa dernière clôture).
- Indices (connus à la fin du mois) : rendements 1, 3, 6 mois et 12 mois sans le dernier ; volatilité (63 jours) ; écart
  au plus haut de 12 mois ; valeur en bourse (log) ; valeur comptable, bénéfice, ventes et argent généré (dernier
  exercice) ÷ valeur en bourse ; rendement de l'actif ; marge brute ÷ actif ; écart bénéfice − argent généré ÷ actif ;
  dette ÷ actif ; liquidité courante ; croissance des ventes, de l'actif et du nombre d'actions sur 1 an ; achats et
  ventes des initiés (90 et 365 jours), achat d'un PDG ou d'un chef des finances (180 jours), montant acheté ÷ valeur en
  bourse (365 jours) ; 13D et 13G (365 jours) ; échecs de livraison ÷ actions (21 jours) ; SPY sur 1 et 3 mois, IWM −
  SPY sur 3 mois, météo des initiés (ci-dessous).
- Portefeuille : chaque fin de mois, les 10 meilleurs scores. Au 1er jour de bourse après : on vend ce qui n'y est plus,
  on achète ce qui entre (part égale), on garde ce qui reste. L'argent qui attend : SPY.

## Chasse A — lire les rapports annuels (« Lazy Prices », Cohen, Malloy et Nguyen, Journal of Finance 2020)
- Chaque 10-K d'une compagnie de l'univers est comparé à son 10-K précédent (déposé 300 à 430 jours avant) : similarité
  cosinus des fréquences de mots (texte du document principal, balises retirées, mots en lettres, minuscules).
- « Ne change pas » : similarité dans les 20 % les plus hautes des 10-K déposés les 12 mois AVANT (jamais après).
- Achat à la clôture du 1er jour de bourse après le dépôt, gardé 252 jours de bourse (12 mois : dans l'étude, le gain
  s'accumule sur 12 à 18 mois) ; 10 positions au plus ; à places égales, la plus haute similarité d'abord ; l'argent qui
  attend dans SPY. Le banc du tournoi, tel quel.

## Chasse C — la météo des initiés (Seyhun 1992 ; Lakonishok et Lee 2001)
- Chaque jour de bourse : parmi les formulaires 4 déposés les 30 jours d'avant (jusqu'à la veille), part des compagnies
  avec un achat parmi les compagnies avec un achat ou une vente. Son rang parmi ses valeurs des 5 années d'avant.
- Normalement : SPY. Quand la part est dans les 10 % les plus hautes de ses 5 années d'avant (les initiés achètent en
  masse) : SSO (S&P 500 deux fois par jour) pour les 126 jours de bourse suivants (6 mois).
- Si SSO a une clôture de la SEC moins de 90 % des jours de bourse : un SSO calculé (2 fois le rendement de SPY du jour,
  moins 0,89 % par année, les frais de SSO), dit dans le résultat.
- Limite connue, dite d'avance : les prix commencent en juillet 2009, donc la chute de 2008 (où les initiés achetaient
  aussi en masse avant une autre baisse) n'est pas dans le test.

## Les frais (deux scénarios, fixés ici)
Écart achat-vente du banc du tournoi selon la valeur en bourse, à l'achat et à la vente, et commission : 10 $ par
transaction (banc du tournoi) ou 0 $ (courtier sans commission). Le verdict utilise les vrais frais de Mathieu ; tant
qu'il ne les a pas donnés : 10 $. Les deux sont montrés.

## Pour réussir (fixé ici)
Pour une chasse : sur les 14 ans (juillet 2012 à juin 2026), après les frais,
- battre SPY au total ;
- gagner au moins 9 années sur 14 (C : au moins 2 années sur 3 parmi celles où elle a fait un pari, et pas de perte
  contre SPY sur l'ensemble des autres) ;
- t ≥ 2,4 sur l'écart MENSUEL du portefeuille contre SPY ;
- et sur 2012-2017 seulement (jamais vu) : battre SPY au total.
Si une chasse réussit : elle est suivie dans l'app comme une information (jamais une promesse), avec ses vrais chiffres.
Si aucune ne réussit : on le dit, chiffres à l'appui, et Radar ne change pas.

## Correction du plan (9 octobre 2026, AVANT tout calcul sur les rendements)
Les clôtures de la SEC ne sont pas corrigées des fractionnements d'actions, et un fractionnement garde en général le
même code de titre (CUSIP) : un 10 pour 1 aurait l'air d'une chute de 90 %. Règle, pour toutes les chasses : entre deux
clôtures du même code de titre, un rapport de prix à 5 % près de 1/N ou de N (N entier de 2 à 50) est un fractionnement
(ou un regroupement) si c'est confirmé : pour une compagnie, ses actions en circulation (les dernières avant, les
premières après, déposées dans les 400 jours) changent du même facteur à 20 % près ; pour un fonds coté (SPY, SSO…), SPY a
bougé de moins de 5 % ce jour-là. Le rendement est alors corrigé du facteur N. Les fractionnements trouvés sont listés
dans les résultats.

## Contrôles avant la vraie course
Pour B (et A, C) : un faux jeu avec un signal caché (il doit être trouvé et réussir) et le même sans signal (rien ne
doit réussir, aucune fuite du futur), comme labo/chasse/essai_chasse.py.
