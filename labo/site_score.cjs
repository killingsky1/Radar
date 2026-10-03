// Vérifie le VRAI site : le score servi = celui publié par le robot sur main ; l'app l'affiche ; photos format iPhone.
const { chromium } = require("playwright");
const fs = require("fs");

(async () => {
  const [fichierMain, dossier] = process.argv.slice(2);
  const local = fs.readFileSync(fichierMain, "utf8");
  const base = "https://killingsky1.github.io/Radar/";
  const b = await chromium.launch({ channel: "chrome" });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const erreurs = [];
  p.on("pageerror", (e) => erreurs.push(String(e)));
  p.on("console", (m) => m.type() === "error" && erreurs.push(m.text()));
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const photo = async (nom) => { await p.waitForTimeout(600); await p.screenshot({ path: `${dossier}/${nom}.png` }); };

  const r = await ctx.request.get(`${base}data/app/aujourdhui.json?x=${Date.now()}`);
  const servi = await r.text();
  const a = JSON.parse(servi);
  const pareil = servi === local;
  dire(`Fichier du score sur le site : HTTP ${r.status()} · identique à celui du robot sur main : ${pareil ? "OUI" : "NON"}`);
  dire(`Version ${a.version} · calculé le ${a.genere_a} · compagnies notées : ${a.compagnies_notees}`);
  dire(`Hausse (${a.hausse.length}) : ${a.hausse.map((x) => `${x.symbole} ${x.score}`).join(", ")}`);
  dire(`Baisse (${a.baisse.length}) : ${a.baisse.map((x) => `${x.symbole} ${x.score}`).join(", ")}`);
  const js = await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text();
  dire(`App en ligne : version 0.7.0 ${js.includes("0.7.0") ? "OUI" : "NON"}`);

  await p.goto(base);
  await p.waitForSelector(".tuiles");
  await photo("v1-accueil");
  const affiches = await p.locator(".ligne.suggestion .symbole").allInnerTexts();
  const attendus = a.hausse.slice(0, 5).map((x) => x.symbole);
  const memeTop = JSON.stringify(affiches) === JSON.stringify(attendus);
  dire(`Accueil : top 5 affiché ${affiches.join(", ")} · conforme au fichier : ${memeTop ? "OUI" : "NON"}`);
  await p.getByRole("button", { name: "Tout voir" }).first().click();
  await photo("v2-hausse");
  await p.locator(".ligne.suggestion").first().click();
  await photo("v3-fiche-1re");
  const titre = await p.locator(".grand-titre h1").innerText();
  dire(`Fiche ouverte : ${titre}`);
  await p.locator(".retour").click();
  await p.locator(".segment", { hasText: "Baisse" }).click();
  await photo("v4-baisse");
  await p.getByRole("button", { name: "Comment le score est calculé" }).click();
  await photo("v5-methode");
  const regles = await p.locator(".regle").count();
  dire(`Page de la méthode : ${regles} règles`);
  dire(`Erreurs du navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  const ok = pareil && memeTop && regles === a.methode.regles.length && !erreurs.length && js.includes("0.7.0");
  dire(ok ? "VERDICT : OK" : "VERDICT : PROBLÈME");
  fs.writeFileSync(`${dossier}/site.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
