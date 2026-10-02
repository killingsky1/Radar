"""Tests de la Maison-Blanche et du recoupement avec le Registre fédéral, sur de VRAIS documents (sept.-oct. 2026)."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from radar.collecteurs import maison_blanche as mb
from radar.collecteurs import registre
from radar.recoupement import titre_normalise
from radar.run import executer
from radar.validate import valider
from test_registre import FauxInternet, ajouter_textes, internet_du_2_octobre

F = Path(__file__).parent / "fixtures" / "maison_blanche" / "flux.xml"


def actions():
    return mb.lire_fil(F.read_bytes())


def par_titre(debut):
    return next(a for a in actions() if a["titre"].startswith(debut))


def test_le_fil_officiel_est_lu():
    a = actions()
    assert len(a) == 13
    assert all(x["lien"].startswith("https://www.whitehouse.gov/presidential-actions/") for x in a)


def test_ce_qu_on_garde_et_ce_qu_on_laisse():
    assert mb.choisir(par_titre("Inaugurating The Era Of Super Intelligence")) == ("decret", "Décret présidentiel")
    assert mb.choisir(par_titre("Modifying the Scope of Products of Canada"))[0] == "proclamation"  # tarifs sur le Canada
    assert mb.choisir(par_titre("Restoring Reciprocity in Government Procurement"))[0] == "memorandum"
    assert mb.choisir(par_titre("National Manufacturing Day, 2026")) is None  # journée commémorative
    assert mb.choisir(par_titre("Patriot Day 2026")) is None
    assert mb.choisir(par_titre("Nominations Sent to the Senate")) is None


def test_une_action_devient_une_info_officielle():
    a = par_titre("Inaugurating The Era Of Super Intelligence")
    ev = valider(mb.evenement(a, mb.choisir(a)), date(2026, 10, 2))
    assert ev.badge == "officiel", ev.checks
    assert ev.official_id == "2026/09/inaugurating-the-era-of-super-intelligence"
    assert ev.published_on == "2026-09-29"  # 21 h 17 UTC = 17 h 17 à Washington, le 29
    assert ev.data["resume"].startswith("Section 1 . Purpose . America stands at the forefront")


def test_titres_normalises():
    assert titre_normalise("Inaugurating The Era Of Super Intelligence") == titre_normalise(
        "Inaugurating the Era of Super Intelligence")
    assert titre_normalise("Reinvigorating America’s Hunting Heritage") == titre_normalise("Reinvigorating America's Hunting Heritage")


def internet_maison_blanche_et_registre():
    pages = internet_du_2_octobre()
    for k in list(pages):
        if "documents.json" in k:
            pages[k] = ajouter_textes(pages[k])
    pages[mb.FIL] = F.read_bytes()
    return FauxInternet(pages)


LECTEURS = {"maison_blanche": mb.collecter, "registre_federal": registre.collecter_registre}


def test_recoupement_maison_blanche_et_registre(tmp_path):
    internet = internet_maison_blanche_et_registre()
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc),
                       collecteurs=LECTEURS)
    assert rapport["maison_blanche"]["ok"] and rapport["registre_federal"]["ok"], rapport
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    decrets = {e["data"]["titre_officiel"]: e for e in fil if e["kind"] in ("decret", "presidentiel")}
    # Les 3 décrets du 29 septembre : la Maison-Blanche (le jour même) confirmée par le Registre (3 jours plus tard)
    for titre in ("Inaugurating The Era Of Super Intelligence",
                  "Eliminating Disease-Carrying Pests And Restoring Enjoyment Of The Great Outdoors",
                  "Streamlining Access to Government Services Through America.gov"):
        ev = decrets[titre]
        assert ev["source"] == "maison_blanche" and ev["badge"] == "confirme", (titre, ev["checks"])
        assert ev["confirmations"][0]["source"] == "registre_federal"
        assert ev["confirmations"][0]["official_url"].startswith("https://www.federalregister.gov/documents/2026/10/02/")
    # Le même acte du Registre n'est pas montré en double
    assert not any(e["source"] == "registre_federal" and e["kind"] == "presidentiel"
                   and e["data"]["titre_officiel"].startswith("Inaugurating") for e in fil)
    meta = json.loads((tmp_path / "app" / "meta.json").read_text(encoding="utf-8"))
    assert meta["compteurs"]["confirmees_30j"] == 3

    # Relancer ne change rien (le recoupement est fait une seule fois)
    avant = {f: f.read_text(encoding="utf-8") for f in (tmp_path / "evenements").glob("*.jsonl")}
    executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 23, 17, tzinfo=timezone.utc), collecteurs=LECTEURS)
    assert avant == {f: f.read_text(encoding="utf-8") for f in (tmp_path / "evenements").glob("*.jsonl")}


def test_pas_de_lien_si_deux_paires_possibles(tmp_path):
    from radar.recoupement import paires_presidentielles

    def ev(source, titre, quand, **data):
        return {"id": f"{source}:{titre}", "source": source, "published_on": quand, "occurred_on": quand,
                "data": {"titre_officiel": titre, **data}}

    tous = [ev("maison_blanche", "Excluding Certain Canadian Products", "2026-09-08"),
            ev("maison_blanche", "Excluding Certain Canadian Products", "2026-09-08"),
            ev("registre_federal", "Excluding Certain Canadian Products", "2026-09-08", sorte="presidentiel")]
    assert paires_presidentielles(tous) == []  # deux proclamations au titre identique : rien plutôt que faux
    tous[1]["data"]["titre_officiel"] = "Another Title"
    assert len(paires_presidentielles(tous)) == 1
    tous[2]["occurred_on"] = "2026-09-20"
    assert paires_presidentielles(tous) == []  # signées à plus de 3 jours d'écart : pas le même acte
