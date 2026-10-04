"""Santé financière d'une compagnie : les 9 critères de Piotroski (2000), calculés avec SON DERNIER RAPPORT ANNUEL
(10-K, ou 20-F / 40-F), aux dates exactes de son exercice, lus sur l'API officielle de la SEC (data.sec.gov,
« companyfacts » : tous les chiffres XBRL déposés par la compagnie, avec le rapport d'où vient chacun).

L'étude : J. D. Piotroski, « Value Investing: The Use of Historical Financial Statement Information to Separate Winners
from Losers », Journal of Accounting Research 38 (supplément, 2000), p. 1-41 (texte lu par le labo). Testée sur les
actions bon marché (les 20 % de la bourse au plus haut ratio valeur comptable / prix, 1976-1996) : y garder les
compagnies solides ajoutait au moins 7,5 % par an ; l'effet est surtout fort chez les petites et moyennes compagnies peu
suivies. L'auteur précise que ses 9 critères ne sont pas forcément les meilleurs. Montré sur la fiche : 0 point.

Les 9 critères (1 = bon signe), comme dans l'étude :
- ROA > 0 et CFO > 0 : bénéfice net et flux de trésorerie d'exploitation, divisés par l'actif du début de l'année ;
- ΔROA > 0 : le ROA monte ; ACCRUAL : CFO > ROA (des profits appuyés par de l'argent réel) ;
- ΔLEVER < 0 : la dette à long terme divisée par l'actif moyen baisse ; ΔLIQUID > 0 : le ratio de liquidité (actif à
  court terme / passif à court terme) monte ; EQ_OFFER : aucune action ordinaire émise pendant l'exercice ;
- ΔMARGIN > 0 : la marge brute (en % des ventes) monte ; ΔTURN > 0 : les ventes divisées par l'actif du début de
  l'année montent.

Les chiffres (refait le 4 oct. 2026 après la contre-vérification du labo) :
- l'exercice étudié (t) = le plus récent exercice complet (350 à 380 jours) dont un rapport annuel donne le bénéfice ;
  son rapport = le dernier déposé pour cet exercice (un rapport modifié remplace l'original) ;
- les chiffres de t et de l'exercice d'avant (t-1) sont ceux que CE rapport donne ; le bilan de fin t-2 (l'actif) vient
  de ce rapport s'il le donne, sinon du dernier rapport annuel déposé qui le donne ;
- un rapport trimestriel (10-Q) ou une circulaire (DEF 14A) ne compte jamais, même s'il répète un chiffre.
Avant ce correctif, les fichiers « frames » de la SEC donnaient le bilan le plus proche de la fin de l'année civile : un
bilan trimestriel pour les exercices qui ne finissent pas vers décembre (ex. LESL : 3 janvier 2026 au lieu du
4 octobre 2025), et le lien menait parfois à la circulaire de procuration (ex. GME : DEF 14A).

Rien plutôt que faux : un score seulement si les 9 critères se calculent. Une dette à long terme non déclarée compte
pour 0 (compagnie sans dette) et une émission d'actions non déclarée pour aucune émission.

Lu pour les compagnies des listes seulement (data/app/aujourdhui.json du passage précédent) : une fois par jour (date
UTC), et une compagnie qui vient d'entrer dans les listes au passage suivant. Un dossier par compagnie.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .. import emetteurs
from ..http import ErreurSource
from ..models import Evenement

VERSION = "sante-2"
DOSSIER = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ETUDE = "https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf"
ANNUELS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A"}
JOURS_EXERCICE = (350, 380)  # un exercice complet : 52 ou 53 semaines, ou une année
# Pour chaque donnée, les étiquettes XBRL dans l'ordre de préférence : la première que le rapport donne pour t compte,
# et la même sert pour t-1.
DUREE = {
    "benefice": ["NetIncomeLoss", "ProfitLoss", "IncomeLossFromContinuingOperations"],
    "flux": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "ventes": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
               "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "marge_brute": ["GrossProfit"],
    "cout_ventes": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "emission": ["ProceedsFromIssuanceOfCommonStock", "StockIssuedDuringPeriodValueNewIssues"],
}
INSTANT = {
    "actif": ["Assets"],
    "actif_court": ["AssetsCurrent"],
    "passif_court": ["LiabilitiesCurrent"],
    "dette_lt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
}
CRITERES = ["ROA", "CFO", "ΔROA", "ACCRUAL", "ΔLEVER", "ΔLIQUID", "EQ_OFFER", "ΔMARGIN", "ΔTURN"]


def chemin(donnees) -> Path:
    return Path(donnees) / "sec" / "sante_xbrl.json"


def lien(cik, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{accn}-index.htm"


def lire_dossier(ctx, cik) -> dict | None:
    """Le dossier XBRL de la compagnie ; None si la SEC n'en a pas (HTTP 404 : aucune donnée XBRL)."""
    try:
        d = json.loads(ctx.client.get(DOSSIER.format(cik=int(cik))).contenu)
    except ErreurSource as exc:
        if str(exc).endswith("HTTP 404"):
            return None
        raise
    if not isinstance(d, dict) or str(d.get("cik")).lstrip("0") != str(int(cik)) or not isinstance(d.get("facts"), dict):
        raise RuntimeError(f"réponse inattendue de l'API de la SEC pour le CIK {cik} (format changé ?)")
    return d


def _annuels(dossier: dict, tag: str) -> list[dict]:
    """Les chiffres en dollars US d'une étiquette qui viennent d'un rapport annuel."""
    faits = dossier.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
    return [f for f in faits if f.get("form") in ANNUELS and f.get("val") is not None and f.get("end") and f.get("accn")]


def _jours(f: dict) -> int:
    return (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days


def extraire(dossier: dict) -> dict:
    """Les chiffres des 9 critères tirés du dernier rapport annuel, aux dates de l'exercice de la compagnie ;
    {"rien": raison} si l'exercice ou son rapport manquent."""
    exercices = [f for tag in DUREE["benefice"] for f in _annuels(dossier, tag)
                 if f.get("start") and JOURS_EXERCICE[0] <= _jours(f) <= JOURS_EXERCICE[1]]
    if not exercices:
        return {"rien": "aucun bénéfice annuel dans un rapport annuel"}
    fin = max(f["end"] for f in exercices)
    ref = max((f for f in exercices if f["end"] == fin), key=lambda f: (f.get("filed", ""), f["accn"]))
    debut, accn = ref["start"], ref["accn"]
    d0 = date.fromisoformat(debut)
    avant = [f for f in exercices if f["accn"] == accn and d0 - timedelta(days=7) <= date.fromisoformat(f["end"]) < d0]
    if not avant:
        return {"rien": "le rapport ne donne pas l'exercice précédent"}
    debut1, fin1 = max((f["start"], f["end"]) for f in avant)
    d1 = date.fromisoformat(debut1)
    bilans_t2 = [f for f in _annuels(dossier, "Assets")
                 if not f.get("start") and d1 - timedelta(days=7) <= date.fromisoformat(f["end"]) < d1]
    if not bilans_t2:
        return {"rien": "aucun bilan de fin t-2 dans un rapport annuel"}
    fin2 = max(f["end"] for f in bilans_t2)

    def du_rapport(tag: str, debut_: str | None, fin_: str):
        faits = [f for f in _annuels(dossier, tag) if f["accn"] == accn and f["end"] == fin_ and f.get("start") == debut_]
        return faits[0]["val"] if faits else None

    t: dict = {}
    t1: dict = {}
    etiquettes: dict = {}
    for groupe, (p, p1) in ((DUREE, ((debut, fin), (debut1, fin1))), (INSTANT, ((None, fin), (None, fin1)))):
        for concept, tags in groupe.items():
            for tag in tags:
                x = du_rapport(tag, *p)
                if x is None:
                    continue
                etiquettes[concept], t[concept] = tag, x
                x1 = du_rapport(tag, *p1)
                if x1 is not None:
                    t1[concept] = x1
                break
    # L'actif de fin t-2 : de ce rapport s'il le donne, sinon du dernier rapport annuel déposé qui le donne
    a2 = max((f for f in bilans_t2 if f["end"] == fin2), key=lambda f: (f["accn"] == accn, f.get("filed", ""), f["accn"]))
    return {"rapport": {"accn": accn, "forme": ref["form"], "depose": ref.get("filed")},
            "debut": debut, "fin": fin, "debut1": debut1, "fin1": fin1, "fin2": fin2, "source_t2": a2["accn"],
            "etiquettes": etiquettes, "t": t, "t1": t1, "t2": {"actif": a2["val"]}}


def listes(donnees) -> list[str]:
    """Les symboles des listes publiées au passage précédent (hausse puis baisse)."""
    p = Path(donnees) / "app" / "aujourdhui.json"
    if not p.exists():
        return []
    a = json.loads(p.read_text(encoding="utf-8"))
    return [x["symbole"] for liste in ("hausse", "baisse") for x in a.get(liste, [])]


def collecter(ctx) -> list[Evenement]:
    """À chaque passage : le dossier XBRL des compagnies des listes qui n'ont pas encore été lues aujourd'hui (date UTC).
    Le fichier ne garde que les compagnies des listes ; il n'est réécrit que s'il change."""
    aujourdhui = ctx.maintenant.date().isoformat()
    ciks = {s: f.get("cik") for s, f in emetteurs.charger(ctx.donnees).items() if f.get("cik")}
    c = chemin(ctx.donnees)
    ancien = json.loads(c.read_text(encoding="utf-8")) if c.exists() else {}
    deja = ancien.get("par_cik", {}) if ancien.get("version") == VERSION else {}
    par_cik: dict = {}
    for s in listes(ctx.donnees):
        if s not in ciks or str(int(ciks[s])) in par_cik:
            continue
        cle = str(int(ciks[s]))
        if deja.get(cle, {}).get("lu") == aujourdhui:
            par_cik[cle] = deja[cle]
            continue
        dossier = lire_dossier(ctx, ciks[s])
        par_cik[cle] = {"lu": aujourdhui, **(extraire(dossier) if dossier else {"rien": "aucune donnée XBRL à la SEC"})}
    nouveau = {"version": VERSION, "par_cik": par_cik}
    if ancien != nouveau:
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(nouveau, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return []


def _ratio(n, d):
    return n / d if n is not None and d else None


def criteres(v: dict) -> dict | None:
    """Les 9 critères (1 ou 0) et les chiffres qui les donnent ; None si un seul critère ne se calcule pas."""
    t, t1, t2 = v.get("t", {}), v.get("t1", {}), v.get("t2", {})
    a0, a1, a2 = t.get("actif"), t1.get("actif"), t2.get("actif")
    roa, roa_avant = _ratio(t.get("benefice"), a1), _ratio(t1.get("benefice"), a2)
    cfo = _ratio(t.get("flux"), a1)
    dette0 = t.get("dette_lt", 0) if a0 else None  # non déclarée : pas de dette à long terme
    dette1 = t1.get("dette_lt", 0) if a1 else None
    levier = dette0 / ((a0 + a1) / 2) if dette0 is not None and a0 and a1 else None
    levier_avant = dette1 / ((a1 + a2) / 2) if dette1 is not None and a1 and a2 else None
    liquidite = _ratio(t.get("actif_court"), t.get("passif_court"))
    liquidite_avant = _ratio(t1.get("actif_court"), t1.get("passif_court"))
    emission = t.get("emission", 0) if a0 else None  # non déclarée : aucune action émise

    def marge(x: dict):
        brute = x.get("marge_brute")
        if brute is None and x.get("ventes") is not None and x.get("cout_ventes") is not None:
            brute = x["ventes"] - x["cout_ventes"]
        return _ratio(brute, x.get("ventes"))

    marge0, marge1 = marge(t), marge(t1)
    rotation, rotation_avant = _ratio(t.get("ventes"), a1), _ratio(t1.get("ventes"), a2)
    chiffres = {"roa": roa, "roa_avant": roa_avant, "cfo": cfo, "levier": levier, "levier_avant": levier_avant,
                "liquidite": liquidite, "liquidite_avant": liquidite_avant, "emission": emission,
                "marge": marge0, "marge_avant": marge1, "rotation": rotation, "rotation_avant": rotation_avant}
    if any(x is None for x in chiffres.values()):
        return None
    c = {"ROA": roa > 0, "CFO": cfo > 0, "ΔROA": roa > roa_avant, "ACCRUAL": cfo > roa, "ΔLEVER": levier < levier_avant,
         "ΔLIQUID": liquidite > liquidite_avant, "EQ_OFFER": emission <= 0, "ΔMARGIN": marge0 > marge1,
         "ΔTURN": rotation > rotation_avant}
    return {"criteres": {k: int(c[k]) for k in CRITERES}, "chiffres": {k: round(x, 6) for k, x in chiffres.items()}}


def pour_app(donnees, symboles_listes: list[str]) -> dict:
    """Le fichier de l'app (data/app/sante.json) : le score des compagnies des listes, seulement s'il est complet."""
    c = chemin(donnees)
    x = json.loads(c.read_text(encoding="utf-8")) if c.exists() else {}
    if x.get("version") != VERSION:
        return {}  # pas encore lu avec le rapport annuel : rien plutôt que l'ancien calcul
    ciks = {s: f.get("cik") for s, f in emetteurs.charger(donnees).items() if f.get("cik")}
    par_symbole = {}
    for s in symboles_listes:
        v = x["par_cik"].get(str(int(ciks[s]))) if s in ciks else None
        r = criteres(v) if v and v.get("rapport") else None
        if r is None:
            continue
        rapport = v["rapport"]
        par_symbole[s] = {"cik": int(ciks[s]), "f_score": sum(r["criteres"].values()), **r, "debut": v["debut"],
                          "fin": v["fin"], "accn": rapport["accn"], "forme": rapport["forme"], "depose": rapport["depose"],
                          "lien": lien(ciks[s], rapport["accn"])}
    return {"version": VERSION, "etude": ETUDE, "source": "https://data.sec.gov/api/xbrl/companyfacts/",
            "par_symbole": par_symbole}
