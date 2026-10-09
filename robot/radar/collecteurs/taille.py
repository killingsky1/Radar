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
  - pas de prix de la SEC depuis 60 jours (un titre a un prix seulement les jours où il a des échecs de livraison), ni de
    prix de formulaire 4 utilisable (étape 2, plus bas) ;
  - changement du code du titre (CUSIP) dont on ne peut pas dire le côté (voir plus bas).
- Étape 1, données sûres (0.27.1) : le prix doit être de la même époque que le nombre d'actions. Un regroupement d'actions
  (ex. 1 pour 10) donne un nouveau CUSIP et divise le nombre d'actions, mais le nombre déclaré à la SEC reste l'ancien
  jusqu'au rapport suivant : ancien nombre × nouveau prix = une valeur 10 fois trop haute (ex. EVLO : 395 M$ calculés au
  lieu d'environ 31 M$). Le robot garde l'historique des CUSIP de chaque symbole (fichiers d'échecs de livraison des 400
  derniers jours au départ, puis chaque nouveau fichier : data/prix/cusips.json) et voit, avec epoque() :
  - le CUSIP du prix était déjà vu au plus tard le jour des actions : même époque, le calcul habituel ;
  - pas de saut de prix au changement (moins de 1,8 fois, dernier prix de l'ancien et 1er du nouveau à 60 jours ou moins
    l'un de l'autre) : pas un regroupement (nom, fusion de forme…), le nombre d'actions ne change pas, le calcul habituel ;
  - l'ancien CUSIP encore vu après le jour des actions : le dernier prix de l'ancien CUSIP (s'il a 60 jours ou moins) ;
  - côté inconnu (ancien vu la dernière fois avant le jour des actions, nouveau la 1re fois après) : les deux valeurs,
    une taille seulement si elles donnent la même, et la règle des 100 M$ prend la plus grande ;
  - ancien prix trop vieux (ou ancien et nouveau vus en même temps), mais prix au moins 1,8 fois plus haut au changement
    (regroupement probable ; les deux prix à 60 jours ou moins l'un de l'autre, sinon le saut mesure aussi la bourse :
    ex. BTU, sortie de faillite) : ancien nombre × nouveau prix est un MAXIMUM ; sous le 30e centile, la compagnie est
    petite dans tous les cas (« au plus … ») ;
  - sinon (plusieurs changements, saut inconnu ou trop loin) : taille inconnue.
  Historique pas encore lu (juste après la mise en ligne : la taille est lue au passage du matin) : le calcul d'avant,
  avec une note ; des tailles inconnues remettraient les écartées (moins de 100 M$) dans la liste « hausse ».
  Mesuré au labo le 8 octobre 2026 (labo/tournoi/mesures/regroupements2.py : le vrai code du robot, avec ce qu'il aurait
  su chaque jour, sur les achats de dirigeants de 2016 à 2026, comparé à la vraie valeur connue après coup ; achats avec
  un changement de CUSIP après les actions, 2023-2026 / 2016-2023) : gardées à tort dans « hausse » sous 100 M$ 40 → 12 /
  35 → 32 ; écartées à tort 1 → 3 / 0 → 0 (des hausses après le dernier prix de la SEC) ; tailles fausses 5 → 0 / 24 → 1 ;
  bonus de petite compagnie à tort 0 → 0 / 13 → 0 ; bonus manqués (taille inconnue) 3 → 1 / 6 → 32 ; tous les autres
  achats : identiques. La règle « taille inconnue » seule aurait été pire (66 / 121 gardées à tort).
- Étape 2 (0.27.2) : pas de prix de la SEC depuis 60 jours (11,5 % des achats de dirigeants de 2023-2026, taille
  inconnue jusqu'ici) : le prix moyen des achats et ventes de dirigeants EN BOURSE du jour le plus récent (formulaire 4,
  60 jours ou moins, voir prix_formulaires_4 : actions ordinaires seulement, jamais lors d'une émission, hors bourse ou
  automatique). Taille inconnue si un CUSIP change après le plus ancien des deux jours (actions ou formulaire 4), ou si
  ce prix est plus de 10 fois loin du dernier prix de la SEC (SAUT_F4_MAX). Titre absent de l'historique : une note.
  Mesuré au labo le 9 octobre 2026 (labo/tournoi/mesures/prix_form4_robot.py : le vrai code du robot, avec ce qu'il
  aurait su chaque jour, achats de dirigeants sans prix de la SEC de 60 jours ou moins, jugés avec la vraie valeur
  connue après coup : 915 en 2023-2026, 2 492 en 2016-2023) : gardées à tort dans « hausse » sous 100 M$ 376 → 7 /
  1 188 → 83 ; bonus de petite compagnie manqués 868 → 4 / 2 282 → 36 ; écartées à tort 0 → 10 / 0 → 73 ; bonus à tort
  0 → 4 / 0 → 28 (surtout des valeurs près des seuils, ou un nombre d'actions d'avant une entrée en bourse ou une fusion).
Lu au passage du matin : les seuils (1 fichier), les actions (5 fichiers), les prix seulement quand la SEC publie un
nouveau fichier (2 fois par mois), et l'historique des CUSIP (chaque fichier une seule fois).
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
HISTOIRE_JOURS = 400  # historique des CUSIP : au départ, les fichiers des 400 derniers jours (plus que les 200 des actions)
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


def chemin_cusips(donnees) -> Path:
    return Path(donnees) / "prix" / "cusips.json"


def charger_cusips(donnees) -> dict:
    """{fichiers : [« 202609a »…], debut : AAAAMMJJ, symboles : {symbole : {CUSIP : [vu la 1re fois, vu la dernière fois,
    jour du dernier prix, dernier prix]}}} (dates de règlement), ou {} si jamais lu."""
    c = chemin_cusips(donnees)
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


def lire_lignes(contenu: bytes) -> list[tuple]:
    """Les lignes d'un fichier d'échecs de livraison : (date de règlement AAAAMMJJ, CUSIP, symbole, prix ou None).
    Prix « . » (absent ou moins d'un cent) : None."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        lignes = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    if not lignes or lignes[0].strip() != prix_sec.ENTETE:
        raise ValueError(f"en-tête inattendu : {lignes[0][:80] if lignes else 'fichier vide'}")
    sortie = []
    for l in lignes[1:]:
        p = l.split("|")
        if len(p) != 6 or not re.fullmatch(r"\d{8}", p[0]) or not p[2].strip():
            continue  # ligne finale « Trailer total quantity of shares … »
        prix = float(p[5]) if re.fullmatch(r"\d+(?:\.\d+)?", p[5].strip()) else None
        sortie.append((p[0], p[1].strip(), p[2].strip(), prix))
    return sortie


def lire_prix(contenu: bytes) -> dict[str, list]:
    """{symbole : [date de règlement AAAAMMJJ, prix, CUSIP]} : le plus récent prix de chaque symbole du fichier."""
    prix = {}
    for jour, cusip, s, p in lire_lignes(contenu):
        if p is not None and (s not in prix or jour > prix[s][0]):
            prix[s] = [jour, p, cusip]
    return prix


def ajouter_lignes(symboles: dict, lignes: list[tuple]) -> None:
    """Ajoute les lignes d'un fichier à l'historique : pour chaque symbole et chaque CUSIP, [1er jour vu, dernier jour
    vu, jour du dernier prix, dernier prix, jour du 1er prix, 1er prix] (même jour : la 1re ligne, comme lire_prix)."""
    for jour, cusip, s, prix in lignes:
        if not cusip:
            continue
        h = symboles.setdefault(s, {}).setdefault(cusip, [jour, jour, None, None, None, None])
        h[0], h[1] = min(h[0], jour), max(h[1], jour)
        if prix is not None and (h[2] is None or jour > h[2]):
            h[2], h[3] = jour, prix
        if prix is not None and (h[4] is None or jour < h[4]):
            h[4], h[5] = jour, prix


def epoque(h: dict, cusip: str, fin: str) -> dict:
    """Le nombre d'actions déclaré au `fin` (AAAAMMJJ) et le prix du `cusip` sont-ils de la même époque du titre ?
    Un regroupement d'actions (ex. 1 pour 10) donne un nouveau CUSIP et divise le nombre d'actions, mais le nombre
    déclaré à la SEC reste l'ancien jusqu'au rapport suivant. `h` : l'historique du symbole (voir charger_cusips).
    - « meme » : le CUSIP du prix était déjà vu au plus tard le jour des actions, ou aucun autre CUSIP avant lui ;
    - « ancien » : l'ancien CUSIP, vu avant et après le jour des actions, puis plus jamais après l'arrivée du nouveau :
      le changement est venu après, le prix à prendre est le dernier de l'ancien CUSIP ;
    - « deux » : l'ancien CUSIP vu la dernière fois avant le jour des actions, le nouveau la 1re fois après : les actions
      peuvent être d'un côté ou de l'autre du changement (les deux valeurs sont possibles) ;
    - « inconnue » : ancien CUSIP encore vu après l'arrivée du nouveau, ou plusieurs changements depuis le jour des
      actions."""
    if cusip not in h:
        return {"cas": "inconnue", "pourquoi": "absent"}
    premier = h[cusip][0]
    anciens = {c: v for c, v in h.items() if c != cusip and v[0] < premier}
    if not anciens or premier <= fin:
        return {"cas": "meme"}
    ancien = max(anciens, key=lambda c: (anciens[c][1], c))  # le plus récent des anciens CUSIP
    if any(v[1] >= premier for v in anciens.values()):
        return {"cas": "inconnue", "pourquoi": "chevauchement", "ancien": ancien, "premier": premier}
    if anciens[ancien][0] > fin:
        return {"cas": "inconnue", "pourquoi": "plusieurs", "ancien": ancien, "premier": premier}
    cas = "ancien" if anciens[ancien][1] >= fin else "deux"
    return {"cas": cas, "ancien": ancien, "dernier_ancien": anciens[ancien][1], "premier": premier}


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
    lus = {}

    def fichier(cle: str) -> bytes:  # chaque fichier lu une seule fois par passage
        if cle not in lus:
            lus[cle] = ctx.client.get(liens[cle]).contenu
        return lus[cle]

    derniers = sorted(liens)[-FICHIERS_PRIX:]
    if e.get("fichiers_prix") != derniers or any(len(p) < 3 for p in (e.get("prix") or {}).values()):
        prix = {}  # (prix d'avant le 8 octobre 2026 sans leur CUSIP : relus une fois)
        for cle in derniers:  # du plus vieux au plus récent : le prix le plus récent l'emporte
            for s, p in lire_prix(fichier(cle)).items():
                if s not in prix or p[0] > prix[s][0]:
                    prix[s] = p
        e["prix"], e["fichiers_prix"], e["prix_lus"] = prix, derniers, lu
    h = charger_cusips(ctx.donnees)
    h_avant = json.dumps(h, sort_keys=True)
    h.setdefault("fichiers", [])
    h.setdefault("symboles", {})
    limite = (ctx.maintenant.date() - timedelta(days=HISTOIRE_JOURS)).strftime("%Y%m%d")
    for cle in sorted(c for c in liens if prix_sec.periode(c)[1] >= limite and c not in h["fichiers"]):
        ajouter_lignes(h["symboles"], lire_lignes(fichier(cle)))
        h["fichiers"] = sorted(h["fichiers"] + [cle])
    h["debut"] = min((prix_sec.periode(c)[0] for c in h["fichiers"]), default=None)
    if json.dumps(h, sort_keys=True) != h_avant:  # écrit seulement quand la SEC publie un nouveau fichier
        c = chemin_cusips(ctx.donnees)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(h, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    if _sans_heures(e) != _sans_heures(json.loads(avant)):  # le fichier change seulement si les chiffres changent
        c = chemin(ctx.donnees)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return []


MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")


def jour_fr(j: str) -> str:
    """« 20260905 » ou « 2026-09-05 » → « 5 septembre 2026 »."""
    j = j.replace("-", "")
    a, m, d = int(j[:4]), int(j[4:6]), int(j[6:8])
    return f"{'1er' if d == 1 else d} {MOIS[m - 1]} {a}"


def millions_fr(v: float) -> str:
    """30.66 → « 30,7 M$ » ; 2236.3 → « 2,2 G$ »."""
    return f"{v / 1000:.1f} G$".replace(".", ",") if v >= 1000 else f"{v:.1f} M$".replace(".", ",")


SAUT_REGROUPEMENT = 1.8  # prix au moins 1,8 fois plus haut au changement de CUSIP : regroupement d'actions probable
NON_VERIFIE = ("Changement du code du titre (CUSIP) pas encore vérifié : l'historique des fichiers de la SEC n'est pas "
               "encore lu jusqu'à la date des actions.")
TAILLES_FR = {"petite": "petite compagnie", "moyenne": "compagnie moyenne", "grande": "grande compagnie"}


def _taille(valeur: float, s: dict) -> str:
    return "petite" if valeur < s["p30"] else "grande" if valeur >= s["p70"] else "moyenne"


def saut_au_changement(h: dict, ancien: str, nouveau: str) -> float | None:
    """1er prix du nouveau CUSIP ÷ dernier prix de l'ancien, s'ils existent et sont à 60 jours ou moins l'un de l'autre :
    au-delà, le saut mesure aussi la bourse (ex. BTU au labo : sortie de faillite, 354 jours entre les deux CUSIP et de
    nouvelles actions émises)."""
    v, n = h[ancien], h[nouveau]
    if v[2] is None or not v[3] or len(n) < 6 or n[4] is None:
        return None
    ecart = (datetime.strptime(n[4], "%Y%m%d") - datetime.strptime(v[2], "%Y%m%d")).days
    return n[5] / v[3] if 0 <= ecart <= PRIX_MAX_JOURS else None


def prix_fr(x: float) -> str:
    return f"{x:.2f} $".replace(".", ",")


def prix_de_l_epoque(h: dict, prix: list, actions: list, jour: date) -> dict:
    """Le prix à multiplier par le nombre d'actions (voir epoque) : {"prix": [jour, prix, CUSIP], "note": …} (même époque
    que les actions ; la note dit d'où vient le prix s'il n'est pas le plus récent, ou qu'on ne peut pas vérifier),
    {"deux": [prix ancien, prix nouveau], "entre": …} (les deux côtés possibles), ou {"raison": …, "saut": …} (saut :
    1er prix du nouveau CUSIP ÷ dernier prix de l'ancien, s'ils sont connus)."""
    fin = actions[1].replace("-", "")
    e = epoque(h, prix[2], fin)
    if e["cas"] == "meme":
        return {"prix": prix}
    d = jour_fr(actions[1])
    if e["cas"] == "inconnue" and e["pourquoi"] == "absent":  # impossible de vérifier : le calcul d'avant, dit tel quel
        return {"prix": prix, "note": NON_VERIFIE}
    if e["cas"] == "inconnue" and e["pourquoi"] == "plusieurs":
        return {"raison": f"plusieurs changements du code du titre (CUSIP) depuis les actions déclarées au {d}"}
    saut = saut_au_changement(h, e["ancien"], prix[2])
    if saut is not None and 1 / SAUT_REGROUPEMENT < saut < SAUT_REGROUPEMENT:
        # pas de saut de prix : pas un regroupement (nom, fusion de forme…), le nombre d'actions ne change pas (ex. DPW au
        # labo, devenue DPW Holdings le 2 janvier 2018)
        return {"prix": prix, "note": f"Nouveau code du titre (CUSIP) vu dès le {jour_fr(e['premier'])}, sans saut de "
                                      f"prix au changement ({prix_fr(h[e['ancien']][3])} puis {prix_fr(h[prix[2]][5])}) "
                                      f": pas un regroupement d'actions, leur nombre ne change pas."}
    if e["cas"] == "inconnue":  # chevauchement
        return {"raison": f"nouveau code du titre (CUSIP) vu dès le {jour_fr(e['premier'])}, après les actions "
                          f"déclarées au {d}, et l'ancien encore vu après : impossible de savoir si leur nombre est "
                          f"d'avant ou d'après un regroupement ou un fractionnement d'actions",
                "saut": saut, "premier": e["premier"]}
    vieux = h[e["ancien"]]
    if vieux[2] is None or datetime.strptime(vieux[2], "%Y%m%d").date() < jour - timedelta(days=PRIX_MAX_JOURS):
        return {"raison": f"nouveau code du titre (CUSIP) vu dès le {jour_fr(e['premier'])}, après les actions déclarées "
                          f"au {d} (regroupement ou fractionnement d'actions possible), et pas de prix de l'ancien code "
                          f"depuis {PRIX_MAX_JOURS} jours", "saut": saut, "premier": e["premier"]}
    ancien = [vieux[2], vieux[3], e["ancien"]]
    if e["cas"] == "ancien":
        return {"prix": ancien, "note": f"Prix de l'ancien code du titre (CUSIP {e['ancien']}), vu jusqu'au "
                                        f"{jour_fr(e['dernier_ancien'])} : le nouveau code, vu dès le "
                                        f"{jour_fr(e['premier'])}, est arrivé après les actions déclarées au {d} "
                                        f"(regroupement ou fractionnement d'actions possible)."}
    return {"deux": [ancien, prix], "entre": [e["dernier_ancien"], e["premier"]]}


# ---------- Étape 2 : le prix du formulaire 4 quand la SEC n'a pas de prix depuis 60 jours ----------

# Actions ordinaires seulement : « Common Stock », « Class A Common Stock », « Ordinary Shares »… ; jamais les
# privilégiées, les bons de souscription, les unités, les billets (labo, mesure 3 : ADTX « Series B Preferred Stock » à
# 20 000 $ quand l'action ordinaire valait 0,18 $)
COMMUNE = re.compile(r"common|ordinary", re.I)
PAS_COMMUNE = re.compile(r"pref|warrant|unit|right|note|debenture|option|depositary|\bADS\b|\bADR\b", re.I)
SOURCE_F4 = "formulaire 4"
# Garde-fou : prix du formulaire 4 plus de 10 fois plus haut ou plus bas que le dernier prix de la SEC du titre (même
# vieux, historique de 400 jours) : autre époque (sortie de faillite, regroupement d'actions pas encore vu dans les fichiers
# de la SEC, qui ont 2 à 6 semaines de retard) ou erreur, taille inconnue. Choisi au labo (mesure 4, 9 octobre 2026 :
# aucun, ×2, ×3, ×5, ×10 essayés ; 2 492 achats jugés de 2016-2023) : ×10 enlève 11 erreurs nouvelles (bonus de petite
# compagnie ou écartée à tort ; ex. BTU, sortie de faillite en avril 2017 : 514 M$ calculés au lieu de 2,8 G$) et 27
# tailles fausses, et laisse 16 décisions comme avant (taille inconnue) ; ×3 : 20 de moins pour 77 ; ×2 : 25 pour 223.
# En 2023-2026 (915 jugés), aucun garde-fou n'enlève d'erreur nouvelle.
SAUT_F4_MAX: float | None = 10
# Titre jamais vu dans les fichiers d'échecs de livraison depuis 400 jours : souvent une nouvelle inscription ou un
# nouveau symbole après une fusion (labo, mesure 4 : TONX, FTH, NKLA… nombre d'actions d'avant l'entrée en bourse ou la
# fusion). Mesuré : bien plus de décisions corrigées que d'erreurs ajoutées, donc la taille est calculée, avec cette note.
ABSENT_F4 = ("Titre absent des fichiers d'échecs de livraison de la SEC depuis 400 jours : un changement de code du titre "
             "(CUSIP) ne peut pas être vérifié, et le nombre d'actions est peut-être d'avant une entrée en bourse ou une "
             "fusion récente.")


def commune(titre: str | None) -> bool:
    return bool(titre) and bool(COMMUNE.search(titre)) and not PAS_COMMUNE.search(titre)


def prix_formulaires_4(evenements: list[dict], jour: date, emissions: frozenset = frozenset()) -> dict[str, list]:
    """{symbole : [AAAAMMJJ, prix]} : le prix moyen (pondéré par les actions) des achats et ventes de dirigeants en bourse
    du jour le plus récent, transactions de 60 jours ou moins avant le `jour`. `evenements` : les infos déjà lues (le
    robot : son dépôt ; un rejeu du labo : seulement les formulaires déposés au plus tard ce jour-là).

    Un formulaire compte seulement si toutes ses transactions (achats P ou ventes S) sont des actions ordinaires (le nom
    du titre est lu depuis le lecteur sec-8 : les formulaires lus avant n'en ont pas et ne comptent pas), avec un prix et
    un nombre d'actions, info « Officiel » ou « Confirmé » (prix de plus de 2 000 $ : « À vérifier »), et jamais lors
    d'une émission, hors bourse ou automatique (note du déposant, ou même action, même jour, même prix qu'un achat
    d'émission : `emissions`, voir score.achats_d_emission) : ces prix ne sont pas ceux de la bourse."""
    debut, fin = (jour - timedelta(days=PRIX_MAX_JOURS)).isoformat(), jour.isoformat()
    par_jour: dict[str, dict[str, list]] = {}
    for ev in evenements:
        d = ev.get("data") or {}
        if (ev.get("source") != "sec_form4" or ev.get("kind") not in ("achat_initie", "vente_initie")
                or not ev.get("tickers") or ev.get("badge") not in ("officiel", "confirme")
                or d.get("hors_bourse") or d.get("automatique")):
            continue
        s = ev["tickers"][0]
        code, sens = ("P", "A") if ev["kind"] == "achat_initie" else ("S", "D")
        lignes = d.get("transactions") or []
        if not lignes or not all(
                commune(t.get("titre_valeur")) and t.get("code") == code and t.get("acquis_cede") == sens
                and (t.get("actions") or 0) > 0 and (t.get("prix") or 0) > 0 and t.get("date")
                and not t.get("hors_bourse") and not t.get("automatique") and (s, t["date"], t["prix"]) not in emissions
                for t in lignes):
            continue
        for t in lignes:  # chaque transaction à son jour (un formulaire peut en couvrir plusieurs)
            if debut <= t["date"] <= fin:
                somme = par_jour.setdefault(s, {}).setdefault(t["date"], [0.0, 0.0])  # [actions, $]
                somme[0] += t["actions"]
                somme[1] += t["actions"] * t["prix"]
    sortie = {}
    for s, jours in par_jour.items():
        j, (n, montant) = max(jours.items())
        sortie[s] = [j.replace("-", ""), round(montant / n, 4)]
    return sortie


def changement_apres(h: dict, depuis: str) -> str | None:
    """Le CUSIP d'un changement de code du titre vu après le `depuis` (AAAAMMJJ) : un CUSIP vu la 1re fois après ce jour,
    alors qu'un autre CUSIP du symbole était vu avant lui. None : aucun."""
    for c, v in sorted(h.items(), key=lambda kv: kv[1][0]):
        if v[0] > depuis and any(w[0] < v[0] for k, w in h.items() if k != c):
            return c
    return None


def classer_formulaire_4(x: dict, s: dict, actions: list, f4: list, cusips: dict | None, symbole: str) -> dict:
    """La taille avec le prix du formulaire 4 `f4` ([AAAAMMJJ, prix]). Le prix n'a pas de CUSIP : s'il y a un changement
    de code du titre vu après le plus ancien des deux jours (actions ou formulaire 4), ils sont peut-être d'époques
    différentes (regroupement d'actions), taille inconnue ; de même si le prix est plus de SAUT_F4_MAX fois loin du dernier
    prix de la SEC. `cusips` : comme dans classer (None : pas de vérification ; historique pas lu : une note)."""
    fin = actions[1].replace("-", "")
    note = None
    h = ((cusips.get("symboles") or {}).get(symbole) or {}) if cusips is not None else {}
    if cusips is not None and (not cusips.get("debut") or fin < cusips["debut"]):
        note = NON_VERIFIE  # historique pas encore lu
    elif cusips is not None and not h:
        note = ABSENT_F4
    elif h:
        c = changement_apres(h, min(fin, f4[0]))
        if c:
            return {**x, "actions": actions, "raison": (
                f"pas de prix de la SEC depuis {PRIX_MAX_JOURS} jours, et le prix du formulaire 4 du {jour_fr(f4[0])} "
                f"est peut-être d'une autre époque que les actions déclarées au {jour_fr(actions[1])} : nouveau code du "
                f"titre (CUSIP) vu dès le {jour_fr(h[c][0])} (regroupement ou fractionnement d'actions possible)")}
        avec_prix = [v for v in h.values() if v[2] is not None and v[3]]
        if SAUT_F4_MAX and avec_prix:
            dernier = max(avec_prix, key=lambda v: v[2])
            q = f4[1] / dernier[3]
            if not 1 / SAUT_F4_MAX <= q <= SAUT_F4_MAX:
                fois = f"{max(q, 1 / q):.1f}".replace(".", ",")
                return {**x, "actions": actions, "raison": (
                    f"pas de prix de la SEC depuis {PRIX_MAX_JOURS} jours, et le prix du formulaire 4 ({prix_fr(f4[1])} "
                    f"le {jour_fr(f4[0])}) est {fois} fois plus {'haut' if q > 1 else 'bas'} que le dernier prix de la "
                    f"SEC ({prix_fr(dernier[3])} le {jour_fr(dernier[2])}) : erreur dans le formulaire ou regroupement "
                    f"d'actions possible")}
    valeur = actions[0] * f4[1] / 1e6
    r = {**x, "taille": _taille(valeur, s), "valeur_m": round(valeur, 1), "actions": actions, "prix": f4[:2],
         "source_prix": SOURCE_F4}
    return {**r, "note": note} if note else r


def classer(fiche: dict | None, t: dict, symbole: str, jour: date, cusips: dict | None = None,
            prix_f4: dict | None = None) -> dict:
    """La taille d'une compagnie (voir les règles en haut), avec les chiffres qui la donnent, ou la raison si inconnue.
    `cusips` (charger_cusips) : vérifie que le prix et le nombre d'actions sont de la même époque du titre ; None (anciens
    rejeux du labo) : pas de vérification. `prix_f4` (prix_formulaires_4) : le prix de secours quand la SEC n'a pas de
    prix depuis 60 jours ; None : pas de prix de secours (comme avant l'étape 2)."""
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
        f4 = (prix_f4 or {}).get(symbole)
        if f4:
            return classer_formulaire_4(x, s, actions, f4, cusips, symbole)
        ni = "" if prix_f4 is None else " ni de prix de formulaire 4 utilisable"
        return {**x, "actions": actions, "raison": f"pas de prix de la SEC{ni} depuis {PRIX_MAX_JOURS} jours"}
    note = None
    if cusips is not None and (not cusips.get("debut") or actions[1].replace("-", "") < cusips["debut"] or len(prix) < 3):
        note = NON_VERIFIE  # historique pas encore lu (juste après la mise en ligne de l'étape 1) : le calcul d'avant
    elif cusips is not None:
        p = prix_de_l_epoque((cusips.get("symboles") or {}).get(symbole) or {}, prix, actions, jour)
        if "raison" in p:
            v_max = actions[0] * prix[1] / 1e6
            if (p.get("saut") or 0) >= SAUT_REGROUPEMENT and _taille(v_max, s) == "petite":
                # regroupement probable : ancien nombre d'actions × nouveau prix = un MAXIMUM (la vraie valeur est plus
                # petite) ; sous le 30e centile, la compagnie est petite dans tous les cas (lab, 8 octobre 2026)
                saut = f"{p['saut']:.1f}".replace(".", ",")
                return {**x, "taille": "petite", "valeur_m": round(v_max, 1), "valeur_max": True, "actions": actions,
                        "prix": prix[:2], "note": (
                            f"Nouveau code du titre (CUSIP) vu dès le {jour_fr(p['premier'])}, après les actions "
                            f"déclarées au {jour_fr(actions[1])}, avec un prix {saut} fois plus haut : regroupement "
                            f"d'actions probable. Leur nombre est peut-être d'avant le regroupement : la valeur est au plus "
                            f"{millions_fr(v_max)}, petite compagnie dans tous les cas.")}
            return {**x, "actions": actions, "raison": p["raison"]}
        if "deux" in p:
            (v_bas, _), (v_haut, p_haut) = sorted((actions[0] * q[1] / 1e6, q) for q in p["deux"])
            entre = (f"code du titre (CUSIP) changé entre le {jour_fr(p['entre'][0])} et le {jour_fr(p['entre'][1])}, "
                     f"autour des actions déclarées au {jour_fr(actions[1])} (regroupement ou fractionnement d'actions "
                     f"possible) : {millions_fr(v_bas)} ou {millions_fr(v_haut)} selon le côté du changement")
            if _taille(v_bas, s) != _taille(v_haut, s):
                return {**x, "actions": actions, "raison": entre}
            r = {**x, "taille": _taille(v_haut, s), "valeur_m": round(v_haut, 1), "valeur_min_m": round(v_bas, 1),
                 "actions": actions, "prix": p_haut[:2]}
            return {**r, "note": f"{entre[0].upper()}{entre[1:]}, {TAILLES_FR[r['taille']]} dans les deux cas ; la "
                                 f"règle des 100 M$ prend la plus grande valeur."}
        prix, note = p["prix"], p.get("note")
    valeur = actions[0] * prix[1] / 1e6
    r = {**x, "taille": _taille(valeur, s), "valeur_m": round(valeur, 1), "actions": actions, "prix": prix[:2]}
    return {**r, "note": note} if note else r


def pour_score(donnees, fiches: dict, jour: date, prix_f4: dict | None = None) -> dict:
    """{symbole : taille} pour chaque compagnie dont le robot a la fiche SEC (emetteurs.json). `prix_f4` :
    prix_formulaires_4 (étape 2)."""
    t, cusips = charger(donnees), charger_cusips(donnees)
    return {s: classer(f, t, s, jour, cusips, prix_f4) for s, f in fiches.items()}
