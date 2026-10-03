"""Mesure : pourquoi l'empreinte brute des pages « -index-headers.html » (8-K) ne correspond jamais à celle du robot ?

Pour les 9 dépôts signalés par l'audit du 3 octobre (lus par le robot le 2 octobre, empreinte des octets bruts) :
  A = page téléchargée comme le robot (requests, gzip)
  B = comme l'audit (urllib, sans gzip)
  C = comme le robot mais sans gzip, D = urllib avec gzip
On compare chaque version à l'empreinte enregistrée par le robot et à la page sauvée par l'audit de 00 h 12 UTC,
et on écrit les différences ligne par ligne.
"""

import difflib
import gzip
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "robot")
from radar.collecteurs.sec import empreinte_entete  # noqa: E402
from radar.http import ClientPoli  # noqa: E402

CONTACT = "math-veronneau1@hotmail.com"
UA = f"Radar projet personnel {CONTACT}"
SORTIE = Path("labo/resultats6")
ACC = ["0001193125-26-405960", "0001493152-26-045040", "0001193125-26-408371", "0001140361-26-038170",
       "0001424929-26-000057", "0001766478-26-000058", "0001437749-26-031535", "0001193125-26-409143",
       "0001193125-26-410681"]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def evenements_du_robot() -> dict[str, dict]:
    subprocess.run(["git", "fetch", "-q", "origin", "main"], check=True)
    fichiers = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/main", "data/evenements/"],
                              capture_output=True, text=True, check=True).stdout.split()
    evs = {}
    for f in fichiers:
        texte = subprocess.run(["git", "show", f"origin/main:{f}"], capture_output=True, text=True, check=True).stdout
        for ligne in texte.splitlines():
            if ligne.strip():
                d = json.loads(ligne)
                if d["source"] == "sec_8k" and d["official_id"] in ACC:
                    evs[d["official_id"]] = d
    return evs


def urllib_get(url: str, avec_gzip: bool) -> tuple[bytes, dict]:
    h = {"User-Agent": UA}
    if avec_gzip:
        h["Accept-Encoding"] = "gzip"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
        brut, entetes = r.read(), dict(r.headers)
    if entetes.get("Content-Encoding") == "gzip":
        brut = gzip.decompress(brut)
    time.sleep(0.4)
    return brut, entetes


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    evs = evenements_du_robot()
    robot = ClientPoli(CONTACT)
    sans_gzip = ClientPoli(CONTACT)
    sans_gzip.entetes = {"User-Agent": UA}
    lignes = ["# Mesure : pages « -index-headers.html » des 8-K", ""]
    for acc in ACC:
        ev = evs.get(acc)
        if not ev:
            lignes.append(f"- {acc} : pas trouvé dans les données du robot")
            continue
        url = ev["official_url"]
        a = robot.get(url)
        c = sans_gzip.get(url)
        b, entetes_b = urllib_get(url, False)
        d, entetes_d = urllib_get(url, True)
        versions = {"A robot (requests+gzip)": a.contenu, "C requests sans gzip": c.contenu,
                    "B audit (urllib)": b, "D urllib+gzip": d}
        sauvee = None
        try:
            sauvee = subprocess.run(["git", "show", f"HEAD:labo/resultats/differents/{acc}.1.html"],
                                    capture_output=True, check=True).stdout
            versions["S sauvée par l'audit à 00 h 12"] = sauvee
        except subprocess.CalledProcessError:
            pass
        lignes.append(f"## {acc} · {ev['title']}")
        lignes.append(f"- robot : empreinte enregistrée {ev['sha256'][:16]} · lu le {ev['collected_at']} · {ev['parser_version']}")
        for nom, contenu in versions.items():
            lignes.append(f"- {nom} : {len(contenu)} octets · empreinte {sha(contenu)[:16]}"
                          f" · = robot : {'OUI' if sha(contenu) == ev['sha256'] else 'non'}"
                          f" · en-tête officiel {empreinte_entete(contenu.decode('utf-8', 'replace'))[:16]}")
        lignes.append(f"- en-têtes B : {json.dumps({k: v for k, v in entetes_b.items() if k.lower() in ('content-type', 'content-length', 'last-modified', 'etag', 'server', 'date', 'x-cache', 'age')})}")
        lignes.append(f"- en-têtes D : {json.dumps({k: v for k, v in entetes_d.items() if k.lower() in ('content-encoding', 'content-length', 'last-modified', 'etag', 'age')})}")
        reference = a.contenu
        for nom, contenu in versions.items():
            if contenu != reference:
                diff = list(difflib.unified_diff(reference.decode("utf-8", "replace").splitlines(),
                                                 contenu.decode("utf-8", "replace").splitlines(),
                                                 "A robot", nom, lineterm="", n=1))
                (SORTIE / f"{acc}.{nom[0]}.diff").write_text("\n".join(diff[:300]), encoding="utf-8")
                lignes.append(f"- différence A → {nom} : {len(diff)} lignes de diff (fichier {acc}.{nom[0]}.diff)")
                if not diff:
                    pos = next(i for i, (x, y) in enumerate(zip(reference, contenu)) if x != y) if len(reference) == len(contenu) else min(len(reference), len(contenu))
                    lignes.append(f"  - octets différents à la position {pos} : {reference[pos-40:pos+40]!r} / {contenu[pos-40:pos+40]!r}")
        (SORTIE / f"{acc}.A.html").write_bytes(a.contenu)
        lignes.append("")
    (SORTIE / "mesure.md").write_text("\n".join(lignes), encoding="utf-8")
    print("\n".join(lignes))


if __name__ == "__main__":
    main()
