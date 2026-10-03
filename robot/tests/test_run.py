import json
from datetime import datetime, timezone

from conftest import SOURCE_GENERIQUE, bonne_info
from radar.run import executer, passage_auto

MAINTENANT = datetime(2026, 10, 2, 16, 37, tzinfo=timezone.utc)


def _json(chemin):
    return json.loads(chemin.read_text(encoding="utf-8"))


def faux_sec(ctx):
    return [bonne_info(), bonne_info(official_id="0001234567-26-000099", tickers=["APPLE INC"])]


def test_passage_complet(tmp_path):
    rapport = executer(tmp_path, collecteurs={"sec_form4": faux_sec}, maintenant=MAINTENANT)
    assert rapport["sec_form4"]["ok"] is True

    app = tmp_path / "app"
    assert [e["id"] for e in _json(app / "fil.json")] == [f"{SOURCE_GENERIQUE}:0001234567-26-000001"]
    assert [e["id"] for e in _json(app / "a_verifier.json")] == [f"{SOURCE_GENERIQUE}:0001234567-26-000099"]

    sources = {s["id"]: s for s in _json(app / "sources.json")}
    assert sources["sec_form4"]["statut"] == "ok"
    assert sources["war_contrats"]["statut"] == "a_venir"
    assert sources["sedi"]["statut"] == "ecartee"

    meta = _json(app / "meta.json")
    assert meta["sources_branchees"] == 1
    assert meta["evenements_3_mois"] == 1 and meta["a_verifier_3_mois"] == 1


def test_une_source_qui_plante_n_arrete_pas_les_autres(tmp_path):
    def plante(ctx):
        raise ConnectionError("site inaccessible")

    rapport = executer(tmp_path, collecteurs={"war_contrats": plante, "sec_form4": faux_sec}, maintenant=MAINTENANT)
    assert rapport["war_contrats"]["ok"] is False
    assert rapport["sec_form4"]["ok"] is True

    sources = {s["id"]: s for s in _json(tmp_path / "app" / "sources.json")}
    assert sources["war_contrats"]["statut"] == "en_panne"
    assert "site inaccessible" in sources["war_contrats"]["explication"]


def test_relancer_ne_modifie_pas_les_infos(tmp_path):
    executer(tmp_path, collecteurs={"sec_form4": faux_sec}, maintenant=MAINTENANT)
    fichier = tmp_path / "evenements" / "2026-09.jsonl"
    avant = fichier.read_bytes()
    executer(tmp_path, collecteurs={"sec_form4": faux_sec}, maintenant=MAINTENANT.replace(hour=22))
    assert fichier.read_bytes() == avant


def test_passage_selon_l_heure_de_l_est():
    assert passage_auto(datetime(2026, 10, 2, 11, 7, tzinfo=timezone.utc)) == "matin"  # 7 h 07 HAE
    assert passage_auto(datetime(2026, 10, 2, 13, 47, tzinfo=timezone.utc)) == "jour"  # 9 h 47
    assert passage_auto(datetime(2026, 10, 2, 16, 37, tzinfo=timezone.utc)) == "midi"  # 12 h 37
    assert passage_auto(datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc)) == "soir"  # 18 h 17
    assert passage_auto(datetime(2026, 10, 3, 3, 17, tzinfo=timezone.utc)) == "nuit"  # 23 h 17
    assert passage_auto(datetime(2026, 12, 1, 12, 7, tzinfo=timezone.utc)) == "matin"  # 7 h 07 HNE (hiver)
