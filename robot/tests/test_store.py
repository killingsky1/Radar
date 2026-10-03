import json

from conftest import AUJOURD_HUI, bonne_info
from radar.models import empreinte
from radar.store import Depot
from radar.validate import valider


def _lignes(chemin):
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines()]


def test_relancer_avec_les_memes_infos_ne_change_rien(tmp_path, aujourd_hui):
    premier = valider(bonne_info(collected_at="2026-10-02T11:07:00+00:00"), aujourd_hui)
    assert Depot(tmp_path).enregistrer([premier]) == {"nouveaux": 1, "modifies": 0, "inchanges": 0}
    fichier = tmp_path / "evenements" / "2026-09.jsonl"
    avant = fichier.read_bytes()

    deuxieme = valider(bonne_info(collected_at="2026-10-02T16:37:00+00:00"), aujourd_hui)
    assert Depot(tmp_path).enregistrer([deuxieme]) == {"nouveaux": 0, "modifies": 0, "inchanges": 1}
    assert fichier.read_bytes() == avant


def test_document_modifie_a_la_source_garde_l_ancienne_empreinte(tmp_path, aujourd_hui):
    Depot(tmp_path).enregistrer([valider(bonne_info(), aujourd_hui)])
    change = valider(bonne_info(sha256=empreinte(b"document corrige")), aujourd_hui)
    assert Depot(tmp_path).enregistrer([change])["modifies"] == 1

    [ligne] = _lignes(tmp_path / "evenements" / "2026-09.jsonl")
    assert ligne["sha256"] == empreinte(b"document corrige")
    assert ligne["data"]["anciennes_empreintes"] == [empreinte(b"document original")]
    assert any("modifié à la source" in n for n in ligne["notes"])


def test_info_corrigee_passe_de_a_verifier_a_evenements(tmp_path, aujourd_hui):
    mauvaise = valider(bonne_info(tickers=["APPLE INC"]), aujourd_hui)
    assert mauvaise.badge == "a_verifier"
    Depot(tmp_path).enregistrer([mauvaise])
    assert (tmp_path / "a_verifier" / "2026-09.jsonl").exists()

    corrigee = valider(bonne_info(), aujourd_hui)
    Depot(tmp_path).enregistrer([corrigee])
    assert not (tmp_path / "a_verifier" / "2026-09.jsonl").exists()
    [ligne] = _lignes(tmp_path / "evenements" / "2026-09.jsonl")
    assert ligne["badge"] == "officiel"


def test_nouveau_lecteur_ne_pretend_pas_que_le_document_a_change(tmp_path):
    from radar.store import Depot

    depot = Depot(tmp_path)
    depot.enregistrer([valider(bonne_info(), AUJOURD_HUI)])
    relu = valider(bonne_info(sha256=empreinte(b"lu autrement"), parser_version="test-2"), AUJOURD_HUI)
    assert Depot(tmp_path).enregistrer([relu]) == {"nouveaux": 0, "modifies": 1, "inchanges": 0}
    [ligne] = Depot(tmp_path).lire("evenements")
    assert ligne["parser_version"] == "test-2" and ligne["notes"] == [] and "anciennes_empreintes" not in ligne["data"]
