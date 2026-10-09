// Photos de la 0.27.3 sur le VRAI site (étape 3, la note honnête) : Réglages (la version), l'Aide (« Radar bat-il le
// marché ? » en haut) et les Résultats (« Avant de lire : ce que le labo a mesuré » en tête), avec les vrais chiffres.
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const [dossier] = process.argv.slice(2);
  const base = process.argv[3] || "https://killingsky1.github.io/Radar/";  // 2e argument : essai local avant le vrai site
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const erreurs = [];
  p.on("pageerror", (e) => erreurs.push(String(e)));
  p.on("console", (m) => m.type() === "error" && erreurs.push(m.text()));
  let servi = false;
  for (let i = 0; i < 40 && !servi; i++) {
    servi = (await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text()).includes("0.27.3");
    if (!servi) await new Promise((ok) => setTimeout(ok, 15000));
  }
  dire(`Site : l'app 0.27.3 est servie : ${servi ? "OUI" : "NON"}`);
  let ok = servi;
  const groupe = async (nom, titre, attendus) => {
    const titres = await p.locator(".ecran").last().locator("h2.section").allInnerTexts();
    const h = p.locator("h2.section", { hasText: titre }).first();
    await h.evaluate((el) => { el.style.scrollMarginTop = "64px"; el.scrollIntoView({ block: "start" }); });
    await p.waitForTimeout(600);
    await p.screenshot({ path: `${dossier}/${nom}.png` });
    const texte = (await h.locator("xpath=..").innerText()).replace(/ | /g, " ");
    const premier = (titres[0] || "").toLowerCase() === titre.toLowerCase();
    const bon = premier && attendus.every((x) => texte.includes(x));
    ok = ok && bon;
    dire(`${nom} : 1er groupe « ${titres[0]} » · « ${texte.split("\n").join(" · ")} » · conforme : ${bon ? "OUI" : "NON"}`);
  };
  await p.goto(base); await p.waitForSelector("nav.onglets"); await p.waitForTimeout(800);
  await p.locator("nav.onglets button", { hasText: "Réglages" }).click(); await p.waitForTimeout(600);
  const ligneVersion = p.getByText(/Radar \d+\.\d+\.\d+ ·/).first();
  const reglages = (await ligneVersion.innerText()).split("\n")[0];
  await ligneVersion.evaluate((el) => el.scrollIntoView({ block: "center" })); await p.waitForTimeout(500);
  await p.screenshot({ path: `${dossier}/x1-reglages-version.png` });
  ok = ok && reglages.startsWith("Radar 0.27.3");
  dire(`Réglages : « ${reglages} » · conforme : ${reglages.startsWith("Radar 0.27.3") ? "OUI" : "NON"}`);
  const chiffres = ["−1,1 %, −3,5 % et +0,7 %", "39 à 50 % des compagnies", "aucune n'a battu le S&P 500 de façon fiable après les frais"];
  await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(500);
  await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape"); await p.waitForTimeout(500);
  await groupe("x2-aide-radar-bat-il-le-marche", "Radar bat-il le marché ?", ["Pas à coup sûr.", ...chiffres, "pas un signal d'achat"]);
  await p.goto(base); await p.waitForSelector("nav.onglets"); await p.waitForTimeout(600);
  await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(500);
  await p.locator(".res-carte").click(); await p.waitForTimeout(700);
  await groupe("x3-resultats-avant-de-lire", "Avant de lire : ce que le labo a mesuré", [...chiffres, "Les mesures en vrai ci-dessous diront si Radar fait mieux."]);
  dire(`Erreurs du navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  ok = ok && !erreurs.length;
  dire(`VERDICT : ${ok ? "OK" : "PROBLÈME"}`);
  fs.writeFileSync(`${dossier}/photos_0273.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
