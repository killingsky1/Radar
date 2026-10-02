"""Tests des lecteurs SEC sur de VRAIS documents officiels du 1er octobre 2026 (tests/fixtures/sec)."""

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from radar.collecteurs import sec
from radar.collecteurs.sec import Symboles, evenements_13dg, evenements_8k, evenements_form4, jours_a_lire, lire_index
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "sec"
JOUR = date(2026, 10, 2)


def lire(nom: str) -> str:
    return (F / nom).read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def syms():
    return Symboles(json.loads(lire("company_tickers_exchange.json")))


@pytest.fixture(scope="module")
def index():
    return lire_index((F / "master.20261001.idx").read_text(encoding="latin-1"))


def form4(acc, index, syms):
    t = lire(f"{acc}.txt")
    return [valider(e, JOUR) for e in evenements_form4(t, empreinte(t.encode()), index[acc], syms)]


# ---------- Index et symboles ----------


def test_index_un_depot_par_numero(index):
    gme = index["0001822293-26-000002"]
    assert gme.forme == "4" and gme.depose == "2026-10-01"
    assert len(gme.filers) == 2  # la compagnie et le dirigeant : même dépôt, listé deux fois


def test_symbole_de_l_action_ordinaire(syms):
    assert syms.cote(1326380)["ticker"] == "GME"  # pas GME-WT (bons de souscription)
    assert syms.cote(1063761)["ticker"] == "SPG"  # pas SPG-PJ (actions privilégiées)
    assert syms.cote(999999999) is None


def test_jours_a_lire_saute_la_fin_de_semaine():
    lundi = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    assert jours_a_lire(lundi, set()) == [date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)]
    assert jours_a_lire(lundi, {"2026-10-01"}) == [date(2026, 9, 30), date(2026, 10, 2)]


# ---------- Formulaire 4 ----------


def test_achat_gamestop(index, syms):
    [ev] = form4("0001822293-26-000002", index, syms)
    assert ev.badge == "officiel", ev.checks
    assert ev.title == "Turner Nat (administrateur) achète 10 462 actions de GameStop Corp."
    assert ev.tickers == ["GME"] and ev.direction == 1
    assert ev.amount_max == 254540.46  # 10 462 × 24,33 $
    assert ev.occurred_on == "2026-10-01" and ev.published_on == "2026-10-01"
    assert ev.official_url == "https://www.sec.gov/Archives/edgar/data/1326380/000182229326000002/0001822293-26-000002-index.htm"


def test_vente_samsara_plusieurs_tranches(index, syms):
    [ev] = form4("0001895111-26-000019", index, syms)
    assert ev.badge == "officiel", ev.checks
    assert ev.kind == "vente_initie" and ev.tickers == ["IOT"]
    assert ev.amount_max == 10036932.05 and ev.data["actions"] == 263900
    assert len(ev.data["transactions"]) == 12
    assert any("10b5-1" in n for n in ev.notes)


@pytest.mark.parametrize("acc,raison", [
    ("0002109729-26-000010", "achat de 3 042 $ : sous le seuil"),
    ("0001193125-26-410415", "BBASX : fonds commun, pas une action cotée"),
    ("0000024741-26-000265", "seulement des avoirs, aucune transaction P ou S"),
])
def test_ecartes_avec_raison(acc, raison, index, syms):
    assert form4(acc, index, syms) == [], raison


def test_piege_symbole_declare_different_de_la_sec(index, syms):
    t = lire("0001822293-26-000002.txt").replace("<issuerTradingSymbol>GME<", "<issuerTradingSymbol>GMEX<")
    [ev] = [valider(e, JOUR) for e in evenements_form4(t, "a" * 64, index["0001822293-26-000002"], syms)]
    assert ev.badge == "a_verifier" and ev.checks["symbole_conforme_sec"] is False


def test_piege_achat_marque_comme_cede(index, syms):
    t = lire("0001822293-26-000002.txt")
    debut = t.index("<transactionAcquiredDisposedCode>")
    t = t[:debut] + t[debut:].replace("<value>A</value>", "<value>D</value>", 1)
    [ev] = [valider(e, JOUR) for e in evenements_form4(t, "a" * 64, index["0001822293-26-000002"], syms)]
    assert ev.badge == "a_verifier" and ev.checks["code_achat_ou_vente_reel"] is False


# ---------- 8-K ----------


def test_8k_national_fuel_gas(index, syms):
    acc = "0001193125-26-409787"
    t = lire(f"{acc}-index-headers.html")
    [ev] = [valider(e, JOUR) for e in evenements_8k(t, empreinte(t.encode()), index[acc], syms)]
    assert ev.badge == "officiel", ev.checks
    assert ev.tickers == ["NFG"]
    assert [i["item"] for i in ev.data["items"]] == ["1.01", "2.01"]
    assert ev.title == "NATIONAL FUEL GAS CO : contrat important signé + acquisition ou vente d'actifs complétée"


def test_8k_sans_item_majeur_ecarte(index, syms):
    t = lire("0000721371-26-000041-index-headers.html")  # Cardinal Health : 7.01 et 9.01 seulement
    assert evenements_8k(t, "a" * 64, index["0000721371-26-000041"], syms) == []


# ---------- 13D / 13G ----------


def test_13d_modifie(index, syms):
    acc = "0000921895-26-002701"
    t = lire(f"{acc}.txt")
    [ev] = [valider(e, JOUR) for e in evenements_13dg(t, empreinte(t.encode()), index[acc], syms)]
    assert ev.badge == "officiel", ev.checks
    assert ev.data["pourcentage"] == 40.8 and ev.data["nb_personnes"] == 9
    assert ev.title.startswith("AULT MILTON C III détient 40,8 % de UNIVERSAL SAFETY PRODUCTS")
    assert "mise à jour n° 20" in ev.title and ev.occurred_on == "2026-09-30"


def test_13g_passif(index, syms):
    acc = "0000899140-26-001079"
    t = lire(f"{acc}.txt")
    [ev] = [valider(e, JOUR) for e in evenements_13dg(t, empreinte(t.encode()), index[acc], syms)]
    assert ev.badge == "officiel", ev.checks
    assert ev.tickers == ["CWH"] and ev.data["pourcentage"] == 7.7
    assert "13G, placement passif" in ev.title and ev.occurred_on == "2026-06-30"


# ---------- Le robot au complet, avec un faux Internet qui sert les vrais documents ----------


class FauxInternet:
    def __init__(self, pages):
        self.pages = pages
        self.appels = []

    def get(self, url):
        self.appels.append(url)
        if url not in self.pages:
            raise ErreurSource(f"{url} : HTTP 404")
        contenu = self.pages[url]
        return type("T", (), {"contenu": contenu, "sha256": empreinte(contenu)})()


def pages_du_1er_octobre(index):
    pages = {
        "https://www.sec.gov/files/company_tickers_exchange.json": (F / "company_tickers_exchange.json").read_bytes(),
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.20261001.idx": (F / "master.20261001.idx").read_bytes(),
    }
    for acc, d in index.items():
        if d.forme in ("4", "SCHEDULE 13D/A", "SCHEDULE 13G"):
            pages[f"https://www.sec.gov/Archives/{d.fichier}"] = (F / f"{acc}.txt").read_bytes()
        elif d.forme == "8-K":
            pages[f"{d.dossier(d.filers[0][0])}/{acc}-index-headers.html"] = (F / f"{acc}-index-headers.html").read_bytes()
    return pages


LECTEURS_SEC = {"sec_form4": sec.collecter_form4, "sec_8k": sec.collecter_8k, "sec_13dg": sec.collecter_13dg}


def test_robot_complet_sur_une_vraie_journee(tmp_path, index):
    internet = FauxInternet(pages_du_1er_octobre(index))
    maintenant = datetime(2026, 10, 2, 11, 7, tzinfo=timezone.utc)
    rapport = executer(tmp_path, client=internet, maintenant=maintenant, collecteurs=LECTEURS_SEC)
    assert all(r["ok"] for r in rapport.values()), rapport
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert sorted(e["tickers"][0] for e in fil) == ["CWH", "GME", "IOT", "NFG", "UUU"]
    assert all(e["badge"] == "officiel" for e in fil)
    sources = {s["id"]: s for s in json.loads((tmp_path / "app" / "sources.json").read_text(encoding="utf-8"))}
    assert sources["sec_form4"]["statut"] == "ok" and sources["sec_8k"]["statut"] == "ok"

    # Deuxième passage : la journée est déjà lue, on ne retélécharge pas les documents
    avant = len(internet.appels)
    executer(tmp_path, client=internet, maintenant=maintenant.replace(hour=16), collecteurs=LECTEURS_SEC)
    nouveaux = internet.appels[avant:]
    assert all("Archives/edgar/data" not in u for u in nouveaux), nouveaux


def test_trop_de_documents_illisibles_met_la_source_en_panne(tmp_path, index, monkeypatch):
    internet = FauxInternet(pages_du_1er_octobre(index))
    monkeypatch.setattr(sec, "evenements_form4", lambda *a: (_ for _ in ()).throw(ValueError("format inconnu")))
    monkeypatch.setattr(sec, "JOURS_OUVRABLES_EN_ARRIERE", 1)
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 11, tzinfo=timezone.utc),
                       collecteurs={"sec_form4": sec.collecter_form4})
    # 5 formulaires 4 dans la journée : tous illisibles -> panne, et la journée n'est PAS marquée comme lue
    assert rapport["sec_form4"]["ok"] is False and "illisibles" in rapport["sec_form4"]["erreur"]
    lus = tmp_path / "sec" / "jours_lus.json"
    assert not lus.exists() or "2026-10-01" not in json.loads(lus.read_text()).get("sec_form4", [])


# ---------- Vraisemblance : les erreurs de frappe dans les documents eux-mêmes ----------


@pytest.mark.parametrize("prix,cas", [
    ("2272653", "SLBT : le prix total écrit dans la case « prix par action »"),
    ("5134", "UUU : 5134 au lieu de 5,134 $"),
])
def test_prix_absurde_va_dans_a_verifier(prix, cas, index, syms):
    t = lire("0001822293-26-000002.txt").replace("<value>24.33</value>", f"<value>{prix}</value>")
    [ev] = [valider(e, JOUR) for e in evenements_form4(t, "a" * 64, index["0001822293-26-000002"], syms)]
    assert ev.badge == "a_verifier", cas
    assert ev.checks["prix_plausible"] is False


def test_prix_eleve_permis_pour_les_actions_qui_valent_vraiment_autant():
    from radar.collecteurs.sec import controles_form4
    from radar.models import Evenement

    ev = Evenement(source="sec_form4", official_id="x:S", category="compagnies", kind="vente_initie", title="t",
                   occurred_on="2026-10-01", published_on="2026-10-01", official_url="https://www.sec.gov/x",
                   sha256="a" * 64, parser_version="t", tickers=["BRK-A"], amount_min=750_000.0, amount_max=750_000.0,
                   data={"symbole_declare": "BRK-A", "symboles_sec": ["BRK-A", "BRK-B"], "transactions": [
                       {"code": "S", "acquis_cede": "D", "actions": 1.0, "prix": 750_000.0, "date": "2026-10-01"}]})
    assert controles_form4(ev)["prix_plausible"] is True


def test_13d_sous_5_pourcent_est_une_sortie(index, syms):
    acc = "0000921895-26-002701"
    t = lire(f"{acc}.txt")
    for vieux in ("<percentOfClass>40.8</percentOfClass>", "<percentOfClass>39.3</percentOfClass>"):
        t = t.replace(vieux, "<percentOfClass>0</percentOfClass>")
    t = re.sub(r"<percentOfClass>[\d.]+</percentOfClass>", "<percentOfClass>0</percentOfClass>", t)
    [ev] = [valider(e, JOUR) for e in evenements_13dg(t, "a" * 64, index[acc], syms)]
    assert ev.badge == "officiel", ev.checks
    assert ev.kind == "sous_5_pourcent" and ev.direction == -1
    assert "passe sous 5 % de UNIVERSAL SAFETY PRODUCTS" in ev.title


def test_les_infos_deja_publiees_sont_reverifiees(tmp_path, index, monkeypatch):
    from radar import validate

    internet = FauxInternet(pages_du_1er_octobre(index))
    maintenant = datetime(2026, 10, 2, 11, 7, tzinfo=timezone.utc)
    executer(tmp_path, client=internet, maintenant=maintenant, collecteurs=LECTEURS_SEC)
    assert any(e["tickers"] == ["GME"] for e in json.loads((tmp_path / "app" / "fil.json").read_text()))

    # Un nouveau contrôle plus sévère apparaît : au passage suivant, l'info déjà publiée retourne « à vérifier ».
    monkeypatch.setitem(validate.CONTROLES_SOURCE, "sec_form4",
                        validate.CONTROLES_SOURCE["sec_form4"] + [lambda ev: {"nouveau_controle": "GME" not in ev.tickers}])
    executer(tmp_path, client=internet, maintenant=maintenant.replace(hour=16), collecteurs=LECTEURS_SEC)
    fil = json.loads((tmp_path / "app" / "fil.json").read_text())
    a_verifier = json.loads((tmp_path / "app" / "a_verifier.json").read_text())
    assert not any(e["tickers"] == ["GME"] for e in fil)
    assert any(e["tickers"] == ["GME"] and e["checks"]["nouveau_controle"] is False for e in a_verifier)


# ---------- Formulaire 144 et offres d'achat (vrais documents des 17 septembre au 1er octobre 2026) ----------


@pytest.fixture(scope="module")
def syms_complets():
    import gzip

    return Symboles(json.loads(gzip.decompress((F / "company_tickers_exchange_complet.json.gz").read_bytes())))


def form144(acc, syms_complets, remplacer=None):
    t = lire(f"{acc}.txt")
    for motif, neuf in (remplacer or {}).items():
        t, n = re.subn(motif, neuf, t, flags=re.S)
        assert n, motif
    depot = sec.DepotSec(acc, "144", "2026-10-01", f"edgar/data/x/{acc}.txt", [])
    return [valider(e, JOUR) for e in sec.evenements_144(t, empreinte(t.encode()), depot, syms_complets)]


SANS_PLAN = {r"<planAdoptionDates>.*?</planAdoptionDates>": ""}


def test_formulaire_144_vente_prevue_d_avance_sous_25_millions_ignoree(syms_complets):
    # Rocket Lab : 9,8 M$ dans un plan automatique (10b5-1) -> trop routinier pour le fil
    assert form144("0001950047-26-009944", syms_complets) == []


def test_formulaire_144_vente_libre_gardee(syms_complets):
    # Même document, sans la date d'adoption du plan (modifié pour le test) : vente décidée librement
    [ev] = form144("0001950047-26-009944", syms_complets, SANS_PLAN)
    assert ev.badge == "officiel", ev.checks
    assert ev.title == "ADAM C SPICE (dirigeant) prévoit vendre 140 157 actions de Rocket Lab Corp"
    assert ev.amount_max == 9766139.76 and ev.direction == -1
    assert ev.notes[0] == "Vente décidée librement (pas dans un plan automatique)."


def test_formulaire_144_prix_par_action_impossible(syms_complets):
    # Comme le cas réel Barclays (5 G$ pour 158 milliards d'actions = 0,03 $) : « à vérifier »
    [ev] = form144("0001950047-26-009944", syms_complets,
                   {**SANS_PLAN, r"<noOfUnitsSold>\d+</noOfUnitsSold>": "<noOfUnitsSold>158000000000</noOfUnitsSold>",
                    r"<noOfUnitsOutstanding>\d+</noOfUnitsOutstanding>":
                    "<noOfUnitsOutstanding>999000000000</noOfUnitsOutstanding>"})
    assert ev.badge == "a_verifier" and ev.checks["prix_implicite_plausible"] is False


def test_formulaire_144_plus_d_actions_qu_il_n_en_existe(syms_complets):
    # Comme le cas réel « 158 milliards d'actions de Barclays » : impossible, donc « à vérifier »
    [ev] = form144("0001950047-26-009944", syms_complets,
                   {**SANS_PLAN, r"<noOfUnitsOutstanding>\d+</noOfUnitsOutstanding>":
                    "<noOfUnitsOutstanding>1000</noOfUnitsOutstanding>"})
    assert ev.badge == "a_verifier" and ev.checks["actions_sous_le_total_en_circulation"] is False


def test_formulaire_144_petite_vente_ignoree(syms_complets):
    acc = "0001921094-26-001064"  # 60 561 $ : sous le seuil de 1 M$
    t = lire(f"{acc}.txt")
    depot = sec.DepotSec(acc, "144", "2026-10-01", f"edgar/data/x/{acc}.txt", [])
    assert sec.evenements_144(t, empreinte(t.encode()), depot, syms_complets) == []


def offre(nom, forme, syms_complets, vus=None):
    t = lire(f"{nom}.headers.html")
    depot = sec.DepotSec(nom.split(".")[0], forme, "2026-09-22", "x", [("1", "x")])
    return [valider(e, JOUR) for e in sec.evenements_offre(t, empreinte(t.encode()), depot, syms_complets,
                                                             set() if vus is None else vus)]


def test_offres_d_achat_reelles(syms_complets):
    [acv] = offre("0001193125-26-393827.SC_TO-T", "SC TO-T", syms_complets)
    assert acv.title == "Offre publique d'achat : COPART INC vise les actions de ACV Auctions Inc."
    assert acv.tickers == ["ACVA", "CPRT"] and acv.badge == "officiel"
    [rgr] = offre("0001193805-26-001242.SC_TO-T", "SC TO-T", syms_complets)
    assert rgr.tickers == ["RGR"] and "Beretta Holding S.A." in rgr.title
    [ssti] = offre("0001140361-26-037933.SC_TO-C", "SC TO-C", syms_complets)
    assert ssti.kind == "offre_annoncee" and ssti.tickers == ["SSTI"]


def test_offres_de_la_compagnie_elle_meme_ignorees(syms_complets):
    assert offre("0001193125-26-410644.SC_TO-I", "SC TO-I", syms_complets) == []  # rachat par l'émetteur
    assert offre("0001193125-26-410845.SC_TO-C", "SC TO-C", syms_complets) == []  # communication de l'émetteur


def test_privatisation_une_seule_info_par_compagnie(syms_complets):
    vus = set()
    a = offre("0001193125-26-398027.SC_13E3", "SC 13E3", syms_complets, vus)  # déposé par ReNew
    b = offre("0001193125-26-398221.SC_13E3", "SC 13E3", syms_complets, vus)  # déposé par le fonds du RPC
    assert len(a) == 1 and b == []
    assert a[0].title == "Projet de privatisation (règle 13e-3) : ReNew Energy Global plc" and a[0].tickers == ["RNW"]
