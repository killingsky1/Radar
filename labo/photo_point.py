"""Photo du résultat de facteurs.py : le seul point solide (compagnies de moins de 100 M$ en bourse), 3 ans.

Usage : python photo_point.py <labo/rejeu3> <sortie.html>
"""
import json
import sys
from pathlib import Path

dossier, sortie = Path(sys.argv[1]), Path(sys.argv[2])
f = json.loads((dossier / "facteurs.json").read_text(encoding="utf-8"))
ANNEES = ["2023-2024", "2024-2025", "2025-2026"]


def pc(x):
    return f"{x * 100:+.1f} %".replace(".", ",").replace("-", "−")


def ligne(an, h):
    r = next((r for r in f["tableau"] if r["facteur"] == "Valeur en bourse" and r["categorie"] == "moins de 100 M$"
              and r["annee"] == an and r["duree"] == h), None)
    if not r:
        return f"<tr><td>{an[:5]}{an[7:]}</td><td colspan='4' class='pm'>pas encore mesurable</td></tr>"
    return (f"<tr><td>{an[:5]}{an[7:]}</td><td>{pc(r['mediane'])}</td><td>{r['bat'] * 100:.0f} %</td>"
            f"<td>{pc(r['reste']['mediane'])}</td><td>{r['reste']['bat'] * 100:.0f} %</td></tr>")


def tableau(h):
    return (f"<h2>Vendre après {h} mois</h2><table><tr><th></th><th colspan='2'>Moins de 100 M$</th>"
            f"<th colspan='2'>Les autres</th></tr><tr><th>Année</th><th>Médiane</th><th>Bat le S&amp;P</th>"
            f"<th>Médiane</th><th>Bat le S&amp;P</th></tr>" + "".join(ligne(an, h) for an in ANNEES) + "</table>")


html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Le point trouvé</title>
<style>
:root {{ color-scheme: light; --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --ring:rgba(11,11,11,0.10); }}
body {{ margin:0; background:var(--page); font-family:system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink); }}
.carte {{ background:var(--surface); margin:16px; padding:16px; border-radius:12px; box-shadow:0 0 0 1px var(--ring); }}
h1 {{ font-size:17px; margin:0 0 4px; font-weight:600; }}
h2 {{ font-size:14px; margin:16px 0 6px; font-weight:600; }}
.sous, .note {{ font-size:13px; color:var(--ink2); margin:0 0 4px; line-height:1.4; }}
.note {{ margin-top:12px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ text-align:right; color:var(--ink2); font-weight:500; padding:4px 0 4px 8px; border-bottom:1px solid var(--grid);
  white-space:nowrap; }}
td {{ text-align:right; padding:5px 0 5px 8px; font-variant-numeric:tabular-nums; border-bottom:1px solid var(--grid);
  white-space:nowrap; }}
th:first-child, td:first-child {{ text-align:left; padding-left:0; }}
td.pm {{ color:var(--muted); }}
</style></head><body><div class="carte">
<h1>Le seul point solide : les compagnies de moins de 100&nbsp;M$</h1>
<p class="sous">15 mesures testées sur les 1&nbsp;597 entrées de Radar (juillet 2023 → juin 2026), connues au moment de
l'achat. Écart médian avec le S&amp;P 500 aux mêmes dates, et part des compagnies qui le battent.</p>
{tableau(1)}
{tableau(3)}
<p class="note">Les compagnies de moins de 100&nbsp;M$ en bourse font perdre chaque année. Les enlever aide un peu
(environ +0,7 point sur la médiane), mais Radar ne bat toujours pas le S&amp;P 500 : aucune des 15 mesures ne fait
gagner Radar chaque année.</p>
</div></body></html>
"""
sortie.write_text(html, encoding="utf-8")
print(f"écrit {sortie}")
