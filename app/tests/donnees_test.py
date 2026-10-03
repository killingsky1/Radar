"""Données de TEST pour les captures (jamais publiées). Tous les titres commencent par « TEST »."""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "robot"))
from radar.models import Confirmation, Evenement, empreinte
from radar.run import executer

J = date.today()
def jour(n): return (J - timedelta(days=n)).isoformat()
def ev(i, source, cat, kind, titre, publie, url, **x):
    return Evenement(source=source, official_id=x.pop("numero", f"TEST-{i}"), category=cat, kind=kind, title=f"TEST : {titre}",
                     occurred_on=x.pop("occ", publie), published_on=publie, official_url=url,
                     sha256=empreinte(f"test{i}".encode()), parser_version="test", **x)

def faux(ctx):
    return [
        ev(1, "war_contrats", "militaire", "contrat", "Lockheed Martin obtient un contrat de missiles", jour(0),
           "https://www.war.gov/News/Contracts/test", tickers=["LMT"], amount_min=2.0e9, amount_max=2.0e9,
           entities=["Lockheed Martin Corp."], direction=1,
           confirmations=[Confirmation("sec_8k", "https://www.sec.gov/test/8k.htm", "TEST-8K")]),
        ev(2, "sec_form4", "compagnies", "achat_initie", "le PDG de Nvidia achète 50 000 actions", jour(0),
           "https://www.sec.gov/test/form4.xml", occ=jour(2), tickers=["NVDA"], amount_min=6.2e6, amount_max=6.2e6,
           entities=["Jensen Huang, PDG"], direction=1,
           data={"symbole_declare": "NVDA", "symboles_sec": ["NVDA"], "actions": 50000,
                 "transactions": [{"code": "P", "acquis_cede": "A", "actions": 50000, "prix": 124.0, "date": jour(2)}]}),
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
        ev(6, "contrats_ca_10k", "canada", "contrat", "contrat de fusils pour les Forces armées canadiennes", jour(2),
           "https://open.canada.ca/test", amount_min=3.07e8, amount_max=3.07e8, currency="CAD",
           entities=["Colt Canada"]),
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
                 "ajoute_le": jour(4), "modifie_le": None, "pdf_valide": True, "taille": 5000}),
        ev(13, "sec_form4", "compagnies", "vente_initie", "le PDG d'Exemple Corp. vend 100 000 actions", jour(1),
           "https://www.sec.gov/test/xmpl-form4.xml", tickers=["XMPL"], amount_min=1.5e6, amount_max=1.5e6,
           entities=["PDG (exemple)", "Exemple Corp."], direction=-1,
           data={"symbole_declare": "XMPL", "symboles_sec": ["XMPL"], "actions": 100000, "roles": ["CEO"], "plan_10b5_1": False,
                 "transactions": [{"code": "S", "acquis_cede": "D", "actions": 100000, "prix": 15.0, "date": jour(1)}]}),
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
# 2 passages : AMD entre dans les suggestions au 2e (pastille « Nouveau ») ; les autres y étaient déjà au 1er.
maintenant = datetime.now(timezone.utc).replace(microsecond=0)
lecteurs["sec_form4"] = sans_amd
print(executer(sys.argv[1], collecteurs=lecteurs, maintenant=maintenant - timedelta(hours=2)))
lecteurs["sec_form4"] = faux
print(executer(sys.argv[1], collecteurs=lecteurs, maintenant=maintenant))
