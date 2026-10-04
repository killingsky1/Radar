# Recherche avant le plan de match — vérifiée en direct par le labo (GitHub), avec les règles du robot
Date : 2026-10-04 00:03 UTC

## A. robots.txt et conditions d'utilisation
- FINRA ventes à découvert (page des fichiers) : robots.txt de www.finra.org → statut 200 · délai None · PERMIS · https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files
- FINRA fichier de ventes à découvert (CDN) : robots.txt de cdn.finra.org → statut 403 · délai None · INTERDIT · https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260915.csv
- FINRA API : robots.txt de api.finra.org → statut 404 · délai None · PERMIS · https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest
- FINRA conditions : robots.txt de www.finra.org → statut 200 · délai None · PERMIS · https://www.finra.org/terms-of-use
- IEX HIST (liste des fichiers) : robots.txt de iextrading.com → statut 200 · délai None · PERMIS · https://iextrading.com/api/1.0/hist?date=20261002
- IEX page des données : robots.txt de iextrading.com → statut 200 · délai None · PERMIS · https://iextrading.com/trading/market-data/
- IEX conditions HIST : robots.txt de www.iexexchange.io → statut 200 · délai None · PERMIS · https://www.iexexchange.io/legal/hist-data-terms
- Nasdaq Trader conditions : robots.txt de www.nasdaqtrader.com → statut 200 · délai None · PERMIS · https://www.nasdaqtrader.com/Trader.aspx?id=CopyDisclaimMain
- Nasdaq Trader liste des symboles : robots.txt de www.nasdaqtrader.com → statut 200 · délai None · PERMIS · https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt
- SEC API data.sec.gov (frames) : robots.txt de data.sec.gov → statut 404 · délai None · PERMIS · https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2025.json
### FINRA conditions : HTTP 200, 23038 caractères · https://www.finra.org/terms-of-use
  > } Terms of Use | FINRA.org Skip to main content FINRA Utility Menu About Us Careers BrokerCheck Data Media Center For Firms For the Public FINRA DATA FINRA Data provides non-commercial use of data, specifically the ability to save data views and create and manage a Bond Watchlist.
  > File a Complaint FINRA Securities Helpline for Seniors Dispute Resolution Services SIPC Protection Avenues for Recovery of Losses FINRA Utility Menu About Us Careers BrokerCheck Data Media Center For Firms For the Public FINRA DATA FINRA Data provides non-commercial use of data, specifically the ability to save data views and create and manage a Bond Watchlist.
  > You are not permitted to and shall not provide us with personal information if you are under 13 years of age.
  > The works of authorship contained in the FINRA Website, including, but not limited to, all design, text, sound recordings, and images—are owned, except as otherwise expressly stated, by FINRA and may not be copied, reproduced, transmitted, displayed, performed, distributed, rented, sublicensed, uploaded, posted, framed, altered, stored for subsequent use, or otherwise used in whole or in part in any manner without FINRA's prior written consent, except to the extent that such use constitutes "fair use" under the Copyright Act of 1976 (17 U.S.C.
  > Permitted Uses Subject to Restrictions, below, and any other restrictions in these Terms of Use, the content and material provided through the FINRA Website shall be used ONLY for your own non-commercial personal or professional use.
  > use any process to monitor or copy the FINRA Website in bulk, or use any data mining, scraping or harvesting tools (including robots), or any similar data-gathering or extraction tools;
  > You and FINRA agree to submit to personal jurisdiction in that court and expressly waive any right to a jury trial.
### IEX conditions HIST : HTTP 200, 34293 caractères · https://www.iexexchange.io/legal/hist-data-terms
  > } /* Superscript fixes for Public Sans font */ .tm-mark { font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  > } } /* attribute to hide things in the designer*/ .wf-design-mode [designer-hide='true'] { display: none !important;
  > // guard if element isn't on the page var updateState = function () { var isOpen = targetElement.hasAttribute("data-nav-menu-open");
  > // Run once on load in case attribute is already present updateState();
  > 01 If you distribute, sell, lease, furnish, or otherwise permit or provide access to Investors’ Exchange LLC (“IEX”) historical data, you must cite IEX as the source with the following text and link: “Data provided for free by IEX.
  > } catch (e) { // Ignore invalid URLs } // If it's already set to _blank OR matches our conditions, make sure it has the right attributes if ($link.attr('target') === '_blank' || isDocumentLink || isDisciplinaryLink || isExternal) { $link.attr('target', '_blank').attr('rel', 'noopener noreferrer');
  > } // jQuery code to add/remove class "is-active" to elements with [mobile-search="content"] attribute $(document).ready(function() { // When input with [mobile-search="trigger"] is focused or active $('[mobile-search="trigger"]').on('focus', function() { $('[mobile-search="content"]').addClass('is-active');
### Nasdaq Trader conditions : HTTP 200, 20819 caractères · https://www.nasdaqtrader.com/Trader.aspx?id=CopyDisclaimMain
  > or one of its affiliates, and may not be copied, reproduced, transmitted, displayed, performed, distributed, rented, sublicensed, altered, stored for subsequent use or otherwise used in whole or in part in any manner without the prior written consent of Nasdaq, except to the extent that such use constitutes "fair use" of the Content under the Copyright Act of 1976 (17 U.S.C.
  > §107), as amended, and except for one temporary copy in a single computer's memory and one unaltered permanent copy to be used by the viewer for personal and non-commercial use only.
  > Except as portions of this website may specific allow by separate agreement, any other use of the Content contained in this site requires the prior written consent of Nasdaq and may require a fee.
  > ACTSM Aggregated Depth at PriceSM (ADAPSM) Automated Confirmation Transaction ServiceSM CAESSM Closing CrossSM CubesSM DepthChartSM ExACTSM Exchange Analysis and Compliance Tracking SystemTM EQ FundSM EQQQSM FlashQuotesSM iMSM INETSM Index TrackersSM InfoQuotesSM Level 1 ServiceSM Level 2SM LogoTickerTM Market ForcesSM MarketLinkSM MarketSite ExperienceSM Market velocitySM MBARSSM Multi QuotesSM Mutual Fund Quotation ServiceSM (MFQSSM) NaqcessSM Nasdaq Corporate Services NetworkSM Nasdaq Global MarketSM Nasdaq Global Select MarketSM Nasdaq Index WatchSM Nasdaq InsideSM Nasdaq InterMarket Quotation ServiceSM (iM QuotesSM) Nasdaq InterMarketSM Nasdaq InternationalSM Nasdaq Market AnaltixSM Nas
### IEX HIST : HTTP 200
  - DEEP IEXTP1 1.0 · 13.8 Go · 20261002 · www.googleapis.com
  - DPLC IEXTP1 1.0 · 16.3 Go · 20261002 · www.googleapis.com
  - DPLS IEXTP1 1.0 · 13.0 Go · 20261002 · www.googleapis.com
  - TOPS IEXTP1 1.6 · 13.0 Go · 20261002 · www.googleapis.com
### FINRA page des fichiers : HTTP 200 · liens : ['/finra-data/browse-catalog/equity-short-interest', '/finra-data/browse-catalog/equity-short-interest/data', '/finra-data/equity-short-interest/glossary', 'https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260915.csv', 'https://otce.finra.org/otce/EquityShortInterest/staticArchives?startDate=2014-01-01&amp;endDate=2018-11-03&amp;dateDisplay=November%203,%202018', 'https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files']

## B. Prix publiés par la SEC (fichiers d'échecs de livraison)
- page https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data : HTTP 200 · 411 fichiers · derniers : ['cnsfails202003b.zip', 'cnsfails202004a.zip', 'cnsfails202004b.zip']
- cnsfails202004a.zip : 45440 lignes · 9977 symboles · 9 jours (20200401 → 20200414)
- cnsfails202004b.zip : 58639 lignes · 10281 symboles · 12 jours (20200415 → 20200430)
- listes du jour (hausse et baisse) : 6/16 symboles ont au moins un prix · en moyenne 58 % des 21 jours
  CPHC 0/21 · CRESY 15/21 · FLNA 0/21 · FUL 5/21 · GME 21/21 · GPUS 0/21 · HELP 0/21 · LESL 0/21 · MNSO 0/21 · NYAX 0/21 · PAM 18/21 · PRHI 0/21 · QTEX 0/21 · SAMG 5/21 · TKLF 0/21 · XENE 9/21
- section Argent (30 jours) : 148/220 symboles ont au moins un prix · en moyenne 53 % des 21 jours

## C. Rachats d'actions déclarés en XBRL (API officielle data.sec.gov, « frames »)
- us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2025 : 2268 compagnies · plus gros : Apple Inc. 90.7 G$ · Alphabet Inc. 45.7 G$ · NVIDIA CORP 40.1 G$
- us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2026Q1 : 1483 compagnies · plus gros : Salesforce, Inc. 27.2 G$ · NVIDIA CORP 19.3 G$ · JPMORGAN CHASE & CO 8.3 G$
- us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2026Q2 : 134 compagnies · plus gros : Netflix, Inc. 4.7 G$ · McKESSON CORPORATION 2.5 G$ · T-MOBILE US, INC. 2.3 G$
- us-gaap/StockRepurchasedDuringPeriodValue/USD/CY2026Q2 : 441 compagnies · plus gros : PROSHARES TRUST II 4.9 G$ · FEDERAL HOME LOAN BANK OF DE 4.1 G$ · FEDERAL HOME LOAN BANK OF AT 4.0 G$
- us-gaap/StockRepurchaseProgramAuthorizedAmount1/USD/CY2026Q2I : HTTP 404
- srt/StockRepurchaseProgramAuthorizedAmount1/USD/CY2026Q2I : 145 compagnies · plus gros : Aon plc 35.0 G$ · O Reilly Automotive Inc 31.8 G$ · Analog Devices, Inc. 26.7 G$

## D. Fins de blocage : tous les prospectus 424B4 de juillet à septembre 2026 (règle stricte)
- 424B4 déposés : avril à juin 170 · juillet à septembre 114 (index officiels de la SEC)
- lus : 114 · vraies entrées en bourse (sans SPAC ni inscription directe) : 25 · PUBLIABLES avec la règle stricte : 12
- raisons d'écarter une vraie entrée en bourse : {'clause de levée anticipée': 5, 'aucune durée': 5, 'date du prospectus loin du dépôt': 1, 'plusieurs durées': 1, 'date du prospectus absente': 2}
- durées des publiables : {90: 1, 180: 11}
- deux preuves de la date (couverture + « 25 jours ») qui concordent : 8/12
  - Apnimed, Inc. · prospectus 2026-07-30 · 180 jours → fin 2027-01-26 · 0001193125-26-328422
  - ADARx Pharmaceuticals, Inc. · prospectus 2026-09-24 · 180 jours → fin 2027-03-23 · 0001193125-26-403094
  - BlossomHill Therapeutics, Inc. · prospectus 2026-08-06 · 180 jours → fin 2027-02-02 · 0001193125-26-340215
  - Scribe Therapeutics, Inc. · prospectus 2026-07-23 · 180 jours → fin 2027-01-19 · 0001193125-26-316503
  - Bending Spoons S.p.A. · prospectus 2026-06-30 · 180 jours → fin 2026-12-27 · 0001104659-26-079884
  - Latigo Biotherapeutics, Inc. · prospectus 2026-08-06 · 180 jours → fin 2027-02-02 · 0001193125-26-340329
  - Attovia Therapeutics, Inc. · prospectus 2026-08-04 · 180 jours → fin 2027-01-31 · 0001193125-26-334997
  - Electra Therapeutics, Inc. · prospectus 2026-09-17 · 180 jours → fin 2027-03-16 · 0001193125-26-395670
  - Ticketplus Ltd. · prospectus 2026-08-06 · 180 jours → fin 2027-02-02 · 0001213900-26-086641
  - ITG, Inc./DE/ · prospectus 2026-06-30 · 180 jours → fin 2026-12-27 · 0001193125-26-292853
  - SK hynix Inc. · prospectus 2026-07-09 · 90 jours → fin 2026-10-07 · 0001193125-26-299963
  - Jersey Mike's Subs Inc. · prospectus 2026-07-29 · 180 jours → fin 2027-01-25 · 0001193125-26-326453

## E. Rachats d'actions annoncés : 8-K du 1er et du 2 octobre 2026 (points 2.02, 7.01, 8.01 ; document et EX-99)
- 20261001 : 259 8-K
- 20261002 : 192 8-K
- 8-K lus : 451 · avec 2.02, 7.01 ou 8.01 : 245 · phrases candidates : 20 · {"hausse d'un programme": 3, "reste d'un ancien programme": 7, 'à lire': 10}
  - [hausse d'un programme] Accenture plc (EX-99, 0001467373-26-000037) : •Accenture’s total outstanding authority is approximately $6.9 billion, which includes $6.0 billion in additional share repurchase authority approved by the company’s Board of Directors in September 2026.
  - [hausse d'un programme] National Bank Holdings Corp (8-K, 0001104659-26-112856) : Item 8.01.Other Events On September 30, 2026, the Board of Directors of the Company approved an additional authorization to repurchase up to $40.1 million of the Company's Class A common stock.
  - [hausse d'un programme] National Bank Holdings Corp (8-K, 0001104659-26-112856) : Following approval of the additional authorization, the Company will have aggregate repurchase authority of $100.0 million.
  - [à lire] NEWS CORP (8-K, 0001564708-26-000213) : As previously reported, under News Corporation's (the "Company's") stock repurchase program (the "Repurchase Program"), the Company is authorized to acquire from time to time up to $1 billion in the aggregate of the Company's outstanding shares of Class A common stock and Class B common stock.
  - [à lire] NEWS CORP (EX-99.1, 0001564708-26-000213) : The company is authorized to acquire up to an aggregate of US$1 billion of the Company’s Nasdaq-listed Class A common stock and Class B common stock under the 2025 Repurchase Program.
  - [à lire] American Outdoor Brands, Inc. (8-K, 0001808997-26-000052) : On October 1, 2026, we announced that our Board of Directors has approved a program to repurchase up to $10.0 million of our outstanding shares of common stock commencing on October 1, 2026 and ending on September 30, 2027.
  - [à lire] American Outdoor Brands, Inc. (8-K, 0001808997-26-000052) : Exhibit Number Description 99.1 Press release from the Registrant, dated October 1, 2026, entitled “American Outdoor Brands Approves $10 Million Share Repurchase Program” 104 Cover Page Interactive Data File (embedded within the Inline XBRL document) SIGNATURES Pursuant to the requirements of the Securities Exchange Act of 1934, the registrant has duly caused this report to be signed on its behalf by the undersigned 
  - [à lire] American Outdoor Brands, Inc. (EX-99, 0001808997-26-000052) : 2 oct2026buybackprclean.htm EX-99 Document Exhibit 99.1 1800 N Route Z Columbia, MO 65202 (800) 338-9585 NASDAQ: AOUT Contact: Liz Sharp, VP, Investor Relations lsharp@aob.com (573) 303-4620 American Outdoor Brands Board of Directors Approves $10 Million Share Repurchase Program COLUMBIA, Mo., October 1, 2026 – American Outdoor Brands, Inc.
  - [à lire] American Outdoor Brands, Inc. (EX-99, 0001808997-26-000052) : (NASDAQ Global Select: AOUT), an innovation company that provides product solutions for outdoor enthusiasts, today announced that its Board of Directors has approved the repurchase of up to $10 million of the Company’s outstanding common stock (“shares”) commencing on October 1, 2026, and ending on September 30, 2027.
  - [à lire] NEWS CORP (8-K, 0001564708-26-000214) : As previously reported, under News Corporation's (the "Company's") stock repurchase program (the "Repurchase Program"), the Company is authorized to acquire from time to time up to $1 billion in the aggregate of the Company's outstanding shares of Class A common stock and Class B common stock.
  - [à lire] NEWS CORP (EX-99.1, 0001564708-26-000214) : The company is authorized to acquire up to an aggregate of US$1 billion of the Company’s Nasdaq-listed Class A common stock and Class B common stock under the 2025 Repurchase Program.

Durée totale : 16 min
