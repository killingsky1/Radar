"""Lot M : une compagnie de moins de 100 M$ en bourse n'entre pas dans la liste « hausse » (rejeu de 3 ans du labo).
Elle est gardée à part (« écartées ») et suivie dans les Résultats, pour vérifier la règle en vrai.
Sur les vrais formulaires 4 du lot L (PRHI, GME, FLNA, PAM, FUL) et les vrais prix de la SEC du lot G."""
import json
from datetime import datetime, timezone

from radar import resultats as rs
from radar import score as sc
from test_lotL import EVENEMENTS, MAINTENANT, evenement


def taille(valeur_m, t="moyenne"):
    return {"taille": t, "valeur_m": valeur_m}


def symboles(score, liste):
    return [r["symbole"] for r in score[liste]]


def test_sous_100_m_ecartee_100_pile_gardee_taille_inconnue_gardee():
    tailles = {"GME": taille(99.9), "FUL": taille(100.0), "PAM": {"taille": None, "raison": "compagnie étrangère"}}
    r = sc.calculer(EVENEMENTS, MAINTENANT, tailles=tailles)
    assert symboles(r, "ecartees") == ["GME"] and "GME" not in symboles(r, "hausse")
    assert "FUL" in symboles(r, "hausse") and "PAM" in symboles(r, "hausse")
    # Même note et mêmes preuves que si elle était gardée : seule la liste change
    gardee = sc.calculer(EVENEMENTS, MAINTENANT, tailles={**tailles, "GME": taille(100.0)})
    gme = next(x for x in gardee["hausse"] if x["symbole"] == "GME")
    assert r["ecartees"][0]["note10"] == gme["note10"] and r["ecartees"][0]["groupes"] == gme["groupes"]
    # Ses preuves sont publiées (la fiche s'ouvre comme les autres)
    assert all(i["id"] in r["evenements"] for g in r["ecartees"][0]["groupes"] for i in g["infos"])


def test_sans_tailles_rien_n_est_ecarte():
    """Tailles illisibles (publish.py) : le score est calculé sans elles, rien n'est écarté."""
    r = sc.calculer(EVENEMENTS, MAINTENANT)
    assert r["ecartees"] == [] and r["version"] == "score-9"


def test_la_place_liberee_va_a_la_suivante(monkeypatch):
    ordre = symboles(sc.calculer(EVENEMENTS, MAINTENANT), "hausse")  # de la plus forte à la plus faible
    assert len(ordre) >= 3
    monkeypatch.setattr(sc, "MAX_LISTE", 2)
    r = sc.calculer(EVENEMENTS, MAINTENANT, tailles={ordre[0]: taille(50.0)})
    assert symboles(r, "hausse") == ordre[1:3]  # la 3e prend la place de l'écartée
    assert symboles(r, "ecartees") == [ordre[0]]


def test_la_liste_baisse_ne_change_pas(monkeypatch):
    monkeypatch.setattr(sc, "NOTE_BAISSE", 4.9)  # une vente seule (−0,5 point, 4,6/10) : pour voir la liste « baisse »
    ev = evenement("sec_form4:0001437749-26-031597:P")  # FLNA
    vente = {**ev, "id": ev["id"] + "V", "kind": "vente_initie", "direction": -1, "amount_min": 2e6, "amount_max": 2e6}
    r = sc.calculer([vente], MAINTENANT, tailles={"FLNA": taille(37.2, "petite")})
    assert symboles(r, "baisse") == ["FLNA"] and r["ecartees"] == []


def test_depuis_garde_pour_les_ecartees():
    tailles = {"GME": taille(99.9)}
    premier = sc.calculer(EVENEMENTS, MAINTENANT, precedent={"version": "score-8", "hausse": [], "baisse": []},
                          tailles=tailles)
    assert premier["ecartees"][0]["depuis"] == MAINTENANT.isoformat()
    plus_tard = datetime(2026, 10, 5, 16, 37, tzinfo=timezone.utc)
    second = sc.calculer(EVENEMENTS, plus_tard, precedent=json.loads(json.dumps(premier)), tailles=tailles)
    assert second["ecartees"][0]["depuis"] == MAINTENANT.isoformat()


def test_la_methode_explique_la_regle():
    m = sc.METHODE
    assert m["version"] == "score-9" and "Moins de 100 M$ en bourse" in m["trop_petites"]
    assert "Taille inconnue : rien n'est écarté" in m["trop_petites"]
    assert m["lien_labo"] == "https://github.com/killingsky1/Radar/blob/labo/labo/rejeu3/facteurs.md"


def test_les_ecartees_entrent_dans_les_resultats_a_part():
    tailles = {"GME": taille(99.9)}
    h = {"entrees": []}
    nouvelles = rs.noter_entrees(h, sc.calculer(EVENEMENTS, MAINTENANT, tailles=tailles), MAINTENANT)
    gme = [e for e in nouvelles if e["symbole"] == "GME"]
    assert [e["sens"] for e in gme] == ["ecartee"] and gme[0]["methode"] == "score-9"
    # Revue le lendemain : pas une 2e entrée ; si elle passe 100 M$, elle entre dans la liste « hausse » (autre sens)
    lendemain = datetime(2026, 10, 6, 11, 7, tzinfo=timezone.utc)
    assert not [e for e in rs.noter_entrees(h, sc.calculer(EVENEMENTS, lendemain, tailles=tailles), lendemain)
                if e["symbole"] == "GME"]
    passe = rs.noter_entrees(h, sc.calculer(EVENEMENTS, lendemain, tailles={"GME": taille(100.0)}), lendemain)
    assert [e["sens"] for e in passe if e["symbole"] == "GME"] == ["hausse"]


def test_ecartees_mesurees_a_part_sur_de_vrais_prix(tmp_path, monkeypatch):
    """La même compagnie aux mêmes dates, entrée « hausse » et « écartée » : mêmes prix ; la règle a frappé juste quand
    la compagnie a fait MOINS bien que le marché. Rien ne change pour le taux des listes ni le résumé par signal."""
    from test_lotG import ENTREES, entree, prepare
    quand = datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc)
    prepare(tmp_path, monkeypatch)
    sans = rs.calculer(tmp_path, quand)
    ecartee = {**entree("AAPL", "ecartee", "2026-07-20T14:00:00+00:00"), "taille": "petite",
               "signaux": [{"famille": "inities", "sens": 1, "regle": "achat_dirigeant", "facteurs": []}]}
    monkeypatch.setattr("test_lotG.ENTREES", ENTREES + [ecartee])
    (tmp_path / "avec").mkdir()
    prepare(tmp_path / "avec", monkeypatch)
    r = rs.calculer(tmp_path / "avec", quand)
    h = next(l for l in r["lignes"] if l["symbole"] == "AAPL" and l["sens"] == "hausse")
    e = next(l for l in r["lignes"] if l["symbole"] == "AAPL" and l["sens"] == "ecartee")
    mesures = 0
    for k in ("7", "30"):
        x, y = h["horizons"][k], e["horizons"][k]
        assert x["statut"] == y["statut"] and x.get("variation") == y.get("variation") and x.get("ecart") == y.get("ecart")
        if x["statut"] == "mesure" and x["battu"] is not None:
            mesures += 1
            assert y["battu"] is (x["ecart"] < 0) and x["battu"] is (x["ecart"] > 0)
            assert r["resume"][f"ecartee_{k}"] == {"mesurees": 1, "battu": int(y["battu"]), "ecart_moyen": x["ecart"],
                                                    "en_attente": 0}
    assert mesures >= 1  # au moins une vraie mesure (AAPL, juillet)
    for k in ("hausse_7", "hausse_30", "baisse_7", "baisse_30"):
        assert r["resume"][k] == sans["resume"][k]
    assert r["par_signal"] == sans["par_signal"]
