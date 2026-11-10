// Validate the actual atlas in a separate headless browser; no host input.
const { chromium } = require('playwright');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
  const [atlas, fixtures, output] = process.argv.slice(2).map(p => path.resolve(p));
  const browser = await chromium.launch({channel:'msedge',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1080}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(atlas).href + '#sphud');
    await page.waitForFunction(() => window.__atlas?.audioSources?.size === 3);
    const read = source => page.evaluate(source => Array.from(window.__atlas.playbackPeaks(source,40)),source);
    assert.equal(Math.max(...await read('radio')),0);
    await page.locator('input[aria-label="Incoming transmission"]').setInputFiles(path.join(fixtures,'pattern.wav'));
    await page.waitForFunction(() => window.__atlas.audioSources.get('radio').peaks);
    await page.evaluate(async () => {
      const audio = window.__atlas.audioSources.get('radio').media;
      audio.currentTime = 1.25;
      await audio.play(); audio.pause();
    });
    const speech = await read('radio');
    assert(Math.max(...speech) > .39 && Math.max(...speech) < .41 && Math.min(...speech) === 0);
    assert.equal(Math.max(...await read('voice:Kaz')),0, 'sources must be independent');
    await page.waitForTimeout(180);
    assert.deepEqual(await read('radio'),speech,'pause must hold the cursor');
    await page.evaluate(() => { window.__atlas.audioSources.get('radio').media.currentTime = .6; });
    assert.equal(Math.max(...await read('radio')),0,'seeking back into silence must clear the trace');
    await page.locator('input[aria-label="Received voice · Kaz"]').setInputFiles(path.join(fixtures,'tone.wav'));
    await page.waitForFunction(() => window.__atlas.audioSources.get('voice:Kaz').peaks);
    await page.evaluate(async () => {
      const audio = window.__atlas.audioSources.get('voice:Kaz').media;
      audio.currentTime=.4; await audio.play(); audio.pause();
      document.getElementById('radioVoice').click();
      document.getElementById('mpVoice').click();
    });
    assert(Math.max(...await read('voice:Kaz'))>.59);
    assert.equal(Math.max(...await read('voice:self')),0);
    assert.equal(Math.max(...await read('radio')),0);
    assert(await page.locator('[data-audio-source="voice:Kaz"]').count() > 0);
    const radio = page.locator('#radioAnat');
    await radio.scrollIntoViewIfNeeded();
    await radio.screenshot({path:path.join(output,'atlas-radio.png')});
    const sources = await page.locator('[data-audio-source]').evaluateAll(nodes => [...new Set(nodes.map(n=>n.dataset.audioSource))]);
    assert(errors.length===0,errors.join('\n'));
    fs.writeFileSync(path.join(output,'atlas-report.json'),JSON.stringify({passed:true,sources,errors,checks:['decoded PCM','silence','independent talkers','pause','seek','actual SVG graphs']},null,2)+'\n');
    console.log('Atlas playback graphs: passed');
  } finally { await browser.close(); }
})().catch(error => { console.error(error);process.exitCode=1; });
