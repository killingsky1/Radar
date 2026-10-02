"""Client web poli : il s'identifie, limite sa vitesse et réessaie quand un site est occupé.

Règles de la SEC : maximum 10 requêtes/seconde et un nom + courriel dans chaque requête.
On reste à 5/seconde pour garder une marge.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse

from .models import empreinte, maintenant_utc

VITESSE_MAX = {"sec.gov": 5.0}  # requêtes par seconde, par domaine
VITESSE_DEFAUT = 2.0
CODES_A_REESSAYER = {429, 500, 502, 503, 504}


class ErreurSource(Exception):
    """Une source n'a pas pu être lue correctement."""


@dataclass
class Telechargement:
    url: str
    statut: int
    contenu: bytes
    sha256: str
    recu_a: str


def _domaine_racine(hote: str) -> str:
    return ".".join(hote.split(".")[-2:])


class ClientPoli:
    def __init__(self, contact: str | None, session=None, delai: float = 30, essais: int = 4,
                 dormir=time.sleep, horloge=time.monotonic):
        if session is None:
            import requests

            session = requests.Session()
        self.contact = (contact or "").strip()
        self.session = session
        self.delai = delai
        self.essais = essais
        self.dormir = dormir
        self.horloge = horloge
        self._dernier_appel: dict[str, float] = {}
        identite = f"Radar projet personnel {self.contact}".strip()
        self.entetes = {"User-Agent": identite, "Accept-Encoding": "gzip, deflate"}

    def _attendre_son_tour(self, domaine: str) -> None:
        intervalle = 1.0 / VITESSE_MAX.get(domaine, VITESSE_DEFAUT)
        dernier = self._dernier_appel.get(domaine)
        if dernier is not None:
            reste = intervalle - (self.horloge() - dernier)
            if reste > 0:
                self.dormir(reste)
        self._dernier_appel[domaine] = self.horloge()

    def get(self, url: str, entetes: dict | None = None) -> Telechargement:
        return self._requete("get", url, entetes)

    def post(self, url: str, donnees: dict, entetes: dict | None = None) -> Telechargement:
        """Pour les sites qui demandent d'accepter des conditions ou d'envoyer un formulaire de recherche (Sénat)."""
        return self._requete("post", url, entetes, donnees)

    def cookie(self, nom: str) -> str | None:
        pot = getattr(self.session, "cookies", None)
        return pot.get(nom) if pot is not None else None

    def _requete(self, methode: str, url: str, entetes: dict | None, donnees: dict | None = None) -> Telechargement:
        hote = (urlparse(url).hostname or "").lower()
        domaine = _domaine_racine(hote)
        if domaine == "sec.gov" and "@" not in self.contact:
            raise ErreurSource("Courriel de contact manquant : la SEC l'exige dans chaque requête.")
        derniere_erreur = "aucun essai"
        for essai in range(self.essais):
            self._attendre_son_tour(domaine)
            try:
                h = {**self.entetes, **(entetes or {})}
                if methode == "post":
                    r = self.session.post(url, data=donnees, headers=h, timeout=self.delai)
                else:
                    r = self.session.get(url, headers=h, timeout=self.delai)
            except Exception as exc:  # coupure réseau, délai dépassé…
                derniere_erreur = f"{type(exc).__name__}"
                self.dormir(min(2 ** essai, 30))
                continue
            if r.status_code == 200:
                return Telechargement(url, 200, r.content, empreinte(r.content), maintenant_utc())
            derniere_erreur = f"HTTP {r.status_code}"
            if r.status_code in CODES_A_REESSAYER:
                try:
                    attente = float(r.headers.get("Retry-After", 2 ** essai))
                except ValueError:
                    attente = 2 ** essai
                self.dormir(min(attente, 60))
                continue
            break  # 403, 404… : réessayer ne changera rien
        raise ErreurSource(f"{url} : {derniere_erreur}")
