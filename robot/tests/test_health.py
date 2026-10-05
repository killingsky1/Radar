from datetime import datetime, timezone

from radar.health import statut

MAINTENANT = datetime(2026, 10, 2, 16, 37, tzinfo=timezone.utc)


def test_source_pas_encore_branchee():
    assert statut("sec_blocage", None, branchee=False, maintenant=MAINTENANT)[0] == "a_venir"


def test_source_laissee_de_cote():
    code, raison = statut("sedi", None, branchee=False, maintenant=MAINTENANT)
    assert code == "ecartee" and "Payant" in raison


def test_lecture_recente_ok():
    etat = {"dernier_succes": "2026-10-02T11:07:00+00:00", "dernier_contenu": "2026-10-01"}
    assert statut("sec_form4", etat, True, MAINTENANT)[0] == "ok"


def test_pas_de_lecture_depuis_trop_longtemps():
    etat = {"dernier_succes": "2026-09-25T11:07:00+00:00"}
    assert statut("sec_form4", etat, True, MAINTENANT)[0] == "en_retard"


def test_erreurs_et_pas_de_succes_recent():
    etat = {"dernier_succes": "2026-09-25T11:07:00+00:00", "derniere_erreur": "HTTP 403"}
    code, raison = statut("sec_form4", etat, True, MAINTENANT)
    assert code == "en_panne" and "403" in raison


def test_jamais_reussi_et_erreur():
    assert statut("sec_form4", {"derniere_erreur": "HTTP 500"}, True, MAINTENANT)[0] == "en_panne"


def test_dernier_essai_rate_mais_succes_recent():
    etat = {"dernier_succes": "2026-10-02T11:07:00+00:00", "derniere_erreur": "HTTP 503"}
    code, raison = statut("sec_form4", etat, True, MAINTENANT)
    assert code == "ok" and "503" in raison


def test_source_qui_ne_publie_plus_est_en_pause():
    # Lecture OK, mais rien de nouveau depuis 10 jours (ex. fermeture du gouvernement)
    etat = {"dernier_succes": "2026-10-02T11:07:00+00:00", "dernier_contenu": "2026-09-22"}
    code, raison = statut("sec_form4", etat, True, MAINTENANT)
    assert code == "en_pause" and "10 jours" in raison


def test_pause_manuelle():
    etat = {"pause": True, "raison_pause": "Fermeture du gouvernement américain"}
    assert statut("cftc_cot", etat, True, MAINTENANT) == ("en_pause", "Fermeture du gouvernement américain")


def test_tresor_pas_en_pause_pendant_un_ecart_normal_entre_2_adjudications():
    """Mesuré sur Fiscal Data (recherche 29) : jusqu'à 19 jours entre 2 adjudications d'obligations depuis 2023. Le
    5 octobre 2026, 11 jours après celle du 24 septembre (les suivantes étaient annoncées du 6 au 8 octobre)."""
    maintenant = datetime(2026, 10, 5, 2, 12, tzinfo=timezone.utc)
    etat = {"dernier_succes": "2026-10-05T02:00:00+00:00", "dernier_contenu": "2026-09-24"}
    assert statut("tresor", etat, True, maintenant) == ("ok", "")
    etat["dernier_contenu"] = "2025-12-24"  # le plus long écart mesuré : 19 jours (12 janvier 2026)
    etat["dernier_succes"] = "2026-01-12T11:00:00+00:00"
    assert statut("tresor", etat, True, datetime(2026, 1, 12, 12, tzinfo=timezone.utc)) == ("ok", "")
    code, raison = statut("tresor", {**etat, "dernier_succes": "2026-01-16T11:00:00+00:00"}, True,
                          datetime(2026, 1, 16, 12, tzinfo=timezone.utc))
    assert code == "en_pause" and raison.startswith("Rien de publié depuis 23 jours")
