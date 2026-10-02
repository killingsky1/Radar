from radar.models import CATEGORIES
from radar.registry import PASSAGES, SOURCES
from radar.validate import domaine_officiel


def test_chaque_source_est_coherente():
    for s in SOURCES.values():
        assert s.categorie in CATEGORIES, s.id
        assert s.domaines, s.id
        assert domaine_officiel(s.site, s.domaines), f"{s.id} : le lien du site n'est pas sur ses domaines"
        assert set(s.passages) <= set(PASSAGES), s.id
        assert s.attente_heures > 0, s.id


def test_sources_ecartees_ont_une_raison_et_aucune_phase():
    for s in SOURCES.values():
        if s.ecartee:
            assert s.phase == 0 and len(s.ecartee) > 5, s.id
        else:
            assert 1 <= s.phase <= 5, s.id
