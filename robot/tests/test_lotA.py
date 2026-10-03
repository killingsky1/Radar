"""Lot A, sur de VRAIES données du 3 octobre 2026 (tests/fixtures/lotA) :
- un site qui refuse le robot (l'état réel de LEGISinfo : réussite à 19 h 33 UTC, 403 à 20 h 28) ;
- un 403 isolé et passager (le vrai cas du Registre fédéral : 403 à 00 h 11, lecture normale ensuite) ;
- les 6 vrais groupes de doublons de formulaires 4 (3 septembre au 3 octobre 2026) ;
- l'info Elmet telle que publiée par la version 1 (titre et extrait)."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar.collecteurs import participations as pa
from radar.http import ErreurSource
from radar.models import Evenement
from radar.recoupement import marquer_doublons_form4
from radar.run import Contexte, executer
from radar.store import Depot

F = Path(__file__).parent / "fixtures" / "lotA"
F3D2 = Path(__file__).parent / "fixtures" / "lot3d2"
LUNDI = datetime(2026, 10, 5, 11, 7, tzinfo=timezone.utc)  # prochain passage « matin » qui lit LEGISinfo
URL_403 = "https://www.parl.ca/legisinfo/fr/projets-de-loi/json?parlsession=45-1 : HTTP 403"


class Robots:
    """Faux internet pour le robots.txt seulement : `reponse` = le texte du fichier, ou un code d'erreur HTTP."""

    def __init__(self, reponse):
        self.reponse, self.appels = reponse, []

    def get(self, url, entetes=None):
        self.appels.append(url)
        if isinstance(self.reponse, int):
            raise ErreurSource(f"{url} : HTTP {self.reponse}")
        return type("T", (), {"contenu": self.reponse.encode()})()


def lecteur(appels, refuse=True):
    def lire(ctx):
        appels.append(ctx.maintenant)
        if refuse:
            raise ErreurSource(URL_403)
        return []
    return lire


def avec_etat_reel(tmp_path):
    (tmp_path / "etat_sources.json").write_text(json.dumps({"legisinfo": json.loads((F / "etat_legisinfo.json").read_text())}))


def etat(tmp_path):
    return json.loads((tmp_path / "etat_sources.json").read_text())["legisinfo"]


def source(tmp_path):
    return {s["id"]: s for s in json.loads((tmp_path / "app" / "sources.json").read_text())}["legisinfo"]


# ---------- Sites qui refusent le robot ----------

def test_legisinfo_2e_refus_lundi_pause_de_7_jours(tmp_path):
    avec_etat_reel(tmp_path)  # le 403 du samedi 3 octobre, écrit avant cette règle, compte comme 1er refus
    appels = []
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, maintenant=LUNDI)
    r = etat(tmp_path)["refus"]
    assert r["confirme"] is True and r["code"] == 403 and r["essais"] == 2
    assert r["depuis"] == "2026-10-03T20:28:12+00:00" and r["prochain_essai"] == "2026-10-12T11:07:00+00:00"
    s = source(tmp_path)
    assert (s["statut"], s["libelle"]) == ("refusee", "Refusée par le site")
    assert s["explication"] == ("Le site refuse l'accès au robot (erreur 403) depuis le 3 octobre 2026 ; Radar respecte ce "
                                "refus et réessaie une fois le 12 octobre 2026.")
    # Pendant la pause, le site n'est plus sollicité du tout
    rapport = executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, maintenant=LUNDI + timedelta(days=3))
    assert len(appels) == 1 and rapport["legisinfo"] == {"ok": False, "refusee_depuis": "2026-10-03T20:28:12+00:00"}


def test_nouvel_essai_robots_txt_d_abord(tmp_path):
    avec_etat_reel(tmp_path)
    appels = []
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, maintenant=LUNDI)
    essai = LUNDI + timedelta(days=7)
    # robots.txt refusé (403) : la source n'est pas lue, nouvelle pause de 7 jours
    robots = Robots(403)
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, client=robots, maintenant=essai)
    assert robots.appels == ["https://www.parl.ca/robots.txt"] and len(appels) == 1
    assert etat(tmp_path)["refus"]["prochain_essai"] == (essai + timedelta(days=7)).isoformat()
    assert etat(tmp_path)["refus"]["robots"] == "robots.txt refusé ou illisible (HTTP 403)"
    # robots.txt qui interdit le chemin : pas lu non plus
    essai += timedelta(days=7)
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, client=Robots("User-agent: *\nDisallow: /legisinfo/\n"),
             maintenant=essai)
    assert len(appels) == 1 and etat(tmp_path)["refus"]["robots"] == "robots.txt ne permet pas"
    # robots.txt qui permet, et le site répond : la pause est finie, la source redevient OK
    essai += timedelta(days=7)
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels, refuse=False)},
             client=Robots("User-agent: *\nDisallow: /recherche/\n"), maintenant=essai)
    assert len(appels) == 2 and "refus" not in etat(tmp_path)
    assert source(tmp_path)["statut"] == "ok"


def test_un_403_isole_et_passager_est_tolere(tmp_path):
    """Le vrai cas du Registre fédéral (3 octobre 2026) : réussite à 00 h 05, 403 à 00 h 11, puis lecture normale."""
    (tmp_path / "etat_sources.json").write_text(json.dumps({"legisinfo": {"dernier_succes": "2026-10-03T00:05:04+00:00"}}))
    appels = []
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, maintenant=datetime(2026, 10, 3, 0, 11, 34, tzinfo=timezone.utc))
    assert etat(tmp_path)["refus"]["confirme"] is False and source(tmp_path)["statut"] == "ok"
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels, refuse=False)},
             maintenant=datetime(2026, 10, 3, 3, 17, tzinfo=timezone.utc))
    assert "refus" not in etat(tmp_path) and source(tmp_path)["statut"] == "ok"


def test_deux_refus_a_moins_d_une_heure_ne_comptent_qu_une_fois(tmp_path):
    t = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)
    appels = []
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, maintenant=t)
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, maintenant=t + timedelta(minutes=10))
    assert etat(tmp_path)["refus"]["essais"] == 1 and etat(tmp_path)["refus"]["confirme"] is False
    executer(tmp_path, collecteurs={"legisinfo": lecteur(appels)}, maintenant=t + timedelta(minutes=70))
    assert etat(tmp_path)["refus"]["confirme"] is True


def test_une_autre_erreur_n_est_pas_un_refus(tmp_path):
    def coupe(ctx):
        raise ErreurSource("https://www.parl.ca/legisinfo/ : HTTP 500")
    executer(tmp_path, collecteurs={"legisinfo": coupe}, maintenant=LUNDI)
    executer(tmp_path, collecteurs={"legisinfo": coupe}, maintenant=LUNDI + timedelta(hours=3))
    assert "refus" not in etat(tmp_path)


# ---------- Doublons de formulaires 4 (vraies infos) ----------

def infos_reelles():
    return [Evenement.from_dict(json.loads(l)) for l in (F / "form4_doublons.jsonl").read_text().splitlines()]


def test_doublons_reels_une_seule_ligne(tmp_path):
    Depot(tmp_path).enregistrer(infos_reelles())
    assert marquer_doublons_form4(tmp_path) == 16  # 6 groupes, 16 formulaires ; les 3 achats de GME ne bougent pas
    assert marquer_doublons_form4(tmp_path) == 0  # relancer ne change rien
    tous = {d["official_id"]: d for d in Depot(tmp_path).lire("evenements")}
    blackstone = [d for d in tous.values() if d["official_id"].startswith(("0001193125-26-4091", "0001193125-26-4092"))]
    gardee = [d for d in blackstone if not d["data"].get("meme_transaction_que")]
    assert len(blackstone) == 5 and len(gardee) == 1
    assert len(gardee[0]["data"]["aussi_declare_par"]) == 4
    assert all(d["data"]["meme_transaction_que"] == gardee[0]["id"] for d in blackstone if d is not gardee[0])
    adarx = tous["0001193125-26-408061:P"]  # George Simeon (administrateur) : déclaré en 1er
    assert adarx["data"]["aussi_declare_par"] == ["SR ONE CAPITAL MANAGEMENT, LLC"]
    assert tous["0001193125-26-408064:P"]["data"]["meme_transaction_que"] == adarx["id"]
    assert all(not d["data"].get("meme_transaction_que") and not d["data"].get("aussi_declare_par")
               for d in tous.values() if d["tickers"] == ["GME"])


def test_le_fil_montre_chaque_transaction_une_seule_fois(tmp_path):
    Depot(tmp_path).enregistrer(infos_reelles())
    executer(tmp_path, collecteurs={}, maintenant=datetime(2026, 10, 3, 20, 28, tzinfo=timezone.utc))
    fil = json.loads((tmp_path / "app" / "fil.json").read_text())
    assert len(fil) == 6 + 3  # une ligne par groupe de doublons + les 3 achats de GME
    assert len({json.dumps(sorted((t["date"], t["code"], t["actions"], t["prix"]) for t in e["data"]["transactions"]))
                for e in fil}) == 9


# ---------- Participations : titre et extraits au mot entier ----------

def test_titre_sans_parentheses_dans_des_parentheses():
    assert pa.titre("Elmet Group Co.", "War") == ("Elmet Group Co. : un 8-K dit que le ministère américain de la Guerre "
                                                  "(Défense) reçoit, détient ou revend des titres de la compagnie")
    assert pa.titre("X Corp", None).startswith("X Corp : un 8-K dit que le gouvernement américain reçoit")


def test_extraits_au_mot_entier_sur_le_vrai_document_elmet():
    texte = pa.texte_doc(gzip.decompress((F3D2 / "pos_dow_2026.gz").read_bytes()))
    trouves = pa.passages(texte)
    assert trouves and "$450 million redeemable preferred stock investment from the Department of War" in trouves[0]["extrait"]
    for t in trouves:
        coeur = t["extrait"].removeprefix("… ").removesuffix(" …")
        i = texte.find(coeur)
        assert i >= 0 and (i == 0 or texte[i - 1] == " ") and (i + len(coeur) == len(texte) or texte[i + len(coeur)] == " ")


def test_l_info_elmet_deja_publiee_est_corrigee_une_seule_fois(tmp_path):
    v1 = json.loads((F / "participation_elmet_v1.json").read_text())
    assert "(ministère de la Guerre (Défense))" in v1["title"]
    assert v1["data"]["documents"][0]["extraits"][0].endswith(" str …")
    Depot(tmp_path).enregistrer([Evenement.from_dict(v1)])
    ctx = Contexte(client=None, maintenant=datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc), donnees=tmp_path)
    corrigees = pa.corriger_anciennes(ctx)
    assert len(corrigees) == 1
    e = corrigees[0]
    assert e.title == ("Elmet Group Co. : un 8-K dit que le ministère américain de la Guerre (Défense) reçoit, détient ou "
                       "revend des titres de la compagnie")
    extrait = e.data["documents"][0]["extraits"][0]
    assert extrait.endswith(" 25.0% …") and dict(e.data["details"])["Extrait (EX-99.1)"] == extrait
    texte = pa.texte_doc(gzip.decompress((F3D2 / "pos_dow_2026.gz").read_bytes()))
    assert extrait.removeprefix("… ").removesuffix(" …") in texte  # toujours mot pour mot dans le document officiel
    Depot(tmp_path).enregistrer(corrigees)
    assert pa.corriger_anciennes(Contexte(client=None, maintenant=ctx.maintenant, donnees=tmp_path)) == []
