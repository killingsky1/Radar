// Photos de la 0.26.1 sur le VRAI site : la fiche d'ASPI (actions du 14 août, dossier companyconcept de la SEC) et la
// source du Trésor (« OK » : 21 jours sans publication avant « en pause »). Chaque photo est vérifiée au fichier du robot.
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const [fichierMain, dossier] = process.argv.slice(2);
  const a = JSON.parse(fs.readFileSync(fichierMain, "utf8"));
  const sources = JSON.parse(fs.readFileSync(fichierMain.replace("aujourdhui.json", "sources.json"), "utf8"));
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const base = "https://killingsky1.github.io/Radar/";
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const photo = async (nom) => { await p.waitForTimeout(600); await p.screenshot({ path: `${dossier}/${nom}.png` }); };
  for (let i = 0; i < 24; i++) {
    const t = await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text();
    if (t.includes("0.26.1")) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  await p.goto(base); await p.waitForSelector(".tuiles"); await p.waitForTimeout(800);
  let ok = true;
  // 1. La fiche d'ASPI : taille avec les actions les plus récentes
  const x = [...a.hausse, ...a.baisse].find((r) => r.symbole === "ASPI");
  if (!x) { dire("ASPI n'est plus dans les listes : pas de photo de sa fiche"); }
  else {
    await p.getByRole("button", { name: "Tout voir" }).first().click(); await p.waitForTimeout(400);
    if (a.baisse.some((r) => r.symbole === "ASPI")) await p.locator(".segment", { hasText: "Baisse" }).click();
    await p.locator(".ligne.suggestion", { hasText: "ASPI" }).first().click(); await p.waitForTimeout(600);
    await p.locator(".taille").evaluate((el) => { el.previousElementSibling.style.scrollMarginTop = "64px"; el.previousElementSibling.scrollIntoView({ block: "start" }); });
    await photo("w1-fiche-aspi-taille");
    const t = (await p.locator(".taille").innerText()).replace(/ | /g, " ");
    const attendu = `${Math.round(x.taille.actions[0]).toLocaleString("fr-CA").replace(/ | /g, " ")} actions déclarées`;
    const bon = t.includes(attendu) && x.taille.source_actions === "companyconcept";
    ok = ok && bon;
    dire(`Fiche ASPI : « ${t.split("\n").join(" · ").slice(0, 220)} » · fichier : ${x.taille.actions} (${x.taille.source_actions}) · conforme : ${bon ? "OUI" : "NON"}`);
    await p.locator(".retour").click(); await p.waitForTimeout(300); await p.locator(".retour").click(); await p.waitForTimeout(300);
  }
  // 2. La source du Trésor, telle que publiée par le robot
  await p.locator(".tuile", { hasText: "Sources actives" }).click(); await p.waitForTimeout(700);
  const s = p.locator(".source", { hasText: "Trésor américain : adjudications" });
  await s.first().evaluate((el) => el.scrollIntoView({ block: "center" }));
  await photo("w2-source-tresor");
  const etat = await s.first().locator(".source-etat").innerText();
  const publie = sources.find((q) => q.id === "tresor");
  const bonT = etat.startsWith(publie.libelle) && publie.statut === "ok";
  ok = ok && bonT;
  dire(`Source du Trésor : « ${etat} » · fichier du robot : ${publie.statut} ${publie.libelle} · conforme : ${bonT ? "OUI" : "NON"}`);
  dire(`VERDICT : ${ok ? "OK" : "PROBLÈME"}`);
  fs.writeFileSync(`${dossier}/photos_0261.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
