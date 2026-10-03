"""Trésor américain (Bureau of the Fiscal Service, données ouvertes « Fiscal Data ») : résultats des adjudications
d'obligations (2 à 30 ans ; indexées sur l'inflation « TIPS » ; à taux variable « FRN ») et solde mensuel du
gouvernement fédéral (état mensuel du Trésor, « MTS »).

API officielle, ouverte et sans compte (api.fiscaldata.treasury.gov : pas de robots.txt ; fiscaldata.treasury.gov :
« Allow: / »). Licence lue le 3 octobre 2026 : « The data is offered free, without restriction, and available to copy,
adapt, redistribute, or otherwise use for non-commercial or commercial purposes. »
- Les bons du Trésor (moins d'un an, plusieurs fois par semaine) ne sont pas montrés : emprunts de trésorerie.
- TreasuryDirect publie les résultats 2 minutes après l'adjudication, mais son robots.txt interdit tous les robots : on
  lit Fiscal Data, mis à jour vers 23 h UTC (calendrier officiel). La date d'une info reste celle de l'adjudication :
  les résultats officiels sont publiés le jour même.
- Comparaison : la moyenne des adjudications précédentes (6 au plus) de même sorte et de même durée de référence
  (réouvertures comprises), calculée sur les mêmes chiffres officiels. Aucune interprétation (« bonne » ou « mauvaise »).
- État mensuel : la 1re lecture est silencieuse (le mois déjà publié n'est pas une nouveauté) ; ensuite, chaque
  nouveau mois devient une info.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..models import Evenement
from ..validate import controle_source
from .gazette import details
from .regulateurs import canonique, deja

VERSION = "tresor-1"
API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
ADJUDICATIONS = API + ("v1/accounting/od/auctions_query?filter=security_type:in:(Note,Bond)&sort=-auction_date"
                       "&page[size]=300")
ETAT_MENSUEL = API + "v1/accounting/mts/mts_table_1?sort=-record_date&page[size]=60"
CALENDRIER = "https://api.fiscaldata.treasury.gov/services/calendar/release"
RESULTATS = "https://fiscaldata.treasury.gov/static-data/published-reports/auctions-query/results/"
PAGE_MTS = "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/"
ID_MTS = "015-BFS-2014Q1-13"  # l'état mensuel dans le calendrier officiel des publications
FENETRE_JOURS = 10
COMPARAISON = 6
TORONTO = ZoneInfo("America/Toronto")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")
MOIS_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
TERME = re.compile(r"(\d+)-Year(?: (\d+)-Month)?")


# ---------- Nombres et textes ----------

def nombre(x) -> float | None:
    if x in (None, "", "null"):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def virgule(v: float, decimales: int) -> str:
    return f"{v:,.{decimales}f}".replace(",", " ").replace(".", ",")


def milliards(v: float, decimales: int = 3) -> str:
    """44 000 000 000 -> « 44 G$ » ; 22 500 000 000 -> « 22,5 G$ » ; avec decimales=1 : 166 796 952 277 -> « 166,8 G$ »."""
    s = f"{v / 1e9:,.{decimales}f}".rstrip("0").rstrip(".")
    return s.replace(",", " ").replace(".", ",") + " G$"


def duree(terme: str) -> tuple[int, int]:
    m = TERME.fullmatch(terme or "")
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)


def duree_texte(terme: str) -> str:
    a, mo = duree(terme)
    return f"{a} an{'s' if a > 1 else ''}" + (f" et {mo} mois" if mo else "")


def sorte(x: dict) -> str:
    if x.get("inflation_index_security") == "Yes":
        return "TIPS"
    if x.get("floating_rate") == "Yes":
        return "FRN"
    return "nominale"


def famille(x: dict) -> tuple[str, int]:
    """Sorte et durée de référence : « 29-Year 10-Month » (réouverture) = 30 ans."""
    a, mo = duree(x.get("security_term"))
    return sorte(x), a + (1 if mo else 0)


def taux(x: dict) -> float | None:
    return nombre(x.get("high_discnt_margin")) if sorte(x) == "FRN" else nombre(x.get("high_yield"))


def resultat(x: dict) -> bool:
    return nombre(x.get("bid_to_cover_ratio")) is not None and bool(nombre(x.get("comp_accepted"))) \
        and taux(x) is not None


def parts(x: dict) -> dict[str, float | None]:
    """En % des offres compétitives acceptées (les 3 catégories officielles)."""
    comp = nombre(x.get("comp_accepted"))
    return {k: (nombre(x.get(f"{k}_accepted")) or 0) / comp * 100 if comp else None
            for k in ("indirect_bidder", "direct_bidder", "primary_dealer")}


def moyenne(valeurs: list[float]) -> float | None:
    return sum(valeurs) / len(valeurs) if valeurs else None


# ---------- Adjudications ----------

def adjudication(x: dict, historique: list[dict]) -> Evenement:
    s, t, btc, p = sorte(x), taux(x), nombre(x["bid_to_cover_ratio"]), parts(x)
    precedentes = [y for y in historique if famille(y) == famille(x) and y["auction_date"] < x["auction_date"]
                   and resultat(y)][:COMPARAISON]
    btc_moy = moyenne([nombre(y["bid_to_cover_ratio"]) for y in precedentes])
    ind_moy = moyenne([parts(y)["indirect_bidder"] for y in precedentes])
    n = len(precedentes)
    montant = nombre(x["offering_amt"])
    sur = f"sur {duree_texte(x['security_term'])}" + (" (réouverture)" if x.get("reopening") == "Yes" else "")
    demande = f"demande : {virgule(btc, 2)} fois l'offre"
    if s == "FRN":
        titre = f"Trésor américain : adjudication de {milliards(montant)} à taux variable {sur}, marge de " \
                f"{virgule(t, 3)} % ({demande})"
        nom_taux = "Marge retenue (taux variable)"
    elif s == "TIPS":
        titre = f"Trésor américain : adjudication de {milliards(montant)} indexés sur l'inflation (TIPS) {sur}, " \
                f"taux réel de {virgule(t, 3)} % ({demande})"
        nom_taux = "Taux réel retenu (le plus élevé accepté)"
    else:
        titre = f"Trésor américain : adjudication de {milliards(montant)} {sur} à {virgule(t, 3)} % ({demande})"
        nom_taux = "Taux retenu (le plus élevé accepté)"
    comparee = f" (moyenne des {n} précédentes : {{}})" if n else ""
    d = {"cusip": x["cusip"], "type": x["security_type"], "terme": x["security_term"], "sorte": s,
         "reference_ans": famille(x)[1], "reouverture": x.get("reopening") == "Yes", "adjudication": x["auction_date"],
         "emission": x.get("issue_date"), "montant_offert": montant, "taux": t, "demande_offre": btc,
         "offres_competitives_acceptees": nombre(x["comp_accepted"]),
         "acceptees": {k: nombre(x.get(f"{k}_accepted")) for k in ("indirect_bidder", "direct_bidder", "primary_dealer")},
         "parts": p, "precedentes": [{"adjudication": y["auction_date"], "cusip": y["cusip"],
                                      "document": y.get("pdf_filenm_comp_results"),
                                      "demande_offre": nombre(y["bid_to_cover_ratio"]),
                                      "part_indirecte": parts(y)["indirect_bidder"]} for y in precedentes],
         "demande_offre_moyenne": btc_moy, "part_indirecte_moyenne": ind_moy,
         "document": x.get("pdf_filenm_comp_results"), "heure_de_cloture": x.get("closing_time_comp"),
         "details": details(
             ("Montant offert", milliards(montant)), (nom_taux, f"{virgule(t, 3)} %"),
             ("Demande / offre", virgule(btc, 2) + (comparee.format(virgule(btc_moy, 2)) if n else "")),
             ("Acheteurs indirects", f"{virgule(p['indirect_bidder'], 1)} %"
              + (comparee.format(virgule(ind_moy, 1) + " %") if n else "")),
             ("Acheteurs directs", f"{virgule(p['direct_bidder'], 1)} %"),
             ("Courtiers primaires", f"{virgule(p['primary_dealer'], 1)} %"),
             ("Titre", f"{x['security_type']} {x['security_term']}, CUSIP {x['cusip']}"),
             ("Date d'émission", x.get("issue_date") or ""),
             ("Résultat officiel", x.get("pdf_filenm_comp_results") or ""))}
    return Evenement(
        source="tresor", official_id=f"{x['cusip']}:{x['auction_date']}", category="gouvernement", kind="adjudication",
        title=titre, occurred_on=x["auction_date"], published_on=x["auction_date"],
        official_url=RESULTATS + (x.get("pdf_filenm_comp_results") or ""), sha256=canonique(x), parser_version=VERSION,
        entities=["Trésor américain"], amount_min=montant, amount_max=montant, currency="USD", data=d,
        notes=["Parts des acheteurs : en % des offres compétitives acceptées (catégories officielles du Trésor).",
               "Bons du Trésor (moins d'un an) non montrés."])


# ---------- État mensuel (solde du gouvernement fédéral) ----------

def lire_mois(lignes: list[dict]) -> dict | None:
    """Le dernier mois publié : ses chiffres, le cumul de l'exercice et le même mois de l'exercice précédent."""
    if not lignes:
        return None
    fin = max(x["record_date"] for x in lignes)
    rangs = [x for x in lignes if x["record_date"] == fin]
    exercices = sorted(((int(m.group(1)), x["classification_id"]) for x in rangs if x.get("parent_id") in (None, "null")
                        for m in [re.fullmatch(r"FY (\d{4})", x.get("classification_desc") or "")] if m), reverse=True)
    if not exercices:
        return None
    nom_mois = MOIS_EN[int(fin[5:7]) - 1]

    def ligne(parent, desc):
        return next((x for x in rangs if x.get("parent_id") == parent and x.get("classification_desc") == desc), None)

    courant, cumul = ligne(exercices[0][1], nom_mois), ligne(exercices[0][1], "Year-to-Date")
    passe = ligne(exercices[1][1], nom_mois) if len(exercices) > 1 else None
    if courant is None or None in (nombre(courant["current_month_gross_rcpt_amt"]),
                                   nombre(courant["current_month_gross_outly_amt"]),
                                   nombre(courant["current_month_dfct_sur_amt"])):
        return None  # mois absent ou chiffres vides : rien plutôt que faux

    def chiffres(x):
        return x and {"recettes": nombre(x["current_month_gross_rcpt_amt"]),
                      "depenses": nombre(x["current_month_gross_outly_amt"]),
                      "solde": nombre(x["current_month_dfct_sur_amt"])}  # positif = déficit (définition officielle)

    return {"fin": fin, "exercice": exercices[0][0], "mois": chiffres(courant), "cumul": chiffres(cumul),
            "an_dernier": chiffres(passe), "brut": [courant, cumul, passe]}


def majuscule(s: str) -> str:
    return s[:1].upper() + s[1:]  # 1re lettre seulement : la méthode « capitalize » mettrait « G$ » en minuscules


def solde_texte(solde: float) -> str:
    return f"déficit de {milliards(solde, 1)}" if solde >= 0 else f"excédent de {milliards(-solde, 1)}"


def evenement_mois(m: dict, publie: str, date_officielle: bool) -> Evenement:
    fin = m["fin"]
    mois = f"{MOIS[int(fin[5:7]) - 1]} {fin[:4]}"
    c, cumul, passe = m["mois"], m["cumul"], m["an_dernier"]
    titre = f"Trésor américain : {solde_texte(c['solde'])} en {mois} (recettes {milliards(c['recettes'], 1)}, " \
            f"dépenses {milliards(c['depenses'], 1)})"
    notes = ["Un montant positif est un déficit (dépenses plus grandes que les recettes), selon la définition officielle."]
    notes.append("Date de publication : celle du calendrier officiel du Trésor." if date_officielle else
                 "Date de publication : le jour où Radar a vu le mois pour la 1re fois (au plus tard).")
    d = {"fin_du_mois": fin, "exercice": m["exercice"], "mois": c, "cumul_exercice": cumul, "meme_mois_an_dernier": passe,
         "details": details(("Mois", mois), ("Recettes", milliards(c["recettes"], 1)),
                            ("Dépenses", milliards(c["depenses"], 1)), ("Solde", majuscule(solde_texte(c["solde"]))),
                            ("Cumul de l'exercice " + str(m["exercice"]),
                             majuscule(solde_texte(cumul["solde"])) if cumul else ""),
                            (f"Même mois, exercice {m['exercice'] - 1}",
                             majuscule(solde_texte(passe["solde"])) if passe else ""))}
    return Evenement(
        source="tresor", official_id=f"mts:{fin[:7]}", category="gouvernement", kind="solde_mensuel", title=titre,
        occurred_on=fin, published_on=publie, official_url=PAGE_MTS, sha256=canonique({"lignes": m["brut"]}),
        parser_version=VERSION, entities=["Trésor américain"], amount_min=abs(c["solde"]), amount_max=abs(c["solde"]),
        currency="USD", data=d, notes=notes)


def date_de_publication(calendrier: list[dict], fin: str, jour: str) -> str | None:
    """La date officielle de publication de l'état mensuel (calendrier du Trésor), si elle y est."""
    dates = [x["date"] for x in calendrier if x.get("datasetId") == ID_MTS and x.get("released") == "true"
             and fin < x.get("date", "") <= jour]
    return max(dates) if dates else None


@controle_source("tresor")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    if ev.kind == "adjudication":
        a = d.get("acceptees") or {}
        return {
            "resultats_publies": bool(d.get("demande_offre")) and d.get("taux") is not None
                                 and bool(d.get("offres_competitives_acceptees")),
            "parts_qui_s_additionnent": bool(d.get("offres_competitives_acceptees"))
                                        and abs(sum(v or 0 for v in a.values()) - d["offres_competitives_acceptees"]) < 1,
            "obligation_du_tresor": d.get("type") in ("Note", "Bond"),
            "resultat_officiel_du_jour": bool(d.get("document"))
                                        and f"R_{(d.get('adjudication') or '').replace('-', '')}_" in d["document"]
                                        and ev.official_url == RESULTATS + d["document"],
        }
    m = d.get("mois") or {}
    return {
        "mois_publie": bool(re.fullmatch(r"\d{4}-\d\d-\d\d", d.get("fin_du_mois") or "")),
        "solde_egal_depenses_moins_recettes": None not in (m.get("recettes"), m.get("depenses"), m.get("solde"))
                                              and abs(m["depenses"] - m["recettes"] - m["solde"]) < 1,
        "cumul_de_l_exercice_lu": bool(d.get("cumul_exercice")),
    }


# ---------- Collecte ----------

def chemin_etat(donnees) -> Path:
    return Path(donnees) / "tresor" / "etat.json"


def mensuel(ctx) -> list[Evenement]:
    chemin = chemin_etat(ctx.donnees)
    etat = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    m = lire_mois(json.loads(ctx.client.get(ETAT_MENSUEL).contenu).get("data") or [])
    if m is None:
        raise RuntimeError("état mensuel du Trésor illisible")
    evs = []
    vu = etat.get("etat_mensuel")
    if vu is not None and m["fin"] > vu and f"mts:{m['fin'][:7]}" not in deja(ctx, "tresor", mois_max=6):
        jour = ctx.maintenant.astimezone(TORONTO).date().isoformat()
        officielle = date_de_publication(json.loads(ctx.client.get(CALENDRIER).contenu), m["fin"], jour)
        evs.append(evenement_mois(m, officielle or jour, officielle is not None))
    if vu is None or m["fin"] > vu:  # 1re lecture : silencieuse (le mois déjà publié n'est pas une nouveauté)
        etat["etat_mensuel"] = m["fin"]
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return evs


def collecter(ctx) -> list[Evenement]:
    lignes = json.loads(ctx.client.get(ADJUDICATIONS).contenu).get("data") or []
    aujourd_hui = ctx.maintenant.date()
    # Les adjudications annoncées y sont aussi : une liste sans adjudication récente est figée ou incomplète.
    if len(lignes) < 100 or max(x["auction_date"] for x in lignes) < (aujourd_hui - timedelta(days=14)).isoformat():
        raise RuntimeError(f"liste des adjudications incomplète ou figée ({len(lignes)} lignes)")
    depuis = (aujourd_hui - timedelta(days=FENETRE_JOURS)).isoformat()
    lus = deja(ctx, "tresor", mois_max=2)
    evs = [adjudication(x, lignes) for x in lignes
           if depuis <= x["auction_date"] <= aujourd_hui.isoformat() and resultat(x)
           and f"{x['cusip']}:{x['auction_date']}" not in lus]
    return evs + mensuel(ctx)
