"""Stockage en fichiers texte JSON Lines : lisibles, et tout l'historique reste dans git.

data/evenements/AAAA-MM.jsonl  : infos validées (badge confirme ou officiel)
data/a_verifier/AAAA-MM.jsonl  : infos qui ont raté au moins un contrôle
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Evenement

DOSSIERS = ("evenements", "a_verifier")


def _dossier(ev: Evenement) -> str:
    return "a_verifier" if ev.badge == "a_verifier" else "evenements"


def _mois(ev: Evenement) -> str:
    return ev.published_on[:7] if ev.published_on and len(ev.published_on) >= 7 else "inconnu"


class Depot:
    def __init__(self, racine: Path):
        self.racine = Path(racine)
        self._cache: dict[Path, dict[str, dict]] = {}

    def _charger(self, fichier: Path) -> dict[str, dict]:
        if fichier not in self._cache:
            lignes = {}
            if fichier.exists():
                for ligne in fichier.read_text(encoding="utf-8").splitlines():
                    if ligne.strip():
                        d = json.loads(ligne)
                        lignes[d["id"]] = d
            self._cache[fichier] = lignes
        return self._cache[fichier]

    def enregistrer(self, evenements: list[Evenement]) -> dict[str, int]:
        """Ajoute ou met à jour. Relancer avec les mêmes infos ne change aucun fichier."""
        bilan = {"nouveaux": 0, "modifies": 0, "inchanges": 0}
        touches: set[Path] = set()
        for ev in evenements:
            mois = _mois(ev)
            cible = self.racine / _dossier(ev) / f"{mois}.jsonl"
            ancien = None
            for dossier in DOSSIERS:
                fichier = self.racine / dossier / f"{mois}.jsonl"
                lignes = self._charger(fichier)
                if ev.id in lignes:
                    ancien = lignes[ev.id]
                    if fichier != cible:
                        del lignes[ev.id]
                        touches.add(fichier)
            nouveau = ev.to_dict()
            if ancien is not None:
                # Même document, même verdict : on garde l'ancienne ligne telle quelle (aucun changement dans git).
                if (ancien["sha256"], ancien["badge"], ancien["checks"]) == (
                    nouveau["sha256"], nouveau["badge"], nouveau["checks"]
                ):
                    bilan["inchanges"] += 1
                    continue
                if ancien["sha256"] != nouveau["sha256"]:
                    empreintes = ancien.get("data", {}).get("anciennes_empreintes", []) + [ancien["sha256"]]
                    nouveau["data"]["anciennes_empreintes"] = empreintes
                    nouveau["notes"].append("Document modifié à la source depuis la 1re lecture.")
                bilan["modifies"] += 1
            else:
                bilan["nouveaux"] += 1
            self._charger(cible)[ev.id] = nouveau
            touches.add(cible)
        for fichier in touches:
            self._ecrire(fichier)
        return bilan

    def _ecrire(self, fichier: Path) -> None:
        lignes = self._charger(fichier)
        if not lignes:
            if fichier.exists():
                fichier.unlink()
            return
        fichier.parent.mkdir(parents=True, exist_ok=True)
        ordre = sorted(lignes.values(), key=lambda d: (d["published_on"], d["id"]))
        texte = "".join(json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n" for d in ordre)
        fichier.write_text(texte, encoding="utf-8")

    def lire(self, dossier: str, mois_max: int = 3) -> list[dict]:
        """Les infos des `mois_max` derniers fichiers mensuels d'un dossier."""
        fichiers = sorted((self.racine / dossier).glob("*.jsonl"))[-mois_max:]
        resultat = []
        for f in fichiers:
            resultat.extend(self._charger(f).values())
        return resultat
