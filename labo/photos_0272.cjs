// Photos de la 0.27.2 sur le VRAI site (étape 2, prix du formulaire 4) : Réglages (la version), puis la taille en bourse
// des compagnies des listes qui ont le prix du formulaire 4, une raison « ni de prix de formulaire 4 utilisable », une
// note ou une raison de l'étape 2, et une fiche avec le prix de la SEC. Chaque fiche est comparée au fichier publié par le
// robot (aujourdhui.json de main), espaces ignorés ; le site doit servir ce même fichier (même heure de calcul).
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const [fichierMain, dossier, depuis] = process.argv.slice(2);  // depuis : début du passage du robot 0.27.2 (ISO)
  const a = JSON.parse(fs.readFileSync(fichierMain, "utf8"));
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const sans = (t) => (t || "").replace(/\s/g, "");
  const base = process.argv[5] || "https://killingsky1.github.io/Radar/";  // 4e argument : essai local avant le vrai site
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const erreurs = [];
  p.on("pageerror", (e) => erreurs.push(String(e)));
  p.on("console", (m) => m.type() === "error" && erreurs.push(m.text()));
  const photo = async (nom) => { await p.waitForTimeout(600); await p.screenshot({ path: `${dossier}/${nom}.png` }); };
  // Le site sert l'app 0.27.2 ET le fichier du robot de main (même heure de calcul) ; on attend jusqu'à 10 minutes
  let servi = false, memes = false;
  for (let i = 0; i < 40 && !(servi && memes); i++) {
    servi = (await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text()).includes("0.27.2");
    const enLigne = JSON.parse(await (await ctx.request.get(`${base}data/app/aujourdhui.json?x=${Date.now()}`)).text());
    memes = enLigne.genere_a === a.genere_a;
    if (!(servi && memes)) await new Promise((ok) => setTimeout(ok, 15000));
  }
  dire(`Site : l'app 0.27.2 est servie : ${servi ? "OUI" : "NON"} · le fichier du score en ligne est celui de main (calculé le ${a.genere_a}) : ${memes ? "OUI" : "NON"}`);
  const apres = !depuis || a.genere_a >= depuis;
  dire(`Le fichier du score a été calculé après le début du passage du robot 0.27.2 (${depuis || "-"}) : ${apres ? "OUI" : "NON"}`);
  let ok = servi && memes && apres;
  await p.goto(base); await p.waitForSelector("nav.onglets"); await p.waitForTimeout(800);
  await p.locator("nav.onglets button", { hasText: "Réglages" }).click(); await p.waitForTimeout(600);
  const ligneVersion = p.getByText(/Radar \d+\.\d+\.\d+ ·/).first();
  const reglages = (await ligneVersion.innerText()).split("\n")[0];
  await ligneVersion.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await photo("x1-reglages-version");
  ok = ok && reglages.startsWith("Radar 0.27.2");
  dire(`Réglages : « ${reglages} » · conforme : ${reglages.startsWith("Radar 0.27.2") ? "OUI" : "NON"}`);

  const toutes = [...(a.hausse || []).map((r) => ["Hausse", r]), ...(a.ecartees || []).map((r) => ["Hausse", r]),
    ...(a.baisse || []).map((r) => ["Baisse", r])];
  const t_ = (r) => r.taille || {};
  const f4 = toutes.filter(([, r]) => t_(r).source_prix === "formulaire 4");
  const sansPrix = toutes.filter(([, r]) => /ni de prix de formulaire 4 utilisable/.test(t_(r).raison || ""));
  const ancienne = toutes.filter(([, r]) => (t_(r).raison || "") === "pas de prix de la SEC depuis 60 jours");
  const etape2 = toutes.filter(([, r]) => /formulaire 4 \(|prix du formulaire 4 du|Titre absent des fichiers/.test(`${t_(r).raison || ""} ${t_(r).note || ""}`));
  const pasVerifie = toutes.filter(([, r]) => /pas encore vérifié/.test(t_(r).note || ""));
  const normale = toutes.find(([, r]) => t_(r).taille && !t_(r).note && t_(r).source_prix !== "formulaire 4");
  dire(`Fichier du robot : ${toutes.length} compagnies dans les listes ; prix du formulaire 4 : ${f4.length} ; « ni de prix de formulaire 4 ` +
       `utilisable » : ${sansPrix.length} ; ancienne raison de la 0.27.1 : ${ancienne.length} (0 attendu) ; autres notes ou raisons ` +
       `de l'étape 2 : ${etape2.filter(([, r]) => !f4.some(([, x]) => x === r)).length} ; « pas encore vérifié » : ${pasVerifie.length} (0 attendu)`);
  ok = ok && ancienne.length === 0 && pasVerifie.length === 0;
  const vus = new Set();
  const aVoir = [];
  for (const groupe of [f4.slice(0, 4), sansPrix.slice(0, 2), etape2.slice(0, 3), normale ? [normale] : []])
    for (const x of groupe) if (!vus.has(x[1].symbole)) { vus.add(x[1].symbole); aVoir.push(x); }
  let n = 1;
  for (const [segment, r] of aVoir) {
    n += 1;
    await p.goto(base); await p.waitForSelector("nav.onglets"); await p.waitForTimeout(600);
    // l'app rouvre le dernier onglet : revenir à l'onglet Radar d'abord
    await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(500);
    await p.getByRole("button", { name: "Tout voir" }).first().click(); await p.waitForTimeout(500);
    await p.locator(".segment", { hasText: segment }).click(); await p.waitForTimeout(300);
    // le symbole est dans <span class="symbole"> : texte exact
    const exact = new RegExp(`^${r.symbole.replace(/[.*+?^${}()|[\]\\-]/g, "\\$&")}$`);
    await p.locator(".ligne.suggestion").filter({ has: p.locator(".symbole", { hasText: exact }) }).first().click();
    await p.waitForTimeout(700);
    const carte = p.locator(".taille");
    await carte.evaluate((el) => { el.previousElementSibling.style.scrollMarginTop = "64px"; el.previousElementSibling.scrollIntoView({ block: "start" }); });
    await photo(`x${n}-fiche-${r.symbole}-taille`);
    const texte = await carte.innerText();
    const source = await p.locator(".taille-source").innerText();
    const t = r.taille;
    const estF4 = t.source_prix === "formulaire 4";
    const attendus = [t.note, t.raison, estF4 ? "prix moyen des dirigeants en bourse le" : null,
      estF4 ? "formulaire 4 : la SEC n'a pas de prix depuis 60 jours" : null, !estF4 && t.taille ? "prix de la SEC du" : null].filter(Boolean);
    const bon = attendus.every((x) => sans(texte).includes(sans(x))) && (estF4 ? source.includes("formulaire 4 déposé à la SEC") : !source.includes("formulaire 4"));
    ok = ok && bon;
    dire(`Fiche ${r.symbole} (${segment}) : « ${texte.split("\n").join(" · ").slice(0, 300)} » · fichier : taille ${t.taille}, ` +
         `${t.valeur_m ?? "-"} M$${estF4 ? ", prix du formulaire 4" : ""} · conforme : ${bon ? "OUI" : "NON"}`);
  }
  dire(`Erreurs du navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  ok = ok && !erreurs.length;
  dire(`VERDICT : ${ok ? "OK" : "PROBLÈME"}`);
  fs.writeFileSync(`${dossier}/photos_0272.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
