"""USAspending.gov (Trésor américain, Bureau of the Fiscal Service) : contrats fédéraux américains de 100 M$ et plus.

API officielle (api.usaspending.gov : pas de robots.txt ; aucun compte ; « Radar projet personnel », sans courriel).
Licence (code source officiel du site, lu le 3 octobre 2026) : « The data on this site is available to copy, adapt,
redistribute, or otherwise use for non-commercial or for commercial purposes, subject to the Limitation on Permissible
Use of Dun & Bradstreet, Inc. Data ». Les noms et adresses d'entreprises sont des données D&B : mention de D&B, jamais
de copie en masse (quelques contrats par jour). La section D&B dit aussi : « Systematic access (electronic harvesting)
or extraction of content from the website, including the use of "bots" or "spiders", is prohibited. » Radar lit
seulement l'API officielle, faite pour les programmes : usage personnel ; avant une vente, retirer la source ou obtenir
une confirmation écrite de D&B.

Délais officiels (site d'USAspending) : un contrat arrive en général moins de 5 jours après sa signature ; ceux de la
Défense (et du Corps des ingénieurs de l'armée) avec 90 jours de délai. USAspending ne date pas la mise en ligne :
- on suit les contrats de 100 M$ et plus signés depuis 150 jours ;
- la 1re lecture est silencieuse (rien n'est daté) ; ensuite, chaque contrat qui apparaît devient une info, datée du
  jour où Radar le voit (lecture chaque matin de semaine).
Montant : les sommes engagées (« obligations ») au moment de la lecture ; le plafond (toutes options) est à part.
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
from .sec import symboles

VERSION = "usaspending-1"
API = "https://api.usaspending.gov/api/v2/"
RECHERCHE = API + "search/spending_by_award/"
FICHE = "https://www.usaspending.gov/award/"
SEUIL = 100_000_000
FENETRE_JOURS = 150
MAX_PAGES = 10
CHAMPS = ["Award ID", "Recipient Name", "Recipient UEI", "Award Amount", "Awarding Agency", "Awarding Sub Agency",
          "Contract Award Type", "Start Date", "Base Obligation Date", "Last Modified Date", "Description",
          "generated_internal_id"]
TORONTO = ZoneInfo("America/Toronto")
DEFENSE = {"Department of Defense", "Department of War"}
# Noms courts en français des grands ministères (le nom officiel anglais reste dans les détails)
MINISTERES = {
    "Department of Defense": "Défense", "Department of War": "Défense", "Department of Veterans Affairs": "Anciens combattants",
    "Department of Homeland Security": "Sécurité intérieure", "Department of Health and Human Services": "Santé",
    "Department of Energy": "Énergie", "Department of Transportation": "Transports", "Department of Justice": "Justice",
    "Department of State": "Affaires étrangères", "Department of the Treasury": "Trésor",
    "Department of Agriculture": "Agriculture", "Department of Commerce": "Commerce", "Department of the Interior": "Intérieur",
    "Department of Education": "Éducation", "Department of Labor": "Travail",
    "Department of Housing and Urban Development": "Logement",
    "National Aeronautics and Space Administration": "NASA", "General Services Administration": "Services généraux (GSA)",
}


TYPES = {"DEFINITIVE CONTRACT": "contrat définitif", "DELIVERY ORDER": "commande dans un contrat-cadre",
         "PURCHASE ORDER": "bon de commande", "BPA CALL": "commande sur une entente d'achat (BPA)"}


def argent(v: float) -> str:
    """1 200 153 023 -> « 1,2 G$ » ; 332 000 000 -> « 332 M$ »."""
    if v >= 1e9:
        return f"{v / 1e9:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",") + " G$"
    return f"{v / 1e6:,.1f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",") + " M$"


def montant(x: dict) -> float | None:
    try:
        return float(x.get("Award Amount"))
    except (TypeError, ValueError):
        return None


def corps_recherche(debut: str, fin: str, page: int) -> dict:
    return {"filters": {"award_type_codes": ["A", "B", "C", "D"],
                        "time_period": [{"start_date": debut, "end_date": fin, "date_type": "new_awards_only"}],
                        "award_amounts": [{"lower_bound": SEUIL}]},
            "fields": CHAMPS, "sort": "Award Amount", "order": "desc", "limit": 100, "page": page}


def lire_contrats(ctx, debut: str, fin: str) -> list[dict]:
    contrats = []
    for page in range(1, MAX_PAGES + 1):
        r = json.loads(ctx.client.post(RECHERCHE, json.dumps(corps_recherche(debut, fin, page)),
                                       {"Content-Type": "application/json"}).contenu)
        contrats += r.get("results") or []
        if not (r.get("page_metadata") or {}).get("hasNext"):
            return contrats
    raise RuntimeError(f"plus de {MAX_PAGES} pages de contrats : lecture incomplète")


def evenement(x: dict, fiche: dict, jour: str, syms=None) -> Evenement:
    fournisseur = " ".join((x.get("Recipient Name") or "").split())
    recipient = fiche.get("recipient") or {}
    mere = " ".join((recipient.get("parent_recipient_name") or "").split())
    agence = x.get("Awarding Agency") or ""
    court = MINISTERES.get(agence, agence)
    somme = montant(x)
    try:
        plafond = float(fiche.get("base_and_all_options"))  # nom du champ vérifié sur de vraies fiches (3 octobre 2026)
    except (TypeError, ValueError):
        plafond = None
    cote = None
    if syms is not None:
        cote = syms.par_nom(fournisseur) or (syms.par_nom(mere) if mere and mere != fournisseur else None)
    defense = agence in DEFENSE
    notes = ["Date de publication : le jour où Radar a vu le contrat pour la 1re fois (USAspending ne date pas la mise "
             "en ligne).",
             "Montant : les sommes engagées (« obligations ») à la lecture ; le plafond, si toutes les options sont "
             "levées, est dans les détails."]
    if defense:
        notes.append("Défense : contrats publiés avec 90 jours de délai (règle officielle).")
    d = {"id": x.get("generated_internal_id"), "numero": x.get("Award ID"), "fournisseur": fournisseur,
         "uei": x.get("Recipient UEI"), "societe_mere": mere, "agence": agence, "sous_agence": x.get("Awarding Sub Agency"),
         "type": x.get("Contract Award Type"), "montant": somme, "plafond": plafond, "signe_le": x.get("Base Obligation Date"),
         "debut": x.get("Start Date"), "modifie_le": x.get("Last Modified Date"), "description": x.get("Description"),
         "details": details(("Fournisseur", fournisseur), ("Société mère déclarée", mere if mere != fournisseur else ""),
                            ("Ministère ou agence", agence), ("Sous-agence", x.get("Awarding Sub Agency") or ""),
                            ("Sommes engagées", argent(somme) if somme else ""),
                            ("Plafond (toutes options)", argent(plafond) if plafond and plafond != somme else ""),
                            ("Signé le", x.get("Base Obligation Date") or ""),
                            ("Type", TYPES.get(x.get("Contract Award Type") or "", x.get("Contract Award Type") or "")),
                            ("Description", x.get("Description") or ""), ("Numéro", x.get("Award ID") or ""))}
    return Evenement(
        source="usaspending", official_id=x.get("generated_internal_id"),
        category="militaire" if defense else "gouvernement", kind="contrat_federal_us",
        title=f"Contrat fédéral américain de {argent(somme)} : {fournisseur} ({court})",
        occurred_on=x.get("Base Obligation Date"), published_on=jour, official_url=FICHE + x.get("generated_internal_id"),
        sha256=canonique({k: v for k, v in x.items() if k not in ("Last Modified Date", "internal_id")}),
        parser_version=VERSION, tickers=[cote["ticker"]] if cote else [], entities=[fournisseur, agence],
        amount_min=somme, amount_max=somme, currency="USD", notes=notes, data=d)


@controle_source("usaspending")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "seuil_de_100_millions": (d.get("montant") or 0) >= SEUIL,
        "contrat_federal": str(d.get("id") or "").startswith("CONT_AWD_"),
        "lien_de_la_fiche_du_contrat": ev.official_url == FICHE + str(d.get("id")),
        "date_de_signature_lue": bool(re.fullmatch(r"\d{4}-\d\d-\d\d", d.get("signe_le") or "")),
        "fournisseur_lu": bool(d.get("fournisseur")),
    }


def chemin_etat(donnees) -> Path:
    return Path(donnees) / "usaspending" / "vus.json"


def collecter(ctx) -> list[Evenement]:
    jour = ctx.maintenant.astimezone(TORONTO).date()
    debut = (jour - timedelta(days=FENETRE_JOURS)).isoformat()
    contrats = [x for x in lire_contrats(ctx, debut, jour.isoformat()) if (montant(x) or 0) >= SEUIL]
    if not contrats:
        raise RuntimeError("aucun contrat de 100 M$ et plus en 150 jours : réponse incomplète")
    chemin = chemin_etat(ctx.donnees)
    etat = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None
    evs = []
    if etat is not None:  # 1re lecture : silencieuse (rien n'est daté), on note seulement ce qui est déjà publié
        vus, publies, syms = etat["vus"], deja(ctx, "usaspending", mois_max=6), None
        for x in contrats:
            i = x.get("generated_internal_id")
            if i in vus or i in publies:
                continue
            if syms is None:
                syms = symboles(ctx)
            fiche = json.loads(ctx.client.get(f"{API}awards/{i}/").contenu)
            evs.append(evenement(x, fiche, jour.isoformat(), syms))
    vus = {**(etat or {}).get("vus", {}), **{x["generated_internal_id"]: x.get("Base Obligation Date") or "" for x in contrats}}
    etat = {"depuis": (etat or {}).get("depuis", jour.isoformat()), "lu_le": jour.isoformat(),
            "vus": {i: s for i, s in vus.items() if s >= debut}}  # au-delà de 150 jours : plus suivi
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return evs

