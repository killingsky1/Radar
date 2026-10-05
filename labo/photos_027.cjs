// Photos de la 0.27.0 (lot M) : les compagnies écartées (moins de 100 M$) sous la liste « hausse », la fiche d'une
// écartée, la règle dans « Comment le score est calculé » et le suivi des écartées dans les Résultats. Chaque photo est
// vérifiée aux fichiers publiés par le robot (aujourdhui.json, resultats.json), puis réunie sur une planche.
// Usage : node photos_027.cjs <adresse du site> <dossier data/app> <dossier des photos> [version attendue]
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const [base, app, dossier, version] = process.argv.slice(2);
  const a = JSON.parse(fs.readFileSync(`${app}/aujourdhui.json`, "utf8"));
  const r = JSON.parse(fs.readFileSync(`${app}/resultats.json`, "utf8"));
  fs.mkdirSync(dossier, { recursive: true });
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const photos = [];
  const photo = async (nom, legende) => { await p.waitForTimeout(600); await p.screenshot({ path: `${dossier}/${nom}.png` }); photos.push([nom, legende]); };
  const net = (t) => t.replace(/ | /g, " ");
  if (version) {
    for (let i = 0; i < 24; i++) {
      const t = await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text();
      if (t.includes(`"${version}"`)) break;
      await new Promise((ok) => setTimeout(ok, 15000));
    }
  }
  await p.goto(base); await p.evaluate(() => localStorage.clear()); await p.reload();
  await p.waitForSelector(".tuiles"); await p.waitForTimeout(800);
  let ok = true;
  const verifier = (nom, bon, detail) => { ok = ok && bon; dire(`${nom} : ${detail} · conforme : ${bon ? "OUI" : "NON"}`); };
  if (version) {
    await p.locator("nav.onglets button", { hasText: "Réglages" }).click(); await p.waitForTimeout(300);
    const t = await p.locator(".ecran").innerText();
    verifier("Version", t.includes(`Radar ${version}`), `« ${(t.match(/Radar \d+\.\d+\.\d+[^\n]*/) || ["?"])[0]} »`);
    await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(300);
  }
  // 1. Suggestions : la liste « hausse », puis les écartées
  await p.getByRole("button", { name: "Tout voir" }).first().click(); await p.waitForTimeout(400);
  await p.locator(".segment", { hasText: "Hausse" }).click(); await p.waitForTimeout(300);
  const listes = p.locator(".carte.liste");
  const hausse = await listes.nth(0).locator(".symbole").allTextContents();
  verifier("Liste « hausse »", JSON.stringify(hausse) === JSON.stringify(a.hausse.map((x) => x.symbole)),
    `${hausse.length} à l'écran · fichier : ${a.hausse.length} (${hausse.join(", ")})`);
  if (!a.ecartees?.length) {
    dire("Aucune compagnie écartée au dernier calcul : pas de photo des écartées");
  } else {
    const titre = p.locator("h2.section", { hasText: "Écartées" });
    await titre.evaluate((el) => { el.style.scrollMarginTop = "64px"; el.scrollIntoView({ block: "start" }); });
    await photo("m1-ecartees", "Sous la liste « hausse » : les écartées (moins de 100 M$), avec la raison");
    const ecartees = await listes.nth(1).locator(".symbole").allTextContents();
    verifier("Écartées", JSON.stringify(ecartees) === JSON.stringify(a.ecartees.map((x) => x.symbole))
      && a.ecartees.every((x) => x.taille.valeur_m < 100) && a.hausse.every((x) => !(x.taille?.valeur_m < 100)),
      `${ecartees.join(", ")} · valeurs du fichier : ${a.ecartees.map((x) => `${x.symbole} ${x.taille.valeur_m} M$`).join(", ")}`);
    // 2. La fiche de la première écartée
    const x = a.ecartees[0];
    await listes.nth(1).locator(".ligne.suggestion").first().click(); await p.waitForTimeout(700);
    await photo("m2-fiche-ecartee", `Fiche de ${x.symbole} : écartée, avec sa note et ses preuves`);
    const sens = await p.locator(".fiche-sens").innerText();
    await p.locator(".taille").evaluate((el) => { el.previousElementSibling.style.scrollMarginTop = "64px"; el.previousElementSibling.scrollIntoView({ block: "start" }); });
    await photo("m3-taille-ecartee", `Taille de ${x.symbole} : ${x.taille.valeur_m} M$, moins de 100 M$`);
    const t = net(await p.locator(".taille").innerText());
    verifier(`Fiche ${x.symbole}`, sens.startsWith("Écartée : moins de 100 M$ en bourse") && t.includes("Moins de 100 M$ : hors de la liste « hausse »."),
      `« ${sens.split("\n")[0]} » · « ${t.split("\n").join(" · ").slice(0, 160)} »`);
    await p.locator(".retour").click(); await p.waitForTimeout(300);
  }
  await p.locator(".retour").click(); await p.waitForTimeout(300);
  // 3. La règle dans « Comment le score est calculé »
  await p.locator("nav.onglets button", { hasText: "Réglages" }).click(); await p.waitForTimeout(300);
  await p.getByRole("button", { name: /Comment le score est calculé/ }).click(); await p.waitForTimeout(400);
  const regle = p.locator(".rangee", { hasText: "Moins de 100 M$ en bourse : la compagnie n'entre pas" });
  await regle.evaluate((el) => { el.style.scrollMarginTop = "120px"; el.scrollIntoView({ block: "start" }); });
  await photo("m4-methode", "« Comment le score est calculé » : la règle des 100 M$ et le lien du rejeu du labo");
  const lien = await p.locator("a.etude", { hasText: "Rejeu de 3 ans du labo" }).getAttribute("href");
  verifier("Méthode", net(await regle.innerText()) === a.methode.trop_petites && lien === a.methode.lien_labo, `lien : ${lien}`);
  await p.locator(".retour").click(); await p.waitForTimeout(300);
  // 4. Les Résultats : les écartées suivies à part
  await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(300);
  await p.locator(".res-carte").click(); await p.waitForTimeout(500);
  if (!r.resume.ecartee_7) {
    dire("Résultats : pas encore de résumé des écartées (robot d'avant la 0.27)");
  } else {
    const g = p.locator(".groupe", { hasText: "la règle des 100 M$ a-t-elle raison" });
    await g.evaluate((el) => { el.style.scrollMarginTop = "64px"; el.scrollIntoView({ block: "start" }); });
    await photo("m5-resultats-ecartees", "Résultats : les écartées suivies à part (la règle a-t-elle raison ?)");
    const n = r.lignes.filter((l) => l.sens === "ecartee").length;
    const titre = n ? await p.locator("h2.section", { hasText: "Écartées suivies" }).textContent() : "";
    verifier("Résultats", !n || titre === `Écartées suivies (${n})`, `${n} écartée(s) suivie(s) dans le fichier · à l'écran : « ${titre} »`);
  }
  // Planche
  const images = photos.map(([nom, legende]) => `<figure><img src="data:image/png;base64,${fs.readFileSync(`${dossier}/${nom}.png`).toString("base64")}"><figcaption>${legende}</figcaption></figure>`).join("");
  const q = await ctx.newPage();
  await q.setViewportSize({ width: 390 * photos.length + 24 * (photos.length + 1), height: 900 });
  await q.setContent(`<html><body style="margin:0;background:#0b0b0b;font:15px system-ui;color:#e8e6e1"><div style="display:flex;gap:24px;padding:24px">${images}</div></body></html>`
    .replace(/<figure>/g, '<figure style="margin:0;width:390px">').replace(/<img /g, '<img style="width:390px;border-radius:14px;display:block" ')
    .replace(/<figcaption>/g, '<figcaption style="margin-top:10px;line-height:1.35">'));
  await q.waitForTimeout(300);
  await q.screenshot({ path: `${dossier}/radar-0.27-photos.png`, fullPage: true });
  dire(`VERDICT : ${ok ? "OK" : "PROBLÈME"}`);
  fs.writeFileSync(`${dossier}/photos_027.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
