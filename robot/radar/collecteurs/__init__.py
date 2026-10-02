"""Un lecteur (collecteur) par source. Chaque phase en ajoute.

Un collecteur reçoit le contexte (client web, date) et retourne une liste d'Evenement.
S'il lève une exception, seule sa source tombe « en panne » ; les autres continuent.
"""

from __future__ import annotations

from collections.abc import Callable

from ..models import Evenement

Collecteur = Callable[["object"], list[Evenement]]

from . import sec  # noqa: E402

COLLECTEURS: dict[str, Collecteur] = {
    "sec_form4": sec.collecter_form4,
    "sec_8k": sec.collecter_8k,
    "sec_13dg": sec.collecter_13dg,
}
