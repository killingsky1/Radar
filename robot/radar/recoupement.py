"""Recoupement : deux sources officielles qui publient le même acte -> badge « Confirmé ».

Maison-Blanche (le jour de la signature) <-> Registre fédéral (quelques jours plus tard) :
même titre officiel (sans tenir compte des majuscules, accents ni ponctuation), signé à 3 jours près,
et une seule paire possible des deux côtés (sinon aucun lien : rien plutôt que faux).

Effet : l'info de la Maison-Blanche reçoit la confirmation du Registre (badge « Confirmé »).
L'info du Registre reçoit celle de la Maison-Blanche et est marquée « même acte » : elle reste
enregistrée, mais l'app ne la montre pas en double.
Testé sur 60 jours de vrais documents : 29 paires, aucune fausse.
"""

from __future__ import annotations

import copy
import html
import re
import unicodedata
from datetime import date
from pathlib import Path

from .models import Evenement
from .store import Depot

ECART_MAX_JOURS = 3


def titre_normalise(titre: str) -> str:
    t = unicodedata.normalize("NFKD", html.unescape(titre or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", t.lower())


def _ajouter_confirmation(ev: dict, autre: dict) -> bool:
    c = {"source": autre["source"], "official_url": autre["official_url"], "official_id": autre["official_id"]}
    if c in ev["confirmations"]:
        return False
    ev["confirmations"].append(c)
    return True


def paires_presidentielles(evenements: list[dict]) -> list[tuple[dict, dict]]:
    mb = [e for e in evenements if e["source"] == "maison_blanche"]
    fr = [e for e in evenements if e["source"] == "registre_federal" and e.get("data", {}).get("sorte") == "presidentiel"]

    def proches(a: dict, b: dict) -> bool:
        return (titre_normalise(a["data"].get("titre_officiel", "")) == titre_normalise(b["data"].get("titre_officiel", ""))
                and abs((date.fromisoformat(a["published_on"]) - date.fromisoformat(b["occurred_on"])).days) <= ECART_MAX_JOURS)

    paires = []
    for a in mb:
        candidats = [b for b in fr if proches(a, b)]
        if len(candidats) == 1 and sum(proches(x, candidats[0]) for x in mb) == 1:
            paires.append((a, candidats[0]))
    return paires


def recouper(donnees: Path) -> int:
    """Ajoute les confirmations manquantes. Retourne le nombre d'infos modifiées."""
    depot = Depot(donnees)
    # Copies : on ne touche pas aux lignes en mémoire du dépôt (sinon il croirait que rien n'a changé).
    tous = copy.deepcopy(depot.lire("evenements") + depot.lire("a_verifier"))
    modifies = {}
    for mb, fr in paires_presidentielles(tous):
        if _ajouter_confirmation(mb, fr):
            modifies[mb["id"]] = mb
        if _ajouter_confirmation(fr, mb) or fr["data"].get("meme_acte_que") != mb["id"]:
            fr["data"]["meme_acte_que"] = mb["id"]
            modifies[fr["id"]] = fr
    if modifies:
        depot.enregistrer([Evenement.from_dict(d) for d in modifies.values()])
    return len(modifies)
