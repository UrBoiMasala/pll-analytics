import {test,before,after} from 'node:test';import assert from 'node:assert/strict';import {readFile,mkdir} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.FRONTEND_URL||'http://127.0.0.1:4173';let browser,page;const errors=[];
const datasets={};for(const y of [2022,2023,2024,2025,2026])datasets[y]=JSON.parse(await readFile(new URL(`../dist/data/${y}.json`,import.meta.url)));
before(async()=>{browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));});
after(async()=>{await browser?.close();});
async function go(hash=''){await page.goto(origin+'/'+hash);await page.waitForSelector('tbody tr');}
async function tab(name){await page.getByRole('link',{name,exact:true}).click();await page.waitForTimeout(70);}
test('default landing, partial indicator and dense data above fold',async()=>{await go();assert.equal(await page.locator('#season').inputValue(),'2026');assert.equal(await page.locator('.partial').innerText(),'');assert.equal(await page.locator('tbody tr').count(),datasets[2026].players.filter(p=>p.level==='SEASON').length);assert.ok((await page.locator('tbody tr').first().boundingBox()).y<360);await mkdir(new URL('../test-results/',import.meta.url),{recursive:true});await page.screenshot({path:new URL('../test-results/desktop.png',import.meta.url).pathname});});
test('switches all five seasons and partial marker',async()=>{for(const y of [2022,2023,2024,2025,2026]){await page.locator('#season').selectOption(String(y));await page.waitForTimeout(70);assert.equal(await page.locator('tbody tr').count(),datasets[y].players.filter(p=>p.level==='SEASON').length);assert.equal(await page.locator('.partial').innerText(),'');}});
test('team, position and search filters',async()=>{await go();await page.locator('#team').selectOption('CAN');await page.locator('#position').selectOption('A');await page.locator('#search').fill('Holman');await page.waitForTimeout(80);assert.equal(await page.locator('tbody tr').count(),1);assert.equal(await page.locator('tbody tr').getAttribute('data-team'),'CAN');assert.equal(await page.locator('tbody tr').getAttribute('data-level'),'STINT');assert.match(await page.locator('tbody tr').innerText(),/Marcus Holman/);});
test('sort changes direction and displayed order',async()=>{await go();await page.getByRole('button',{name:'PTS ↕',exact:true}).count();await page.locator('button[data-sort="points"]').click();await page.waitForTimeout(70);const pts=await page.locator('td[data-key="points"]').allTextContents();assert.ok(Number(pts[0])<=Number(pts.at(-1)));assert.equal(await page.locator('th[aria-sort="ascending"] button').getAttribute('data-sort'),'points');});
test('all categories and Traditional/Advanced views work',async()=>{for(const c of ['PLAYERS','TEAMS','GOALIES','FACEOFFS']){await tab(c);for(const v of ['ADVANCED','TRADITIONAL']){await tab(v);assert.ok(await page.locator('tbody tr').count()>0);assert.equal(await page.locator('h1').innerText(),`${c} STATISTICS — ${v}`);}}});
test('undefined advanced value is em dash, not zero',async()=>{const zero=datasets[2026].players.find(p=>p.level==='SEASON'&&p.advanced.two_point_conversion_pct===null);await go('#/players?season=2026&view=advanced');await page.locator('#search').fill(zero.name);await page.waitForTimeout(70);assert.equal(await page.locator(`tr[data-id="${zero.id}"] td[data-key="two_point_conversion_pct"]`).innerText(),'—');});
test('player navigation and traditional values match source bundle',async()=>{await go();const top=datasets[2026].players.filter(p=>p.level==='SEASON').sort((a,b)=>b.traditional.points-a.traditional.points||a.id.localeCompare(b.id))[0];await page.locator('td.identity a').first().click();await page.waitForSelector('.detail-head h1');assert.equal(await page.locator('.detail-head h1').innerText(),top.name);assert.equal(Number(await page.locator('.stat-strip dd[data-key="points"]').first().innerText()),top.traditional.points);assert.ok(await page.getByRole('heading',{name:'SEASON HISTORY Season totals'}).isVisible());});
test('transfer details separate totals and actual team splits',async()=>{await go('#/players/001729?season=2022&view=traditional');assert.equal(await page.locator('.stat-strip dd[data-key="games_played"]').innerText(),'5');assert.equal(await page.locator('.stat-strip dd[data-key="shots"]').innerText(),'20');const splitRows=page.locator('tr[data-level="STINT"]');assert.equal(await splitRows.count(),2);const shots=await splitRows.locator('td[data-key="shots"]').allTextContents();assert.equal(shots.reduce((a,b)=>a+Number(b),0),20);});
test('goalie detail hides irrelevant offense metrics',async()=>{const goalie=datasets[2026].players.find(p=>p.level==='SEASON'&&p.position==='G');await go(`#/players/${goalie.id}?season=2026&view=advanced`);assert.equal(await page.locator('.stat dd[data-key="shot_share"]').count(),0);assert.equal(await page.locator('.stat dd[data-key="save_pct"]').count(),1);await page.screenshot({path:new URL('../test-results/detail.png',import.meta.url).pathname});});
test('mobile keeps scrollable table without page overflow',async()=>{await page.setViewportSize({width:390,height:844});await go();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.ok(await page.locator('.table-scroll').evaluate(e=>e.scrollWidth>e.clientWidth));await page.screenshot({path:new URL('../test-results/mobile.png',import.meta.url).pathname});});
test('no uncaught browser errors',()=>assert.deepEqual(errors,[]));

test('displayed statistical spot checks across all eight views',async()=>{
 await page.setViewportSize({width:1440,height:1000});
 const check=async(category,view,search,expected)=>{await go(`#/${category}?season=2026&view=${view}`);await page.locator('#search').fill(search);await page.waitForTimeout(70);assert.equal(await page.locator('tbody tr').count(),1);for(const [key,want] of Object.entries(expected))assert.equal(await page.locator(`tbody td[data-key="${key}"]`).innerText(),want,`${category}/${view}/${key}`);};
 await check('players','traditional','Marcus Holman',{games_played:'13',goals:'28',points:'42'});
 await check('players','advanced','Logan Wisnauskas',{scoring_points_per_shot:'0.58',shooting_value_above_expected:'+12.43'});
 await check('teams','traditional','Waterdogs',{goals:'139',points:'151',assists:'76'});
 await check('teams','advanced','Waterdogs',{offensive_efficiency:'29.96',shot_producing_possession_rate:'71.0%',multi_shot_possession_rate:'22.0%'});
 await check('goalies','traditional','Sean Byrne',{saves:'86',goalsAgainst:'52',save_pct:'62.3%'});
 await check('goalies','advanced','Sean Byrne',{saves_above_average:'+11.94',resolved_shots_faced:'138'});
 await check('faceoffs','traditional','TD Ierlan',{faceoffsWon:'206',faceoffs:'353'});
 await check('faceoffs','advanced','TD Ierlan',{faceoff_wins_above_average:'+30.71'});
});

test('keyboard search retains focus while entering multiple characters',async()=>{await go();await page.locator('#search').pressSequentially('Holman');assert.equal(await page.locator('#search').inputValue(),'Holman');assert.equal(await page.locator('tbody tr').count(),1);});


test('traditional player history includes GB, CT and TO without partial label',async()=>{
 await go('#/players/000216?season=2026&view=traditional');
 const row=page.locator('#results tbody tr').first();
 assert.equal(await row.locator('[data-key="groundBalls"]').innerText(),'23');
 assert.equal(await row.locator('[data-key="causedTurnovers"]').innerText(),'4');
 assert.equal(await row.locator('[data-key="turnovers"]').innerText(),'15');
 assert.equal(await row.locator('.history-link').innerText(),'2026');
});
test('advanced history displays each seasons actual role metrics',async()=>{
 for(const [id,metric] of [['000216','shooting_value_above_expected'],['003264','saves_above_average'],['001812','faceoff_wins_above_average']]){
  await go(`#/players/${id}?season=2026&view=advanced`);
  assert.equal(await page.locator('#results [data-key="goals"]').count(),0);
  const available=[2026,2025,2024,2023,2022].filter(y=>datasets[y].players.some(p=>p.id===id&&p.level==='SEASON'));
  for(let i=0;i<available.length;i++){
   const source=datasets[available[i]].players.find(p=>p.id===id&&p.level==='SEASON').advanced[metric];
   const expected=source===null?'—':(source>0?'+':'')+source.toFixed(2);
   assert.equal(await page.locator(`#results [data-key="${metric}"]`).nth(i).innerText(),expected);
  }
 }
});
test('wrapped stat strips have consistent column alignment',async()=>{
 await page.setViewportSize({width:820,height:1000});await go('#/players/000216?season=2026&view=traditional');
 const cells=page.locator('.stat-strip .stat');const first=await cells.nth(0).boundingBox();const wrapped=await cells.nth(6).boundingBox();
 assert.equal(first.x,wrapped.x);assert.equal(first.width,wrapped.width);assert.ok(wrapped.y>first.y);
 await page.screenshot({path:new URL('../test-results/spacing-fixed.png',import.meta.url).pathname});
 await page.getByRole('link',{name:'ADVANCED',exact:true}).click();await page.waitForTimeout(80);
 await page.screenshot({path:new URL('../test-results/advanced-history-fixed.png',import.meta.url).pathname});
});


test('advanced tooltips do not repeat their explanation',async()=>{
 await go('#/players?season=2026&view=advanced');
 const title=await page.locator('button[data-sort="shot_share"]').getAttribute('title');
 assert.equal(title,'Shot Share. Share of team shots during actual appearances; follows the actual team in each game.');
 await go('#/players/000216?season=2026&view=advanced');
 const detailTitle=await page.locator('.stat').filter({has:page.locator('[data-key="shot_share"]')}).getAttribute('title');
 assert.equal(detailTitle,title);
});
