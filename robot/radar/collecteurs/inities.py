"""Initiés « routiniers » (lot L) : ceux qui achètent ou vendent en bourse dans le même mois de l'année, chaque année.

Cohen, Malloy et Pomorski (2012, « Decoding Inside Information ») : au début de chaque année civile, un initié est
« routinier » s'il a acheté ou vendu en bourse dans le même mois de l'année chacune des 3 années précédentes (ex. en
mars 2023, en mars 2024 et en mars 2025). Les transactions des routiniers ne prédisent rien (environ 0 par mois) ; celles
des autres initiés qui ont transigé chacune des 3 années (« opportunistes ») rapportent 82 points de base par mois.
Un initié sans transaction une des 3 années n'est pas classé (l'étude ne dit rien sur lui) : rien ne change pour lui.

Données : les jeux de données officiels de la SEC sur les formulaires 3, 4 et 5, un fichier par trimestre (classé par
date de dépôt). Seules les transactions en bourse comptent (codes P = achat, S = vente), selon leur date de transaction,
comme dans l'étude.
- Classement de l'année Y avec les années Y-3, Y-2 et Y-1, fait seulement quand les 12 fichiers trimestriels de ces
  années sont publiés (mesuré le 5 octobre 2026 : le dernier fichier est celui du 2e trimestre 2026). Avant : aucun
  classement pour l'année, donc aucun changement.
- Un initié = le même numéro CIK dans la même compagnie, ou le même nom (lettres et chiffres, en majuscules) dans la même
  compagnie : la même personne peut déclarer sous 2 numéros CIK.
- Les 12 fichiers sont lus une fois par année ; le robot garde seulement les paires routinières
  (data/sec/inities_routiniers.json), pour l'année en cours et la précédente (une info de décembre compte encore en
  janvier).
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from ..models import Evenement

PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
LIEN = re.compile(r"""href=["']([^"']*?(\d{4})q([1-4])_form345\.zip)["']""", re.I)
VERSION = "inities-1"
ANNEES_D_HISTORIQUE = 3
MOIS_EN = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV",
                                       "DEC"], 1)}
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
           "décembre"]
COLONNES = {"SUBMISSION": ("ACCESSION_NUMBER", "ISSUERCIK"),
            "REPORTINGOWNER": ("ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME"),
            "NONDERIV_TRANS": ("ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE")}


def chemin(donnees) -> Path:
    return Path(donnees) / "sec" / "inities_routiniers.json"


def charger(donnees) -> dict:
    c = chemin(donnees)
    e = json.loads(c.read_text(encoding="utf-8")) if c.exists() else {}
    return e if e.get("version") == VERSION else {"version": VERSION, "annees": {}}


def fichiers_de_la_page(page: str) -> dict[str, str]:
    """{« 2025q4 » : adresse du fichier} d'après les liens de la page officielle."""
    return {f"{m.group(2)}q{m.group(3)}": urljoin(PAGE, m.group(1)) for m in LIEN.finditer(page)}


def nom_normal(nom: str) -> str:
    """« Ault Milton C. III » et « AULT MILTON C III » : le même nom."""
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", (nom or "").upper()).split())


def _jour(texte: str) -> date | None:
    """Les dates des jeux de données : « 15-MAR-2024 »."""
    m = re.fullmatch(r"(\d{2})-([A-Z]{3})-(\d{4})", (texte or "").strip().upper())
    if not m or m.group(2) not in MOIS_EN:
        return None
    try:
        return date(int(m.group(3)), MOIS_EN[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def _table(z: zipfile.ZipFile, nom: str):
    """Les lignes d'une table du fichier (en-tête vérifié) : [colonnes voulues] par ligne."""
    vrai = next((n for n in z.namelist() if n.rsplit("/", 1)[-1].upper() == f"{nom}.TSV"), None)
    if vrai is None:
        raise ValueError(f"table {nom} absente du fichier")
    lignes = z.read(vrai).decode("utf-8", "replace").split("\n")
    entete = lignes[0].rstrip("\r").split("\t")
    manque = [c for c in COLONNES[nom] if c not in entete]
    if manque:
        raise ValueError(f"colonnes absentes de {nom} : {manque}")
    idx = [entete.index(c) for c in COLONNES[nom]]
    for l in lignes[1:]:
        p = l.rstrip("\r").split("\t")
        if len(p) > max(idx):
            yield [p[i].strip() for i in idx]


def transactions(contenu: bytes, annees: set[int]):
    """(CIK de l'initié, son nom normalisé, CIK de la compagnie, année, mois) de chaque transaction en bourse (P ou S)
    du fichier trimestriel, pour les années voulues."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        emetteur = {acc: str(int(cik)) for acc, cik in _table(z, "SUBMISSION") if cik.isdigit()}
        proprios = defaultdict(list)
        for acc, cik, nom in _table(z, "REPORTINGOWNER"):
            if cik.isdigit():
                proprios[acc].append((str(int(cik)), nom_normal(nom)))
        for acc, jour, code in _table(z, "NONDERIV_TRANS"):
            if code not in ("P", "S") or acc not in emetteur:
                continue
            j = _jour(jour)
            if j is None or j.year not in annees:
                continue
            for cik, nom in proprios.get(acc, []):
                yield cik, nom, emetteur[acc], j.year, j.month


def classer(lignes, annees: list[int]) -> dict:
    """Les paires routinières : {"cik": {compagnie: {initié: mois communs}}, "noms": {compagnie: {nom: mois}}}."""
    par_cik = defaultdict(lambda: defaultdict(set))
    par_nom = defaultdict(lambda: defaultdict(set))
    for cik, nom, emetteur, annee, mois in lignes:
        par_cik[(emetteur, cik)][annee].add(mois)
        if nom:
            par_nom[(emetteur, nom)][annee].add(mois)
    sortie = {"depuis": list(annees), "cik": {}, "noms": {}, "compte": {}}
    for cle, nom_cle in ((par_cik, "cik"), (par_nom, "noms")):
        classes = defaultdict(int)
        for (emetteur, qui), h in cle.items():
            if not all(h.get(a) for a in annees):
                classes["sans historique"] += 1
                continue
            communs = sorted(set.intersection(*(h[a] for a in annees)))
            classes["routinier" if communs else "inhabituel"] += 1
            if communs:
                sortie[nom_cle].setdefault(emetteur, {})[qui] = communs
        sortie["compte"][nom_cle] = {"paires": len(cle), **dict(sorted(classes.items()))}
    return sortie


def collecter(ctx) -> list[Evenement]:
    e = charger(ctx.donnees)
    avant = json.dumps(e, sort_keys=True)
    liens = fichiers_de_la_page(ctx.client.get(PAGE).contenu.decode("utf-8", "replace"))
    if not liens:
        raise RuntimeError("aucun fichier sur la page officielle (la page a changé ?)")
    annee = ctx.maintenant.year

    def faisable(y: int) -> list[str] | None:
        besoin = [f"{a}q{q}" for a in range(y - ANNEES_D_HISTORIQUE, y) for q in (1, 2, 3, 4)]
        return besoin if all(t in liens for t in besoin) else None

    # L'année en cours ; sinon (tôt dans l'année, avant le fichier du 4e trimestre) la précédente si elle manque.
    for y in (annee, annee - 1):
        if str(y) in e["annees"]:
            break
        besoin = faisable(y)
        if besoin is None:
            continue
        annees = list(range(y - ANNEES_D_HISTORIQUE, y))
        lignes = []
        for t in besoin:
            lignes.extend(transactions(ctx.client.get(liens[t]).contenu, set(annees)))
        if not lignes:
            raise RuntimeError(f"aucune transaction en bourse dans les fichiers de {annees[0]} à {annees[-1]}")
        e["annees"][str(y)] = {**classer(lignes, annees), "fichiers": [liens[t] for t in besoin],
                               "lu": ctx.maintenant.isoformat(), "transactions": len(lignes)}
        break
    e["annees"] = {y: c for y, c in e["annees"].items() if int(y) >= annee - 1}
    if json.dumps(e, sort_keys=True) != avant:
        c = chemin(ctx.donnees)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return []


def routinier(classement: dict | None, ev: dict) -> dict | None:
    """Si un déclarant de ce formulaire 4 est routinier dans cette compagnie (classement de l'année de la transaction) :
    {"mois": [...], "annees": [...]} ; sinon None (pas routinier, ou pas de classement pour cette année)."""
    d = ev.get("data") or {}
    c = ((classement or {}).get("annees") or {}).get((ev.get("occurred_on") or "")[:4])
    cik = str(d.get("cik_emetteur") or "").strip()
    if not c or not cik.isdigit():
        return None
    emetteur = str(int(cik))
    for o in d.get("proprietaires_cik") or []:
        if str(o).strip().isdigit() and (mois := c["cik"].get(emetteur, {}).get(str(int(o)))):
            return {"mois": mois, "annees": c["depuis"]}
    for nom in (ev.get("entities") or [])[:-1]:
        if mois := c["noms"].get(emetteur, {}).get(nom_normal(nom)):
            return {"mois": mois, "annees": c["depuis"]}
    return None


def en_mots(r: dict) -> str:
    """« mars et mai (2023, 2024 et 2025) » ; « chaque mois (2023, 2024 et 2025) »."""
    mois = [MOIS_FR[m - 1] for m in r["mois"]]
    texte = "chaque mois" if len(mois) == 12 else mois[0] if len(mois) == 1 else ", ".join(mois[:-1]) + " et " + mois[-1]
    annees = [str(a) for a in r["annees"]]
    return f"{texte} ({', '.join(annees[:-1])} et {annees[-1]})"
