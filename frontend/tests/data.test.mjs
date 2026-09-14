import test from 'node:test';import assert from 'node:assert/strict';
import {readState,route,selectRows,sortRows,format,defaultSort,playerSeason} from '../src/data.js';
import {columns,roleSections} from '../src/columns.js';
const base={id:'001',name:'Player One',team:'ALL',teams:['A','B'],position:'A',season:2026,level:'SEASON',traditional:{points:12},advanced:{shooting_value_above_expected:1}};
const stint={...base,team:'A',teams:['A'],level:'STINT',traditional:{points:4}};
const other={...base,id:'002',name:'Second Player',team:'B',teams:['B'],position:'G',traditional:{points:0},advanced:{shooting_value_above_expected:null,resolved_shots_faced:12}};
const data={players:[base,stint,other],teams:[]};
test('default is Players Traditional 2026',()=>{assert.deepEqual(readState().category,'players');assert.equal(readState().view,'traditional');assert.equal(readState().season,2026);assert.equal(defaultSort('players','traditional'),'points');});
test('routes preserve season, view, player and filters',()=>{const s={...readState(),season:2023,player:'001',team:'A',search:'One & Two',view:'advanced'};assert.deepEqual(readState(route(s)),s);});
test('unknown seasons and categories have safe defaults',()=>{assert.equal(readState('#/bad?season=2050').season,2026);assert.equal(readState('#/bad').category,'players');});
test('all-team lists select SEASON exactly once',()=>{assert.deepEqual(selectRows(data,readState()).map(r=>r.traditional.points),[12,0]);});
test('team filtering selects actual STINT, not full-season totals',()=>{const rows=selectRows(data,{...readState(),team:'A'});assert.equal(rows.length,1);assert.equal(rows[0].traditional.points,4);});
test('search and position filters combine',()=>{assert.equal(selectRows(data,{...readState(),position:'G',search:'SECOND'}).length,1);assert.equal(selectRows(data,{...readState(),position:'A',search:'Second'}).length,0);});
test('null values stay last in both sort directions',()=>{for(const direction of ['asc','desc'])assert.equal(sortRows([base,other],'shooting_value_above_expected','advanced',direction).at(-1).id,'002');});
test('sort ties use stable player identity',()=>{assert.equal(sortRows([{...base,id:'002'},base],'points','traditional')[0].id,'001');});
test('formatting distinguishes missing and zero',()=>{assert.equal(format(null,'pct'),'—');assert.equal(format(NaN),'—');assert.equal(format(0,'pct'),'0.0%');assert.equal(format(.381,'pct'),'38.1%');assert.equal(format(12.43,'signed'),'+12.43');assert.equal(format(26.4,'seconds'),'26.4 sec');});
test('player detail takes season total rather than first stint',()=>assert.equal(playerSeason({...data,players:[stint,base]},'001').traditional.points,12));
test('all eight table configurations exist without composite metrics',()=>{for(const c of ['players','teams','goalies','faceoffs'])for(const v of ['traditional','advanced'])assert.ok(columns(c,v).length>=5);});
test('goalie detail includes only relevant advanced section',()=>assert.deepEqual(roleSections(other).map(([name])=>name),['GOALKEEPING']));


test('metric descriptions deduplicate repeated explanations and keep distinct limitations',async()=>{
 const {metricDescription}=await import('../src/data.js');
 assert.equal(metricDescription({display_name:'Shot Share',interpretation:'Share of team attempts.',limitation_summary:'Share of team attempts. Actual appearances only.'}),'Shot Share. Share of team attempts. Actual appearances only.');
 assert.equal(metricDescription({display_name:'Save rate',interpretation:'Resolved outcomes only.',limitation_summary:'Shot difficulty is not observed.'}),'Save rate. Resolved outcomes only. Shot difficulty is not observed.');
});
