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


def cle_transaction(ev: dict) -> tuple | None:
    """Même compagnie, même sens, et exactement les mêmes lignes (date, code, nombre d'actions, prix)."""
    lignes = (ev.get("data") or {}).get("transactions") or []
    if ev["source"] != "sec_form4" or not ev.get("tickers") or not lignes:
        return None
    return (ev["tickers"][0], ev["kind"],
            tuple(sorted((t.get("date"), t.get("code"), t.get("actions"), t.get("prix")) for t in lignes)))


def marquer_doublons_form4(donnees: Path) -> int:
    """La même transaction déclarée dans plusieurs formulaires 4 (entités liées : un administrateur et son fonds, un
    fonds et ses gestionnaires) n'est montrée qu'une fois : la 1re déclaration (la plus ancienne) reste, les autres
    sont marquées « même transaction » et nommées dans « aussi déclarée par ». Mesuré du 3 septembre au 3 octobre
    2026 : 6 cas sur 201 formulaires 4 (ex. Blackstone : 5 dépôts pour une seule vente).
    Le score n'est pas touché : il ne compte déjà qu'une fois le même achat (même jour, même montant)."""
    depot = Depot(donnees)
    tous = copy.deepcopy(depot.lire("evenements"))
    groupes: dict[tuple, list[dict]] = {}
    for ev in tous:
        cle = cle_transaction(ev)
        if cle:
            groupes.setdefault(cle, []).append(ev)
    modifies = {}
    for membres in groupes.values():
        membres.sort(key=lambda d: (d["published_on"], d["id"]))
        premier, autres = membres[0], membres[1:]
        noms = []
        for ev in autres:
            declarants = (ev.get("entities") or [])[:-1]  # la dernière entité est la compagnie
            if not declarants:
                nom = ev["official_id"]
            elif len(declarants) == 1:
                nom = declarants[0]
            else:
                nom = f"{declarants[0]} et {len(declarants) - 1} autre{'s' if len(declarants) > 2 else ''}"
            noms.append(nom)
            if ev["data"].get("meme_transaction_que") != premier["id"]:
                ev["data"]["meme_transaction_que"] = premier["id"]
                modifies[ev["id"]] = ev
        if premier["data"].get("meme_transaction_que"):
            del premier["data"]["meme_transaction_que"]
            modifies[premier["id"]] = premier
        if (premier["data"].get("aussi_declare_par") or []) != noms:
            if noms:
                premier["data"]["aussi_declare_par"] = noms
            else:
                premier["data"].pop("aussi_declare_par", None)
            modifies[premier["id"]] = premier
    if modifies:
        depot.enregistrer([Evenement.from_dict(d) for d in modifies.values()])
    return len(modifies)
