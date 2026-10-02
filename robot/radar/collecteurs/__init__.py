"""Un lecteur (collecteur) par source. Chaque phase en ajoute.

Un collecteur reçoit le contexte (client web, date) et retourne une liste d'Evenement.
S'il lève une exception, seule sa source tombe « en panne » ; les autres continuent.
"""

from __future__ import annotations

from collections.abc import Callable

from ..models import Evenement

Collecteur = Callable[["object"], list[Evenement]]

COLLECTEURS: dict[str, Collecteur] = {}
