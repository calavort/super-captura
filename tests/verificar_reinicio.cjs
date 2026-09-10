const {chromium} = require('playwright');
const [endpoint, folder, screenshot] = process.argv.slice(2);

(async () => {
    let browser;
    for (let attempt = 0; attempt < 50; attempt++) {
        try {
            browser = await chromium.connectOverCDP(endpoint);
            break;
        } catch {
            await new Promise(resolve => setTimeout(resolve, 200));
        }
    }
    if (!browser) throw new Error('O programa atualizado nao abriu o canal de validacao.');
    const pages = browser.contexts().flatMap(context => context.pages());
    const page = pages.find(page => decodeURI(page.url()).includes(folder.replaceAll('\\', '/')));
    if (!page) throw new Error('A pagina do aplicativo atualizado nao foi localizada.');
    await page.waitForFunction(() => typeof pyBridge !== 'undefined' && pyBridge &&
        typeof homeAnnotations !== 'undefined' && homeAnnotations.length === 1 && homeBgImage !== null);
    await page.waitForFunction(() => document.getElementById('update-status').textContent.includes('mais recente'));
    const state = await page.evaluate(() => ({
        version: document.getElementById('update-version').textContent,
        status: document.getElementById('update-status').textContent,
        text: homeAnnotations[0].text,
        imageWidth: homeBgImage.naturalWidth,
        editionImages: editionItems.length,
        user: document.getElementById('user-name').value,
    }));
    if (state.version !== 'Versao ' + process.argv[5] || state.text !== 'Teste de reinicio real' ||
        state.imageWidth !== 120 || state.editionImages !== 1 || state.user !== 'Teste local') {
        throw new Error('A recuperacao da atualizacao divergiu: ' + JSON.stringify(state));
    }
    await page.evaluate(() => document.querySelector('.ribbon-tab[onclick*="tab-config"]').click());
    await page.screenshot({path: screenshot});
    console.log(JSON.stringify(state));
    try {
        await page.evaluate(() => pyBridge.closeWindow());
    } catch (error) {
        if (!String(error).includes('closed')) throw error;
    }
})().then(() => process.exit(0)).catch(error => {
    console.error(error);
    process.exit(1);
});
