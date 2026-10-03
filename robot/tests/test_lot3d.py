"""Lot 3d, livraison 1, sur de VRAIES données officielles lues le 3 octobre 2026 vers 19 h 15 UTC (tests/fixtures/lot3d) :
Trésor américain (Fiscal Data : adjudications, état mensuel, calendrier) et douane américaine (flux CSMS)."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from radar.collecteurs import douane, tresor
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import Contexte, executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "lot3d"
PAGES = json.loads((F / "pages.json").read_text(encoding="utf-8"))
MAINTENANT = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


def lu(url):
    return gzip.decompress((F / PAGES[url]).read_bytes())


class FauxInternet:
    def __init__(self, remplacements=None):
        self.remplacements = remplacements or {}
        self.appels = []

    def get(self, url):
        self.appels.append(url)
        if url in self.remplacements:
            c = self.remplacements[url]
        elif url in PAGES:
            c = lu(url)
        else:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def contexte(tmp_path, internet=None, quand=MAINTENANT):
    return Contexte(client=internet or FauxInternet(), maintenant=quand, donnees=tmp_path)


def adjudications():
    return json.loads(lu(tresor.ADJUDICATIONS))["data"]


# ---------- Trésor : adjudications ----------

def test_tresor_les_obligations_des_10_derniers_jours_avec_leurs_resultats(tmp_path):
    evs = [e for e in tresor.collecter(contexte(tmp_path)) if e.kind == "adjudication"]
    assert [(e.occurred_on, e.data["terme"], e.data["sorte"]) for e in evs] == [
        ("2026-09-24", "7-Year", "nominale"), ("2026-09-23", "5-Year", "nominale"),
        ("2026-09-23", "1-Year 10-Month", "FRN")]
    sept = valider(evs[0], MAINTENANT.date())
    assert sept.badge == "officiel", sept.checks
    assert sept.title == "Trésor américain : adjudication de 44 G$ sur 7 ans à 5,085 % (demande : 2,42 fois l'offre)"
    assert sept.official_url == ("https://fiscaldata.treasury.gov/static-data/published-reports/auctions-query/results/"
                                 "R_20260924_3.pdf")
    assert (sept.published_on, sept.amount_min, sept.currency) == ("2026-09-24", 44e9, "USD")
    d = dict(sept.data["details"])
    assert d["Demande / offre"] == "2,42 (moyenne des 6 précédentes : 2,49)"
    assert d["Acheteurs indirects"] == "57,2 % (moyenne des 6 précédentes : 64,6 %)"
    assert (d["Acheteurs directs"], d["Courtiers primaires"]) == ("30,3 %", "12,5 %")
    assert [p["adjudication"] for p in sept.data["precedentes"]] == [
        "2026-08-27", "2026-07-28", "2026-06-25", "2026-05-28", "2026-04-28", "2026-03-26"]
    frn = valider(evs[2], MAINTENANT.date())
    assert frn.badge == "officiel", frn.checks
    assert frn.title == ("Trésor américain : adjudication de 28 G$ à taux variable sur 1 an et 10 mois (réouverture), "
                         "marge de 0,040 % (demande : 2,63 fois l'offre)")


def test_tresor_les_3_categories_d_acheteurs_font_le_total_sur_tout_l_historique():
    """Le contrôle « parts qui s'additionnent » ne doit jamais rater sur de vrais résultats (300 adjudications)."""
    avec = [x for x in adjudications() if tresor.resultat(x)]
    assert len(avec) > 250
    for x in avec:
        somme = sum(tresor.nombre(x[f"{k}_accepted"]) or 0 for k in ("indirect_bidder", "direct_bidder", "primary_dealer"))
        assert abs(somme - tresor.nombre(x["comp_accepted"])) < 1, x["cusip"]


@pytest.mark.parametrize("terme, sorte, attendu", [
    ({"security_term": "29-Year 10-Month"}, {}, ("nominale", 30)),
    ({"security_term": "9-Year 8-Month"}, {"inflation_index_security": "Yes"}, ("TIPS", 10)),
    ({"security_term": "1-Year 11-Month"}, {"floating_rate": "Yes"}, ("FRN", 2)),
    ({"security_term": "2-Year"}, {}, ("nominale", 2)),
])
def test_tresor_duree_de_reference_des_reouvertures(terme, sorte, attendu):
    assert tresor.famille({**terme, **sorte}) == attendu


def test_tresor_montants_et_durees_en_francais():
    assert [tresor.milliards(v) for v in (44e9, 22.5e9, 125.25e9)] == ["44 G$", "22,5 G$", "125,25 G$"]
    assert tresor.milliards(166_796_952_277.38, 1) == "166,8 G$"
    assert [tresor.duree_texte(t) for t in ("1-Year", "7-Year", "29-Year 10-Month")] == ["1 an", "7 ans",
                                                                                      "29 ans et 10 mois"]


def test_tresor_liste_figee_met_la_source_en_panne(tmp_path):
    vieux = contexte(tmp_path, quand=MAINTENANT + timedelta(days=30))  # rien de récent dans la liste : figée
    with pytest.raises(RuntimeError, match="figée"):
        tresor.collecter(vieux)


# ---------- Trésor : état mensuel ----------

def test_tresor_etat_mensuel_1re_lecture_silencieuse_puis_nouveau_mois(tmp_path):
    assert all(e.kind == "adjudication" for e in tresor.collecter(contexte(tmp_path)))
    etat = tresor.chemin_etat(tmp_path)
    assert json.loads(etat.read_text()) == {"etat_mensuel": "2026-08-31"}
    # Comme si Radar avait vu juillet : août (vrais chiffres de la publication) devient une info
    etat.write_text(json.dumps({"etat_mensuel": "2026-07-31"}))
    mois = [e for e in tresor.collecter(contexte(tmp_path)) if e.kind == "solde_mensuel"]
    assert len(mois) == 1
    e = valider(mois[0], MAINTENANT.date())
    assert e.badge == "officiel", e.checks
    assert e.title == "Trésor américain : déficit de 166,8 G$ en août 2026 (recettes 360 G$, dépenses 526,8 G$)"
    assert (e.occurred_on, e.published_on, e.official_id) == ("2026-08-31", "2026-10-03", "mts:2026-08")
    assert any("au plus tard" in n for n in e.notes)  # pas de date passée dans le calendrier officiel
    d = dict(e.data["details"])
    assert d["Cumul de l'exercice 2026"] == "Déficit de 1 965,6 G$"
    assert d["Même mois, exercice 2025"] == "Déficit de 344,8 G$"
    assert json.loads(etat.read_text()) == {"etat_mensuel": "2026-08-31"}


def test_tresor_date_officielle_du_calendrier_si_elle_existe():
    cal = [{"datasetId": tresor.ID_MTS, "date": "2026-09-11", "time": "18:00", "released": "true"},
           {"datasetId": tresor.ID_MTS, "date": "2026-11-12", "time": "19:00", "released": "false"}]
    assert tresor.date_de_publication(cal, "2026-08-31", "2026-10-03") == "2026-09-11"
    assert tresor.date_de_publication(cal, "2026-09-30", "2026-10-03") is None


# ---------- Douane : messages CSMS ----------

def test_douane_les_8_messages_sur_les_surtaxes_et_rien_d_autre(tmp_path):
    evs = douane.collecter(contexte(tmp_path))
    assert [e.official_id for e in evs] == ["70054007", "70050970", "69994928", "69990649", "69851916", "69738151",
                                            "69606660", "69415934"]
    tous = douane.lire_flux(lu(douane.FLUX))
    assert len(tous) == 100
    # Exemples écartés : technique (codes d'erreur) même s'il parle d'IEEPA, contingents, maintenance
    ecartes = {x["numero"] for x in tous} - {e.official_id for e in evs}
    assert {"69635410", "70023767", "70087229"} <= ecartes
    for e in evs:
        assert valider(e, MAINTENANT.date()).badge == "officiel", (e.official_id, e.checks)


def test_douane_details_d_un_vrai_message(tmp_path):
    evs = {e.official_id: e for e in douane.collecter(contexte(tmp_path))}
    pharma = evs["70054007"]
    assert pharma.title == ("Douane américaine : UPDATED GUIDANCE: Section 232 Duties on Imports of Pharmaceutical "
                            "Articles and Ingredients")
    assert pharma.official_url == "https://content.govdelivery.com/accounts/USDHSCBP/bulletins/42cf077"
    assert (pharma.occurred_on, pharma.published_on) == ("2026-09-28", "2026-09-28")
    d = dict(pharma.data["details"])
    assert d["Envoyé"] == "28 septembre 2026 à 17 h 42 (heure de New York)"
    assert d["Proclamations citées"] == "11020"
    assert d["Numéros du tarif cités (chapitre 99)"].startswith("9903.04.60, 9903.04.61")
    assert d["Extrait"].startswith("This message provides updated guidance regarding the implementation of "
                                   "Proclamation 11020")
    canada = evs["70050970"]
    assert canada.data["proclamations"][:3] == ["11061", "11062", "11063"]


def test_douane_texte_sans_mots_coupes():
    assert douane.texte_message("<p>to remov<span>e</span> the <a href='x'>suspension</a></p><p>Next</p>") == \
        "to remove the suspension Next"


def test_douane_flux_fige_met_la_source_en_panne(tmp_path):
    with pytest.raises(RuntimeError, match="figé"):
        douane.collecter(contexte(tmp_path, quand=MAINTENANT + timedelta(days=30)))


# ---------- Les 2 lecteurs ensemble ----------

def test_tresor_et_douane_ensemble_sans_doublon(tmp_path):
    from radar.collecteurs import COLLECTEURS
    deux = {s: COLLECTEURS[s] for s in ("tresor", "tarifs")}
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT, collecteurs=deux)
    assert {s: rapport[s]["nouveaux"] for s in deux} == {"tresor": 3, "tarifs": 8}, rapport
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=MAINTENANT, collecteurs=deux)
    assert all(rapport[s].get("nouveaux", 0) == 0 for s in deux), rapport
