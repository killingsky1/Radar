"""Régulateurs américains : rappels d'autos (NHTSA), antitrust (DOJ), sanctions (OFAC), suspensions de cotation
et procédures administratives (SEC). Fusions (FTC) : voir plus bas.

Toutes ces sources sont officielles, gratuites, sans compte, et leur robots.txt permet nos adresses (vérifié
le 3 octobre 2026). Les rappels de la NHTSA sont lus sur le portail de données du ministère américain des
Transports (datahub.transportation.gov) : les sites nhtsa.gov refusent les robots, on n'y va pas.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source
from .banques import _items, texte_html
from .sec import symboles

NEW_YORK = ZoneInfo("America/New_York")
FENETRE_JOURS = 30


def deja(ctx, source: str) -> set[str]:
    return Depot(ctx.donnees).ids_enregistres({source})


def jour_new_york(date_rss: str) -> str | None:
    try:
        return parsedate_to_datetime(date_rss).astimezone(NEW_YORK).date().isoformat()
    except (TypeError, ValueError):
        return None


def canonique(d: dict) -> str:
    return empreinte(json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8"))


# ---------- NHTSA : rappels de véhicules ----------

NHTSA_API = "https://datahub.transportation.gov/resource/6axg-epim.json"
NHTSA_SEUIL = 10_000  # véhicules touchés : sous ce nombre, un rappel ne bouge pas une action
NHTSA_VERSION = "nhtsa-1"
SORTES_RAPPEL = {"Vehicle": "véhicules", "Equipment": "équipements", "Tire": "pneus", "Child Seat": "sièges pour enfants"}


def requete_nhtsa(depuis: date) -> str:
    return (f"{NHTSA_API}?$where=report_received_date%20%3E%3D%20%27{depuis:%Y-%m-%d}T00%3A00%3A00%27"
            f"&$order=report_received_date%20DESC&$limit=1000")


def nombre(x) -> int | None:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def evenement_nhtsa(r: dict, syms=None) -> Evenement | None:
    n = nombre(r.get("potentially_affected"))
    if n is None or n < NHTSA_SEUIL or not r.get("nhtsa_id") or not r.get("report_received_date"):
        return None
    numero = r["nhtsa_id"].strip()
    jour = r["report_received_date"][:10]
    constructeur = (r.get("manufacturer") or "").strip()
    sorte = SORTES_RAPPEL.get(r.get("recall_type"), "unités")
    lien = (r.get("recall_link") or {}).get("url") or ""
    if not lien.startswith("https://www.nhtsa.gov/recalls?nhtsaId="):
        lien = f"https://www.nhtsa.gov/recalls?nhtsaId={numero}"
    tickers = []
    if syms is not None:
        cote = syms.par_nom(constructeur)
        tickers = [cote["ticker"]] if cote else []
    notes = []
    if str(r.get("do_not_drive", "")).lower() == "yes":
        notes.append("Consigne officielle : ne pas conduire le véhicule avant la réparation.")
    if str(r.get("fire_risk_when_parked", "")).lower() == "yes":
        notes.append("Risque d'incendie même stationné : garer dehors, loin des bâtiments.")
    return Evenement(
        source="nhtsa", official_id=numero, category="gouvernement", kind="rappel",
        title=f"Rappel de {constructeur} : {n:,} {sorte}".replace(f"{n:,}", f"{n:,}".replace(",", " "))
              + f" — « {r.get('subject', '').strip()} »",
        occurred_on=jour, published_on=jour, official_url=lien, sha256=canonique(r), parser_version=NHTSA_VERSION,
        tickers=tickers, entities=[constructeur], direction=-1, notes=notes,
        data={"numero": numero, "constructeur": constructeur, "unites": n, "sorte": r.get("recall_type"),
              "sujet": r.get("subject"), "composant": r.get("component"), "campagne": r.get("mfr_campaign_number"),
              "defaut": (r.get("defect_summary") or "")[:500], "consequence": (r.get("consequence_summary") or "")[:300]},
    )


@controle_source("nhtsa")
def controles_nhtsa(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "numero_de_rappel_officiel": bool(re.fullmatch(r"\d{2}[VETC]\d{6}", d.get("numero", ""))),
        "nombre_plausible": NHTSA_SEUIL <= (d.get("unites") or 0) <= 50_000_000,
        "lien_du_meme_rappel": ev.official_url.endswith(f"nhtsaId={d.get('numero')}"),
    }


def collecter_nhtsa(ctx) -> list[Evenement]:
    depuis = ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)
    rangees = json.loads(ctx.client.get(requete_nhtsa(depuis)).contenu)
    if not isinstance(rangees, list):
        raise RuntimeError("réponse inattendue du portail de données des Transports")
    lus, syms = deja(ctx, "nhtsa"), symboles(ctx)
    evs = []
    for r in rangees:
        if f"nhtsa:{r.get('nhtsa_id', '').strip()}" in lus:
            continue
        ev = evenement_nhtsa(r, syms)
        if ev:
            evs.append(ev)
    return evs


# ---------- DOJ : division antitrust ----------

DOJ_FLUX = ("https://www.justice.gov/news/rss?type%5B0%5D=image_gallery&type%5B1%5D=press_release&type%5B2%5D=speech"
            "&type%5B3%5D=youtube_video&field_component=376&search_api_language=en&show_public_archived=0&require_all=0")
DOJ_LIEN = re.compile(r"https://www\.justice\.gov/opa/pr/([a-z0-9-]+)")
DOJ_VERSION = "doj-1"


def evenement_doj(item: dict) -> Evenement | None:
    m = DOJ_LIEN.fullmatch(item["lien"].strip())
    jour = jour_new_york(item["date"])
    if not m or not jour or not item["titre"]:
        return None  # discours, vidéos : seuls les communiqués comptent
    return Evenement(
        source="doj_antitrust", official_id=m.group(1), category="gouvernement", kind="antitrust",
        title=f"Antitrust (ministère de la Justice) : {item['titre']}", occurred_on=jour, published_on=jour,
        official_url=item["lien"].strip(), sha256=canonique(item), parser_version=DOJ_VERSION,
        data={"titre_officiel": item["titre"]},
    )


@controle_source("doj_antitrust")
def controles_doj(ev: Evenement) -> dict[str, bool]:
    return {"communique_officiel": bool(DOJ_LIEN.fullmatch(ev.official_url))
            and ev.official_url.endswith(ev.official_id)}


def collecter_doj(ctx) -> list[Evenement]:
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus = deja(ctx, "doj_antitrust")
    evs = []
    for item in _items(ctx.client.get(DOJ_FLUX).contenu.decode("utf-8", "replace")):
        ev = evenement_doj(item)
        if ev and ev.published_on >= limite and ev.id not in lus:
            evs.append(ev)
    return evs


# ---------- SEC : suspensions de cotation et procédures administratives ----------

SEC_SUSPENSIONS = "https://www.sec.gov/enforcement-litigation/trading-suspensions/rss"
SEC_PROCEDURES = "https://www.sec.gov/enforcement-litigation/administrative-proceedings/rss"
SEC_DOC = re.compile(r"https://www\.sec\.gov/files/litigation/(suspensions|admin)/\d{4}/([0-9a-z-]+)\.pdf")
SEC_VERSION = "sec-poursuites-1"


def compagnies_cotees(titre: str, syms) -> list[dict]:
    """Les compagnies cotées nommées EXACTEMENT dans le titre officiel (« X, Inc. and Y LLC » -> X, Y)."""
    trouvees = []
    for morceau in [titre] + re.split(r"\s+(?:and|And|AND)\s+|;", titre):
        cote = syms.par_nom(morceau.strip(" ,"))
        if cote and cote["ticker"] not in [c["ticker"] for c in trouvees]:
            trouvees.append(cote)
    return trouvees


def evenement_sec(item: dict, sorte: str, syms) -> Evenement | None:
    m = SEC_DOC.fullmatch(item["lien"].strip())
    jour = jour_new_york(item["date"])
    if not m or not jour or not item["titre"]:
        return None
    cotees = compagnies_cotees(item["titre"], syms)
    if sorte == "procedure" and not cotees:
        return None  # procédures contre des personnes ou des firmes non cotées : pas un signal boursier
    nom = item["titre"].strip()
    titre = (f"SEC : cotation suspendue, {nom}" if sorte == "suspension"
             else f"SEC : procédure administrative visant {nom}")
    return Evenement(
        source="sec_poursuites", official_id=m.group(2), category="compagnies",
        kind="suspension_cotation" if sorte == "suspension" else "procedure_sec", title=titre,
        occurred_on=jour, published_on=jour, official_url=item["lien"].strip(), sha256=canonique(item),
        parser_version=SEC_VERSION, tickers=[c["ticker"] for c in cotees], entities=[nom], direction=-1,
        data={"nom_officiel": nom, "sorte": sorte},
    )


@controle_source("sec_poursuites")
def controles_sec(ev: Evenement) -> dict[str, bool]:
    m = SEC_DOC.fullmatch(ev.official_url)
    return {"document_officiel_sec": bool(m) and m.group(2) == ev.official_id
            and (m.group(1) == "suspensions") == (ev.kind == "suspension_cotation")}


def collecter_sec_poursuites(ctx) -> list[Evenement]:
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus, syms = deja(ctx, "sec_poursuites"), symboles(ctx)
    evs = []
    for url, sorte in ((SEC_SUSPENSIONS, "suspension"), (SEC_PROCEDURES, "procedure")):
        for item in _items(ctx.client.get(url).contenu.decode("utf-8", "replace")):
            ev = evenement_sec(item, sorte, syms)
            if ev and ev.published_on >= limite and ev.id not in lus:
                evs.append(ev)
    return evs


# ---------- OFAC : sanctions ----------

OFAC_LISTE = "https://ofac.treasury.gov/recent-actions"
OFAC_ACTION = re.compile(r"https://ofac\.treasury\.gov/recent-actions/(\d{8}(?:_\d+)?)")
OFAC_VERSION = "ofac-1"
CATEGORIES_SDN = {"individuals": "personnes", "entities": "entités", "vessels": "navires", "aircraft": "aéronefs"}


def lire_liste_ofac(page: str) -> list[dict]:
    actions, vus = [], set()
    for href, titre in re.findall(r'<a[^>]+href="((?:https://ofac\.treasury\.gov)?/recent-actions/\d{8}(?:_\d+)?)"[^>]*>(.*?)</a>',
                                  page, re.S):
        url = href if href.startswith("https://") else f"https://ofac.treasury.gov{href}"
        if url not in vus:
            vus.add(url)
            actions.append({"url": url, "titre": texte_html(titre)})
    return actions


def _champ_ofac(page: str, classe: str) -> str:
    """Le HTML d'un champ officiel de la page (de son étiquette jusqu'au champ suivant)."""
    debut = page.find(f"field--name-{classe}")
    if debut < 0:
        return ""
    fin = page.find("field--name-", debut + 20)
    return page[debut:fin if fin > 0 else len(page)]


def lire_action_ofac(page: str) -> dict:
    """Page officielle d'une action : titre, date, communiqués du Trésor, et COMBIEN de fiches sont ajoutées
    ou retirées de la liste SDN. Les noms ne sont pas extraits : ils contiennent des virgules (« CO., LIMITED »,
    « S. DE R.L. DE C.V. ») et les couper au hasard serait inventer."""
    m = re.search(r"<title>(.*?)\|", page, re.S)
    titre = texte_html(m.group(1)) if m else ""
    m = re.search(r">\s*(\d\d)/(\d\d)/(\d{4})\s*<", _champ_ofac(page, "field-release-date"))
    jour = f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else None
    communiques = [texte_html(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", _champ_ofac(page, "field-press-release-link"),
                                                      re.S)]
    corps = _champ_ofac(page, "field-body") or page
    texte = texte_html(corps.replace("<", " <"))
    ajouts: dict[str, int] = {}
    retraits = 0
    blocs = re.split(r"(The following [^:]{5,90}OFAC's SDN List:)", texte)
    for i in range(1, len(blocs) - 1, 2):
        entete = blocs[i].lower()
        # La liste s'arrête au paragraphe administratif qui peut la suivre (vu le 23 sept. 2026 : « Unrelated
        # Administrative List Changes… », compté à tort comme 2 retraits de plus).
        contenu = re.split(r"Unrelated Administrative List Changes", blocs[i + 1])[0]
        fiches = len(re.findall(r"(?:\[[A-Z0-9-]+\]\s*)+", contenu))  # chaque fiche finit par [PROGRAMME(S)]
        if "added" in entete:
            cat = next((v for k, v in CATEGORIES_SDN.items() if k[:6] in entete), "fiches")
            ajouts[cat] = ajouts.get(cat, 0) + fiches
        elif "deletion" in entete or "removed" in entete:
            retraits += fiches
    return {"titre": titre, "jour": jour, "communiques": communiques, "ajouts": ajouts, "retraits": retraits,
            "texte": texte}


def resume_ofac(compte: dict) -> str:
    return ", ".join(f"{n} {cat}" for cat, n in compte.items() if n)


def evenement_ofac(url: str, page: str) -> Evenement | None:
    m = OFAC_ACTION.fullmatch(url)
    a = lire_action_ofac(page)
    if not m or not a["jour"] or not a["titre"] or "Designation" not in a["titre"]:
        return None  # licences, FAQ, règlements : pas des désignations
    notes = [f"Communiqué du Trésor : {c}" for c in a["communiques"][:2]]
    if a["ajouts"]:
        notes.append(f"Ajoutés à la liste des sanctions (SDN) : {resume_ofac(a['ajouts'])}.")
    if a["retraits"]:
        notes.append(f"Retirés de la liste : {a['retraits']} fiche{'s' if a['retraits'] > 1 else ''}.")
    return Evenement(
        source="sanctions_us", official_id=m.group(1), category="gouvernement", kind="sanctions",
        title=f"Sanctions américaines (OFAC) : {a['titre']}", occurred_on=a["jour"], published_on=a["jour"],
        official_url=url, sha256=empreinte(a["texte"].encode("utf-8")), parser_version=OFAC_VERSION, notes=notes,
        data={"titre_officiel": a["titre"], "ajouts": a["ajouts"], "retraits": a["retraits"],
              "communiques": a["communiques"]},
    )


@controle_source("sanctions_us")
def controles_ofac(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "action_officielle": bool(OFAC_ACTION.fullmatch(ev.official_url)) and ev.official_url.endswith(ev.official_id),
        "date_de_l_adresse_concorde": ev.official_id[:8] == ev.published_on.replace("-", ""),
        "liste_sdn_lue": bool(d.get("ajouts") or d.get("retraits")),
        "titre_et_liste_concordent": ("Removal" in d.get("titre_officiel", "")) <= bool(d.get("retraits"))
    }


def collecter_ofac(ctx) -> list[Evenement]:
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).strftime("%Y%m%d")
    lus = deja(ctx, "sanctions_us")
    evs = []
    for action in lire_liste_ofac(ctx.client.get(OFAC_LISTE).contenu.decode("utf-8", "replace")):
        numero = OFAC_ACTION.fullmatch(action["url"]).group(1)
        if numero[:8] < limite or f"sanctions_us:{numero}" in lus or "Designation" not in action["titre"]:
            continue
        ev = evenement_ofac(action["url"], ctx.client.get(action["url"]).contenu.decode("utf-8", "replace"))
        if ev:
            evs.append(ev)
    return evs


# ---------- FTC : fin anticipée de l'examen antitrust d'une fusion ----------

FTC_FLUX = "https://www.ftc.gov/feeds/hsr-early-termination-notices.xml"
FTC_LIEN = re.compile(r"https://www\.ftc\.gov/legal-library/browse/early-termination-notices/(\d{8})")
FTC_VERSION = "ftc-1"


def lire_ftc(flux: str) -> list[dict]:
    """Chaque avis du flux officiel : ses champs nommés (Date, Transaction Number, Acquiring Party…)."""
    avis = []
    for it in re.findall(r"<item>(.*?)</item>", flux, re.S):
        def balise(nom):
            m = re.search(rf"<{nom}>(.*?)</{nom}>", it, re.S)
            return html.unescape(m.group(1)).strip() if m else ""
        desc = balise("description")
        champs: dict[str, list[str]] = {}
        for etiquette, valeurs in re.findall(r'field__label">(.*?)</div>\s*<div class="field__items">(.*?)</div>\s*</div>',
                                             desc, re.S):
            champs[texte_html(etiquette)] = [texte_html(v) for v in re.findall(r'field__item">(.*?)</div>', valeurs + "</div>", re.S)]
        jour = re.search(r'field--name-field-date.*?datetime="(\d{4}-\d\d-\d\d)', desc, re.S)
        avis.append({"lien": balise("link"), "publie": balise("pubDate"), "jour": jour.group(1) if jour else None,
                     "numero": (champs.get("Transaction Number") or [""])[0],
                     "acquereur": (champs.get("Acquiring Party") or [""])[0],
                     "partie_visee": (champs.get("Acquired Party") or [""])[0],
                     "entites_visees": champs.get("Acquired Entities") or [],
                     "statut": (champs.get("Granting Status") or [""])[0]})
    return avis


def evenement_ftc(a: dict, syms=None) -> Evenement | None:
    m = FTC_LIEN.fullmatch(a["lien"])
    publie = jour_new_york(a["publie"])
    if not m or not a["jour"] or not publie or a["statut"] != "Granted" or not a["acquereur"] or not a["partie_visee"]:
        return None
    tickers = []
    if syms is not None:
        for nom in [a["acquereur"], a["partie_visee"], *a["entites_visees"]]:
            cote = syms.par_nom(nom)
            if cote and cote["ticker"] not in tickers:
                tickers.append(cote["ticker"])
    return Evenement(
        source="ftc_fusions", official_id=m.group(1), category="gouvernement", kind="fusion_feu_vert",
        title=f"FTC : feu vert antitrust anticipé, {a['acquereur']} (acquéreur) et {a['partie_visee']} (partie visée)",
        occurred_on=a["jour"], published_on=max(publie, a["jour"]), official_url=a["lien"], sha256=canonique(a),
        parser_version=FTC_VERSION, tickers=tickers, entities=[a["acquereur"], a["partie_visee"]],
        data={k: a[k] for k in ("numero", "acquereur", "partie_visee", "entites_visees", "statut")},
    )


@controle_source("ftc_fusions")
def controles_ftc(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "numero_de_transaction_officiel": bool(re.fullmatch(r"20\d{6}", d.get("numero", "")))
                                          and ev.official_url.endswith(d["numero"]),
        "feu_vert_accorde": d.get("statut") == "Granted",
        "parties_lues": bool(d.get("acquereur")) and bool(d.get("partie_visee")),
    }


def collecter_ftc(ctx) -> list[Evenement]:
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus, syms = deja(ctx, "ftc_fusions"), symboles(ctx)
    evs = []
    for a in lire_ftc(ctx.client.get(FTC_FLUX).contenu.decode("utf-8", "replace")):
        ev = evenement_ftc(a, syms)
        if ev and ev.occurred_on >= limite and ev.id not in lus:
            evs.append(ev)
    return evs
