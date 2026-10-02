"""Tests du Centre des nouvelles du Canada sur le VRAI fil français (24 sept. au 2 oct. 2026, 200 entrées)."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from radar.collecteurs import canada
from radar.collecteurs.canada import categorie, lire_fil
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "canada" / "nouvelles_fr.atom"


def entrees():
    return lire_fil(F.read_bytes())


def par_titre(debut, ministere=None):
    return next(e for e in entrees() if e["titre"].startswith(debut) and ministere in (None, e["ministere"]))


FINANCES = "Ministère des Finances Canada"


def test_le_fil_officiel_est_lu_au_complet():
    es = entrees()
    assert len(es) == 200
    assert all(e["lien"].startswith("https://www.canada.ca/fr/") for e in es)
    assert all(e["ministere"] and e["type"] and e["mis_a_jour"] for e in es)


def test_defense_et_economie_seulement_les_communiques():
    assert categorie(par_titre("L’Aviation royale canadienne s’associe au Fanshawe College")) == "militaire"
    assert categorie(par_titre("Le gouvernement du Canada franchit une nouvelle étape en vue de doter")) == "militaire"
    assert categorie(par_titre("Le gouvernement du Canada présente la nouvelle Mégadéduction", FINANCES)) == "canada"
    # Même annonce relayée par une agence régionale : pas dans la liste des ministères économiques
    assert categorie(par_titre("Le gouvernement du Canada présente la nouvelle Mégadéduction",
                               "Agence fédérale de développement économique pour le Sud de l’Ontario")) is None
    assert categorie(par_titre("La Régie approuve le règlement de Trans Mountain")) == "canada"
    # Compte rendu de la Défense, avis aux médias des Finances, diplomatie : laissés de côté
    assert categorie(par_titre("Le ministre McGuinty participe à la réunion des ministres de la Défense")) is None
    assert categorie(par_titre("Le secrétaire d'État Long sera à Saint John")) is None
    assert categorie(par_titre("Annonce de nouvelles nominations diplomatiques")) is None


def test_une_nouvelle_devient_une_info_officielle():
    e = par_titre("Le gouvernement du Canada présente la nouvelle Mégadéduction", FINANCES)
    ev = valider(canada.evenement(e, "canada"), date(2026, 10, 2))
    assert ev.badge == "officiel", ev.checks
    assert ev.source == "nouvelles_eco_ca" and ev.published_on == "2026-10-01"
    assert ev.official_id.startswith("ministere-finances/nouvelles/2026/10/"), ev.official_id
    assert ev.data["ministere"] == "Ministère des Finances Canada"


def test_date_selon_l_heure_de_l_est():
    e = dict(par_titre("Le gouvernement du Canada présente la nouvelle Mégadéduction", FINANCES), mis_a_jour="2026-10-01T22:30:00-04:00")
    assert canada.evenement(e, "canada").published_on == "2026-10-01"  # 22 h 30 à Ottawa : encore le 1er octobre


class FauxInternet:
    def __init__(self, contenu):
        self.contenu, self.appels = contenu, []

    def get(self, url):
        self.appels.append(url)
        if not url.startswith("https://api.io.canada.ca/io-server/gc/news/fr/v2"):
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": self.contenu, "sha256": empreinte(self.contenu)})()


def test_les_deux_lecteurs_partagent_un_seul_telechargement(tmp_path):
    internet = FauxInternet(F.read_bytes())
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc),
                       collecteurs={"nouvelles_defense_ca": canada.collecter_defense,
                                    "nouvelles_eco_ca": canada.collecter_economie})
    assert rapport["nouvelles_defense_ca"]["ok"] and rapport["nouvelles_eco_ca"]["ok"], rapport
    assert len(internet.appels) == 1
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert {e["category"] for e in fil} == {"militaire", "canada"}
    assert all(e["badge"] == "officiel" for e in fil)
    assert all(e["currency"] == "CAD" for e in fil)
