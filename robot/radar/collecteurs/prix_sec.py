"""Prix de clôture officiels de la SEC, tirés des fichiers d'échecs de livraison (lot G), SEULEMENT pour mesurer les
résultats de Radar : jamais un signal, jamais une suggestion (voir resultats.py).

La SEC, sur sa page officielle (lue le 4 octobre 2026) :
- « The price field includes the closing price of the security on the previous day as long as the price is available
  and is greater than one penny » : pour une date de règlement, la clôture de la veille ;
- « Even when prices are included in the data, we cannot guarantee that this price matches closing prices available
  from other sources » ;
- « The first half of a given month is available at the end of the month. The second half of a given month is
  available at about the 15th of the next month. »
Un titre a un prix seulement les jours où il a des échecs de livraison (mesuré : SPY 34 jours sur 43).

Le robot garde, pour chaque fichier lu, le calendrier COMPLET des dates de règlement (toutes les lignes), et les prix
(avec le CUSIP de la ligne) des seules compagnies entrées dans ses listes, plus 3 fonds qui suivent le S&P 500 (SPY, IVV,
VOO) pour comparer au marché. Une compagnie ajoutée plus tard est relue dans les fichiers qui couvrent son entrée.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from calendar import monthrange
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from ..models import Evenement

PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
ENTETE = "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE"
MARCHE = ("SPY", "IVV", "VOO")
PREMIER_FICHIER = "202610a"  # les listes de la méthode actuelle commencent le 3 octobre 2026
LIEN = re.compile(r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", re.I)


def fichiers_de_la_page(page: str) -> dict[str, str]:
    """{« 202609a » : adresse du fichier} d'après les liens de la page officielle."""
    return {m.group(2) + m.group(3).lower(): urljoin(PAGE, m.group(1)) for m in LIEN.finditer(page)}


def periode(cle: str) -> tuple[str, str]:
    """Dates de règlement d'un fichier : « a » = du 1er au 14, « b » = du 15 à la fin du mois (mesuré dans les vrais
    fichiers : avril, août et septembre 2026 « a » finissent le 14 ; juillet 2026 « b » commence le 15)."""
    annee, mois = int(cle[:4]), int(cle[4:6])
    if cle[6] == "a":
        return f"{cle[:6]}01", f"{cle[:6]}14"
    return f"{cle[:6]}15", f"{cle[:6]}{monthrange(annee, mois)[1]:02d}"


def lire_fichier(contenu: bytes, garder: set[str]) -> tuple[list[str], dict[str, dict[str, list]]]:
    """(toutes les dates de règlement du fichier, {symbole : {date : [prix, CUSIP]}} pour les symboles gardés).
    Prix « . » (absent ou moins d'un cent) : pas de prix."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        lignes = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    if not lignes or lignes[0].strip() != ENTETE:
        raise ValueError(f"en-tête inattendu : {lignes[0][:80] if lignes else 'fichier vide'}")
    jours, prix = set(), {}
    for l in lignes[1:]:
        p = l.split("|")
        if len(p) != 6 or not re.fullmatch(r"\d{8}", p[0]):
            continue  # ligne finale « Trailer total quantity of shares … »
        jours.add(p[0])
        symbole = p[2].strip()
        if symbole in garder and re.fullmatch(r"\d+(?:\.\d+)?", p[5].strip()):
            prix.setdefault(symbole, {})[p[0]] = [float(p[5]), p[1].strip()]
    return sorted(jours), prix


def chemin_etat(donnees) -> Path:
    return Path(donnees) / "prix" / "sec_ftd.json"


def lire_etat(donnees) -> dict:
    c = chemin_etat(donnees)
    return json.loads(c.read_text(encoding="utf-8")) if c.exists() else {"fichiers": {}, "prix": {}}


def entrees_suivies(donnees) -> dict[str, str]:
    """{symbole : date de sa première entrée (AAAAMMJJ)} d'après l'historique des listes (resultats.py)."""
    c = Path(donnees) / "resultats" / "suggestions.json"
    suivis = {s: "00000000" for s in MARCHE}
    for e in (json.loads(c.read_text(encoding="utf-8")).get("entrees", []) if c.exists() else []):
        jour = e["entree"][:10].replace("-", "")
        suivis[e["symbole"]] = min(suivis.get(e["symbole"], jour), jour)
    return suivis


def collecter(ctx) -> list[Evenement]:
    e = lire_etat(ctx.donnees)
    suivis = entrees_suivies(ctx.donnees)
    liens = fichiers_de_la_page(ctx.client.get(PAGE).contenu.decode("utf-8", "replace"))
    if not liens:
        raise RuntimeError("aucun fichier sur la page officielle (la page a changé ?)")
    for cle in sorted(c for c in liens if c >= PREMIER_FICHIER):
        deja = e["fichiers"].get(cle)
        fin = periode(cle)[1]
        a_lire = {s for s, debut in suivis.items() if fin >= debut and (not deja or s not in deja["symboles"])}
        if deja and not a_lire:
            continue
        jours, prix = lire_fichier(ctx.client.get(liens[cle]).contenu, a_lire)
        for s, p in prix.items():
            e["prix"].setdefault(s, {}).update(p)
        e["fichiers"][cle] = {"adresse": liens[cle], "jours": jours, "lu": ctx.maintenant.isoformat(),
                              "symboles": sorted(set(deja["symboles"] if deja else []) | a_lire)}
    c = chemin_etat(ctx.donnees)
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_text(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return []


def couvert_jusqu_au(e: dict) -> str | None:
    """Dernière date de règlement couverte par les fichiers lus (fin de période du plus récent), AAAAMMJJ."""
    return max((periode(c)[1] for c in e["fichiers"]), default=None)


def calendrier(e: dict) -> list[str]:
    return sorted({j for f in e["fichiers"].values() for j in f["jours"]})


def mise_en_ligne_prevue(jour_reglement: str) -> date:
    """Quand la SEC publie le fichier qui contient cette date de règlement (« vers » : elle ne garantit pas la date)."""
    a, m, j = int(jour_reglement[:4]), int(jour_reglement[4:6]), int(jour_reglement[6:])
    if j <= 14:
        return date(a, m, monthrange(a, m)[1])
    return date(a + (m == 12), m % 12 + 1, 15)
