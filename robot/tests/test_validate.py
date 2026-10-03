from datetime import date

import pytest

from conftest import SOURCE_GENERIQUE, bonne_info, confirmation_pentagone
from radar import validate
from radar.models import Confirmation, empreinte
from radar.validate import delai_depasse, jours_ouvrables, valider


def test_bonne_info_est_officielle(aujourd_hui):
    ev = valider(bonne_info(), aujourd_hui)
    assert ev.badge == "officiel"
    assert all(ev.checks.values())


def test_confirmee_par_une_autre_source_officielle(aujourd_hui):
    ev = valider(bonne_info(confirmations=[confirmation_pentagone()]), aujourd_hui)
    assert ev.badge == "confirme"


PIEGES = [
    ("site non officiel", dict(official_url="https://www.capitoltrades.com/trades/1"), "domaine_officiel"),
    ("http au lieu de https", dict(official_url="http://www.sec.gov/x"), "domaine_officiel"),
    ("faux domaine qui ressemble", dict(official_url="https://sec.gov.faux-site.com/x"), "domaine_officiel"),
    ("date dans le futur", dict(published_on="2026-12-25"), "dates_coherentes"),
    ("action après la publication", dict(occurred_on="2026-10-01", published_on="2026-09-30"), "dates_coherentes"),
    ("date illisible", dict(occurred_on="28/09/2026"), "dates_coherentes"),
    ("montant à l'envers", dict(amount_min=50000.0, amount_max=1000.0), "montant_coherent"),
    ("montant négatif", dict(amount_min=-5.0, amount_max=10.0), "montant_coherent"),
    ("empreinte invalide", dict(sha256="abc"), "empreinte"),
    ("symbole invalide", dict(tickers=["APPLE INC"]), "symboles_valides"),
    ("catégorie inconnue", dict(category="crypto"), "champs_requis"),
    ("numéro officiel manquant", dict(official_id=""), "champs_requis"),
    ("source inconnue", dict(source="blogue_random"), "source_connue"),
    ("source laissée de côté", dict(source="sedi", official_url="https://www.sedi.ca/x"), "source_connue"),
    ("source non officielle", dict(source="prix_yahoo", official_url="https://finance.yahoo.com/quote/AAPL"),
     "source_officielle"),
]


@pytest.mark.parametrize("nom,changements,controle", PIEGES, ids=[p[0] for p in PIEGES])
def test_piege_va_dans_a_verifier(nom, changements, controle, aujourd_hui):
    ev = valider(bonne_info(**changements), aujourd_hui)
    assert ev.badge == "a_verifier", nom
    assert ev.checks[controle] is False, nom


def test_une_source_ne_peut_pas_se_confirmer_elle_meme(aujourd_hui):
    soi_meme = Confirmation(SOURCE_GENERIQUE, "https://www.sec.gov/autre.xml", "0001234567-26-000002")
    ev = valider(bonne_info(confirmations=[soi_meme]), aujourd_hui)
    assert ev.badge == "a_verifier"
    assert ev.checks["confirmations_valides"] is False


def test_confirmation_sur_un_site_non_officiel_refusee(aujourd_hui):
    fausse = Confirmation("war_contrats", "https://www.blogue-defense.com/contrat", "x")
    ev = valider(bonne_info(confirmations=[fausse]), aujourd_hui)
    assert ev.badge == "a_verifier"


def test_controle_de_source_rate(aujourd_hui, monkeypatch):
    monkeypatch.setitem(validate.CONTROLES_SOURCE, SOURCE_GENERIQUE, [lambda ev: {"code_P_achat_reel": False}])
    ev = valider(bonne_info(), aujourd_hui)
    assert ev.badge == "a_verifier"
    assert ev.checks["code_P_achat_reel"] is False


def test_controle_qui_plante_compte_comme_un_echec(aujourd_hui, monkeypatch):
    def plante(ev):
        raise ValueError("format inattendu")

    monkeypatch.setitem(validate.CONTROLES_SOURCE, SOURCE_GENERIQUE, [plante])
    ev = valider(bonne_info(), aujourd_hui)
    assert ev.badge == "a_verifier"
    assert ev.checks["controle_plante"] is False


def test_jours_ouvrables_sautent_la_fin_de_semaine():
    vendredi, mardi = date(2026, 9, 25), date(2026, 9, 29)
    assert jours_ouvrables(vendredi, mardi) == 2


def test_delai_legal_du_formulaire_4():
    # Achat un vendredi : déposé le mardi = à temps (2 jours ouvrables), le mercredi = en retard.
    a_temps = bonne_info(occurred_on="2026-09-25", published_on="2026-09-29")
    en_retard = bonne_info(occurred_on="2026-09-25", published_on="2026-09-30")
    assert not delai_depasse(a_temps, 2, ouvrables=True)
    assert delai_depasse(en_retard, 2, ouvrables=True)


def test_empreinte_est_stable():
    assert empreinte(b"abc") == empreinte(b"abc")
    assert empreinte(b"abc") != empreinte(b"abd")
