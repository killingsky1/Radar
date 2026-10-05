// Photo du graphique à la largeur d'un iPhone (390 px, écran ×3)
const { chromium } = require('playwright');
(async () => {
  const [entree, sortie] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 800 }, deviceScaleFactor: 3, colorScheme: 'light' });
  await p.goto('file://' + entree);
  const largeur = await p.evaluate(() => document.documentElement.scrollWidth);
  if (largeur > 390) throw new Error('défilement horizontal : ' + largeur);
  await p.screenshot({ path: sortie, fullPage: true });
  await b.close();
  console.log('photo', sortie, 'largeur', largeur);
})();
