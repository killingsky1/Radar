"""Sauver 2 pages d'actions OFAC telles quelles (pour recompter sans rien deviner)."""
import time
from pathlib import Path
import requests
S = Path("labo/resultats-ofac"); S.mkdir(parents=True, exist_ok=True)
for n in ("20260923", "20260918"):
    time.sleep(1)
    r = requests.get(f"https://ofac.treasury.gov/recent-actions/{n}", headers={"User-Agent": "Radar projet personnel"}, timeout=60)
    (S / f"ofac_{n}.html").write_bytes(r.content)
    print(n, r.status_code, len(r.content))
