"""Type des émetteurs sur de VRAIES fiches SEC (data.sec.gov/submissions, lues le 3 octobre 2026) :
un fonds fermé (SWZ), une compagnie (GME), une BDC (KBDC), une compagnie qui dépose des N-PX (AFL)."""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from radar import emetteurs as em
from radar.collecteurs.sec import Symboles
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import Contexte

F = Path(__file__).parent / "fixtures" / "sec"
CIK = {"SWZ": 813623, "GME": 1326380, "KBDC": 1747172, "AFL": 4977}


def fiche(cik):
    return gzip.decompress((F / "emetteurs" / f"submissions_{cik}.json.gz").read_bytes())


def symboles_sec():
    return Symboles(json.loads(gzip.decompress((F / "company_tickers_exchange_complet.json.gz").read_bytes())))


class FauxInternet:
    def __init__(self):
        self.appels = []

    def get(self, url):
        self.appels.append(url)
        for cik in CIK.values():
            if url == f"https://data.sec.gov/submissions/CIK{cik:010d}.json":
                c = fiche(cik)
                return type("T", (), {"contenu": c, "sha256": empreinte(c)})()
        raise ErreurSource(f"{url} : HTTP 404")


def contexte(tmp_path, jour=datetime(2026, 10, 3, 3, 17, tzinfo=timezone.utc), avec_symboles=True):
    ctx = Contexte(client=FauxInternet(), maintenant=jour, donnees=tmp_path)
    if avec_symboles:
        ctx.cache["sec_symboles"] = symboles_sec()
    return ctx


def test_seuls_les_rapports_de_fonds_font_un_fonds():
    assert em.classer(json.loads(fiche(CIK["SWZ"]))) == (
        "fonds", ["N-CEN", "N-CSR", "N-CSR/A", "N-CSRS", "NPORT-P", "NPORT-P/A"])
    assert em.classer(json.loads(fiche(CIK["GME"])))[0] == "compagnie"
    kbdc = json.loads(fiche(CIK["KBDC"]))
    assert "N-2" in kbdc["filings"]["recent"]["form"] and em.classer(kbdc)[0] == "compagnie"  # une BDC reste
    afl = json.loads(fiche(CIK["AFL"]))
    assert "N-PX" in afl["filings"]["recent"]["form"] and em.classer(afl)[0] == "compagnie"  # N-PX : pas un fonds


def test_fiches_lues_une_fois_puis_relues_apres_90_jours(tmp_path):
    ctx = contexte(tmp_path)
    bilan = em.rafraichir(ctx, {"SWZ", "GME", "KBDC", "AFL", "ZZZZ"})  # ZZZZ : pas dans la liste de la SEC
    assert bilan == {"lues": 4, "erreurs": 0}
    connus = em.charger(tmp_path)
    assert connus["SWZ"]["type"] == "fonds" and connus["SWZ"]["cik"] == 813623
    assert {s: f["type"] for s, f in connus.items() if s != "SWZ"} == {"GME": "compagnie", "KBDC": "compagnie",
                                                                       "AFL": "compagnie"}
    assert em.fonds(tmp_path) == {"SWZ"}
    ctx2 = contexte(tmp_path, datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert em.rafraichir(ctx2, {"SWZ", "GME"}) == {"lues": 0, "erreurs": 0} and ctx2.client.appels == []
    ctx3 = contexte(tmp_path, datetime(2027, 1, 2, tzinfo=timezone.utc))  # 91 jours plus tard : relues
    assert em.rafraichir(ctx3, {"SWZ"}) == {"lues": 1, "erreurs": 0}
    assert em.charger(tmp_path)["SWZ"]["lu"] == "2027-01-02"


def test_fiche_illisible_garde_l_ancienne_valeur(tmp_path):
    ctx = contexte(tmp_path)
    em.rafraichir(ctx, {"SWZ"})
    ctx_panne = contexte(tmp_path, datetime(2027, 1, 2, tzinfo=timezone.utc))
    ctx_panne.client.get = lambda url: (_ for _ in ()).throw(ErreurSource("HTTP 503"))
    assert em.rafraichir(ctx_panne, {"SWZ"}) == {"lues": 0, "erreurs": 1}
    assert em.charger(tmp_path)["SWZ"]["type"] == "fonds"


def test_sans_la_liste_de_la_sec_rien_n_est_lu(tmp_path):
    ctx = contexte(tmp_path, avec_symboles=False)
    assert em.rafraichir(ctx, {"SWZ"})["lues"] == 0 and ctx.client.appels == []
