"""Graphique du rejeu d'un an : valeur à la fin de chaque mois (argent réinvesti), Radar contre le S&P 500 aux mêmes
dates, avec l'argent mis. Lit labo/rejeu/mensuel.json ; écrit un HTML autonome (SVG) pour la photo.

Usage : python graphique_rejeu.py <dossier labo/rejeu> <sortie.html>
"""
import json
import sys
from pathlib import Path

dossier, sortie = Path(sys.argv[1]), Path(sys.argv[2])
m = json.loads((dossier / "mensuel.json").read_text(encoding="utf-8"))
b = m["bilan"]
MOIS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
mois = b["mois"]
radar = b["versions"]["Radar"]["chemin_reinvesti"]
spy = b["versions"]["S&P 500 (SPY) aux mêmes dates"]["chemin_reinvesti"]
mis = [round(x, 2) for x in b["investi_par_mois"]]
final_radar = b["versions"]["Radar"]["reinvesti"]
final_spy = b["versions"]["S&P 500 (SPY) aux mêmes dates"]["reinvesti"]
final_frais = b["versions"]["Radar, frais de 10 $ par transaction"]["reinvesti"]
final_garde = b["spy_garde"]["valeur"]


def argent(x):
    return f"{x:,.0f} $".replace(",", " ")


def court(x):
    return f"{x / 1000:.1f} k$".replace(".", ",")


def pc(x):
    return f"{x * 100:+.1f} %".replace(".", ",").replace("-", "−")


L, H = 358, 230  # zone du graphique (px CSS), largeur d'un iPhone moins les marges
G, D, HAUT, BAS = 44, 58, 12, 26  # marges : axe des montants à gauche, étiquettes de fin à droite
haut_max = max(radar + spy + mis)
pas = 2000 if haut_max <= 14000 else 5000
ymax = pas * (int(haut_max // pas) + 1)


def X(i):
    return G + (L - G - D) * i / (len(mois) - 1)


def Y(v):
    return HAUT + (H - HAUT - BAS) * (1 - v / ymax)


grille = ""
for v in range(0, ymax + 1, pas):
    grille += (f'<line x1="{G}" x2="{L - D}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="{"base" if v == 0 else "grille"}"/>'
               f'<text x="{G - 6}" y="{Y(v) + 4:.1f}" class="axe" text-anchor="end">{v // 1000} k$</text>')
for i, mo in enumerate(mois):
    if i in (0, 3, 6, 9, len(mois) - 1):
        a, n = int(mo[:4]), int(mo[5:])
        grille += (f'<text x="{X(i):.1f}" y="{H - 8}" class="axe" text-anchor="middle">{MOIS_FR[n - 1]}'
                   f'{" " + str(a)[2:] if n in (1, 7) else ""}</text>')


def ligne(vals, cls):
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    return (f'<polyline points="{pts}" class="l {cls}"/>'
            f'<circle cx="{X(len(vals) - 1):.1f}" cy="{Y(vals[-1]):.1f}" r="4" class="p {cls}"/>')


courbes = ligne(mis, "mis") + ligne(spy, "spy") + ligne(radar, "radar")
# Étiquettes de fin : Radar d'abord (c'est le sujet), puis les autres seulement si elles ne touchent pas une étiquette
# déjà placée (sinon la légende et les tuiles donnent les montants)
etiquettes, places = "", []
for vals in (radar, spy, mis):
    y = Y(vals[-1])
    if all(abs(y - autre) >= 14 for autre in places):
        etiquettes += f'<text x="{L - D + 8}" y="{y + 4:.1f}" class="fin">{court(vals[-1])}</text>'
        places.append(y)

lignes_tableau = ""
for x in m["mois"]:
    a, n = int(x["mois"][:4]), int(x["mois"][5:])
    lignes_tableau += (f"<tr><td>{MOIS_FR[n - 1]} {a}</td><td>{x['achetees']}</td>"
                       f"<td>{'—' if x['rendement_moyen'] is None else pc(x['rendement_moyen'])}</td>"
                       f"<td>{'—' if x['marche_moyen'] is None else pc(x['marche_moyen'])}</td></tr>")

MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
              "novembre", "décembre"]
v = b["derniere_vente"]
resultats_fin = f"{int(v[6:])} {MOIS_LONGS[int(v[4:6]) - 1]} {v[:4]}"
html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Rejeu d'un an</title>
<style>
:root {{ color-scheme: light; --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --base:#c3c2b7; --s1:#2a78d6; --s2:#eb6834; --ring:rgba(11,11,11,0.10); }}
body {{ margin:0; background:var(--page); font-family:system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink); }}
.carte {{ background:var(--surface); margin:16px; padding:16px 0 12px; border-radius:12px; box-shadow:0 0 0 1px var(--ring); }}
h1 {{ font-size:17px; margin:0 16px 4px; font-weight:600; }}
.sous {{ font-size:13px; color:var(--ink2); margin:0 16px 12px; line-height:1.35; }}
.tuiles {{ display:flex; gap:8px; margin:0 16px 12px; }}
.tuile {{ flex:1; border-radius:10px; box-shadow:0 0 0 1px var(--ring); padding:8px 8px; min-width:0;
  display:flex; flex-direction:column; justify-content:space-between; gap:4px; }}
.tuile .n {{ font-size:12px; color:var(--ink2); display:flex; align-items:center; gap:6px; }}
.tuile .v {{ font-size:19px; font-weight:600; margin-top:2px; }}
.cle {{ width:14px; height:3px; border-radius:2px; display:inline-block; }}
.legende {{ display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:var(--ink2); margin:0 16px 4px; }}
.legende span {{ display:flex; align-items:center; gap:6px; }}
svg {{ display:block; margin:0 16px; }}
.grille {{ stroke:var(--grid); stroke-width:1; }} .base {{ stroke:var(--base); stroke-width:1; }}
.axe {{ font-size:11px; fill:var(--muted); font-variant-numeric:tabular-nums; }}
.fin {{ font-size:11px; fill:var(--ink2); font-variant-numeric:tabular-nums; }}
.l {{ fill:none; stroke-width:2; stroke-linejoin:round; stroke-linecap:round; }}
.p {{ stroke:var(--surface); stroke-width:2; }}
.radar {{ stroke:var(--s1); }} .p.radar {{ fill:var(--s1); stroke:var(--surface); }}
.spy {{ stroke:var(--s2); }} .p.spy {{ fill:var(--s2); stroke:var(--surface); }}
.mis {{ stroke:var(--muted); }} .p.mis {{ fill:var(--muted); stroke:var(--surface); }}
.note {{ font-size:12px; color:var(--ink2); margin:10px 16px 0; line-height:1.4; }}
table {{ width:calc(100% - 32px); margin:12px 16px 0; border-collapse:collapse; font-size:12px; }}
th {{ text-align:right; color:var(--ink2); font-weight:500; padding:4px 0; border-bottom:1px solid var(--grid); }}
td {{ text-align:right; padding:3px 0; font-variant-numeric:tabular-nums; border-bottom:1px solid var(--grid); }}
th:first-child, td:first-child {{ text-align:left; }}
</style></head><body><div class="carte">
<h1>10 000 $ qui suivent Radar pendant 1 an</h1>
<p class="sous">833 $ par mois de juillet 2025 à juin 2026, divisés entre les nouvelles compagnies de la liste « hausse »,
vendues 1 mois plus tard, argent réinvesti. Règles actuelles de Radar, prix officiels de la SEC.</p>
<div class="tuiles">
<div class="tuile"><div class="n"><i class="cle" style="background:var(--s1)"></i>Radar</div><div class="v">{argent(final_radar)}</div></div>
<div class="tuile"><div class="n"><i class="cle" style="background:var(--s2)"></i>S&amp;P 500</div><div class="v">{argent(final_spy)}</div></div>
<div class="tuile"><div class="n">S&amp;P 500 gardé</div><div class="v">{argent(final_garde)}</div></div>
</div>
<div class="legende"><span><i class="cle" style="background:var(--s1)"></i>Radar</span>
<span><i class="cle" style="background:var(--s2)"></i>S&amp;P 500 aux mêmes dates</span>
<span><i class="cle" style="background:var(--muted)"></i>Argent mis</span></div>
<svg width="{L}" height="{H}" viewBox="0 0 {L} {H}" role="img" aria-label="Valeur à la fin de chaque mois">
{grille}{courbes}{etiquettes}</svg>
<p class="note">S&amp;P 500 : le même argent aux mêmes dates. S&amp;P 500 gardé : 833 $ achetés chaque mois et gardés
jusqu'au {resultats_fin}. {b["pas_achetees"]} entrées sur {b["positions"]} pas achetées (pas de prix de la SEC).
Avec des frais de 10 $ par achat et par vente : {argent(final_frais)}. Sans impôt ni change (dollars américains).
Un an peut être de la chance : ce n'est pas une promesse.</p>
<table><tr><th>Mois</th><th>Achetées</th><th>Radar (1 mois)</th><th>S&amp;P 500</th></tr>{lignes_tableau}</table>
</div></body></html>
"""
sortie.write_text(html, encoding="utf-8")
print(f"écrit {sortie}")
