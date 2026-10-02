"""Tests des lecteurs SEC sur de VRAIS documents officiels du 1er octobre 2026 (tests/fixtures/sec)."""

import json
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


def test_robot_complet_sur_une_vraie_journee(tmp_path, index):
    internet = FauxInternet(pages_du_1er_octobre(index))
    maintenant = datetime(2026, 10, 2, 11, 7, tzinfo=timezone.utc)
    rapport = executer(tmp_path, client=internet, maintenant=maintenant)
    assert all(r["ok"] for r in rapport.values()), rapport
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert sorted(e["tickers"][0] for e in fil) == ["CWH", "GME", "IOT", "NFG", "UUU"]
    assert all(e["badge"] == "officiel" for e in fil)
    sources = {s["id"]: s for s in json.loads((tmp_path / "app" / "sources.json").read_text(encoding="utf-8"))}
    assert sources["sec_form4"]["statut"] == "ok" and sources["sec_8k"]["statut"] == "ok"

    # Deuxième passage : la journée est déjà lue, on ne retélécharge pas les documents
    avant = len(internet.appels)
    executer(tmp_path, client=internet, maintenant=maintenant.replace(hour=16))
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
