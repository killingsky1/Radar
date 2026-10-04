"""Données de TEST pour les captures (jamais publiées). Tous les titres commencent par « TEST »."""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "robot"))
from radar.models import Confirmation, Evenement, empreinte
from radar.run import executer
from radar.collecteurs.contrats_ca import fiche as fiche_contrat, trimestre

J = date.today()
def jour(n): return (J - timedelta(days=n)).isoformat()
def ev(i, source, cat, kind, titre, publie, url, **x):
    return Evenement(source=source, official_id=x.pop("numero", f"TEST-{i}"), category=cat, kind=kind, title=f"TEST : {titre}",
                     occurred_on=x.pop("occ", publie), published_on=publie, official_url=url,
                     sha256=empreinte(f"test{i}".encode()), parser_version="test", **x)

# Une ligne au format du portail du gouvernement ouvert (champs lus par le robot), avec des valeurs d'exemple
CONTRAT_TEST = {"_id": 1, "reference_number": "TEST-6", "owner_org": "dnd-mdn",
                "owner_org_title": "National Defence | Défense nationale", "vendor_name": "Colt Canada",
                "contract_date": jour(12), "contract_value": "307000000.00", "original_value": "307000000.00",
                "amendment_value": None, "description_fr": "Armes (exemple)", "instrument_type": "C",
                "reporting_period": trimestre(J), "fournisseur": "Colt Canada", "ministere": "Défense nationale",
                "montant": 3.07e8, "type": "contrat"}

RESULTAT_TEST = ("https://fiscaldata.treasury.gov/static-data/published-reports/auctions-query/results/R_"
                 + jour(5).replace("-", "") + "_1.pdf")

def faux(ctx):
    return [
        ev(1, "usaspending", "militaire", "contrat", "Lockheed Martin obtient un contrat de missiles", jour(0),
           "https://www.usaspending.gov/award/CONT_AWD_TEST_1", numero="CONT_AWD_TEST_1", tickers=["LMT"],
           amount_min=2.0e9, amount_max=2.0e9, currency="USD", entities=["Lockheed Martin Corp."], direction=1,
           data={"id": "CONT_AWD_TEST_1", "montant": 2.0e9, "signe_le": jour(95), "fournisseur": "LOCKHEED MARTIN CORP",
                 "details": [["Fournisseur", "LOCKHEED MARTIN CORP"], ["Ministère ou agence", "Department of Defense"],
                             ["Sommes engagées", "2 G$"]]},
           confirmations=[Confirmation("sec_8k", "https://www.sec.gov/test/8k.htm", "TEST-8K")]),
        ev(2, "sec_form4", "compagnies", "achat_initie", "le PDG de Nvidia achète 50 000 actions", jour(0),
           "https://www.sec.gov/test/form4.xml", occ=jour(2), tickers=["NVDA"], amount_min=6.2e6, amount_max=6.2e6,
           entities=["Jensen Huang", "NVIDIA CORP"], direction=1,
           data={"symbole_declare": "NVDA", "symboles_sec": ["NVDA"], "actions": 50000, "roles": ["CEO"], "prix_moyen": 124.0,
                 "transactions": [{"code": "P", "acquis_cede": "A", "actions": 50000, "prix": 124.0, "date": jour(2),
                                   "apres": 1050000}]}),
        ev(3, "registre_federal", "gouvernement", "presidentiel", "nouveaux tarifs sur l'acier (publication demain)", jour(0),
           "https://www.federalregister.gov/public-inspection/2026-99999/test", numero="2026-99999",
           entities=["Executive Office of the President"],
           data={"numero": "2026-99999", "etape": "inspection_publique", "numero_dans_le_texte": True}),
        ev(4, "sec_13dg", "baleines", "plus_5_pourcent", "un fonds dépasse 5 % d'Intel", jour(1),
           "https://www.sec.gov/test/13d.xml", tickers=["INTC"], entities=["Fonds activiste (exemple)"], direction=1,
           data={"pourcentage": 5.4, "cik_emetteur": "50863", "cik_sujet_entete": "0000050863",
                 "extrait_but": "The Reporting Persons believe the Shares are undervalued (exemple)."}),
        ev(5, "chambre_ptr", "politiciens", "achat_elu", "une personne élue achète des actions de Microsoft", jour(1),
           "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/test.pdf", occ=jour(20), tickers=["MSFT"],
           amount_min=15001.0, amount_max=50000.0, entities=["Élu·e (exemple)", "MICROSOFT CORP"], direction=1,
           data={"lecture_complete": True, "recoupements": {"numero": True, "nom": True}, "nom_sec": "MICROSOFT CORP",
                 "elu": "Élu·e (exemple)", "circonscription": "ZZ01",
                 "transactions": [{"proprietaire": "SP", "actif": "Microsoft Corporation - Common Stock (MSFT) [ST]",
                                   "date": jour(20), "montant": "$15,001 - $50,000", "partielle": False}]}),
        ev(6, "contrats_ca_10k", "canada", "contrat_federal", "contrat de fusils pour les Forces armées canadiennes", jour(2),
           fiche_contrat(CONTRAT_TEST), numero="dnd-mdn:TEST-6", occ=jour(12), amount_min=3.07e8, amount_max=3.07e8,
           currency="CAD", entities=["Colt Canada", "Défense nationale"], data=CONTRAT_TEST),
        ev(7, "sec_8k", "compagnies", "evenement", "Apple annonce une acquisition", jour(3),
           "https://www.sec.gov/test/aapl-8k.htm", tickers=["AAPL"], entities=["Apple Inc."],
           data={"type": "8-K", "items": [{"item": "2.01", "libelle": "acquisition", "direction": 0}]}),
        ev(8, "chambre_ptr", "politiciens", "achat_elu", "transaction lue sur un site non officiel (piège)", jour(1),
           "https://www.capitoltrades.com/trades/test", occ=jour(15), tickers=["NVDA"],
           amount_min=15001.0, amount_max=50000.0),
        # Pour le score : un groupe d'achats chez AMD (directrice financière + administrateur) et un 13G sans points ;
        # une faillite et une vente du PDG chez Exemple Corp. (2 familles à la baisse : bonus).
        ev(9, "sec_form4", "compagnies", "achat_initie", "la directrice financière d'AMD achète 20 000 actions", jour(1),
           "https://www.sec.gov/test/amd-form4-1.xml", tickers=["AMD"], amount_min=3.1e6, amount_max=3.1e6,
           entities=["Directrice financière (exemple)", "ADVANCED MICRO DEVICES INC"], direction=1,
           data={"symbole_declare": "AMD", "symboles_sec": ["AMD"], "actions": 20000, "roles": ["Chief Financial Officer"],
                 "plan_10b5_1": False,
                 "transactions": [{"code": "P", "acquis_cede": "A", "actions": 20000, "prix": 155.0, "date": jour(1)}]}),
        ev(10, "sec_form4", "compagnies", "achat_initie", "un administrateur d'AMD achète 5 000 actions", jour(1),
           "https://www.sec.gov/test/amd-form4-2.xml", occ=jour(2), tickers=["AMD"], amount_min=7.5e5, amount_max=7.5e5,
           entities=["Administrateur (exemple)", "ADVANCED MICRO DEVICES INC"], direction=1,
           data={"symbole_declare": "AMD", "symboles_sec": ["AMD"], "actions": 5000, "roles": ["administrateur"],
                 "plan_10b5_1": False,
                 "transactions": [{"code": "P", "acquis_cede": "A", "actions": 5000, "prix": 150.0, "date": jour(2)}]}),
        ev(11, "sec_13dg", "baleines", "plus_5_pourcent", "un fonds indiciel dépasse 5 % d'AMD (13G)", jour(2),
           "https://www.sec.gov/test/amd-13g.xml", tickers=["AMD"], entities=["Fonds indiciel (exemple)", "ADVANCED MICRO DEVICES INC"],
           data={"type": "SCHEDULE 13G", "pourcentage": 6.1, "cik_emetteur": "2488", "cik_sujet_entete": "0000002488"}),
        ev(12, "sec_8k", "compagnies", "evenement_8k", "Exemple Corp. se place sous la protection de la loi sur les faillites",
           jour(1), "https://www.sec.gov/test/xmpl-8k.htm", tickers=["XMPL"], entities=["Exemple Corp."], direction=-1,
           data={"type": "8-K", "items": [{"item": "1.03", "libelle": "faillite ou mise sous séquestre", "direction": -1}]}),
        ev(14, "oge_278t", "politiciens", "rapport_278t", "une ministre (exemple) dépose un rapport de transactions (278-T)",
           jour(4), "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/0123456789ABCDEF0123456789ABCDEF/$FILE/Test-278T.pdf",
           numero="0123456789ABCDEF0123456789ABCDEF", entities=["Ministre (exemple)", "Department of Test"],
           notes=["Liste seulement : le robot ne lit pas le contenu du rapport."],
           data={"nom": "Exemple, Ministre", "titre": "Secretary", "agence": "Department of Test", "niveau": "Level I",
                 "ajoute_le": jour(4), "modifie_le": None, "pdf_valide": True, "taille": 5000,
                 "lecture_complete": True, "declarant_concorde": True, "signe_le": jour(4),
                 "transactions": [
                     {"n": "1", "description": "Exemple Corp. (XMPL)", "type": "Sale", "date": jour(30), "avis": "No",
                      "montant": "$15,001 - $50,000", "note": None, "symbole": "XMPL"},
                     {"n": "2", "description": "Fonds privé (exemple) LP", "type": "Purchase", "date": jour(29),
                      "avis": "Yes", "montant": "$1,001 - $15,000", "note": "Placement fait par le gestionnaire (exemple)."}]}),
        # Canada (lot 3c) : un règlement de la Gazette et un examen de fusion, avec l'encadré « Détails » et la mention exigée
        ev(15, "gazette_ca", "canada", "reglement", "Décret imposant une surtaxe (exemple) (DORS/2026-999)", jour(5),
           "https://gazette.gc.ca/rp-pr/p2/2026/test/html/sor-dors999-fra.html", occ=jour(19), numero="DORS/2026-999",
           entities=["Tarif des douanes"], currency="CAD",
           data={"numero": "DORS/2026-999", "titre": "Décret imposant une surtaxe (exemple)", "loi": "Tarif des douanes",
                 "enregistre_le": jour(19), "numero_index": "DORS/2026-999",
                 "resume": "Le présent décret impose une surtaxe sur des marchandises (exemple).",
                 "details": [["Numéro", "DORS/2026-999"], ["Loi", "Tarif des douanes"], ["Enregistré le", jour(19)]]}),
        ev(16, "concurrence_ca", "canada", "fusion_examen_conclu",
           "Bureau de la concurrence : examen de fusion conclu (lettre de non-intervention), Acheteur (exemple) / Cible (exemple)",
           jour(6), "https://bureau-concurrence.canada.ca/fr/fusions-acquisitions/rapport-examens-fusions-termines",
           occ=jour(8), numero="TEST-fusion:conclu", entities=["Acheteur (exemple)", "Cible (exemple)"], currency="CAD",
           data={"parties": "Acheteur (exemple) / Cible (exemple)", "acquereur": "Acheteur (exemple)", "cibles": ["Cible (exemple)"],
                 "debut": jour(30), "conclusion": jour(8), "scian": "5415", "code": "LNI",
                 "resultat": "lettre de non-intervention",
                 "details": [["Acquéreur", "Acheteur (exemple)"], ["Visé(s)", "Cible (exemple)"],
                             ["Résultat", "lettre de non-intervention"]]}),
        # Canada (lot 3c, livraison 2) : un nouveau médicament de Santé Canada et un rapport de la CCC (ses lignes)
        ev(17, "sante_canada", "canada", "approbation_sante_canada", "Santé Canada : nouveau médicament autorisé, EXEMPLA (exemple)",
           jour(7), "https://health-products.canada.ca/noc-ac/nocInfo?lang=fre&no=99999", numero="99999",
           entities=["Fabricant (exemple)"], currency="CAD",
           data={"numero": 99999, "classe": "Nouvelle substance active (NSA)", "actif": "1", "marques": ["EXEMPLA"],
                 "ingredients": [{"nom": "exemplamab", "dose": "10 MG"}], "fiches_meme_avis": True,
                 "details": [["Médicament", "EXEMPLA"], ["Ingrédient(s)", "exemplamab 10 MG"], ["Fabricant", "Fabricant (exemple)"]]}),
        ev(18, "ccc", "canada", "transactions_signees", "Corporation commerciale canadienne : 2 transactions signées (exemple)",
           jour(9), "https://www.ccc.ca/wp-content/uploads/2026/07/TEST.pdf", occ=jour(40), numero="TEST-ccc",
           entities=["Corporation commerciale canadienne"], currency="CAD", amount_min=1.1e6, amount_max=6.0e6,
           data={"debut": jour(130), "fin": jour(40), "fin_lien": jour(40), "nombre": 2,
                 "transactions": [
                     {"exportateur": "Exportateur (exemple)", "destination": "United States",
                      "description": "Defence Products / Produits de défense", "min": 1.0e6, "max": 5.0e6,
                      "fourchette": "1 M$ à 5 M$"},
                     {"exportateur": "Canadian Exporter", "destination": "Canada",
                      "description": "Medical Equipment / Équipement médical", "min": 100000.0, "max": 1.0e6,
                      "fourchette": "100 000 $ à 1 M$"}]}),
        # Lot 3d : une adjudication du Trésor (détails officiels) et une directive de la douane (CSMS)
        ev(19, "tresor", "gouvernement", "adjudication", "Trésor américain : adjudication de 44 G$ sur 7 ans (exemple)",
           jour(5), RESULTAT_TEST, numero="TESTCUSIP:" + jour(5), amount_min=44e9, amount_max=44e9, currency="USD",
           entities=["Trésor américain"],
           data={"type": "Note", "adjudication": jour(5), "document": RESULTAT_TEST.rsplit("/", 1)[1], "taux": 4.5,
                 "demande_offre": 2.4, "offres_competitives_acceptees": 43e9,
                 "acceptees": {"indirect_bidder": 25e9, "direct_bidder": 13e9, "primary_dealer": 5e9},
                 "details": [["Montant offert", "44 G$"], ["Taux retenu (le plus élevé accepté)", "4,500 %"],
                             ["Demande / offre", "2,40 (moyenne des 6 précédentes : 2,50)"]]}),
        ev(20, "tarifs", "gouvernement", "directive_douane",
           "Douane américaine : GUIDANCE: Section 232 Duties on Imports of Example Articles", jour(6),
           "https://content.govdelivery.com/accounts/USDHSCBP/bulletins/test20", numero="99999999",
           entities=["U.S. Customs and Border Protection"],
           data={"numero": "99999999", "guid": "99999999", "envoye_le": jour(6) + "T17:42:00-04:00",
                 "titre_officiel": "GUIDANCE: Section 232 Duties on Imports of Example Articles",
                 "details": [["Message", "CSMS # 99999999"], ["Proclamations citées", "11020"],
                             ["Extrait", "This message provides guidance (example)."]]}),
        ev(21, "participations_gouv", "gouvernement", "participation_gouv",
           "MP Materials : un 8-K dit que le ministère américain du Commerce reçoit, détient ou revend des titres de la "
           "compagnie (exemple)", jour(7), "https://www.sec.gov/Archives/edgar/data/1801368/test-index.htm",
           numero="0001801368-26-999999", tickers=["MP"], entities=["MP Materials Corp.", "Gouvernement américain"],
           data={"points": ["1.01", "3.02"], "ministere": "Commerce",
                 "documents": [{"url": "https://www.sec.gov/Archives/edgar/data/1801368/test.htm", "type": "8-K",
                                "extraits": ["On August 22, 2025, the Company entered into an agreement with the United "
                                             "States Department of Commerce to issue shares of common stock (exemple)."]}],
                 "details": [["Compagnie", "MP Materials Corp."], ["Ministère", "ministère du Commerce"],
                             ["Extrait (8-K)", "On August 22, 2025, the Company entered into an agreement with the "
                                               "United States Department of Commerce to issue shares of common stock "
                                               "(exemple)."]]}),
        ev(13, "sec_form4", "compagnies", "vente_initie", "le PDG d'Exemple Corp. vend 100 000 actions", jour(1),
           "https://www.sec.gov/test/xmpl-form4.xml", tickers=["XMPL"], amount_min=1.5e6, amount_max=1.5e6,
           entities=["PDG (exemple)", "Exemple Corp."], direction=-1,
           data={"symbole_declare": "XMPL", "symboles_sec": ["XMPL"], "actions": 100000, "roles": ["CEO"], "plan_10b5_1": False,
                 "prix_moyen": 15.0,
                 "transactions": [{"code": "S", "acquis_cede": "D", "actions": 100000, "prix": 15.0, "date": jour(1),
                                   "apres": 400000}]}),
        # La même vente, déclarée aussi par une entité liée (ex. le fonds du PDG) : une seule ligne dans le fil
        ev(22, "sec_form4", "compagnies", "vente_initie", "Fonds lié (exemple) vend 100 000 actions d'Exemple Corp.", jour(1),
           "https://www.sec.gov/test/xmpl-form4-fonds.xml", tickers=["XMPL"], amount_min=1.5e6, amount_max=1.5e6,
           entities=["Fonds lié (exemple)", "Exemple Corp."], direction=-1,
           data={"symbole_declare": "XMPL", "symboles_sec": ["XMPL"], "actions": 100000, "roles": ["10% owner"], "plan_10b5_1": False,
                 "prix_moyen": 15.0,
                 "transactions": [{"code": "S", "acquis_cede": "D", "actions": 100000, "prix": 15.0, "date": jour(1),
                                   "apres": 400000}]}),
    ]

def sans_amd(ctx):
    return [e for e in faux(ctx) if e.tickers[:1] != ["AMD"]]

# Congrès : le VRAI statut de H.R. 7008 et ses VRAIS votes (fichiers officiels gardés pour les tests du robot),
# plus une personne élue fictive (« Élu·e Exemple », circonscription ZZ01) et ses votes fictifs.
import gzip  # noqa: E402
import json  # noqa: E402
from radar.collecteurs import congres as cg  # noqa: E402
FC = Path(__file__).resolve().parents[2] / "robot" / "tests" / "fixtures" / "congres"
def lu(nom): return gzip.decompress((FC / nom).read_bytes())
projet = cg.lire_projet(lu("BILLSTATUS-119hr7008.xml.gz"))
votes = {}
for info, nom in zip(projet["votes"], ("roll279.xml.gz", "roll280.xml.gz", "vote_119_2_00253.xml.gz")):
    v = (cg.lire_vote_chambre if info["chambre"] == "House" else cg.lire_vote_senat)(lu(nom))
    votes[f"{v['chambre'][0]}{info['numero']}-{v['date'][:4]}"] = {**v, "numero": info["numero"], "url": info["url"]}
votes["H279-2026"]["votes"]["Z000001"], votes["H280-2026"]["votes"]["Z000001"] = "Nay", "Yea"
cg._ecrire(cg.chemin_projet(sys.argv[1]), {**projet, "lu": datetime.now(timezone.utc).isoformat()})
cg._ecrire(cg.chemin_votes(sys.argv[1]), votes)
cg._ecrire(cg.chemin_congres(sys.argv[1]), {
    "chambre": {"ZZ01": {"nom": "Élu·e Exemple", "nom_famille": "Exemple", "bioguide": "Z000001", "parti": "I",
                         "comites": [{"nom": "Committee on Financial Services (exemple)", "role": "Chair"},
                                     {"nom": "Committee on Agriculture (exemple)", "role": None}]}},
    "senat": {}, "chefs": [], "lu": datetime.now(timezone.utc).isoformat()})

# Lobbying : 3 fiches fictives (TEST) au format exact du robot (lobbying.bilan) : montants, aucun rapport, trop large.
from radar.collecteurs import lobbying as lb  # noqa: E402
annee, trim = lb.dernier_trimestre_complet(datetime.now(timezone.utc).date())
def rapport(uuid, qui, soi_meme, montant, sujets):
    return {"uuid": uuid, "type": f"Q{trim}", "registrant": qui, "registrant_id": uuid, "client": "TEST", "client_id": 1,
            "soi_meme": soi_meme, "sans_activite": False, "montant": montant, "poste": jour(70),
            "url": f"https://lda.gov/filings/public/filing/{uuid}/print/", "sujets": sujets, "sujets_officiels": {}}
lu = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
cache = {
    "AMD": {"nom": "ADVANCED MICRO DEVICES INC", "recherche": "ADVANCED", "pages": 1, "complet": True, "lu": lu,
            **lb.bilan("ADVANCED MICRO DEVICES INC", [rapport("test-1", "COMPAGNIE (EXEMPLE)", True, 1_230_000.0, ["TRD", "TAX"]),
                                                      rapport("test-2", "FIRME DE LOBBYING (EXEMPLE)", False, 40_000.0, ["TRD"])], trim)},
    "NVDA": {"nom": "NVIDIA CORP", "recherche": "NVIDIA", "pages": 1, "complet": True, "lu": lu, **lb.bilan("NVIDIA CORP", [], trim)},
    "XMPL": {"nom": "EXEMPLE CORP", "recherche": "EXEMPLE", "pages": 4, "complet": False, "lu": lu, **lb.bilan("EXEMPLE CORP", [], trim)},
}
c = lb.chemin_cache(sys.argv[1], annee, trim)
c.parent.mkdir(parents=True, exist_ok=True)
c.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

# Les sources branchées dans le vrai robot répondent « rien de neuf » ; le faux lecteur fournit les infos TEST.
from radar.collecteurs import COLLECTEURS  # noqa: E402
lecteurs = {sid: (lambda ctx: []) for sid in COLLECTEURS}
# Un site qui refuse le robot (403) aux 2 passages (2 heures d'écart) : « Refusée par le site »
from radar.http import ErreurSource  # noqa: E402
def refuse(ctx):
    raise ErreurSource("https://www.parl.ca/legisinfo/fr/projets-de-loi/json?parlsession=45-1 : HTTP 403")
lecteurs["legisinfo"] = refuse
# Fins de blocage (lot F) : 4 entrées en bourse fictives (TEST) faites par la vraie fonction du lecteur (blocage.evenement),
# fins dans 10, 40 et 80 jours, et une fin passée il y a 3 jours (montrée « Blocage terminé » dans la page du calendrier) ;
# prospectus de plus de 3 mois : hors du fil, comme les vrais du rattrapage (les compteurs de l'accueil ne changent pas).
from radar.collecteurs import blocage as bl  # noqa: E402
from radar.collecteurs.sec import DepotSec  # noqa: E402
def blocage_test(i, nom, symbole, fin_dans, duree=180):
    fin = J + timedelta(days=fin_dans)
    pros = fin - timedelta(days=duree)
    r = {"date_prospectus": pros.isoformat(), "duree_jours": duree, "fin_blocage": fin.isoformat(), "entree_en_bourse": True,
         "levee_anticipee": False, "ecart_ouvrables": 1,
         "preuves_date": [{"sorte": "couverture", "date": pros.isoformat(), "directe": True,
                           "phrase": f"The date of this prospectus is {pros:%B} {pros.day}, {pros.year}"}],
         "phrase_blocage": f"TEST : We, our directors and officers have agreed with the underwriters that for a period of "
                           f"{duree} days after the date of this prospectus, we and they will not sell."}
    depot = DepotSec(f"0009999999-26-00000{i}", "424B4", (pros + timedelta(days=1)).isoformat(),
                     f"edgar/data/999999{i}/0009999999-26-00000{i}.txt")
    e = bl.evenement(depot, f"999999{i}", nom, {"ticker": symbole, "exchange": "Nasdaq"}, r, empreinte(f"blocage{i}".encode()))
    e.title = "TEST : " + e.title
    return e
BLOCAGES = [blocage_test(1, "Fusée Exemple Inc.", "FXMP", 10), blocage_test(2, "Biotech Exemple Inc.", "BXMP", 40),
            blocage_test(3, "Ferme Exemple Inc.", "AXMP", 80), blocage_test(4, "Ancienne Exemple Inc.", "PXMP", -3)]

# 2 passages : AMD entre dans les suggestions au 2e (pastille « Nouveau ») ; les autres y étaient déjà au 1er.
maintenant = datetime.now(timezone.utc).replace(microsecond=0)
lecteurs["sec_form4"] = sans_amd
print(executer(sys.argv[1], collecteurs=lecteurs, maintenant=maintenant - timedelta(hours=2)))
lecteurs["sec_form4"] = faux
print(executer(sys.argv[1], collecteurs=lecteurs, maintenant=maintenant))
# Le calendrier : les blocages TEST sont ajoutés APRÈS les passages (leurs prospectus ont plus de 3 mois ; les données de
# test n'ont pas un fichier par mois comme les vraies, donc ils entreraient dans le fil de test). Même calcul que le robot.
from radar import calendrier  # noqa: E402
from radar.publish import _ecrire_compact  # noqa: E402
from radar.store import Depot  # noqa: E402
from radar.validate import valider  # noqa: E402
Depot(sys.argv[1]).enregistrer([valider(e, J) for e in BLOCAGES])
_ecrire_compact(Path(sys.argv[1]) / "app" / "calendrier.json", calendrier.preparer(Depot(sys.argv[1]), J))
# Résultats de Radar (lot G) : entrées TEST de juillet à septembre 2026, mesurées par le vrai calcul du robot sur de VRAIS
# extraits des fichiers de la SEC (robot/tests/fixtures/lotG) : mesurée, en attente, pas de prix, nouveau CUSIP, à vérifier.
import io  # noqa: E402
import zipfile  # noqa: E402
from radar import resultats as rs  # noqa: E402
from radar.collecteurs import prix_sec as ps  # noqa: E402
from radar.run import Contexte  # noqa: E402
FG = Path(__file__).resolve().parents[2] / "robot" / "tests" / "fixtures" / "lotG"
class FauxSec:
    def get(self, url, entetes=None):
        if url == ps.PAGE:
            c = gzip.decompress((FG / "page_ftd.html.gz").read_bytes())
        else:
            cle = url.rsplit("cnsfails", 1)[1][:7]
            tampon = io.BytesIO()
            with zipfile.ZipFile(tampon, "w") as z:
                z.writestr(f"cnsfails{cle}.txt", (FG / f"cnsfails{cle}.txt").read_bytes())
            c = tampon.getvalue()
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()
def entree_test(symbole, nom, sens, quand, note):
    return {"symbole": symbole, "nom": f"TEST {nom}", "sens": sens, "entree": quand, "vue": quand[:10], "note10": note,
            "methode": "score-7"}
(Path(sys.argv[1]) / "resultats").mkdir(parents=True, exist_ok=True)
(Path(sys.argv[1]) / "resultats" / "suggestions.json").write_text(json.dumps({"entrees": [
    entree_test("AAPL", "Apple", "hausse", "2026-07-20T14:00:00+00:00", 8.1),
    entree_test("LESL", "Leslie's", "baisse", "2026-07-20T14:00:00+00:00", 1.1),
    entree_test("XMPL", "Exemple Corp.", "hausse", "2026-07-20T14:00:00+00:00", 7.4),
    entree_test("MSTU", "T-REX 2X", "hausse", "2026-08-14T21:00:00+00:00", 7.2),
    entree_test("CRE", "CRE8 Enterprise", "baisse", "2026-08-17T12:00:00+00:00", 2.0),
    entree_test("GME", "GameStop", "hausse", "2026-09-11T15:00:00+00:00", 9.3)]}), encoding="utf-8")
ps.PREMIER_FICHIER = "202607b"  # les vrais extraits gardés pour les tests : juillet à septembre 2026
ps.collecter(Contexte(client=FauxSec(), maintenant=maintenant, donnees=Path(sys.argv[1])))
from radar.publish import _ecrire  # noqa: E402
_ecrire(Path(sys.argv[1]) / "app" / "resultats.json", rs.calculer(Path(sys.argv[1]), maintenant))
# Rachats d'actions (lot H) : une annonce TEST (faite par la vraie fonction du lecteur à partir d'un faux dépôt dont la
# phrase suit la règle stricte), ajoutée APRÈS les passages comme les blocages (les compteurs du fil ne changent pas) ;
# l'onglet Argent est refait par le même calcul que le robot. Rachats faits (XBRL) : 2 compagnies des listes, au format
# exact du robot (rachats.pour_app).
from radar import argent  # noqa: E402
from radar.collecteurs import rachats as ra  # noqa: E402
from radar.score import jour_de_calcul  # noqa: E402
quand = jour_de_calcul(maintenant)
phrase = (f"TEST : On {quand:%B} {quand.day}, {quand.year}, the Board of Directors approved a new $1.5 billion share "
          f"repurchase program.")
class FauxDepot8k:
    def __init__(self):
        self.pages = {
            "https://www.sec.gov/files/company_tickers_exchange.json": json.dumps({"fields": ["cik", "name", "ticker", "exchange"],
                "data": [[2488, "ADVANCED MICRO DEVICES INC", "AMD", "Nasdaq"]]}).encode(),
            "https://www.sec.gov/Archives/edgar/data/2488/000000248826000099/0000002488-26-000099-index-headers.html":
                (f"<SEC-HEADER>CONFORMED PERIOD OF REPORT:\t{quand:%Y%m%d}\nITEM INFORMATION:\t\tOther Events\n"
                 "COMPANY CONFORMED NAME:\t\t\tADVANCED MICRO DEVICES INC\nCENTRAL INDEX KEY:\t\t\t0000002488\n</SEC-HEADER>").encode(),
            "https://www.sec.gov/Archives/edgar/data/2488/000000248826000099/0000002488-26-000099-index.htm":
                ('<table><tr><td>1</td><td><a href="/Archives/edgar/data/2488/000000248826000099/test-ex99.htm">test-ex99.htm</a>'
                 '</td><td>EX-99.1</td><td>1</td></tr></table>').encode(),
            "https://www.sec.gov/Archives/edgar/data/2488/000000248826000099/test-ex99.htm": f"<p>{phrase}</p>".encode(),
            # Fiche officielle (vérification de nouveauté) : aucun 8-K dans les 90 jours avant
            "https://data.sec.gov/submissions/CIK0000002488.json": json.dumps({"filings": {"recent": {
                "accessionNumber": [], "filingDate": [], "form": [], "items": []}}}).encode(),
        }
    def get(self, url, entetes=None):
        c = self.pages[url]
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()
depot8k = DepotSec("0000002488-26-000099", "8-K", quand.isoformat(), "edgar/data/2488/0000002488-26-000099.txt",
                   [("2488", "ADVANCED MICRO DEVICES INC")])
annonces = ra.lire_un(Contexte(client=FauxDepot8k(), maintenant=maintenant, donnees=Path(sys.argv[1])), depot8k)
assert len(annonces) == 1, annonces
annonces[0].title = "TEST : " + annonces[0].title
Depot(sys.argv[1]).enregistrer([valider(e, quand) for e in annonces])
tous = Depot(sys.argv[1]).lire("evenements")
fil = sorted((e for e in tous if not e.get("data", {}).get("meme_acte_que") and not e.get("data", {}).get("meme_transaction_que")),
             key=lambda d: (d["published_on"], d["collected_at"], d["id"]), reverse=True)
lignes, infos = argent.preparer(fil, quand)
_ecrire_compact(Path(sys.argv[1]) / "app" / "argent.json", lignes)
_ecrire_compact(Path(sys.argv[1]) / "app" / "argent_infos.json", infos)
(Path(sys.argv[1]) / "sec").mkdir(parents=True, exist_ok=True)
(Path(sys.argv[1]) / "sec" / "emetteurs.json").write_text(json.dumps({
    "AMD": {"cik": 2488, "nom": "Advanced Micro Devices, Inc.", "type": "compagnie", "formulaires_fonds": [], "lu": jour(1)},
    "NVDA": {"cik": 1045810, "nom": "NVIDIA CORP", "type": "compagnie", "formulaires_fonds": [], "lu": jour(1)}}), encoding="utf-8")
ra.chemin_xbrl(sys.argv[1]).write_text(json.dumps({"cadre": "CY2025", "adresse": ra.FRAMES.format(annee=2025),
    "par_cik": {"2488": [1_230_000_000, "2024-12-29", "2025-12-27", "0000002488-26-000018"]}}), encoding="utf-8")
score = json.loads((Path(sys.argv[1]) / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
_ecrire(Path(sys.argv[1]) / "app" / "rachats.json",
        ra.pour_app(Path(sys.argv[1]), [x["symbole"] for l in ("hausse", "baisse") for x in score.get(l, [])]))
