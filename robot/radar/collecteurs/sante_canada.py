"""Santé Canada : nouveaux médicaments autorisés (avis de conformité pour une nouvelle substance active, « NSA »).

API officielle de la Base de données sur les avis de conformité (health-products.canada.ca : pas de robots.txt, tout est
permis ; vérifié le 3 octobre 2026), en français, mise à jour chaque nuit. Licence du gouvernement ouvert – Canada.
L'API n'a aucun filtre par date et les numéros d'avis ne suivent pas les dates : on lit la liste complète (environ
24 Mo, compressée pendant le transfert) une fois par jour, puis 2 petites fiches (marque, ingrédient) par nouvelle
substance active.

Mesuré le 3 octobre 2026 : 38 068 avis depuis 1994 ; 1 707 en 2026, dont 30 nouvelles substances actives. Les autres
avis (suppléments, génériques, changements administratifs) ne sont pas des nouveautés : on ne les garde pas.
"""

from __future__ import annotations

import json
from datetime import timedelta

from ..models import Evenement
from ..validate import controle_source
from .gazette import details
from .regulateurs import canonique, deja
from .sec import symboles

VERSION = "sante-canada-1"
API = "https://health-products.canada.ca/api/notice-of-compliance/"
LISTE = API + "noticeofcompliancemain/?lang=fr&type=json"
FENETRE_JOURS = 60  # relu chaque jour : un avis peut entrer dans la base quelques jours après sa date
CLASSES_NSA = {"Nouvelle substance active (NSA)", "Priorité-NSA"}


FICHE = "https://health-products.canada.ca/noc-ac/nocInfo?lang=fre&no="


def fiche(n: int) -> str:
    """La fiche publique de l'avis dans la Base de données sur les avis de conformité (lien du « Document officiel »)."""
    return f"{FICHE}{n}"


def nouvelles_substances(avis: list[dict], depuis: str) -> list[dict]:
    return [x for x in avis if x.get("noc_submission_class") in CLASSES_NSA and (x.get("noc_date") or "") >= depuis]


def evenement(avis: dict, produits: list[dict], ingredients: list[dict], syms=None) -> Evenement:
    n = avis["noc_number"]
    marques = sorted({" ".join(p["noc_br_brandname"].split()) for p in produits if p.get("noc_br_brandname")})
    composants = []
    for i in ingredients:
        nom = " ".join((i.get("noc_pi_medic_ingr_name") or "").split()).lower()
        if nom and nom not in [c["nom"] for c in composants]:
            dose = i.get("noc_pi_strength")
            composants.append({"nom": nom, "dose": f"{dose:g} {i.get('noc_pi_unit') or ''}".strip()
                               + (f" / {i['noc_pi_basic_unit']}" if i.get("noc_pi_basic_unit") else "")
                               if dose is not None else ""})
    fabricant = " ".join((avis.get("noc_manufacturer_name") or "").split())
    cote = syms.par_nom(fabricant) if syms is not None and fabricant else None
    notes = []
    if avis.get("noc_status_with_conditions") == "Y":
        notes.append("Autorisé avec conditions (AC-C) : le fabricant doit faire d'autres études pour confirmer le bienfait.")
    if avis.get("noc_submission_class") == "Priorité-NSA":
        notes.append("Examen prioritaire (classe « Priorité-NSA ») : Santé Canada a examiné la demande en accéléré.")
    if avis.get("noc_product_type") == "Vétérinaire":
        notes.append("Médicament vétérinaire.")
    noms = ", ".join(c["nom"] for c in composants)
    d = {"numero": n, "date": avis.get("noc_date"), "fabricant": fabricant, "classe": avis.get("noc_submission_class"),
         "presentation": avis.get("noc_on_submission_type"), "type_produit": avis.get("noc_product_type"),
         "avec_conditions": avis.get("noc_status_with_conditions") == "Y", "actif": avis.get("noc_active_status"),
         "classe_therapeutique": avis.get("noc_therapeutic_class") or "", "marques": marques, "ingredients": composants,
         "din": sorted({p.get("noc_br_din") for p in produits if p.get("noc_br_din")}),
         "fiches_meme_avis": all(x.get("noc_number") == n for x in [*produits, *ingredients]),
         "details": details(("Médicament", " / ".join(marques)),
                            ("Ingrédient(s)", "; ".join(f"{c['nom']} {c['dose']}".strip() for c in composants)),
                            ("Fabricant", fabricant), ("Type", avis.get("noc_product_type") or ""),
                            ("Présentation", avis.get("noc_on_submission_type") or ""),
                            ("Classe", avis.get("noc_submission_class") or ""),
                            ("Classe thérapeutique", avis.get("noc_therapeutic_class") or ""),  # telle quelle (sigles compris)
                            ("Avis de conformité", f"n° {n} du {avis.get('noc_date')}"))}
    return Evenement(
        source="sante_canada", official_id=str(n), category="canada", kind="approbation_sante_canada",
        title=f"Santé Canada : nouveau médicament autorisé, {' / '.join(marques)}" + (f" ({noms})" if noms else "")
              + f", de {fabricant}",
        occurred_on=avis["noc_date"], published_on=avis["noc_date"], official_url=fiche(n),
        sha256=canonique({"avis": avis, "produits": produits, "ingredients": ingredients}), parser_version=VERSION,
        tickers=[cote["ticker"]] if cote else [], entities=[fabricant], currency="CAD", notes=notes, data=d)


@controle_source("sante_canada")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "nouvelle_substance_active": d.get("classe") in CLASSES_NSA,
        "avis_actif": d.get("actif") == "1",
        "marque_et_ingredient_lus": bool(d.get("marques")) and bool(d.get("ingredients")),
        "fiches_du_meme_avis": bool(d.get("fiches_meme_avis")),
    }


def collecter(ctx) -> list[Evenement]:
    avis = json.loads(ctx.client.get(LISTE).contenu.decode("utf-8-sig"))
    plus_recent = max((x.get("noc_date") or "" for x in avis), default="")
    # La base est mise à jour chaque nuit : une liste vide, courte ou figée depuis 3 semaines est une erreur.
    if len(avis) < 1000 or plus_recent < (ctx.maintenant.date() - timedelta(days=21)).isoformat():
        raise RuntimeError(f"liste des avis de conformité incomplète ou figée ({len(avis)} avis, dernier : {plus_recent})")
    depuis = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus, syms = deja(ctx, "sante_canada"), symboles(ctx)
    evs = []
    for x in sorted(nouvelles_substances(avis, depuis), key=lambda x: x["noc_number"]):
        n = x["noc_number"]
        if str(n) in lus:
            continue
        produits = json.loads(ctx.client.get(API + f"drugproduct/?id={n}&lang=fr&type=json").contenu.decode("utf-8-sig"))
        ingredients = json.loads(ctx.client.get(API + f"medicinalingredient/?id={n}&lang=fr&type=json")
                                 .contenu.decode("utf-8-sig"))
        if not produits or not ingredients:
            continue  # fiches pas encore remplies : on réessaiera demain (rien plutôt qu'incomplet)
        evs.append(evenement(x, produits, ingredients, syms))
    return evs
