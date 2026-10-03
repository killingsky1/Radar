"""Où est la date dans une lettre d'approbation FDA ? Et que dit la page Drugs@FDA ? (sans rien deviner)"""
import io, re, time
from pathlib import Path
import pdfplumber, requests
S = Path("labo/resultats-lettres"); S.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Radar projet personnel"}
out = []
for nom, u in [("MIMRYLO", "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220605Orig1s000ltr.pdf"),
               ("ONSWIK", "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/761408Orig1s000ltr.pdf")]:
    time.sleep(1)
    r = requests.get(u, headers=UA, timeout=60)
    out.append(f"## {nom} · HTTP {r.status_code} · {u}")
    if r.ok:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            textes = [(p.extract_text() or "") for p in pdf.pages]
        out.append(f"--- dernière page ---\n{textes[-1][-1500:]}")
        tout = " ".join(textes)
        out.append("dates trouvées : " + str(sorted(set(re.findall(
            r"\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}\.\d\d\.\d\d|(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December) \d{1,2}, \d{4})\b", tout)))))
for appl in ("220605", "220496"):
    time.sleep(1)
    u = f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={appl}"
    r = requests.get(u, headers=UA, timeout=60)
    t = " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)).split())
    i = t.find("Approval Date")
    out.append(f"## Drugs@FDA {appl} · HTTP {r.status_code}\n{t[max(0, i - 600):i + 1500] if i >= 0 else t[:2000]}")
(S / "lettres2.md").write_text("\n".join(out) + "\n", encoding="utf-8"); print("\n".join(out))
