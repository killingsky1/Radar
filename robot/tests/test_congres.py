"""Congrès : chefs, comités, H.R. 7008 et ses votes, sur les VRAIS fichiers officiels lus le 3 octobre 2026
(tests/fixtures/congres : Clerk de la Chambre, house.gov, senate.gov, govinfo)."""

import copy
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from radar import score as sc
from radar.collecteurs import congres as cg
from radar.models import empreinte
from radar.run import Contexte, executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures"
C = F / "congres"
MAINTENANT = datetime(2026, 10, 3, 3, 17, tzinfo=timezone.utc)
CHEFS = {
    "chambre:LA04": "Speaker of the House", "chambre:LA01": "Majority Leader", "chambre:MN06": "Majority Whip",
    "chambre:MI09": "Republican Conference Chairman", "chambre:NY08": "Democratic Leader",
    "chambre:MA05": "Democratic Whip", "chambre:CA33": "Democratic Caucus Chairman",
    "senat:THUNE:SD": "Senate Majority Leader", "senat:BARRASSO:WY": "Majority Whip",
    "senat:COTTON:AR": "Republican Conference Chair", "senat:SCHUMER:NY": "Democratic Leader Chair of the Conference",
    "senat:DURBIN:IL": "Democratic Whip",
}


def lu(nom):
    return gzip.decompress((C / nom).read_bytes())


def congres_officiel():
    codes = cg.codes_comites_senat(lu("senat_comites.html.gz").decode())
    return cg.construire_congres(cg.lire_membres_chambre(lu("MemberData.xml.gz")),
                                 cg.lire_chefs_chambre(lu("chambre_chefs.html.gz").decode()),
                                 [cg.lire_comite_senat(lu(f"senat_{c}.xml.gz")) for c in codes],
                                 cg.lire_chefs_senat(lu("senat_chefs.html.gz").decode()))


def vraies_infos():
    return [json.loads(l) for l in gzip.decompress((F / "score" / "evenements_20261003.jsonl.gz").read_bytes()).splitlines()]


PAGES = {
    cg.MEMBRES_CHAMBRE: "MemberData.xml.gz", cg.CHEFS_CHAMBRE: "chambre_chefs.html.gz",
    cg.CHEFS_SENAT: "senat_chefs.html.gz", cg.COMITES_SENAT: "senat_comites.html.gz",
    cg.PROJET: "BILLSTATUS-119hr7008.xml.gz",
    "https://clerk.house.gov/evs/2026/roll279.xml": "roll279.xml.gz",
    "https://clerk.house.gov/evs/2026/roll280.xml": "roll280.xml.gz",
    "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_00253.xml": "vote_119_2_00253.xml.gz",
}


class FauxInternet:
    def __init__(self, sauf=()):
        self.appels, self.sauf = [], set(sauf)

    def get(self, url):
        self.appels.append(url)
        nom = PAGES.get(url)
        if nom is None and url.startswith(cg.COMITE_SENAT.split("{}")[0]):
            nom = f"senat_{url.rsplit('_', 1)[1][:4]}.xml.gz"
        if nom is None or nom in self.sauf:
            raise AssertionError(f"page inattendue : {url}")
        c = lu(nom)
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def contexte(tmp_path, **k):
    return Contexte(client=FauxInternet(**k), maintenant=MAINTENANT, donnees=tmp_path)


# ---------- Chefs et comités ----------

def test_les_12_chefs_de_l_etude_selon_les_listes_officielles():
    c = congres_officiel()
    cg.verifier_congres(c)
    assert {x["cle"]: x["titre"] for x in c["chefs"]} == CHEFS
    assert len(c["chambre"]) == 439 and len(c["senat"]) == 100
    assert c["senat"]["SCHUMER:NY"]["nom"] == "Charles E. Schumer"


@pytest.mark.parametrize("titre, attendu", [
    ("Speaker of the House", "speaker"), ("Senate Majority Leader", "chef"), ("Democratic Leader", "chef"),
    ("Democratic Leader Chair of the Conference", "chef"), ("Majority Whip", "whip"),
    ("Republican Conference Chairman", "president_caucus"), ("Democratic Caucus Chairman", "president_caucus"),
    ("Assistant Democratic Leader", None), ("Vice Chair of the Conference", None), ("Deputy Whip", None),
    ("President pro tempore", None), ("Republican Policy Committee Chairman", None),
])
def test_seuls_les_postes_de_l_etude_comptent(titre, attendu):
    assert cg.poste(titre) == attendu


def test_liste_de_chefs_incomplete_refusee():
    c = congres_officiel()
    c["chefs"] = [x for x in c["chefs"] if x["cle"] != "senat:SCHUMER:NY"]
    with pytest.raises(ValueError, match="4 au Sénat"):
        cg.verifier_congres(c)


def test_lecteur_des_comites_ecrit_la_liste_sans_infos_dans_le_fil(tmp_path):
    ctx = contexte(tmp_path)
    assert cg.collecter_comites(ctx) == []
    gardee = json.loads(cg.chemin_congres(tmp_path).read_text(encoding="utf-8"))
    assert len(gardee["chefs"]) == 12 and gardee["lu"] == MAINTENANT.isoformat()
    assert sum(1 for u in ctx.client.appels if "committee_memberships_" in u) == 24  # les 24 comités du Sénat


def test_lecteur_des_comites_en_panne_garde_l_ancienne_liste(tmp_path, monkeypatch):
    cg.collecter_comites(contexte(tmp_path))
    avant = cg.chemin_congres(tmp_path).read_text(encoding="utf-8")
    monkeypatch.setattr(cg, "lire_chefs_senat", lambda page: [])  # page des chefs changée : 0 chef trouvé
    with pytest.raises(ValueError, match="0 au Sénat"):
        cg.collecter_comites(contexte(tmp_path))
    assert cg.chemin_congres(tmp_path).read_text(encoding="utf-8") == avant


# ---------- H.R. 7008 et ses votes ----------

def test_statut_officiel_du_projet():
    p = cg.lire_projet(lu("BILLSTATUS-119hr7008.xml.gz"))
    assert (p["numero"], p["congres"], p["titre"]) == ("HR 7008", "119", "Stop Insider Trading Act")
    assert p["derniere_action"]["date"] == "2026-09-30"
    assert [(v["chambre"], v["numero"], v["date"]) for v in p["votes"]] == [
        ("House", "279", "2026-07-22"), ("House", "280", "2026-07-22"), ("Senate", "253", "2026-09-30")]
    assert cg.etape_fr(p["derniere_action"]["texte"]) == \
        "bloqué au Sénat (clôture rejetée, 53 pour, 47 contre, 60 voix requises)"


def test_projet_une_info_par_nouvelle_etape(tmp_path):
    ctx = contexte(tmp_path)
    evs = cg.collecter_hr7008(ctx)
    assert len(evs) == 1 and evs[0].title.endswith("bloqué au Sénat (clôture rejetée, 53 pour, 47 contre, "
                                                   "60 voix requises)")
    assert evs[0].published_on == "2026-09-30" and evs[0].official_url == cg.PROJET
    assert "7 à 14 jours" in evs[0].data["resume"]
    assert valider(evs[0], MAINTENANT.date()).badge == "officiel"
    assert json.loads(cg.chemin_projet(tmp_path).read_text(encoding="utf-8"))["derniere_action"]["date"] == "2026-09-30"


def test_votes_lus_une_fois_avec_le_sujet_en_clair(tmp_path):
    ctx = contexte(tmp_path)
    cg.collecter_hr7008(ctx)
    evs = cg.collecter_votes(ctx)
    assert [e.title.split(" : ", 1)[1] for e in evs] == [
        "la Chambre rejette la motion de renvoi en comité (procédure), 211 pour, 218 contre",
        "la Chambre adopte le projet de loi, 232 pour, 198 contre",
        "le Sénat rejette la clôture (60 voix requises pour ouvrir le débat), 53 pour, 47 contre"]
    for e in evs:
        assert valider(e, MAINTENANT.date()).badge == "officiel", e.official_id  # le total officiel = le recompte des votes un par un
    gardes = json.loads(cg.chemin_votes(tmp_path).read_text(encoding="utf-8"))
    assert sorted(gardes) == ["H279-2026", "H280-2026", "S253-2026"] and len(gardes["S253-2026"]["votes"]) == 100


def test_votes_deja_lus_pas_relus_meme_hors_des_3_derniers_mois(tmp_path):
    lecteurs = {"hr7008": cg.collecter_hr7008, "votes": cg.collecter_votes}
    executer(tmp_path, collecteurs=lecteurs, client=FauxInternet(), maintenant=MAINTENANT)
    assert sorted(f.name for f in (tmp_path / "evenements").glob("*.jsonl")) == ["2026-07.jsonl", "2026-09.jsonl"]
    for mois in ("2026-08", "2026-10"):  # juillet sort des 3 derniers fichiers mensuels
        (tmp_path / "evenements" / f"{mois}.jsonl").write_text("", encoding="utf-8")
    internet = FauxInternet()
    rapport = executer(tmp_path, collecteurs=lecteurs, client=internet, maintenant=MAINTENANT)
    assert internet.appels == [cg.PROJET]  # seulement le statut du projet : aucun vote retéléchargé
    assert all(r["ok"] for r in rapport.values())
    etat = json.loads((tmp_path / "etat_sources.json").read_text(encoding="utf-8"))
    assert etat["votes"]["compte"]["recus"] == 0 and etat["hr7008"]["compte"]["recus"] == 0


def test_vote_dont_le_total_ne_se_recompte_pas_refuse():
    v = cg.lire_vote_senat(lu("vote_119_2_00253.xml.gz"))
    v["oui"] = 54  # total officiel qui ne correspond pas aux votes un par un
    url = "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_00253.xml"
    info = {"chambre": "Senate", "numero": "253", "url": url, "date": "2026-09-30"}
    ev = valider(cg.evenement_vote(v, info, lu("vote_119_2_00253.xml.gz")), MAINTENANT.date())
    assert ev.badge == "a_verifier" and ev.checks["total_recompte"] is False


# ---------- Relier les élus des transactions ----------

def votes_officiels():
    p = cg.lire_projet(lu("BILLSTATUS-119hr7008.xml.gz"))
    votes = {}
    for info, nom in zip(p["votes"], ("roll279.xml.gz", "roll280.xml.gz", "vote_119_2_00253.xml.gz")):
        v = (cg.lire_vote_chambre if info["chambre"] == "House" else cg.lire_vote_senat)(lu(nom))
        votes[f"{v['chambre'][0]}{info['numero']}-{v['date'][:4]}"] = {**v, "numero": info["numero"]}
    return votes


def test_les_14_elus_des_transactions_relies_aux_listes_officielles():
    par_elu = cg.relier_elus(vraies_infos(), congres_officiel(), votes_officiels())
    assert len(par_elu) == 14 and not any(i["chef"] for i in par_elu.values())  # aucun chef n'a de transaction
    assert par_elu["A. Mitchell McConnell Jr."]["cle"] == "senat:MCCONNELL:KY"
    b = par_elu["John Boozman"]
    assert b["cle"] == "senat:BOOZMAN:AR"
    assert {"nom": "Committee on Agriculture, Nutrition, and Forestry", "role": "Chairman"} in b["comites"]
    assert [(v["sujet"], v["vote_fr"]) for v in b["votes_hr7008"]] == [
        ("clôture pour ouvrir le débat (60 voix requises)", "pour")]
    assert [v["vote_fr"] for v in par_elu["Sheldon Whitehouse"]["votes_hr7008"]] == ["contre"]
    # À la Chambre : les DEUX votes, chacun avec son sujet (contre le renvoi en comité ≠ contre le projet)
    k = par_elu["Thomas H. Kean"]
    assert k["cle"] == "chambre:NJ07"
    assert [(v["numero"], v["sujet"], v["vote_fr"]) for v in k["votes_hr7008"]] == [
        ("279", "motion de renvoi en comité (procédure)", "contre"), ("280", "adoption du projet de loi", "pour")]


def test_lien_pas_sur_rien_plutot_que_faux():
    infos = [e for e in vraies_infos() if e["source"] == "chambre_ptr"][:1]
    autre = copy.deepcopy(infos[0])
    autre["data"]["elu"], autre["data"]["circonscription"] = "Kevin Hern", "NJ07"  # nom et circonscription en désaccord
    assert cg.relier_elus([autre], congres_officiel(), {}) == {}
    assert cg.relier_elus(infos, {}, {}) == {}  # listes pas encore lues : personne


# ---------- Score : les chefs ----------

def test_achat_d_un_chef_vaut_2_points_et_sa_vente_moins_1():
    infos = vraies_infos()
    achat = next(e for e in infos if e["source"] == "senat_ptr" and e["kind"] == "achat_elu")
    vente = next(e for e in infos if e["source"] == "senat_ptr" and e["kind"] == "vente_elu")
    for e, ordinaire, chef in ((achat, "achat_elu", "achat_chef"), (vente, None, "vente_chef")):
        assert sc.evaluer(e)[0].regle == ordinaire
        assert sc.evaluer(e, chefs=frozenset({e["data"]["elu"]}))[0].regle == chef
    assert (sc.REGLES["achat_chef"]["points"], sc.REGLES["vente_chef"]["points"]) == (2.0, -1.0)


def test_option_de_vente_achetee_par_un_chef_reste_sans_points():
    infos = vraies_infos()
    e = copy.deepcopy(next(x for x in infos if x["source"] == "senat_ptr" and x["kind"] == "vente_elu"))
    e["kind"], e["direction"] = "achat_elu_option", -1  # achat d'options de vente : pas une vente d'actions
    assert sc.evaluer(e, chefs=frozenset({e["data"]["elu"]}))[0].regle is None


def test_un_chef_relie_par_les_listes_officielles_recoit_le_bonus():
    # Transaction FICTIVE (test seulement) : le rapport réel de John Boozman, attribué à John Thune (chef au Sénat).
    infos = vraies_infos()
    e = copy.deepcopy(next(x for x in infos if x["source"] == "senat_ptr" and x["data"]["elu"] == "John Boozman"
                           and x["kind"] == "achat_elu"))
    e["id"], e["data"]["elu"] = "fictif-thune", "John Thune"
    par_elu = cg.relier_elus([e], congres_officiel(), votes_officiels())
    assert par_elu["John Thune"]["chef"] == {"poste": "chef de parti", "titre": "Senate Majority Leader"}
    chefs = {n for n, i in par_elu.items() if i["chef"]}
    lendemain = datetime(2026, 9, 12, 16, tzinfo=timezone.utc)  # publié le 11 septembre
    assert sc.calculer([e], lendemain)["hausse"] == []  # élu ordinaire : 1 point, sous le seuil de 1,5
    r = sc.calculer([e], lendemain, chefs=chefs)
    assert [x["symbole"] for x in r["hausse"]] == ["FSLR"] and r["hausse"][0]["score"] == round(2 * 0.5 ** (1 / 30), 2)
    assert r["hausse"][0]["groupes"][0]["infos"][0]["regle"] == "achat_chef"


# ---------- Publication ----------

def test_publication_du_fichier_des_elus(tmp_path):
    ctx = contexte(tmp_path)
    cg.collecter_comites(ctx)
    cg.collecter_hr7008(ctx)
    cg.collecter_votes(ctx)
    (tmp_path / "evenements").mkdir(exist_ok=True)
    (tmp_path / "evenements" / "2026-10.jsonl").write_bytes(gzip.decompress(
        (F / "score" / "evenements_20261003.jsonl.gz").read_bytes()))
    executer(tmp_path, collecteurs={}, maintenant=MAINTENANT)
    elus = json.loads((tmp_path / "app" / "elus.json").read_text(encoding="utf-8"))
    assert len(elus["par_elu"]) == 14 and len(elus["chefs"]) == 12
    assert elus["projet"]["etape"] == "bloqué au Sénat (clôture rejetée, 53 pour, 47 contre, 60 voix requises)"
    assert [(v["numero"], v["phrase"], v["oui"], v["non"]) for v in elus["projet"]["votes"]] == [
        ("279", "la Chambre rejette la motion de renvoi en comité (procédure)", 211, 218),
        ("280", "la Chambre adopte le projet de loi", 232, 198),
        ("253", "le Sénat rejette la clôture (60 voix requises pour ouvrir le débat)", 53, 47)]
    assert json.loads((tmp_path / "app" / "aujourdhui.json").read_text(encoding="utf-8"))["version"] == sc.VERSION


def test_sans_les_listes_du_congres_l_app_recoit_des_listes_vides(tmp_path):
    (tmp_path / "evenements").mkdir()
    (tmp_path / "evenements" / "2026-10.jsonl").write_bytes(gzip.decompress(
        (F / "score" / "evenements_20261003.jsonl.gz").read_bytes()))
    executer(tmp_path, collecteurs={}, maintenant=MAINTENANT)
    elus = json.loads((tmp_path / "app" / "elus.json").read_text(encoding="utf-8"))
    assert elus == {"par_elu": {}, "chefs": [], "listes_lues": None, "projet": None}
