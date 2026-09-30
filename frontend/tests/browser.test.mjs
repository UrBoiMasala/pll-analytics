import {test,before,after} from 'node:test';import assert from 'node:assert/strict';import {readFile,mkdir} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.FRONTEND_URL||'http://127.0.0.1:4173';let browser,page;const errors=[];
const datasets={};for(const y of [2022,2023,2024,2025,2026])datasets[y]=JSON.parse(await readFile(new URL(`../dist/data/${y}.json`,import.meta.url)));
before(async()=>{browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));});
after(async()=>{await browser?.close();});
async function go(hash='#/players?season=2026&segment=combined'){if(hash.includes('season=2026')&&!hash.includes('segment='))hash+='&segment=combined';await page.goto(origin+'/'+hash);await page.waitForSelector('tbody tr');}
async function tab(name){name=name==='TRADITIONAL'?'Standard':name[0]+name.slice(1).toLowerCase();await page.getByRole('link',{name,exact:true}).click();await page.waitForTimeout(70);}
test('default landing, partial indicator and dense data above fold',async()=>{await go('');assert.equal(await page.locator('#season').inputValue(),'2026');assert.equal(await page.locator('.partial').innerText(),'');assert.equal(await page.locator('tbody tr').count(),datasets[2026].segments.regular.players.filter(p=>p.level==='SEASON').length);const first=await page.locator('tbody tr').first().boundingBox();assert.ok(first.y+8*first.height<1000,'At least eight rows fit above the desktop fold');await mkdir(new URL('../test-results/',import.meta.url),{recursive:true});await page.screenshot({path:new URL('../test-results/desktop.png',import.meta.url).pathname});});
test('switches all five seasons and partial marker',async()=>{for(const y of [2022,2023,2024,2025,2026]){await page.locator('#season').selectOption(String(y));await page.waitForTimeout(70);assert.equal(await page.locator('tbody tr').count(),datasets[y].segments.regular.players.filter(p=>p.level==='SEASON').length);assert.equal(await page.locator('.partial').innerText(),'');}});
test('team, position and search filters',async()=>{await go();await page.locator('#team').selectOption('CAN');await page.locator('#position').selectOption('A');await page.locator('#search').fill('Holman');await page.waitForTimeout(80);assert.equal(await page.locator('tbody tr').count(),1);assert.equal(await page.locator('tbody tr').getAttribute('data-team'),'CAN');assert.equal(await page.locator('tbody tr').getAttribute('data-level'),'STINT');assert.match(await page.locator('tbody tr').innerText(),/Marcus Holman/);});
test('sort changes direction and displayed order',async()=>{await go();await page.getByRole('button',{name:'PTS ↕',exact:true}).count();await page.locator('button[data-sort="points"]').click();await page.waitForTimeout(70);const pts=await page.locator('td[data-key="points"]').allTextContents();assert.ok(Number(pts[0])<=Number(pts.at(-1)));assert.equal(await page.locator('th[aria-sort="ascending"] button').getAttribute('data-sort'),'points');});
test('all categories and Traditional/Advanced views work',async()=>{for(const c of ['PLAYERS','TEAMS','GOALIES','FACEOFFS']){await tab(c);for(const v of ['ADVANCED','TRADITIONAL']){await tab(v);assert.ok(await page.locator('tbody tr').count()>0);assert.equal(await page.locator('h1').innerText(),`PLL ${{PLAYERS:'Player',TEAMS:'Team',GOALIES:'Goalie',FACEOFFS:'Faceoff'}[c]} Stats 2026`);}}});
test('undefined advanced value is em dash, not zero',async()=>{const zero=datasets[2026].players.find(p=>p.level==='SEASON'&&p.advanced.two_point_conversion_pct===null);await go('#/players?season=2026&view=advanced');await page.locator('#search').fill(zero.name);await page.waitForTimeout(70);assert.equal(await page.locator(`tr[data-id="${zero.id}"] td[data-key="two_point_conversion_pct"]`).innerText(),'—');});
test('player navigation and traditional values match source bundle',async()=>{await go();const top=datasets[2026].players.filter(p=>p.level==='SEASON').sort((a,b)=>b.traditional.points-a.traditional.points||a.id.localeCompare(b.id))[0];await page.locator('td.identity a').first().click();await page.waitForSelector('.detail-head h1');assert.equal(await page.locator('.detail-head h1').innerText(),top.name);assert.equal(Number(await page.locator('.stat-strip dd[data-key="points"]').first().innerText()),top.traditional.points);assert.ok(await page.getByRole('heading',{name:'Season stats Regular season + playoffs'}).isVisible());});
test('transfer details separate totals and actual team splits',async()=>{await go('#/players/001729?season=2022&segment=combined&view=traditional');assert.equal(await page.locator('.stat-strip dd[data-key="games_played"]').innerText(),'5');assert.equal(await page.locator('.stat-strip dd[data-key="shots"]').innerText(),'20');const splitRows=page.locator('tr[data-level="STINT"]');assert.equal(await splitRows.count(),2);const shots=await splitRows.locator('td[data-key="shots"]').allTextContents();assert.equal(shots.reduce((a,b)=>a+Number(b),0),20);});
test('goalie detail hides irrelevant offense metrics',async()=>{const goalie=datasets[2026].players.find(p=>p.level==='SEASON'&&p.position==='G');await go(`#/players/${goalie.id}?season=2026&view=advanced`);assert.equal(await page.locator('.stat dd[data-key="shot_share"]').count(),0);assert.equal(await page.locator('.stat dd[data-key="save_pct"]').count(),1);await page.screenshot({path:new URL('../test-results/detail.png',import.meta.url).pathname});});
test('mobile keeps scrollable table without page overflow',async()=>{await page.setViewportSize({width:390,height:844});await go();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.ok(await page.locator('.table-scroll').evaluate(e=>e.scrollWidth>e.clientWidth));await page.screenshot({path:new URL('../test-results/mobile.png',import.meta.url).pathname});});
test('no uncaught browser errors',()=>assert.deepEqual(errors,[]));

test('displayed statistical spot checks across all eight views',async()=>{
 await page.setViewportSize({width:1440,height:1000});
 const check=async(category,view,search,expected)=>{await go(`#/${category}?season=2026&view=${view}`);await page.locator('#search').fill(search);await page.waitForTimeout(70);assert.equal(await page.locator('tbody tr').count(),1);for(const [key,want] of Object.entries(expected))assert.equal(await page.locator(`tbody td[data-key="${key}"]`).innerText(),want,`${category}/${view}/${key}`);};
 await check('players','traditional','Marcus Holman',{games_played:'14',goals:'30',points:'44'});
 await check('players','advanced','Logan Wisnauskas',{scoring_points_per_shot:'0.49',shooting_value_above_expected:'+10.18'});
 await check('teams','traditional','Waterdogs',{goals:'166',points:'178',assists:'87'});
 await check('teams','advanced','Waterdogs',{offensive_efficiency:'29.82',shot_producing_possession_rate:'70.5%',multi_shot_possession_rate:'20.8%'});
 await check('goalies','traditional','Sean Byrne',{saves:'111',goalsAgainst:'65',save_pct:'63.1%'});
 await check('goalies','advanced','Sean Byrne',{saves_above_average:'+16.15',resolved_shots_faced:'176'});
 await check('faceoffs','traditional','TD Ierlan',{faceoffsWon:'206',faceoffs:'353'});
 await check('faceoffs','advanced','TD Ierlan',{faceoff_wins_above_average:'+30.78'});
});

test('keyboard search retains focus while entering multiple characters',async()=>{await go();await page.locator('#search').pressSequentially('Holman');assert.equal(await page.locator('#search').inputValue(),'Holman');assert.equal(await page.locator('tbody tr').count(),1);});


test('traditional player history includes GB, CT and TO without partial label',async()=>{
 await go('#/players/000216?season=2026&view=traditional');
 const row=page.locator('#results tbody tr').first();
 assert.equal(await row.locator('[data-key="groundBalls"]').innerText(),'25');
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
 await page.getByRole('link',{name:'Advanced',exact:true}).click();await page.waitForTimeout(80);
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


test('2022 competition filtering, reload and Championship Series empty state',async()=>{
 await go('#/players?season=2022&view=advanced');
 assert.equal(await page.locator('#segment').inputValue(),'regular');
 await page.locator('#segment').selectOption('post');
 await page.waitForTimeout(70);
 assert.equal(await page.locator('tbody tr').count(),datasets[2022].segments.post.players.filter(p=>p.level==='SEASON').length);
 await page.reload();await page.waitForSelector('tbody tr');
 assert.equal(await page.locator('#segment').inputValue(),'post');
 await page.locator('td.identity a').first().click();await page.waitForSelector('.detail-head');
 assert.match(await page.locator('.detail-meta').innerText(),/Playoffs/);
 const historyLink=page.locator('.history-link').filter({hasText:'2022'});
 assert.match(await historyLink.getAttribute('href'),/segment=combined/);
 await page.locator('#segment').selectOption('champ_series');await page.waitForTimeout(70);
 assert.match(await page.locator('main').innerText(),/No Championship Series was held in 2022/);
 await page.locator('.back').click();await page.waitForSelector('.empty');
 assert.equal(await page.locator('tbody tr').count(),0);
 await page.locator('#season').selectOption('2025');await page.waitForSelector('tbody tr');
 assert.equal(await page.locator('#segment').inputValue(),'regular');
 await page.setViewportSize({width:390,height:844});await go('#/players?season=2022&segment=post');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
});


test('2023 regular, playoff and Sixes views remain distinct',async()=>{
 await page.setViewportSize({width:1440,height:1000});await go('#/players?season=2023&view=advanced');
 assert.equal(await page.locator('#segment').inputValue(),'regular');
 for(const segment of ['regular','post','champ_series','combined']){
  await page.locator('#segment').selectOption(segment);await page.waitForTimeout(80);
  const sample=segment==='combined'?datasets[2023]:datasets[2023].segments[segment];
  assert.equal(await page.locator('tbody tr').count(),sample.players.filter(p=>p.level==='SEASON').length);
 }
 await page.locator('#segment').selectOption('champ_series');await page.waitForTimeout(80);
 assert.match(await page.locator('.competition-note').innerText(),/Possession and pace metrics are unavailable/);
 await page.locator('td.identity a').first().click();await page.waitForSelector('.detail-head');
 assert.ok(await page.locator('.stat dd[data-key="shooting_value_above_expected"]').count()>0);
 await page.locator('.back').click();await page.waitForSelector('tbody tr');
 await tab('TEAMS');assert.equal(await page.locator('tbody tr').count(),4);
 assert.equal(await page.locator('button[data-sort="offensive_efficiency"]').count(),0);
 assert.equal(await page.locator('button[data-sort="team_two_point_attempt_rate"]').count(),1);
 await page.reload();await page.waitForSelector('tbody tr');assert.equal(await page.locator('#segment').inputValue(),'champ_series');
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
});


test('2024–2026 competition scope applies across all categories and reloads',async()=>{
 await page.setViewportSize({width:1440,height:1000});
 for(const year of [2024,2025,2026]){
  await go(`#/players?season=${year}&segment=regular&view=advanced`);
  for(const segment of ['regular','post','champ_series','combined']){
   await page.locator('#segment').selectOption(segment);await page.waitForTimeout(60);
   const data=segment==='combined'?datasets[year]:datasets[year].segments[segment];
   for(const category of ['players','teams','goalies','faceoffs']){
    await tab(category.toUpperCase());
    const {selectRows,readState}=await import('../src/data.js');
    const state=readState(`#/${category}?season=${year}&segment=${segment}&view=advanced`);
    assert.equal(await page.locator('tbody tr').count(),selectRows(data,state).length,`${year}/${segment}/${category}`);
   }
   await tab('PLAYERS');
  }
  await page.locator('#segment').selectOption('post');await page.waitForTimeout(60);
  await page.locator('td.identity a').first().click();await page.waitForSelector('.detail-head');
  assert.match(await page.locator('.detail-meta').innerText(),/Playoffs/);
  await page.reload();await page.waitForSelector('.detail-head');
  assert.equal(await page.locator('#segment').inputValue(),'post');
 }
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
});


test('readable rows, sorted column, stat key and pinned mobile names',async()=>{
 await page.setViewportSize({width:1440,height:1000});await go();
 const fill=locator=>locator.evaluate(e=>getComputedStyle(e).backgroundColor);
 assert.notEqual(await fill(page.locator('tbody tr').nth(0).locator('[data-key="goals"]')),await fill(page.locator('tbody tr').nth(1).locator('[data-key="goals"]')));
 assert.notEqual(await fill(page.locator('tbody tr').first().locator('[data-key="points"]')),await fill(page.locator('tbody tr').first().locator('[data-key="goals"]')));
 await page.getByText('Stat key',{exact:true}).click();assert.ok(await page.locator('.stat-key dd').first().isVisible());
 await page.setViewportSize({width:390,height:844});
 const before=await page.locator('td.identity').first().boundingBox();
 await page.locator('.table-scroll').evaluate(e=>e.scrollLeft=500);
 const after=await page.locator('td.identity').first().boundingBox();assert.equal(before.x,after.x);
});
test('season charts preserve source values and explicit competition scope',async()=>{
 await page.setViewportSize({width:1440,height:1000});
 for(const [id,view,key] of [['000216','traditional','points'],['000216','advanced','scoring_points_per_shot'],[datasets[2026].players.find(p=>p.name==='Blaze Riorden'&&p.level==='SEASON').id,'advanced','save_pct'],['001812','advanced','faceoff_pct']]){
  await go(`#/players/${id}?season=2026&segment=post&view=${view}`);
  assert.match(await page.locator('.trend figcaption').innerText(),/Regular season \+ playoffs/);
  for(const row of await page.locator('.trend li').all()){
   const year=await row.getAttribute('data-season');const source=datasets[year].players.find(p=>p.id===id&&p.level==='SEASON')[view][key];
   assert.equal(await row.getAttribute('data-metric'),key);
   assert.equal(await row.getAttribute('data-value'),String(source??''));
  }
 }
 assert.deepEqual(errors,[]);
});
