"""Lot C, section « Argent », sur de VRAIES infos publiées par le robot (29 septembre au 2 octobre 2026 ; élus et
cabinet plus anciens) : chiffres attendus calculés à la main à partir des lignes des dépôts officiels."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from radar import argent
from radar.publish import publier
from radar.models import Evenement
from radar.store import Depot

F = Path(__file__).parent / "fixtures" / "lotC"
JOUR = date(2026, 10, 3)


def infos():
    return [json.loads(l) for l in (F / "argent_reels.jsonl").read_text().splitlines()]


def lignes():
    return {l["id"].split(":", 1)[1]: l for l in argent.preparer(infos(), JOUR)[0]["lignes"]}


def test_achats_de_gamestop_actions_prix_total_et_part_de_ses_actions():
    ls = lignes()
    oct2 = ls["0000921895-26-002719:P"]  # Ryan Cohen, 2 octobre : une ligne
    assert (oct2["actions"], oct2["prix"], oct2["montant"]) == (700000, 24.4061, 17084270.0)
    assert oct2["part"] == {"pourcentage": 1.71}  # 700 000 / (41 648 522 − 700 000) = 1,709 %
    sept29 = ls["0000921895-26-002670:P"]  # 2 lignes du même compte : 446 500 puis 3 500
    assert (sept29["actions"], sept29["montant"]) == (450000, 10563796.1)
    assert sept29["part"] == {"pourcentage": 1.11}  # 450 000 / (40 945 022 − 446 500) = 1,111 %
    turner = ls["0001822293-26-000002:P"]  # administrateur : 10 462 actions, il n'en avait aucune
    assert turner["part"] == {"nouvelle": True}
    assert (oct2["famille"], oct2["sens"], oct2["symbole"], oct2["compagnie"]) == ("dirigeants", 1, "GME", "GameStop Corp.")


def test_titres_differents_pas_de_prix_moyen():
    pam = lignes()["0002028916-26-000011:P"]  # actions ordinaires à 3,105 $ et certificats (ADS) à 77,628 $
    assert pam["prix_multiples"] is True and pam["prix"] is None and pam["actions"] is None
    assert pam["montant"] == 5564816.68 and pam["nb_lignes"] == 2 and pam["part"] is None


def test_ventes_part_vendue_plan_et_doublons():
    ls = lignes()
    beke = ls["0001193125-26-405896:S"]  # PDG : 16 033 983 vendues, 62 824 251 gardées
    assert beke["part"] == {"pourcentage": 20.33} and beke["plan"] is False
    cbrs = ls["0001628280-26-064042:S"]  # vente planifiée (10b5-1), jusqu'à 0 action
    assert cbrs["plan"] is True and cbrs["part"] == {"pourcentage": 100.0}
    bmbl = [l for l in ls.values() if l["symbole"] == "BMBL"]  # Blackstone : 5 dépôts, une seule vente
    assert len(bmbl) == 1 and len(bmbl[0]["aussi"]) == 4
    assert bmbl[0]["part"] is None  # 7 comptes différents : pas de pourcentage deviné


def test_avis_144_part_de_la_compagnie():
    ls = lignes()
    th = ls["0000950142-26-002664"]
    assert (th["famille"], th["sens"], th["actions"], th["montant"]) == ("intentions", -1, 8361829.0, 153857653.6)
    assert th["part"] == {"pourcentage_compagnie": 8.539}  # 8 361 829 / 97 929 824
    assert ls["0001950047-26-009982"]["plan"] is True  # UTHR : plan du 21 novembre 2025


def test_avis_144_a_plusieurs_lignes_jamais_d_addition_du_total_en_circulation():
    th = next(d for d in infos() if d["official_id"] == "0000950142-26-002664")
    ligne1 = th["data"]["lignes"][0]
    # Deux courtiers, même titre : chaque ligne répète le total en circulation (97 929 824) -> 8 361 829 / 97 929 824
    deux = dict(th, data=dict(th["data"], lignes=[dict(ligne1, actions=4000000.0), dict(ligne1, actions=4361829.0)]))
    assert argent.ligne(deux)["part"] == {"pourcentage_compagnie": 8.539}
    # Deux titres différents : pas de pourcentage deviné
    autre = dict(th, data=dict(th["data"], lignes=[ligne1, dict(ligne1, classe="Warrants", en_circulation=5000000.0)]))
    assert argent.ligne(autre)["part"] is None


def test_elus_fourchettes_et_periode_de_30_jours():
    ls = lignes()
    msft = [l for l in ls.values() if l["symbole"] == "MSFT"]
    assert sorted((l["sens"], l["montant_min"], l["montant_max"], l["role"]) for l in msft) == [
        (-1, 750002.0, 1500000.0, "options"), (1, 750002.0, 1500000.0, "options")]
    assert all(l["montant"] is None for l in msft)
    # Cabinet (OGE) : rapports de juillet et août, hors des 30 derniers jours
    assert not [l for l in ls.values() if l["source"] == "oge_278t"]


def test_tri_et_thermometre():
    a = argent.preparer(infos(), JOUR)[0]
    montants = [l["montant"] if l["montant"] is not None else l["montant_min"] for l in a["lignes"]]
    assert montants == sorted(montants, reverse=True)
    t = a["thermometre"]
    assert t["depuis"] == "2026-09-27"
    assert t["achats"] == {"nombre": 6, "montant": round(17084270.0 + 10563796.1 + 254540.46 + 5564816.68 + 1956500.0
                                                          + 66278316.42, 2)}
    assert t["ventes_libres"] == {"nombre": 2, "montant": round(84552002.55 + 11070102.67, 2)}
    assert t["ventes_planifiees"] == {"nombre": 2, "montant": round(80798603.74 + 6614881.88, 2)}
    assert t["intentions"] == {"nombre": 5, "montant": round(153857653.6 + 48542346.4 + 4990466.8 + 140910000.0
                                                             + 113255010.0, 2)}


def test_publication_des_deux_fichiers(tmp_path):
    Depot(tmp_path).enregistrer([Evenement.from_dict(d) for d in infos()])
    publier(tmp_path, {}, set(), datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc))
    a = json.loads((tmp_path / "app" / "argent.json").read_text())
    tous = json.loads((tmp_path / "app" / "argent_infos.json").read_text())
    assert {l["id"] for l in a["lignes"]} == set(tous)
    assert all(not tous[i]["data"].get("meme_transaction_que") for i in tous)  # chaque transaction une seule fois
    # 26 infos − 3 rapports du cabinet (juillet, août : hors des 30 jours) − 4 doublons de Blackstone = 19 lignes
    assert len(a["lignes"]) == 19 and a["dernier_jour"] == "2026-10-02"
