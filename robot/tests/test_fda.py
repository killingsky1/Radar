"""Tests de la FDA sur les VRAIES fiches openFDA (applications avec une nouvelle molécule, juin à octobre 2026).

Les fiches sont celles reçues de l'API le 3 octobre 2026 ; seule l'enveloppe « meta » des 2 pages est refaite
(total et date de mise à jour repris de la vraie réponse).
"""

import copy
import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

from radar.collecteurs import fda
from radar.collecteurs.sec import Symboles
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures"
JOUR = date(2026, 10, 2)


def page(n):
    return json.loads(gzip.decompress((F / "fda" / f"page{n}.json.gz").read_bytes()))


def applications():
    return page(0)["results"] + page(1)["results"]


def symboles_sec():
    return Symboles(json.loads(gzip.decompress((F / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())))


def app(numero):
    return next(a for a in applications() if a["application_number"] == numero)


def test_seulement_les_nouvelles_molecules_approuvees():
    trouvees = fda.approbations(applications(), "20260601")
    assert len(trouvees) == 24  # compté à la main dans la réponse officielle
    assert all(a["application_number"][:3] in ("NDA", "BLA") for a, _ in trouvees)
    assert max(s["submission_status_date"] for _, s in trouvees) == "20260928"
    assert len(fda.approbations(applications(), "20260803")) == 16  # fenêtre de 60 jours au 2 octobre


def test_mimrylo_de_takeda():
    [(a, s)] = [(a, s) for a, s in fda.approbations(applications(), "20260601") if a["application_number"] == "NDA220605"]
    ev = valider(fda.evenement(a, s, symboles_sec()), JOUR)
    assert ev.badge == "officiel", ev.checks
    assert ev.title == ("FDA : nouveau médicament approuvé, MIMRYLO (rusfertide acetate), "
                        "de Takeda Pharmaceuticals America, Inc.")
    assert (ev.official_id, ev.published_on) == ("NDA220605-ORIG-1", "2026-08-28")
    assert ev.official_url.endswith("ApplNo=220605")
    assert ev.data["lettre"] == "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220605Orig1s000ltr.pdf"
    assert ev.tickers == []  # filiale américaine : on ne devine pas la mère cotée
    assert ev.notes == ["Examen prioritaire : la FDA juge qu'il peut apporter un progrès important.",
                        "Médicament orphelin : maladie rare."]


def test_symbole_seulement_si_le_nom_officiel_concorde():
    syms = symboles_sec()
    attendus = {"BLA761408": ["LLY"], "NDA221198": ["INCY"], "NDA220415": ["ABBV"], "NDA220910": ["RVMD"],
                "NDA221075": ["BMY"], "NDA220210": []}  # « IONIS PHARMS » est une abréviation : rien
    for numero, tickers in attendus.items():
        [(a, s)] = [(a, s) for a, s in fda.approbations(applications(), "20260601") if a["application_number"] == numero]
        assert fda.evenement(a, s, syms).tickers == tickers, numero


def test_deux_noms_qui_menent_a_deux_compagnies_differentes_donnent_rien():
    a = copy.deepcopy(app("NDA220910"))  # Revolution Medicines (RVMD)
    a["sponsor_name"] = "ABBVIE INC"
    s = next(x for x in a["submissions"] if x["submission_type"] == "ORIG")
    assert fda.evenement(a, s, symboles_sec()).tickers == []


def test_sans_lettre_officielle_va_dans_a_verifier():
    a = copy.deepcopy(app("NDA220605"))
    s = next(x for x in a["submissions"] if x["submission_type"] == "ORIG")
    s["application_docs"] = [d for d in s["application_docs"] if d["type"] != "Letter"]
    ev = valider(fda.evenement(a, s), JOUR)
    assert ev.badge == "a_verifier" and ev.checks["lettre_officielle"] is False


def test_l_empreinte_ne_bouge_pas_quand_la_fda_ajoute_un_document():
    a = copy.deepcopy(app("NDA220605"))
    s = next(x for x in a["submissions"] if x["submission_type"] == "ORIG")
    avant = fda.evenement(a, s).sha256
    s["application_docs"].append({"id": "1", "url": "https://www.accessdata.fda.gov/x.pdf", "date": "20261010",
                                  "type": "Review"})
    assert fda.evenement(a, s).sha256 == avant
    s["submission_status_date"] = "20260829"  # un fait officiel change : l'empreinte aussi
    assert fda.evenement(a, s).sha256 != avant


class FauxInternet:
    def __init__(self, pages):
        self.pages, self.appels = pages, []

    def get(self, url):
        self.appels.append(url)
        if url == "https://www.sec.gov/files/company_tickers_exchange.json":
            c = gzip.decompress((F / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())
        elif url.startswith(fda.API + "?search="):
            saut = int(url.rsplit("skip=", 1)[1])
            c = json.dumps(self.pages[saut // fda.PAGE]).encode()
        else:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def test_lecteur_au_complet_et_relance_sans_doublon(tmp_path):
    internet = FauxInternet([page(0), page(1)])
    lecteur = {"fda": fda.collecter}
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs=lecteur)
    assert rapport["fda"] == {"ok": True, "nouveaux": 16, "modifies": 0, "inchanges": 0}, rapport
    assert sum("skip=" in u for u in internet.appels) == 2  # 2 pages de 100, pas plus
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert all(e["badge"] == "officiel" for e in fil), [e["checks"] for e in fil if e["badge"] != "officiel"]
    assert fil[0]["title"].startswith("FDA : nouveau médicament approuvé, EMCITATE")
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
                       collecteurs=lecteur)
    assert rapport["fda"]["nouveaux"] == 0 and rapport["fda"]["modifies"] == 0


def test_openfda_pas_a_jour_met_la_source_en_panne(tmp_path):
    vieux = page(0)
    vieux["meta"]["last_updated"] = "2026-09-01"
    rapport = executer(tmp_path, client=FauxInternet([vieux, page(1)]),
                       maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc), collecteurs={"fda": fda.collecter})
    assert rapport["fda"]["ok"] is False and "plus mis à jour" in rapport["fda"]["erreur"]
