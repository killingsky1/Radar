"""État de santé de chaque source. Principe : rien plutôt que faux."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .registry import SOURCES

LIBELLES = {
    "a_venir": "À venir",
    "ok": "OK",
    "en_retard": "En retard",
    "en_panne": "En panne",
    "en_pause": "En pause",
    "refusee": "Refusée par le site",
    "ecartee": "Laissée de côté",
}


MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")


def jour_fr(iso: str) -> str:
    """« 2026-10-03T20:28:12+00:00 » -> « 3 octobre 2026 » (jour de l'heure de l'Est)."""
    d = datetime.fromisoformat(iso).astimezone(ZoneInfo("America/Toronto")).date()
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


def statut(source_id: str, etat: dict | None, branchee: bool, maintenant: datetime) -> tuple[str, str]:
    """Retourne (code, explication) pour une source."""
    src = SOURCES[source_id]
    if src.ecartee:
        return "ecartee", src.ecartee
    if not branchee:
        return "a_venir", f"Prévue à la phase {src.phase}."
    etat = etat or {}
    if etat.get("pause"):
        return "en_pause", etat.get("raison_pause") or "Mise en pause."
    refus = etat.get("refus") or {}
    if refus.get("confirme"):
        return "refusee", (f"Le site refuse l'accès au robot (erreur {refus['code']}) depuis le {jour_fr(refus['depuis'])} ; "
                           f"Radar respecte ce refus et réessaie une fois le {jour_fr(refus['prochain_essai'])}.")

    limite = timedelta(hours=src.attente_heures)
    succes = etat.get("dernier_succes")
    erreur = etat.get("derniere_erreur")
    if succes is None or maintenant - datetime.fromisoformat(succes) > limite:
        if erreur:
            return "en_panne", f"Dernière erreur : {erreur}"
        return "en_retard", "Pas de lecture réussie récemment."

    # La lecture marche, mais la source publie-t-elle encore ? (ex. fermeture du gouvernement)
    contenu = etat.get("dernier_contenu")
    if src.publication_max_jours and contenu:
        silence = (maintenant.date() - date.fromisoformat(contenu)).days
        if silence > src.publication_max_jours:
            return "en_pause", f"Rien de publié depuis {silence} jours (fermeture du gouvernement ?)."

    if erreur:
        return "ok", f"Lecture OK récemment, mais le dernier essai a échoué : {erreur}"
    return "ok", ""
