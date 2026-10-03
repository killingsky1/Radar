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
           data={"pourcentage": 5.4, "cik_emetteur": "50863", "cik_sujet_entete": "0000050863"}),
        ev(5, "chambre_ptr", "politiciens", "achat_elu", "une personne élue achète des actions de Microsoft", jour(1),
           "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/test.pdf", occ=jour(20), tickers=["MSFT"],
           amount_min=15001.0, amount_max=50000.0, entities=["Élu·e (exemple)", "MICROSOFT CORP"], direction=1,
           data={"lecture_complete": True, "recoupements": {"numero": True, "nom": True}, "nom_sec": "MICROSOFT CORP",
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
    ]

# Les sources branchées dans le vrai robot répondent « rien de neuf » ; le faux lecteur fournit les infos TEST.
from radar.collecteurs import COLLECTEURS  # noqa: E402
lecteurs = {sid: (lambda ctx: []) for sid in COLLECTEURS}
lecteurs["sec_form4"] = faux
print(executer(sys.argv[1], collecteurs=lecteurs, maintenant=datetime.now(timezone.utc).replace(microsecond=0)))
