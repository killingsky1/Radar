"""Lot H : rachats d'actions, sur de VRAIES données officielles lues le 4 octobre 2026 (tests/fixtures/lotH) :
5 vrais 8-K du 1er octobre 2026 (en-tête, index et documents tels que la SEC les sert) et un extrait du vrai fichier
« frames » de l'API XBRL de la SEC (PaymentsForRepurchaseOfCommonStock, CY2025)."""

import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from radar import argent
from radar.collecteurs import rachats as ra
from radar.collecteurs.participations import texte_doc
from radar.collecteurs.sec import DepotSec
from radar.models import empreinte
from radar.run import Contexte
from radar.score import SANS_POINTS, evaluer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "lotH"
PAGES = json.loads((F / "pages.json").read_text(encoding="utf-8"))
# Vérification de nouveauté : vraies fiches officielles (data.sec.gov/submissions, réduites aux 200 derniers dépôts) et
# vrais 8-K des 90 jours avant, de 4 compagnies (Accenture, National Bank Holdings, American Outdoor Brands, Coursera)
F2 = Path(__file__).parent / "fixtures" / "lotH2"
PAGES2 = json.loads((F2 / "pages.json").read_text(encoding="utf-8"))
SEC = Path(__file__).parent / "fixtures" / "sec" / "company_tickers_exchange_complet.json.gz"
FRAMES = json.loads((F / "frames_CY2025_extrait.json").read_text(encoding="utf-8"))
MAINTENANT = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
J = date(2026, 10, 1)


def lu(nom):
    return gzip.decompress((F / nom).read_bytes())


class FauxInternet:
    def __init__(self, pages=None):
        self.appels = []
        self.pages = pages or {}

    def get(self, url, entetes=None):
        self.appels.append(url)
        if url in self.pages:
            c = self.pages[url]
        elif url == "https://www.sec.gov/files/company_tickers_exchange.json":
            c = gzip.decompress(SEC.read_bytes())
        elif url.startswith("https://data.sec.gov/api/xbrl/frames/"):
            c = json.dumps(FRAMES).encode()
        elif url in PAGES2:
            c = gzip.decompress((F2 / PAGES2[url]).read_bytes())
        else:
            c = lu(PAGES[url])
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def contexte(tmp_path, internet=None):
    return Contexte(client=internet or FauxInternet(), maintenant=MAINTENANT, donnees=tmp_path)


def depot(acc, cik, nom, jour="2026-10-01"):
    return DepotSec(acc, "8-K", jour, f"edgar/data/{cik}/{acc}.txt", [(str(cik), nom)])


ACN = ("0001467373-26-000037", 1467373, "Accenture plc")
NBHC = ("0001104659-26-112856", 1475841, "National Bank Holdings Corp")
AOUT = ("0001808997-26-000052", 1808997, "American Outdoor Brands, Inc.")
NWS = ("0001564708-26-000213", 1564708, "NEWS CORP")
AVAX = ("0001493152-26-045263", 1826397, "AVAX ONE TECHNOLOGY LTD.")


# ---------- Les 5 vrais 8-K du 1er octobre 2026, lus de bout en bout ----------

def test_accenture_hausse_de_6_milliards_dans_le_communique(tmp_path):
    evs = ra.lire_un(contexte(tmp_path), depot(*ACN))
    assert len(evs) == 1
    e = valider(evs[0], J)
    assert e.badge == "officiel", e.checks
    assert e.title == "Accenture plc : programme de rachat d'actions augmenté de 6 G$"
    assert (e.tickers, e.amount_min, e.amount_max, e.kind, e.category) == (["ACN"], 6e9, 6e9, "rachat_annonce", "compagnies")
    assert (e.occurred_on, e.published_on) == ("2026-10-01", "2026-10-01")  # « September 2026 » sans jour : date du dépôt
    assert e.official_url == "https://www.sec.gov/Archives/edgar/data/1467373/000146737326000037/0001467373-26-000037-index.htm"
    assert [d["type"] for d in e.data["documents"]] == ["EX-99"]
    assert e.data["documents"][0]["extraits"] == [
        "•Accenture’s total outstanding authority is approximately $6.9 billion, which includes $6.0 billion in additional "
        "share repurchase authority approved by the company’s Board of Directors in September 2026."]
    assert e.data["points"] == ["2.02"] and e.data["sorte"] == "hausse"
    assert e.data["nouveaute"] == {"jours": 90, "depots_relus": ["0001193125-26-300813"]}  # 8-K du 10 juillet relu
    assert e.checks["pas_deja_annonce"] is True
    assert [(a.regle, a.pourquoi) for a in evaluer(e.to_dict())] == [(None, SANS_POINTS["rachat_annonce"])]


def test_national_bank_hausse_de_40_1_millions_datee_du_jour_de_l_autorisation(tmp_path):
    """L'en-tête dit « période du 28 septembre » (la dépréciation, point 2.06, du même 8-K) : la date de l'autorisation
    vient de la phrase (30 septembre)."""
    e = valider(ra.lire_un(contexte(tmp_path), depot(*NBHC))[0], J)
    assert e.badge == "officiel", e.checks
    assert e.title == "National Bank Holdings Corp : programme de rachat d'actions augmenté de 40,1 M$"
    assert (e.occurred_on, e.amount_min, e.data["points"]) == ("2026-09-30", 40.1e6, ["8.01"])
    assert e.data["nouveaute"]["depots_relus"] == ["0001104659-26-090375", "0001104659-26-087128", "0001104659-26-085408"]
    assert e.data["documents"][0]["extraits"] == [
        "On September 30, 2026, the Board of Directors of the Company approved an additional authorization to repurchase "
        "up to $40.1 million of the Company's Class A common stock."]  # « Item 8.01.Other Events » n'est pas collé devant


def test_american_outdoor_nouveau_programme_de_10_millions_dans_le_8k_et_le_communique(tmp_path):
    e = valider(ra.lire_un(contexte(tmp_path), depot(*AOUT))[0], J)
    assert e.badge == "officiel", e.checks
    assert e.title == "American Outdoor Brands, Inc. : nouveau programme de rachat d'actions, jusqu'à 10 M$"
    assert [d["type"] for d in e.data["documents"]] == ["8-K", "EX-99"]  # « $10.0 million » et « $10 million » : même montant
    communique = e.data["documents"][1]["extraits"][0]
    assert communique.startswith("American Outdoor Brands, Inc. (NASDAQ Global Select: AOUT)")  # pas l'en-tête du communiqué
    assert "has approved the repurchase of up to $10 million" in communique
    assert e.occurred_on == "2026-10-01"
    # Chaque extrait est mot pour mot dans le document officiel
    for d in e.data["documents"]:
        texte = texte_doc(lu(PAGES[d["url"]]))
        assert all(x in texte for x in d["extraits"])


@pytest.mark.parametrize("cas", [NWS, AVAX])
def test_anciens_programmes_decrits_de_nouveau_ecartes(tmp_path, cas):
    """News Corp : « As previously reported… », « 2025 Repurchase Program » ; AVAX ONE : « previously authorized $40
    million share repurchase program » : rien de nouveau, rien de publié."""
    assert ra.lire_un(contexte(tmp_path), depot(*cas)) == []


# ---------- La règle stricte, phrase par phrase ----------

@pytest.mark.parametrize("phrase, attendu", [
    ("On September 29, 2026, the Board of Directors approved a new $5 billion share repurchase program.",
     ("nouveau", 5e9, None)),
    ("Today the Board approved a new share repurchase program under which the Company may repurchase up to $500 million of "
     "its common stock, which replaces the prior program approved on March 3, 2025.", ("nouveau", 5e8, None)),
    ("The Company's board of directors has authorized a $1 billion increase to its existing share repurchase program.",
     ("hausse", 1e9, None)),
    ("On September 30, the Company's Board of Directors increased its share repurchase authorization by $2.0 billion.",
     ("hausse", 2e9, None)),
    ("On Sept. 28, 2026, the Board of Directors approved a stock repurchase program of up to 5,000,000 shares of the "
     "Company's common stock.", ("nouveau", None, 5e6)),
    ("XYZ Corp. (NYSE: XYZ) today announced that its Board of Directors authorized the repurchase of up to $250,000,000 "
     "of its common stock.", ("nouveau", 2.5e8, None)),
])
def test_regle_stricte_annonces_retenues(phrase, attendu):
    a = ra.analyser(phrase, J)
    assert (a.get("sorte"), a.get("dollars"), a.get("actions")) == attendu, a


@pytest.mark.parametrize("phrase, raison", [
    ("As previously reported, under News Corporation's stock repurchase program, the Company is authorized to acquire "
     "from time to time up to $1 billion in the aggregate.", "aucune formule"),
    ("In March 2025, our Board of Directors approved a share repurchase program of up to $500 million.", "ancienne date"),
    ("The Board of Directors authorized the repurchase of up to $50 million of the Company's 5.25% Senior Notes due 2030.",
     "autre titre"),
    ("The Board authorized the repurchase of up to $25 million of the Company's outstanding warrants.", "autre titre"),
    ("As of September 30, 2026, the Board had authorized the repurchase of up to $300 million.", "ancien programme"),
    ("The program follows the Company’s prior share repurchase program, which authorized the Company to repurchase up to "
     "$10.0 million of its common stock, was initiated in 2025 and, as of September 30, 2026, resulted in 236,907 shares.",
     "conseil"),
    ("The Board of Directors approved a share repurchase program, and declared a quarterly dividend of $0.25 per share.",
     "aucune formule"),
    ("During the quarter, the Company repurchased 1.2 million shares for $45 million under its share repurchase program.",
     "aucune formule"),
    # Aucun signe d'annonce récente : souvent un programme déjà connu (diapo, avertissement légal, note de bas de page)
    ("• $150M share repurchase program authorized by Board through December 2026", "aucune formule"),
    ("The Board of Directors approved a new $5 billion share repurchase program.", "pas de signe d'une annonce récente"),
    ("5. Share Repurchase Program was the program which the Board of Directors authorized the repurchase of up to $12.0 "
     "million of the Exzeo's common stock.", "ancien programme"),
    ("In June 2026, the Company's Board of Directors approved a share repurchase program pursuant to which the Company is "
     "authorized to repurchase up to an aggregate of $100.0 million.", "ancienne date"),
    ("On September 30, 2026, the Board approved a new $50 million share repurchase program, as previously announced.",
     "ancien programme"),
])
def test_regle_stricte_phrases_ecartees(phrase, raison):
    a = ra.analyser(phrase, J)
    assert "sorte" not in a and raison in a["rejet"], a


def test_phrases_sans_coupure_apres_une_abreviation_et_lignes_de_date_coupees():
    assert ra.phrases("The Board of ABC Inc. approved it. The U.S. Department of Commerce agreed. Next one") == [
        "The Board of ABC Inc. approved it.", "The U.S. Department of Commerce agreed.", "Next one"]
    assert ra.phrases("NEW YORK, Oct. 1, 2026 /PRNewswire/ -- XYZ Corp. (NYSE: XYZ) today announced a plan. "
                      "SAN JOSE, Calif.--(BUSINESS WIRE)--Acme Inc. today said so. • Point un • Point deux") == [
        "NEW YORK, Oct. 1, 2026 /PRNewswire/ --", "XYZ Corp. (NYSE: XYZ) today announced a plan.",
        "SAN JOSE, Calif.--(BUSINESS WIRE)--", "Acme Inc. today said so.", "• Point un", "• Point deux"]
    assert ra.phrases("Item 8.01.Other Events On September 30, 2026, the Board approved it.") == [
        "Item 8.01.Other Events", "On September 30, 2026, the Board approved it."]


# ---------- Un dépôt : même montant partout, 10 M$ et plus, compagnie cotée, points du 8-K ----------

def faux_8k(phrases_doc, items=("Other Events",), cik=1808997, acc="0001808997-26-000999"):
    dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    entete = "<SEC-HEADER>\n" + "".join(f"ITEM INFORMATION:\t\t{i}\n" for i in items) + (
        f"COMPANY CONFORMED NAME:\t\t\tTEST\nCENTRAL INDEX KEY:\t\t\t{cik:010d}\n</SEC-HEADER>")
    index = f'<table><tr><td>1</td><td><a href="/Archives/edgar/data/{cik}/{acc.replace("-", "")}/ex99.htm">x</a></td>' \
            f'<td>EX-99.1</td><td>1</td></tr></table>'
    return {f"{dossier}/{acc}-index-headers.html": entete.encode(), f"{dossier}/{acc}-index.htm": index.encode(),
            f"{dossier}/ex99.htm": ("<p>" + " ".join(phrases_doc) + "</p>").encode()}, depot(acc, cik, "TEST")


def test_deux_montants_differents_dans_le_meme_depot_rien(tmp_path):
    pages, d = faux_8k(["On October 1, 2026, the Board of Directors approved a new $50 million share repurchase program.",
                        "On October 1, 2026, the Board of Directors approved a new $75 million share repurchase program."])
    documents, cle = ra.retenir([(None, "EX-99.1", texte_doc(pages[next(u for u in pages if u.endswith("ex99.htm"))]))], J)
    assert cle is None and len(documents) == 1 and len(documents[0][2]) == 2  # 2 phrases retenues, 2 montants : rien
    assert ra.lire_un(contexte(tmp_path, FauxInternet(pages)), d) == []


def test_sous_10_millions_rien_mais_un_nombre_d_actions_va_au_fil_sans_montant(tmp_path):
    pages, d = faux_8k(["On October 1, 2026, the Board of Directors approved a new $5 million share repurchase program."])
    assert ra.retenir([(None, "EX-99.1", "On October 1, 2026, the Board of Directors approved a new $5 million share "
                                         "repurchase program.")], J)[1] is None
    assert ra.lire_un(contexte(tmp_path, FauxInternet(pages)), d) == []
    pages, d = faux_8k(["On October 1, 2026, the Board of Directors approved a stock repurchase program of up to "
                        "2,000,000 shares of the Company's common stock."])
    e = valider(ra.lire_un(contexte(tmp_path, FauxInternet(pages)), d)[0], J)
    assert e.badge == "officiel", e.checks
    assert (e.amount_min, e.data["actions"]) == (None, 2e6)
    assert e.title.endswith("nouveau programme de rachat d'actions, jusqu'à 2 000 000 actions")
    assert argent.ligne(e.to_dict()) is None  # pas de montant : pas dans l'onglet Argent


def test_sans_point_2_02_7_01_ou_8_01_les_documents_ne_sont_pas_lus(tmp_path):
    pages, d = faux_8k(["On October 1, 2026, the Board of Directors approved a new $50 million share repurchase program."],
                       items=("Entry into a Material Definitive Agreement",))
    internet = FauxInternet(pages)
    assert ra.lire_un(contexte(tmp_path, internet), d) == []
    assert not any(u.endswith("-index.htm") or u.endswith("ex99.htm") for u in internet.appels)


def test_compagnie_non_cotee_ignoree_sans_lire_ses_documents(tmp_path):
    pages, d = faux_8k(["On October 1, 2026, the Board of Directors approved a new $50 million share repurchase "
                        "program."], cik=999999999,
                       acc="0000999999-26-000001")
    internet = FauxInternet(pages)
    assert ra.lire_un(contexte(tmp_path, internet), d) == []
    assert not any(u.endswith("ex99.htm") for u in internet.appels)


def test_documents_deja_lus_par_les_participations_pas_relus(tmp_path):
    from radar.collecteurs import participations as pa
    internet = FauxInternet()
    ctx = contexte(tmp_path, internet)
    assert pa.lire_un(ctx, depot(*NBHC)) == []  # point 8.01 : les participations lisent le 8-K (rien pour elles)
    avant = list(internet.appels)
    assert len(ra.lire_un(ctx, depot(*NBHC))) == 1
    nouveaux = internet.appels[len(avant):]
    assert not set(nouveaux) & set(avant)  # ni en-tête, ni index, ni document relu
    assert nouveaux[0] == "https://data.sec.gov/submissions/CIK0001475841.json"  # seulement la vérification de nouveauté
    assert all("112856" not in u for u in nouveaux)


def test_controle_rate_si_l_extrait_ne_dit_plus_la_meme_chose(tmp_path):
    e = ra.lire_un(contexte(tmp_path), depot(*NBHC))[0]
    e.data["dollars"] = 41e6
    v = valider(e, J)
    assert v.badge == "a_verifier" and v.checks["meme_montant_partout"] is False


# ---------- Onglet Argent ----------

def test_argent_famille_rachats_neutre_avec_le_plafond(tmp_path):
    e = valider(ra.lire_un(contexte(tmp_path), depot(*ACN))[0], J).to_dict()
    l = argent.ligne(e)
    assert (l["famille"], l["sens"], l["montant"], l["role"], l["compagnie"], l["symbole"]) == (
        "rachats", 0, 6e9, "hausse", "Accenture plc", "ACN")
    a, infos = argent.preparer([e], J)
    assert [x["famille"] for x in a["lignes"]] == ["rachats"] and e["id"] in infos
    assert a["thermometre"]["achats"]["nombre"] == 0  # un rachat n'est pas un achat de dirigeant
    assert "rachats d'actions annoncés de 10 M$ et plus (un plafond autorisé, pas un achat fait)" in a["seuils"]


# ---------- Rachats faits : XBRL (API officielle de la SEC) ----------

def test_annee_du_fichier_xbrl():
    assert ra.annee_xbrl(date(2026, 10, 4)) == 2025
    assert ra.annee_xbrl(date(2027, 3, 31)) == 2025  # avant avril : les rapports annuels de 2026 ne sont pas tous là
    assert ra.annee_xbrl(date(2027, 4, 1)) == 2026


def test_xbrl_lu_garde_et_pas_reecrit_s_il_ne_change_pas(tmp_path):
    internet = FauxInternet()
    assert ra.collecter_xbrl(contexte(tmp_path, internet)) == []
    assert internet.appels == [ra.FRAMES.format(annee=2025)]
    x = json.loads(ra.chemin_xbrl(tmp_path).read_text())
    assert x["cadre"] == "CY2025" and x["par_cik"]["320193"] == [90711000000, "2024-09-29", "2025-09-27",
                                                                  "0000320193-25-000079"]
    ra.chemin_xbrl(tmp_path).write_text(ra.chemin_xbrl(tmp_path).read_text() + " ")  # marque
    ra.collecter_xbrl(contexte(tmp_path))
    assert ra.chemin_xbrl(tmp_path).read_text().endswith("\n ")  # même contenu : fichier pas réécrit


def test_xbrl_format_inattendu_met_la_source_en_panne(tmp_path):
    autre = dict(FRAMES, tag="PaymentsForRepurchaseOfEquity")
    internet = FauxInternet({ra.FRAMES.format(annee=2025): json.dumps(autre).encode()})
    with pytest.raises(RuntimeError, match="réponse inattendue"):
        ra.collecter_xbrl(contexte(tmp_path, internet))


def test_xbrl_pour_l_app_compagnies_des_listes_seulement(tmp_path):
    ra.collecter_xbrl(contexte(tmp_path))
    (tmp_path / "sec" / "emetteurs.json").write_text(json.dumps({
        "AAPL": {"cik": 320193, "type": "compagnie"}, "SAH": {"cik": 1043509, "type": "compagnie"},
        "CECO": {"cik": 3197, "type": "compagnie"}, "ZZZZ": {"cik": 42, "type": "compagnie"}}))
    app = ra.pour_app(tmp_path, ["AAPL", "SAH", "CECO", "ZZZZ", "NOPE"])
    assert app["cadre"] == "CY2025" and app["etiquette"] == "PaymentsForRepurchaseOfCommonStock"
    assert app["par_symbole"]["AAPL"] == {
        "cik": 320193, "montant": 90711000000, "debut": "2024-09-29", "fin": "2025-09-27", "accn": "0000320193-25-000079",
        "lien": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/0000320193-25-000079-index.htm"}
    assert app["par_symbole"]["SAH"]["illisible"] is True and "montant" not in app["par_symbole"]["SAH"]  # −82,4 M$
    assert app["par_symbole"]["CECO"]["montant"] == 0  # aucun rachat déclaré : montré comme tel
    assert app["par_symbole"]["ZZZZ"] == {"cik": 42} and app["par_symbole"]["NOPE"] == {"cik": None}
    assert set(app["par_symbole"]) == {"AAPL", "SAH", "CECO", "ZZZZ", "NOPE"}


# ---------- La mesure du labo : vrais textes de 12 dépôts (21 sept. au 2 oct. 2026), revus à la main ----------

MESURE = json.loads(gzip.decompress((F / "textes_mesure.json.gz").read_bytes()))


def decider(acc):
    x = MESURE[acc]
    return ra.retenir([(None, t, texte) for t, texte in x["docs"].items()], date.fromisoformat(x["jour"]))


@pytest.mark.parametrize("acc, attendu", [
    ("0001622536-26-000074", ("hausse", 1.5e9, None)),  # Talen : « approved the upsizing … by $1.5 billion »
    ("0000842162-26-000080", ("total", 1.5e9, None)),  # Lear : « approved an increase … authorization to $1.5 billion »
    ("0000096223-26-000028", ("total", 2.5e8, None)),  # Jefferies : « increased … authorization back to $250 million »
    ("0001628280-26-063850", ("hausse", 1e9, None)),  # MongoDB : « authorized an additional $1.0 billion »
    ("0001423869-26-000031", ("nouveau", None, 7e5)),  # PCB Bancorp : 700 000 actions, dans le 8-K et le communiqué
    ("0001193125-26-408295", ("nouveau", None, 464769.0)),  # Winchester Bancorp
])
def test_mesure_vraies_annonces_trouvees(acc, attendu):
    documents, cle = decider(acc)
    assert cle == attendu, [(s, [p[:120] for p, _ in ts]) for _, s, ts in documents]


def test_mesure_le_total_ne_contredit_pas_la_hausse_et_les_deux_documents_de_lear():
    documents, _ = decider("0000842162-26-000080")
    assert [s for _, s, _ in documents] == ["8-K", "EX-99.1"]
    assert documents[0][2][0][0].startswith("On September 24, 2026, Lear Corporation")  # pas l'en-tête du formulaire
    documents, _ = decider("0001622536-26-000074")
    assert [s for _, s, _ in documents] == ["8-K"]


@pytest.mark.parametrize("acc", [
    "0001294133-26-000037",  # Inogen : hausse de 15 M$ « Subject to the closing of the transaction » (conditionnelle)
    "0001193125-26-409792",  # Ovintiv : approbation de la Bourse de Toronto, pas une formule du conseil
    "0001628280-26-063643",  # SSR Mining : autorisations du 13 février et du 15 juin 2026 (plus de 60 jours)
    "0001628280-26-063618",  # KeyCorp : « May 2026: Board authorized up to $3Bn » (présentation, ancien)
    "0001628280-26-063657",  # MongoDB, la veille : changement de PDG, pas de rachat
    "0001193125-26-402928",  # Vylor : les anciens programmes de Corteva (2021, 2022, 2024)
])
def test_mesure_rien_a_publier(acc):
    assert decider(acc)[1] is None


def test_plafond_total_titre_et_onglet_argent(tmp_path):
    pages, d = faux_8k(["On October 1, 2026, the Board of Directors approved an increase to the Company's share "
                        "repurchase authorization to $1.5 billion."])
    e = valider(ra.lire_un(contexte(tmp_path, FauxInternet(pages)), d)[0], J)
    assert e.badge == "officiel", e.checks
    assert e.title == "American Outdoor Brands, Inc. : programme de rachat d'actions porté à 1,5 G$ au total"  # nom : liste de la SEC
    assert dict(e.data["details"])["Nouveau plafond total"] == "1,5 G$"
    l = argent.ligne(e.to_dict())
    assert (l["famille"], l["role"], l["montant"]) == ("rachats", "total", 1.5e9)


def test_la_meme_annonce_dans_deux_8k_de_la_compagnie_une_seule_fois(tmp_path):
    phrase = ["On October 1, 2026, the Board of Directors approved a new $50 million share repurchase program."]
    pages1, d1 = faux_8k(phrase, acc="0001808997-26-000901")
    pages2, d2 = faux_8k(phrase, acc="0001808997-26-000902")
    ctx = contexte(tmp_path, FauxInternet({**pages1, **pages2}))
    assert len(ra.lire_un(ctx, d1)) == 1 and ra.lire_un(ctx, d2) == []  # même passage
    from radar.store import Depot
    Depot(tmp_path).enregistrer([valider(ra.lire_un(contexte(tmp_path, FauxInternet(pages1)), d1)[0], J)])
    assert ra.lire_un(contexte(tmp_path, FauxInternet(pages2)), d2) == []  # passage suivant (déjà publiée)
    assert len(ra.lire_un(contexte(tmp_path, FauxInternet(pages1)), d1)) == 1  # le même dépôt relu : pas écarté


# ---------- Mesure TÉMOIN du labo (3 au 7 août 2026, jours jamais regardés avant la règle v2) : 27 vrais dépôts ----------

TEMOIN = json.loads(gzip.decompress((F / "textes_temoin.json.gz").read_bytes()))  # phrases qui parlent de rachat


@pytest.mark.parametrize("acc, attendu", [
    ("0001104659-26-091377", ("hausse", 15e6, None)),  # ATN : « authorization increase of $15 million » (pas « nouveau »)
    ("0001628280-26-052541", ("hausse", 1e8, None)),  # BlackLine : « increase … (the “Stock Buyback Program”) of an additional »
    ("0001193125-26-335025", ("hausse", 5e8, None)),  # CoreCivic : « … may purchase up to an additional $500.0 million »
    ("0000785161-26-000183", ("total", 1e9, None)),  # Encompass Health : « increase in the aggregate … authorization to $1 billion »
    ("0001559865-26-000043", ("total", 1.5e8, None)),  # Evertec : « increase to Evertec's existing … up to an aggregate of »
    ("0001539838-26-000137", ("total", 1.6e10, None)),  # Diamondback : « doubled … authorization to $16.0 billion »
    ("0002089271-26-000020", ("nouveau", 3.5e9, None)),  # Honeywell Aerospace : « accelerated share repurchase agreements » permis
    ("0001538263-26-000101", ("hausse", None, 832000.0)),  # HomeTrust : « the repurchase of up to an additional 832,000 shares »
    ("0001193125-26-335148", ("nouveau", 1e9, None)),  # HubSpot : « … in an aggregate amount of up to $1.0 billion »
    ("0000051253-26-000028", ("nouveau", 2.5e9, None)),  # IFF : « an enhanced $2.5 billion share repurchase program »
    ("0001104659-26-091178", ("hausse", 3e7, None)),  # ISG : la phrase « new … authorization » sans signe récent est écartée
    ("0001193125-26-336057", ("nouveau", 1e8, None)),  # LifeStance : la date du 24 février est celle de l'ANCIEN programme
    ("0001099219-26-000048", ("nouveau", 3e9, None)),  # MetLife : « approved a new $3.0 billion authorization to repurchase »
    ("0001104485-26-000030", ("hausse", 1.5e8, None)),  # NOG : autorisé le 10 juillet, déposé le 6 août (27 jours)
    ("0001193125-26-333913", ("nouveau", 2.5e7, None)),  # SmartRent : « On July 24 » sans année = l'année du dépôt
    ("0001628280-26-053346", ("nouveau", 1.4e10, None)),  # Sandisk : « a $14 billion (exclusive of fees …) share repurchase »
    ("0001193125-26-333122", ("total", 2e8, None)),  # Talos : « recently authorized an increase … back up to $200 million »
])
def test_temoin_vraies_annonces_trouvees(acc, attendu):
    x = TEMOIN[acc]
    documents, cle = ra.retenir([(None, t, v) for t, v in x["docs"].items()], date.fromisoformat(x["jour"]))
    assert cle == attendu, [(s, [p[:120] for p, _ in ts]) for _, s, ts in documents]


@pytest.mark.parametrize("acc", [
    "0001628280-26-053849",  # Collegium : « • $150M share repurchase program authorized by Board through December 2026 » (diapo)
    "0001193125-26-336562",  # GEO : le programme de 500 M$ nommé dans l'avertissement légal (« forward-looking statements »)
    "0001193125-26-338098",  # Exzeo : note de bas de page « Share Repurchase Program was the program which the Board … »
    "0001371285-26-000171",  # Trupanion : le même programme de 100 M$ « In June 2026 » dans le 8-K (plus de 30 jours)
    "0001421461-26-000020",  # Intrepid Potash : « In June 2026, Intrepid's Board approved an expansion … to $50 million »
    "0000749251-26-000243",  # Gartner : « … by $500 million in July 2026 » (le 1er juillet : 34 jours, on ne devine pas le jour)
    "0001628280-26-052608",  # Healthpeak : « In July 2026, … authorized a new $500 million … » (même raison)
    "0000908255-26-000049",  # BorgWarner : vraie hausse, mais aucun signe d'annonce récente dans la phrase (manquée, voulu)
    "0001827090-26-000026",  # Certara : « In the third quarter, the Board approved an additional $50 million » (même raison)
])
def test_temoin_rien_a_publier(acc):
    x = TEMOIN[acc]
    assert ra.retenir([(None, t, v) for t, v in x["docs"].items()], date.fromisoformat(x["jour"]))[1] is None


# ---------- Vérification de nouveauté : les vrais 8-K de Coursera (fiche officielle et dépôts de mai et juin 2026) ----------

def test_coursera_le_29_juillet_decrit_le_programme_de_mai(tmp_path):
    """Le vrai dépôt du 29 juillet (résultats) : « In May, our Board authorized a $500 million share repurchase program,
    and we moved quickly to execute against that authorization… » : écarté par la règle (mois de mai, programme qui sert
    déjà)."""
    assert ra.lire_un(contexte(tmp_path), depot("0001651562-26-000059", 1651562, "Coursera, Inc.", "2026-07-29")) == []


def test_nouveaute_le_meme_montant_deja_annonce_dans_un_8k_precedent(tmp_path):
    """Même si une phrase passait la règle, le vrai 8-K du 18 mai 2026 annonçait déjà ce programme de 500 M$ (« the board
    of directors of Coursera, Inc. … approved a stock repurchase program … up to $500 million ») : rien de publié."""
    phrase = ["On July 28, 2026, the Board of Directors approved a share repurchase program of up to $500 million."]
    pages, d = faux_8k(phrase, cik=1651562, acc="0001651562-26-000099")
    d.depose = "2026-07-29"
    ctx = contexte(tmp_path, FauxInternet(pages))
    assert ra.deja_annoncee(ctx, 1651562, d, ("nouveau", 5e8, None))[0] == "0001651562-26-000041"
    assert ra.lire_un(ctx, d) == []
    # Un autre montant : publié, avec les 3 vrais 8-K relus (23 juin, 18 mai, 11 mai)
    pages, d = faux_8k(["On July 28, 2026, the Board of Directors approved a share repurchase program of up to $600 "
                        "million."], cik=1651562, acc="0001651562-26-000098")
    d.depose = "2026-07-29"
    e = valider(ra.lire_un(contexte(tmp_path, FauxInternet(pages)), d)[0], date(2026, 7, 29))
    assert e.badge == "officiel", e.checks
    assert e.data["nouveaute"]["depots_relus"] == ["0001651562-26-000051", "0001651562-26-000041", "0001140361-26-020399"]


# ---------- 2e mesure TÉMOIN (28 au 31 juillet 2026, jamais regardée avant la version 2) : 22 vrais dépôts ----------

TEMOIN2 = json.loads(gzip.decompress((F / "textes_temoin2.json.gz").read_bytes()))


@pytest.mark.parametrize("acc, attendu", [
    ("0001628280-26-051029", ("hausse", 5e8, None)),  # Monolithic Power : « has authorized an additional $500 million »
    ("0001334036-26-000050", ("hausse", 1.5e9, None)),  # Crocs : 8-K et communiqué disent la même chose
    ("0001628280-26-051046", ("hausse", 2.5e9, None)),  # LPL Financial : « approved a $2.5 billion increase »
    ("0000860731-26-000048", ("nouveau", 1.5e9, None)),  # Tyler : « approved a share repurchase plan … up to $1.5 billion »
    ("0000004127-26-000047", ("nouveau", 2e9, None)),  # Skyworks
    ("0000712537-26-000026", ("hausse", 7.5e7, None)),  # First Commonwealth : « an additional $75.0 million … program »
    ("0001171843-26-005042", ("hausse", 1.5e9, None)),  # WTW : « … share repurchase authority in the amount of $1.5 billion »
    ("0001193125-26-326149", ("hausse", 3.5e8, None)),  # Dolby : « approved increasing the size of its … program by »
    ("0001104659-26-088462", ("total", 4e9, None)),  # ICE : « Board approved increase in share repurchase authorization up to »
    ("0001628280-26-050792", ("hausse", 1.5e8, None)),  # Laureate : « an additional $150 million increase to the existing … »
    ("0000920148-26-000162", ("hausse", 1e9, None)),  # LabCorp : « In July, the Board … approved an increase of $1.0 billion »
    ("0001058090-26-000063", ("nouveau", 1.3e9, None)),  # Chipotle : « … with a total aggregate purchase price of $1.3 billion »
    ("0001410384-26-000051", ("hausse", 3.5e8, None)),  # Q2 : « has authorized up to $350 million of additional repurchases »
    ("0001562528-26-000025", ("total", 5e7, None)),  # Franklin BSP : « reauthorized … making $50.0 million available »
    ("0001193125-26-318759", ("hausse", 8e8, None)),  # Armstrong : « an additional $800 million to be added to … »
])
def test_temoin2_vraies_annonces_trouvees(acc, attendu):
    x = TEMOIN2[acc]
    documents, cle = ra.retenir([(None, t, v) for t, v in x["docs"].items()], date.fromisoformat(x["jour"]))
    assert cle == attendu, [(s, [p[:120] for p, _ in ts]) for _, s, ts in documents]


@pytest.mark.parametrize("acc", [
    "0001651562-26-000059",  # Coursera : « In May, our Board authorized … and we moved quickly to execute against it »
    "0001628280-26-051320",  # Greif : « we asked our stock repurchase committee of the Board to approve … » (pas encore)
    "0001193125-26-328715",  # FTI Consulting : autorisé le 3 juin (plus de 30 jours)
    "0001171843-26-005081",  # Exponent : vraie hausse, sans signe d'annonce récente (manquée, voulu)
    "0000876437-26-000026",  # MGIC : « authorizing us to purchase an additional $750 million » (même raison)
    "0001628280-26-050815",  # Vericel : « •Board of Directors authorized $200 million share repurchase program » (même raison)
])
def test_temoin2_rien_a_publier(acc):
    x = TEMOIN2[acc]
    assert ra.retenir([(None, t, v) for t, v in x["docs"].items()], date.fromisoformat(x["jour"]))[1] is None
