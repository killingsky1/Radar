from datetime import date

import pytest

from radar.models import Confirmation, Evenement, empreinte

AUJOURD_HUI = date(2026, 10, 2)
# Une source officielle de la SEC SANS contrôles propres (sinon ses contrôles s'ajoutent aux tests génériques).
# À changer si cette source reçoit un jour son lecteur et ses contrôles.
SOURCE_GENERIQUE = "sec_blocage"


def bonne_info(**changements) -> Evenement:
    """Une info réaliste qui doit passer tous les contrôles."""
    valeurs = dict(
        source=SOURCE_GENERIQUE,
        official_id="0001234567-26-000001",
        category="compagnies",
        kind="achat_initie",
        title="Le PDG achète 1 000 actions",
        occurred_on="2026-09-28",
        published_on="2026-09-30",
        official_url="https://www.sec.gov/Archives/edgar/data/320193/000123456726000001/form4.xml",
        sha256=empreinte(b"document original"),
        parser_version="test-1",
        tickers=["AAPL"],
        amount_min=100000.0,
        amount_max=100000.0,
        direction=1,
    )
    valeurs.update(changements)
    return Evenement(**valeurs)


def confirmation_officielle() -> Confirmation:
    """Une 2e source officielle, active, sur son propre domaine (le Pentagone, laissé de côté, ne peut plus confirmer)."""
    return Confirmation(
        source="registre_federal",
        official_url="https://www.federalregister.gov/documents/2026/10/01/2026-12345/exemple",
        official_id="2026-12345",
    )


@pytest.fixture
def aujourd_hui():
    return AUJOURD_HUI
