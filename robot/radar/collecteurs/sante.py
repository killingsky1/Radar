"""Santé financière d'une compagnie : les 9 critères de Piotroski (2000), calculés avec ses rapports annuels (XBRL),
lus sur l'API officielle de la SEC (data.sec.gov, « frames » : un fichier par donnée et par année, toutes les
compagnies d'un coup).

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

Rien plutôt que faux : un score seulement si les 9 critères se calculent. Une dette à long terme non déclarée compte
pour 0 (compagnie sans dette) et une émission d'actions non déclarée pour aucune émission. Mesuré au labo le 4 oct. 2026
sur 512 compagnies connues de Radar : 47 % ont alors les 9 critères (10 % si chaque donnée devait être déclarée) ; il
manque surtout la marge brute (biotechs, banques), la liquidité (banques) et les compagnies étrangères (normes IFRS).
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import emetteurs
from ..http import ErreurSource
from ..models import Evenement
from .rachats import annee_xbrl

VERSION = "sante-1"
FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{periode}.json"
ETUDE = "https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf"
# Pour chaque donnée, les étiquettes XBRL dans l'ordre de préférence : la première trouvée pour la compagnie compte.
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


def periodes(annee: int) -> dict:
    """t = l'exercice étudié, t1 = celui d'avant ; les bilans (instants) de fin t, t1 et t2."""
    return {"duree": {"t": f"CY{annee}", "t1": f"CY{annee - 1}"},
            "instant": {"t": f"CY{annee}Q4I", "t1": f"CY{annee - 1}Q4I", "t2": f"CY{annee - 2}Q4I"}}


def lire_frame(ctx, tag: str, periode: str) -> list[dict]:
    """Les lignes d'un fichier « frames » ; [] si la SEC n'a pas ce fichier (étiquette abandonnée : HTTP 404)."""
    try:
        r = json.loads(ctx.client.get(FRAMES.format(tag=tag, periode=periode)).contenu)
    except ErreurSource as exc:
        if str(exc).endswith("HTTP 404"):
            return []
        raise
    if (r.get("tag"), r.get("ccp"), r.get("uom")) != (tag, periode, "USD") or not isinstance(r.get("data"), list):
        raise RuntimeError(f"réponse inattendue de l'API de la SEC pour {tag} {periode} (format changé ?)")
    return r["data"]


def collecter(ctx) -> list[Evenement]:
    """Chaque matin : les données des 9 critères pour les compagnies connues de Radar (fiches SEC, voir emetteurs.py).
    Le fichier n'est réécrit que s'il change."""
    annee = annee_xbrl(ctx.maintenant.date())
    connus = {int(f["cik"]) for f in emetteurs.charger(ctx.donnees).values() if f.get("cik")}
    par_cik: dict = {}
    p = periodes(annee)
    for genre, groupe in (("duree", DUREE), ("instant", INSTANT)):
        for concept, tags in groupe.items():
            for cle, periode in p[genre].items():
                for tag in tags:
                    for x in lire_frame(ctx, tag, periode):
                        if x.get("cik") not in connus or x.get("val") is None:
                            continue
                        d = par_cik.setdefault(str(x["cik"]), {})
                        valeurs = d.setdefault(cle, {})
                        if concept in valeurs:
                            continue  # une étiquette préférée a déjà donné cette donnée
                        valeurs[concept] = x["val"]
                        if (concept, cle) == ("benefice", "t"):  # le rapport annuel de l'exercice étudié
                            d.update({"accn": x.get("accn"), "debut": x.get("start"), "fin": x.get("end")})
    nouveau = {"version": VERSION, "cadre": f"CY{annee}", "par_cik": par_cik}
    c = chemin(ctx.donnees)
    if not c.exists() or json.loads(c.read_text(encoding="utf-8")) != nouveau:
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
    if not c.exists():
        return {}
    x = json.loads(c.read_text(encoding="utf-8"))
    ciks = {s: f.get("cik") for s, f in emetteurs.charger(donnees).items()}
    par_symbole = {}
    for s in symboles_listes:
        cik = ciks.get(s)
        v = x["par_cik"].get(str(cik)) if cik else None
        r = criteres(v) if v else None
        if r is None or not v.get("accn"):
            continue
        accn = v["accn"]
        par_symbole[s] = {"cik": cik, "f_score": sum(r["criteres"].values()), **r, "debut": v.get("debut"),
                          "fin": v.get("fin"), "accn": accn,
                          "lien": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{accn}-index.htm"}
    return {"version": x.get("version", VERSION), "cadre": x["cadre"], "etude": ETUDE,
            "source": "https://data.sec.gov/api/xbrl/frames/", "par_symbole": par_symbole}
