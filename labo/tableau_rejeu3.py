"""Image du rejeu de 3 ans : Radar contre le S&P 500, année par année (labo/rejeu3/strategies.json → HTML autonome).

Usage : python tableau_rejeu3.py <labo/rejeu3> <sortie.html>
"""
import json
import sys
from pathlib import Path

dossier, sortie = Path(sys.argv[1]), Path(sys.argv[2])
cases = json.loads((dossier / "strategies.json").read_text(encoding="utf-8"))
ANNEES = ["2023-2024", "2024-2025", "2025-2026"]


def case(annee, sel, h):
    return next(c for c in cases if c["annee"] == annee and c["selection"] == sel and c["duree"] == h
                and c["depart"] == "strict")


def pc(x):
    return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",").replace("-", "−")


def lignes(sel, h):
    sortie_ = ""
    for an in ANNEES:
        c = case(an, sel, h)
        if not c.get("mesurable") or not c.get("achetees"):
            sortie_ += f"<tr><td>{an[:5]}{an[7:]}</td><td colspan='4' class='pm'>pas encore mesurable</td></tr>"
            continue
        sortie_ += (f"<tr><td>{an[:5]}{an[7:]}</td><td>{c['achetees']}</td><td>{pc(c['ecart_moyen_estime'])}</td>"
                    f"<td>{pc(c['ecart_median_estime'])}</td>"
                    f"<td>{c['battent_le_marche'] * 100 // c['achetees']} %</td></tr>")
    return sortie_


def tableau(titre, sel, h):
    return (f"<h2>{titre}</h2><table><tr><th>Année</th><th>Nombre</th><th>Moyenne</th><th>Médiane</th>"
            f"<th>Bat le S&amp;P</th></tr>{lignes(sel, h)}</table>")


html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Radar contre le S&amp;P 500</title>
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
td.pm {{ text-align:right; color:var(--muted); }}
</style></head><body><div class="carte">
<h1>Radar contre le S&amp;P 500, 3 ans</h1>
<p class="sous">Chaque nouvelle compagnie de la liste « hausse », de juillet 2023 à juin 2026, avec les règles actuelles
de Radar et les prix officiels de la SEC. Écart avec le S&amp;P 500 aux mêmes dates, sans frais.</p>
{tableau("Règle actuelle : garder 1 mois", "toutes", 1)}
{tableau("Garder 12 mois", "toutes", 12)}
{tableau("Petites compagnies, note de 9 et plus, 1 mois", "petites, note de 9 et plus", 1)}
<p class="note"><b>Médiane</b> : la compagnie du milieu. Elle fait moins bien que le S&amp;P 500 presque partout : la
moyenne monte seulement grâce à quelques compagnies qui explosent (AXTI ×24, TERN ×14, RLMD ×12).
Avec 10 $ par transaction, l'écart se creuse encore. Années de 12 mois après juin 2025 : prix pas encore publiés.</p>
</div></body></html>
"""
sortie.write_text(html, encoding="utf-8")
print(f"écrit {sortie}")
