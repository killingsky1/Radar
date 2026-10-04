"""Catalogue de toutes les sources : branchées, à venir et laissées de côté.

`domaines` = seuls domaines acceptés pour les liens de cette source.
`attente_heures` = délai max sans lecture réussie avant « en retard » (80 h couvre une fin de semaine).
`publication_max_jours` = si la source n'a rien publié depuis ce délai, elle est « en pause »
(ex. fermeture du gouvernement américain). None = pas de vérification.
`officielle=False` = sert seulement à recouper ou calculer, jamais à créer une suggestion seule.
"""

from __future__ import annotations

from dataclasses import dataclass

PASSAGES = ("matin", "jour", "midi", "soir", "nuit")


@dataclass(frozen=True)
class Source:
    id: str
    nom: str
    categorie: str
    domaines: tuple[str, ...]
    phase: int
    site: str
    attente_heures: int = 80
    publication_max_jours: int | None = None
    officielle: bool = True
    ecartee: str | None = None  # raison si la source est laissée de côté
    passages: tuple[str, ...] = PASSAGES


S = Source
_LISTE = [
    # Phase 1 : compagnies et gros joueurs (SEC en premier : elle relie chaque compagnie à son symbole)
    S("sec_form4", "SEC : formulaire 4 (achats et ventes des dirigeants)", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4", publication_max_jours=5),
    S("sec_form144", "SEC : formulaire 144 (intention de vendre)", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=144", publication_max_jours=5),
    S("sec_13dg", "SEC : 13D/13G (un gros joueur dépasse 5 %)", "baleines", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SCHEDULE+13D", publication_max_jours=7),
    S("sec_8k", "SEC : 8-K (événements majeurs)", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K", publication_max_jours=5),
    S("sec_13f", "SEC : 13F (achats et ventes des gros fonds, chaque trimestre)", "baleines", ("sec.gov",), 1,
      "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets", publication_max_jours=100),
    S("sec_offres", "SEC : offres d'achat de compagnies entières et privatisations", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=SC+TO-T"),
    # Lot F : prospectus finals (424B4) des entrées en bourse ; information seulement (0 point), voir blocage.py
    S("sec_blocage", "SEC : fins de blocage après une entrée en bourse (prospectus 424B4)", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=424B4"),
    S("sec_poursuites", "SEC : suspensions de cotation et procédures contre des compagnies cotées", "compagnies",
      ("sec.gov",), 1, "https://www.sec.gov/enforcement-litigation/trading-suspensions"),
    S("cftc_cot", "CFTC : positions des gros joueurs (contrats à terme)", "baleines", ("cftc.gov",), 1,
      "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm", publication_max_jours=10),
    # Phase 2 : militaire et défense
    S("ventes_armes", "Ventes d'armes à l'étranger (avis officiels au Registre fédéral)", "militaire",
      ("federalregister.gov",), 2,
      "https://www.federalregister.gov/documents/search?conditions%5Bterm%5D=%22Arms+Sales+Notification%22"),
    # Lot 3d : contrats de 100 M$ et plus ; une info va dans « Militaire » si le contrat vient de la Défense
    S("usaspending", "USAspending : contrats fédéraux américains de 100 M$ et plus", "gouvernement", ("usaspending.gov",),
      2, "https://www.usaspending.gov/search", attente_heures=24 * 8, publication_max_jours=21, passages=("matin",)),
    # Lot 3d : la phrase exacte d'un 8-K où le gouvernement reçoit, détient ou revend des titres de la compagnie
    S("participations_gouv", "Gouvernement américain actionnaire (8-K de la SEC)", "gouvernement", ("sec.gov",), 2,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K"),
    # Lot H : rachats d'actions, information seulement (0 point), voir rachats.py
    S("sec_rachats", "SEC : annonces de rachat d'actions (8-K)", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K"),
    S("sec_rachats_xbrl", "SEC : rachats d'actions faits (rapports annuels, données XBRL)", "compagnies", ("sec.gov",), 1,
      "https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2025.json",
      passages=("matin",)),
    # Lot K : santé financière (9 critères de Piotroski) des rapports annuels : montrée sur la fiche, 0 point
    S("sec_sante", "SEC : santé financière des compagnies (rapports annuels, données XBRL)", "compagnies", ("sec.gov",), 1,
      "https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/CY2025Q4I.json", passages=("matin",)),
    # Lot 3c : contrats de 10 M$ et plus (nouveaux ou hausses), lus chaque matin sur l'API du portail (20 s entre 2 requêtes)
    S("contrats_ca_10k", "Contrats fédéraux de 10 M$ et plus (publication proactive)", "canada",
      ("open.canada.ca", "ouvert.canada.ca"), 2, "https://rechercher.ouvert.canada.ca/contrats/",
      attente_heures=24 * 8, publication_max_jours=130, passages=("matin",)),
    S("nouvelles_defense_ca", "Canada : nouvelles de la Défense nationale", "militaire", ("canada.ca",), 2,
      "https://www.canada.ca/fr/nouvelles.html", publication_max_jours=21),
    S("ccc", "Corporation commerciale canadienne : transactions signées (rapport trimestriel)", "canada", ("ccc.ca",), 2,
      "https://www.ccc.ca/en/about/corporate-reports/", passages=("matin",)),
    # Phase 3 : politiciens
    S("chambre_ptr", "Chambre des représentants : transactions des élus", "politiciens", ("house.gov",), 3,
      "https://disclosures-clerk.house.gov/FinancialDisclosure", publication_max_jours=21),
    S("senat_ptr", "Sénat : transactions des sénateurs", "politiciens", ("senate.gov",), 3,
      "https://efdsearch.senate.gov/search/", publication_max_jours=30),
    # Rapports 278-T publiés sans formulaire 201 (président, vice-président, niveaux I et II) : une fois par jour
    S("oge_278t", "Président, vice-président et cabinet : rapports de transactions (OGE)", "politiciens", ("oge.gov",),
      3, "https://www.oge.gov/web/OGE.nsf/Officials%20Individual%20Disclosures%20Search%20Collection",
      passages=("matin",)),
    # 27 pages officielles (dont 24 comités du Sénat) qui changent rarement : une fois par jour de semaine suffit
    S("comites", "Chefs et comités du Congrès (Chambre et Sénat)", "politiciens", ("house.gov", "senate.gov"), 3,
      "https://clerk.house.gov/xml/lists/MemberData.xml", passages=("matin",)),
    S("votes", "Votes du Congrès sur les projets de loi suivis", "politiciens", ("house.gov", "senate.gov"), 3,
      "https://clerk.house.gov/Votes"),
    # Lobbying des compagnies des listes (15 requêtes par minute sans compte) : une fois par jour de semaine
    S("lobbying", "Lobbying des compagnies des listes (LDA.gov)", "politiciens", ("lda.gov",), 3, "https://lda.gov/",
      passages=("matin",)),
    S("hr7008", "Suivi de H.R. 7008 (interdiction des transactions des élus)", "politiciens",
      ("govinfo.gov", "congress.gov"), 3, "https://www.congress.gov/bill/119th-congress/house-bill/7008"),
    # Phase 4 : gouvernement, régulateurs, économie
    S("registre_federal", "Registre fédéral : décrets, tarifs, sanctions (la veille)", "gouvernement",
      ("federalregister.gov", "govinfo.gov"), 4, "https://www.federalregister.gov/public-inspection/current",
      publication_max_jours=5),
    S("maison_blanche", "Maison-Blanche : actions présidentielles", "gouvernement", ("whitehouse.gov",), 4,
      "https://www.whitehouse.gov/presidential-actions/"),
    # Lot 3d : les directives de la douane sur les surtaxes et les interdictions d'importation (messages CSMS)
    S("tarifs", "Douane américaine : directives sur les surtaxes (messages CSMS)", "gouvernement",
      ("cbp.gov", "govdelivery.com"), 4, "https://www.cbp.gov/trade/automated/cargo-systems-messaging-service",
      passages=("matin", "soir")),
    S("sanctions_us", "Sanctions américaines (OFAC)", "gouvernement",
      ("treasury.gov", "treas.gov", "trade.gov", "bis.gov"), 4, "https://ofac.treasury.gov/recent-actions",
      publication_max_jours=21),
    S("fda", "FDA : nouveaux médicaments approuvés (données openFDA)", "gouvernement", ("fda.gov",), 4,
      "https://www.fda.gov/drugs/novel-drug-approvals-fda", publication_max_jours=45),
    S("ftc_fusions", "FTC : fusions (fin anticipée de l'examen)", "gouvernement", ("ftc.gov",), 4,
      "https://www.ftc.gov/legal-library/browse/early-termination-notices", publication_max_jours=30),
    S("doj_antitrust", "Ministère de la Justice : antitrust", "gouvernement", ("justice.gov",), 4,
      "https://www.justice.gov/atr/news-feeds", publication_max_jours=45),
    S("fed", "Réserve fédérale (Fed) : décisions de taux", "gouvernement", ("federalreserve.gov",), 4,
      "https://www.federalreserve.gov/newsevents/pressreleases.htm"),
    # Lot 3d : les résultats arrivent sur Fiscal Data vers 23 h UTC (calendrier officiel) : lus la nuit, le matin en secours
    S("tresor", "Trésor américain : adjudications d'obligations et déficit mensuel (Fiscal Data)", "gouvernement",
      ("fiscaldata.treasury.gov", "treasury.gov"), 4,
      "https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/", publication_max_jours=10,
      passages=("nuit", "matin")),
    S("nhtsa", "NHTSA : gros rappels d'autos (10 000 véhicules et plus)", "gouvernement", ("nhtsa.gov",), 4,
      "https://www.nhtsa.gov/recalls", publication_max_jours=21),
    S("nouvelles_eco_ca", "Canada : nouvelles des ministères économiques", "canada", ("canada.ca",), 4,
      "https://www.canada.ca/fr/nouvelles.html", publication_max_jours=10),
    S("banque_canada", "Banque du Canada : décisions de taux", "canada", ("bankofcanada.ca",), 4,
      "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/"),
    # Lot 3c : le Quotidien paraît à 8 h 30 (heure de l'Est) : lu au passage « jour », et le soir en secours
    S("statcan", "Statistique Canada : grands indicateurs économiques", "canada", ("statcan.gc.ca",), 4,
      "https://www150.statcan.gc.ca/n1/dai-quo/cal1-fra.htm", passages=("jour", "soir")),
    # Gazette : Partie II un mercredi sur deux (9 h), Partie I le samedi ; les 2 sources se partagent la lecture
    S("gazette_ca", "Gazette du Canada : règlements liés à l'argent (surtaxes, sanctions, commerce)", "canada",
      ("gazette.gc.ca",), 4, "https://gazette.gc.ca/rp-pr/p2/2026/index-fra.html", passages=("matin", "soir")),
    S("sante_canada", "Santé Canada : nouveaux médicaments (nouvelles substances actives)", "canada", ("canada.ca",), 4,
      "https://health-products.canada.ca/noc-ac/?lang=fre", passages=("matin",)),
    S("concurrence_ca", "Bureau de la concurrence : examens de fusion", "canada", ("canada.ca",), 4,
      "https://bureau-concurrence.canada.ca/fr/fusions-acquisitions/rapport-examens-fusions-termines",
      publication_max_jours=21, passages=("matin",)),
    S("grands_projets_ca", "Grands projets d'intérêt national (Canada)", "canada", ("canada.ca", "gazette.gc.ca"), 4,
      "https://www.canada.ca/fr/conseil-prive/bureau-grands-projets/projets/national.html", passages=("matin", "soir")),
    S("sanctions_ca", "Sanctions canadiennes : nouvelles inscriptions", "canada", ("international.gc.ca",), 4,
      "https://www.international.gc.ca/world-monde/international_relations-relations_internationales/sanctions/"
      "consolidated-consolide.aspx?lang=fra", passages=("matin", "soir")),
    S("legisinfo", "Projets de loi du gouvernement fédéral (LEGISinfo)", "canada", ("parl.ca",), 4,
      "https://www.parl.ca/legisinfo/fr/projets-de-loi", passages=("matin", "soir")),
    # Laissées de côté
    S("sedi", "SEDI : initiés canadiens", "canada", ("sedi.ca",), 0, "https://www.sedi.ca/",
      ecartee="Payant : aucun accès gratuit pour un robot"),
    S("sedar", "SEDAR+ : documents des compagnies canadiennes", "canada", ("sedarplus.ca",), 0,
      "https://www.sedarplus.ca/", ecartee="Robots interdits par ses conditions d'utilisation"),
    # Lu en direct le 4 octobre 2026 : finra.org/terms-of-use ; robots.txt de cdn.finra.org : erreur 403
    S("finra", "FINRA : ventes à découvert", "compagnies", ("finra.org",), 0, "https://www.finra.org/finra-data",
      ecartee="Ses conditions d'utilisation interdisent les robots et l'usage commercial ; son serveur de fichiers refuse "
              "le robot (erreur 403) et son API exige un compte"),
    S("sam_gov", "SAM.gov : contrats fédéraux", "militaire", ("sam.gov",), 0, "https://sam.gov/",
      ecartee="Compte obligatoire (USAspending le remplace)"),
    S("prix_payants", "Prix officiels payants (EODHD)", "compagnies", ("eodhd.com",), 0, "https://eodhd.com/",
      ecartee="Payant"),
    S("sp_indices", "S&P : entrées et sorties d'indices", "compagnies", ("spglobal.com",), 0,
      "https://press.spglobal.com/",
      ecartee="Conditions d'utilisation de S&P Dow Jones Indices : robots interdits sans permission écrite"),
    S("canadabuys", "CanadaBuys : appels d'offres et contrats", "canada", ("canadabuys.canada.ca",), 0,
      "https://canadabuys.canada.ca/",
      ecartee="Son robots.txt interdit les robots sur tout le site, données ouvertes comprises"),
    S("arrets_negociation", "Arrêts de négociation (OCRI)", "canada", ("ciro.ca",), 0, "https://www.ciro.ca/",
      ecartee="Le site bloque les robots (vérification anti-robots)"),
    # Lot 3d (3 octobre 2026) : robots.txt et conditions lus avec notre identification
    S("war_contrats", "Pentagone : contrats du jour (war.gov)", "militaire", ("war.gov", "defense.gov"), 0,
      "https://www.war.gov/News/Contracts/", ecartee="Le site refuse les robots (erreur 403)"),
    S("gao_contestations", "GAO : contestations de contrats", "militaire", ("gao.gov",), 0,
      "https://www.gao.gov/legal/bid-protests/search", ecartee="Le site refuse les robots (erreur 403)"),
    S("nbim", "Fonds souverain de la Norvège (NBIM)", "baleines", ("nbim.no",), 0,
      "https://www.nbim.no/en/investments/all-investments/",
      ecartee="Ses conditions interdisent les copies automatiques du site ; ses actions américaines restent suivies "
              "par son 13F (SEC)"),
    S("communiques", "Communiqués officiels des compagnies", "compagnies",
      ("globenewswire.com", "newsfilecorp.com", "newswire.ca", "prnewswire.com"), 0, "https://www.globenewswire.com/",
      ecartee="Conditions des agences de presse : lecture personnelle, sans robots ni copie (GlobeNewswire : robots.txt "
              "sans réponse) ; les communiqués importants arrivent par les 8-K de la SEC"),
    S("prix_yahoo", "Prix des actions (Yahoo, non officiel)", "compagnies", ("yahoo.com",), 0, "https://finance.yahoo.com/",
      officielle=False, ecartee="Robots interdits par le robots.txt de son API des prix et par ses conditions d'utilisation"),
    # Lot G : jamais un signal (la SEC précise que ce n'est pas une preuve de vente à découvert abusive) ; seulement le
    # prix de clôture de la veille de chaque ligne, pour mesurer les résultats de Radar (voir resultats.py)
    S("sec_ftd", "SEC : prix de clôture des fichiers d'échecs de livraison (seulement pour mesurer les résultats de Radar)",
      "compagnies", ("sec.gov",), 1, "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data",
      officielle=False, passages=("soir",)),
]

SOURCES: dict[str, Source] = {s.id: s for s in _LISTE}
assert len(SOURCES) == len(_LISTE), "identifiant de source en double"
