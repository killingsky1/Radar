"""Lot 3c, livraison 1, sur de VRAIES pages officielles lues le 3 octobre 2026 (tests/fixtures/canada3c) :
Bureau de la concurrence, sanctions canadiennes, Statistique Canada, Gazette du Canada (règlements et projets
d'intérêt national), LEGISinfo."""

import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from radar.collecteurs import canada_eco as ce
from radar.collecteurs import gazette as g
from radar.collecteurs import legisinfo as li
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import Contexte, executer
from radar.score import evaluer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "canada3c"
SEC = Path(__file__).parent / "fixtures" / "sec" / "company_tickers_exchange_complet.json.gz"
PAGES = json.loads((F / "pages.json").read_text(encoding="utf-8"))
MAINTENANT = datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc)
JOUR = date(2026, 10, 3)


def lu(url):
    return gzip.decompress((F / PAGES[url]).read_bytes())


class FauxInternet:
    def __init__(self, remplacements=None):
        self.appels = []
        self.remplacements = remplacements or {}

    def get(self, url):
        self.appels.append(url)
        if url in self.remplacements:
            c = self.remplacements[url]
        elif url == "https://www.sec.gov/files/company_tickers_exchange.json":
            c = gzip.decompress(SEC.read_bytes())
        elif url in PAGES:
            c = lu(url)
        else:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def contexte(tmp_path, internet=None, quand=MAINTENANT):
    return Contexte(client=internet or FauxInternet(), maintenant=quand, donnees=tmp_path)


def par_id(evs, ident):
    return next(e for e in evs if e.official_id == ident)


# ---------- Bureau de la concurrence ----------

def test_concurrence_tableau_officiel_lu_au_complet():
    page = lu(ce.CONCURRENCE).decode("utf-8")
    lignes = ce.lire_examens(page)
    assert len(lignes) == 833 and g.date_modifiee(page) == "2026-09-29"  # + 1 ligne d'en-tête (th)
    codes = {x["code"] for x in lignes}
    assert codes <= set(ce.RESULTATS) | {ce.EN_COURS}, codes  # aucun code inconnu dans le vrai rapport
    assert sum(x["conclusion"] == ce.EN_COURS for x in lignes) == 48


def test_concurrence_parties_acquereur_et_cibles():
    assert ce.parties("Nordic Capital Epsilon SCA SICAV RAIF / BWXT Medical Ltd, Kinectrics Inc et Kinectrics Kipling Inc") \
        == ("Nordic Capital Epsilon SCA SICAV RAIF", ["BWXT Medical Ltd", "Kinectrics Inc", "Kinectrics Kipling Inc"])
    assert ce.parties("Henset Capital Inc. / FCR (Hazelton) LP, First Capital Holdings (Ontario) Corporation , et "
                      "The Hazelton Food Services Partnership")[1] == [
        "FCR (Hazelton) LP", "First Capital Holdings (Ontario) Corporation", "The Hazelton Food Services Partnership"]


def test_concurrence_30_jours_symboles_exacts_sans_points(tmp_path):
    evs = ce.collecter_concurrence(contexte(tmp_path))
    assert len(evs) == 39
    amd = par_id(evs, "2026-08-10:advanced-micro-devices-inc-taalas-inc:conclu")
    valider(amd, JOUR)
    assert amd.badge == "officiel", amd.checks
    assert amd.title == ("Bureau de la concurrence : examen de fusion conclu (lettre de non-intervention), "
                         "Advanced Micro Devices Inc / Taalas Inc")
    assert (amd.tickers, amd.occurred_on, amd.published_on) == (["AMD"], "2026-09-21", "2026-09-29")
    olin = next(e for e in evs if e.data["acquereur"] == "Olin Corporation")
    assert olin.kind == "fusion_examen_ouvert" and olin.tickers == ["OLN", "HUN"] and olin.occurred_on == "2026-09-18"
    # Filiale canadienne : pas rattachée à la mère cotée (rien n'est deviné)
    assert next(e for e in evs if e.data["acquereur"] == "Lockheed Martin Canada Inc").tickers == []
    assert [a.regle for a in evaluer(amd.to_dict())] == [None]  # contexte seulement, 0 point
    assert "Bureau de la concurrence" in evaluer(amd.to_dict())[0].pourquoi


def test_concurrence_code_inconnu_va_a_verifier():
    x = {"parties": "A Inc / B Inc", "debut": "2026-09-01", "conclusion": "2026-09-20", "scian": "5415", "code": "ZZZ"}
    ev = valider(ce.evenements_examen(x, "2026-09-29")[0], JOUR)
    assert ev.badge == "a_verifier" and ev.checks["resultat_officiel_connu"] is False


# ---------- Sanctions canadiennes ----------

def test_sanctions_liste_complete_et_regime_en_francais():
    inscriptions = ce.lire_sanctions(lu(ce.SANCTIONS_XML))
    assert len(inscriptions) == 5707
    assert ce.regime("Russia / Russie") == "Russie" and ce.regime("Myanmar (Burma) / Myanmar (Birmanie)") == "Myanmar (Birmanie)"


def test_sanctions_inscriptions_groupees_par_jour_et_regime(tmp_path):
    evs = ce.collecter_sanctions(contexte(tmp_path))
    assert [e.official_id for e in evs] == ["2026-09-04:russie", "2026-09-22:iran"]
    iran = valider(evs[1], JOUR)
    assert iran.badge == "officiel", iran.checks
    assert iran.title == "Sanctions canadiennes (Iran) : 10 nouvelle(s) inscription(s)"
    assert len(iran.data["entites"]) == 5 and len(iran.data["personnes"]) == 5 and "Douran Group" in iran.data["entites"]
    assert iran.official_url.endswith("consolidated-consolide.aspx?lang=fra")
    assert evs[0].data["resume"] == "8 inscription(s) le 4 septembre 2026 : 8 personne(s)."


def test_sanctions_liste_presque_vide_met_la_source_en_panne(tmp_path):
    petit = b"<data-set><record><Country-Pays>Iran</Country-Pays></record></data-set>"
    with pytest.raises(RuntimeError, match="incomplète"):
        ce.collecter_sanctions(contexte(tmp_path, FauxInternet({ce.SANCTIONS_XML: petit})))


# ---------- Statistique Canada ----------

def test_statcan_liste_officielle_des_28_grands_indicateurs():
    noms = ce.lire_principaux(lu(ce.PRINCIPAUX).decode("utf-8"))
    assert len(noms) == 28 and "Indice des prix à la consommation" in noms and "Enquête sur la population active" in noms


def test_statcan_seulement_les_grands_indicateurs(tmp_path):
    evs = ce.collecter_statcan(contexte(tmp_path))
    assert len(evs) == 19  # 30 derniers jours ; 52 sur 271 annonces en 100 jours
    ipc = par_id(evs, "260914/dq260914a")
    valider(ipc, JOUR)
    assert ipc.badge == "officiel", ipc.checks
    assert ipc.title == "Statistique Canada : Indice des prix à la consommation, août 2026"
    assert (ipc.published_on, ipc.data["indicateur"], ipc.data["periode"]) == ("2026-09-14", "Indice des prix à la consommation", "août 2026")
    assert ipc.data["resume"]
    titres = {e.title for e in evs}
    assert not any("indicateur avancé" in t for t in titres)  # pas dans la liste officielle


def test_statcan_le_nom_le_plus_long_gagne():
    noms = ["Produit intérieur brut par industrie", "Produit intérieur brut par industrie : provinces et territoires"]
    assert ce.indicateur("Produit intérieur brut par industrie : provinces et territoires, 2025", noms) == noms[1]
    assert ce.indicateur("Produit intérieur brut par industrie, juillet 2026", noms) == noms[0]
    assert ce.indicateur("Commerce de gros : indicateur avancé, août 2026", ["Commerce de gros"]) is None


# ---------- Gazette du Canada ----------

def test_gazette_fil_officiel_numeros_et_editions_speciales():
    p2 = [n for n in g.liens_du_fil(lu(g.FILS["p2"])) if n["jour"] >= "2026-07-05"]
    assert [n["jour"] for n in p2] == ["2026-09-23", "2026-09-09", "2026-08-26", "2026-08-12", "2026-07-29", "2026-07-15"]
    assert all(n["page"] == "index" for n in p2)  # l'index codifié trimestriel (-c2) est écarté
    p1 = [n for n in g.liens_du_fil(lu(g.FILS["p1"])) if n["jour"] >= "2026-07-05"]
    assert len(p1) == 15 and sum(n["speciale"] for n in p1) == 2


def test_gazette_index_et_page_officielle_d_un_texte():
    idx = g.lire_index_p2(lu("https://gazette.gc.ca/rp-pr/p2/2026/2026-09-23/html/index-fra.html").decode("utf-8", "replace"))
    assert len(idx) == 10
    erratum = next(x for x in idx if x["numero"] == "DORS/2026-154")
    assert erratum["erratum"] and erratum["loi"] == "Tarif des douanes"
    t = g.lire_texte(lu("https://gazette.gc.ca/rp-pr/p2/2026/2026-09-23/html/sor-dors186-fra.html").decode("utf-8", "replace"))
    assert (t["titre"], t["numero"], t["enregistre_le"], t["loi_page"]) == (
        "Décret imposant une surtaxe aux États-Unis (2026)", "DORS/2026-186", "2026-09-04", "TARIF DES DOUANES")
    assert t["cp"] == "C.P. 2026-785 Le 4 septembre 2026" and t["enjeux"].startswith("Le 22 août 2026, les États-Unis")
    assert t["enjeux"].endswith("touchées par les droits de douane américains.")  # le paragraphe au complet
    assert g.extrait("Une phrase. " * 100).endswith("Une phrase. […]") and len(g.extrait("Une phrase. " * 100)) < 910


def test_gazette_lien_brise_du_fil_page_404_renvoyee_avec_le_code_200():
    page = lu("https://gazette.gc.ca/rp-pr/p1/2026/2026-08-24-x7/html/extra6-fra.html").decode("utf-8", "replace")
    assert g.contenu_principal(page) is None


def test_gazette_et_projets_au_complet(tmp_path):
    internet = FauxInternet()
    ctx = contexte(tmp_path, internet)
    regl, proj = g.collecter_reglements(ctx), g.collecter_projets(ctx)
    assert sorted(e.official_id for e in regl) == ["DORS/2026-169", "DORS/2026-172", "DORS/2026-173", "DORS/2026-178",
                                                   "DORS/2026-179", "DORS/2026-186", "DORS/2026-187", "DORS/2026-188",
                                                   "TR/2026-34"]
    for e in regl + proj:
        valider(e, JOUR)
        assert e.badge == "officiel", (e.official_id, e.checks)
    surtaxe = par_id(regl, "DORS/2026-186")
    assert surtaxe.title == "Gazette du Canada : Décret imposant une surtaxe aux États-Unis (2026) (DORS/2026-186)"
    assert (surtaxe.occurred_on, surtaxe.published_on, surtaxe.data["loi"]) == ("2026-09-04", "2026-09-23", "Tarif des douanes")
    assert surtaxe.official_url == "https://gazette.gc.ca/rp-pr/p2/2026/2026-09-23/html/sor-dors186-fra.html"
    assert [e.official_id for e in proj] == ["avis:2026-08-01:sup1", "avis:2026-08-29:nb2", "avis:2026-08-29:nb3",
                                             "avis:2026-09-19:ne2"]
    oleoduc = proj[0]
    assert oleoduc.title == "Projet d'intérêt national : avis d'inscription possible, Oléoduc pétrolier de la côte ouest"
    assert "afin d’inscrire l’oléoduc pétrolier de la côte Ouest" in oleoduc.data["texte"]
    assert all(e.kind == "avis_projet" for e in proj)  # 1re lecture : la liste du Bureau est notée, sans info
    lus = json.loads((tmp_path / "gazette" / "lus.json").read_text(encoding="utf-8"))
    assert len(lus) == 21 and sum(v["retenus"] for v in lus.values()) == 13
    assert "lien brisé" in lus["https://gazette.gc.ca/rp-pr/p1/2026/2026-08-24-x7/html/extra6-fra.html"]["note"]
    assert len(json.loads((tmp_path / "gazette" / "grands_projets.json").read_text(encoding="utf-8"))) == 18


def test_gazette_numeros_lus_une_seule_fois(tmp_path):
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT,
                       collecteurs={"gazette_ca": g.collecter_reglements, "grands_projets_ca": g.collecter_projets})
    assert (rapport["gazette_ca"]["nouveaux"], rapport["grands_projets_ca"]["nouveaux"]) == (9, 4), rapport
    internet = FauxInternet()
    rapport = executer(tmp_path, client=internet, maintenant=MAINTENANT,
                       collecteurs={"gazette_ca": g.collecter_reglements, "grands_projets_ca": g.collecter_projets})
    assert rapport["gazette_ca"].get("nouveaux", 0) == 0 and rapport["grands_projets_ca"].get("nouveaux", 0) == 0
    assert sorted(internet.appels) == sorted([g.FILS["p1"], g.FILS["p2"], g.BGP_LISTE])  # les 2 fils et la liste


def test_gazette_une_seule_des_2_sources_ne_fait_rien_perdre(tmp_path):
    executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT, collecteurs={"gazette_ca": g.collecter_reglements})
    assert not (tmp_path / "gazette" / "lus.json").exists()  # numéros pas notés « lus » : l'autre source les relira
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT,
                       collecteurs={"gazette_ca": g.collecter_reglements, "grands_projets_ca": g.collecter_projets})
    assert rapport["grands_projets_ca"]["nouveaux"] == 4 and rapport["gazette_ca"].get("nouveaux", 0) == 0


def test_nouveau_projet_du_bureau_des_grands_projets(tmp_path):
    executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT,
             collecteurs={"gazette_ca": g.collecter_reglements, "grands_projets_ca": g.collecter_projets})
    chemin = tmp_path / "gazette" / "grands_projets.json"
    connus = json.loads(chemin.read_text(encoding="utf-8"))
    oublie = "/fr/conseil-prive/bureau-grands-projets/projets/national/ouest.html"
    del connus[oublie]
    chemin.write_text(json.dumps(connus), encoding="utf-8")
    ctx = contexte(tmp_path)
    assert g.collecter_reglements(ctx) == []
    nouveaux = g.collecter_projets(ctx)
    assert [e.official_id for e in nouveaux] == ["bgp:ouest"]
    e = valider(nouveaux[0], JOUR)
    assert e.badge == "officiel", e.checks
    assert e.title == "Bureau des grands projets : nouveau projet soutenu, Oléoduc pétrolier de la côte ouest"  # tel qu'écrit
    assert e.published_on == "2026-07-16"  # « Date de modification » de la page officielle
    assert e.data["promoteur"] == "Gouvernement de l'Alberta"  # apostrophe droite sur la page officielle


def test_gazette_texte_illisible_met_la_source_en_panne(tmp_path):
    casse = {"https://gazette.gc.ca/rp-pr/p2/2026/2026-09-23/html/sor-dors186-fra.html": b"<html><main>?</main></html>"}
    rapport = executer(tmp_path, client=FauxInternet(casse), maintenant=MAINTENANT,
                       collecteurs={"gazette_ca": g.collecter_reglements, "grands_projets_ca": g.collecter_projets})
    assert rapport["gazette_ca"]["ok"] is False and "illisible" in rapport["gazette_ca"]["erreur"]
    assert not (tmp_path / "gazette" / "lus.json").exists()  # rien n'est noté « lu » : tout sera relu


def test_gazette_loi_hors_liste_et_errata_ecartes():
    assert g.ARGENT.search(g.norme("Licences d’exportation et d’importation (Loi sur les)"))
    assert g.ARGENT.search(g.norme("LOI SUR LES MESURES ÉCONOMIQUES SPÉCIALES"))
    assert not g.ARGENT.search(g.norme("Protection de l’environnement (1999) (Loi canadienne sur la)"))
    assert not g.ARGENT.search(g.norme("Autorité autre que statutaire"))
    assert g.BATIR.search(g.norme("LOI VISANT À BÂTIR LE CANADA"))


# ---------- LEGISinfo ----------

def test_legisinfo_projets_du_gouvernement_seulement():
    projets = json.loads(lu(li.LISTE).decode("utf-8-sig"))
    assert len(projets) == 188 and sum(li.du_gouvernement(p) for p in projets) == 44


def test_legisinfo_etapes_des_30_derniers_jours(tmp_path):
    evs = li.collecter(contexte(tmp_path))
    assert sorted(e.official_id for e in evs) == ["45-1:C-10:chambre-3", "45-1:C-10:senat-1", "45-1:C-27:senat-2",
                                                  "45-1:C-38:chambre-1", "45-1:C-38:chambre-2", "45-1:C-39:chambre-1"]
    c10 = valider(par_id(evs, "45-1:C-10:chambre-3"), JOUR)
    assert c10.badge == "officiel", c10.checks
    assert c10.title == ("Projet de loi C-10 (Loi sur le commissaire à la mise en œuvre des traités modernes) : "
                         "adopté en troisième lecture à la Chambre des communes")
    assert c10.published_on == "2026-09-21" and c10.official_url == "https://www.parl.ca/legisinfo/fr/projet-de-loi/45-1/c-10"


def test_legisinfo_date_selon_l_heure_de_l_est():
    assert li.jour("2026-03-12T06:14:57.98-04:00") == "2026-03-12"
    assert li.jour("2026-03-13T02:30:00+00:00") == "2026-03-12"  # 22 h 30 à Ottawa la veille
    assert li.jour("0001-01-01T00:00:00") is None and li.jour(None) is None


def test_legisinfo_session_terminee_met_la_source_en_panne(tmp_path):
    projets = json.loads(lu(li.LISTE).decode("utf-8-sig"))
    finie = json.dumps([dict(p, IsSessionOngoing=False) for p in projets]).encode()
    with pytest.raises(RuntimeError, match="session"):
        li.collecter(contexte(tmp_path, FauxInternet({li.LISTE: finie})))


# ---------- Les 6 lecteurs ensemble ----------

def test_les_6_lecteurs_ensemble_sans_doublon(tmp_path):
    from radar.collecteurs import COLLECTEURS
    six = {s: COLLECTEURS[s] for s in ("concurrence_ca", "sanctions_ca", "statcan", "gazette_ca", "grands_projets_ca",
                                        "legisinfo")}
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT, collecteurs=six)
    assert {s: rapport[s]["nouveaux"] for s in six} == {"concurrence_ca": 39, "sanctions_ca": 2, "statcan": 19,
                                                         "gazette_ca": 9, "grands_projets_ca": 4, "legisinfo": 6}, rapport
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert {e["badge"] for e in fil if e["source"] in six} == {"officiel"}
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT, collecteurs=six)
    assert all(rapport[s].get("nouveaux", 0) == 0 for s in six), rapport
