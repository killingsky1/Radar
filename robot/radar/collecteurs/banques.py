"""Banques centrales : décisions de taux directeur.

- Fed (États-Unis) : communiqué du FOMC (« The Committee decided to raise/lower/maintain the target range… »).
- Banque du Canada : communiqué des dates d'annonce fixes (« The Bank of Canada today held/reduced its target… »).

La décision est lue dans la phrase officielle du communiqué, le jour même. (La série officielle du taux
de la Banque du Canada change seulement le lendemain : vérifié sur 10 décisions de 2024-2025.)
Formats vérifiés sur de vrais communiqués : Fed juillet et septembre 2026 ; Banque du Canada juin 2024 à sept. 2026.
"""

from __future__ import annotations

import html
import re
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source

VERSION = "banques-1"
FLUX_FED = "https://www.federalreserve.gov/feeds/press_monetary.xml"
FLUX_BDC = "https://www.bankofcanada.ca/content_type/press-releases/feed/"
FRACTIONS = {"¼": 0.25, "½": 0.5, "¾": 0.75}


def texte_html(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def nombre(texte: str) -> float:
    """« 3-3/4 » -> 3.75 ; « 1/4 » -> 0.25 ; « 4¾ » -> 4.75 ; « 2.25 » -> 2.25."""
    t = texte.strip()
    for f, v in FRACTIONS.items():
        if t.endswith(f):
            return float(t[:-1] or 0) + v
    m = re.fullmatch(r"(?:(\d+)-)?(\d+)/(\d+)", t)
    if m:
        return float(m.group(1) or 0) + int(m.group(2)) / int(m.group(3))
    return float(t)


def pourcent(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " %"


def _items(flux: str) -> list[dict]:
    items = []
    for it in re.findall(r"<item[ >](.*?)</item>", flux, re.S):
        def champ(nom):
            m = re.search(rf"<{nom}>(.*?)</{nom}>", it, re.S)
            return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)).strip()) if m else ""
        items.append({"titre": champ("title"), "lien": champ("link"), "date": champ("pubDate") or champ("dc:date")})
    return items


# ---------- Fed ----------

DECISION_FED = re.compile(
    r"decided to (raise|lower|maintain|reduce|increase) the target range for the federal funds rate "
    r"(?:by ([\d/-]+) percentage points? )?(?:to|at) ([\d/-]+) to ([\d/-]+) percent")
VERBES_FED = {"raise": "releve", "increase": "releve", "lower": "abaisse", "reduce": "abaisse", "maintain": "maintenu"}


def lire_fomc(page: str) -> dict:
    texte = texte_html(page[page.find('id="article"'):] if 'id="article"' in page else page)
    debut = texte.find("The Federal Open Market Committee approved")
    if debut < 0:
        debut = texte.find("The Committee decided")
    fin = texte.find("For media inquiries", debut)
    declaration = texte[debut:fin if fin > 0 else None].strip() if debut >= 0 else ""
    d = {"declaration": declaration}
    m = DECISION_FED.search(declaration)
    if m:
        d.update(decision=VERBES_FED[m.group(1)], pas=nombre(m.group(2)) if m.group(2) else None,
                 bas=nombre(m.group(3)), haut=nombre(m.group(4)))
    v = re.search(r"by a (\d+)\s*[–-]\s*(\d+) vote", declaration)
    if v:
        d["vote"] = f"{v.group(1)}-{v.group(2)}"
    return d


def evenement_fed(item: dict, page: str) -> Evenement | None:
    m = re.fullmatch(r"https://www\.federalreserve\.gov/newsevents/pressreleases/(monetary\d{8}\w)\.htm", item["lien"])
    try:
        quand = parsedate_to_datetime(item["date"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except (TypeError, ValueError):
        return None
    if not m:
        return None
    d = lire_fomc(page)
    if d.get("decision") == "maintenu":
        titre = f"Fed : taux directeur maintenu entre {pourcent(d['bas'])} et {pourcent(d['haut'])}"
    elif d.get("decision"):
        mot = "relevé" if d["decision"] == "releve" else "abaissé"
        pas = f" de {pourcent(d['pas']).replace(' %', ' point')}" if d.get("pas") else ""
        titre = f"Fed : taux directeur {mot}{pas}, entre {pourcent(d['bas'])} et {pourcent(d['haut'])}"
    else:
        titre = "Fed : décision de taux (texte à lire sur le site officiel)"
    if d.get("vote"):
        titre += " (vote : {} pour, {} contre)".format(*d["vote"].split("-"))
    return Evenement(
        source="fed", official_id=m.group(1), category="gouvernement", kind="decision_taux", title=titre,
        occurred_on=quand, published_on=quand, official_url=item["lien"],
        sha256=empreinte(d["declaration"].encode("utf-8")), parser_version=VERSION,
        entities=["Federal Reserve (FOMC)"],
        direction={"releve": -1, "abaisse": 1}.get(d.get("decision"), 0),
        data={**{k: v for k, v in d.items() if k != "declaration"}, "resume": d["declaration"][:700],
              "titre_officiel": item["titre"]},
    )


@controle_source("fed")
def controles_fed(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "decision_lue": d.get("decision") in ("releve", "abaisse", "maintenu"),
        "fourchette_plausible": d.get("bas") is not None and 0 <= d["bas"] < d["haut"] <= 25
        and abs(d["haut"] - d["bas"] - 0.25) < 1e-9,
        "vote_lu": bool(d.get("vote")),
    }


def collecter_fed(ctx) -> list[Evenement]:
    items = _items(ctx.client.get(FLUX_FED).contenu.decode("utf-8", "replace"))
    if not items:
        raise RuntimeError("fil de la Fed vide")
    deja = Depot(ctx.donnees).ids_enregistres({"fed"})
    evs = []
    for it in items:
        if not it["titre"].startswith("Federal Reserve issues FOMC statement"):
            continue
        ident = it["lien"].rsplit("/", 1)[-1].replace(".htm", "")
        if ident in deja:
            continue
        ev = evenement_fed(it, ctx.client.get(it["lien"]).contenu.decode("utf-8", "replace"))
        if ev:
            evs.append(ev)
    return evs


# ---------- Banque du Canada ----------

DECISION_BDC = re.compile(
    r"The Bank of Canada today (held|reduced|lowered|cut|raised|increased) its target for the overnight rate "
    r"(?:by (\d+) basis points )?(?:at|to) (\d+(?:\.\d+)?[¼½¾]?|[¼½¾])\s?%")
VERBES_BDC = {"held": "maintenu", "reduced": "abaisse", "lowered": "abaisse", "cut": "abaisse",
              "raised": "releve", "increased": "releve"}
VERBES_TITRE = {"maintenu": ("maintains", "holds"), "abaisse": ("reduces", "lowers", "cuts"),
                "releve": ("raises", "increases")}
LIEN_BDC = re.compile(r"https://www\.bankofcanada\.ca/\d{4}/\d\d/(fad-press-release-(\d{4}-\d\d-\d\d))/?")


def lire_decision_bdc(page: str) -> dict:
    titre = re.search(r'<meta property="og:title" content="([^"]+)"', page)
    texte = texte_html(page)
    d = {"titre_officiel": html.unescape(titre.group(1)).strip() if titre else ""}
    m = DECISION_BDC.search(texte)
    if m:
        fin = texte.find(".", m.end())
        d.update(phrase=texte[m.start():fin + 1] if fin > 0 else m.group(0), decision=VERBES_BDC[m.group(1)],
                 pas_points_base=int(m.group(2)) if m.group(2) else None, taux=nombre(m.group(3)))
    return d


def evenement_bdc(item: dict, page: str) -> Evenement | None:
    m = LIEN_BDC.fullmatch(item["lien"])
    if not m:
        return None
    d = lire_decision_bdc(page)
    if d.get("decision") == "maintenu":
        titre = f"Banque du Canada : taux directeur maintenu à {pourcent(d['taux'])}"
    elif d.get("decision"):
        mot = "relevé" if d["decision"] == "releve" else "abaissé"
        pas = f" de {pourcent(d['pas_points_base'] / 100).replace(' %', ' point')}" if d.get("pas_points_base") else ""
        titre = f"Banque du Canada : taux directeur {mot}{pas}, à {pourcent(d['taux'])}"
    else:
        titre = "Banque du Canada : décision de taux (texte à lire sur le site officiel)"
    canon = f"{d['titre_officiel']}\n{d.get('phrase', '')}"
    return Evenement(
        source="banque_canada", official_id=m.group(1), category="canada", kind="decision_taux", title=titre,
        occurred_on=m.group(2), published_on=m.group(2), official_url=item["lien"],
        sha256=empreinte(canon.encode("utf-8")), parser_version=VERSION, entities=["Banque du Canada"],
        currency="CAD", direction={"releve": -1, "abaisse": 1}.get(d.get("decision"), 0),
        data={**d, "resume": d.get("phrase", "")},
    )


@controle_source("banque_canada")
def controles_bdc(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    titre = d.get("titre_officiel", "").lower()
    verbes = VERBES_TITRE.get(d.get("decision"), ())
    taux_titre = re.search(r"(?:at|to) (\d+(?:\.\d+)?[¼½¾]?|[¼½¾])\s?%", d.get("titre_officiel", ""))
    return {
        "decision_lue": d.get("decision") in VERBES_TITRE,
        "taux_plausible": d.get("taux") is not None and 0 <= d["taux"] <= 20,
        # Le titre officiel dit la même chose que la phrase (même verbe, même taux s'il est écrit)
        "titre_officiel_concorde": any(v in titre for v in verbes)
        and (taux_titre is None or abs(nombre(taux_titre.group(1)) - d.get("taux", -1)) < 1e-9),
    }


def collecter_bdc(ctx) -> list[Evenement]:
    items = _items(ctx.client.get(FLUX_BDC).contenu.decode("utf-8", "replace"))
    if not items:
        raise RuntimeError("fil de la Banque du Canada vide")
    deja = Depot(ctx.donnees).ids_enregistres({"banque_canada"})
    evs = []
    for it in items:
        m = LIEN_BDC.fullmatch(it["lien"])
        if not m or m.group(1) in deja:
            continue
        ev = evenement_bdc(it, ctx.client.get(it["lien"]).contenu.decode("utf-8", "replace"))
        if ev:
            evs.append(ev)
    return evs
