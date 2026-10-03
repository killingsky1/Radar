"""Contrats fédéraux du Canada (publication proactive des contrats de plus de 10 000 $), portail du gouvernement ouvert.

API officielle du portail (open.canada.ca, CKAN, ressource « Contracts over $10,000 ») : son robots.txt permet
/data/api/ et demande 20 secondes entre deux requêtes (respecté : voir http.py). Le site de recherche interdit aux
robots le tri et la pagination : on ne s'en sert que pour le lien public d'un contrat (fiche « record », permise).
Licence du gouvernement ouvert – Canada.

Seuil : 10 M$ et plus (nouveau contrat : sa valeur ; modification : la hausse). Mesuré sur avril à juin 2026 (23 381
lignes) : 47 nouveaux contrats et 45 modifications de 10 M$ et plus.

Le portail ne date pas chaque ligne. Pour ne rien présenter comme nouveau à tort :
- la 1re lecture d'un trimestre est silencieuse : elle note ce qui est déjà publié (le plus haut numéro interne « _id »
  et les contrats de 10 M$ et plus déjà vus) ;
- ensuite, on lit seulement les lignes ajoutées (« _id » plus haut) : leur date de publication est le jour où Radar
  les voit pour la 1re fois (lecture chaque matin de semaine).
Trimestres suivis : celui en cours et les 2 précédents (les ministères publient dans les 30 jours après la fin d'un
trimestre, parfois plus tard).
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from ..models import Evenement
from ..validate import controle_source
from .gazette import details
from .regulateurs import canonique, deja
from .sec import symboles

VERSION = "contrats-ca-1"
API = "https://open.canada.ca/data/api/action/datastore_search"
RESSOURCE = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"
FICHE = "https://rechercher.ouvert.canada.ca/contrats/record/"
CHAMPS = ("_id,reference_number,owner_org,owner_org_title,vendor_name,contract_date,contract_value,original_value,"
          "amendment_value,description_fr,instrument_type,reporting_period")
LIMITE = 1000
MAX_PAGES = 40  # au plus 40 000 lignes par trimestre et par lecture (avril à juin 2026 : 23 381)
SEUIL = 10_000_000
TYPES = {"C": "contrat", "A": "modification d'un contrat",
         "SOSA": "commande subséquente à une offre à commandes ou à un arrangement en matière d'approvisionnement"}
PERIODE = re.compile(r"(\d{4})-(\d{4})-Q([1-4])")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")
TORONTO = ZoneInfo("America/Toronto")


# ---------- Trimestres de l'exercice fédéral (1er avril au 31 mars) ----------

def trimestre(d: date) -> str:
    an = d.year if d.month >= 4 else d.year - 1
    return f"{an}-{an + 1}-Q{(d.month - 4) % 12 // 3 + 1}"


def debut_trimestre(periode: str) -> date:
    m = PERIODE.fullmatch(periode)
    an, q = int(m.group(1)), int(m.group(3))
    return date(an + 1, 1, 1) if q == 4 else date(an, 4 + 3 * (q - 1), 1)


def trimestres_suivis(d: date) -> list[str]:
    """Le trimestre en cours et les 2 précédents (du plus récent au plus ancien)."""
    suivis, jour = [], d
    for _ in range(3):
        p = trimestre(jour)
        suivis.append(p)
        debut = debut_trimestre(p)
        jour = date(debut.year - 1, 12, 1) if debut.month == 1 else date(debut.year, debut.month - 1, 1)
    return suivis


def libelle_trimestre(periode: str) -> str:
    debut = debut_trimestre(periode)
    fin_mois = debut.month + 2
    return f"{MOIS[debut.month - 1]} à {MOIS[fin_mois - 1]} {debut.year}"


# ---------- Montants ----------

def valeur(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def argent(v: float) -> str:
    """12 345 678 -> « 12,3 M$ » ; 6 382 883 843 -> « 6,38 G$ »."""
    if v >= 1e9:
        return f"{v / 1e9:.2f}".replace(".", ",") + " G$"
    if v >= 1e6:
        return f"{v / 1e6:.1f}".replace(".", ",") + " M$"
    return f"{v:,.0f}".replace(",", " ") + " $"


def montant(x: dict) -> float | None:
    """La nouvelle somme engagée : la valeur d'un nouveau contrat, ou la hausse d'une modification."""
    return valeur(x.get("amendment_value")) if x.get("instrument_type") == "A" else valeur(x.get("contract_value"))


def retenu(x: dict) -> bool:
    m = montant(x)
    return m is not None and m >= SEUIL


def cle(x: dict) -> str:
    return f"{x.get('owner_org')}:{x.get('reference_number')}"


def fiche(x: dict) -> str:
    return FICHE + quote(f"{x.get('owner_org')},{x.get('reference_number')}", safe=",-_.")


# ---------- Lecture d'un trimestre (du plus récent au plus ancien) ----------

def adresse(periode: str, page: int) -> str:
    return (f"{API}?resource_id={RESSOURCE}&filters=" + quote(json.dumps({"reporting_period": periode}))
            + "&sort=" + quote("_id desc") + f"&limit={LIMITE}&offset={page * LIMITE}&fields={CHAMPS}")


def lire_trimestre(ctx, periode: str, deja_haut: int | None) -> tuple[list[dict], int | None, bool]:
    """Les lignes plus récentes que `deja_haut` (toutes s'il est None), le plus haut _id vu, et si tout a été lu."""
    neuves, haut, vus = [], None, set()
    for page in range(MAX_PAGES):
        r = json.loads(ctx.client.get(adresse(periode, page)).contenu)
        if not r.get("success"):
            raise RuntimeError(f"API du portail : réponse en erreur ({periode})")
        lignes = r["result"]["records"]
        for x in lignes:
            if x["_id"] in vus:
                continue  # une ligne ajoutée pendant la lecture décale les pages : déjà lue
            vus.add(x["_id"])
            haut = x["_id"] if haut is None else max(haut, x["_id"])
            if deja_haut is None or x["_id"] > deja_haut:
                neuves.append(x)
        if len(lignes) < LIMITE or (deja_haut is not None and any(x["_id"] <= deja_haut for x in lignes)):
            return neuves, haut, True
    return neuves, haut, False


# ---------- Événements ----------

def evenement(x: dict, jour: str, syms=None) -> Evenement:
    periode = x.get("reporting_period") or ""
    modif = x.get("instrument_type") == "A"
    total, hausse = valeur(x.get("contract_value")), valeur(x.get("amendment_value"))
    somme = montant(x)
    fournisseur = " ".join((x.get("vendor_name") or "").split())
    ministere = (x.get("owner_org_title") or "").split(" | ")[-1].strip()
    if modif:
        titre = f"Contrat fédéral modifié : +{argent(hausse)} pour {fournisseur} ({ministere}), valeur totale {argent(total)}"
        quand = debut_trimestre(periode).isoformat()
    else:
        titre = f"Contrat fédéral de {argent(total)} : {fournisseur} ({ministere})"
        quand = x.get("contract_date") if re.fullmatch(r"\d{4}-\d\d-\d\d", x.get("contract_date") or "") \
            else debut_trimestre(periode).isoformat()
    cote = syms.par_nom(fournisseur) if syms is not None and fournisseur else None
    notes = ["Date de publication : le jour où Radar a vu la ligne pour la 1re fois (le portail ne date pas chaque ligne)."]
    if modif:
        notes.append(f"Date exacte de la modification non publiée : déclarée pour le trimestre {libelle_trimestre(periode)}.")
    d = {**x, "fournisseur": fournisseur, "ministere": ministere, "montant": somme, "type": TYPES.get(x.get("instrument_type")),
         "details": details(("Fournisseur", fournisseur), ("Ministère ou organisme", ministere),
                            ("Hausse" if modif else "Valeur du contrat", argent(somme) if somme is not None else ""),
                            ("Nouvelle valeur totale", argent(total) if modif and total is not None else ""),
                            ("Valeur d'origine", argent(valeur(x.get("original_value")))
                             if modif and valeur(x.get("original_value")) is not None else ""),
                            ("Date du contrat", x.get("contract_date") or ""), ("Description", x.get("description_fr") or ""),
                            ("Type", TYPES.get(x.get("instrument_type"), x.get("instrument_type") or "")),
                            ("Trimestre déclaré", libelle_trimestre(periode) if PERIODE.fullmatch(periode) else periode),
                            ("Référence", x.get("reference_number") or ""))}
    return Evenement(
        source="contrats_ca_10k", official_id=cle(x), category="canada",
        kind="contrat_modifie" if modif else "contrat_federal", title=titre, occurred_on=quand, published_on=jour,
        official_url=fiche(x), sha256=canonique({k: v for k, v in x.items() if k != "_id"}), parser_version=VERSION,
        tickers=[cote["ticker"]] if cote else [], entities=[fournisseur, ministere], amount_min=somme, amount_max=somme,
        currency="CAD", notes=notes, data=d)


@controle_source("contrats_ca_10k")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "seuil_de_10_millions": (d.get("montant") or 0) >= SEUIL,
        "valeurs_lues": valeur(d.get("contract_value")) is not None
                        and (d.get("instrument_type") != "A" or valeur(d.get("amendment_value")) is not None),
        "type_d_instrument_connu": d.get("instrument_type") in TYPES,
        "trimestre_declare_valide": bool(PERIODE.fullmatch(d.get("reporting_period") or "")),
        "lien_de_la_fiche_du_contrat": ev.official_url == fiche(d),
    }


# ---------- Collecte ----------

def chemin_etat(donnees) -> Path:
    return Path(donnees) / "contrats" / "trimestres.json"


def collecter(ctx) -> list[Evenement]:
    chemin = chemin_etat(ctx.donnees)
    etat = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    jour = ctx.maintenant.astimezone(TORONTO).date()
    deja_publies, syms = deja(ctx, "contrats_ca_10k", mois_max=6), None
    evs = []
    suivis = trimestres_suivis(jour)
    for periode in suivis:
        e = etat.get(periode)
        neuves, haut, complet = lire_trimestre(ctx, periode, e["max_id"] if e else None)
        if e is None:  # 1re lecture : silencieuse (rien n'est daté), on note seulement ce qui est déjà publié
            etat[periode] = {"max_id": haut or 0, "vus": sorted({cle(x) for x in neuves if retenu(x)}),
                             "lignes_lues": len(neuves), "complet": complet, "depuis": jour.isoformat(),
                             "lu_le": jour.isoformat()}
            continue
        vus = set(e["vus"])
        for x in sorted(neuves, key=lambda x: x["_id"]):
            if not retenu(x) or cle(x) in vus:
                continue  # sous le seuil, ou ligne déjà vue renvoyée par le ministère
            vus.add(cle(x))
            if cle(x) not in deja_publies:
                if syms is None:
                    syms = symboles(ctx)
                evs.append(evenement(x, jour.isoformat(), syms))
        e.update(max_id=max(e["max_id"], haut or 0), vus=sorted(vus), lu_le=jour.isoformat(),
                 lignes_lues=e.get("lignes_lues", 0) + len(neuves))
    for vieux in [p for p in etat if p not in suivis]:
        del etat[vieux]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return evs
