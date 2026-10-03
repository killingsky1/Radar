// Vérifie le VRAI site : le score servi = celui publié par le robot sur main ; l'app l'affiche ; photos format iPhone.
const { chromium } = require("playwright");
const fs = require("fs");

(async () => {
  const [fichierMain, dossier, fichierElus, fichierLobbying] = process.argv.slice(2);
  const local = fs.readFileSync(fichierMain, "utf8");
  const elusLocal = fs.readFileSync(fichierElus, "utf8");
  const lobbyingLocal = fs.readFileSync(fichierLobbying, "utf8");
  const lobbying = JSON.parse(lobbyingLocal);
  const VERSION = "0.12.0";
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
  let lobbyingServi = "";
  for (let i = 0; i < 12; i++) {
    lobbyingServi = await (await ctx.request.get(`${base}data/app/lobbying.json?x=${Date.now()}`)).text();
    if (lobbyingServi === lobbyingLocal) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  const lobbyingPareil = lobbyingServi === lobbyingLocal;
  dire(`Fichier du lobbying sur le site : identique à celui du robot sur main : ${lobbyingPareil ? "OUI" : "NON"} · ${Object.keys(lobbying.par_symbole).length} compagnies · ${lobbying.trimestre.libelle}`);
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
  // Le lobbying de cette compagnie, comme dans lobbying.json
  let lobbyingOk = false;
  const entree = lobbying.par_symbole[titre];
  if (await p.locator(".lobbying").count()) {
    await p.locator(".lobbying").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v9-fiche-lobbying");
    const texte = (await p.locator(".lobbying").innerText()).replace(/\u00a0|\u202f/g, " ");
    const pied = await p.locator(".congres-source").last().innerText();
    const attendu = !entree ? "Pas encore lu" : !entree.complet ? "Recherche trop large" : entree.total == null
      ? "Aucun rapport de lobbying au nom exact" : entree.base === "compagnie" ? "Dépenses déclarées par la compagnie" : "Payés à";
    lobbyingOk = texte.includes(attendu) && pied.includes("Senate Office of Public Records cannot vouch");
    dire(`Lobbying sur la fiche ${titre} : « ${texte.split("\n")[0]} » · conforme : ${lobbyingOk ? "OUI" : "NON"}`);
  } else dire("Lobbying : section absente de la fiche");
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
  // Un rapport 278-T de l'OGE : mention légale de l'OGE, aucun contrôle raté
  let ogeOk = false;
  const ligneOge = p.locator(".ligne", { hasText: "278-T" });
  if (await ligneOge.count()) {
    await ligneOge.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v10-rapport-oge");
    const pied = await p.locator(".detail-pied").innerText();
    const rates = await p.locator(".feuille .controle.rate").count();
    ogeOk = pied.includes("Office of Government Ethics") && rates === 0;
    dire(`Rapport de l'OGE : « ${(await p.locator(".detail-titre").innerText()).slice(0, 90)} » · ${rates} contrôle(s) raté(s) · conforme : ${ogeOk ? "OUI" : "NON"}`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("Rapport de l'OGE : aucun dans le fil Politiciens");
  // Transactions du cabinet : un rapport lu (ses lignes) et une info de compagnie
  let cabinetOk = false;
  const ligneRapport = p.locator(".ligne", { hasText: /278-T\), \d+ transactions?/ });
  if (await ligneRapport.count()) {
    await ligneRapport.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreR = await p.locator(".detail-titre").innerText();
    const n = Number(titreR.match(/(\d+) transactions?$/)[1]);
    await p.locator(".lignes-oge").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v11-rapport-cabinet-lignes");
    const lues = await p.locator(".lignes-oge .ligne-oge").count();
    const ratesR = await p.locator(".feuille .controle.rate").count();
    dire(`Rapport du cabinet : « ${titreR.slice(0, 80)}… » · ${lues} lignes affichées pour ${n} annoncées · ${ratesR} contrôle(s) raté(s)`);
    cabinetOk = lues === n && ratesR === 0;
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("Rapport du cabinet : aucun dans le fil Politiciens");
  const ligneCie = p.locator(".ligne", { hasText: /niveau I+\) (vend|achète|échange) / });
  if (await ligneCie.count()) {
    await ligneCie.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v12-cabinet-compagnie");
    const titreC = await p.locator(".detail-titre").innerText();
    const lignesC = await p.locator(".lignes-oge .ligne-oge").count();
    const ratesC = await p.locator(".feuille .controle.rate").count();
    const pied = await p.locator(".detail-pied").innerText();
    dire(`Info de compagnie : « ${titreC} » · ${lignesC} ligne(s) · ${ratesC} contrôle(s) raté(s)`);
    cabinetOk = cabinetOk && lignesC >= 1 && ratesC === 0 && pied.includes("Office of Government Ethics");
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else { dire("Info de compagnie du cabinet : aucune dans le fil Politiciens"); cabinetOk = false; }
  dire(`Transactions du cabinet affichées : ${cabinetOk ? "OUI" : "NON"}`);
  const ligneVote = p.locator(".ligne", { hasText: "le Sénat rejette la clôture" });
  if (await ligneVote.count()) {
    await ligneVote.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v8-vote-senat");
    dire(`Vote du Sénat : ${await p.locator(".feuille .controle.rate").count()} contrôle(s) raté(s)`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  }
  // Canada (lot 3c, livraison 1) : une fiche de chaque source, l'encadré « Détails » et la mention exigée
  await p.locator("nav.onglets button", { hasText: "Fil" }).click();
  await p.locator(".puce", { hasText: "Canada" }).click();
  await photo("v13-fil-canada");
  const CANADA = [
    ["v14-gazette", "Gazette du Canada :", "Reproduction non officielle"],
    ["v15-concurrence", "Bureau de la concurrence :", "Contient de l'information visée par la Licence du gouvernement ouvert"],
    ["v16-grand-projet", "Projet d'intérêt national :", "Reproduction non officielle"],
    ["v17-statcan", "Statistique Canada :", "Source : Statistique Canada, Le Quotidien"],
    ["v18-legisinfo", "Projet de loi ", "Source : LEGISinfo, Parlement du Canada"],
    ["v19-sanctions", "Sanctions canadiennes", "Contient de l'information visée par la Licence du gouvernement ouvert"],
    // Lot 3c, livraison 2
    ["v20-sante-canada", "Santé Canada : nouveau médicament", "Contient de l'information visée par la Licence du gouvernement ouvert"],
    ["v21-ccc", "Corporation commerciale canadienne :", "Source : Corporation commerciale canadienne. Usage personnel et non commercial"],
  ];
  let canadaOk = true;
  for (const [nom, debut, mention] of CANADA) {
    const l = p.locator(".ligne", { hasText: debut });
    if (!(await l.count())) { dire(`Canada : aucune info « ${debut} » dans le fil`); canadaOk = false; continue; }
    await l.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreC = await p.locator(".detail-titre").innerText();
    const details = await p.locator(".details-officiels .detail-officiel").count();
    if (details) await p.locator(".details-officiels").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo(nom);
    const m = (await p.locator(".detail-pied .mention").count()) ? await p.locator(".detail-pied .mention").innerText() : "";
    const rates = await p.locator(".feuille .controle.rate").count();
    const bon = titreC.includes(debut.trim()) && details > 0 && m.startsWith(mention) && rates === 0;
    dire(`Canada : « ${titreC.slice(0, 95)} » · ${details} détails · mention « ${m.slice(0, 60)}… » · ${rates} contrôle(s) raté(s) · conforme : ${bon ? "OUI" : "NON"}`);
    canadaOk = canadaOk && bon;
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  }
  dire(`Fiches du Canada affichées : ${canadaOk ? "OUI" : "NON"}`);
  // CCC : chaque transaction du rapport est listée (autant de lignes que le nombre écrit dans le titre)
  let cccOk = false;
  const lc = p.locator(".ligne", { hasText: "Corporation commerciale canadienne :" });
  if (await lc.count()) {
    await lc.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreCcc = await p.locator(".detail-titre").innerText();
    const n = Number((titreCcc.match(/(\d+) transactions signées/) || [])[1]);
    const lignesCcc = await p.locator(".lignes-ccc .ligne-oge").count();
    if (lignesCcc) await p.locator(".lignes-ccc").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v22-ccc-transactions");
    const premiere = lignesCcc ? (await p.locator(".lignes-ccc .ligne-oge").first().innerText()).replace(/\s+/g, " ") : "";
    cccOk = n > 0 && lignesCcc === n;
    dire(`CCC : ${n} transactions dans le titre, ${lignesCcc} lignes listées · 1re : « ${premiere.slice(0, 110)} » · conforme : ${cccOk ? "OUI" : "NON"}`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("CCC : aucune info dans le fil");
  // Contrats fédéraux : 1re lecture silencieuse (aucune info), l'état de la source se voit dans l'écran Sources
  await p.locator("nav.onglets button", { hasText: "Accueil" }).click(); await p.waitForTimeout(400);
  await p.locator(".tuile", { hasText: "Sources actives" }).click(); await p.waitForTimeout(600);
  let sourcesOk = true;
  for (const nom of ["Santé Canada : nouveaux médicaments", "Contrats fédéraux de 10 M$ et plus", "Corporation commerciale canadienne : transactions"]) {
    const s = p.locator(".source", { hasText: nom });
    const etat = (await s.count()) ? await s.first().locator(".source-etat").innerText() : "absente";
    if (nom.startsWith("Contrats")) { await s.first().evaluate((el) => el.scrollIntoView({ block: "center" })); await photo("v23-sources-canada"); }
    dire(`Source « ${nom} » : ${etat}`);
    sourcesOk = sourcesOk && etat.startsWith("OK");
  }
  await p.locator(".ecran-retour, .retour").first().click().catch(() => {});
  dire(`Erreurs du navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  const ok = pareil && elusPareil && lobbyingPareil && memeTop && regles === a.methode.regles.length && carteOk && congresOk && lobbyingOk && ogeOk && cabinetOk && canadaOk && cccOk && sourcesOk && !erreurs.length && js.includes(VERSION);
  dire(ok ? "VERDICT : OK" : "VERDICT : PROBLÈME");
  fs.writeFileSync(`${dossier}/site.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
