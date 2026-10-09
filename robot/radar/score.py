"""Score par compagnie : où va le gros argent, preuves à l'appui. Pas un conseil financier.

Chaque info officielle sur une compagnie cotée vaut des points selon ce que les études ont mesuré (REGLES).
- Les points fondent avec le temps : moitié après 30 jours (60 pour les grands fonds, qui déclarent en retard).
  Après 90 jours, une info ne compte plus.
- Dans une même famille de sources, seule l'info la plus forte compte : 7 administrateurs qui achètent le même jour
  forment UN groupe d'achats (avec son bonus), pas 7 fois les points. Le même achat déclaré par un administrateur
  et par son fonds ne compte donc qu'une fois.
- Plusieurs familles qui pointent dans le même sens : +25 % par famille de plus (choix du modèle, pas une étude).
- Lot L : un achat ou une vente d'un initié « routinier » (même mois chaque année, Cohen, Malloy et Pomorski 2012) :
  0 point ; un achat de dirigeant dans une petite compagnie (sous le 30e centile du NYSE) : ×1,5 (Lakonishok et Lee
  2001 ; voir collecteurs/inities.py et collecteurs/taille.py).
- Lot M : une compagnie de moins de 100 M$ en bourse n'entre pas dans la liste « hausse » : dans le rejeu de 3 ans du
  labo (juillet 2023 à juin 2026), ces entrées ont fait pire que le S&P 500 chacune des 3 années. Elle est montrée à
  part (« écartées ») et suivie dans les Résultats, pour vérifier la règle en vrai.
- Seules les infos « Officiel » ou « Confirmé » de sources officielles comptent.
Les infos sans points (contexte) restent visibles avec la raison.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from .collecteurs import inities
from .registry import SOURCES

VERSION = "score-9"
DEMI_VIE = 30
DEMI_VIE_FONDS = 60  # le 13F arrive jusqu'à 45 jours après la fin du trimestre
AGE_MAX = 90
# Note sur 10 (lot B, 3 octobre 2026) : 5 = neutre ; 6 points ou plus = 10/10 ; −6 ou moins = 0/10. Une seule famille
# plafonne à 5,25 points (achat du PDG en groupe : 2 × 1,5 × 1,75), soit 9,4/10 : 10/10 demande plusieurs familles.
POINTS_POUR_10 = 6
NOTE_HAUSSE = 7.0  # liste « hausse » : 7/10 et plus (2,34 points et plus : 6,95 s'arrondit à 7,0)
NOTE_BAISSE = 3.0  # liste « baisse » : 3/10 et moins
JOURS_RECENT = 3  # « Récent » : preuve déposée il y a moins de 3 jours de bourse (la réaction du cours suit le dépôt)
BONUS_FAMILLE = 0.25
MAX_LISTE = 20
MAX_CONTEXTE = 5
JOURS_GROUPE = 2  # jours ouvrables (comme dans l'étude d'Alldredge et Blank)
ROLE_PRINCIPAL = 1.5
ROLE_GROS_ACTIONNAIRE = 0.5
GROUPE = 1.75  # 2,1 % contre 1,2 % le mois suivant (Alldredge et Blank)
# Lakonishok et Lee (2001, tableau 8) : signal d'achat fort 7,27 % par an dans les petites compagnies contre 4,82 % pour
# l'ensemble (×1,51) ; Cohen, Malloy et Pomorski (2012, tableau IX) : 0,80 contre 0,55 % par mois (×1,45).
PETITE = 1.5
# Lot M : sous 100 M$ en bourse (taille connue), pas dans la liste « hausse ». Rejeu de 3 ans du labo, garder 1 mois :
# écart médian avec le S&P 500 de −11,8 / −6,6 / −1,3 % (2023-2024 / 2024-2025 / 2025-2026), contre −2,0 / −3,1 / −0,2 %
# pour les autres entrées ; 35 / 30 / 48 % ont battu le S&P 500, contre 41 / 41 / 49 %.
TROP_PETITE = 100  # M$

# PDG, directeur financier, président du conseil (pas les vice-présidents ni les vice-présidents du conseil)
PRINCIPAL = re.compile(r"\b(CEO|CFO|PEO|PFO|COB)\b|CHIEF EXECUTIVE|CHIEF FINANCIAL|(?<!VICE )(?<!VICE-)\bCHAIR", re.I)

ETUDES = {
    "lakonishok_lee": ("Lakonishok et Lee (2001)",
                       "Les achats des dirigeants prédisent les rendements, surtout dans les petites compagnies (7,27 % "
                       "par an contre 4,82 % pour l'ensemble) ; leurs ventes, non.",
                       "https://www.lsvasset.com/pdf/research-papers/Insider-Trades-Informative.pdf"),
    "cohen_malloy_pomorski": ("Cohen, Malloy et Pomorski (2012)",
                              "Les achats et ventes inhabituels rapportent 0,82 % par mois ; ceux des initiés "
                              "routiniers (même mois chaque année), rien.",
                              "https://www.nber.org/digest/apr11/decoding-inside-information"),
    "alldredge_blank": ("Alldredge et Blank (2019)",
                        "Un achat fait à 2 jours d'un autre initié : 2,1 % le mois suivant, contre 1,2 % pour un achat seul.",
                        "https://onlinelibrary.wiley.com/doi/abs/10.1111/jfir.12172"),
    "seyhun": ("Seyhun (1986)", "Les dirigeants et administrateurs en savent plus que les gros actionnaires.",
               "https://doi.org/10.1016/0304-405X(86)90060-7"),
    "wang_shin_francis": ("Wang, Shin et Francis (2012)", "Les achats du directeur financier en disent encore plus que ceux du PDG.",
                          "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1787482"),
    "cziraki_gider": ("Cziraki et Gider (document de travail)",
                      "Les achats les plus payants sont souvent modestes : pas de bonus pour le montant.",
                      "https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2019/03/CZiraki.pdf"),
    "brav": ("Brav, Jiang, Partnoy et Thomas (2008)",
             "Un fonds activiste qui dépasse 5 % : environ +7 % autour du dépôt, sans retour en arrière.",
             "https://www.ecgi.global/sites/default/files/working_papers/documents/finalbravjiangthomaspartnoy.pdf"),
    "cohen_polk_silli": ("Cohen, Polk et Silli (« Best Ideas »)",
                         "Les titres où les gestionnaires misent le plus battent le marché de 1 à 2,5 % par trimestre.",
                         "https://conference.nber.org/confer/2008/bff08/polk.pdf"),
    "eggers_hainmueller": ("Eggers et Hainmueller (2013)", "Les élus du Congrès ne battent pas le marché.",
                           "https://andy.egge.rs/papers/Eggmueller_CapitolLosses.pdf"),
    "wei_zhou": ("Wei et Zhou (2025)",
                 "Après leur nomination, les chefs du Congrès battent leurs pairs de 47 points de pourcentage par an ; "
                 "leurs ventes précèdent des mesures des régulateurs.",
                 "https://www.nber.org/papers/w34524"),
    "sarkar_de_jong": ("Sarkar et de Jong (2006)",
                       "Approbation finale de la FDA : +0,35 % le jour même ; le marché l'avait surtout déjà prévue.",
                       "https://econpapers.repec.org/RePEc:eee:quaeco:v:46:y:2006:i:4:p:586-597"),
    "rappels": ("Rappels d'autos aux États-Unis (201 rappels, 1980-2016)",
                "En moyenne, un rappel d'autos ne fait pas bouger le cours de façon nette ; autres études : −0,54 %.",
                "https://escholarship.org/content/qt4t6187tk/qt4t6187tk.pdf?t=paq0n2"),
    "karpoff": ("Karpoff, Lee et Martin (2008)",
                "Après une sanction de la SEC pour fraude comptable, la perte de réputation dépasse de loin l'amende.",
                "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=652121"),
    "brochet": ("Brochet (2010)",
                "Depuis 2002 (dépôt du formulaire 4 en 2 jours), le cours réagit nettement plus aux achats d'initiés "
                "dans les jours qui entourent le dépôt.",
                "https://www.researchgate.net/publication/228238781_Information_Content_of_Insider_Trades_Before_and_After_the_Sarbanes-Oxley_Act"),
    "palmrose": ("Palmrose, Richardson et Scholz (2004)", "Annonce d'états financiers à refaire : environ −9 % en 2 jours.",
                 "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=265009"),
}

FAMILLES = {
    "inities": "Dirigeants et administrateurs (formulaire 4)",
    "activistes": "Fonds activistes (13D)",
    "fonds": "Grands fonds (13F)",
    "elus": "Élus du Congrès",
    "fda": "FDA",
    "sec": "SEC (poursuites)",
    "rappels": "Rappels de véhicules (NHTSA)",
    "compagnie": "La compagnie elle-même (8-K)",
}

REGLES = {
    "achat_dirigeant": {
        "famille": "inities", "points": 2.0, "libelle": "Achat d'actions par un dirigeant ou un administrateur",
        "details": ["×1,5 si c'est le PDG, le directeur financier ou le président du conseil",
                    "×0,5 si c'est seulement un actionnaire de 10 %",
                    "×1,75 si un autre initié de la même compagnie a acheté à 2 jours ouvrables près (groupe d'achats)",
                    "×1,5 si c'est une petite compagnie : valeur en bourse sous le 30e centile des compagnies du NYSE "
                    "(seuil de Kenneth French, environ 2,2 G$ en août 2026) ; compagnies étrangères et tailles "
                    "inconnues : pas de bonus",
                    "Pas de bonus pour le montant",
                    "0 point si l'achat était planifié d'avance (plan 10b5-1)",
                    "0 point si l'initié est « routinier » : il a acheté ou vendu en bourse dans le même mois de l'année, "
                    "chacune des 3 années précédentes (jeux de données officiels de la SEC)",
                    "0 point si le déposant écrit que l'achat est automatique (réinvestissement de dividendes, "
                    "régime d'achat des employés)",
                    "0 point si le déposant écrit que l'achat s'est fait lors d'une émission (entrée en bourse, "
                    "placement) ou hors bourse, ou s'il a eu lieu le même jour au même prix qu'un tel achat"],
        "etudes": ["lakonishok_lee", "cohen_malloy_pomorski", "alldredge_blank", "seyhun", "wang_shin_francis",
                   "cziraki_gider"]},
    "vente_dirigeant": {
        "famille": "inities", "points": -0.5, "libelle": "Vente d'actions par un dirigeant ou un administrateur",
        "details": ["Seulement les ventes de 1 M$ et plus, décidées sur le moment (pas de plan 10b5-1)",
                    "0 point si l'initié est « routinier » (même mois de l'année, chacune des 3 années précédentes)",
                    "Les ventes disent peu de choses : un dirigeant vend aussi pour payer une maison ou diversifier"],
        "etudes": ["lakonishok_lee", "cohen_malloy_pomorski"]},
    "activiste_13d": {
        "famille": "activistes", "points": 5.0,
        "libelle": "Un gestionnaire de fonds dépasse 5 % avec des intentions actives (13D)",
        "details": ["Seulement le premier dépôt d'un gestionnaire de placements (type « IA » dans le document) : "
                    "il pourrait déclarer en 13G (passif) mais choisit le 13D",
                    "Et seulement s'il écrit au point 4 (le but de l'achat) que l'action est sous-évaluée : c'est ce "
                    "qu'écrivent les fonds activistes dans environ 2 cas sur 3"],
        "etudes": ["brav"]},
    "fonds_13f": {
        "famille": "fonds", "points": 1.0, "libelle": "Un grand fonds suivi ouvre ou grossit une position importante (13F)",
        "details": ["Moitié des points après 60 jours au lieu de 30 : le 13F arrive jusqu'à 45 jours en retard"],
        "etudes": ["cohen_polk_silli"]},
    "achat_elu": {
        "famille": "elus", "points": 1.0, "libelle": "Un élu du Congrès achète (actions ou options d'achat)",
        "details": ["Les études se contredisent : poids faible",
                    "Les chefs du Congrès ont leur propre règle, plus forte"],
        "etudes": ["eggers_hainmueller", "wei_zhou"]},
    "achat_chef": {
        "famille": "elus", "points": 2.0, "libelle": "Un chef du Congrès achète (actions ou options d'achat)",
        "details": ["Les 12 postes de l'étude : président de la Chambre, chefs de parti, whips, présidents de conférence "
                    "ou de caucus, selon les listes officielles actuelles de la Chambre et du Sénat",
                    "Le double d'un élu ordinaire : les élus ordinaires ne battent pas le marché, les chefs battent "
                    "leurs pairs"],
        "etudes": ["wei_zhou", "eggers_hainmueller"]},
    "vente_chef": {
        "famille": "elus", "points": -1.0, "libelle": "Un chef du Congrès vend des actions",
        "details": ["Les ventes des chefs précèdent des mesures des régulateurs ; celles des autres élus ne disent rien"],
        "etudes": ["wei_zhou"]},
    "fda": {
        "famille": "fda", "points": 0.5, "libelle": "La FDA approuve un nouveau médicament (nouvelle molécule)",
        "details": ["Le marché a surtout prévu l'approbation avant qu'elle arrive : poids très faible"],
        "etudes": ["sarkar_de_jong"]},
    "rappel": {
        "famille": "rappels", "points": -0.5, "libelle": "Gros rappel de véhicules (10 000 et plus)",
        "details": ["Effet moyen faible ou nul sur le cours"],
        "etudes": ["rappels"]},
    "sec_suspension": {
        "famille": "sec", "points": -5.0, "libelle": "La SEC suspend la cotation de la compagnie",
        "details": [], "etudes": ["karpoff"]},
    "sec_procedure": {
        "famille": "sec", "points": -2.0, "libelle": "La SEC ouvre une procédure contre la compagnie",
        "details": ["L'étude porte sur la fraude comptable ; nos procédures sont de toutes sortes : poids moyen"],
        "etudes": ["karpoff"]},
    "faillite": {
        "famille": "compagnie", "points": -5.0, "libelle": "Faillite ou mise sous séquestre (8-K, point 1.03)",
        "details": [], "etudes": []},
    "etats_financiers": {
        "famille": "compagnie", "points": -5.0, "libelle": "États financiers passés à ne plus croire (8-K, point 4.02)",
        "details": [], "etudes": ["palmrose"]},
}

SANS_POINTS = {
    "plan": "Planifié d'avance (plan 10b5-1) : comme les achats « routiniers » des études, ça ne prédit rien.",
    "routinier": "Initié « routinier » : il a acheté ou vendu des actions de cette compagnie en bourse dans le même mois de "
                 "l'année, chacune des 3 années précédentes (jeux de données officiels de la SEC). Selon Cohen, Malloy "
                 "et Pomorski (2012), ces transactions ne prédisent rien ; celles des autres initiés, oui.",
    "avis_144": "Avis d'intention de vente : la même vente arrive ensuite dans le formulaire 4 (sinon elle compterait "
                "deux fois).",
    "13d_autre": "13D d'un déclarant qui n'est pas un gestionnaire de fonds (individu, compagnie, commanditaire de SPAC…) : "
                 "l'étude ne porte pas sur ce cas.",
    "13d_type_inconnu": "13D lu avant que le robot note le type de déclarant : 0 point par prudence.",
    "13d_but_inconnu": "13D lu avant que le robot lise son but (point 4) : 0 point par prudence.",
    "13d_pas_sous_evalue": "13D d'un gestionnaire de fonds qui n'écrit pas que l'action est sous-évaluée (ex. achat lors "
                           "d'une entrée en bourse, financement d'une fusion) : ce n'est pas le cas mesuré par l'étude.",
    "emission": "Transaction lors d'une émission (entrée en bourse, placement) ou hors bourse, selon la note du "
                "déposant : les études portent sur les achats et les ventes en bourse.",
    "emission_meme_prix": "Même jour et même prix qu'un achat déclaré lors d'une émission : c'est la même émission.",
    "automatique": "Achat automatique (réinvestissement de dividendes, régime d'achat des employés), selon la note du "
                   "déposant : ce n'est pas une décision d'acheter.",
    "fonds": "Fonds de placement enregistré (il dépose des rapports de fonds N-CSR ou N-PORT à la SEC) : les études "
             "portent sur des compagnies, pas sur des fonds.",
    "13g": "13G : placement passif (souvent un fonds indiciel qui grossit).",
    "13d_suivi": "Mise à jour d'un 13D ou passage sous 5 % : seul le premier dépôt compte.",
    "fonds_vente": "Vente ou baisse d'un grand fonds : les études portent sur les achats.",
    "elu_vente": "Vente d'un élu : les études ne montrent rien.",
    "offre": "Offre d'achat : le prix a déjà bondi à l'annonce.",
    "ftc": "Feu vert antitrust (FTC) : aucune étude solide trouvée.",
    "concurrence": "Examen de fusion du Bureau de la concurrence (Canada) : aucune étude solide trouvée.",
    "sante_canada": "Approbation de Santé Canada : aucune étude solide trouvée (les études trouvées portent sur la FDA).",
    "contrat_ca": "Contrat fédéral canadien : aucune étude solide trouvée sur les contrats canadiens.",
    "ccc": "Transaction de la Corporation commerciale canadienne : aucune étude solide trouvée ; montants publiés en "
           "fourchettes.",
    "usaspending": "Contrat fédéral américain (USAspending) : publié des jours après la signature (90 jours pour la "
                   "Défense) ; aucune étude solide trouvée sur ces données publiées plus tard.",
    "fin_blocage": "Fin prévue du blocage après une entrée en bourse : information seulement. Les études (Field et Hanka "
                   "2001 ; Brav et Gompers 2003) trouvent −1,2 à −1,5 % sur 3 jours, sur des données de 1988 à 1997 ; "
                   "rien de solide trouvé depuis 2015.",
    "participation_gouv": "Participation du gouvernement américain : aucune étude solide trouvée sur les cas de 2025-2026 ; "
                          "les études plus anciennes trouvent l'effet surtout à l'annonce.",
    "rachat_annonce": "Annonce de rachat d'actions : un plafond autorisé, pas un achat fait. L'étude d'Ikenberry, "
                      "Lakonishok et Vermaelen (annonces de 1980 à 1990) trouve +12,1 % sur 4 ans par rapport à des "
                      "actions comparables, mais surtout pour les actions bon marché (+45,3 %) et rien pour les actions "
                      "chères.",
    "lobbying": "Lobbying à Washington (LDA.gov) : montré sur la fiche de la compagnie, sans points. L'étude de Chen, "
                "Parsley et Yang (2015) mesure un effet sur 3 ans, selon le lobbying par rapport à la taille de la "
                "compagnie.",
    "cabinet": "Transaction d'un ministre ou d'un haut fonctionnaire (rapport 278-T de l'OGE) : aucune étude ne mesure "
               "d'effet pour ces postes (les études portent sur le Congrès), et une vente peut être imposée par "
               "l'entente d'éthique du poste.",
    "oge": "Rapports de transactions du président (OGE) : sans points ; le détail est dans le document officiel.",
    "8k_autre": "Autre point du 8-K (contrat, acquisition, avis de retrait de la bourse…) : effet incertain.",
    "contexte": "Contexte seulement.",
}

METHODE = {
    "version": VERSION,
    "resume": "Chaque info officielle sur une compagnie vaut des points selon ce que les études ont mesuré. "
              "Les points fondent avec le temps, seule l'info la plus forte de chaque famille compte, "
              "et plusieurs familles d'accord donnent un bonus.",
    "temps": f"Moitié des points après {DEMI_VIE} jours ({DEMI_VIE_FONDS} pour les grands fonds, qui déclarent en "
             f"retard). Après {AGE_MAX} jours, une info ne compte plus.",
    "familles": "Dans une même famille, seule l'info la plus forte compte : 7 administrateurs qui achètent le même jour "
                "forment UN groupe d'achats (avec son bonus), pas 7 fois les points. Le même achat déclaré par un "
                "administrateur et par son fonds compte aussi une seule fois.",
    "bonus": "Plusieurs familles qui pointent dans le même sens : +25 % par famille de plus. Ce bonus est un choix du "
             "modèle, pas une mesure d'étude.",
    "seuil": "Une compagnie entre dans la liste à partir de 7/10 (hausse) ou à 3/10 et moins (baisse).",
    "note10": "Note sur 10 = 5 + points × 5/6, entre 0 et 10, arrondie au dixième. 5 = neutre. Les achats de "
              "dirigeants seuls plafonnent à 9,4 ; 10/10 demande plusieurs familles de sources d'accord. La note mesure "
              "la force des preuves officielles, pas une promesse de hausse.",
    "recent": "« Récent » : une preuve qui compte dans la note a été déposée il y a moins de 3 jours de bourse. "
              "Depuis 2002, le cours réagit surtout dans les jours qui entourent le dépôt (Brochet, 2010).",
    "etudes_note": ["brochet"],
    "badges": "Seules les infos « Officiel » ou « Confirmé » comptent ; les « À vérifier » n'entrent jamais.",
    "prix": "Les résultats de Radar sont mesurés avec les prix officiels de la SEC (page « Résultats de Radar »).",
    "avertissement": "Une aide pour voir où va le gros argent, preuves à l'appui. Pas un conseil financier.",
    "regles": [{"code": c, **{k: r[k] for k in ("famille", "points", "libelle", "details", "etudes")}}
               for c, r in REGLES.items()],
    "taille": "Taille en bourse = actions en circulation déclarées à la SEC × dernier prix de la SEC. Petite : sous le "
              "30e centile des compagnies du NYSE ; grande : au 70e et plus (seuils publiés chaque mois par Kenneth "
              "French). Le prix doit être de la même époque que le nombre d'actions : si le code du titre (CUSIP) a "
              "changé après la date des actions (souvent un regroupement d'actions, qui divise leur nombre), c'est le "
              "dernier prix de l'ancien code ; si on ne sait pas de quel côté du changement sont les actions, les deux "
              "valeurs possibles, et une taille seulement si elles donnent la même ; après un regroupement probable "
              "(prix au moins 1,8 fois plus haut au changement), ancien nombre × nouveau prix est un maximum. Quand la "
              "SEC n'a pas de prix depuis 60 jours (un titre a un prix seulement les jours où il a des échecs de "
              "livraison), le prix moyen des achats et ventes de dirigeants en bourse du jour le plus récent (formulaire "
              "4 de 60 jours ou moins, actions ordinaires seulement, jamais lors d'une émission, hors bourse ou "
              "automatique) ; pas s'il est plus de 10 fois loin du dernier prix de la SEC ou si le code du titre a "
              "changé entre-temps. Taille inconnue, donc pas de bonus : compagnie étrangère (20-F, 40-F, 6-K), actions "
              "déclarées il y a plus de 200 jours ou moins de 500 000 actions déclarées, pas de prix de la SEC ni de prix "
              "de formulaire 4 utilisable depuis 60 jours, changement de code du titre dont on ne peut pas dire le côté.",
    "etudes_taille": ["lakonishok_lee", "cohen_malloy_pomorski"],
    "routiniers": "Un initié qui achète ou vend en bourse dans le même mois de l'année, chacune des 3 années précédentes "
                  "(« routinier ») : 0 point, ses transactions ne prédisent rien (Cohen, Malloy et Pomorski 2012). "
                  "Vérifié dans les jeux de données officiels de la SEC sur les formulaires 3, 4 et 5.",
    "sans_points": [SANS_POINTS[k] for k in ("fonds", "plan", "routinier", "automatique", "emission", "emission_meme_prix",
                                             "avis_144",
                                             "13g", "13d_autre", "13d_pas_sous_evalue", "13d_suivi", "fonds_vente",
                                             "elu_vente", "cabinet", "offre", "ftc", "8k_autre", "lobbying", "oge")]
                   + ["Fed, Banque du Canada, décrets, sanctions, ventes d'armes, CFTC : contexte, sans points."],
    "familles_noms": FAMILLES,
    "etudes": {k: {"titre": t, "constat": c, "lien": u} for k, (t, c, u) in ETUDES.items()},
    "trop_petites": f"Moins de {TROP_PETITE} M$ en bourse : la compagnie n'entre pas dans la liste « hausse ». Dans le "
                    "rejeu de 3 ans du labo (juillet 2023 à juin 2026, prix de la SEC), ces compagnies ont fait pire que "
                    "le S&P 500 chacune des 3 années : écart médian de −11,8, −6,6 et −1,3 % un mois après l'achat, "
                    "contre −2,0, −3,1 et −0,2 % pour les autres. Elles restent visibles à part (« écartées ») et sont "
                    "suivies dans les Résultats pour vérifier la règle. Taille inconnue : rien n'est écarté.",
    "lien_labo": "https://github.com/killingsky1/Radar/blob/labo/labo/rejeu3/facteurs.md",
}


@dataclass
class Apport:
    """Ce qu'une info apporte à une compagnie : des points (règle) ou rien (contexte, avec la raison)."""

    symbole: str
    ev: dict
    regle: str | None = None
    pourquoi: str | None = None
    facteurs: list = field(default_factory=list)  # [(libellé, multiplicateur)]
    age: int = 0
    temps: float = 1.0  # ce qui reste des points après la fonte avec le temps
    points: float = 0.0

    @property
    def famille(self) -> str | None:
        return REGLES[self.regle]["famille"] if self.regle else None

    @property
    def sens(self) -> int:
        return (self.points > 0) - (self.points < 0)


def facteurs_role(roles: list[str]) -> list:
    if any(PRINCIPAL.search(r) for r in roles):
        return [("PDG, directeur financier ou président du conseil", ROLE_PRINCIPAL)]
    if roles and all(r == "actionnaire de 10 %" for r in roles):
        return [("Seulement un actionnaire de 10 %", ROLE_GROS_ACTIONNAIRE)]
    return []


def evaluer(ev: dict, emissions: frozenset = frozenset(), chefs: frozenset = frozenset(),
            routiniers: dict | None = None) -> list[Apport]:
    """Les apports d'une info, un par compagnie visée.

    `emissions` : (symbole, date, prix) des achats déclarés lors d'une émission (voir achats_d_emission).
    `chefs` : les élus (nom écrit dans leur rapport) qui sont chefs du Congrès selon les listes officielles.
    `routiniers` : le classement des initiés routiniers (collecteurs/inities.py), None si pas encore lu.
    """
    s, k, d, symboles = ev["source"], ev["kind"], ev.get("data") or {}, ev.get("tickers") or []

    def regle(code, facteurs=(), viser=None):
        return [Apport(t, ev, regle=code, facteurs=list(facteurs)) for t in (viser or symboles[:1])]

    def contexte(raison, detail=""):
        return [Apport(t, ev, pourquoi=SANS_POINTS[raison] + detail) for t in symboles]

    if not symboles:
        return []
    if s == "sec_form4":
        if d.get("plan_10b5_1"):
            return contexte("plan")
        if d.get("automatique"):
            return contexte("automatique")
        if d.get("hors_bourse"):
            return contexte("emission")
        if k == "achat_initie" and any((symboles[0], t.get("date"), t.get("prix")) in emissions
                                       for t in d.get("transactions") or []):
            return contexte("emission_meme_prix")
        if k in ("achat_initie", "vente_initie") and (r := inities.routinier(routiniers, ev)):
            return contexte("routinier", f" Mois : {inities.en_mots(r)}.")
        return regle("achat_dirigeant", facteurs_role(d.get("roles") or [])) if k == "achat_initie" else (
            regle("vente_dirigeant") if k == "vente_initie" else contexte("contexte"))
    if s == "sec_form144":
        return contexte("avis_144")
    if s == "sec_13dg":
        if d.get("type") == "SCHEDULE 13D" and k == "plus_5_pourcent":
            types = d.get("types_declarants")
            if not types:
                return contexte("13d_type_inconnu")
            if "IA" not in types:
                return contexte("13d_autre")
            if "but_sous_evalue" not in d:
                return contexte("13d_but_inconnu")
            return regle("activiste_13d") if d["but_sous_evalue"] else contexte("13d_pas_sous_evalue")
        return contexte("13g" if (d.get("type") or "").startswith("SCHEDULE 13G") else "13d_suivi")
    if s == "sec_13f":
        return regle("fonds_13f") if ev.get("direction", 0) > 0 else contexte("fonds_vente")
    if s in ("chambre_ptr", "senat_ptr"):
        chef = d.get("elu") in chefs
        if ev.get("direction", 0) > 0:
            return regle("achat_chef" if chef else "achat_elu")
        return regle("vente_chef") if chef and k == "vente_elu" else contexte("elu_vente")
    if s == "fda":
        return regle("fda")
    if s == "nhtsa":
        return regle("rappel")
    if s == "sec_poursuites":  # toutes les compagnies cotées nommées
        return regle("sec_suspension" if d.get("sorte") == "suspension" else "sec_procedure", viser=symboles)
    if s == "sec_8k":
        items = {i.get("item") for i in d.get("items") or []}
        return regle("faillite") if "1.03" in items else regle("etats_financiers") if "4.02" in items else contexte("8k_autre")
    if s == "sec_offres":
        return contexte("offre")
    if s == "oge_278t":
        return contexte("cabinet")
    if s == "ftc_fusions":
        return contexte("ftc")
    if s == "concurrence_ca":
        return contexte("concurrence")
    if s == "sante_canada":
        return contexte("sante_canada")
    if s == "contrats_ca_10k":
        return contexte("contrat_ca")
    if s == "ccc":
        return contexte("ccc")
    if s == "usaspending":
        return contexte("usaspending")
    if s == "participations_gouv":
        return contexte("participation_gouv")
    if s == "sec_blocage":
        return contexte("fin_blocage")
    if s == "sec_rachats":
        return contexte("rachat_annonce")
    return contexte("contexte")


def achats_d_emission(evenements: list[dict]) -> frozenset:
    """(symbole, date, prix) des achats que le déposant dit faits lors d'une émission ou hors bourse.

    Un autre initié qui achète la même action le même jour au même prix (ex. un fonds lors d'une entrée en bourse,
    sans la note) participe à la même émission.
    """
    return frozenset((ev["tickers"][0], t.get("date"), t.get("prix")) for ev in evenements
                     if ev["source"] == "sec_form4" and ev["kind"] == "achat_initie" and ev.get("tickers")
                     and ev.get("badge") in ("officiel", "confirme") and (ev.get("data") or {}).get("hors_bourse")
                     for t in ev["data"].get("transactions") or [] if t.get("hors_bourse"))


def jours_ouvrables(a: date, b: date) -> int:
    a, b = min(a, b), max(a, b)
    return sum(1 for i in range((b - a).days) if (a + timedelta(days=i)).weekday() < 5)


def personnes(ev: dict) -> set[str]:
    return {n.strip().upper() for n in (ev.get("entities") or [])[:-1]}


def groupe_d_achats(a: Apport, achats: list[Apport]) -> bool:
    """Un autre initié (d'autres personnes) a acheté la même action à 2 jours ouvrables près.

    Le même achat déclaré par plusieurs personnes (même jour, même montant : un administrateur et son fonds) n'est pas
    un groupe.
    """
    jour = date.fromisoformat(a.ev["occurred_on"])
    for b in achats:
        if b is a or personnes(b.ev) & personnes(a.ev):
            continue
        if b.ev["occurred_on"] == a.ev["occurred_on"] and round(b.ev.get("amount_min") or 0) == round(a.ev.get("amount_min") or 0):
            continue
        if jours_ouvrables(jour, date.fromisoformat(b.ev["occurred_on"])) <= JOURS_GROUPE:
            return True
    return False


def trop_petite(r: dict) -> bool:
    """Valeur en bourse connue et sous TROP_PETITE M$ (lot M). Taille inconnue : jamais écartée."""
    v = (r.get("taille") or {}).get("valeur_m")
    return v is not None and v < TROP_PETITE


def note_sur_10(score: float) -> float:
    """5 + points × 5/6, bornée entre 0 et 10, arrondie au dixième (5 vers le haut), à partir du score publié
    (2 décimales) : le labo la recalcule à l'identique. 5,13 points -> 9,3 ; −4,67 -> 1,1."""
    n = Decimal(str(round(score, 2))) * 5 / POINTS_POUR_10 + 5
    n = min(max(n, Decimal(0)), Decimal(10))
    return float(n.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def recent(depot: str | None, jour: date) -> bool:
    """La preuve a été déposée il y a moins de JOURS_RECENT jours de bourse (le jour même compte pour 0)."""
    return bool(depot) and jours_ouvrables(date.fromisoformat(depot), jour) < JOURS_RECENT


def jour_de_calcul(maintenant: datetime) -> date:
    return maintenant.astimezone(ZoneInfo("America/Toronto")).date()


def nom_de(symbole: str, apports: list[Apport], symboles) -> str:
    """Nom officiel : la liste de la SEC si le robot l'a lue à ce passage, sinon les infos de la SEC elles-mêmes."""
    if symboles is not None and (cote := symboles.par_symbole(symbole)):
        return re.sub(r"\s*[/\\][A-Z]{2,4}[/\\]?\s*$", "", cote["name"])
    for sources, lire in (
        (("sec_form4", "sec_form144", "sec_8k", "sec_13dg", "sec_13f", "sec_offres"), lambda e: e["entities"][-1]),
        (("chambre_ptr", "senat_ptr"), lambda e: e["data"].get("nom_sec")),
        (("sec_poursuites",), lambda e: e["data"].get("nom_officiel")),
        (("nhtsa",), lambda e: e["entities"][0]),
    ):
        for a in sorted(apports, key=lambda a: a.ev["published_on"], reverse=True):
            if a.ev["source"] in sources and a.ev["tickers"][:1] == [symbole] and (nom := lire(a.ev)):
                return nom
    return symbole


def _infos(a: Apport, compte: bool) -> dict:
    return {"id": a.ev["id"], "regle": a.regle, "points": round(a.points, 2), "base": REGLES[a.regle]["points"],
            "facteurs": [[l, m] for l, m in a.facteurs], "age": a.age, "temps": round(a.temps, 3), "compte": compte}


def calculer(evenements: list[dict], maintenant: datetime, precedent: dict | None = None, symboles=None,
             fonds: set[str] | frozenset = frozenset(), chefs: set[str] | frozenset = frozenset(),
             routiniers: dict | None = None, tailles: dict | None = None) -> dict:
    """`fonds` : symboles des fonds enregistrés selon leur fiche SEC (voir emetteurs.py) : 0 point, contexte seulement.
    `chefs` : noms des élus chefs du Congrès (voir congres.relier_elus).
    `routiniers` : classement des initiés routiniers (collecteurs/inities.py) ; `tailles` : {symbole : taille en bourse}
    (collecteurs/taille.py). Absents : aucune info n'est mise à 0 comme routinière, aucun bonus de taille."""
    jour = jour_de_calcul(maintenant)
    emissions = achats_d_emission(evenements)
    chefs = frozenset(chefs)
    par_symbole: dict[str, list[Apport]] = defaultdict(list)
    for ev in evenements:
        source = SOURCES.get(ev["source"])
        if ev.get("badge") not in ("officiel", "confirme") or source is None or not source.officielle:
            continue
        age = (jour - date.fromisoformat(ev["published_on"])).days
        if age > AGE_MAX:
            continue
        for a in evaluer(ev, emissions, chefs, routiniers):
            a.age = max(age, 0)
            if a.regle and a.symbole in fonds:
                a.regle, a.pourquoi, a.facteurs = None, SANS_POINTS["fonds"], []
            par_symbole[a.symbole].append(a)

    resultats = []
    for symbole, apports in par_symbole.items():
        achats = [a for a in apports if a.regle == "achat_dirigeant"]
        for a in apports:
            if not a.regle:
                continue
            if a.regle == "achat_dirigeant" and groupe_d_achats(a, achats):
                a.facteurs.append(("Groupe d'achats", GROUPE))
            if a.regle == "achat_dirigeant" and ((tailles or {}).get(symbole) or {}).get("taille") == "petite":
                a.facteurs.append(("Petite compagnie", PETITE))
            a.temps = 0.5 ** (a.age / (DEMI_VIE_FONDS if a.famille == "fonds" else DEMI_VIE))
            a.points = REGLES[a.regle]["points"] * a.temps
            for _, m in a.facteurs:
                a.points *= m
        groupes = defaultdict(list)
        for a in apports:
            if a.regle and a.points:
                groupes[(a.famille, a.sens)].append(a)
        if not groupes:
            continue
        sortie_groupes, totaux, frais = [], {1: 0.0, -1: 0.0}, {1: None, -1: None}
        sans_taille = {1: 0.0, -1: 0.0}  # la même chose sans le bonus de petite compagnie (pour les Résultats)
        for (famille, sens), membres in groupes.items():
            membres.sort(key=lambda a: (abs(a.points), a.ev["published_on"], a.ev["id"]), reverse=True)
            retenu = membres[0]
            totaux[sens] += retenu.points
            sans_taille[sens] += max((a.points / PETITE if ("Petite compagnie", PETITE) in a.facteurs else a.points
                                      for a in membres), key=abs)
            frais[sens] = max(frais[sens] or "", retenu.ev["published_on"])  # dépôt le plus récent qui compte
            sortie_groupes.append({"famille": famille, "sens": sens, "points": round(retenu.points, 2),
                                   "infos": [_infos(a, a is retenu) for a in membres]})
        nb = {s: sum(1 for (_, sg) in groupes if sg == s) for s in (1, -1)}
        bonus = {s: 1 + BONUS_FAMILLE * max(nb[s] - 1, 0) for s in (1, -1)}
        plus, moins = totaux[1] * bonus[1], totaux[-1] * bonus[-1]
        sortie_groupes.sort(key=lambda g: (-abs(g["points"]), g["famille"]))
        contexte = sorted((a for a in apports if not a.regle), key=lambda a: (a.ev["published_on"], a.ev["id"]),
                          reverse=True)[:MAX_CONTEXTE]
        resultats.append({
            "symbole": symbole, "nom": nom_de(symbole, apports, symboles), "score": round(plus + moins, 2),
            "note10": note_sur_10(plus + moins),
            "plus": round(plus, 2), "moins": round(moins, 2), "bonus": {"plus": bonus[1], "moins": bonus[-1]},
            "derniere_info": max(a.ev["published_on"] for a in apports if a.regle),
            "groupes": sortie_groupes, "contexte": [{"id": a.ev["id"], "pourquoi": a.pourquoi} for a in contexte],
            "taille": (tailles or {}).get(symbole),
            # Pour mesurer les choix du modèle (page Résultats) : la note sans le bonus de familles, et sans le bonus de
            # petite compagnie
            "note10_sans_bonus": note_sur_10(totaux[1] + totaux[-1]),
            "note10_sans_taille": note_sur_10(sans_taille[1] * bonus[1] + sans_taille[-1] * bonus[-1]),
            "_brut": plus + moins, "_apports": apports, "_frais": frais,
        })

    candidates = sorted((r for r in resultats if r["note10"] >= NOTE_HAUSSE), key=lambda r: (-r["_brut"], r["symbole"]))
    hausse = [r for r in candidates if not trop_petite(r)][:MAX_LISTE]
    ecartees = [r for r in candidates if trop_petite(r)][:MAX_LISTE]  # lot M : montrées à part, suivies dans les Résultats
    baisse = sorted((r for r in resultats if r["note10"] <= NOTE_BAISSE),
                    key=lambda r: (r["_brut"], r["symbole"]))[:MAX_LISTE]

    # « Nouveau » : la date où la compagnie est entrée dans sa liste (gardée tant qu'elle y reste).
    premier_calcul = not precedent or precedent.get("version", "").split("-")[0] != "score"
    avant = {(nom, r["symbole"]): r.get("depuis") for nom in ("hausse", "baisse", "ecartees")
             for r in (precedent or {}).get(nom, [])}
    evenements_cites = {}
    for nom, liste in (("hausse", hausse), ("baisse", baisse), ("ecartees", ecartees)):
        for r in liste:
            r["depuis"] = avant[(nom, r["symbole"])] if (nom, r["symbole"]) in avant else (
                None if premier_calcul else maintenant.isoformat())
            r["depot_recent"] = r.pop("_frais")[-1 if nom == "baisse" else 1]
            r["recent"] = recent(r["depot_recent"], jour)
            for a in r.pop("_apports"):
                if a.regle or any(c["id"] == a.ev["id"] for c in r["contexte"]):
                    evenements_cites[a.ev["id"]] = a.ev
            del r["_brut"]
    return {
        "version": VERSION, "genere_a": maintenant.isoformat(), "jour": jour.isoformat(),
        "hausse": hausse, "baisse": baisse, "ecartees": ecartees, "evenements": evenements_cites,
        "compagnies_notees": len(resultats), "methode": METHODE,
        "note": METHODE["avertissement"],
    }
