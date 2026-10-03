"""Tests du lecteur 13F sur les VRAIS dépôts de 5 fonds (2e trimestre 2026 comparé au 1er).

Fichiers officiels gardés tels quels (compressés) ; l'index du 14 août et les tables « fails-to-deliver » sont
réduits à quelques lignes, intactes. La page qui liste les tables « fails-to-deliver » est refaite (2 liens).
"""

import gzip
import io
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from radar.collecteurs import fonds13f as f
from radar.collecteurs.sec import ARCHIVES, DepotSec, Symboles
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures"
D = F / "13f"
JOUR = date(2026, 10, 2)
DEPOTS = {  # fonds -> (dépôt T2, table T2, dépôt T1, table T1)
    1067983: ("0001193125-26-352200", "56757.xml", "0001193125-26-226661", "53405.xml"),
    1536411: ("0001536411-26-000006", "form13f_20260630.xml", "0001536411-26-000004", "form13f_20260331.xml"),
    898286: ("0001140361-26-033187", "informationtable.xml", "0001140361-26-021351", "informationtable.xml"),
    1166559: ("0001104659-26-097175", "infotable.xml", "0001104659-26-062592", "infotable.xml"),
    2026053: ("0001172661-26-003790", "infotable.xml", "0001172661-26-002339", "infotable.xml"),
}


def lire(nom):
    return gzip.decompress((D / f"{nom}.gz").read_bytes())


def symboles_sec():
    return Symboles(json.loads(gzip.decompress((F / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())))


def table_cusip():
    table = {}
    for nom in ("cnsfails202608b.txt", "cnsfails202609a.txt"):
        for ligne in lire(nom).decode("latin-1").splitlines()[1:]:
            p = ligne.split("|")
            table[p[1]] = (p[2], p[4])
    return table


def evenements(cik):
    acc, tab, acc0, tab0 = DEPOTS[cik]
    depot = DepotSec(acc, "13F-HR", "2026-08-14", "", [(str(cik), "x")])
    return [valider(e, JOUR) for e in f.evenements_13f(
        cik, depot, lire(f"{acc}.{tab}"), f.lire_couverture(lire(f"{acc}.primary_doc.xml")),
        f.lire_couverture(lire(f"{acc0}.primary_doc.xml")), lire(f"{acc0}.{tab0}"), acc0, table_cusip(), symboles_sec())]


def test_valeurs_en_milliers_detectees():
    duquesne = f.lire_positions(lire("0001536411-26-000006.form13f_20260630.xml"))
    caisse = f.lire_positions(lire("0001140361-26-033187.informationtable.xml"))
    assert duquesne["en_milliers"] is True and caisse["en_milliers"] is False
    # Même action (10X Genomics), mêmes jours : le prix par action doit être le même une fois converti
    p1 = duquesne["positions"]["88025U109"]
    p2 = caisse["positions"]["88025U109"]
    assert abs(p1["valeur"] / p1["actions"] - p2["valeur"] / p2["actions"]) < 0.5


def test_berkshire_deuxieme_trimestre_2026():
    evs = evenements(1067983)
    assert all(e.badge == "officiel" for e in evs), [e.checks for e in evs]
    assert [e.title for e in evs[:3]] == [
        "Berkshire Hathaway achète 24,5 M d'actions d'Alphabet Inc. (classe A) (+45 %), trimestre au 30 juin 2026",
        "Berkshire Hathaway achète 23,6 M d'actions d'Alphabet Inc. (classe C) (+658 %), trimestre au 30 juin 2026",
        "Berkshire Hathaway vend 30,2 M d'actions de BANK OF AMERICA CORP (−6 %), trimestre au 30 juin 2026",
    ]
    assert [e.tickers for e in evs[:3]] == [["GOOGL"], ["GOOG"], ["BAC"]]
    assert (evs[0].occurred_on, evs[0].published_on, evs[0].direction, evs[2].direction) == ("2026-06-30", "2026-08-14", 1, -1)
    assert evs[0].official_url.endswith("/1067983/000119312526352200/0001193125-26-352200-index.htm")
    assert len(evs) == f.MAX_PAR_DEPOT


def test_duquesne_valeurs_converties_et_note():
    evs = evenements(1536411)
    alphabet = evs[0]
    assert alphabet.title.startswith("Duquesne Family Office achète 336 300 actions d'Alphabet Inc. (classe A) "
                                     "(nouvelle position)")
    assert 110e6 < alphabet.amount_min < 130e6  # 120 M$, pas 120 000 $ ni 120 G$
    assert "Le fonds déclare ses valeurs en milliers de dollars : converties en dollars." in alphabet.notes


def test_caisse_de_depot_seuil_plafonne():
    evs = evenements(898286)
    assert evs and all(e.amount_min >= f.PLAFOND for e in evs)  # 1 % de 70 G$ serait 700 M$ : plafonné à 250 M$
    assert evs[0].title.startswith("Caisse de dépôt et placement du Québec vend 3,3 M d'actions de NVIDIA CORP")


def test_sans_symbole_sur_on_garde_le_nom_officiel_du_13f():
    gates = evenements(1166559)
    brk = next(e for e in gates if "BERKSHIRE" in e.title)
    assert brk.tickers == [] and "BERKSHIRE HATHAWAY INC DEL (classe B)" in brk.title


def test_fractionnement_n_est_pas_un_achat():
    avant = {"positions": {"X": {"nom": "X CORP", "classe": "COM", "actions": 1_000_000, "valeur": 500e6}}, "total": 1e9}
    apres = {"positions": {"X": {"nom": "X CORP", "classe": "COM", "actions": 10_000_000, "valeur": 540e6}},
             "total": 1e9}
    assert f.mouvements(avant, apres) == []  # 10 pour 1 : 10 fois plus d'actions, prix 10 fois plus bas
    apres["positions"]["X"]["actions"] = 3_000_000  # vrai achat : 3 fois plus d'actions, prix inchangé
    apres["positions"]["X"]["valeur"] = 1_500e6
    assert [m["sorte"] for m in f.mouvements(avant, apres)] == ["hausse"]


def test_controle_detecte_des_trimestres_non_consecutifs():
    e = evenements(1067983)[0]
    e.data["trimestre_precedent"] = "2025-12-31"
    assert valider(e, JOUR).badge == "a_verifier"


class FauxInternet:
    def __init__(self):
        self.appels = []

    def get(self, url):
        self.appels.append(url)
        c = self._contenu(url)
        if c is None:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()

    def _contenu(self, url):
        if url == "https://www.sec.gov/files/company_tickers_exchange.json":
            return gzip.decompress((F / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())
        if url == f"{ARCHIVES}/edgar/daily-index/2026/QTR3/master.20260814.idx":
            return lire("master.20260814.idx")
        if url.startswith("https://data.sec.gov/submissions/CIK"):
            cik = int(url.rsplit("CIK", 1)[1].removesuffix(".json"))
            return lire(f"submissions_{cik}.json") if (D / f"submissions_{cik}.json.gz").exists() else None
        if url == f.PAGE_FTD:
            return (b'<a href="/files/data/fails-deliver-data/cnsfails202608b.zip">a</a>'
                    b'<a href="/files/data/fails-deliver-data/cnsfails202609a.zip">b</a>')
        if url.startswith("https://www.sec.gov/files/data/fails-deliver-data/cnsfails"):
            nom = url.rsplit("/", 1)[1].replace(".zip", ".txt")
            tampon = io.BytesIO()
            with zipfile.ZipFile(tampon, "w") as z:
                z.writestr(nom, lire(nom))
            return tampon.getvalue()
        if url.startswith(f"{ARCHIVES}/edgar/data/"):
            dossier, fichier = url.rsplit("/", 1)
            num = dossier.rsplit("/", 1)[1]
            acc = f"{num[:10]}-{num[10:12]}-{num[12:]}"
            chemin = D / f"{acc}.{fichier}.gz"
            return gzip.decompress(chemin.read_bytes()) if chemin.exists() else None
        return None


def test_lecteur_au_complet_sur_la_journee_du_14_aout(tmp_path):
    internet = FauxInternet()
    lecteur = {"sec_13f": f.collecter}
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 8, 17, 12, tzinfo=timezone.utc),
                       collecteurs=lecteur)
    assert rapport["sec_13f"] == {"ok": True, "nouveaux": 26, "modifies": 0, "inchanges": 0}, rapport
    # 8 Berkshire + 8 Duquesne + 8 Caisse + 2 Gates ; Pershing Square : T1 est un rapport combiné -> rien
    assert not any("/2026053/" in u and u.endswith("infotable.xml") and "002339" in u for u in internet.appels)
    assert sum(u.endswith(".zip") for u in internet.appels) == 2  # table des symboles téléchargée une seule fois
    assert not any("/1000097/" in u for u in internet.appels)  # fonds non suivi : aucune requête
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert {e["badge"] for e in fil} == {"officiel"}
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 8, 17, 16, tzinfo=timezone.utc),
                       collecteurs=lecteur)
    assert rapport["sec_13f"]["nouveaux"] == 0
