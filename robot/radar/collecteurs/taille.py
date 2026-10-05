"""Taille des compagnies en bourse (lot L) : petite, moyenne ou grande, selon les seuils du NYSE.

Lakonishok et Lee (2001, tableau 8) : le signal d'achat des dirigeants rapporte 7,27 % par année dans les petites
compagnies, contre 4,82 % pour l'ensemble (1,5 fois plus), 3,34 % dans les moyennes et 1,32 % dans les grandes (pas
significatif). Cohen, Malloy et Pomorski (2012, tableau IX) : 0,80 % par mois dans la moitié la plus petite, contre
0,55 % dans la plus grande (1,45 fois plus). Petite = sous le 30e centile des compagnies du NYSE ; grande = au 70e
centile et plus ; moyenne entre les deux (les 3, 4 et 3 déciles de Lakonishok et Lee).

- Seuils : les centiles de valeur en bourse des compagnies du NYSE que Kenneth French publie chaque mois (fichier
  ME_Breakpoints_CSV.zip, données CRSP, en millions de dollars) : le dernier mois du fichier.
- Valeur en bourse = actions en circulation déclarées à la SEC sur la page couverture des rapports
  (dei:EntityCommonStockSharesOutstanding) × dernier prix de clôture de la SEC (les 2 derniers fichiers d'échecs de
  livraison, voir prix_sec.py). Les actions : le fait le plus récent de 2 API de la SEC, qui ne concordent pas toujours
  (recherche 29, 5 octobre 2026) :
  - les fichiers « frames » des 5 derniers trimestres (toutes les compagnies, mais un seul fait par trimestre : un
    10-Q peut y manquer ; ex. XAIR : 14 410 621 actions au 23 juin, alors qu'elle en déclare 957 631 au 12 août après un
    regroupement d'actions, soit une valeur 15 fois trop haute avec le prix de septembre) ;
  - le dossier « companyconcept » de chaque compagnie qui compte : un achat de dirigeant depuis 90 jours (numéro CIK du
    formulaire 4) ou une place dans les listes publiées (ex. ASPI : 153 309 380 au 14 août, absent des frames ; FLNA :
    le 10-Q de juillet est dans les frames, pas dans companyconcept).
- Taille inconnue, donc aucun bonus :
  - compagnie qui ne dépose pas de rapports américains (10-K, 10-Q) ou qui dépose ceux d'un émetteur étranger (20-F,
    40-F, 6-K) : ses titres cotés aux États-Unis sont souvent des certificats (ADS) qui valent plusieurs actions, la
    valeur serait fausse (mesuré le 5 octobre 2026 : Pampa Energía, 1,36 milliard d'actions × 88,45 $ par certificat
    = 120 G$, alors qu'un certificat vaut 25 actions) ;
  - actions déclarées il y a plus de 200 jours (une compagnie américaine les déclare à chaque rapport trimestriel) ;
  - moins de 500 000 actions déclarées : impossible pour une action cotée (le Nasdaq exige au moins 500 000 actions dans
    le public pour garder une compagnie inscrite) ; mesuré le 5 octobre 2026 : QVCG, 1 action déclarée au 30 juin 2026 ;
  - pas de prix de la SEC depuis 60 jours (un titre a un prix seulement les jours où il a des échecs de livraison).
Lu au passage du matin : les seuils (1 fichier), les actions (5 fichiers), et les prix seulement quand la SEC publie un
nouveau fichier (2 fois par mois).
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from ..http import ErreurSource
from ..models import Evenement
from . import prix_sec

SEUILS = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/ME_Breakpoints_CSV.zip"
FRAMES = "https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{}.json"
CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{:010d}/dei/EntityCommonStockSharesOutstanding.json"
JOURS_ACHATS = 90  # comme l'âge maximal d'une info dans le score
TRIMESTRES = 5
FICHIERS_PRIX = 2
ACTIONS_MAX_JOURS = 200
ACTIONS_MIN = 500_000
PRIX_MAX_JOURS = 60
AMERICAINS = {"10-K", "10-Q", "10-KT", "10-QT"}
ETRANGERS = {"20-F", "40-F", "6-K"}


def chemin(donnees) -> Path:
    return Path(donnees) / "prix" / "taille.json"


def charger(donnees) -> dict:
    c = chemin(donnees)
    return json.loads(c.read_text(encoding="utf-8")) if c.exists() else {}


def lire_seuils(contenu: bytes) -> dict:
    """Le dernier mois du fichier de Kenneth French : {mois, compagnies du NYSE, 30e et 70e centiles en M$}."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        texte = z.read(z.namelist()[0]).decode("latin-1")
    mois = [[x.strip() for x in l.split(",")] for l in texte.splitlines() if re.match(r"\s*\d{6}\s*,", l)]
    if not mois or len(mois[-1]) != 22:
        raise ValueError("format inattendu (on attend : mois, nombre de compagnies, 20 centiles)")
    m = mois[-1]
    centiles = [float(x) for x in m[2:]]
    if centiles != sorted(centiles):
        raise ValueError(f"centiles pas en ordre pour {m[0]}")
    return {"mois": m[0], "compagnies_nyse": int(m[1]), "p30": centiles[5], "p70": centiles[13]}


def periodes(jour: date) -> list[str]:
    """Les 5 derniers trimestres, celui en cours compris : CY2026Q4I, CY2026Q3I…"""
    a, q, sortie = jour.year, (jour.month - 1) // 3 + 1, []
    for _ in range(TRIMESTRES):
        sortie.append(f"CY{a}Q{q}I")
        a, q = (a, q - 1) if q > 1 else (a - 1, 4)
    return sortie


def lire_prix(contenu: bytes) -> dict[str, list]:
    """{symbole : [date de règlement AAAAMMJJ, prix]} : le plus récent prix de chaque symbole du fichier."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        lignes = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    if not lignes or lignes[0].strip() != prix_sec.ENTETE:
        raise ValueError(f"en-tête inattendu : {lignes[0][:80] if lignes else 'fichier vide'}")
    prix = {}
    for l in lignes[1:]:
        p = l.split("|")
        if len(p) != 6 or not re.fullmatch(r"\d{8}", p[0]) or not re.fullmatch(r"\d+(?:\.\d+)?", p[5].strip()):
            continue
        s = p[2].strip()
        if s and (s not in prix or p[0] > prix[s][0]):
            prix[s] = [p[0], float(p[5])]
    return prix


def ciks_a_relire(donnees, jour: date) -> list[int]:
    """Les compagnies dont la taille compte : un achat de dirigeant publié depuis 90 jours (CIK écrit dans le formulaire
    4), et celles des listes publiées (leur fiche montre la taille)."""
    from ..emetteurs import charger as fiches_sec  # import ici : emetteurs n'est pas un collecteur
    from ..store import Depot

    depuis = (jour - timedelta(days=JOURS_ACHATS)).isoformat()
    ciks = {int(str(e["data"]["cik_emetteur"]).strip()) for e in Depot(donnees).lire("evenements", mois_max=4)
            if e.get("source") == "sec_form4" and e.get("kind") == "achat_initie" and e.get("published_on", "") >= depuis
            and str((e.get("data") or {}).get("cik_emetteur") or "").strip().isdigit()}
    chemin_listes = Path(donnees) / "app" / "aujourdhui.json"
    if chemin_listes.exists():
        listes = json.loads(chemin_listes.read_text(encoding="utf-8"))
        fiches = fiches_sec(donnees)
        ciks |= {fiches[x["symbole"]]["cik"] for n in ("hausse", "baisse") for x in listes.get(n, [])
                 if (fiches.get(x["symbole"]) or {}).get("cik")}
    return sorted(ciks)


def fait_recent(faits: list) -> list | None:
    """[actions, date] du fait le plus récent (date de la page couverture, puis date de dépôt), ou None."""
    bons = [f for f in faits if isinstance(f.get("val"), (int, float)) and f["val"] > 0 and f.get("end")]
    f = max(bons, key=lambda f: (f["end"], f.get("filed") or ""), default=None)
    return [f["val"], f["end"]] if f else None


def _sans_heures(e: dict) -> str:
    """Le contenu sans les heures de lecture (pour ne pas réécrire le fichier quand rien n'a changé)."""
    return json.dumps({k: ({c: w for c, w in v.items() if c != "lu"} if k == "seuils" else v) for k, v in e.items()
                       if k not in ("actions_lues", "prix_lus")}, sort_keys=True)


def collecter(ctx) -> list[Evenement]:
    e = charger(ctx.donnees)
    avant = json.dumps(e, sort_keys=True)
    lu = ctx.maintenant.isoformat()
    e["seuils"] = {**lire_seuils(ctx.client.get(SEUILS).contenu), "adresse": SEUILS, "lu": lu}
    actions, frames = {}, {}
    for per in periodes(ctx.maintenant.date()):
        try:
            f = json.loads(ctx.client.get(FRAMES.format(per)).contenu)
        except ErreurSource as exc:
            if not str(exc).endswith("HTTP 404"):  # le trimestre en cours n'existe pas encore au début : normal
                raise
            frames[per] = {"statut": 404}
            continue
        for r in f.get("data") or []:
            cik, fin = str(r.get("cik")), r.get("end")
            if isinstance(r.get("val"), (int, float)) and r["val"] > 0 and fin and (cik not in actions or
                                                                                  fin > actions[cik][1]):
                actions[cik] = [r["val"], fin]
        frames[per] = {"statut": 200, "compagnies": len(f.get("data") or [])}
    if not actions:
        raise RuntimeError("aucune action en circulation dans les fichiers frames de la SEC")
    e["actions"], e["frames"], e["actions_lues"] = actions, frames, lu
    concept = {}
    for cik in ciks_a_relire(ctx.donnees, ctx.maintenant.date()):
        try:
            d = json.loads(ctx.client.get(CONCEPT.format(cik)).contenu)
        except ErreurSource as exc:
            if not str(exc).endswith("HTTP 404"):  # pas de dossier pour cette compagnie (ex. fonds) : normal
                raise
            continue
        if fait := fait_recent((d.get("units") or {}).get("shares") or []):
            concept[str(cik)] = fait
    e["actions_concept"] = concept
    liens = prix_sec.fichiers_de_la_page(ctx.client.get(prix_sec.PAGE).contenu.decode("utf-8", "replace"))
    if not liens:
        raise RuntimeError("aucun fichier d'échecs de livraison sur la page officielle (la page a changé ?)")
    derniers = sorted(liens)[-FICHIERS_PRIX:]
    if e.get("fichiers_prix") != derniers:
        prix = {}
        for cle in derniers:  # du plus vieux au plus récent : le prix le plus récent l'emporte
            for s, p in lire_prix(ctx.client.get(liens[cle]).contenu).items():
                if s not in prix or p[0] > prix[s][0]:
                    prix[s] = p
        e["prix"], e["fichiers_prix"], e["prix_lus"] = prix, derniers, lu
    if _sans_heures(e) != _sans_heures(json.loads(avant)):  # le fichier change seulement si les chiffres changent
        c = chemin(ctx.donnees)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return []


def classer(fiche: dict | None, t: dict, symbole: str, jour: date) -> dict:
    """La taille d'une compagnie (voir les règles en haut), avec les chiffres qui la donnent, ou la raison si inconnue."""
    s = t.get("seuils")
    x = {"taille": None, "seuils": {k: s[k] for k in ("mois", "p30", "p70")} if s else None}
    rapports = set((fiche or {}).get("rapports") or [])
    cik = (fiche or {}).get("cik")
    if not s:
        return {**x, "raison": "seuils du NYSE pas encore lus"}
    if fiche is None or cik is None or "rapports" not in fiche:
        return {**x, "raison": "fiche de la SEC pas encore lue"}
    if rapports & ETRANGERS or not rapports & AMERICAINS:
        return {**x, "raison": "compagnie étrangère ou sans rapports américains (10-K, 10-Q) : ses titres cotés aux "
                               "États-Unis peuvent valoir plusieurs actions"}
    sources = [(a, n) for a, n in (((t.get("actions") or {}).get(str(cik)), "frames"),
                                    ((t.get("actions_concept") or {}).get(str(cik)), "companyconcept")) if a]
    actions, source = max(sources, key=lambda x: x[0][1], default=(None, None))  # même date : les frames d'abord
    x["source_actions"] = source
    if not actions or date.fromisoformat(actions[1]) < jour - timedelta(days=ACTIONS_MAX_JOURS):
        return {**x, "raison": f"pas d'actions en circulation déclarées depuis {ACTIONS_MAX_JOURS} jours"}
    if actions[0] < ACTIONS_MIN:
        n = f"{actions[0]:,.0f}".replace(",", " ")
        return {**x, "actions": actions, "raison": f"{n} {'action déclarée' if actions[0] < 2 else 'actions déclarées'} à la "
                                                   f"SEC : impossible pour une action cotée (au moins 500 000 dans le public)"}
    prix = (t.get("prix") or {}).get(symbole)
    if not prix or datetime.strptime(prix[0], "%Y%m%d").date() < jour - timedelta(days=PRIX_MAX_JOURS):
        return {**x, "actions": actions, "raison": f"pas de prix de la SEC depuis {PRIX_MAX_JOURS} jours"}
    valeur = actions[0] * prix[1] / 1e6
    taille = "petite" if valeur < s["p30"] else "grande" if valeur >= s["p70"] else "moyenne"
    return {**x, "taille": taille, "valeur_m": round(valeur, 1), "actions": actions, "prix": prix}


def pour_score(donnees, fiches: dict, jour: date) -> dict:
    """{symbole : taille} pour chaque compagnie dont le robot a la fiche SEC (emetteurs.json)."""
    t = charger(donnees)
    return {s: classer(f, t, s, jour) for s, f in fiches.items()}
