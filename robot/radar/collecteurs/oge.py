"""Rapports de transactions (278-T) du président, du vice-président et des postes de niveaux I et II (OGE).

Source : l'adresse de données publique qu'appelle la page officielle « Officials' Individual Disclosures Search
Collection » de l'OGE (extapps2.oge.gov ; robots.txt absent : tout est permis). Lue une fois par jour de semaine.
Seuls les rapports avec un lien direct vers le PDF sont gardés : l'OGE les publie sans formulaire 201 (président,
vice-président, postes payés aux niveaux I et II de l'Executive Schedule). Les autres (« Request this Document »)
exigent un formulaire 201 : le robot ne les lit jamais.
Le robot ne lit pas le contenu des rapports (celui du président est une image numérisée) : la liste dit qui a déclaré
des transactions et quand, avec le lien vers le document officiel. Aucun symbole, donc 0 point dans le score.
Loi (5 U.S.C. § 13107(c)) : interdit d'obtenir ou d'utiliser ces rapports à des fins commerciales (sauf les médias),
pour établir une cote de crédit ou pour solliciter de l'argent. Radar : usage personnel seulement.
"""

from __future__ import annotations

import html
import json
import re
from datetime import timedelta
from urllib.parse import quote

from ..http import ErreurSource
from ..models import Evenement
from ..validate import controle_source
from .regulateurs import deja

VERSION = "oge-1"
API = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest"
COLONNES = ("docDate", "title", "type", "name", "agency", "level")
# Les 2 recherches de la page officielle : les 278-T des niveaux I et II, et ceux dont le poste contient « President »
FILTRES = ({2: "Transaction", 5: "Level"}, {2: "Transaction", 1: "President"})
LIEN = re.compile(r"href='(https://extapps2\.oge\.gov/201/Presiden\.nsf/PAS\+Index/([0-9A-F]{32})/\$FILE/[^']+\.pdf)'"
                  r">278 Transaction</a>", re.I)
POSTES_SANS_201 = {"President": "président des États-Unis", "Vice President": "vice-président des États-Unis"}
NIVEAUX_SANS_201 = {"Level I": "niveau I", "Level II": "niveau II"}
JOURS = 90  # comme le fil : les rapports ajoutés depuis 3 mois


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


def evenement(x: dict, sha256: str) -> Evenement:
    notes = ["Liste seulement : le robot ne lit pas le contenu du rapport (celui du président est une image "
             "numérisée). Ouvrez le document officiel pour voir les transactions."]
    if x["modifie_le"]:
        notes.append(f"Rapport modifié (amended) le {x['modifie_le']}, selon l'OGE.")
    return Evenement(
        source="oge_278t", official_id=x["unid"], category="politiciens", kind="rapport_278t",
        title=f"{nom_affiche(x['nom'])} ({poste_fr(x)}) : nouveau rapport de transactions (278-T)",
        occurred_on=x["ajoute_le"], published_on=x["ajoute_le"], official_url=x["pdf"], sha256=sha256,
        parser_version=VERSION, entities=[nom_affiche(x["nom"]), x["agence"]], notes=notes,
        data={k: x[k] for k in ("nom", "titre", "agence", "niveau", "ajoute_le", "modifie_le", "pdf_valide", "taille")},
    )


def collecter(ctx) -> list[Evenement]:
    connus = deja(ctx, "oge_278t", mois_max=24)  # un rapport déjà lu ne se relit pas, même après 3 mois
    limite = (ctx.maintenant.date() - timedelta(days=JOURS)).isoformat()
    lignes: dict[str, dict] = {}
    for filtres in FILTRES:
        d = json.loads(ctx.client.get(adresse(filtres)).contenu)
        if not isinstance(d.get("data"), list) or "recordsFiltered" not in d:
            raise ErreurSource("réponse inattendue de l'OGE (pas de tableau « data »)")
        for r in d["data"]:
            x = lire_ligne(r)
            if x and x["ajoute_le"] >= limite and x["unid"] not in connus:
                lignes[x["unid"]] = x
    evs = []
    for x in sorted(lignes.values(), key=lambda x: (x["ajoute_le"], x["unid"])):
        try:
            t = ctx.client.get(x["pdf"])  # sans formulaire 201 : permis ; l'empreinte prouve que le document existe
        except ErreurSource:
            continue  # document pas lisible maintenant : rien de publié, nouvel essai au prochain passage
        x["pdf_valide"], x["taille"] = t.contenu[:5] == b"%PDF-", len(t.contenu)
        evs.append(evenement(x, t.sha256))
    return evs


@controle_source("oge_278t")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "sans_formulaire_201": bool(re.fullmatch(r"https://extapps2\.oge\.gov/201/Presiden\.nsf/PAS\+Index/[0-9A-Fa-f]{32}"
                                                 r"/\$FILE/[^']+\.pdf", ev.official_url or "")),
        "poste_publie_sans_201": d.get("titre") in POSTES_SANS_201 or d.get("niveau") in NIVEAUX_SANS_201,
        "document_pdf": d.get("pdf_valide") is True,
    }
