"""Lot F, fins de blocage après une entrée en bourse, sur 16 VRAIS prospectus finals (424B4) lus à la SEC le 4 octobre
2026 (tests/fixtures/lotF : en-tête officiel + document 424B4, sans pièces jointes ni images) et les vraies lignes 424B4
des index trimestriels de la SEC. Les dates attendues sont calculées à la main à partir des phrases des prospectus."""

import gzip
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from radar import calendrier
from radar.collecteurs import blocage as b
from radar.collecteurs.sec import DepotSec, entete, iso
from radar.http import ErreurSource
from radar.models import Evenement, empreinte
from radar.publish import publier
from radar.registry import SOURCES
from radar.run import Contexte
from radar.score import SANS_POINTS, evaluer
from radar.store import Depot
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "lotF"
MAINTENANT = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
MANIFESTE = {m["acc"]: m for m in json.loads((F / "manifeste.json").read_text(encoding="utf-8"))}


def txt(acc):
    return gzip.decompress((F / f"{acc}.txt.gz").read_bytes())


def analyse(acc, depose=None):
    t = b.decoder(txt(acc))
    return b.analyser(b.texte_doc(b.document_424b4(t)), depose or date.fromisoformat(iso(entete(t)["depose"])))


PUBLIABLES = [  # (numéro, compagnie, date du prospectus, fin = date + 180 jours, mots de la phrase montrée)
    ("0001104659-26-079884", "Bending Spoons", "2026-06-30", "2026-12-27", "executive officers and directors"),
    ("0001193125-26-316503", "Scribe", "2026-07-23", "2027-01-19", "directors and officers"),
    ("0001193125-26-326453", "Jersey Mike's", "2026-07-29", "2027-01-25", "Principal Stockholders"),
    ("0001193125-26-328422", "Apnimed", "2026-07-30", "2027-01-26", "for a period of 180 days after the date"),
    ("0001213900-26-086641", "Ticketplus", "2026-08-06", "2027-02-02", "for a period of 180 days after the date"),
    ("0001193125-26-395670", "Electra", "2026-09-17", "2027-03-16", "for a period of 180 days after the date"),
    ("0001193125-26-403094", "ADARx", "2026-09-24", "2027-03-23", "through the date 180 days after the date"),
]


@pytest.mark.parametrize("acc,nom,prospectus,fin,mots", PUBLIABLES, ids=[p[1] for p in PUBLIABLES])
def test_les_7_vraies_entrees_en_bourse_publiables(acc, nom, prospectus, fin, mots):
    r = analyse(acc)
    assert r["raisons"] == [], nom
    assert (r["date_prospectus"], r["duree_jours"], r["fin_blocage"]) == (prospectus, 180, fin)
    assert r["fin_blocage"] == (date.fromisoformat(prospectus) + timedelta(days=180)).isoformat()
    assert mots in r["phrase_blocage"] and "180" in r["phrase_blocage"]
    assert "directed share program" not in r["phrase_blocage"]  # Jersey Mike's : l'engagement principal, pas le programme
    assert r["ecart_ouvrables"] <= 2 and any(p["directe"] for p in r["preuves_date"])


IGNORES = [  # (numéro, pourquoi, raison attendue)
    ("0001193125-26-299963", "SK hynix, déjà cotée en Corée", "exclu : actions déjà négociées ailleurs"),
    ("0001104659-26-088733", "Reformation", "levée anticipée mentionnée"),
    ("0001104659-26-084293", "Csquare", "levée anticipée mentionnée"),
    ("0001213900-26-078747", "Standard Nuclear", "plusieurs durées de blocage"),
    ("0001628280-26-062794", "Orion180", "date du prospectus absente"),
    ("0001185185-26-004253", "RUI Holdings", "aucune durée de blocage"),
    ("0001104659-26-110065", "InnovAge, offre secondaire", "pas une entrée en bourse"),
    ("0001193125-26-395319", "Haymaker V, SPAC", "exclu : compagnie de chèque en blanc (SPAC)"),
    ("0001213900-26-104150", "ROZE AI, inscription directe", "exclu : inscription directe"),
]


@pytest.mark.parametrize("acc,pourquoi,raison", IGNORES, ids=[i[1] for i in IGNORES])
def test_les_9_autres_ignores_avec_la_bonne_raison(acc, pourquoi, raison):
    assert raison in analyse(acc)["raisons"], pourquoi


def test_rui_holdings_une_phrase_au_futur_n_est_pas_une_cotation():
    # « until our Ordinary Shares are listed on a national securities exchange » : vraie entrée en bourse
    assert not any(r.startswith("exclu") for r in analyse("0001185185-26-004253")["raisons"])


def test_texte_une_balise_dans_un_mot_ne_coupe_pas_la_date():
    assert b.texte_doc("<p>Prospectus dated September 29, 202<span>6</span></p><div>Table</div>") == \
        "Prospectus dated September 29, 2026 Table"


def test_la_date_doit_avoir_une_preuve_directe():
    t = b.texte_doc(b.document_424b4(b.decoder(txt("0001193125-26-403094"))))  # ADARx
    assert "LifeSci Capital September 24, 2026" in t
    # Sans la date du bas de la couverture, il reste seulement « 25 days after the commencement of this offering »
    r = b.analyser(t.replace("LifeSci Capital September 24, 2026", "LifeSci Capital"), date(2026, 9, 28))
    assert r["raisons"] == ["date du prospectus absente"]
    assert [p["sorte"] for p in r["preuves_date"]] == ["25 jours"] and not r["preuves_date"][0]["directe"]


def test_deux_dates_differentes_rien():
    t = b.texte_doc(b.document_424b4(b.decoder(txt("0001193125-26-328422"))))  # Apnimed
    r = b.analyser(t.replace("The date of this prospectus is July 30, 2026", "The date of this prospectus is July 31, 2026"),
                   date(2026, 7, 31))
    assert "dates du prospectus différentes" in r["raisons"]


def test_depot_trop_loin_de_la_date_du_prospectus():
    assert analyse("0001193125-26-328422", depose=date(2026, 7, 31))["raisons"] == []  # 1 jour ouvrable
    assert analyse("0001193125-26-328422", depose=date(2026, 8, 5))["raisons"] == [
        "date du prospectus trop loin du dépôt à la SEC"]  # 4 jours ouvrables


# ---------- Le robot : lecture, attente du symbole, rattrapage, contrôles, note ----------


class FauxInternet:
    def __init__(self, symboles=None):
        self.appels = []
        self.symboles = symboles or json.loads((F / "symboles.json").read_text(encoding="utf-8"))

    def _rep(self, c):
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()

    def get(self, url, entetes=None):
        self.appels.append(url)
        if url == "https://www.sec.gov/files/company_tickers_exchange.json":
            return self._rep(json.dumps(self.symboles).encode())
        if "/full-index/2026/QTR" in url:
            t = url.split("/QTR")[1][0]
            lignes = (F / f"master_424b4_2026T{t}.idx").read_text(encoding="latin-1").splitlines()
            # Les vraies lignes 424B4 de l'index, seulement nos 16 prospectus (les autres ne sont pas dans les tests)
            garde = lignes[:11] + [l for l in lignes[11:] if l.split("|")[4].rsplit("/", 1)[1][:-4] in MANIFESTE]
            return self._rep(("\n".join(garde) + "\n").encode("latin-1"))
        acc = url.rsplit("/", 1)[1].removesuffix(".txt")
        if url.startswith("https://www.sec.gov/Archives/edgar/data/") and acc in MANIFESTE:
            return self._rep(txt(acc))
        raise ErreurSource(f"{url} : HTTP 404")


def contexte(tmp_path, internet, quand=MAINTENANT):
    return Contexte(client=internet, maintenant=quand, donnees=tmp_path)


def test_rattrapage_une_seule_fois_puis_plus_rien(tmp_path):
    internet = FauxInternet()
    evs = b.collecter(contexte(tmp_path, internet))
    assert sorted(e.tickers[0] for e in evs) == ["ADRX", "APMD", "BSP", "ETRA", "JMKE", "SCTX", "TP"]
    assert sum("/full-index/" in u for u in internet.appels) == 2  # 2e et 3e trimestres de 2026
    etat = json.loads((tmp_path / "sec" / "blocage.json").read_text())
    assert etat["trimestres_finis"] == ["2026T2", "2026T3"] and len(etat["lus"]) == 16 and etat["en_attente"] == {}
    internet2 = FauxInternet()
    assert b.collecter(contexte(tmp_path, internet2)) == []
    assert not [u for u in internet2.appels if "/full-index/" in u or u.endswith(".txt")]  # rien n'est relu


def test_info_publiee_controles_et_badge_officiel(tmp_path):
    ev = next(e for e in b.collecter(contexte(tmp_path, FauxInternet())) if e.tickers == ["APMD"])
    assert ev.title == "Apnimed, Inc. : fin prévue du blocage de 180 jours le 26 janvier 2027 (entrée en bourse, " \
                       "prospectus du 30 juillet 2026)"
    assert (ev.source, ev.kind, ev.category, ev.direction) == ("sec_blocage", "fin_blocage", "compagnies", 0)
    assert (ev.occurred_on, ev.published_on) == ("2026-07-30", "2026-07-31")
    assert ev.official_url == "https://www.sec.gov/Archives/edgar/data/1745648/000119312526328422/0001193125-26-328422-index.htm"
    assert ev.data["fin_blocage"] == "2027-01-26" and ev.data["bourse"] == "Nasdaq"
    assert ["Fin prévue du blocage", "mardi 26 janvier 2027 (inclus)"] in ev.data["details"]
    v = valider(ev, date(2026, 10, 4))
    assert v.badge == "officiel" and all(v.checks.values())
    # Une fin mal calculée ou une durée absente de la phrase : « À vérifier »
    faux = Evenement.from_dict({**ev.to_dict(), "data": {**ev.data, "fin_blocage": "2027-01-27"}})
    assert valider(faux, date(2026, 10, 4)).checks["fin_calculee"] is False
    faux = Evenement.from_dict({**ev.to_dict(), "data": {**ev.data, "duree_jours": 90}})
    assert valider(faux, date(2026, 10, 4)).badge == "a_verifier"


def test_zero_point_dans_la_note(tmp_path):
    ev = next(e for e in b.collecter(contexte(tmp_path, FauxInternet())) if e.tickers == ["APMD"])
    apports = evaluer(valider(ev, date(2026, 10, 4)).to_dict())
    assert len(apports) == 1 and apports[0].pourquoi == SANS_POINTS["fin_blocage"] and apports[0].regle is None


def sans_apnimed():
    symboles = json.loads((F / "symboles.json").read_text(encoding="utf-8"))
    return dict(symboles, data=[r for r in symboles["data"] if r[0] != 1745648])


def depot_apnimed():
    return DepotSec("0001193125-26-328422", "424B4", "2026-07-31", "edgar/data/1745648/0001193125-26-328422.txt",
                    [("1745648", "Apnimed, Inc.")])


def le(jour):
    return datetime.combine(date.fromisoformat(jour), datetime.min.time(), timezone.utc).replace(hour=12)


def test_nouvelle_compagnie_sans_symbole_attend_puis_publiee(tmp_path):
    # Lu le lundi 3 août, quand le symbole d'Apnimed n'est pas encore dans la liste officielle de la SEC : en attente
    attente = {}
    assert b.lire_depot(contexte(tmp_path, FauxInternet(sans_apnimed()), quand=le("2026-08-03")), depot_apnimed(),
                        attente) == []
    assert list(attente) == ["0001193125-26-328422"]
    # Le lendemain, le symbole officiel existe : publiée, plus en attente
    evs = b.en_attente(contexte(tmp_path, FauxInternet(), quand=le("2026-08-04")), attente)
    assert [e.tickers for e in evs] == [["APMD"]] and attente == {}


def test_attente_abandonnee_apres_20_jours(tmp_path):
    attente = {}
    b.lire_depot(contexte(tmp_path, FauxInternet(sans_apnimed()), quand=le("2026-08-03")), depot_apnimed(), attente)
    assert b.en_attente(contexte(tmp_path, FauxInternet(sans_apnimed()), quand=le("2026-08-20")), attente) == []
    assert list(attente) == ["0001193125-26-328422"]  # 20 jours après le dépôt du 31 juillet : encore attendue
    assert b.en_attente(contexte(tmp_path, FauxInternet(sans_apnimed()), quand=le("2026-08-21")), attente) == []
    assert attente == {}  # 21 jours : abandonnée (pas cotée au Nasdaq, au NYSE ni au CBOE)


def test_trop_de_prospectus_illisibles_la_source_tombe(tmp_path):
    class Panne(FauxInternet):
        def get(self, url, entetes=None):
            if url.endswith(".txt"):
                raise ErreurSource(f"{url} : HTTP 503")
            return super().get(url, entetes)

    with pytest.raises(RuntimeError, match="prospectus illisibles"):
        b.collecter(contexte(tmp_path, Panne()))
    assert not (tmp_path / "sec" / "blocage.json").exists()  # tout sera relu au prochain passage


# ---------- Calendrier de l'app ----------


def test_calendrier_trie_par_date_et_fins_passees(tmp_path):
    evs = [valider(e, date(2026, 10, 4)) for e in b.collecter(contexte(tmp_path, FauxInternet()))]
    Depot(tmp_path).enregistrer(evs)
    c = calendrier.preparer(Depot(tmp_path), date(2026, 10, 4))
    assert [(l["symbole"], l["fin"]) for l in c["lignes"]] == [
        ("BSP", "2026-12-27"), ("SCTX", "2027-01-19"), ("JMKE", "2027-01-25"), ("APMD", "2027-01-26"),
        ("TP", "2027-02-02"), ("ETRA", "2027-03-16"), ("ADRX", "2027-03-23")]
    assert not any(l["passee"] for l in c["lignes"]) and set(c["evenements"]) == {l["id"] for l in c["lignes"]}
    # Le 30 décembre : Bending Spoons est passée (moins de 7 jours) ; le 4 janvier, elle n'y est plus
    assert calendrier.preparer(Depot(tmp_path), date(2026, 12, 30))["lignes"][0]["passee"] is True
    assert calendrier.preparer(Depot(tmp_path), date(2027, 1, 4))["lignes"][0]["symbole"] == "SCTX"


def test_calendrier_lit_plus_que_les_3_mois_du_fil(tmp_path):
    evs = [valider(e, date(2026, 10, 4)) for e in b.collecter(contexte(tmp_path, FauxInternet()))]
    vieille = Evenement.from_dict({**evs[0].to_dict(), "published_on": "2026-04-02", "occurred_on": "2026-04-01",
                                   "official_id": "0000000000-26-000001",
                                   "data": {**evs[0].data, "date_prospectus": "2026-04-01", "fin_blocage": "2026-09-28",
                                            "preuves_date": [{"sorte": "couverture", "date": "2026-04-01", "directe": True,
                                                              "phrase": "The date of this prospectus is April 1, 2026"}]}})
    Depot(tmp_path).enregistrer(evs + [valider(vieille, date(2026, 10, 4))])
    assert "sec_blocage:0000000000-26-000001" in calendrier.preparer(Depot(tmp_path), date(2026, 10, 4))["evenements"]
    assert "sec_blocage:0000000000-26-000001" not in {e["id"] for e in Depot(tmp_path).lire("evenements")}  # le fil : 3 mois


def test_publication_du_calendrier(tmp_path):
    Depot(tmp_path).enregistrer([valider(e, date(2026, 10, 4)) for e in b.collecter(contexte(tmp_path, FauxInternet()))])
    publier(tmp_path, {}, set(), MAINTENANT)
    c = json.loads((tmp_path / "app" / "calendrier.json").read_text(encoding="utf-8"))
    assert len(c["lignes"]) == 7 and c["lignes"][0]["compagnie"] == "Bending Spoons S.p.A."
    assert "0 point dans la note" in c["explication"]


def test_finra_la_vraie_raison():
    assert SOURCES["finra"].ecartee.startswith("Ses conditions d'utilisation interdisent les robots et l'usage commercial")
    assert SOURCES["sec_blocage"].ecartee is None
