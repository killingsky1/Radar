// Photos de la 0.27.1 sur le VRAI site (étape 1, données sûres) : Réglages (la version), puis la taille en bourse des
// compagnies des listes qui ont une note ou une raison sur le code du titre (CUSIP), et une fiche sans note. Chaque fiche
// est comparée au fichier publié par le robot (aujourdhui.json), espaces ignorés.
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const [fichierMain, dossier] = process.argv.slice(2);
  const a = JSON.parse(fs.readFileSync(fichierMain, "utf8"));
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const sans = (t) => (t || "").replace(/\s/g, "");
  const base = process.argv[4] || "https://killingsky1.github.io/Radar/";  // 3e argument : essai local avant le vrai site
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const erreurs = [];
  p.on("pageerror", (e) => erreurs.push(String(e)));
  const photo = async (nom) => { await p.waitForTimeout(600); await p.screenshot({ path: `${dossier}/${nom}.png` }); };
  let servi = false;
  for (let i = 0; i < 40 && !servi; i++) {
    servi = (await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text()).includes("0.27.1");
    if (!servi) await new Promise((ok) => setTimeout(ok, 15000));
  }
  dire(`Site : l'app 0.27.1 est servie : ${servi ? "OUI" : "NON"}`);
  let ok = servi;
  await p.goto(base); await p.waitForSelector("nav.onglets"); await p.waitForTimeout(800);
  await p.locator("nav.onglets button", { hasText: "Réglages" }).click(); await p.waitForTimeout(600);
  const reglages = ((await p.locator(".ecran").last().innerText()).match(/Radar \d+\.\d+\.\d+[^\n]*/) || [""])[0];
  const ligneVersion = p.getByText(/Radar \d+\.\d+\.\d+ ·/).first();  // la ligne est en bas de Réglages : la montrer
  if (await ligneVersion.count()) await ligneVersion.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await photo("x1-reglages-version");
  ok = ok && reglages.startsWith("Radar 0.27.1");
  dire(`Réglages : « ${reglages} » · conforme : ${reglages.startsWith("Radar 0.27.1") ? "OUI" : "NON"}`);

  const toutes = [...(a.hausse || []).map((r) => ["Hausse", r]), ...(a.ecartees || []).map((r) => ["Hausse", r]),
    ...(a.baisse || []).map((r) => ["Baisse", r])];
  const cusip = toutes.filter(([, r]) => /CUSIP/.test(`${(r.taille || {}).note || ""} ${(r.taille || {}).raison || ""}`));
  const pasVerifie = toutes.filter(([, r]) => /pas encore vérifié/.test((r.taille || {}).note || ""));
  const normale = toutes.find(([, r]) => r.taille && r.taille.taille && !r.taille.note);
  dire(`Fichier du robot : ${toutes.length} compagnies dans les listes ; ${cusip.length} avec une note ou une raison sur le code du titre ; ` +
       `${pasVerifie.length} « pas encore vérifié » (0 attendu : l'historique est lu)`);
  ok = ok && pasVerifie.length === 0;
  const aVoir = [...cusip.filter(([, r]) => !pasVerifie.includes(r)).slice(0, 6), ...(normale ? [normale] : [])];
  let n = 1;
  for (const [segment, r] of aVoir) {
    n += 1;
    await p.goto(base); await p.waitForSelector("nav.onglets"); await p.waitForTimeout(600);
    // l'app rouvre le dernier onglet (Réglages, vu plus haut) : revenir à l'onglet Radar d'abord
    await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(500);
    await p.getByRole("button", { name: "Tout voir" }).first().click(); await p.waitForTimeout(500);
    await p.locator(".segment", { hasText: segment }).click(); await p.waitForTimeout(300);
    // le symbole est dans <span class="symbole"> : texte exact (le texte de la ligne colle tout : « 9,3GMEGameStop »)
    const exact = new RegExp(`^${r.symbole.replace(/[.*+?^${}()|[\]\\-]/g, "\\$&")}$`);
    await p.locator(".ligne.suggestion").filter({ has: p.locator(".symbole", { hasText: exact }) }).first().click();
    await p.waitForTimeout(700);
    const carte = p.locator(".taille");
    await carte.evaluate((el) => { el.previousElementSibling.style.scrollMarginTop = "64px"; el.previousElementSibling.scrollIntoView({ block: "start" }); });
    await photo(`x${n}-fiche-${r.symbole}-taille`);
    const texte = await carte.innerText();
    const t = r.taille;
    const attendus = [t.note, t.raison, t.valeur_max ? "au plus" : null].filter(Boolean);
    const bon = attendus.every((x) => sans(texte).includes(sans(x))) && (t.note || t.raison ? true : !/CUSIP/.test(texte));
    ok = ok && bon;
    dire(`Fiche ${r.symbole} (${segment}) : « ${texte.split("\n").join(" · ").slice(0, 260)} » · fichier : taille ${t.taille}, ` +
         `${t.valeur_m ?? "-"} M$${t.valeur_max ? " (maximum)" : ""}${t.valeur_min_m != null ? ` (dès ${t.valeur_min_m})` : ""} · conforme : ${bon ? "OUI" : "NON"}`);
  }
  dire(`Erreurs du navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  ok = ok && !erreurs.length;
  dire(`VERDICT : ${ok ? "OK" : "PROBLÈME"}`);
  fs.writeFileSync(`${dossier}/photos_0271.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
