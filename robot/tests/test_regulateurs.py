"""Tests des régulateurs américains sur de VRAIS documents (reçus le 3 octobre 2026) : rappels NHTSA, antitrust DOJ,
suspensions et procédures SEC, sanctions OFAC, fins anticipées d'examen des fusions (FTC)."""

import copy
import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

from radar.collecteurs import regulateurs as r
from radar.collecteurs.banques import _items
from radar.collecteurs.sec import Symboles
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures"
D = F / "regulateurs"
JOUR = date(2026, 10, 2)


def lire(nom):
    return gzip.decompress((D / f"{nom}.gz").read_bytes()).decode("utf-8")


def symboles_sec():
    return Symboles(json.loads(gzip.decompress((F / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())))


# ---------- NHTSA ----------

def test_nhtsa_gros_rappels_seulement_avec_symbole_exact():
    rangees = json.loads(lire("nhtsa_50.json"))
    evs = [valider(e, JOUR) for e in (r.evenement_nhtsa(x, symboles_sec()) for x in rangees) if e]
    assert len(evs) == 11  # 11 rappels de 10 000 unités et plus sur les 50 derniers
    assert all(e.badge == "officiel" for e in evs), [e.checks for e in evs if e.badge != "officiel"]
    ford = next(e for e in evs if "223 472" in e.title)
    assert ford.title.startswith("Rappel de Ford Motor Company : 223 472 véhicules — « Fuel Tank May Leak or Detach »")
    assert ford.tickers == ["F"] and ford.direction == -1
    par_constructeur = {e.data["constructeur"]: e.tickers for e in evs}
    assert par_constructeur["Rivian Automotive, LLC"] == ["RIVN"]
    assert par_constructeur["Volkswagen Group of America, Inc."] == []  # pas cotée à la SEC : rien de deviné
    assert par_constructeur["Chrysler (FCA US, LLC)"] == []


# ---------- DOJ ----------

def test_doj_communiques_seulement():
    items = _items(lire("doj_atr_rss.xml"))
    evs = [valider(e, JOUR) for e in (r.evenement_doj(i) for i in items) if e]
    assert len(evs) < len(items)  # les discours sont écartés
    assert all(e.official_url.startswith("https://www.justice.gov/opa/pr/") for e in evs)
    kkr = next(e for e in evs if "KKR" in e.title)
    assert kkr.title == ("Antitrust (ministère de la Justice) : KKR Agrees to Pay Record $250M Penalty for Serial "
                         "Violations of Federal Premerger Review Law")
    assert (kkr.published_on, kkr.badge) == ("2026-08-26", "officiel")


# ---------- SEC ----------

def test_sec_procedures_seulement_contre_des_compagnies_cotees():
    syms = symboles_sec()
    evs = [valider(e, JOUR) for e in (r.evenement_sec(i, "procedure", syms) for i in _items(lire("sec_ap_rss.xml"))) if e]
    noms = {e.data["nom_officiel"]: e.tickers for e in evs}
    assert noms["Eagle Bancorp, Inc."] == ["EGBN"] and noms["CBIZ, Inc."] == ["CBZ"]
    assert "CityVest Capital Inc., CV Manager LLC, and Alan P. Donenfeld" not in noms  # pas cotée : écartée
    assert all(e.badge == "officiel" and e.kind == "procedure_sec" for e in evs)


def test_sec_suspensions_toutes_gardees():
    evs = [valider(e, JOUR) for e in (r.evenement_sec(i, "suspension", symboles_sec())
                                      for i in _items(lire("sec_susp_rss.xml"))) if e]
    assert len(evs) == 25
    happy = evs[0]
    assert (happy.title, happy.official_id, happy.published_on) == (
        "SEC : cotation suspendue, Happy City Holdings Limited", "34-105675", "2026-06-11")
    assert happy.badge == "officiel"


# ---------- OFAC ----------

def page_ofac(n):
    return lire(f"ofac_{n}.html")


def test_ofac_compte_les_fiches_sans_inventer_de_noms():
    attendus = {
        "20261002": ({"personnes": 3, "entités": 2}, 0, "Counter Terrorism Designations"),
        "20261001": ({"personnes": 2, "entités": 29}, 0, None),
        "20260930": ({"personnes": 9, "entités": 2}, 6, None),
        # Congo : 8 fiches retirées, puis un paragraphe administratif sans rapport qui ne doit pas compter
        "20260923": ({}, 8, "Democratic Republic of the Congo-related Designations Removals"),
    }
    for n, (ajouts, retraits, titre) in attendus.items():
        ev = valider(r.evenement_ofac(f"https://ofac.treasury.gov/recent-actions/{n}", page_ofac(n)), JOUR)
        assert ev.badge == "officiel", (n, ev.checks)
        assert (ev.data["ajouts"], ev.data["retraits"]) == (ajouts, retraits), n
        assert ev.published_on == f"{n[:4]}-{n[4:6]}-{n[6:]}"
        if titre:
            assert ev.title == f"Sanctions américaines (OFAC) : {titre}"
    oct1 = r.evenement_ofac("https://ofac.treasury.gov/recent-actions/20261001", page_ofac("20261001"))
    assert oct1.notes[0] == ("Communiqué du Trésor : Operation Economic Outcast Takes Unprecedented Action Against "
                             "Sanctions Evasion Network Used by Iran")


def test_ofac_liste_officielle_et_actions_sans_designation_ignorees():
    actions = r.lire_liste_ofac(lire("ofac_recent.html"))
    assert len(actions) == 10 and actions[0]["url"] == "https://ofac.treasury.gov/recent-actions/20261002"
    licences = next(a for a in actions if a["titre"].startswith("Issuance of Amended Venezuela General Licenses"))
    assert "Designation" not in licences["titre"]  # pas lue : licences, pas des sanctions


# ---------- FTC ----------

def test_ftc_feux_verts_et_symboles_exacts():
    avis = r.lire_ftc(lire("ftc_et_rss.xml"))
    assert len(avis) == 20
    evs = [valider(e, JOUR) for e in (r.evenement_ftc(a, symboles_sec()) for a in avis) if e]
    assert len(evs) == 20 and all(e.badge == "officiel" for e in evs)
    integer = next(e for e in evs if e.official_id == "20262239")
    assert integer.title == ("FTC : feu vert antitrust anticipé, KKR Armstrong Aggregator L.P. (acquéreur) et "
                             "Integer Holdings Corporation (partie visée)")
    assert (integer.tickers, integer.occurred_on, integer.published_on) == (["ITGR"], "2026-09-29", "2026-09-30")
    indivior = next(e for e in evs if e.data["acquereur"].startswith("Indivior"))
    assert indivior.tickers == ["INDV", "SUPN"]


def test_ftc_avis_non_accorde_ignore():
    a = copy.deepcopy(r.lire_ftc(lire("ftc_et_rss.xml"))[0])
    a["statut"] = "Denied"
    assert r.evenement_ftc(a) is None


# ---------- Lecteurs au complet ----------

class FauxInternet:
    def __init__(self):
        self.appels = []

    def get(self, url):
        self.appels.append(url)
        pages = {
            r.DOJ_FLUX: "doj_atr_rss.xml", r.SEC_SUSPENSIONS: "sec_susp_rss.xml", r.SEC_PROCEDURES: "sec_ap_rss.xml",
            r.OFAC_LISTE: "ofac_recent.html", r.FTC_FLUX: "ftc_et_rss.xml",
            "https://ofac.treasury.gov/recent-actions/20261002": "ofac_20261002.html",
            "https://ofac.treasury.gov/recent-actions/20261001": "ofac_20261001.html",
            "https://ofac.treasury.gov/recent-actions/20260930": "ofac_20260930.html",
        }
        if url == "https://www.sec.gov/files/company_tickers_exchange.json":
            c = gzip.decompress((F / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())
        elif url.startswith(r.NHTSA_API):
            c = lire("nhtsa_50.json").encode()
        elif url in pages:
            c = lire(pages[url]).encode()
        else:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


LECTEURS = {"nhtsa": r.collecter_nhtsa, "doj_antitrust": r.collecter_doj, "sec_poursuites": r.collecter_sec_poursuites,
            "ftc_fusions": r.collecter_ftc}


def test_lecteurs_au_complet_fenetre_de_30_jours_et_sans_doublon(tmp_path):
    internet = FauxInternet()
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs=LECTEURS)
    assert all(rapport[s]["ok"] for s in LECTEURS), rapport
    assert rapport["nhtsa"]["nouveaux"] == 11
    assert rapport["ftc_fusions"]["nouveaux"] == 20
    assert rapport["sec_poursuites"]["nouveaux"] == 2  # 2 procédures (Eagle Bancorp, CBIZ) ; aucune suspension en 30 jours
    assert rapport["doj_antitrust"]["nouveaux"] == 3  # communiqués du 2 sept. au 2 oct. seulement
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert {e["badge"] for e in fil} == {"officiel"}
    avant = {s: rapport[s]["nouveaux"] for s in LECTEURS}
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 23, tzinfo=timezone.utc),
                       collecteurs=LECTEURS)
    assert all(rapport[s].get("nouveaux", 0) == 0 for s in LECTEURS if rapport[s]["ok"]), (avant, rapport)


def test_ofac_au_complet(tmp_path, monkeypatch):
    # La vraie liste a 10 actions ; on a gardé les pages des 3 plus récentes, donc on lit ces 3-là.
    vraie = r.lire_liste_ofac
    monkeypatch.setattr(r, "lire_liste_ofac", lambda page: vraie(page)[:3])
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs={"sanctions_us": r.collecter_ofac})
    assert rapport["sanctions_us"] == {"ok": True, "nouveaux": 3, "modifies": 0, "inchanges": 0}, rapport


def test_ofac_page_introuvable_met_la_source_en_panne(tmp_path):
    rapport = executer(tmp_path, client=FauxInternet(), maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs={"sanctions_us": r.collecter_ofac})
    assert rapport["sanctions_us"]["ok"] is False and "404" in rapport["sanctions_us"]["erreur"]
