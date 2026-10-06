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
from collections import Counter
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


def faits_zip():
    """Faux companyfacts.zip : actions en circulation pour chaque compagnie ; pour GME, un actif CORRIGÉ en 2026 (la 1re
    version doit rester), un bénéfice annuel, un trimestre, un cumul de 6 mois (à écarter) et un fait d'un 8-K (à écarter)."""
    t = io.BytesIO()
    actions = {"shares": [{"end": "2024-12-31", "val": 5_000_000, "filed": "2025-02-14", "form": "10-K"},
                          {"end": "2025-06-30", "val": 6_000_000, "filed": "2025-08-10", "form": "10-Q"}]}
    with zipfile.ZipFile(t, "w") as z:
        for cik in CIKS:
            faits = {"dei": {"EntityCommonStockSharesOutstanding": {"units": actions}}}
            if cik == CIK_13D:
                faits["us-gaap"] = {
                    "Assets": {"units": {"USD": [
                        {"end": "2024-12-31", "val": 123456, "accn": "A1", "filed": "2025-03-25", "form": "10-K"},
                        {"end": "2024-12-31", "val": 999999, "accn": "A2", "filed": "2026-03-02", "form": "10-K"}]}},
                    "CommonStockSharesOutstanding": {"units": {"shares": [
                        {"end": "2024-12-31", "val": 4_900_000, "accn": "A1", "filed": "2025-03-25", "form": "10-K"},
                        {"end": "2024-12-31", "val": 4_800_000, "accn": "A2", "filed": "2026-03-02", "form": "10-K"},
                        {"end": "2025-03-31", "val": 4_700_000, "accn": "S1", "filed": "2025-04-20", "form": "S-1"}]}},
                    "NetIncomeLoss": {"units": {"USD": [
                        {"start": "2024-01-01", "end": "2024-12-31", "val": 5000, "accn": "A1", "filed": "2025-03-25", "form": "10-K"},
                        {"start": "2025-01-01", "end": "2025-06-30", "val": 2000, "accn": "Q2", "filed": "2025-08-10", "form": "10-Q"},
                        {"start": "2025-04-01", "end": "2025-06-30", "val": 1200, "accn": "Q2", "filed": "2025-08-10", "form": "10-Q"},
                        {"start": "2025-04-01", "end": "2025-06-30", "val": 7777, "accn": "E1", "filed": "2025-07-01", "form": "8-K"}]}}}
            z.writestr(f"CIK{int(cik):010d}.json", json.dumps({"cik": int(cik), "facts": faits}))
    return t.getvalue()


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
    if url == d.FAITS_ZIP:
        return faits_zip()
    if url.endswith("master.idx"):
        return MASTER.encode() if "/2025/QTR1/" in url else b"CIK|Company Name|Form Type|Date Filed|Filename\n"
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


S, C, R = TMP / "cache" / "decouverte", TMP / "cache" / "coffre", TMP / "sortie"
dec, cof = lire(S / "evenements.jsonl.gz"), lire(C / "evenements.jsonl.gz")
dec_p = [e for e in dec if e["depot"] >= "2023-07-01"]
dec_c = [e for e in dec if e["depot"] < "2023-07-01"]
verifier("Découverte : dépôts du 2023-07-01 au 2026-06-30, plus 1 an de contexte (dès le 2022-07-01)",
         dec_p and dec_c and all("2022-07-01" <= e["depot"] <= "2026-06-30" for e in dec), f"({len(dec_p)} + {len(dec_c)} de contexte)")
verifier("periode.json de la découverte : début, fin, contexte", json.loads((S / "periode.json").read_text()) ==
         {"debut": "2023-07-01", "fin": "2026-06-30", "contexte_depuis": "2022-07-01"})
verifier("periode.json du coffre-fort", json.loads((C / "periode.json").read_text()) ==
         {"debut": "2016-01-01", "fin": "2023-06-30", "contexte_depuis": "2015-01-01"})
verifier("Coffre-fort : seulement 2015 (contexte) à juin 2023, et dans le cache (pas dans la sortie)",
         cof and all("2015-01-01" <= e["depot"] <= "2023-06-30" for e in cof) and not (S / "coffre").exists() and not (R / "evenements.jsonl.gz").exists(),
         f"({len(cof)} infos)")
verifier("Aucune info de la période de découverte dans le coffre-fort", not ({e["id"] for e in dec_p} & {e["id"] for e in cof}))
verifier("Le contexte de la découverte = les dépôts du coffre-fort depuis le 2022-07-01, à l'identique",
         dec_c == [e for e in cof if e["depot"] >= "2022-07-01"])
verifier("Toutes les infos des fichiers de test (2023-2025) sont là",
         len(dec_p) + len(cof) == sum(1 for e in EVS if e["depot"] >= "2016-01-01"), f"({len(dec_p) + len(cof)} / {len(EVS)})")
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
gfi = next((x["faits"] for x in fin if x["cik"] == CIK_13D), {})
verifier("Finances : l'actif de GME fin 2024 = la 1re version (pas la correction de 2026), utilisable à sa date de dépôt",
         gfi.get("Assets") == [[None, "2024-12-31", 123456, "A1", "2025-03-25", "10-K"]], str(gfi.get("Assets")))
verifier("Finances : exercice et trimestre gardés ; cumul de 6 mois et fait d'un 8-K écartés",
         gfi.get("NetIncomeLoss") == [["2024-01-01", "2024-12-31", 5000, "A1", "2025-03-25", "10-K"],
                                      ["2025-04-01", "2025-06-30", 1200, "Q2", "2025-08-10", "10-Q"]], str(gfi.get("NetIncomeLoss")))
gac = next((x.get("actions") for x in fin if x["cik"] == CIK_13D), None)
verifier("Actions en circulation à part des finances en $ : 1re version au bilan (us-gaap, pas la correction ni le S-1) "
         "et page couverture (dei)",
         gac == {"CommonStockSharesOutstanding": [[None, "2024-12-31", 4_900_000, "A1", "2025-03-25", "10-K"]],
                 "EntityCommonStockSharesOutstanding": [[None, "2024-12-31", 5_000_000, None, "2025-02-14", "10-K"],
                                                        [None, "2025-06-30", 6_000_000, None, "2025-08-10", "10-Q"]]}
         and not {"CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"} & set(gfi), str(gac))
verifier("companyfacts.zip : une seule requête pour toutes les compagnies", sum(u == d.FAITS_ZIP for u in APPELS) == 1)
px = {x["s"]: x for x in lire(S / "prix.jsonl.gz")}
verifier("Prix : SPY, IVV, VOO, IWM et les symboles avec un achat", {"SPY", "IVV", "VOO", "IWM", "GME"} <= set(px))
spy = px["SPY"]
i = spy["d"].index(20250404)
n_reg = (date(2025, 4, 7) - date(2023, 1, 1)).days
verifier("Prix : le prix du règlement du lundi est rangé à la clôture du vendredi",
         abs(spy["p"][i] - 400 * 1.0001 ** n_reg) < 0.01, f"{spy['p'][i]:.4f} contre {400 * 1.0001 ** n_reg:.4f}")
verifier("Prix de la découverte : à partir de juillet 2015 (pour juger les achats passés des initiés)", min(spy["d"]) >= 20150701)
cal_dec = json.loads((S / "calendrier.json").read_text())
verifier("Calendrier : les fériés de la bourse qui sont des jours de règlement (Vendredi saint, Noël du faux jeu) ne sont "
         "pas des jours de bourse", not {"2024-03-29", "2025-04-18", "2024-12-25"} & set(cal_dec)
         and 20240329 not in spy["d"] and "2024-03-28" in cal_dec and "2024-04-01" in cal_dec)
spec = json.loads((R / "resume.json").read_text())["alignement_des_prix"]["jours_speciaux"]
verifier("Jours spéciaux : fériés retirés listés (Vendredi saint 2024) ; aucun jour de bourse sans règlement dans le faux jeu",
         "2024-03-29" in spec["feries_retires_du_calendrier"] and spec["jours_de_bourse_sans_reglement"] == []
         and spec["le_prix_range_a_A_est_de"] == "inconnu", str({k: v for k, v in spec.items() if k != "feries_retires_du_calendrier"}))


class PrixFixes:
    """Un prix par (symbole, jour) donné à la main, pour essayer verifier_jours_speciaux."""
    def __init__(self, p):
        self.p = p

    def dernier(self, s, jour, tol):
        return (jour, self.p[(s, jour)], "C") if (s, jour) in self.p else None


# Columbus Day 2024 (lundi 14 octobre) : la bourse est ouverte, pas de règlement. Règlements le vendredi 11 et le mardi 15.
# Le prix du règlement du 15 est rangé au 11 (A). S'il vaut la clôture du 14 (B), les achats du 14 en sont plus proches.
def achats_essai(jour, prix_paye, n=40):
    return [{"sens": "achat", "symbole": f"S{i}", "prix_moyen": prix_paye, "jour_premier": jour, "jour_dernier": jour}
            for i in range(n)]


reg_essai = ["20241010", "20241011", "20241015", "20241016"]
evs_essai = achats_essai("2024-10-11", 100.0) + achats_essai("2024-10-14", 110.0)
v_b = d.verifier_jours_speciaux(evs_essai, PrixFixes({(f"S{i}", "2024-10-11"): 110.0 for i in range(40)}), reg_essai)
v_a = d.verifier_jours_speciaux(evs_essai, PrixFixes({(f"S{i}", "2024-10-11"): 100.0 for i in range(40)}), reg_essai)
verifier("Jours spéciaux : Columbus Day trouvé ; prix rangé au vendredi = clôture du lundi → décalé ; = clôture du "
         "vendredi → bon", v_b["jours_de_bourse_sans_reglement"] == ["2024-10-14"]
         and v_b["le_prix_range_a_A_est_de"].startswith("B") and v_a["le_prix_range_a_A_est_de"] == "A (bon)",
         f"{v_b['le_prix_range_a_A_est_de']} / {v_a['le_prix_range_a_A_est_de']}")
cal = json.loads((S / "calendrier.json").read_text())
verifier("Calendrier des clôtures trié, sans fin de semaine", cal == sorted(cal) and all(
    date.fromisoformat(x).weekday() < 5 for x in cal))
res = json.loads((R / "resume.json").read_text())
verifier("Branche : seulement le résumé et le journal (les données restent dans le cache)",
         sorted(x.name for x in R.iterdir()) == ["journal.md", "resume.json"], str(sorted(x.name for x in R.iterdir())))
verifier("Résumé : nombres seulement pour le coffre-fort (aucun rendement)", set(res["coffre"]) == {
    "evenements", "evenements_contexte", "inities_avec_historique", "achats", "symboles_prix", "compagnies_finances",
    "compagnies_13", "compagnies_actions"})
compte_actions = Counter(k for x in fin for k, fs in (x.get("actions") or {}).items() if fs)
verifier("Résumé : compagnies avec des actions en circulation, comptées comme dans le fichier (au bilan : au moins GME)",
         res["decouverte"]["compagnies_actions"] == {"CommonStockSharesOutstanding": compte_actions["CommonStockSharesOutstanding"],
                                                     "EntityCommonStockSharesOutstanding": compte_actions["EntityCommonStockSharesOutstanding"]}
         and compte_actions["CommonStockSharesOutstanding"] >= 1 and compte_actions["EntityCommonStockSharesOutstanding"] >= 1,
         f"{res['decouverte']['compagnies_actions']} / {dict(compte_actions)}")
his = {x["initie"]: x["depots"] for x in lire(S / "historiques.jsonl.gz")}
acheteurs = {i["cik"] for e in dec_p if e["sens"] == "achat" for i in e["inities"]}
verifier("Historiques : un par initié qui achète dans la découverte", set(his) == acheteurs, f"{len(his)} / {len(acheteurs)}")
cohen = next(i["cik"] for i in gme["inities"])
lignes_cohen = his.get(cohen, [])
verifier("Historique de l'initié de GME : son achat du 2025-04-07 y est, trié, rien après juin 2026",
         any(r[0] == "2025-04-07" and r[3] == "achat" and r[2] == "GME" for r in lignes_cohen)
         and lignes_cohen == sorted(lignes_cohen) and all(r[0] <= "2026-06-30" for r in lignes_cohen), str(lignes_cohen[:3]))
tous_his = [r for v in his.values() for r in v]
verifier("Historiques : toutes compagnies et ventes comprises (pas seulement les achats de la période)",
         any(r[3] == "vente" for r in tous_his) and any(r[0] < "2023-07-01" for r in tous_his))
verifier("Résumé : les achats comptés sont ceux de la période (pas du contexte)",
         res["decouverte"]["achats"] == sum(e["sens"] == "achat" for e in dec_p)
         and res["decouverte"]["evenements_contexte"] == len(dec_c))
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
historiques = {}
for e in x:
    for i in e["inities"]:
        historiques.setdefault(i["cik"], []).append([e["depot"], e["cik"], e["symbole"], e["sens"], e["jour_premier"],
                                                     e["jour_premier"], 100.0, 10.0])
historiques["A"].append(["2009-06-01", "6", "TST", "achat", "2009-05-29", "2009-05-29", 50.0, 3.0])  # seulement dans l'historique
for v in historiques.values():
    v.sort()
d.ajouter_contexte(x, historiques)
verifier("Groupe 30 jours : B (A à 19 jours) → 2 ; C (B à 26 jours, A à 45) → 2", x[1]["groupe_30j"] == 2 and x[2]["groupe_30j"] == 2)
verifier("Ventes 90 jours avant C : 1 ; achats 90 jours avant C : 2", x[2]["ventes_90j"] == 1 and x[2]["achats_90j"] == 2)
verifier("Historique : A a 2 achats avant celui du 2024-03-01 (2024 ailleurs, et 2009 dans l'historique seulement) ; "
         "même compagnie : le 2009-06-01", x[4]["historique"]["achats_avant"] == 2
         and x[4]["historique"]["jours_depuis_achat_meme_cie"] == (date(2024, 3, 1) - date(2009, 6, 1)).days, str(x[4]["historique"]))
brut_ = {"acc1": {"s": ["2024-05-02", "77", "abc", "ABC Inc", None],
                  "l": [[1, "P", "2024-04-30", 100.0, 10.0, "A", 1100.0, "D", "Common Stock"],
                        [2, "S", "2024-04-30", 40.0, 12.0, "D", 1060.0, "D", "Common Stock"],
                        [3, "P", "2024-05-01", 0.0, 10.0, "A", 1060.0, "D", "Common Stock"]],
                  "p": [["501", "Initie Un", "Director", ""], ["502", "Fonds", "TenPercentOwner", ""]]}}
lh = sorted(d.lignes_historique(brut_))
verifier("Historique brut : un dépôt par sens et par déclarant (2 × 2), lignes à 0 action ignorées",
         lh == sorted([("501", "2024-05-02", "77", "ABC", "achat", "2024-04-30", "2024-04-30", 100.0, 10.0),
                       ("501", "2024-05-02", "77", "ABC", "vente", "2024-04-30", "2024-04-30", 40.0, 12.0),
                       ("502", "2024-05-02", "77", "ABC", "achat", "2024-04-30", "2024-04-30", 100.0, 10.0),
                       ("502", "2024-05-02", "77", "ABC", "vente", "2024-04-30", "2024-04-30", 40.0, 12.0)]), str(lh))
lignes_vides = [["2024-05-02", "77", None, "achat", None, None, 10.0, None],
                ["2024-05-02", "77", "ABC", "achat", "2024-05-01", "2024-05-01", 5.0, 3.0],
                ["2024-05-01", "77", "ABC", "vente", "2024-04-30", "2024-04-30", 5.0, 3.0]]
try:
    lignes_vides.sort(key=d.cle_historique)
    tri_ok = [r[0] for r in lignes_vides] == ["2024-05-01", "2024-05-02", "2024-05-02"] and lignes_vides[1][2] is None
except TypeError as exc:
    tri_ok = f"TypeError : {exc}"
verifier("Historique : des cases vides (symbole, dates) ne bloquent pas le tri (bug du 1er passage réel)", tri_ok is True, str(tri_ok))
verifier("Trimestre d'une date", (d.trimestre_de("2014-10-01"), d.trimestre_de("2015-03-31")) == ("2014q4", "2015q1"))

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
# ---- Dates des prix : un achat d'un jour doit être plus proche de la clôture de CE jour ----
import math  # noqa: E402
import random  # noqa: E402
hasard = random.Random(3)
jours_px = [x for x in (date(2024, 1, 1) + timedelta(days=i) for i in range(400)) if x.weekday() < 5]
cal_px = [int(f"{x:%Y%m%d}") for x in jours_px]
px = d.Prix()
niveau = 50.0
for j in cal_px:
    niveau *= math.exp(hasard.gauss(0, 0.02))
    px.d["XX"].append(j)
    px.p["XX"].append(niveau)
    px.q["XX"].append(0)
    px.c["XX"].append("C")
cloture = {d.iso(str(j)): float(v) for j, v in zip(px.d["XX"], px.p["XX"])}
isos = [d.iso(str(j)) for j in cal_px]


def achats(decalage):
    return [{"sens": "achat", "symbole": "XX", "jour_premier": isos[i], "jour_dernier": isos[i],
             "prix_moyen": cloture[isos[i + decalage]] * math.exp(hasard.gauss(0, 0.005))} for i in range(5, len(isos) - 5)]


bon = d.verifier_dates_prix(achats(0), px, cal_px)
verifier("Dates des prix : achats au prix du jour → bon alignement", bon["bon_alignement"] and bon["achats_compares"] > 200, str(bon))
mauvais = d.verifier_dates_prix(achats(1), px, cal_px)
verifier("Dates des prix décalées d'un jour → alerte (le lendemain est plus proche)",
         not mauvais["bon_alignement"] and min(mauvais["ecart_median_veille_jour_lendemain"],
                                               key=mauvais["ecart_median_veille_jour_lendemain"].get) == "1", str(mauvais))
verifier("Résumé : l'alignement des prix est publié", "alignement_des_prix" in res)

print(f"\n{sum(ok)}/{len(ok)} vérifications réussies")
sys.exit(0 if all(ok) else 1)
