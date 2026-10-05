"""Essai hors ligne de labo/tournoi/donnees.py : faux Internet qui sert les VRAIS jeux de données de la SEC gardés pour
les tests du robot (2023-2025), des fichiers d'échecs d'essai, des actions en circulation, un 13D et des frames d'essai.
Puis des vérifications précises sur les sorties (et des cas faits à la main pour les routiniers, les groupes, le bilan)."""
import gzip
import io
import json
import os
import shutil
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

ICI = Path(__file__).parent
TMP = ICI / "tmp"
shutil.rmtree(TMP, ignore_errors=True)
os.environ.update({"TOURNOI_ROBOT": "/home/user/radar-labo/robot", "TOURNOI_CACHE": str(TMP / "cache"),
                   "TOURNOI_SORTIE": str(TMP / "sortie"), "TOURNOI_ESSAI": "1"})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import donnees as d  # noqa: E402
from radar.collecteurs import inities, prix_sec, sec  # noqa: E402

FIX = Path("/home/user/radar-labo/robot/tests/fixtures/lotL/jeux")
ok = []


def verifier(nom, condition, detail=""):
    ok.append(bool(condition))
    print(f"{'OK    ' if condition else 'ÉCHEC '} {nom} {detail}")


def zip_vide():
    t = io.BytesIO()
    with zipfile.ZipFile(t, "w") as z:
        z.writestr("SUBMISSION.tsv", "ACCESSION_NUMBER\tFILING_DATE\tDOCUMENT_TYPE\tISSUERCIK\tISSUERNAME\tISSUERTRADINGSYMBOL\tAFF10B5ONE\n")
        z.writestr("NONDERIV_TRANS.tsv", "ACCESSION_NUMBER\tNONDERIV_TRANS_SK\tSECURITY_TITLE\tTRANS_DATE\tTRANS_CODE\tTRANS_SHARES\t"
                   "TRANS_PRICEPERSHARE\tTRANS_ACQUIRED_DISP_CD\tSHRS_OWND_FOLWNG_TRANS\tDIRECT_INDIRECT_OWNERSHIP\n")
        z.writestr("REPORTINGOWNER.tsv", "ACCESSION_NUMBER\tRPTOWNERCIK\tRPTOWNERNAME\tRPTOWNER_RELATIONSHIP\tRPTOWNER_TITLE\n")
    return t.getvalue()


# Les vrais événements des fichiers de test, pour fabriquer des prix cohérents
depots = {}
for z in sorted(FIX.glob("*.zip")):
    depots.update(d.lire_ds(z.read_bytes()))
EVS = d.faire_evenements(depots)
SYMBOLES = sorted({e["symbole"] for e in EVS if e["symbole"]})
CIKS = sorted({e["cik"] for e in EVS})

# Fichiers d'échecs d'essai : de 2023-01 à 2026-09, chaque jour ouvrable ; SPY monte de 0,01 % par jour, les autres
# symboles ont un prix fixe 10 $ sauf GME (20 $ puis 22 $ après le 2025-04-10) ; IWM, IVV, VOO pareils à SPY.
CLES = [f"{a}{m:02d}{h}" for a in range(2023, 2027) for m in range(1, 13) for h in "ab" if f"{a}{m:02d}" <= "202609"]


def ftd(cle):
    a, m, h = int(cle[:4]), int(cle[4:6]), cle[6]
    j0 = date(a, m, 1 if h == "a" else 16)
    j1 = date(a, m, 15) if h == "a" else (date(a + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
    lignes = [prix_sec.ENTETE]
    j = j0
    while j <= j1:
        if j.weekday() < 5:
            n = (j - date(2023, 1, 1)).days
            for s in ("SPY", "IVV", "VOO", "IWM"):
                lignes.append(f"{j:%Y%m%d}|CUSIP{s}|{s}|1000|{s} ETF|{400 * 1.0001 ** n:.4f}")
            for s in SYMBOLES:
                if n % 3 == 0:  # un prix tous les 3 jours seulement, comme une petite compagnie
                    p = 22.0 if (s == "GME" and j >= date(2025, 4, 10)) else 20.0 if s == "GME" else 10.0
                    lignes.append(f"{j:%Y%m%d}|CUSIP{s}|{s}|500|{s}|{p:.2f}")
        j += timedelta(days=1)
    t = io.BytesIO()
    with zipfile.ZipFile(t, "w") as z:
        z.writestr(f"cnsfails{cle}.txt", "\n".join(lignes) + "\n")
    return t.getvalue()


CIK_13D = next(e["cik"] for e in EVS if e["symbole"] == "GME")
MASTER = ("Description: Master Index\n\nCIK|Company Name|Form Type|Date Filed|Filename\n" + "-" * 40 + "\n"
          f"{CIK_13D}|GAMESTOP CORP|SC 13D|2025-03-20|edgar/data/{CIK_13D}/0000000000-25-000001.txt\n"
          f"999999|FONDS EXEMPLE|SC 13D|2025-03-20|edgar/data/{CIK_13D}/0000000000-25-000001.txt\n"
          f"{CIK_13D}|GAMESTOP CORP|10-K|2025-03-25|edgar/data/{CIK_13D}/0000000000-25-000002.txt\n")
APPELS = []


def servir(url):
    APPELS.append(url)
    if url == inities.PAGE:
        return "".join(f'<a href="/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip">x</a>'
                       for q in d.trimestres("2012q1", "2026q2")).encode()
    if url.endswith("_form345.zip"):
        q = url.rsplit("/", 1)[1][:6]
        return (FIX / f"{q}_form345.zip").read_bytes() if (FIX / f"{q}_form345.zip").exists() else zip_vide()
    if url == prix_sec.PAGE:
        return "".join(f'<a href="/files/data/fails-deliver-data/cnsfails{c}.zip">x</a>' for c in CLES).encode()
    if "cnsfails" in url:
        return ftd(url.rsplit("cnsfails", 1)[1][:7])
    if "companyconcept" in url:
        cik = int(url.split("CIK")[1][:10])
        return json.dumps({"units": {"shares": [{"end": "2024-12-31", "val": 5_000_000, "filed": "2025-02-14"},
                                                {"end": "2025-06-30", "val": 6_000_000, "filed": "2025-08-10"}]}}).encode() \
            if str(cik) in CIKS else None
    if url.endswith("master.idx"):
        return MASTER.encode() if "/2025/QTR1/" in url else b"CIK|Company Name|Form Type|Date Filed|Filename\n"
    if "/frames/" in url:
        concept, periode = url.split("/us-gaap/")[1].split("/USD/")
        periode = periode.removesuffix(".json")
        if concept == "Assets" and periode == "CY2024Q4I":
            return json.dumps({"data": [{"cik": int(CIK_13D), "end": "2024-12-31", "val": 123456, "accn": "x"}]}).encode()
        return None
    return None


def faux_brut(url, nom=None):
    if nom and (d.CACHE / nom).exists():
        return (d.CACHE / nom).read_bytes()
    c = servir(url)
    if c is None:
        raise d.ErreurSource(f"{url} : HTTP 404")
    if nom:
        (d.CACHE / nom).parent.mkdir(parents=True, exist_ok=True)
        (d.CACHE / nom).write_bytes(c)
    return c


def faux_ou_rien(url):
    return servir(url)


d.brut, d.ou_rien = faux_brut, faux_ou_rien
d.main()


def lire(ch):
    with gzip.open(ch, "rt", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


S, C = TMP / "sortie", TMP / "cache" / "coffre"
dec, cof = lire(S / "evenements.jsonl.gz"), lire(C / "evenements.jsonl.gz")
verifier("Découverte : seulement les dépôts du 2023-07-01 au 2026-06-30",
         dec and all("2023-07-01" <= e["depot"] <= "2026-06-30" for e in dec), f"({len(dec)} infos)")
verifier("Coffre-fort : seulement 2016 à juin 2023, et dans le cache (pas dans la sortie)",
         cof and all("2016-01-01" <= e["depot"] <= "2023-06-30" for e in cof) and not (S / "coffre").exists(),
         f"({len(cof)} infos)")
verifier("Aucune info en double entre découverte et coffre-fort", not ({e["id"] for e in dec} & {e["id"] for e in cof}))
verifier("Toutes les infos des fichiers de test (2023-2025) sont là",
         len(dec) + len(cof) == sum(1 for e in EVS if e["depot"] >= "2016-01-01"), f"({len(dec) + len(cof)} / {len(EVS)})")
gme = next(e for e in dec if e["symbole"] == "GME" and e["sens"] == "achat" and e["depot"] == "2025-04-07")
verifier("GME, achat de Ryan Cohen du 2025-04-07 : 500 000 actions à 21,55 $",
         gme["actions"] == 500000 and gme["prix_moyen"] == 21.55 and gme["montant"] == 10775000.0, str(gme["montant"]))
verifier("GME : clôture d'avant le dépôt = 20 $ (prix d'essai), au plus 30 jours avant",
         gme["cloture_avant"] and gme["cloture_avant"][1] == 20.0 and gme["cloture_avant"][0] < "2025-04-07",
         str(gme["cloture_avant"]))
verifier("GME : actions en circulation = le fait DÉPOSÉ avant (5 000 000, pas celui déposé en août)",
         gme["actions_circulation"] == 5_000_000 and gme["valeur_m"] == 100.0, f"{gme['actions_circulation']} {gme['valeur_m']}")
verifier("GME : le 13D du 2025-03-20 compte dans les 90 jours avant", gme["13d_90j"] == 1 and gme["13g_90j"] == 0)
verifier("GME : 1 initié dans le groupe de 30 jours", gme["groupe_30j"] == 1)
fin = [json.loads(l) for l in gzip.open(S / "finances.jsonl.gz", "rt")]
verifier("Finances : l'actif de GME fin 2024, utilisable 90 jours après", any(
    x["cik"] == CIK_13D and x["faits"]["Assets"][0][1:3] == ["2024-12-31", 123456] and x["faits"]["Assets"][0][4] == "2025-03-31"
    for x in fin), str(fin[:1])[:200])
px = {x["s"]: x for x in lire(S / "prix.jsonl.gz")}
verifier("Prix : SPY, IVV, VOO, IWM et les symboles avec un achat", {"SPY", "IVV", "VOO", "IWM", "GME"} <= set(px))
spy = px["SPY"]
i = spy["d"].index(20250404)
n_reg = (date(2025, 4, 7) - date(2023, 1, 1)).days
verifier("Prix : le prix du règlement du lundi est rangé à la clôture du vendredi",
         abs(spy["p"][i] - 400 * 1.0001 ** n_reg) < 0.01, f"{spy['p'][i]:.4f} contre {400 * 1.0001 ** n_reg:.4f}")
verifier("Prix de la découverte : à partir de juillet 2022 seulement", min(spy["d"]) >= 20220701)
cal = json.loads((S / "calendrier.json").read_text())
verifier("Calendrier des clôtures trié, sans fin de semaine", cal == sorted(cal) and all(
    date.fromisoformat(x).weekday() < 5 for x in cal))
res = json.loads((S / "resume.json").read_text())
verifier("Résumé : nombres seulement pour le coffre-fort (aucun rendement)", set(res["coffre"]) == {
    "evenements", "achats", "symboles_prix", "compagnies_finances", "compagnies_13"})
avant = len(APPELS)
d.main()  # 2e passage : tout vient du cache
verifier("Le 2e passage relit le cache : aucune nouvelle requête", len(APPELS) == avant, f"({len(APPELS) - avant} nouvelles)")
verifier("Le 2e passage donne exactement les mêmes infos", lire(S / "evenements.jsonl.gz") == dec)

# ---- Cas faits à la main ----
def ev(id_, sens, depot, cik, initie, symbole="TST", j=None):
    return {"id": id_, "sens": sens, "depot": depot, "jour_premier": j or depot, "cik": cik, "symbole": symbole,
            "inities": [{"cik": initie, "nom": "X", "roles": ["administrateur"], "titre": ""}]}


hist = [("7", "1", 2021, 3, "2021-03-05"), ("7", "1", 2022, 3, "2022-03-04"), ("7", "1", 2023, 3, "2023-03-03"),
        ("8", "1", 2021, 3, "2021-03-05"), ("8", "1", 2022, 3, "2022-03-04"), ("8", "1", 2023, 3, "2024-05-01")]
a, b = ev("a", "achat", "2024-04-02", "1", "7"), ev("b", "achat", "2024-04-02", "1", "8")
d.ajouter_routiniers([a, b], hist)
verifier("Routinier : même mois (mars) en 2021, 2022 et 2023 → routinier", a["routinier"] and a["mois_routine"] == [3])
verifier("Routinier : la ligne de 2023 déposée APRÈS l'info ne compte pas → pas routinier", not b["routinier"])
x = [ev("1", "achat", "2024-01-01", "5", "A"), ev("2", "achat", "2024-01-20", "5", "B"), ev("3", "achat", "2024-02-15", "5", "C"),
     ev("4", "vente", "2024-02-10", "5", "D"), ev("5", "achat", "2024-03-01", "6", "A")]
d.ajouter_contexte(x)
verifier("Groupe 30 jours : B (A à 19 jours) → 2 ; C (B à 26 jours, A à 45) → 2", x[1]["groupe_30j"] == 2 and x[2]["groupe_30j"] == 2)
verifier("Ventes 90 jours avant C : 1 ; achats 90 jours avant C : 2", x[2]["ventes_90j"] == 1 and x[2]["achats_90j"] == 2)
verifier("Historique : A a 1 achat avant celui du 2024-03-01 (autre compagnie) ; même compagnie : aucun",
         x[4]["historique"]["achats_avant"] == 1 and x[4]["historique"]["jours_depuis_achat_meme_cie"] is None)

p = d.Prix()
cloture = {"20240102": "20231229", "20240103": "20240102", "20240201": "20240131", "20240202": "20240201",
           "20240305": "20240304", "20240306": "20240305"}
p.ajouter_fichier(["20240103|C1|ZZZ|10|Z|10.00", "20240202|C1|ZZZ|10|Z|12.00", "20240306|C1|ZZZ|10|Z|9.00",
                   "20240103|S|SPY|10|S|100.00", "20240202|S|SPY|10|S|101.00", "20240306|S|SPY|10|S|102.00"],
                  None, cloture)
p.trier()
verifier("Prix.premier / dernier avec tolérance",
         p.premier("ZZZ", "2024-01-01", 10)[0] == "2024-01-02" and p.dernier("ZZZ", "2024-02-20", 30)[1] == 12.0
         and p.premier("ZZZ", "2024-02-06", 10) is None)
e1 = ev("e1", "achat", "2024-01-01", "9", "Q", "ZZZ")
e2 = ev("e2", "achat", "2024-04-15", "9", "Q", "ZZZ")
e3 = ev("e3", "achat", "2024-02-20", "9", "Q", "ZZZ")
d.ajouter_bilan_initie([e1, e2, e3], p)
attendu = round((12 / 10 - 1) - (101 / 100 - 1), 4)
verifier("Bilan de l'initié : l'achat de janvier (+20 % contre +1 % pour SPY) compte pour celui d'avril",
         e2["bilan_initie"] == {"mesures": 1, "ecart_moyen": attendu, "part_gagnante": 1.0}, str(e2["bilan_initie"]))
verifier("Bilan : un achat de moins de 60 jours avant ne compte pas encore", e3["bilan_initie"]["mesures"] == 0)
treize = d.lire_13(MASTER, {CIK_13D})
verifier("13D : le dépôt est rangé sur la compagnie visée seulement (pas le fonds), le 10-K ignoré",
         treize == [["2025-03-20", "13D", [CIK_13D]]], str(treize))
print(f"\n{sum(ok)}/{len(ok)} vérifications réussies")
sys.exit(0 if all(ok) else 1)
