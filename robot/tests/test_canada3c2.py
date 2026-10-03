"""Lot 3c, livraison 2, sur de VRAIES données officielles lues le 3 octobre 2026 (tests/fixtures/canada3c2) :
Santé Canada (avis de conformité), contrats fédéraux (portail du gouvernement ouvert), CCC (rapports PDF)."""

import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from radar.collecteurs import ccc
from radar.collecteurs import contrats_ca as ct
from radar.collecteurs import sante_canada as sc
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import Contexte, executer
from radar.score import SANS_POINTS, evaluer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "canada3c2"
SEC = Path(__file__).parent / "fixtures" / "sec" / "company_tickers_exchange_complet.json.gz"
PAGES = json.loads((F / "pages.json").read_text(encoding="utf-8"))
MAINTENANT = datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc)
JOUR = date(2026, 10, 3)


def lu(url):
    return gzip.decompress((F / PAGES[url]).read_bytes())


class FausseApiContrats:
    """Le moteur de recherche du portail (filtre par trimestre, tri par _id décroissant, pages) sur de VRAIES lignes :
    les 1 000 plus récentes d'avril à juin 2026 et toutes celles de 1 M$ et plus (2 428 lignes, dont 92 de 10 M$ et plus)."""

    def __init__(self):
        self.lignes = json.loads(gzip.decompress((F / "contrats_q1_extrait.json.gz").read_bytes()))
        q2 = json.loads(lu(ct.adresse("2026-2027-Q2", 0)))["result"]["records"]  # la vraie ligne du trimestre 2
        self.lignes += q2

    def repondre(self, url):
        q = parse_qs(urlparse(url).query)
        periode = json.loads(q["filters"][0])["reporting_period"]
        assert q["sort"] == ["_id desc"] and q["fields"] == [ct.CHAMPS]
        choisies = sorted((x for x in self.lignes if x["reporting_period"] == periode), key=lambda x: -x["_id"])
        debut, n = int(q["offset"][0]), int(q["limit"][0])
        return json.dumps({"success": True, "result": {"records": choisies[debut:debut + n],
                                                       "total": len(choisies)}}).encode()


class FauxInternet:
    def __init__(self, remplacements=None, contrats=None):
        self.appels = []
        self.remplacements = remplacements or {}
        self.contrats = contrats or FausseApiContrats()

    def get(self, url):
        self.appels.append(url)
        if url in self.remplacements:
            c = self.remplacements[url]
        elif url == "https://www.sec.gov/files/company_tickers_exchange.json":
            c = gzip.decompress(SEC.read_bytes())
        elif url.startswith(ct.API):
            c = self.contrats.repondre(url)
        elif url in PAGES:
            c = lu(url)
        else:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def contexte(tmp_path, internet=None, quand=MAINTENANT):
    return Contexte(client=internet or FauxInternet(), maintenant=quand, donnees=tmp_path)


# ---------- Santé Canada ----------

def test_sante_canada_seulement_les_nouvelles_substances_des_60_derniers_jours():
    avis = json.loads(lu(sc.LISTE).decode("utf-8-sig"))
    assert len(avis) == 1707  # les avis de 2026 (la vraie liste complète en a 38 068)
    # « Nouvelle substance active (NSA) » et « Priorité-NSA » (38296, examen prioritaire)
    assert sorted(x["noc_number"] for x in sc.nouvelles_substances(avis, "2026-08-04")) == [38047, 38296, 38344, 38346, 38368]


def test_sante_canada_infos_officielles_lien_public_sans_points(tmp_path):
    evs = sc.collecter(contexte(tmp_path))
    assert [e.official_id for e in evs] == ["38047", "38296", "38344", "38346", "38368"]
    d = next(e for e in evs if e.official_id == "38368")
    valider(d, JOUR)
    assert d.badge == "officiel", d.checks
    assert d.title == "Santé Canada : nouveau médicament autorisé, DAWNZERA (donidalorsen sodique), de CELYSTRA PHARMA INC."
    assert d.official_url == "https://health-products.canada.ca/noc-ac/nocInfo?lang=fre&no=38368"
    assert (d.occurred_on, d.published_on) == ("2026-09-28", "2026-09-28")
    assert dict(d.data["details"])["Ingrédient(s)"] == "donidalorsen sodique 80 MG / 0.8ML"
    assert d.tickers == []  # Celystra n'est pas cotée à la SEC
    assert next(e for e in evs if e.official_id == "38047").tickers == []  # filiale canadienne : rien n'est deviné
    bi = next(e for e in evs if e.official_id == "38344")
    assert any("avec conditions" in n for n in bi.notes)
    assert any("Examen prioritaire" in n for n in next(e for e in evs if e.official_id == "38296").notes)
    assert [(a.regle, a.pourquoi) for a in evaluer(dict(d.to_dict(), tickers=["XMPL"]))] == \
        [(None, SANS_POINTS["sante_canada"])]  # contexte, 0 point


def test_liens_document_officiel_vraies_fiches_publiques():
    """Le lien « Document officiel » mène à la fiche publique de l'avis ou du contrat (pages lues le 3 octobre 2026)."""
    noc = lu(sc.fiche(38368)).decode("utf-8")
    assert all(x in noc for x in ("DAWNZERA", "2026-09-28", "CELYSTRA PHARMA INC.", "Nouvelle substance active (NSA)"))
    lien = ct.fiche({"owner_org": "cbsa-asfc", "reference_number": "C-2025-2026-Q3-908"})
    assert lien == "https://rechercher.ouvert.canada.ca/contrats/record/cbsa-asfc,C-2025-2026-Q3-908"
    contrat = " ".join(lu(lien).decode("utf-8").replace("&nbsp;", " ").split())
    assert all(x in contrat for x in ("Real Time Networks Inc", "2025-2026-Q3", "120 518,57"))


def test_sante_canada_fiches_vides_pas_d_info_on_reessaiera(tmp_path):
    vide = {sc.API + "drugproduct/?id=38368&lang=fr&type=json": b"[]"}
    evs = sc.collecter(contexte(tmp_path, FauxInternet(vide)))
    assert "38368" not in [e.official_id for e in evs] and len(evs) == 4


def test_sante_canada_liste_figee_met_la_source_en_panne(tmp_path):
    with pytest.raises(RuntimeError, match="figée"):
        sc.collecter(contexte(tmp_path, quand=datetime(2026, 11, 30, tzinfo=timezone.utc)))


# ---------- Contrats fédéraux ----------

@pytest.mark.parametrize("jour, attendu", [
    (date(2026, 10, 3), ["2026-2027-Q3", "2026-2027-Q2", "2026-2027-Q1"]),
    (date(2027, 1, 5), ["2026-2027-Q4", "2026-2027-Q3", "2026-2027-Q2"]),
    (date(2026, 4, 1), ["2026-2027-Q1", "2025-2026-Q4", "2025-2026-Q3"]),
])
def test_trimestres_de_l_exercice_federal(jour, attendu):
    assert ct.trimestres_suivis(jour) == attendu


def test_libelles_et_montants():
    assert ct.libelle_trimestre("2026-2027-Q1") == "avril à juin 2026"
    assert ct.libelle_trimestre("2026-2027-Q4") == "janvier à mars 2027"
    assert (ct.argent(353_432_290), ct.argent(6_382_883_842.61), ct.argent(12_345)) == ("353,4 M$", "6,38 G$", "12 345 $")


def test_vraie_page_de_l_api_lue_jusqu_aux_lignes_deja_vues():
    reel = json.loads(lu(ct.adresse("2026-2027-Q1", 0)))["result"]["records"]
    seuil = reel[10]["_id"]  # les 10 plus récentes sont « nouvelles »
    internet = type("I", (), {"get": lambda self, url: type("T", (), {"contenu": lu(url)})()})()
    neuves, haut, complet = ct.lire_trimestre(Contexte(client=internet, maintenant=MAINTENANT, donnees=Path(".")),
                                              "2026-2027-Q1", seuil)
    assert [x["_id"] for x in neuves] == [x["_id"] for x in reel[:10]] and haut == reel[0]["_id"] and complet


def test_contrats_1re_lecture_silencieuse_puis_seulement_les_nouvelles_lignes(tmp_path):
    api = FausseApiContrats()
    assert ct.collecter(contexte(tmp_path, FauxInternet(contrats=api))) == []  # rien n'est daté : rien de « nouveau »
    etat = json.loads(ct.chemin_etat(tmp_path).read_text(encoding="utf-8"))
    assert sorted(etat) == ["2026-2027-Q1", "2026-2027-Q2", "2026-2027-Q3"]
    assert len(etat["2026-2027-Q1"]["vus"]) == 92 and etat["2026-2027-Q1"]["complet"]
    assert etat["2026-2027-Q3"]["max_id"] == 0
    # Le lendemain : 2 vraies lignes publiées (copiées avec un nouveau _id dans le trimestre 2) et 1 ligne déjà vue
    # renvoyée par son ministère (nouveau _id, même numéro de référence) : seules les 2 premières sont nouvelles.
    haut = max(x["_id"] for x in api.lignes)
    nouveau_contrat = dict(next(x for x in api.lignes if x["instrument_type"] == "C" and ct.retenu(x)),
                           _id=haut + 1, reference_number="C-2026-2027-Q2-90001", reporting_period="2026-2027-Q2")
    lm = next(x for x in api.lignes if (x["owner_org"], x["reference_number"]) == ("dnd-mdn", "C-2026-2027-Q1-08143"))
    modification = dict(lm, _id=haut + 2, reference_number="C-2026-2027-Q2-90002", reporting_period="2026-2027-Q2")
    renvoyee = dict(next(x for x in api.lignes if ct.retenu(x)), _id=haut + 3)
    api.lignes += [nouveau_contrat, modification, renvoyee]
    lendemain = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    evs = ct.collecter(contexte(tmp_path, FauxInternet(contrats=api), quand=lendemain))
    assert sorted(e.official_id for e in evs) == sorted([ct.cle(nouveau_contrat), ct.cle(modification)])
    for e in evs:
        valider(e, lendemain.date())
        assert e.badge == "officiel", e.checks
        assert e.published_on == "2026-10-05" and e.official_url.startswith(ct.FICHE)
    m = next(e for e in evs if e.kind == "contrat_modifie")
    assert m.title == ("Contrat fédéral modifié : +944,4 M$ pour Lockheed Martin Canada Inc. (Défense nationale), "
                       "valeur totale 6,38 G$")
    assert m.occurred_on == "2026-07-01" and any("trimestre juillet à septembre 2026" in n for n in m.notes)
    assert m.amount_min == m.amount_max == pytest.approx(944_354_368.8)
    # Relancé : rien de nouveau
    assert ct.collecter(contexte(tmp_path, FauxInternet(contrats=api), quand=lendemain)) == []


def test_contrat_nom_exact_seulement_et_sans_points():
    x = {"_id": 1, "reference_number": "C-1", "owner_org": "dnd-mdn", "owner_org_title": "National Defence | Défense nationale",
         "vendor_name": "General Dynamics", "contract_date": "2026-05-01", "contract_value": "20000000.0",
         "original_value": "20000000.0", "amendment_value": None, "description_fr": "Véhicules", "instrument_type": "C",
         "reporting_period": "2026-2027-Q1"}
    from radar.collecteurs.sec import Symboles
    ev = ct.evenement(x, "2026-10-05", Symboles(json.loads(gzip.decompress(SEC.read_bytes()))))
    assert ev.tickers == ["GD"] and ev.title == "Contrat fédéral de 20,0 M$ : General Dynamics (Défense nationale)"
    assert ev.official_url == "https://rechercher.ouvert.canada.ca/contrats/record/dnd-mdn,C-1"
    assert [(a.regle, a.pourquoi) for a in evaluer(ev.to_dict())] == [(None, SANS_POINTS["contrat_ca"])]  # 0 point
    petit = dict(x, contract_value="9999999.99")
    assert not ct.retenu(petit) and ct.retenu(x)


# ---------- CCC ----------

def test_ccc_montants_exacts():
    assert [ccc.argent(v) for v in (500_000_000, 2_500_000, 1_000_000, 100_000, 1_250_000_000)] == \
        ["500 M$", "2,5 M$", "1 M$", "100 000 $", "1 250 M$"]


def test_ccc_page_des_rapports():
    page = lu(ccc.PAGE).decode("utf-8", "replace")
    liste = ccc.rapports(page)
    assert liste[0] == {"url": "https://www.ccc.ca/wp-content/uploads/2026/07/TD-2026-2027-Q1.pdf",
                        "libelle": "Quarter ending June 30, 2026", "fin": "2026-06-30"}
    assert len(liste) == 20 and ccc.page_modifiee(page) == "2026-08-31"


def test_ccc_rapport_avril_a_juin_2026_37_transactions():
    r = ccc.lire_rapport(lu("https://www.ccc.ca/wp-content/uploads/2026/07/TD-2026-2027-Q1.pdf"))
    ts = r["transactions"]
    assert (r["debut"], r["fin"], len(ts)) == ("2026-04-01", "2026-06-30", 37)
    assert sum(t["exportateur"] == "Canadian Exporter" for t in ts) == 11
    assert [ccc.libelle_fourchette(t) for t in ts if (t["min"] or 0) >= 250e6] == ["250 M$ à 500 M$"] * 2
    explosifs = [t["description"] for t in ts if "Valleyfield" in t["exportateur"]]
    assert explosifs == ["Explosives (inc. Propellant & Pyrotechnic) / Explosifs (y compris propulseur et pyrotechnique)"] * 4
    assert all(t["exportateur"] and t["destination"] and " / " in t["description"] for t in ts)


def test_ccc_rapport_janvier_a_mars_2026_plus_de_500_millions_et_lignes_separees():
    r = ccc.lire_rapport(lu("https://www.ccc.ca/wp-content/uploads/2026/06/TD-2025-2026-Q4.pdf"))
    ts = r["transactions"]
    assert len(ts) == 55  # 2 pages
    gdls = next(t for t in ts if t["exportateur"] == "General Dynamics Land Systems - Canada Corporation")
    assert (gdls["min"], gdls["max"], ccc.libelle_fourchette(gdls)) == (500e6, None, "plus de 500 M$")
    ferno = next(t for t in ts if t["exportateur"] == "Ferno Canada Inc.")
    assert (ferno["destination"], ferno["description"]) == ("Canada", "Medical Equipment / Équipement médical")
    airboss = next(t for t in ts if t["exportateur"] == "AirBoss Defense Group Ltd")
    assert airboss["description"] == "Nuclear Biological Chemical (NBC) Equipment / Nucléaire Biologique Chimique Équipement"
    ev = valider(ccc.evenement(r, {"url": "https://www.ccc.ca/x.pdf", "libelle": "", "fin": "2026-03-31"}, "2026-06-30"), JOUR)
    assert ev.badge == "officiel", ev.checks
    assert ev.amount_max is None and "au moins" in ev.data["resume"]


def test_ccc_une_info_par_rapport(tmp_path):
    evs = ccc.collecter(contexte(tmp_path))
    assert len(evs) == 1
    e = valider(evs[0], JOUR)
    assert e.badge == "officiel", e.checks
    assert e.title == ("Corporation commerciale canadienne : 37 transactions signées (1er avril 2026 au 30 juin 2026), "
                       "la plus grosse de 250 M$ à 500 M$")
    assert (e.occurred_on, e.published_on, e.official_id) == ("2026-06-30", "2026-08-31", "2026-04-01:2026-06-30")
    assert len(e.data["transactions"]) == 37 and e.tickers == []
    assert [(a.regle, a.pourquoi) for a in evaluer(dict(e.to_dict(), tickers=["XMPL"]))] == [(None, SANS_POINTS["ccc"])]


# ---------- Les 3 lecteurs ensemble ----------

def test_les_3_lecteurs_ensemble_sans_doublon(tmp_path):
    from radar.collecteurs import COLLECTEURS
    trois = {s: COLLECTEURS[s] for s in ("sante_canada", "contrats_ca_10k", "ccc")}
    api = FausseApiContrats()
    rapport = executer(tmp_path, client=FauxInternet(contrats=api), maintenant=MAINTENANT, collecteurs=trois)
    assert {s: rapport[s]["nouveaux"] for s in trois} == {"sante_canada": 5, "contrats_ca_10k": 0, "ccc": 1}, rapport
    rapport = executer(tmp_path, client=FauxInternet(contrats=api), maintenant=MAINTENANT, collecteurs=trois)
    assert all(rapport[s].get("nouveaux", 0) == 0 for s in trois), rapport
