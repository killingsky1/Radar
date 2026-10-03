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
    assert r["version"] == sc.VERSION and r["jour"] == "2026-10-02"
    # Listes strictes (lot B) : 7/10 et plus, 3/10 et moins. Mesuré sur ces vraies infos : 16 au lieu de 20, 1 au lieu
    # de 3 (EGBN 3,4/10 et CBZ 3,5/10 sortent de la liste « baisse »).
    assert len(r["hausse"]) == 16 and all(x["note10"] >= 7.0 for x in r["hausse"])
    assert [x["score"] for x in r["hausse"]] == sorted((x["score"] for x in r["hausse"]), reverse=True)
    assert [x["symbole"] for x in r["baisse"]] == ["LESL"] and r["baisse"][0]["note10"] <= 3.0
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


def test_meme_achat_declare_par_l_administrateur_et_son_fonds_n_est_pas_un_groupe(monkeypatch):
    monkeypatch.setattr(sc, "NOTE_HAUSSE", 5.1)  # pour voir les petites notes
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


def test_13d_seulement_un_gestionnaire_de_fonds_qui_dit_l_action_sous_evaluee():
    saba = une(vraies_infos(), source="sec_13dg", tickers=["ZTR"])
    assert saba["data"]["type"] == "SCHEDULE 13D" and "types_declarants" not in saba["data"]  # lu avant le changement
    assert sc.evaluer(saba)[0].pourquoi == sc.SANS_POINTS["13d_type_inconnu"]  # 0 point par prudence
    cas = (
        ({"types_declarants": ["IA", "PN"], "but_sous_evalue": True}, "activiste_13d", None),
        ({"types_declarants": ["IA", "PN"], "but_sous_evalue": False}, None, "13d_pas_sous_evalue"),
        ({"types_declarants": ["IA", "PN"], "but_sous_evalue": None}, None, "13d_pas_sous_evalue"),  # sans point 4
        ({"types_declarants": ["IA", "PN"]}, None, "13d_but_inconnu"),  # lu avant que le robot lise le but
        ({"types_declarants": ["IN"], "but_sous_evalue": True}, None, "13d_autre"),
        ({"types_declarants": ["CO", "OO"], "but_sous_evalue": True}, None, "13d_autre"),
    )
    for champs, regle, raison in cas:
        e = copy.deepcopy(saba)
        e["data"].update(champs)
        (a,) = sc.evaluer(e)
        assert (a.regle, a.pourquoi) == (regle, sc.SANS_POINTS.get(raison)), champs
    e["data"].update(cas[0][0])
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
    monkeypatch.setattr(sc, "NOTE_HAUSSE", 5.1)  # pour voir les petites notes
    e = copy.deepcopy(une(vraies_infos(), source="sec_form4", kind="achat_initie", tickers=["DKS"]))
    jour = sc.jour_de_calcul(MAINTENANT)
    for age, attendu in ((0, 2.0), (30, 1.0), (60, 0.5), (90, 0.25)):
        e["published_on"] = (jour - timedelta(days=age)).isoformat()
        assert sc.calculer([e], MAINTENANT)["hausse"][0]["score"] == attendu, age
    e["published_on"] = (jour - timedelta(days=91)).isoformat()
    assert sc.calculer([e], MAINTENANT)["compagnies_notees"] == 0


def test_grands_fonds_moitie_apres_60_jours(monkeypatch):
    from test_fonds13f import evenements  # vrais dépôts 13F de Berkshire (14 août 2026)

    monkeypatch.setattr(sc, "NOTE_HAUSSE", 5.1)
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


def test_faillite_et_procedures_sec_a_la_baisse(monkeypatch):
    monkeypatch.setattr(sc, "NOTE_BAISSE", 4.9)  # EGBN (3,4/10) : pour voir la règle même hors de la liste
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


def test_noms_officiels_de_la_sec(monkeypatch):
    monkeypatch.setattr(sc, "NOTE_BAISSE", 4.9)  # EGBN (3,4/10)
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
    assert r["version"] == sc.VERSION and r["hausse"][0]["symbole"] in ("PRHI", "XENE")
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


# ---------- Émissions et 13D : vrais dépôts relus le 3 octobre 2026 (tests/fixtures/sec/emissions) ----------

E = F / "sec" / "emissions"


def depot_lu(acc, forme, depose, cik):
    from radar.collecteurs.sec import DepotSec, evenements_13dg, evenements_form4
    from radar.models import empreinte
    from radar.validate import valider

    texte = gzip.decompress((E / f"{acc}.txt.gz").read_bytes()).decode("utf-8")
    lire = evenements_form4 if forme == "4" else evenements_13dg
    evs = lire(texte, empreinte(texte.encode()), DepotSec(acc, forme, depose, "", [(str(cik), "x")]), symboles_sec())
    return [valider(e, date(2026, 10, 2)).to_dict() for e in evs]


def test_entree_en_bourse_d_adarx_zero_point():
    # OrbiMed (note « purchased in the Issuer's initial public offering ») + le 13D d'OrbiMed (pas « sous-évaluée »)
    # + George Simeon (même jour, même prix de 17 $, sans la note) : rien de tout ça n'est un achat en bourse.
    orbimed = depot_lu("0000947871-26-000910", "4", "2026-09-30", 1802369)
    treize_d = depot_lu("0000947871-26-000917", "SCHEDULE 13D", "2026-10-02", 1802369)
    simeon = [e for e in vraies_infos() if e["tickers"] == ["ADRX"] and "George Simeon" in e["entities"]]
    assert len(orbimed) == len(treize_d) == len(simeon) == 1
    assert "initial public offering" in orbimed[0]["data"]["hors_bourse"] and orbimed[0]["badge"] == "officiel"
    assert any("Note du déposant : transaction lors d'une émission" in n for n in orbimed[0]["notes"])
    assert treize_d[0]["data"]["but_sous_evalue"] is False
    r = sc.calculer(orbimed + treize_d + simeon, MAINTENANT)
    assert r["compagnies_notees"] == 0
    raisons = {a.ev["id"]: a.pourquoi for e in orbimed + treize_d + simeon
               for a in sc.evaluer(e, sc.achats_d_emission(orbimed + simeon))}
    assert sorted(raisons.values()) == sorted([sc.SANS_POINTS["emission"], sc.SANS_POINTS["13d_pas_sous_evalue"],
                                               sc.SANS_POINTS["emission_meme_prix"]])


def test_achat_negocie_en_prive_zero_point():
    (hgbl,) = depot_lu("0001193125-26-407271", "4", "2026-09-29", 849145)
    assert "privately negotiated" in hgbl["data"]["hors_bourse"]
    assert [a.pourquoi for a in sc.evaluer(hgbl)] == [sc.SANS_POINTS["emission"]]


def test_vrais_fonds_activistes_et_financement_de_fusion():
    (equinox,) = depot_lu("0001013594-26-000998", "SCHEDULE 13D", "2026-09-30", 1549966)
    (gate_city,) = depot_lu("0001398344-26-017759", "SCHEDULE 13D", "2026-10-01", 1672909)
    (nccs,) = depot_lu("0001493152-26-045190", "SCHEDULE 13D", "2026-09-30", 1846416)
    assert equinox["data"]["but_sous_evalue"] and gate_city["data"]["but_sous_evalue"]
    assert "undervalued" in equinox["data"]["extrait_but"]
    assert nccs["data"]["but_sous_evalue"] is False and "Forward Purchase Agreement" in nccs["data"]["extrait_but"]
    r = sc.calculer([equinox, gate_city, nccs], MAINTENANT)
    assert {x["symbole"] for x in r["hausse"]} == {equinox["tickers"][0], gate_city["tickers"][0]}
    assert ligne(r, gate_city["tickers"][0])["score"] == round(5 * 0.5 ** (1 / 30), 2)


def test_note_d_une_autre_ligne_ne_marque_pas_l_achat():
    # Dépôt de George Simeon : les conversions d'actions privilégiées (code C) parlent de l'entrée en bourse, pas ses
    # achats (code P). L'achat n'est donc pas marqué par sa propre note : c'est la règle « même jour, même prix » qui joue.
    (simeon,) = depot_lu("0001193125-26-408061", "4", "2026-09-29", 1802369)
    assert simeon["data"]["hors_bourse"] is None and all(t["hors_bourse"] is None for t in simeon["data"]["transactions"])
    orbimed = depot_lu("0000947871-26-000910", "4", "2026-09-30", 1802369)
    assert [a.pourquoi for a in sc.evaluer(simeon, sc.achats_d_emission(orbimed))] == [sc.SANS_POINTS["emission_meme_prix"]]
    assert [a.regle for a in sc.evaluer(simeon)] == ["achat_dirigeant"]  # sans l'achat d'OrbiMed : un achat normal


def test_achat_automatique_reinvestissement_de_dividendes():
    # Simon Property, 1er oct. 2026 : 7 administrateurs « achètent » le même jour ; la note dit que ce sont des actions
    # acquises par le réinvestissement des dividendes d'actions reçues en rémunération. Pas une décision d'acheter.
    (spg,) = depot_lu("0001189793-26-000014", "4", "2026-10-01", 1063761)
    assert spg["badge"] == "officiel" and spg["data"]["hors_bourse"] is None
    assert "reinvestment of dividends" in spg["data"]["automatique"]
    assert any(n.startswith("Note du déposant : achat automatique") for n in spg["notes"])
    assert [a.pourquoi for a in sc.evaluer(spg)] == [sc.SANS_POINTS["automatique"]]
    assert sc.calculer([spg], MAINTENANT)["compagnies_notees"] == 0


def test_fonds_enregistre_mis_a_part():
    # Total Return Securities Fund (SWZ) : le PDG achète, mais c'est un fonds fermé (sa fiche SEC : N-CSR, NPORT-P…).
    infos = vraies_infos()
    swz = une(infos, source="sec_form4", tickers=["SWZ"])
    assert [a.regle for a in sc.evaluer(swz)] == ["achat_dirigeant"]
    r = sc.calculer(infos, MAINTENANT, fonds={"SWZ"})
    assert "SWZ" not in {x["symbole"] for x in r["hausse"] + r["baisse"]}
    assert sc.calculer([swz], MAINTENANT, fonds={"SWZ"})["compagnies_notees"] == 0
    assert sc.SANS_POINTS["fonds"] in r["methode"]["sans_points"]


def test_publication_met_les_fonds_a_part(tmp_path):
    (tmp_path / "evenements").mkdir()
    (tmp_path / "evenements" / "2026-10.jsonl").write_bytes(gzip.decompress(
        (F / "score" / "evenements_20261003.jsonl.gz").read_bytes()))
    executer(tmp_path, collecteurs={}, maintenant=MAINTENANT)
    avant = json.loads((tmp_path / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
    assert "SWZ" in {x["symbole"] for x in avant["hausse"]}
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "emetteurs.json").write_text(json.dumps(
        {"SWZ": {"cik": 813623, "nom": "Total Return Securities Fund", "type": "fonds", "lu": "2026-10-03",
                 "formulaires_fonds": ["N-CSR", "NPORT-P"]}}), encoding="utf-8")
    executer(tmp_path, collecteurs={}, maintenant=MAINTENANT)
    apres = json.loads((tmp_path / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
    assert "SWZ" not in {x["symbole"] for x in apres["hausse"]}


def test_note_sur_le_total_detenu_ne_rend_pas_l_achat_automatique():
    # PG&E : un administrateur achète 7 500 actions en bourse ; la note « dividend reinvestment » porte sur le TOTAL
    # détenu après la transaction (des unités reçues en juillet), pas sur l'achat. L'achat compte.
    (pcg,) = depot_lu("0001628280-26-064255", "4", "2026-10-01", 1004980)
    assert pcg["data"]["automatique"] is None and pcg["data"]["hors_bourse"] is None
    assert [a.regle for a in sc.evaluer(pcg)] == ["achat_dirigeant"]
