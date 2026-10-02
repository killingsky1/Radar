"""Audit de vérité : 20 infos publiées, tirées au hasard, comparées au document officiel original.

Pour chaque info :
1. on retélécharge le document original à la SEC ;
2. on vérifie que c'est EXACTEMENT le même document que le robot a lu (même empreinte SHA-256) ;
3. on relit les chiffres avec une méthode indépendante (expressions simples sur le texte brut,
   pas le lecteur XML du robot) et on compare : actions, montant, pourcentage, items 8-K, dates.

Résultat : labo/resultats/verification.md (+ .json). Ne publie rien dans l'app.
"""

from __future__ import annotations

import hashlib
import html
import json
import random
import re
import subprocess
import sys
import time
import urllib.request

UA = "Radar projet personnel math-veronneau1@hotmail.com"
TAILLE = int(sys.argv[1]) if len(sys.argv) > 1 else 20


def telecharger(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        contenu = r.read()
    time.sleep(0.3)
    return contenu


def infos_publiees() -> list[dict]:
    subprocess.run(["git", "fetch", "-q", "origin", "main"], check=True)
    fichiers = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/main", "data/evenements/"],
                              capture_output=True, text=True, check=True).stdout.split()
    infos = []
    for f in fichiers:
        texte = subprocess.run(["git", "show", f"origin/main:{f}"], capture_output=True, text=True, check=True).stdout
        infos += [json.loads(l) for l in texte.splitlines() if l.strip()]
    return [i for i in infos if i["source"].startswith("sec_")]


def valeur(bloc: str, balise: str) -> str | None:
    m = re.search(rf"<{balise}>\s*<value>\s*([^<]*?)\s*</value>", bloc, re.S)
    return m.group(1) if m else None


def verifier(info: dict) -> dict:
    acc = info["official_id"].split(":")[0]
    dossier = info["official_url"].rsplit("/", 1)[0]
    cik = dossier.split("/edgar/data/")[1].split("/")[0]
    if info["source"] == "sec_8k":
        url = f"{dossier}/{acc}-index-headers.html"
    else:  # même chemin que le robot : le document complet du dépôt
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}.txt"
    brut = telecharger(url)
    texte = html.unescape(brut.decode("utf-8", "replace")) if info["source"] == "sec_8k" else brut.decode("utf-8", "replace")
    r = {"id": info["id"], "titre": info["title"], "document": url,
         "meme_document": hashlib.sha256(brut).hexdigest() == info["sha256"], "ecarts": []}

    def comparer(nom, lu, attendu, tolerance=0.0):
        ok = lu == attendu if tolerance == 0 else (lu is not None and attendu is not None and abs(lu - attendu) <= tolerance)
        if not ok:
            r["ecarts"].append(f"{nom} : robot={lu!r} document={attendu!r}")

    depose = re.search(r"FILED AS OF DATE:\s*(\d{8})", texte).group(1)
    comparer("date de dépôt", info["published_on"], f"{depose[:4]}-{depose[4:6]}-{depose[6:]}")

    if info["source"] == "sec_form4":
        code = info["official_id"].split(":")[1]
        actions = montant = 0.0
        for bloc in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", texte, re.S):
            if re.search(rf"<transactionCode>\s*{code}\s*</transactionCode>", bloc):
                a, p = float(valeur(bloc, "transactionShares") or 0), float(valeur(bloc, "transactionPricePerShare") or 0)
                actions += a
                montant += a * p
        comparer("actions", info["data"]["actions"], actions, 1e-6)
        comparer("montant", info["amount_max"], round(montant, 2), 0.01)
        nom = re.search(r"<rptOwnerName>\s*([^<]+?)\s*</rptOwnerName>", texte).group(1)
        if nom not in info["title"]:
            r["ecarts"].append(f"nom absent du titre : {nom}")
    elif info["source"] == "sec_13dg":
        pcts = [float(x) for x in re.findall(r"<(?:percentOfClass|classPercent)>\s*([\d.]+)\s*<", texte)]
        comparer("pourcentage", info["data"]["pourcentage"], max(pcts) if pcts else None, 1e-9)
    elif info["source"] == "sec_8k":
        descriptions = [d.strip().lower() for d in re.findall(r"ITEM INFORMATION:\s*([^\n<]+)", texte)]
        for item in info["data"]["items"]:
            if item["officiel"].lower() not in descriptions:
                r["ecarts"].append(f"item absent du document : {item['officiel']}")
    r["ok"] = r["meme_document"] and not r["ecarts"]
    return r


def main() -> None:
    infos = infos_publiees()
    random.seed(int(time.time()) // 86400)  # un nouvel échantillon chaque jour
    echantillon = random.sample(infos, min(TAILLE, len(infos)))
    resultats = []
    for info in echantillon:
        try:
            resultats.append(verifier(info))
        except Exception as exc:  # noqa: BLE001
            resultats.append({"id": info["id"], "titre": info["title"], "ok": False, "ecarts": [f"erreur : {exc}"]})
    ok = sum(1 for r in resultats if r["ok"])
    lignes = [f"# Audit de vérité : {ok}/{len(resultats)} infos identiques au document officiel", "",
              f"Infos publiées par le robot : {len(infos)} · échantillon au hasard : {len(resultats)}", ""]
    for r in resultats:
        etat = "OK" if r["ok"] else "ÉCART"
        lignes.append(f"- **{etat}** · {r['titre']}")
        if r.get("document"):
            lignes.append(f"  - document : {r['document']} · même document que le robot : {'oui' if r.get('meme_document') else 'NON'}")
        for e in r["ecarts"]:
            lignes.append(f"  - {e}")
    import pathlib

    sortie = pathlib.Path("labo/resultats")
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "verification.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    (sortie / "verification.json").write_text(json.dumps(resultats, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(lignes))


if __name__ == "__main__":
    main()
