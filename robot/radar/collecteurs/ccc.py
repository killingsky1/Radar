"""Corporation commerciale canadienne (CCC) : rapport trimestriel des transactions signées (contrats de gouvernement à
gouvernement : la CCC signe avec un gouvernement étranger et confie le travail à une compagnie canadienne).

Publié en PDF sur la page des rapports de la CCC (www.ccc.ca : son robots.txt permet ces pages ; vérifié le 3 octobre
2026). Conditions d'utilisation de la CCC : exploitation commerciale interdite, donc usage personnel seulement.

Une info par rapport : le nombre de transactions, leurs fourchettes de montants (officielles) et chaque ligne
(exportateur, destination, description). Beaucoup d'exportateurs sont anonymes (« Canadian Exporter »).
Mesuré : avril à juin 2026, 37 transactions ; janvier à mars 2026, 55 (dont une de « plus de 500 M$ »).
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from ..models import Evenement
from ..validate import controle_source
from .gazette import details, texte
from .regulateurs import canonique, deja
from .sec import symboles

VERSION = "ccc-1"
PAGE = "https://www.ccc.ca/en/about/corporate-reports/"
TORONTO = ZoneInfo("America/Toronto")
MOIS_EN = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August",
                                       "September", "October", "November", "December"), 1)}
MOIS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
           "décembre")
JETON_MONTANT = re.compile(r"^[<>]?\$[\d,.]+$|^[–-]$")
FOURCHETTE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*[–-]\s*\$\s*([\d,]+(?:\.\d+)?)")
MOINS_DE = re.compile(r"<\s*\$\s*([\d,]+(?:\.\d+)?)")
PLUS_DE = re.compile(r">\s*\$\s*([\d,]+(?:\.\d+)?)")  # ex. « >$500,000,000.00 » (janvier à mars 2026)
MEME_LIGNE = 2.0  # points : les cellules d'une même ligne peuvent être décalées de quelques dixièmes


# ---------- La page des rapports ----------

def rapports(page: str) -> list[dict]:
    """Les rapports des transactions signées, du plus récent au plus ancien : lien PDF et fin du trimestre."""
    debut = page.find('id="transactions"')
    fin = page.find("Quarterly Disclosure of Business Event Participation", debut)
    if debut < 0 or fin < 0:
        return []
    liste, vus = [], set()
    for lien, libelle in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page[debut:fin], re.S):
        m = re.search(r"Quarter ending (?:on )?([A-Z][a-z]+) (\d{1,2}), (\d{4})", texte(libelle))
        url = urljoin(PAGE, lien)
        if m and m.group(1) in MOIS_EN and url not in vus:
            vus.add(url)
            liste.append({"url": url, "libelle": texte(libelle),
                          "fin": f"{m.group(3)}-{MOIS_EN[m.group(1)]:02d}-{int(m.group(2)):02d}"})
    return liste


def page_modifiee(page: str) -> str | None:
    """« article:modified_time » de la page (WordPress) : la page, avec ses liens, était à jour ce jour-là."""
    m = re.search(r'<meta property="article:modified_time" content="([^"]+)"', page)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1)).astimezone(TORONTO).date().isoformat()
    except ValueError:
        return None


# ---------- Le rapport PDF ----------

def fourchette(t: str) -> tuple[float, float | None] | None:
    """(minimum, maximum) d'une fourchette officielle ; maximum None pour « plus de … »."""
    m = FOURCHETTE.search(t)
    if m:
        return float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
    m = MOINS_DE.search(t)
    if m:
        return 0.0, float(m.group(1).replace(",", ""))
    m = PLUS_DE.search(t)
    return (float(m.group(1).replace(",", "")), None) if m else None


def lire_rapport(pdf: bytes) -> dict | None:
    """La période et chaque ligne du tableau. Une ligne = un montant ; les morceaux de description (au-dessus ou
    au-dessous) vont à la ligne au montant la plus proche."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        mots, colonnes, periode = [], None, None
        for numero, page in enumerate(doc.pages):
            mp = page.extract_words(x_tolerance=1.5, y_tolerance=2)
            plat = " ".join(w["text"] for w in mp)
            p = re.search(r"Pour la période\s*:\s*(\d{4}-\d\d-\d\d)\s+to/à\s+(\d{4}-\d\d-\d\d)", plat)
            periode = periode or (p.groups() if p else None)
            # La mention « Protected B - Protégé B # » en haut à droite de chaque page n'est pas une ligne du tableau.
            mp = [w for w in mp if not (w["top"] < 110 and w["text"] in ("Protected", "B", "-", "Protégé", "#"))]
            entetes = {w["text"]: w for w in mp if w["text"] in ("Exporter/Exportateur", "Destination/Destination",
                                                                  "Description/Description")}
            if len(entetes) == 3:
                colonnes = (entetes["Destination/Destination"]["x0"] - 5, entetes["Description/Description"]["x0"] - 5)
                haut = entetes["Description/Description"]["top"]
                bas_entete = max(w["bottom"] for w in mp if abs(w["top"] - haut) <= 12)
                mp = [w for w in mp if w["top"] > bas_entete + 1]  # titre, période et en-têtes : au-dessus
            elif colonnes is None:
                continue
            mots += [dict(w, top=w["top"] + numero * 10000) for w in mp]
    if not colonnes or not periode:
        return None
    # Lignes : mots dont le haut est à moins de MEME_LIGNE points du 1er mot de la ligne
    groupes: list[list[dict]] = []
    for w in sorted(mots, key=lambda w: (w["top"], w["x0"])):
        if groupes and w["top"] - groupes[-1][0]["top"] <= MEME_LIGNE:
            groupes[-1].append(w)
        else:
            groupes.append([w])
    rangs = []
    for ws in groupes:
        ws.sort(key=lambda w: w["x0"])
        montant = [w for w in ws if JETON_MONTANT.match(w["text"]) and w["x0"] > colonnes[1] + 100]
        rangs.append({"top": ws[0]["top"], "montant": " ".join(w["text"] for w in montant),
                      "exportateur": " ".join(w["text"] for w in ws if w["x0"] < colonnes[0]),
                      "destination": " ".join(w["text"] for w in ws if colonnes[0] <= w["x0"] < colonnes[1]),
                      "description": " ".join(w["text"] for w in ws if w["x0"] >= colonnes[1] and w not in montant)})
    ancres = [r for r in rangs if r["montant"]]
    if not ancres:
        return None
    # Chaque morceau (au-dessus ou au-dessous) va à la ligne au montant la plus proche, puis tout est remis
    # dans l'ordre vertical.
    morceaux = {id(a): {k: [(a["top"], a[k])] if a[k] else [] for k in ("exportateur", "destination", "description")}
                for a in ancres}
    for r in rangs:
        if r["montant"] or not any(r[k] for k in ("exportateur", "destination", "description")):
            continue
        proche = min(ancres, key=lambda a: abs(a["top"] - r["top"]))
        for k in ("exportateur", "destination", "description"):
            if r[k]:
                morceaux[id(proche)][k].append((r["top"], r[k]))
    transactions = []
    for a in ancres:
        m = {k: " ".join(x for _, x in sorted(v)) for k, v in morceaux[id(a)].items()}
        f = fourchette(a["montant"])
        transactions.append({**m, "montant": a["montant"], "min": f[0] if f else None, "max": f[1] if f else None})
    return {"debut": periode[0], "fin": periode[1], "transactions": transactions}


# ---------- Événement ----------

def argent(v: float) -> str:
    """Exact : 500 000 000 -> « 500 M$ » ; 2 500 000 -> « 2,5 M$ » ; 100 000 -> « 100 000 $ »."""
    if v >= 1e6:
        m = f"{v / 1e6:,.2f}".rstrip("0").rstrip(".")
        return m.replace(",", " ").replace(".", ",") + " M$"
    return f"{v:,.0f}".replace(",", " ") + " $"


def libelle_fourchette(t: dict) -> str:
    if t["min"] is None:
        return t["montant"]
    if t["max"] is None:
        return f"plus de {argent(t['min'])}"
    return f"moins de {argent(t['max'])}" if t["min"] == 0 else f"{argent(t['min'])} à {argent(t['max'])}"


def jour_fr(iso: str) -> str:
    a, m, j = (int(x) for x in iso.split("-"))
    return f"{'1er' if j == 1 else j} {MOIS_FR[m - 1]} {a}"


def evenement(r: dict, lien: dict, publie: str, syms=None) -> Evenement:
    ts = r["transactions"]
    plus_gros = max(ts, key=lambda t: (t["max"] is None, t["max"] or 0, t["min"] or 0))
    anonymes = sum(1 for t in ts if t["exportateur"].startswith("Canadian Exporter"))
    noms = sorted({t["exportateur"] for t in ts if t["exportateur"] and not t["exportateur"].startswith("Canadian Exporter")})
    tickers = []
    for n in noms:
        cote = syms.par_nom(n) if syms is not None else None
        if cote and cote["ticker"] not in tickers:
            tickers.append(cote["ticker"])
    total_min = sum(t["min"] or 0 for t in ts)
    total_max = None if any(t["max"] is None for t in ts) else sum(t["max"] for t in ts)  # « plus de » : pas de plafond
    d = {"debut": r["debut"], "fin": r["fin"], "pdf": lien["url"], "libelle_lien": lien["libelle"], "fin_lien": lien["fin"],
         "transactions": [dict(t, fourchette=libelle_fourchette(t)) for t in ts], "nombre": len(ts), "anonymes": anonymes,
         "page_modifiee_le": publie,
         "resume": f"{len(ts)} transactions signées du {jour_fr(r['debut'])} au {jour_fr(r['fin'])}, dont {anonymes} "
                   f"avec un exportateur anonyme. Montant total déclaré : "
                   + (f"entre {argent(total_min)} et {argent(total_max)}." if total_max is not None
                      else f"au moins {argent(total_min)} (une fourchette n'a pas de plafond)."),
         "details": details(("Période", f"{jour_fr(r['debut'])} au {jour_fr(r['fin'])}"), ("Transactions", str(len(ts))),
                            ("La plus grosse", f"{libelle_fourchette(plus_gros)} ({plus_gros['description']})"),
                            ("Exportateurs nommés", ", ".join(noms)))}
    return Evenement(
        source="ccc", official_id=f"{r['debut']}:{r['fin']}", category="canada", kind="transactions_signees",
        title=f"Corporation commerciale canadienne : {len(ts)} transactions signées "
              f"({jour_fr(r['debut'])} au {jour_fr(r['fin'])}), la plus grosse de {libelle_fourchette(plus_gros)}",
        occurred_on=r["fin"], published_on=max(r["fin"], publie), official_url=lien["url"],
        sha256=canonique({"periode": [r["debut"], r["fin"]], "transactions": ts}), parser_version=VERSION,
        tickers=tickers, entities=["Corporation commerciale canadienne"], amount_min=total_min, amount_max=total_max,
        currency="CAD", data=d,
        notes=["Date de publication : la date de mise à jour de la page officielle des rapports (au plus tard)."])


@controle_source("ccc")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    ts = d.get("transactions") or []
    return {
        "periode_lue": bool(re.fullmatch(r"\d{4}-\d\d-\d\d", d.get("debut") or "")) and d.get("fin", "") > d.get("debut", ""),
        "meme_periode_que_le_lien": d.get("fin") == d.get("fin_lien"),
        "lignes_lues": bool(ts) and all(t["exportateur"] and t["destination"] and t["description"] for t in ts),
        "fourchettes_reconnues": bool(ts) and all(t["min"] is not None and (t["max"] is None or t["max"] >= t["min"])
                                                   for t in ts),
    }


def collecter(ctx) -> list[Evenement]:
    page = ctx.client.get(PAGE).contenu.decode("utf-8", "replace")
    liste = rapports(page)
    if not liste:
        raise RuntimeError("page des rapports de la CCC : liste des transactions signées introuvable")
    courant = liste[0]
    lus = deja(ctx, "ccc", mois_max=12)
    r = lire_rapport(ctx.client.get(courant["url"]).contenu)
    if r is None:
        raise RuntimeError(f"rapport illisible : {courant['url']}")
    if f"{r['debut']}:{r['fin']}" in lus:
        return []
    publie = page_modifiee(page) or ctx.maintenant.astimezone(TORONTO).date().isoformat()
    return [evenement(r, courant, publie, symboles(ctx))]
