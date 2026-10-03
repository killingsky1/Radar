"""Lot B : note sur 10, listes strictes (7/10 et plus, 3/10 et moins) et « Récent » (moins de 3 jours de bourse),
sur les vraies infos des tests du score (2 octobre 2026) et les vrais scores publiés le 3 octobre 2026."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from radar import score as sc
from test_score import MAINTENANT, vraies_infos


@pytest.mark.parametrize("points, note", [
    # Vrais scores publiés le 3 octobre 2026 (GME, PRHI, CPHC, SAMG, PAM, LESL, EGBN, CBZ). PAM : 3,42 -> 7,85 exact -> 7,9
    (5.13, 9.3), (5.01, 9.2), (4.77, 9.0), (4.67, 8.9), (3.42, 7.9), (-4.67, 1.1), (-1.87, 3.4), (-1.78, 3.5),
    # Limites : achat du PDG en groupe (une seule famille) = 9,4 ; 6 points = 10 ; bornée entre 0 et 10
    (5.25, 9.4), (6.0, 10.0), (9.06, 10.0), (-6.0, 0.0), (-8.2, 0.0), (0.0, 5.0),
    # Arrondi au dixième, 5 vers le haut : 2,34 -> 6,95 -> 7,0 (dans la liste) ; 2,33 -> 6,94… -> 6,9 (dehors)
    (2.34, 7.0), (2.33, 6.9), (-2.34, 3.1), (-2.4, 3.0),
])
def test_note_sur_10(points, note):
    assert sc.note_sur_10(points) == note


@pytest.mark.parametrize("depot, jour, attendu", [
    ("2026-10-02", "2026-10-02", True),   # le jour même
    ("2026-10-02", "2026-10-03", True),   # vendredi -> samedi : 1 jour de bourse
    ("2026-10-02", "2026-10-06", True),   # vendredi -> mardi : vendredi et lundi
    ("2026-10-02", "2026-10-07", False),  # vendredi -> mercredi : 3 jours de bourse
    ("2026-09-30", "2026-10-02", True),   # mercredi -> vendredi : 2
    ("2026-09-30", "2026-10-05", False),  # mercredi -> lundi : 3
    (None, "2026-10-05", False),
])
def test_recent_en_jours_de_bourse(depot, jour, attendu):
    assert sc.recent(depot, date.fromisoformat(jour)) is attendu


def test_listes_strictes_sur_les_vraies_infos():
    r = sc.calculer(vraies_infos(), MAINTENANT)
    jour = sc.jour_de_calcul(MAINTENANT)
    for nom, liste in (("hausse", r["hausse"]), ("baisse", r["baisse"])):
        for x in liste:
            attendu = float(min(max(Decimal(str(x["score"])) * 5 / 6 + 5, Decimal(0)), Decimal(10))
                            .quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
            assert x["note10"] == attendu, x["symbole"]
            assert (x["note10"] >= 7.0) if nom == "hausse" else (x["note10"] <= 3.0)
            # « Récent » = la preuve qui compte la plus récente, dans le sens de la liste
            sens = 1 if nom == "hausse" else -1
            depots = [i for g in x["groupes"] if g["sens"] == sens for i in g["infos"] if i["compte"]]
            plus_recent = max(r["evenements"][i["id"]]["published_on"] for i in depots)
            assert x["depot_recent"] == plus_recent
            assert x["recent"] is sc.recent(plus_recent, jour)
    assert r["methode"]["seuil"].startswith("Une compagnie entre dans la liste à partir de 7/10")
    assert "5 + points × 5/6" in r["methode"]["note10"] and "moins de 3 jours de bourse" in r["methode"]["recent"]
    assert r["methode"]["etudes"]["brochet"]["titre"] == "Brochet (2010)"
