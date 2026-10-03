"""Canada, économie : examens de fusion (Bureau de la concurrence), sanctions canadiennes et grands indicateurs
de Statistique Canada.

Sources officielles, gratuites, sans compte, lues en français ; robots.txt vérifiés le 3 octobre 2026 :
- bureau-concurrence.canada.ca : pas de robots.txt (tout est permis). Le rapport est mis à jour chaque mardi.
- international.gc.ca : permis. La liste consolidée (XML) n'a pas force de loi : les règlements font foi.
- www150.statcan.gc.ca : permis, 2 s entre deux requêtes (Crawl-delay).

Licences : le rapport des fusions et la liste des sanctions sont inscrits au portail du gouvernement ouvert (Licence du
gouvernement ouvert – Canada) ; Statistique Canada a sa propre licence ouverte. Les deux permettent la réutilisation,
avec la mention de la source affichée dans l'app.
"""

from __future__ import annotations

import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import Evenement
from ..validate import controle_source
from .gazette import date_modifiee, details, extrait, texte
from .regulateurs import canonique, deja
from .sec import symboles

FENETRE_JOURS = 30
TORONTO = ZoneInfo("America/Toronto")


def slug(t: str, n: int = 80) -> str:
    a = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", a))[:n].strip("-")


def jour_long(iso: str) -> str:
    mois = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
            "novembre", "décembre")
    d = date.fromisoformat(iso)
    return f"{'1er' if d.day == 1 else d.day} {mois[d.month - 1]} {d.year}"


def symboles_de(noms: list[str], syms) -> list[str]:
    """Les symboles des compagnies cotées dont le nom officiel est EXACTEMENT un de ces noms (rien n'est deviné)."""
    tickers = []
    for n in noms:
        cote = syms.par_nom(n) if syms is not None else None
        if cote and cote["ticker"] not in tickers:
            tickers.append(cote["ticker"])
    return tickers


# ---------- Bureau de la concurrence : examens de fusion ----------

CONCURRENCE = "https://bureau-concurrence.canada.ca/fr/fusions-acquisitions/rapport-examens-fusions-termines"
CONCURRENCE_VERSION = "concurrence-1"
EN_COURS = "en cours"
# Les codes de la note ** du rapport officiel (quelques lignes du rapport français gardent le code anglais).
RESULTATS = {"LNI": "lettre de non-intervention", "CDP": "certificat de décision préalable",
             "ARC": "certificat de décision préalable", "cons.": "consentement enregistré",
             "déc. jud.": "décision judiciaire", "TA": "transaction abandonnée par les parties",
             "autre": "autre raison", "Other": "autre raison"}


def lire_examens(page: str) -> list[dict]:
    """Les lignes du tableau officiel : parties, date de début, date de conclusion, SCIAN, résultat."""
    tableau = re.search(r"<table.*?</table>", page, re.S)
    lignes = []
    for tr in re.findall(r"<tr.*?</tr>", tableau.group(0) if tableau else "", re.S):
        c = [texte(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) == 5:
            lignes.append({"parties": c[0], "debut": c[1], "conclusion": c[2], "scian": c[3], "code": c[4]})
    return lignes


def parties(t: str) -> tuple[str, list[str]]:
    """« Acquéreur / Cible 1, Cible 2 et Cible 3 » -> (acquéreur, [cibles])."""
    acquereur, _, cibles = t.partition(" / ")
    return acquereur.strip(), [c.strip() for c in re.split(r"\s*,\s*(?:et\s+)?|\s+et\s+", cibles) if c.strip()]


def evenements_examen(x: dict, page_modifiee: str | None, syms=None) -> list[Evenement]:
    """Une info quand l'examen s'ouvre (encore « en cours ») et une autre quand il est conclu."""
    acquereur, cibles = parties(x["parties"])
    cle = f"{x['debut']}:{slug(x['parties'])}"
    tickers = symboles_de([acquereur, *cibles], syms)
    conclu = x["conclusion"] != EN_COURS
    libelle = RESULTATS.get(x["code"], x["code"])
    d = {**x, "acquereur": acquereur, "cibles": cibles, "resultat": "" if not conclu else libelle,
         "page_modifiee_le": page_modifiee,
         "details": details(("Acquéreur", acquereur), ("Visé(s)", ", ".join(cibles)), ("Examen ouvert le", x["debut"]),
                            ("Examen conclu le", x["conclusion"] if conclu else ""),
                            ("Résultat", libelle if conclu else "en cours"), ("Industrie (SCIAN)", x["scian"]))}
    evs = []
    for etape in (("conclu",) if conclu else ("ouvert",)):
        jour = x["conclusion"] if etape == "conclu" else x["debut"]
        titre = (f"Bureau de la concurrence : examen de fusion conclu ({libelle}), {x['parties']}" if etape == "conclu"
                 else f"Bureau de la concurrence : examen de fusion ouvert, {x['parties']}")
        evs.append(Evenement(
            source="concurrence_ca", official_id=f"{cle}:{etape}", category="canada",
            kind="fusion_examen_conclu" if etape == "conclu" else "fusion_examen_ouvert", title=titre,
            occurred_on=jour, published_on=max(jour, page_modifiee or jour), official_url=CONCURRENCE,
            sha256=canonique(x), parser_version=CONCURRENCE_VERSION, tickers=tickers,
            entities=[acquereur, *cibles], currency="CAD", data=d,
            notes=["Date de publication : la date de mise à jour de la page officielle (le rapport est mis à jour "
                   "chaque semaine)."]))
    return evs


@controle_source("concurrence_ca")
def controles_examen(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    dates = all(re.fullmatch(r"\d{4}-\d\d-\d\d", v or "") for v in (d.get("debut"),
                                                                    *((d.get("conclusion"),) if ev.kind.endswith("conclu") else ())))
    return {
        "resultat_officiel_connu": d.get("code") in RESULTATS or d.get("code") == EN_COURS,
        "dates_dans_l_ordre": dates and (not ev.kind.endswith("conclu") or d["conclusion"] >= d["debut"]),
        "parties_lues": bool(d.get("acquereur")) and bool(d.get("cibles")),
        "industrie_scian": bool(re.fullmatch(r"\d{2,6}", d.get("scian") or "")),
    }


def collecter_concurrence(ctx) -> list[Evenement]:
    page = ctx.client.get(CONCURRENCE).contenu.decode("utf-8", "replace")
    lignes = lire_examens(page)
    if not lignes:
        raise RuntimeError("tableau des examens de fusion illisible")
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus, syms, modifiee = deja(ctx, "concurrence_ca"), symboles(ctx), date_modifiee(page)
    evs = []
    for x in lignes:
        for ev in evenements_examen(x, modifiee, syms):
            if ev.occurred_on >= limite and ev.official_id not in lus:
                evs.append(ev)
    return evs


# ---------- Sanctions canadiennes : nouvelles inscriptions ----------

SANCTIONS_XML = ("https://www.international.gc.ca/world-monde/assets/office_docs/international_relations-"
                 "relations_internationales/sanctions/sema-lmes.xml")
SANCTIONS_PAGE = ("https://www.international.gc.ca/world-monde/international_relations-relations_internationales/"
                  "sanctions/consolidated-consolide.aspx?lang=fra")
SANCTIONS_VERSION = "sanctions-ca-1"
B = {"pays": "Country-Pays", "nom": "LastName-NomDeFamille", "prenom": "GivenName-Prenom", "entite": "EntityOrShip-EntiteOuNavire",
     "annexe": "Schedule-Annexe", "article": "Item-NumeroDarticle", "date": "DateOfListing-DateDinscription",
     "omi": "ShipIMONumber-NumeroOMIDuNavire", "titre": "TitleOrShipType-TitreOuTypeDeNavire"}


def lire_sanctions(contenu: bytes) -> list[dict]:
    racine = ET.fromstring(contenu)
    return [{k: " ".join((r.findtext(b) or "").replace("\xa0", " ").split()) for k, b in B.items()}
            for r in racine.findall("record")]


def regime(pays: str) -> str:
    """« Russia / Russie » -> « Russie » (la partie française)."""
    return pays.split(" / ")[-1].strip()


def evenements_sanctions(inscriptions: list[dict], depuis: str, syms=None) -> list[Evenement]:
    groupes: dict[tuple[str, str], list[dict]] = {}
    for x in inscriptions:
        if re.fullmatch(r"\d{4}-\d\d-\d\d", x["date"]) and x["date"] >= depuis:
            groupes.setdefault((x["date"], regime(x["pays"])), []).append(x)
    evs = []
    for (jour, reg), lot in sorted(groupes.items()):
        entites = [x["entite"] for x in lot if x["entite"]]
        navires = [x["entite"] for x in lot if x["entite"] and x["omi"]]
        personnes = [f"{x['prenom']} {x['nom']}".strip() for x in lot if not x["entite"]]
        n = len(lot)
        quoi = ", ".join(p for p in (f"{len(personnes)} personne(s)" if personnes else "",
                                     f"{len(entites) - len(navires)} entité(s)" if len(entites) > len(navires) else "",
                                     f"{len(navires)} navire(s)" if navires else "") if p)
        d = {"regime": reg, "date": jour, "nombre": n, "personnes": personnes, "entites": entites, "navires": navires,
             "annexes": sorted({x["annexe"] for x in lot if x["annexe"]}), "liste_xml": SANCTIONS_XML,
             "resume": f"{n} inscription(s) le {jour_long(jour)} : {quoi}.",
             "details": details(("Régime", reg), ("Inscrites le", jour), ("Personnes", ", ".join(personnes)),
                                ("Entités et navires", ", ".join(entites)))}
        evs.append(Evenement(
            source="sanctions_ca", official_id=f"{jour}:{slug(reg, 60)}", category="canada", kind="sanctions_inscriptions",
            title=f"Sanctions canadiennes ({reg}) : {n} nouvelle(s) inscription(s)",
            occurred_on=jour, published_on=jour, official_url=SANCTIONS_PAGE,
            sha256=canonique({"lot": sorted(lot, key=lambda x: (x["annexe"], x["article"], x["nom"], x["entite"]))}),
            parser_version=SANCTIONS_VERSION, tickers=symboles_de(entites, syms), entities=[reg], currency="CAD",
            data=d, notes=["La liste consolidée n'a pas force de loi : seuls les règlements font foi."]))
    return evs


@controle_source("sanctions_ca")
def controles_sanctions(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "date_d_inscription_valide": bool(re.fullmatch(r"\d{4}-\d\d-\d\d", d.get("date") or "")),
        "chaque_inscription_nommee": bool(d.get("nombre")) and all(d.get("personnes") or [True])
                                     and all(d.get("entites") or [True]),
        "regime_lu": bool(d.get("regime")),
    }


def collecter_sanctions(ctx) -> list[Evenement]:
    inscriptions = lire_sanctions(ctx.client.get(SANCTIONS_XML).contenu)
    if len(inscriptions) < 1000:  # 5 707 inscriptions le 3 octobre 2026 : une liste presque vide est une erreur
        raise RuntimeError(f"liste des sanctions incomplète ({len(inscriptions)} inscriptions)")
    depuis = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus = deja(ctx, "sanctions_ca")
    return [ev for ev in evenements_sanctions(inscriptions, depuis, symboles(ctx)) if ev.official_id not in lus]


# ---------- Statistique Canada : les grands indicateurs du Quotidien ----------

QUOTIDIEN = "https://www150.statcan.gc.ca/n1/fr/rss/dai-quo/0-fra.atom"
PRINCIPAUX = "https://www150.statcan.gc.ca/n1/dai-quo/cal1-fra.htm"
STATCAN_VERSION = "statcan-1"
NS = {"a": "http://www.w3.org/2005/Atom"}
LIEN_QUOTIDIEN = re.compile(r"https://www\.statcan\.gc\.ca/daily-quotidien/(\d{6})/(dq\d{6}[a-z]+)-fra\.htm")


def lire_principaux(page: str) -> list[str]:
    """La liste officielle des « Communiqués économiques principaux » (menu de la page du calendrier)."""
    menu = re.search(r'<select[^>]*id="select_keylist"[^>]*>(.*?)</select>', page, re.S)
    return [" ".join(html.unescape(o).split()) for o in re.findall(r"<option[^>]*>(.*?)</option>", menu.group(1), re.S)] \
        if menu else []


def lire_quotidien(contenu: bytes) -> list[dict]:
    racine = ET.fromstring(contenu)
    entrees = []
    for e in racine.findall("a:entry", NS):
        titre, resume, lien = e.find("a:title", NS), e.find("a:summary", NS), e.find("a:link", NS)
        entrees.append({"titre": " ".join("".join(titre.itertext()).split()) if titre is not None else "",
                        "resume": " ".join("".join(resume.itertext()).split()) if resume is not None else "",
                        "lien": (lien.get("href") if lien is not None else "") or "",
                        "mis_a_jour": (e.findtext("a:updated", "", NS)).strip()})
    return entrees


def indicateur(titre: str, noms: list[str]) -> str | None:
    """Le grand indicateur dont le titre est « <nom officiel>, <période> » (le nom le plus long gagne)."""
    return next((n for n in sorted(noms, key=len, reverse=True) if titre.startswith(n + ", ")), None)


def evenement_statcan(e: dict, noms: list[str]) -> Evenement | None:
    nom, m = indicateur(e["titre"], noms), LIEN_QUOTIDIEN.fullmatch(e["lien"])
    try:
        jour = datetime.fromisoformat(e["mis_a_jour"]).astimezone(TORONTO).date().isoformat()
    except ValueError:
        return None
    if not nom or not m:
        return None
    periode = e["titre"][len(nom) + 2:]
    d = {"indicateur": nom, "periode": periode, "lien": e["lien"], "mis_a_jour": e["mis_a_jour"],
         "resume": extrait(e["resume"]), "liste_officielle": PRINCIPAUX,
         "details": details(("Indicateur", nom), ("Période", periode))}
    return Evenement(
        source="statcan", official_id=f"{m.group(1)}/{m.group(2)}", category="canada", kind="indicateur_principal",
        title=f"Statistique Canada : {e['titre']}", occurred_on=jour, published_on=jour, official_url=e["lien"],
        sha256=canonique({k: e[k] for k in ("titre", "resume", "lien", "mis_a_jour")}), parser_version=STATCAN_VERSION,
        entities=["Statistique Canada"], currency="CAD", data=d)


@controle_source("statcan")
def controles_statcan(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "indicateur_de_la_liste_officielle": bool(d.get("indicateur")) and ev.title.startswith(
            f"Statistique Canada : {d['indicateur']}, "),
        "lien_du_quotidien": bool(LIEN_QUOTIDIEN.fullmatch(ev.official_url)),
        "resume_lu": bool(d.get("resume")),
    }


def collecter_statcan(ctx) -> list[Evenement]:
    noms = lire_principaux(ctx.client.get(PRINCIPAUX).contenu.decode("utf-8", "replace"))
    if len(noms) < 10:  # 28 le 3 octobre 2026
        raise RuntimeError(f"liste des grands indicateurs illisible ({len(noms)} noms)")
    entrees = lire_quotidien(ctx.client.get(QUOTIDIEN).contenu)
    if not entrees:
        raise RuntimeError("fil du Quotidien vide")
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus = deja(ctx, "statcan")
    evs = []
    for e in entrees:
        ev = evenement_statcan(e, noms)
        if ev and ev.occurred_on >= limite and ev.official_id not in lus:
            evs.append(ev)
    return evs
