"""Rapports de transactions (278-T) du président, du vice-président et des postes de niveaux I et II (OGE).

Source : l'adresse de données publique qu'appelle la page officielle « Officials' Individual Disclosures Search
Collection » de l'OGE (extapps2.oge.gov ; robots.txt absent : tout est permis). Lue une fois par jour de semaine.
Seuls les rapports avec un lien direct vers le PDF sont gardés : l'OGE les publie sans formulaire 201 (président,
vice-président, postes payés aux niveaux I et II de l'Executive Schedule). Les autres (« Request this Document »)
exigent un formulaire 201 : le robot ne les lit jamais.
Rapports du cabinet (PDF texte d'Integrity.gov) : chaque ligne est lue par la position de ses colonnes (#, description,
type, date, avis tardif, montant), avec les notes de fin du déclarant. Une ligne n'est reliée à une compagnie que si le
déclarant a écrit un symbole d'action cotée à la SEC ; le nom officiel doit concorder (sinon : « À vérifier »). Les fonds,
obligations et placements privés restent dans le détail du rapport. Une info par compagnie et par sens dans chaque rapport.
Rapports du président : images numérisées, jamais lues (trop de risque d'erreur) : liste seulement.
Score : 0 point (aucune étude ne mesure d'effet pour ces postes ; une vente peut être imposée par l'entente d'éthique).
Loi (5 U.S.C. § 13107(c)) : interdit d'obtenir ou d'utiliser ces rapports à des fins commerciales (sauf les médias),
pour établir une cote de crédit ou pour solliciter de l'argent. Radar : usage personnel seulement.
"""

from __future__ import annotations

import html
import io
import json
import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from ..http import ErreurSource
from ..models import Evenement
from ..validate import controle_source
from .elus import iso_us, nom_coherent, plage
from .regulateurs import deja

VERSION = "oge-2"  # oge-2 : lit les lignes des rapports du cabinet
API = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest"
COLONNES = ("docDate", "title", "type", "name", "agency", "level")
# Les 2 recherches de la page officielle : les 278-T des niveaux I et II, et ceux dont le poste contient « President »
FILTRES = ({2: "Transaction", 5: "Level"}, {2: "Transaction", 1: "President"})
LIEN = re.compile(r"href='(https://extapps2\.oge\.gov/201/Presiden\.nsf/PAS\+Index/([0-9A-F]{32})/\$FILE/[^']+\.pdf)'"
                  r">278 Transaction</a>", re.I)
POSTES_SANS_201 = {"President": "président des États-Unis", "Vice President": "vice-président des États-Unis"}
NIVEAUX_SANS_201 = {"Level I": "niveau I", "Level II": "niveau II"}
JOURS = 90  # comme le fil : les rapports ajoutés depuis 3 mois
COLONNES_PDF = ("#", "DESCRIPTION", "TYPE", "DATE", "NOTIFICATION", "AMOUNT")
CHAMPS = ("n", "description", "type", "date", "avis", "montant")
SOUS_TITRES = {"RECEIVED OVER", "30 DAYS AGO", "RECEIVED OVER 30 DAYS AGO"}  # sous « NOTIFICATION »
PIED = re.compile(r" - Page \d+$")  # « Mullin, Markwayne - Page 2 » (en-tête et pied de page)
TYPES_278T = {"Purchase": ("P", 1, "achète", "achat"), "Sale": ("S", -1, "vend", "vente"),
              "Exchange": ("E", 0, "échange", "echange")}
SYMBOLE_ECRIT = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*$")


def adresse(filtres: dict[int, str], longueur: int = 100) -> str:
    """Les mêmes paramètres que le tableau de la page officielle (le plus récent d'abord)."""
    p = "draw=1&order%5B0%5D%5Bcolumn%5D=0&order%5B0%5D%5Bdir%5D=desc"
    for i, c in enumerate(COLONNES):
        p += f"&columns%5B{i}%5D%5Bdata%5D={c}&columns%5B{i}%5D%5Bsearchable%5D=true&columns%5B{i}%5D%5Borderable%5D=true"
    p += "&search%5Bvalue%5D="
    for i, valeur in filtres.items():
        p += f"&columns%5B{i}%5D%5Bsearch%5D%5Bvalue%5D={quote(valeur)}"
    return f"{API}?{p}&start=0&length={longueur}"


def nom_affiche(nom: str) -> str:
    """« Kupor, Scott A » → « Scott A Kupor »."""
    famille, _, prenoms = (nom or "").partition(",")
    return " ".join(f"{prenoms.strip()} {famille.strip()}".split())


def lire_ligne(r: dict) -> dict | None:
    """Une ligne du tableau officiel, ou None si le rapport exige un formulaire 201 (jamais lu)."""
    m = LIEN.search(r.get("type") or "")
    titre, niveau = " ".join((r.get("title") or "").split()), " ".join((r.get("level") or "").split())
    if not m or (titre not in POSTES_SANS_201 and niveau not in NIVEAUX_SANS_201):
        return None
    return {"pdf": html.unescape(m.group(1)), "unid": m.group(2).upper(), "nom": " ".join((r.get("name") or "").split()),
            "titre": titre, "agence": " ".join((r.get("agency") or "").split()), "niveau": niveau,
            "ajoute_le": (r.get("docDate") or "")[:10], "modifie_le": (r.get("amended") or "")[:10] or None}


def poste_fr(x: dict) -> str:
    if x["titre"] in POSTES_SANS_201:
        return POSTES_SANS_201[x["titre"]]
    return f"{x['titre']}, {x['agence']}, {NIVEAUX_SANS_201[x['niveau']]}"


# ---------- Lecture d'un rapport du cabinet (PDF texte) ----------

def _lignes(doc) -> list[dict] | None:
    """Les lignes du tableau « Transactions », colonne par colonne ; None si aucun tableau (ex. image numérisée)."""
    res, cur, tableau = [], None, False
    for page in doc.pages:
        mots = page.extract_words(x_tolerance=1.5, y_tolerance=2)
        entete: dict = {}
        for w in mots:
            if w["text"] in COLONNES_PDF and w["text"] not in entete:
                entete[w["text"]] = w
        if not all(c in entete for c in COLONNES_PDF):
            continue  # page sans le tableau (signatures, notes de fin)
        tableau = True
        bas_entete = max(entete[c]["bottom"] for c in COLONNES_PDF)
        bornes = [entete[c]["x0"] - 2 for c in COLONNES_PDF]
        par_ligne: dict = {}
        for w in mots:
            if w["top"] > bas_entete:
                par_ligne.setdefault(round(w["top"] / 3), []).append(w)
        fin = False
        for cle in sorted(par_ligne):
            ws = sorted(par_ligne[cle], key=lambda w: w["x0"])
            texte = " ".join(w["text"] for w in ws)
            if PIED.search(texte) or texte in SOUS_TITRES:
                continue
            if ws[0]["x0"] < bornes[1] and ws[0]["text"] in ("Endnotes", "Summary", "PART"):
                fin = True
                break
            cellules = [""] * len(CHAMPS)
            for w in ws:
                i = max((k for k, b in enumerate(bornes) if w["x0"] >= b), default=0)
                cellules[i] = f"{cellules[i]} {w['text']}".strip()
            if re.fullmatch(r"\d+", cellules[0]):
                if cur:
                    res.append(cur)
                cur = dict(zip(CHAMPS, cellules))
            elif cur:  # suite d'une cellule sur 2 lignes (description ou montant)
                for k, c in zip(CHAMPS[1:], cellules[1:]):
                    if c:
                        cur[k] = f"{cur[k]} {c}".strip()
        if fin:
            break
    if cur:
        res.append(cur)
    return res if tableau else None


def _notes_de_fin(texte: str) -> dict[str, str]:
    """« Transactions 42 Sold stock that resulted from exercising vested stock options. » → {"42": "Sold stock…"}."""
    i = texte.find("\nEndnotes")
    if i < 0:
        return {}
    j = texte.find("Summary of Contents", i)
    # Sans les en-têtes et pieds de page (« PART # ENDNOTE » se répète en haut de chaque page de notes)
    bloc = "\n".join(l for l in texte[i:j if j > 0 else None].splitlines()
                     if not PIED.search(l.strip()) and l.strip() != "PART # ENDNOTE")
    return {m.group(1): " ".join(m.group(2).split())
            for m in re.finditer(r"^Transactions (\d+) (.+?)(?=^Transactions \d+ |\Z)", bloc, re.M | re.S)}


def lire_rapport(pdf: bytes) -> dict | None:
    """Le contenu d'un rapport 278-T en texte ; None s'il est illisible ou numérisé (aucun tableau trouvé)."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texte = "\n".join(p.extract_text() or "" for p in doc.pages)
            lignes = _lignes(doc)
    except Exception:  # noqa: BLE001 - PDF illisible : rien plutôt que faux
        return None
    if lignes is None or "Periodic Transaction Report" not in texte:
        return None
    notes = _notes_de_fin(texte)
    for l in lignes:
        l["description"] = " ".join(re.sub(r"\bSee Endnote\b", " ", l["description"]).split())
        l["date"] = iso_us(l["date"]) or l["date"]
        l["note"] = notes.get(l["n"])
    qui = re.search(r"Filer's Information\n(.+)\n(.+)", texte)
    signe = re.search(r"electronically signed on (\d{2}/\d{2}/\d{4}) by", texte)
    return {"declarant": qui.group(1).strip() if qui else None, "poste_declare": qui.group(2).strip() if qui else None,
            "signe_le": iso_us(signe.group(1)) if signe else None, "lignes": lignes,
            "prolongation": "filing extension" in texte,
            "lecture_complete": [l["n"] for l in lignes] == [str(i) for i in range(1, len(lignes) + 1)]}


def meme_declarant(rapport: dict, x: dict) -> bool:
    """Le nom de famille écrit dans le PDF = celui de l'index officiel (attrape un mauvais fichier)."""
    a = (rapport.get("declarant") or "").split(",")[0].strip().upper()
    return bool(a) and a == x["nom"].split(",")[0].strip().upper()


# ---------- Infos ----------

def evenement(x: dict, sha256: str, rapport: dict | None = None, reliees: int = 0) -> Evenement:
    """Le rapport lui-même (liste) ; avec ses lignes si c'est un rapport du cabinet en texte."""
    nom = nom_affiche(x["nom"])
    data = {k: x[k] for k in ("nom", "titre", "agence", "niveau", "ajoute_le", "modifie_le", "pdf_valide", "taille")}
    if rapport is None:
        quoi = "image numérisée" if x["pdf_valide"] else "document illisible"
        notes = [f"{quoi.capitalize()} : le robot ne lit pas ses transactions (trop de risque d'erreur). Ouvrez le "
                 "document officiel pour les voir."]
    else:
        n = len(rapport["lignes"])
        quoi = f"{n} transaction{'s' if n > 1 else ''}"
        autres = "des fonds, des obligations, des placements privés ou un symbole introuvable à la SEC"
        if reliees == n:
            resume = f"{'toutes reliées' if n > 1 else 'reliée'} à une action cotée à la SEC."
        elif reliees == 0:
            resume = f"aucune action cotée à la SEC ({autres} : voir les lignes)."
        else:
            resume = f"{reliees} reliée{'s' if reliees > 1 else ''} à une action cotée à la SEC ; les autres sont {autres}."
        notes = [f"{n} ligne{'s' if n > 1 else ''} lue{'s' if n > 1 else ''} : {resume}"]
        data.update({"transactions": rapport["lignes"], "lecture_complete": rapport["lecture_complete"],
                     "signe_le": rapport["signe_le"], "declarant_concorde": meme_declarant(rapport, x)})
        if rapport["prolongation"]:
            notes.append("Rapport déposé avec une prolongation de 45 jours (selon le document).")
    if x["modifie_le"]:
        notes.append(f"Rapport modifié (amended) le {x['modifie_le']}, selon l'OGE.")
    return Evenement(
        source="oge_278t", official_id=x["unid"], category="politiciens", kind="rapport_278t",
        title=f"{nom} ({poste_fr(x)}) : rapport de transactions (278-T), {quoi}",
        occurred_on=x["ajoute_le"], published_on=x["ajoute_le"], official_url=x["pdf"], sha256=sha256,
        parser_version=VERSION, entities=[nom, x["agence"]], notes=notes, data=data,
    )


def evenements_compagnies(x: dict, sha256: str, rapport: dict, syms) -> list[Evenement]:
    """Une info par compagnie cotée et par sens : les lignes dont le symbole écrit est une action cotée à la SEC."""
    groupes: dict = {}
    for l in rapport["lignes"]:
        m = SYMBOLE_ECRIT.search(l["description"])
        cote = syms.par_symbole(m.group(1)) if m else None
        l["symbole"] = cote["ticker"] if cote else None
        if cote and l["type"] in TYPES_278T:
            groupes.setdefault((cote["ticker"], l["type"]), (cote, []))[1].append(l)
    evs, nom = [], nom_affiche(x["nom"])
    for (symbole, sorte), (cote, ls) in sorted(groupes.items()):
        code, sens, verbe, mot = TYPES_278T[sorte]
        plages = [plage(l["montant"]) for l in ls]
        bas = sum(p[0] for p in plages) if all(plages) else None
        haut = None if not all(plages) or any(p[1] is None for p in plages) else sum(p[1] for p in plages)
        notes = []
        if any(l["avis"] == "Yes" for l in ls):
            notes.append("Le déclarant a reçu l'avis de cette transaction plus de 30 jours après qu'elle a eu lieu.")
        notes += [f"Note du déclarant (ligne {l['n']}) : « {l['note']} »" for l in ls if l.get("note")]
        dates = sorted(l["date"] for l in ls if re.fullmatch(r"\d{4}-\d\d-\d\d", l["date"] or ""))
        evs.append(Evenement(
            source="oge_278t", official_id=f"{x['unid']}:{symbole}:{code}", category="politiciens",
            kind=f"{mot}_cabinet",
            title=f"{nom} ({poste_fr(x)}) {verbe} {symbole}" + (f" ({len(ls)} transactions)" if len(ls) > 1 else ""),
            occurred_on=dates[0] if dates else x["ajoute_le"], published_on=x["ajoute_le"], official_url=x["pdf"],
            sha256=sha256, parser_version=VERSION, tickers=[symbole], entities=[nom, cote["name"]],
            amount_min=float(bas) if bas is not None else None, amount_max=float(haut) if haut is not None else None,
            direction=sens, notes=notes,
            data={**{k: x[k] for k in ("nom", "titre", "agence", "niveau", "ajoute_le", "pdf_valide", "taille")},
                  "rapport": x["unid"], "nom_sec": cote["name"], "transactions": ls,
                  "lecture_complete": rapport["lecture_complete"], "signe_le": rapport["signe_le"],
                  "declarant_concorde": meme_declarant(rapport, x)},
        ))
    return evs


def chemin_lus(donnees) -> Path:
    return Path(donnees) / "oge" / "lus.json"


def collecter(ctx) -> list[Evenement]:
    from .sec import symboles

    connus = deja(ctx, "oge_278t", mois_max=24)  # un rapport déjà lu ne se relit pas, même après 3 mois
    p = chemin_lus(ctx.donnees)
    lus = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    limite = (ctx.maintenant.date() - timedelta(days=JOURS)).isoformat()
    lignes: dict[str, dict] = {}
    for filtres in FILTRES:
        d = json.loads(ctx.client.get(adresse(filtres)).contenu)
        if not isinstance(d.get("data"), list) or "recordsFiltered" not in d:
            raise ErreurSource("réponse inattendue de l'OGE (pas de tableau « data »)")
        for r in d["data"]:
            x = lire_ligne(r)
            # À lire : un rapport nouveau, ou lu par une version plus ancienne du lecteur (une seule fois)
            if x and x["ajoute_le"] >= limite and (x["unid"] not in connus
                                                   or lus.get(x["unid"], {}).get("version") != VERSION):
                lignes[x["unid"]] = x
    if not lignes:
        return []
    try:
        syms = symboles(ctx)  # liste officielle de la SEC : sans elle, aucun symbole n'est relié
    except Exception as exc:
        raise RuntimeError(f"liste officielle des symboles (SEC) indisponible : {exc}") from exc
    evs = []
    for x in sorted(lignes.values(), key=lambda x: (x["ajoute_le"], x["unid"])):
        try:
            t = ctx.client.get(x["pdf"])  # sans formulaire 201 : permis
        except ErreurSource:
            continue  # document pas lisible maintenant : rien de publié, nouvel essai au prochain passage
        x["pdf_valide"], x["taille"] = t.contenu[:5] == b"%PDF-", len(t.contenu)
        # Les rapports du président sont des images numérisées : jamais lus (trop de risque d'erreur)
        rapport = lire_rapport(t.contenu) if x["pdf_valide"] and x["titre"] != "President" else None
        compagnies = evenements_compagnies(x, t.sha256, rapport, syms) if rapport else []
        evs.append(evenement(x, t.sha256, rapport, reliees=sum(len(e.data["transactions"]) for e in compagnies)))
        evs += compagnies
        lus[x["unid"]] = {"version": VERSION, "lu": ctx.maintenant.isoformat(),
                          "lignes": len(rapport["lignes"]) if rapport else None}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(lus, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return evs


@controle_source("oge_278t")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    c = {
        "sans_formulaire_201": bool(re.fullmatch(r"https://extapps2\.oge\.gov/201/Presiden\.nsf/PAS\+Index/[0-9A-Fa-f]{32}"
                                                 r"/\$FILE/[^']+\.pdf", ev.official_url or "")),
        "poste_publie_sans_201": d.get("titre") in POSTES_SANS_201 or d.get("niveau") in NIVEAUX_SANS_201,
        "document_pdf": d.get("pdf_valide") is True,
    }
    if "transactions" in d:  # rapport du cabinet lu, ou info d'une compagnie
        ts = d["transactions"]
        c["lecture_complete"] = d.get("lecture_complete") is True
        c["declarant_concorde"] = d.get("declarant_concorde") is True
        c["montants_officiels"] = bool(ts) and all(plage(t["montant"]) for t in ts)
        c["dates_transactions_valides"] = bool(ts) and all(
            re.fullmatch(r"\d{4}-\d\d-\d\d", t["date"] or "") and t["date"] <= (d.get("signe_le") or ev.published_on)
            for t in ts)
        c["type_reconnu"] = bool(ts) and all(t["type"] in TYPES_278T for t in ts)
    if ev.kind != "rapport_278t":  # une compagnie : symbole coté et nom qui concorde
        c["symbole_cote_sec"] = bool(d.get("nom_sec"))
        c["nom_coherent_avec_symbole"] = all(nom_coherent(t["description"], d.get("nom_sec")) for t in d["transactions"])
    return c
