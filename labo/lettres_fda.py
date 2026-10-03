"""Le vrai texte de 3 lettres d'approbation de la FDA (pour régler le vérificateur sans rien deviner)."""
import io, time
from pathlib import Path
import pdfplumber, requests
S = Path("labo/resultats-lettres"); S.mkdir(parents=True, exist_ok=True)
out = []
for nom, u in [("MIMRYLO", "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220605Orig1s000ltr.pdf"),
               ("LISRAYA", "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220106Orig1s000ltr.pdf"),
               ("TAUKLARIFY", "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220496Orig1s000ltr.pdf")]:
    time.sleep(1)
    r = requests.get(u, headers={"User-Agent": "Radar projet personnel"}, timeout=60)
    out.append(f"## {nom} · HTTP {r.status_code} · {len(r.content)} octets · {u}")
    if r.ok:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            out.append(f"pages : {len(pdf.pages)} · images page 1 : {len(pdf.pages[0].images)}")
            for i, p in enumerate(pdf.pages[:2]):
                out.append(f"--- page {i + 1} ---\n{(p.extract_text() or '(aucun texte)')[:1800]}")
(S / "lettres.md").write_text("\n".join(out) + "\n", encoding="utf-8"); print("\n".join(out))
