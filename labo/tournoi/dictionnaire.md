# Tournoi Radar — dictionnaire du jeu de recherche

Fait par `labo/tournoi/donnees.py` à partir de sources officielles gratuites de la SEC. Rien du futur : chaque champ
d'un événement n'utilise que ce qui était DÉPOSÉ avant le formulaire 4 de cet événement.

- **Découverte** : formulaires 4 déposés du 1er juillet 2023 au 30 juin 2026 → cache du labo (`cache/decouverte/`, trop
  gros pour la branche) ; le résumé et le journal du calcul → `labo/tournoi/donnees/`. Les programmeurs des règles
  travaillent sur un FAUX jeu au même format (`essais/faux_jeu.py`) ; le juge passe les règles sur le vrai, au labo.
- **Coffre-fort** (examen final) : déposés du 1er janvier 2016 au 30 juin 2023. Jamais dans la branche ; personne ne le
  voit avant l'examen final, où chaque règle finaliste est testée UNE fois.
- Chaque période contient aussi **1 an de dépôts d'avant son début (contexte)** : une règle peut s'en servir (météo des
  initiés, ventes récentes), mais le banc ne les achète jamais. `periode.json` : `{"debut", "fin", "contexte_depuis"}`.
- Dans une règle, `ctx.evenements_avant(cik, depuis)` donne les dépôts d'une compagnie et `ctx.evenements_marche(depuis)`
  ceux de toutes les compagnies, jusqu'au jour de la décision seulement.

## evenements.jsonl.gz (une ligne par formulaire 4 et par sens)

| Champ | Sens |
|---|---|
| `id` | numéro du dépôt + `:achat` ou `:vente` |
| `sens` | `achat` (code P, actions acquises) ou `vente` (code S, actions cédées), en bourse, titres non dérivés |
| `depot` | date du dépôt à la SEC (AAAA-MM-JJ). L'HEURE est inconnue : on peut acheter au plus tôt à la clôture du 1er jour de bourse APRÈS le dépôt |
| `jour_premier`, `jour_dernier` | dates de la 1re et de la dernière transaction du formulaire |
| `cik`, `symbole`, `symbole_ecrit`, `nom` | la compagnie ; `symbole` au format des prix (« BRK.B » → « BRK-B »), `None` s'il est illisible |
| `inities` | les déclarants : `cik`, `nom`, `roles` (administrateur, dirigeant, actionnaire de 10 %, autre), `titre` (texte libre, ex. « CEO/President ») |
| `actions`, `montant`, `prix_moyen` | total du formulaire pour ce sens (`montant` et `prix_moyen` : lignes avec un prix seulement) |
| `apres`, `avant` | actions détenues après et avant, dans le groupe de lignes (direct ou indirect, même titre) le plus gros ; `avant` = `None` si la déclaration est incohérente |
| `part` | actions achetées (ou vendues) ÷ détenues avant ; `None` si `avant` est 0 ou inconnu |
| `nouvelle_position` | achat d'un initié qui n'en détenait aucune (dans ce groupe de lignes) |
| `direct` | au moins une ligne détenue directement |
| `plan_10b5_1` | case du formulaire (depuis avril 2023) : `true`, `false`, ou `null` (pas remplie) |
| `titres` | titres déclarés (ex. « Common Stock ») |
| `routinier`, `mois_routine` | règle de Radar (Cohen, Malloy et Pomorski 2012) : un des déclarants a acheté ou vendu en bourse des actions de cette compagnie dans un même mois, chacune des 3 années civiles avant ; d'après les formulaires déposés avant |
| `groupe_30j` | achats seulement : nombre d'initiés différents qui ont acheté la même compagnie dans les 30 jours avant le dépôt (celui-ci compris) |
| `achats_90j`, `ventes_90j` | nombre de formulaires d'achat et de vente sur la même compagnie dans les 90 jours avant (pas le jour même) |
| `historique` | achats seulement : `achats_avant` (achats en bourse de l'initié depuis 2012, toutes compagnies) et `jours_depuis_achat_meme_cie` ; s'il y a plusieurs déclarants, celui qui a le plus d'achats |
| `bilan_initie` | achats seulement : ses achats passés (déposés 60 jours ou plus avant, dès juillet 2015) mesurés 1 mois contre le S&P 500 (SPY) : `mesures`, `ecart_moyen`, `part_gagnante` |
| `cloture_avant` | [date, prix, CUSIP] : dernière clôture de la SEC au plus tard la veille du dépôt (30 jours au plus) |
| `actions_circulation`, `valeur_m` | actions en circulation (fait XBRL déposé avant) et valeur en bourse en M$ |
| `13d_90j`, `13g_90j` | 13D et 13G ORIGINAUX (pas les modifications) sur la compagnie, déposés dans les 90 jours avant (jour du dépôt compris) |

## prix.jsonl.gz (une ligne par symbole)

`{"s": symbole, "d": [dates de clôture AAAAMMJJ], "p": [prix], "q": [quantité d'échecs de livraison], "c": [CUSIP]}`

- Source : fichiers d'échecs de livraison de la SEC. Les QUANTITÉS d'échecs sont publiées par demi-mois, quelques
  semaines plus tard : dans une règle, `ctx.echecs()` ne montre que celles d'au moins 35 jours civils avant.
  Pour une date de règlement, la SEC donne la clôture du jour ouvrable
  d'avant ; la date gardée est la date de règlement précédente du calendrier des fichiers (décalage possible d'un jour
  autour des congés des banques où la bourse est ouverte).
- **Un titre a un prix seulement les jours où il a des échecs de livraison** : souvent pas tous les jours pour les
  petites compagnies. Pas de volume, pas d'ouverture.
- Un changement de CUSIP = regroupement d'actions ou nouveau titre : ne pas comparer deux prix de CUSIP différents.
- Marché : `SPY`, `IVV`, `VOO` (S&P 500) et `IWM` (Russell 2000).
- Découverte : prix du 1er juillet 2022 à mi-septembre 2026 (les derniers fichiers publiés).
- Aucune source gratuite des clôtures de CHAQUE jour n'est permise : Stooq interdit les robots (robots.txt).

## finances.jsonl.gz (une ligne par compagnie avec un achat)

`{"cik": ..., "faits": {concept: [[début, fin, valeur, numéro du dépôt, déposé_le, forme], ...]}}` — tiré du fichier
complet de la SEC (companyfacts.zip). Concepts : Assets, Liabilities, StockholdersEquity, AssetsCurrent,
LiabilitiesCurrent, LongTermDebtNoncurrent (bilans : `début` = null, à la date `fin`) ; NetIncomeLoss,
NetCashProvidedByUsedInOperatingActivities, Revenues, RevenueFromContractWithCustomerExcludingAssessedTax,
SalesRevenueNet, GrossProfit (durées : un trimestre de 80 à 100 jours, ou un exercice de 350 à 380 jours).
- Formes : 10-K (rapport annuel), 10-Q (trimestriel), et leurs modifications (/A).
- Pour chaque période : la **PREMIÈRE version déposée** (une correction déposée plus tard n'était pas connue avant).
- `déposé_le` = la vraie date de dépôt : le banc ne montre un chiffre qu'à partir de cette date.
- Dans une règle : `ctx.finances(cik)` → `{concept: [[début, fin, valeur, forme], ...]}` (déposés au plus tard ce
  jour-là, la fin la plus récente en dernier).
- Gardé : périodes finies au plus 2 ans (et 1 mois) avant le début de la période (assez pour comparer 2 exercices).

## historiques.jsonl.gz (une ligne par initié qui achète dans la période)

`{"initie": cik, "depots": [[dépôt, cik de la compagnie, symbole, sens, jour_premier, jour_dernier, actions, prix_moyen], ...]}`
— TOUS ses dépôts de formulaires 4 originaux avec un achat ou une vente en bourse (un par sens), dans toutes ses
compagnies, depuis le plus ancien jeu de données de la SEC offert (2006 si disponible). Dans une règle :
`ctx.historique_initie(cik, depuis)` ne donne que les dépôts faits au plus tard le jour de la décision. Pour juger un
achat passé, `ctx.clotures(symbole, depuis, jusqu_a)` (prix depuis juillet 2015).

## 13d13g.jsonl.gz (une ligne par compagnie)

`{"cik": ..., "depots": [[date, forme], ...]}` — formes : 13D, 13D/A, 13G, 13G/A (index trimestriels d'EDGAR).

## calendrier.json

Les dates de clôture (jours de bourse) du calendrier des fichiers d'échecs.

## resume.json, journal.md

Nombres de lignes, couverture (part des achats avec symbole, prix, valeur en bourse…) et journal du calcul. Pour le
coffre-fort : des NOMBRES de lignes seulement, aucun rendement.
