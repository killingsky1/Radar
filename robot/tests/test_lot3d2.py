"""Lot 3d, livraison 2, sur de VRAIES données officielles lues le 3 octobre 2026 (tests/fixtures/lot3d2) :
USAspending (124 contrats de 100 M$ et plus signés depuis 150 jours, 8 fiches) et documents de 8-K (participations
du gouvernement américain : 4 vrais cas, 2 anciennes fausses alertes)."""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from radar.collecteurs import participations as pa
from radar.collecteurs import usaspending as us
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import Contexte
from radar.score import SANS_POINTS, evaluer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "lot3d2"
PAGES = json.loads((F / "pages.json").read_text(encoding="utf-8"))
SEC = Path(__file__).parent / "fixtures" / "sec" / "company_tickers_exchange_complet.json.gz"
MAINTENANT = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


def lu(nom):
    return gzip.decompress((F / nom).read_bytes())


class FauxInternet:
    def __init__(self, pages_api=None):
        self.appels = []
        self.pages_api = pages_api  # remplace les réponses de la recherche (ex. vide)

    def _rep(self, c):
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()

    def get(self, url, entetes=None):
        self.appels.append(("GET", url))
        if url == "https://www.sec.gov/files/company_tickers_exchange.json":
            return self._rep(gzip.decompress(SEC.read_bytes()))
        if url in PAGES:
            return self._rep(lu(PAGES[url]))
        raise ErreurSource(f"{url} : HTTP 404")

    def post(self, url, donnees, entetes=None):
        corps = json.loads(donnees)
        self.appels.append(("POST", url, corps["page"]))
        assert entetes == {"Content-Type": "application/json"} and corps["filters"]["time_period"][0]["date_type"] == \
            "new_awards_only"
        if self.pages_api is not None:
            return self._rep(self.pages_api)
        return self._rep(lu(PAGES[f"POST {url} page={corps['page']}"]))


def contexte(tmp_path, internet=None, quand=MAINTENANT):
    return Contexte(client=internet or FauxInternet(), maintenant=quand, donnees=tmp_path)


# ---------- USAspending ----------

def test_usaspending_1re_lecture_silencieuse_puis_les_contrats_qui_apparaissent(tmp_path):
    internet = FauxInternet()
    assert us.collecter(contexte(tmp_path, internet)) == []
    assert [a[2] for a in internet.appels if a[0] == "POST"] == [1, 2]  # les 2 pages, rien d'autre
    etat = json.loads(us.chemin_etat(tmp_path).read_text())
    assert len(etat["vus"]) == 124 and etat["depuis"] == "2026-10-03"
    # Comme si 4 contrats (fiches officielles en fichier) n'étaient pas encore publiés hier
    nouveaux = {"CONT_AWD_70B01C26F00000405_7014_70B01C26D00000012_7014": "Fisher",
                "CONT_AWD_36C24026K1010_3600_36W79720D0001_3600": "McKesson",
                "CONT_AWD_N0001926F0301_9700_N0001924G0010_9700": "Lockheed",
                "CONT_AWD_36C10G26K0278_3600_36C79119D0006_3600": "Optum"}
    for i in nouveaux:
        del etat["vus"][i]
    us.chemin_etat(tmp_path).write_text(json.dumps(etat))
    evs = {e.official_id: valider(e, MAINTENANT.date()) for e in us.collecter(contexte(tmp_path))}
    assert set(evs) == set(nouveaux)
    for e in evs.values():
        assert e.badge == "officiel", e.checks
        assert e.published_on == "2026-10-03" and e.official_url == us.FICHE + e.official_id
    fisher = evs["CONT_AWD_70B01C26F00000405_7014_70B01C26D00000012_7014"]
    assert fisher.title == "Contrat fédéral américain de 2,59 G$ : FISHER SAND & GRAVEL CO (Sécurité intérieure)"
    assert (fisher.category, fisher.tickers, fisher.occurred_on) == ("gouvernement", [], "2026-06-02")
    lockheed = evs["CONT_AWD_N0001926F0301_9700_N0001924G0010_9700"]
    assert lockheed.title == "Contrat fédéral américain de 991,1 M$ : LOCKHEED MARTIN CORPORATION (Défense)"
    assert (lockheed.category, lockheed.tickers) == ("militaire", ["LMT"])
    assert any("90 jours" in n for n in lockheed.notes)
    assert evs["CONT_AWD_36C24026K1010_3600_36W79720D0001_3600"].tickers == ["MCK"]
    optum = evs["CONT_AWD_36C10G26K0278_3600_36C79119D0006_3600"]
    assert optum.tickers == ["UNH"]  # par la société mère déclarée : UNITEDHEALTH GROUP INCORPORATED
    assert dict(optum.data["details"])["Société mère déclarée"] == "UNITEDHEALTH GROUP INCORPORATED"
    assert [(a.regle, a.pourquoi) for a in evaluer(lockheed.to_dict())] == [(None, SANS_POINTS["usaspending"])]
    assert json.loads(us.chemin_etat(tmp_path).read_text())["vus"].keys() >= set(nouveaux)


def test_usaspending_montants_et_plafond():
    assert [us.argent(v) for v in (2_594_040_000, 991_127_074, 1_200_153_022.86, 100_000_000)] == \
        ["2,59 G$", "991,1 M$", "1,2 G$", "100 M$"]
    x = json.loads(lu("us_page_1.gz"))["results"][0]
    fiche = json.loads(lu("us_fiche_0.gz"))
    e = us.evenement(x, fiche, "2026-10-03")
    assert "Plafond (toutes options)" not in dict(e.data["details"])  # plafond = sommes engagées : pas répété
    e = us.evenement(x, dict(fiche, base_and_all_options=3_000_000_000.0), "2026-10-03")
    assert dict(e.data["details"])["Plafond (toutes options)"] == "3 G$"


def test_usaspending_reponse_vide_met_la_source_en_panne(tmp_path):
    vide = json.dumps({"results": [], "page_metadata": {"page": 1, "hasNext": False}}).encode()
    with pytest.raises(RuntimeError, match="aucun contrat"):
        us.collecter(contexte(tmp_path, FauxInternet(pages_api=vide)))


# ---------- Participations du gouvernement : la détection sur de vrais documents ----------

@pytest.mark.parametrize("doc, attendu", [
    ("pos_intel.gz", "entered into a Warrant and Common Stock Agreement"),
    ("pos_dwave.gz", "covering the resale by the United States Department of Commerce of an aggregate of 7,095,721 shares"),
    ("pos_trilogy.gz", "the DOW will purchase from Trilogy 8,215,570 units"),
    ("pos_dow_2026.gz", "$450 million redeemable preferred stock investment from the Department of War"),
])
def test_participations_vrais_cas_trouves(doc, attendu):
    trouves = pa.passages(pa.texte_doc(lu(doc)))
    assert trouves and attendu in trouves[0]["extrait"], [t["extrait"][:200] for t in trouves]


@pytest.mark.parametrize("doc", ["neg_fiducie_spac.gz", "neg_gaap.gz"])
def test_participations_anciennes_fausses_alertes_ecartees(doc):
    """« U.S. government treasury obligations » (placement d'un fonds en fiducie) et l'abréviation « GAAP » définie après
    « United States of America » (formule comptable) : ce ne sont pas des participations."""
    assert pa.passages(pa.texte_doc(lu(doc))) == []


def test_participations_abreviations_seulement_celles_du_gouvernement():
    texte = ("in accordance with accounting principles generally accepted in the United States of America (“GAAP”). "
             "The U.S. Department of Energy (“DOE”) approved the loan. The Company issued to DOE warrants to purchase "
             "shares of common stock.")
    trouves = pa.passages(texte)
    assert len(trouves) == 1 and "issued to DOE warrants" in trouves[0]["extrait"]


def test_participations_points_lus_dans_l_entete():
    entete = ("ITEM INFORMATION:\t\tEntry into a Material Definitive Agreement\n"
              "ITEM INFORMATION:\t\tUnregistered Sales of Equity Securities\n"
              "ITEM INFORMATION:\t\tRegulation FD Disclosure\nITEM INFORMATION:\t\tOther Events\n"
              "ITEM INFORMATION:\t\tFinancial Statements and Exhibits\n")
    assert [p["item"] for p in pa.points(entete)] == ["1.01", "3.02", "8.01"]


# ---------- Participations : un dépôt lu de bout en bout (vraies pages : en-tête, index, documents) ----------

def depot(acc, cik, nom, jour):
    from radar.collecteurs.sec import DepotSec
    return DepotSec(acc, "8-K", jour, f"edgar/data/{cik}/{acc}.txt", [(str(cik), nom)])


def test_participations_intel_et_d_wave_de_bout_en_bout(tmp_path):
    ctx = contexte(tmp_path)
    intel = pa.lire_un(ctx, depot("0000050863-25-000129", 50863, "INTEL CORP", "2025-08-25"))
    assert len(intel) == 1
    e = valider(intel[0], datetime(2025, 8, 26).date())
    assert e.badge == "officiel", e.checks
    assert e.title == ("INTEL CORP : un 8-K dit que le gouvernement américain (ministère du Commerce) reçoit, détient ou "
                       "revend des titres de la compagnie")
    assert (e.tickers, e.official_id, e.published_on) == (["INTC"], "0000050863-25-000129", "2025-08-25")
    assert e.official_url == "https://www.sec.gov/Archives/edgar/data/50863/000005086325000129/0000050863-25-000129-index.htm"
    assert e.data["points"] == ["1.01", "3.02", "8.01"]
    assert [d["type"] for d in e.data["documents"]] == ["8-K", "EX-99.1"]  # le document principal et le communiqué
    assert any("U.S. Government to make $8.9 billion investment in Intel common stock" in x
               for d in e.data["documents"] for x in d["extraits"])
    assert [(a.regle, a.pourquoi) for a in evaluer(e.to_dict())] == [(None, SANS_POINTS["participation_gouv"])]
    dwave = pa.lire_un(ctx, depot("0001907982-26-000146", 1907982, "D-Wave Quantum Inc.", "2026-09-10"))
    assert len(dwave) == 1 and dwave[0].data["points"] == ["8.01"] and dwave[0].tickers == ["QBTS"]
    assert "resale by the United States Department of Commerce" in dwave[0].data["documents"][0]["extraits"][0]


def test_participations_l_en_tete_deja_lu_par_le_lecteur_des_8k_n_est_pas_relu(tmp_path):
    internet = FauxInternet()
    ctx = contexte(tmp_path, internet)
    url = "https://www.sec.gov/Archives/edgar/data/1907982/000190798226000146/0001907982-26-000146-index-headers.html"
    ctx.cache["entetes_8k"] = {"0001907982-26-000146": lu(PAGES[url]).decode()}
    assert len(pa.lire_un(ctx, depot("0001907982-26-000146", 1907982, "D-Wave Quantum Inc.", "2026-09-10"))) == 1
    assert ("GET", url) not in internet.appels


def test_participations_compagnie_non_cotee_ignoree(tmp_path):
    """HPS Real Assets Lending (points 3.02 et 8.01) n'est pas cotée : rien, comme le lecteur des 8-K."""
    internet = FauxInternet()
    assert pa.lire_un(contexte(tmp_path, internet), depot("0001193125-26-412040", 2089975, "HPS Real Assets Lending Co LP",
                                                         "2026-10-02")) == []
    assert not any("d177455" in a[1] for a in internet.appels)  # ses documents ne sont même pas lus
