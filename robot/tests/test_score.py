"""Tests du score sur les VRAIES infos validées du robot (copie de data/evenements au 3 octobre 2026, 02 h 03 UTC)."""

import copy
import gzip
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from radar import score as sc
from radar.collecteurs.sec import Symboles
from radar.run import executer

F = Path(__file__).parent / "fixtures"
MAINTENANT = datetime(2026, 10, 3, 3, 17, tzinfo=timezone.utc)  # 23 h 17 le 2 octobre à Toronto


def vraies_infos():
    return [json.loads(l) for l in gzip.decompress((F / "score" / "evenements_20261003.jsonl.gz").read_bytes()).splitlines()]


def une(infos, **critere):
    trouvees = [e for e in infos if all(e.get(k) == v or e.get("data", {}).get(k) == v for k, v in critere.items())]
    assert len(trouvees) == 1, (critere, len(trouvees))
    return trouvees[0]


def symboles_sec():
    return Symboles(json.loads(gzip.decompress((F / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())))


def ligne(resultat, symbole):
    return next(r for liste in ("hausse", "baisse") for r in resultat[liste] if r["symbole"] == symbole)


def test_jour_de_calcul_a_l_heure_de_toronto():
    assert sc.jour_de_calcul(MAINTENANT).isoformat() == "2026-10-02"


def test_listes_sur_les_vraies_infos():
    r = sc.calculer(vraies_infos(), MAINTENANT)
    assert r["version"] == "score-1" and r["jour"] == "2026-10-02"
    assert len(r["hausse"]) == sc.MAX_LISTE and all(x["score"] >= sc.SEUIL for x in r["hausse"])
    assert [x["score"] for x in r["hausse"]] == sorted((x["score"] for x in r["hausse"]), reverse=True)
    assert [x["symbole"] for x in r["baisse"]] == ["LESL", "EGBN", "CBZ"]
    # Chaque info citée est jointe (l'app l'ouvre même si elle n'est plus dans le fil)
    for liste in ("hausse", "baisse"):
        for x in r[liste]:
            for g in x["groupes"]:
                assert all(i["id"] in r["evenements"] for i in g["infos"])
            assert all(c["id"] in r["evenements"] for c in x["contexte"])


def test_pdg_et_administrateur_en_groupe_gamestop():
    gme = ligne(sc.calculer(vraies_infos(), MAINTENANT), "GME")
    (g,) = gme["groupes"]
    assert (g["famille"], g["sens"]) == ("inities", 1)
    cohen = next(i for i in g["infos"] if i["compte"])
    assert cohen["id"].endswith(":P") and cohen["age"] == 3  # Ryan Cohen, déposé le 29 sept.
    assert cohen["facteurs"] == [["PDG, directeur financier ou président du conseil", 1.5], ["Groupe d'achats", 1.75]]
    assert cohen["points"] == round(2 * 1.5 * 1.75 * 0.5 ** (3 / 30), 2) == gme["score"] == 4.9


def test_sept_administrateurs_le_meme_jour_comptent_une_fois():
    spg = ligne(sc.calculer(vraies_infos(), MAINTENANT), "SPG")
    (g,) = spg["groupes"]
    assert len(g["infos"]) == 7 and sum(i["compte"] for i in g["infos"]) == 1
    assert spg["score"] == round(2 * 1.75 * 0.5 ** (1 / 30), 2) == 3.42  # pas 7 fois les points


def test_meme_achat_declare_par_l_administrateur_et_son_fonds_n_est_pas_un_groupe():
    infos = vraies_infos()
    simeon = une(infos, source="sec_form4", tickers=["ADRX"], entities=["George Simeon", "ADARx Pharmaceuticals, Inc."])
    sr_one = une(infos, source="sec_form4", tickers=["ADRX"],
                 entities=["SR ONE CAPITAL MANAGEMENT, LLC", "ADARx Pharmaceuticals, Inc."])
    assert (simeon["occurred_on"], simeon["amount_min"]) == (sr_one["occurred_on"], sr_one["amount_min"])
    adrx = ligne(sc.calculer([simeon, sr_one], MAINTENANT), "ADRX")
    assert all(["Groupe d'achats", 1.75] not in i["facteurs"] for i in adrx["groupes"][0]["infos"])
    age = (sc.jour_de_calcul(MAINTENANT) - date.fromisoformat(simeon["published_on"])).days
    assert adrx["score"] == round(2 * 0.5 ** (age / 30), 2)  # l'administrateur compte, seul


def test_achats_planifies_d_avance_zero_point():
    infos = [e for e in vraies_infos() if e["tickers"] == ["CRBG"] and e["kind"] == "achat_initie"]
    assert len(infos) == 3 and all(e["data"]["plan_10b5_1"] for e in infos)  # Nippon Life, 3 jours de suite
    assert all(a.regle is None and "10b5-1" in a.pourquoi for e in infos for a in sc.evaluer(e))
    assert sc.calculer(infos, MAINTENANT)["compagnies_notees"] == 0


@pytest.mark.parametrize("role, attendu", [
    ("Chief Executive Officer", 1.5), ("Chairperson & CEO", 1.5), ("VP and Chief Financial Officer", 1.5),
    ("CFO, Treasurer", 1.5), ("Executive COB", 1.5), ("Representative Director (PEO)", 1.5), ("Executive Chairman", 1.5),
    ("Vice Chairman", None), ("Vicepresident", None), ("PRESIDENT AND COO", None), ("Chief Operating Officer", None),
    ("administrateur", None), ("actionnaire de 10 %", 0.5),
])
def test_roles(role, attendu):
    f = sc.facteurs_role([role])
    assert (f[0][1] if f else None) == attendu


def test_13d_seulement_un_gestionnaire_de_fonds():
    saba = une(vraies_infos(), source="sec_13dg", tickers=["ZTR"])
    assert saba["data"]["type"] == "SCHEDULE 13D" and "types_declarants" not in saba["data"]  # lu avant le changement
    assert sc.evaluer(saba)[0].regle is None  # type inconnu : 0 point par prudence
    for types, regle in ((["IA", "PN"], "activiste_13d"), (["IN"], None), (["CO", "OO"], None)):
        e = copy.deepcopy(saba)
        e["data"]["types_declarants"] = types
        assert sc.evaluer(e)[0].regle == regle
    e["data"]["types_declarants"] = ["IA"]
    assert ligne(sc.calculer([e], MAINTENANT), "ZTR")["score"] == round(5 * 0.5 ** (2 / 30), 2)


def test_avis_144_ventes_d_elus_offres_et_ftc_sans_points():
    vues = 0
    for e in vraies_infos():
        if not e["tickers"]:
            assert sc.evaluer(e) == []  # aucune compagnie cotée : rien à noter
        elif e["source"] in ("sec_form144", "ftc_fusions", "sec_offres") or (e["source"].endswith("_ptr") and e["direction"] <= 0):
            apports = sc.evaluer(e)
            assert len(apports) == len(e["tickers"]) and all(a.regle is None and a.pourquoi for a in apports), e["id"]
            vues += 1
    assert vues == 23 + 9 + 61  # 23 avis 144, 9 feux verts avec symbole, 61 ventes d'élus


def test_les_points_fondent_avec_le_temps(monkeypatch):
    monkeypatch.setattr(sc, "SEUIL", 0.01)  # pour voir les petits scores
    e = copy.deepcopy(une(vraies_infos(), source="sec_form4", kind="achat_initie", tickers=["DKS"]))
    jour = sc.jour_de_calcul(MAINTENANT)
    for age, attendu in ((0, 2.0), (30, 1.0), (60, 0.5), (90, 0.25)):
        e["published_on"] = (jour - timedelta(days=age)).isoformat()
        assert sc.calculer([e], MAINTENANT)["hausse"][0]["score"] == attendu, age
    e["published_on"] = (jour - timedelta(days=91)).isoformat()
    assert sc.calculer([e], MAINTENANT)["compagnies_notees"] == 0


def test_grands_fonds_moitie_apres_60_jours(monkeypatch):
    from test_fonds13f import evenements  # vrais dépôts 13F de Berkshire (14 août 2026)

    monkeypatch.setattr(sc, "SEUIL", 0.01)
    evs = [e.to_dict() for e in evenements(1067983)]
    alphabet = next(e for e in evs if e["tickers"] == ["GOOGL"])
    (x,) = sc.calculer([alphabet], MAINTENANT)["hausse"]
    assert x["groupes"][0]["infos"][0]["age"] == 49
    assert x["score"] == round(1 * 0.5 ** (49 / 60), 2)
    bac = next(e for e in evs if e["tickers"] == ["BAC"])
    assert [a.regle for a in sc.evaluer(bac)] == [None]  # une vente de fonds : 0 point


def test_bonus_quand_deux_familles_sont_d_accord():
    infos = vraies_infos()
    cohen = une(infos, source="sec_form4", tickers=["GME"], entities=["Cohen Ryan", "GameStop Corp."])
    elu = copy.deepcopy(une(infos, source="chambre_ptr", kind="achat_elu", tickers=["LIN"]))
    elu["tickers"] = ["GME"]  # même élu, même date, mais sur GameStop : pour tester la règle
    gme = ligne(sc.calculer([cohen, elu], MAINTENANT), "GME")
    assert gme["bonus"]["plus"] == 1.25 and len(gme["groupes"]) == 2
    pts = {g["famille"]: g["points"] for g in gme["groupes"]}
    assert gme["score"] == round((2 * 1.5 * 0.5 ** (3 / 30) + 1 * 0.5 ** (20 / 30)) * 1.25, 2)
    assert pts["elus"] == round(0.5 ** (20 / 30), 2)


def test_infos_a_verifier_jamais_comptees():
    infos = vraies_infos()
    for e in infos:
        e["badge"] = "a_verifier"
    assert sc.calculer(infos, MAINTENANT)["compagnies_notees"] == 0


def test_faillite_et_procedures_sec_a_la_baisse():
    r = sc.calculer(vraies_infos(), MAINTENANT)
    lesl, egbn = ligne(r, "LESL"), ligne(r, "EGBN")
    assert lesl["groupes"][0]["infos"][0]["regle"] == "faillite" and lesl["score"] == round(-5 * 0.5 ** (2 / 30), 2)
    assert egbn["groupes"][0]["infos"][0]["regle"] == "sec_procedure"


def test_nouveau_seulement_pour_qui_vient_d_entrer():
    infos = vraies_infos()
    premier = sc.calculer(infos, MAINTENANT, precedent={"top": [], "eviter": []})  # ancien format : 1er calcul
    assert all(x["depuis"] is None for x in premier["hausse"] + premier["baisse"])
    plus_tard = datetime(2026, 10, 3, 11, 7, tzinfo=timezone.utc)
    sortie = premier["hausse"][-1]["symbole"]
    precedent = json.loads(json.dumps(premier))
    precedent["hausse"] = precedent["hausse"][:-1]  # une compagnie n'y était pas au calcul d'avant
    second = sc.calculer(infos, plus_tard, precedent=precedent)
    depuis = {x["symbole"]: x["depuis"] for x in second["hausse"]}
    assert depuis[sortie] == plus_tard.isoformat()
    assert all(d is None for s, d in depuis.items() if s != sortie)


def test_noms_officiels_de_la_sec():
    infos = vraies_infos()
    sans = sc.calculer(infos, MAINTENANT)
    avec = sc.calculer(infos, MAINTENANT, symboles=symboles_sec())
    assert ligne(sans, "EGBN")["nom"] == "Eagle Bancorp, Inc."  # nom du communiqué de la SEC
    assert ligne(avec, "EGBN")["nom"] == "EAGLE BANCORP INC"  # liste officielle de la SEC
    assert ligne(avec, "GME")["nom"] == ligne(sans, "GME")["nom"] == "GameStop Corp."


def test_publication_ecrit_le_score(tmp_path):
    (tmp_path / "evenements").mkdir()
    (tmp_path / "evenements" / "2026-10.jsonl").write_bytes(gzip.decompress(
        (F / "score" / "evenements_20261003.jsonl.gz").read_bytes()))
    executer(tmp_path, collecteurs={}, maintenant=MAINTENANT)
    r = json.loads((tmp_path / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
    assert r["version"] == "score-1" and r["hausse"][0]["symbole"] in ("PRHI", "XENE")
    assert r["methode"]["regles"][0]["code"] == "achat_dirigeant"
    assert all(e in r["methode"]["etudes"] for regle in r["methode"]["regles"] for e in regle["etudes"])
    # Le passage suivant garde la date d'entrée de chacun
    executer(tmp_path, collecteurs={}, maintenant=datetime(2026, 10, 3, 11, 7, tzinfo=timezone.utc))
    r2 = json.loads((tmp_path / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
    assert {x["symbole"]: x["depuis"] for x in r2["hausse"]} == {x["symbole"]: x["depuis"] for x in r["hausse"]}


def test_un_score_qui_plante_n_empeche_pas_la_publication(tmp_path, monkeypatch, capsys):
    from radar import publish

    (tmp_path / "evenements").mkdir()
    (tmp_path / "evenements" / "2026-10.jsonl").write_bytes(gzip.decompress(
        (F / "score" / "evenements_20261003.jsonl.gz").read_bytes()))
    executer(tmp_path, collecteurs={}, maintenant=MAINTENANT)
    avant = (tmp_path / "app" / "aujourdhui.json").read_text(encoding="utf-8")

    def plante(*args, **kwargs):
        raise ValueError("bogue simulé")

    monkeypatch.setattr(publish, "calculer", plante)
    (tmp_path / "app" / "fil.json").unlink()
    executer(tmp_path, collecteurs={}, maintenant=datetime(2026, 10, 3, 11, 7, tzinfo=timezone.utc))
    assert (tmp_path / "app" / "fil.json").exists()  # les infos sont publiées quand même
    assert (tmp_path / "app" / "aujourdhui.json").read_text(encoding="utf-8") == avant  # l'ancien score reste
    assert "Score : erreur, l'ancien calcul est gardé (ValueError: bogue simulé)" in capsys.readouterr().out
