"""Tests des décisions de taux sur de VRAIS communiqués (Fed 2026, Banque du Canada 2024-2026)."""

import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

from radar.collecteurs import banques
from radar.collecteurs.banques import evenement_bdc, evenement_fed, lire_fomc, nombre
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "banques"
JOUR = date(2026, 10, 2)


def page(nom):
    return gzip.decompress((F / f"{nom}.gz").read_bytes()).decode("utf-8")


def item_fed(ident):
    return next(i for i in banques._items((F / "fed_monetary.xml").read_text(encoding="utf-8")) if ident in i["lien"])


def item_bdc(jour):
    a, m = jour[:4], jour[5:7]
    return {"titre": "", "lien": f"https://www.bankofcanada.ca/{a}/{m}/fad-press-release-{jour}/", "date": ""}


def test_nombres_officiels():
    assert [nombre(x) for x in ("3-3/4", "4", "1/4", "4¾", "2.25", "½")] == [3.75, 4.0, 0.25, 4.75, 2.25, 0.5]


def test_fed_hausse_de_septembre():
    ev = valider(evenement_fed(item_fed("monetary20260916a"), page("monetary20260916a.htm")), JOUR)
    assert ev.badge == "officiel", ev.checks
    assert ev.title == "Fed : taux directeur relevé de 0,25 point, entre 3,75 % et 4 % (vote : 12 pour, 0 contre)"
    assert (ev.data["bas"], ev.data["haut"], ev.direction, ev.published_on) == (3.75, 4.0, -1, "2026-09-16")


def test_fed_statu_quo_de_juillet_avec_dissidence():
    ev = valider(evenement_fed(item_fed("monetary20260729a"), page("monetary20260729a.htm")), JOUR)
    assert ev.title == "Fed : taux directeur maintenu entre 3,5 % et 3,75 % (vote : 9 pour, 3 contre)"
    assert ev.direction == 0 and ev.badge == "officiel"


def test_fed_ancien_format_decision_au_milieu_et_vote_en_noms():
    # Avril 2026 : « In support of its goals, the Committee decided to maintain … at 3‑1/2 to 3‑3/4 percent »
    ev = valider(evenement_fed(item_fed("monetary20260429a"), page("monetary20260429a.htm")), JOUR)
    assert ev.badge == "officiel", ev.checks
    assert ev.title == "Fed : taux directeur maintenu entre 3,5 % et 3,75 % (avec dissidence)"


def test_fed_texte_illisible_va_dans_a_verifier():
    p = page("monetary20260916a.htm").replace("decided to raise the target range", "decided to change the target range")
    ev = valider(evenement_fed(item_fed("monetary20260916a"), p), JOUR)
    assert ev.badge == "a_verifier" and ev.checks["decision_lue"] is False
    assert "texte à lire" in ev.title  # rien d'inventé


def test_bdc_statu_quo_baisse_et_titre_sans_taux():
    attendus = {
        "2026-09-02": ("Banque du Canada : taux directeur maintenu à 2,25 %", 0),
        "2025-10-29": ("Banque du Canada : taux directeur abaissé de 0,25 point, à 2,25 %", 1),
        "2024-06-05": ("Banque du Canada : taux directeur abaissé, à 4,75 %", 1),  # titre officiel sans le taux
    }
    for jour, (titre, direction) in attendus.items():
        ev = valider(evenement_bdc(item_bdc(jour), page(f"fad-press-release-{jour}.html")), JOUR)
        assert ev.badge == "officiel", (jour, ev.checks)
        assert (ev.title, ev.direction, ev.published_on, ev.currency) == (titre, direction, jour, "CAD")


def test_bdc_titre_et_phrase_en_desaccord():
    p = page("fad-press-release-2026-09-02.html").replace("today held its target", "today reduced its target")
    ev = valider(evenement_bdc(item_bdc("2026-09-02"), p), JOUR)
    assert ev.badge == "a_verifier" and ev.checks["titre_officiel_concorde"] is False


class FauxInternet:
    def __init__(self, pages):
        self.pages, self.appels = pages, []

    def get(self, url):
        self.appels.append(url)
        if url not in self.pages:
            raise ErreurSource(f"{url} : HTTP 404")
        c = self.pages[url]
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def fil_reduit(nom, garder):
    """Le vrai fil, réduit aux communiqués dont on a la page dans les fichiers de test (items inchangés)."""
    import re

    t = (F / nom).read_text(encoding="utf-8")
    items = re.findall(r"<item[ >].*?</item>", t, re.S)
    gardes = [i for i in items if any(g in i for g in garder)]
    return (t[:t.index(items[0])] + "".join(gardes) + t[t.rindex(items[-1]) + len(items[-1]):]).encode()


def internet_des_banques():
    return FauxInternet({
        banques.FLUX_FED: fil_reduit("fed_monetary.xml", ["monetary20260916a", "monetary20260729a"]),
        banques.FLUX_BDC: fil_reduit("bdc_communiques.xml", ["fad-press-release-2026-09-02"]),
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm": page("monetary20260916a.htm").encode(),
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm": page("monetary20260729a.htm").encode(),
        "https://www.bankofcanada.ca/2026/09/fad-press-release-2026-09-02/": page("fad-press-release-2026-09-02.html").encode(),
    })


LECTEURS = {"fed": banques.collecter_fed, "banque_canada": banques.collecter_bdc}


def test_lecteurs_au_complet(tmp_path):
    internet = internet_des_banques()
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs=LECTEURS)
    assert rapport["fed"]["ok"] and rapport["banque_canada"]["ok"], rapport
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    titres = {e["official_id"]: e["title"] for e in fil}
    assert titres["monetary20260916a"].startswith("Fed : taux directeur relevé")
    assert titres["monetary20260729a"].startswith("Fed : taux directeur maintenu")
    assert titres["fad-press-release-2026-09-02"] == "Banque du Canada : taux directeur maintenu à 2,25 %"
    assert all(e["badge"] == "officiel" for e in fil)

    avant = len(internet.appels)  # 2e passage : les communiqués déjà lus ne sont pas retéléchargés
    executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 3, 12, tzinfo=timezone.utc), collecteurs=LECTEURS)
    assert all("pressreleases/monetary" not in u and "fad-press-release" not in u for u in internet.appels[avant:])


def test_page_introuvable_met_la_source_en_panne(tmp_path):
    internet = internet_des_banques()
    del internet.pages["https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm"]
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs=LECTEURS)
    assert rapport["fed"]["ok"] is False and "404" in rapport["fed"]["erreur"]
    assert rapport["banque_canada"]["ok"]  # une source en panne n'arrête pas les autres
