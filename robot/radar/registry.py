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
    S("sec_blocage", "SEC : fins de blocage après entrée en bourse", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=424B4"),
    S("sec_poursuites", "SEC : suspensions de cotation et procédures contre des compagnies cotées", "compagnies",
      ("sec.gov",), 1, "https://www.sec.gov/enforcement-litigation/trading-suspensions"),
    S("sec_ftd", "SEC : échecs de livraison d'actions", "compagnies", ("sec.gov",), 1,
      "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data", publication_max_jours=40),
    S("nbim", "Fonds souverain de la Norvège (NBIM)", "baleines", ("nbim.no",), 1,
      "https://www.nbim.no/en/investments/all-investments/", attente_heures=24 * 8),
    S("cftc_cot", "CFTC : positions des gros joueurs (contrats à terme)", "baleines", ("cftc.gov",), 1,
      "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm", publication_max_jours=10),
    S("communiques", "Communiqués officiels des compagnies", "compagnies",
      ("globenewswire.com", "newsfilecorp.com", "newswire.ca", "prnewswire.com"), 1,
      "https://www.globenewswire.com/rss/list", publication_max_jours=3),
    # Phase 2 : militaire et défense
    S("war_contrats", "Pentagone : contrats du jour (war.gov)", "militaire", ("war.gov", "defense.gov"), 2,
      "https://www.war.gov/News/Contracts/", publication_max_jours=5),
    S("ventes_armes", "Ventes d'armes à l'étranger (avis officiels au Registre fédéral)", "militaire",
      ("federalregister.gov",), 2,
      "https://www.federalregister.gov/documents/search?conditions%5Bterm%5D=%22Arms+Sales+Notification%22"),
    S("usaspending", "USAspending : contrats, subventions, prêts", "militaire", ("usaspending.gov",), 2,
      "https://www.usaspending.gov/", publication_max_jours=7),
    S("gao_contestations", "GAO : contestations de contrats", "militaire", ("gao.gov",), 2,
      "https://www.gao.gov/legal/bid-protests/search"),
    S("participations_gouv", "Gouvernement américain actionnaire", "gouvernement",
      ("sec.gov", "war.gov", "energy.gov", "commerce.gov", "whitehouse.gov"), 2, "https://www.sec.gov/edgar/search/"),
    S("contrats_ca_10k", "Contrats fédéraux de plus de 10 000 $", "canada", ("open.canada.ca",), 2,
      "https://search.open.canada.ca/contracts/", attente_heures=24 * 8, publication_max_jours=130),
    S("nouvelles_defense_ca", "Canada : nouvelles de la Défense nationale", "militaire", ("canada.ca",), 2,
      "https://www.canada.ca/fr/nouvelles.html", publication_max_jours=21),
    S("ccc", "Corporation commerciale canadienne", "canada", ("ccc.ca",), 2, "https://www.ccc.ca/en/announcements/"),
    # Phase 3 : politiciens
    S("chambre_ptr", "Chambre des représentants : transactions des élus", "politiciens", ("house.gov",), 3,
      "https://disclosures-clerk.house.gov/FinancialDisclosure", publication_max_jours=21),
    S("senat_ptr", "Sénat : transactions des sénateurs", "politiciens", ("senate.gov",), 3,
      "https://efdsearch.senate.gov/search/", publication_max_jours=30),
    S("oge_278t", "Président, vice-président et cabinet (OGE)", "politiciens", ("oge.gov",), 3,
      "https://www.oge.gov/"),
    # 27 pages officielles (dont 24 comités du Sénat) qui changent rarement : une fois par jour de semaine suffit
    S("comites", "Chefs et comités du Congrès (Chambre et Sénat)", "politiciens", ("house.gov", "senate.gov"), 3,
      "https://clerk.house.gov/xml/lists/MemberData.xml", passages=("matin",)),
    S("votes", "Votes du Congrès sur les projets de loi suivis", "politiciens", ("house.gov", "senate.gov"), 3,
      "https://clerk.house.gov/Votes"),
    S("lobbying", "Lobbying (LDA.gov)", "politiciens", ("lda.gov",), 3, "https://lda.gov/"),
    S("hr7008", "Suivi de H.R. 7008 (interdiction des transactions des élus)", "politiciens",
      ("govinfo.gov", "congress.gov"), 3, "https://www.congress.gov/bill/119th-congress/house-bill/7008"),
    # Phase 4 : gouvernement, régulateurs, économie
    S("registre_federal", "Registre fédéral : décrets, tarifs, sanctions (la veille)", "gouvernement",
      ("federalregister.gov", "govinfo.gov"), 4, "https://www.federalregister.gov/public-inspection/current",
      publication_max_jours=5),
    S("maison_blanche", "Maison-Blanche : actions présidentielles", "gouvernement", ("whitehouse.gov",), 4,
      "https://www.whitehouse.gov/presidential-actions/"),
    S("tarifs", "Tarifs : USTR, douanes, taux officiels", "gouvernement", ("ustr.gov", "cbp.gov", "usitc.gov"), 4,
      "https://ustr.gov/"),
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
    S("tresor", "Trésor américain (Fiscal Data)", "gouvernement", ("fiscaldata.treasury.gov", "treasury.gov"), 4,
      "https://fiscaldata.treasury.gov/"),
    S("nhtsa", "NHTSA : gros rappels d'autos (10 000 véhicules et plus)", "gouvernement", ("nhtsa.gov",), 4,
      "https://www.nhtsa.gov/recalls", publication_max_jours=21),
    S("nouvelles_eco_ca", "Canada : nouvelles des ministères économiques", "canada", ("canada.ca",), 4,
      "https://www.canada.ca/fr/nouvelles.html", publication_max_jours=10),
    S("banque_canada", "Banque du Canada : décisions de taux", "canada", ("bankofcanada.ca",), 4,
      "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/"),
    S("statcan", "Statistique Canada", "canada", ("statcan.gc.ca",), 4, "https://www150.statcan.gc.ca/"),
    S("gazette_ca", "Gazette du Canada (règlements, surtaxes)", "canada", ("gazette.gc.ca",), 4,
      "https://gazette.gc.ca/"),
    S("sante_canada", "Santé Canada : approbations de médicaments", "canada", ("canada.ca",), 4,
      "https://health-products.canada.ca/"),
    S("concurrence_ca", "Bureau de la concurrence : fusions", "canada", ("canada.ca",), 4,
      "https://competition-bureau.canada.ca/en/mergers-and-acquisitions/report-concluded-merger-reviews"),
    S("grands_projets_ca", "Grands projets d'intérêt national (Canada)", "canada", ("canada.ca",), 4,
      "https://www.canada.ca/en/one-canadian-economy/services/building-canada-act-projects-national-interest.html"),
    S("sanctions_ca", "Sanctions canadiennes", "canada", ("international.gc.ca",), 4, "https://www.international.gc.ca/"),
    S("legisinfo", "Projets de loi fédéraux (LEGISinfo)", "canada", ("parl.ca",), 4, "https://www.parl.ca/legisinfo/"),
    # Phase 5 : prix (non officiel, seulement pour le tableau de score)
    S("prix_yahoo", "Prix des actions (Yahoo, non officiel)", "compagnies", ("yahoo.com",), 5,
      "https://finance.yahoo.com/", officielle=False),
    # Laissées de côté
    S("sedi", "SEDI : initiés canadiens", "canada", ("sedi.ca",), 0, "https://www.sedi.ca/",
      ecartee="Payant : aucun accès gratuit pour un robot"),
    S("sedar", "SEDAR+ : documents des compagnies canadiennes", "canada", ("sedarplus.ca",), 0,
      "https://www.sedarplus.ca/", ecartee="Robots interdits par ses conditions d'utilisation"),
    S("finra", "FINRA : ventes à découvert", "compagnies", ("finra.org",), 0, "https://www.finra.org/finra-data",
      ecartee="Compte obligatoire"),
    S("sam_gov", "SAM.gov : contrats fédéraux", "militaire", ("sam.gov",), 0, "https://sam.gov/",
      ecartee="Compte obligatoire (USAspending le remplace)"),
    S("prix_payants", "Prix officiels payants (EODHD)", "compagnies", ("eodhd.com",), 0, "https://eodhd.com/",
      ecartee="Payant (Yahoo gratuit le remplace)"),
    S("sp_indices", "S&P : entrées et sorties d'indices", "compagnies", ("spglobal.com",), 0,
      "https://press.spglobal.com/",
      ecartee="Conditions d'utilisation de S&P Dow Jones Indices : robots interdits sans permission écrite"),
    S("canadabuys", "CanadaBuys : appels d'offres et contrats", "canada", ("canadabuys.canada.ca",), 0,
      "https://canadabuys.canada.ca/",
      ecartee="Son robots.txt interdit les robots sur tout le site, données ouvertes comprises"),
    S("arrets_negociation", "Arrêts de négociation (OCRI)", "canada", ("ciro.ca",), 0, "https://www.ciro.ca/",
      ecartee="Le site bloque les robots (vérification anti-robots)"),
]

SOURCES: dict[str, Source] = {s.id: s for s in _LISTE}
assert len(SOURCES) == len(_LISTE), "identifiant de source en double"
