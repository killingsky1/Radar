"""Télécharge 9 vrais dépôts SEC (achats lors d'une émission ou hors bourse, 13D avec ou sans « sous-évaluée »)
pour les tests du robot. Lecture seule, 4 requêtes par seconde au plus."""
import gzip
import time
from pathlib import Path

import requests

UA = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com", "Accept-Encoding": "gzip, deflate"}
DEPOTS = [  # (cik du dossier, numéro officiel)
    (849145, "0001193125-26-407271"),   # HGBL : achat négocié en privé (formulaire 4)
    (1802369, "0001193125-26-408061"),  # ADRX : George Simeon (formulaire 4, sans note d'émission)
    (1802369, "0000947871-26-000910"),  # ADRX : OrbiMed (formulaire 4, « initial public offering »)
    (1549966, "0001013594-26-000998"),  # SAMG : Equinox (13D, « undervalued »)
    (1846416, "0001493152-26-045190"),  # ONEN : NCCS (13D, contrat d'achat à terme d'une fusion)
    (1672909, "0001398344-26-017759"),  # CPHC : Gate City (13D, « undervalued »)
    (1802369, "0000947871-26-000917"),  # ADRX : OrbiMed (13D, entrée en bourse)
    (1063761, "0001189793-26-000014"),  # SPG : administrateur, réinvestissement de dividendes (formulaire 4)
]
sortie = Path("labo/fixtures-emissions")
sortie.mkdir(parents=True, exist_ok=True)
for cik, acc in DEPOTS:
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}.txt"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    (sortie / f"{acc}.txt.gz").write_bytes(gzip.compress(r.content, 9))
    print(acc, len(r.content))
    time.sleep(0.3)
