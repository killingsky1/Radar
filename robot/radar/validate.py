"""Contrôles automatiques. Une info entre dans les suggestions seulement si TOUT passe.

Badges :
- confirme   : une 2e source officielle indépendante confirme l'info
- officiel   : une source officielle, tous les contrôles passés
- a_verifier : au moins un contrôle raté ; n'entre jamais dans le top 10
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, timedelta
from urllib.parse import urlparse

from .models import CATEGORIES, Evenement
from .registry import SOURCES

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SYMBOLE_RE = re.compile(r"^[A-Z0-9]{1,6}([.\-][A-Z0-9]{1,3})?$")
PLUS_VIEILLE_DATE = date(1990, 1, 1)

# Contrôles propres à une source : fonction(événement) -> {nom_du_controle: réussi}
ControleSource = Callable[[Evenement], dict[str, bool]]
CONTROLES_SOURCE: dict[str, list[ControleSource]] = {}


def controle_source(source_id: str):
    """Décorateur pour ajouter un contrôle spécifique à une source."""

    def enregistrer(fn: ControleSource) -> ControleSource:
        CONTROLES_SOURCE.setdefault(source_id, []).append(fn)
        return fn

    return enregistrer


def domaine_officiel(url: str, domaines: tuple[str, ...]) -> bool:
    morceaux = urlparse(url or "")
    hote = (morceaux.hostname or "").lower()
    if morceaux.scheme != "https" or not hote:
        return False
    return any(hote == d or hote.endswith("." + d) for d in domaines)


def _date(texte: str) -> date | None:
    try:
        return date.fromisoformat(texte)
    except (TypeError, ValueError):
        return None


def jours_ouvrables(debut: date, fin: date) -> int:
    """Nombre de jours ouvrables (lun.-ven.) après `debut`, jusqu'à `fin` inclus."""
    jours, d = 0, debut
    while d < fin:
        d += timedelta(days=1)
        if d.weekday() < 5:
            jours += 1
    return jours


def delai_depasse(ev: Evenement, limite: int, ouvrables: bool) -> bool:
    """Vrai si la publication a dépassé le délai légal (ex. formulaire 4 : 2 jours ouvrables).

    Un retard n'invalide pas l'info : c'est noté, et c'est un signal en soi.
    """
    occ, pub = _date(ev.occurred_on), _date(ev.published_on)
    if occ is None or pub is None:
        return False
    ecart = jours_ouvrables(occ, pub) if ouvrables else (pub - occ).days
    return ecart > limite


def controles_generaux(ev: Evenement, aujourd_hui: date) -> dict[str, bool]:
    src = SOURCES.get(ev.source)
    c: dict[str, bool] = {}
    c["source_connue"] = src is not None and src.ecartee is None
    c["source_officielle"] = src is not None and src.officielle
    c["champs_requis"] = (
        all([ev.official_id, ev.kind, ev.title, ev.official_url, ev.parser_version]) and ev.category in CATEGORIES
    )
    c["empreinte"] = bool(SHA256_RE.match(ev.sha256 or ""))
    c["domaine_officiel"] = src is not None and domaine_officiel(ev.official_url, src.domaines)
    occ, pub = _date(ev.occurred_on), _date(ev.published_on)
    c["dates_coherentes"] = (
        occ is not None and pub is not None and PLUS_VIEILLE_DATE <= occ <= pub <= aujourd_hui + timedelta(days=1)
    )
    if ev.amount_min is not None or ev.amount_max is not None:
        bas = ev.amount_min if ev.amount_min is not None else ev.amount_max
        haut = ev.amount_max if ev.amount_max is not None else ev.amount_min
        c["montant_coherent"] = bas >= 0 and haut >= bas
    c["symboles_valides"] = all(SYMBOLE_RE.match(t or "") for t in ev.tickers)
    return c


def valider(ev: Evenement, aujourd_hui: date) -> Evenement:
    checks = controles_generaux(ev, aujourd_hui)
    for fn in CONTROLES_SOURCE.get(ev.source, []):
        try:
            checks.update(fn(ev))
        except Exception:  # un contrôle qui plante compte comme un échec, jamais comme un succès
            checks[f"controle_{fn.__name__}"] = False

    # Une confirmation doit venir d'une AUTRE source officielle, sur son propre domaine officiel.
    valides = []
    for conf in ev.confirmations:
        s = SOURCES.get(conf.source)
        if s and s.officielle and s.ecartee is None and conf.source != ev.source and conf.official_id \
                and domaine_officiel(conf.official_url, s.domaines):
            valides.append(conf)
    if ev.confirmations:
        checks["confirmations_valides"] = len(valides) == len(ev.confirmations)

    ev.checks = checks
    if not all(checks.values()):
        ev.badge = "a_verifier"
    elif valides:
        ev.badge = "confirme"
    else:
        ev.badge = "officiel"
    return ev
