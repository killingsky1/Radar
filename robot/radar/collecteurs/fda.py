"""FDA : nouveaux médicaments approuvés (nouvelles molécules), par l'API officielle openFDA (base Drugs@FDA).

openFDA : données du domaine public (CC0), gratuites, sans compte (240 requêtes/minute, 1 000/jour sans clé).
Mise à jour chaque jour ouvrable (meta.last_updated). On garde seulement l'approbation ORIGINALE d'une NOUVELLE
MOLÉCULE (classe officielle « Type 1 - New Molecular Entity »), médicament (NDA) ou produit biologique (BLA).
Laissés de côté : génériques (ANDA), nouveaux dosages, nouvelles indications (trop nombreux, peu d'effet).
Données fournies par la Food and Drug Administration des États-Unis (https://open.fda.gov).
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from ..models import Evenement, empreinte
from ..validate import controle_source
from .sec import symboles

VERSION = "fda-1"
API = "https://api.fda.gov/drug/drugsfda.json"
DRUGS_AT_FDA = "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo="
FENETRE_JOURS = 60  # relu à chaque passage : openFDA ajoute parfois une approbation quelques jours plus tard
PAGE = 100
PAGES_MAX = 10
FRAICHEUR_MAX_JOURS = 10  # si openFDA n'est plus mis à jour, la source doit le dire


def requete(debut: date, fin: date, saut: int) -> str:
    # Toute application qui a une soumission « Type 1 » ET une soumission datée dans la fenêtre : le tri fin
    # (même soumission, originale, approuvée) se fait ensuite ici, champ par champ.
    return (f"{API}?search=submissions.submission_class_code:%22TYPE+1%22"
            f"+AND+submissions.submission_status_date:[{debut:%Y%m%d}+TO+{fin:%Y%m%d}]&limit={PAGE}&skip={saut}")


def iso(aaaammjj: str) -> str:
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:8]}"


def approbations(applications: list[dict], depuis: str) -> list[tuple[dict, dict]]:
    """(application, soumission) : approbation originale d'une nouvelle molécule, datée depuis `depuis` (AAAAMMJJ)."""
    trouvees = []
    for app in applications:
        if not str(app.get("application_number", "")).startswith(("NDA", "BLA")):
            continue
        for s in app.get("submissions", []):
            if (s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"
                    and (s.get("submission_class_code") or "").startswith("TYPE 1")
                    and len(s.get("submission_status_date") or "") == 8 and s["submission_status_date"] >= depuis):
                trouvees.append((app, s))
    return trouvees


def _faits(app: dict, sub: dict) -> dict:
    """Les faits officiels qui comptent ; l'empreinte porte sur eux (la fiche openFDA grossit à chaque document ajouté)."""
    produits = sorted({(p.get("brand_name") or "").strip() for p in app.get("products", []) if p.get("brand_name")})
    ingredients = sorted({(i.get("name") or "").strip() for p in app.get("products", [])
                          for i in p.get("active_ingredients", []) if i.get("name")})
    return {"application": app["application_number"], "sponsor": app.get("sponsor_name"), "marques": produits,
            "ingredients": ingredients, "type_soumission": sub.get("submission_type"),
            "numero_soumission": sub.get("submission_number"), "statut": sub.get("submission_status"),
            "date": sub.get("submission_status_date"), "classe": sub.get("submission_class_code")}


def evenement(app: dict, sub: dict, syms=None) -> Evenement:
    faits = _faits(app, sub)
    numero = faits["application"]
    fabricant = ((app.get("openfda") or {}).get("manufacturer_name") or [None])[0]
    compagnie = fabricant or faits["sponsor"] or "compagnie inconnue"
    marque = " / ".join(faits["marques"]) or "nom inconnu"
    ingredient = ", ".join(i.lower() for i in faits["ingredients"])
    lettre = next((d.get("url") for d in sub.get("application_docs", []) if d.get("type") == "Letter"), None)
    proprietes = {p.get("code") for p in sub.get("submission_property_type", [])}
    jour = iso(faits["date"])
    tickers = []
    if syms is not None:
        # Le nom du fabricant et celui du détenteur doivent mener à la MÊME compagnie cotée (sinon rien).
        trouves = {r["ticker"] for r in (syms.par_nom(fabricant), syms.par_nom(faits["sponsor"])) if r}
        tickers = sorted(trouves) if len(trouves) == 1 else []
    notes = []
    if sub.get("review_priority") == "PRIORITY":
        notes.append("Examen prioritaire : la FDA juge qu'il peut apporter un progrès important.")
    if "Orphan" in proprietes:
        notes.append("Médicament orphelin : maladie rare.")
    if numero.startswith("BLA"):
        notes.append("Produit biologique.")
    return Evenement(
        source="fda", official_id=f"{numero}-ORIG-{faits['numero_soumission']}", category="gouvernement",
        kind="approbation_fda",
        title=f"FDA : nouveau médicament approuvé, {marque}" + (f" ({ingredient})" if ingredient else "")
              + f", de {compagnie}",
        occurred_on=jour, published_on=jour, official_url=f"{DRUGS_AT_FDA}{numero[3:]}",
        sha256=empreinte(json.dumps(faits, sort_keys=True, ensure_ascii=False).encode("utf-8")),
        parser_version=VERSION, tickers=tickers, entities=[compagnie], direction=1, notes=notes,
        data={**faits, "compagnie": compagnie, "fabricant": fabricant, "lettre": lettre,
              "priorite": sub.get("review_priority"), "orphelin": "Orphan" in proprietes},
    )


@controle_source("fda")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    chiffres = str(d.get("application", ""))[3:]
    return {
        "approbation_originale": d.get("type_soumission") == "ORIG" and d.get("statut") == "AP",
        "nouvelle_molecule": str(d.get("classe") or "").startswith("TYPE 1"),
        "lettre_officielle": bool(chiffres) and str(d.get("lettre") or "").startswith(
            "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/") and chiffres in str(d.get("lettre")),
    }


def collecter(ctx) -> list[Evenement]:
    fin = ctx.maintenant.date()
    debut = fin - timedelta(days=FENETRE_JOURS)
    applications: list[dict] = []
    for page in range(PAGES_MAX):
        r = json.loads(ctx.client.get(requete(debut, fin, page * PAGE)).contenu)
        if page == 0:
            maj = (r.get("meta") or {}).get("last_updated") or ""
            if maj < (fin - timedelta(days=FRAICHEUR_MAX_JOURS)).isoformat():
                raise RuntimeError(f"openFDA n'est plus mis à jour (dernière mise à jour : {maj or 'inconnue'})")
        applications += r.get("results", [])
        if (page + 1) * PAGE >= r["meta"]["results"]["total"]:
            break
    else:
        raise RuntimeError("openFDA : trop de résultats, la fenêtre doit être réduite")
    syms = symboles(ctx)
    return [evenement(app, sub, syms) for app, sub in approbations(applications, f"{debut:%Y%m%d}")]
