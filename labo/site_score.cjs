// Vérifie le VRAI site : le score servi = celui publié par le robot sur main ; l'app l'affiche ; photos format iPhone.
const { chromium } = require("playwright");
const fs = require("fs");

(async () => {
  const [fichierMain, dossier, fichierElus] = process.argv.slice(2);
  const local = fs.readFileSync(fichierMain, "utf8");
  const elusLocal = fs.readFileSync(fichierElus, "utf8");
  const VERSION = "0.8.0";
  const base = process.env.BASE || "https://killingsky1.github.io/Radar/"; // BASE : essai local seulement
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const erreurs = [];
  p.on("pageerror", (e) => erreurs.push(String(e)));
  p.on("console", (m) => m.type() === "error" && erreurs.push(m.text()));
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const photo = async (nom) => { await p.waitForTimeout(600); await p.screenshot({ path: `${dossier}/${nom}.png` }); };

  // Attendre que GitHub Pages serve la nouvelle app (au plus 6 minutes).
  for (let i = 0; i < 24; i++) {
    const t = await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text();
    if (t.includes(VERSION)) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  // Attendre que le site serve le score publié par le robot sur main (au plus 6 minutes).
  let r, servi;
  for (let i = 0; i < 24; i++) {
    r = await ctx.request.get(`${base}data/app/aujourdhui.json?x=${Date.now()}`);
    servi = await r.text();
    if (servi === local) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  let elusServi = "";
  for (let i = 0; i < 12; i++) {
    elusServi = await (await ctx.request.get(`${base}data/app/elus.json?x=${Date.now()}`)).text();
    if (elusServi === elusLocal) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  const elusPareil = elusServi === elusLocal;
  const elus = JSON.parse(elusLocal);
  dire(`Fichier des élus sur le site : identique à celui du robot sur main : ${elusPareil ? "OUI" : "NON"} · ${Object.keys(elus.par_elu).length} élus reliés, ${elus.chefs.length} chefs`);
  const a = JSON.parse(servi);
  const pareil = servi === local;
  dire(`Fichier du score sur le site : HTTP ${r.status()} · identique à celui du robot sur main : ${pareil ? "OUI" : "NON"}`);
  dire(`Version ${a.version} · calculé le ${a.genere_a} · compagnies notées : ${a.compagnies_notees}`);
  dire(`Hausse (${a.hausse.length}) : ${a.hausse.map((x) => `${x.symbole} ${x.score}`).join(", ")}`);
  dire(`Baisse (${a.baisse.length}) : ${a.baisse.map((x) => `${x.symbole} ${x.score}`).join(", ")}`);
  const js = await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text();
  dire(`App en ligne : version ${VERSION} ${js.includes(VERSION) ? "OUI" : "NON"}`);

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
  await p.locator(".regle", { hasText: "Un chef du Congrès achète" }).scrollIntoViewIfNeeded();
  await p.evaluate(() => window.scrollBy(0, -120));
  await photo("v5b-methode-chefs");
  const regleChef = (await p.locator(".regle", { hasText: "Un chef du Congrès achète" }).innerText()).replace(/\u00a0/g, " ");
  dire(`Règle des chefs affichée : ${regleChef.split("\n").slice(0, 2).join(" · ")}`);

  // Fil Politiciens : la carte H.R. 7008
  await p.locator("nav.onglets button", { hasText: "Fil" }).click();
  await p.locator(".puce", { hasText: "Politiciens" }).click();
  await photo("v6-politiciens");
  const carte = await p.locator(".carte-projet").innerText();
  const etape = elus.projet.etape.charAt(0).toUpperCase() + elus.projet.etape.slice(1);
  const carteOk = carte.includes(etape) && (await p.locator(".carte-projet-vote").count()) === elus.projet.votes.length;
  dire(`Carte H.R. 7008 : « ${etape} » · ${elus.projet.votes.length} votes · conforme : ${carteOk ? "OUI" : "NON"}`);

  // Une transaction d'élu : la section « Au Congrès »
  await p.locator(".ligne", { hasText: / achète | vend / }).first().click();
  await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
  let congresOk = false;
  if (await p.locator(".congres").count()) {
    // Le titre « Au Congrès » en haut de l'écran : on voit le rôle, les comités et les votes
    await p.locator(".congres").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v7-elu-au-congres");
    const source = await p.locator(".congres-source").innerText();
    const entree = Object.values(elus.par_elu).find((x) => source.startsWith(x.nom_officiel + " ·"));
    const comites = await p.locator(".congres .transaction").count();
    const votes = await p.locator(".votes-elu .transaction").count();
    const chef = await p.locator(".congres-chef").innerText();
    congresOk = !!entree && comites === entree.comites.length && votes === entree.votes_hr7008.length && (entree.chef ? chef.includes("Chef du Congrès") : chef === "Pas un des 12 chefs du Congrès.");
    dire(`Au Congrès (${entree ? entree.nom_officiel : "?"}) : ${comites} comités, ${votes} votes, « ${chef} » · conforme : ${congresOk ? "OUI" : "NON"}`);
  } else dire("Au Congrès : section absente");
  await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  const ligneVote = p.locator(".ligne", { hasText: "le Sénat rejette la clôture" });
  if (await ligneVote.count()) {
    await ligneVote.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v8-vote-senat");
    dire(`Vote du Sénat : ${await p.locator(".feuille .controle.rate").count()} contrôle(s) raté(s)`);
  }
  dire(`Erreurs du navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  const ok = pareil && elusPareil && memeTop && regles === a.methode.regles.length && carteOk && congresOk && !erreurs.length && js.includes(VERSION);
  dire(ok ? "VERDICT : OK" : "VERDICT : PROBLÈME");
  fs.writeFileSync(`${dossier}/site.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
