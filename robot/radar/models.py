"""Format commun de chaque info collectée par le robot, peu importe la source."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

CATEGORIES = ("compagnies", "baleines", "politiciens", "militaire", "gouvernement", "canada")
BADGES = ("confirme", "officiel", "a_verifier")


def maintenant_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empreinte(contenu: bytes) -> str:
    """Empreinte SHA-256 : prouve plus tard que le document n'a pas changé."""
    return hashlib.sha256(contenu).hexdigest()


@dataclass
class Confirmation:
    """Une 2e source officielle qui confirme la même info."""

    source: str
    official_url: str
    official_id: str


@dataclass
class Evenement:
    source: str  # identifiant de la source (voir registry.py)
    official_id: str  # numéro officiel : n° SEC, n° de contrat, n° de document…
    category: str
    kind: str  # ex. achat_initie, contrat, decret
    title: str  # résumé en français
    occurred_on: str  # date de l'action (AAAA-MM-JJ)
    published_on: str  # date de publication officielle (AAAA-MM-JJ)
    official_url: str  # lien vers le document original
    sha256: str  # empreinte du document original
    parser_version: str  # version du lecteur qui l'a décortiqué
    collected_at: str = field(default_factory=maintenant_utc)
    tickers: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    amount_min: float | None = None
    amount_max: float | None = None
    currency: str = "USD"
    direction: int = 0  # +1 positif, -1 négatif, 0 neutre
    checks: dict[str, bool] = field(default_factory=dict)
    badge: str = "a_verifier"
    confirmations: list[Confirmation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.official_id}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Evenement:
        d = dict(d)
        d.pop("id", None)
        d["confirmations"] = [Confirmation(**c) for c in d.get("confirmations", [])]
        return cls(**d)
