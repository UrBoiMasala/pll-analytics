// @ts-check
/** @typedef {'players'|'teams'|'goalies'|'faceoffs'} Category */
/** @typedef {'traditional'|'advanced'} View */
/** @typedef {{id:string,name:string,team:string,teams:string[],position:string,level:string,season:number,traditional:Record<string,number|null>,advanced:Record<string,number|null>}} StatRecord */
/** @typedef {{season:number,players:StatRecord[],teams:StatRecord[],partial:boolean,cutoff:string}} SeasonData */
/** @typedef {{category:Category,view:View,season:number,segment:string,team:string,position:string,search:string,sort:string,direction:string,player:string}} State */
export const seasons=[2026,2025,2024,2023,2022];
export const splitSeasons=seasons;
export const categories=['players','teams','goalies','faceoffs'];
/** @returns {State} */
export function readState(hash=''){
 const [path,query='']=hash.replace(/^#\/?/,'').split('?');const [cat,id='']=path.split('/');const q=new URLSearchParams(query);
 const year=seasons.includes(Number(q.get('season')))?Number(q.get('season')):2026;
 const segment=splitSeasons.includes(year)?(['regular','post','combined','champ_series'].includes(q.get('segment'))?q.get('segment'):'regular'):'combined';
 return {segment,category:categories.includes(cat)?/** @type {Category} */(cat):'players',view:q.get('view')==='advanced'?'advanced':'traditional',season:seasons.includes(Number(q.get('season')))?Number(q.get('season')):2026,team:q.get('team')||'',position:q.get('position')||'',search:q.get('q')||'',sort:q.get('sort')||'',direction:q.get('dir')==='asc'?'asc':'desc',player:id};
}
export function route(s){const q=new URLSearchParams({season:String(s.season),view:s.view});if(splitSeasons.includes(s.season))q.set('segment',s.segment||'regular');for(const [key,val] of Object.entries({team:s.team,position:s.position,q:s.search,sort:s.sort,dir:s.sort?s.direction:''}))if(val)q.set(key,val);return `#/${s.category}${s.player?'/'+encodeURIComponent(s.player):''}?${q}`;}
export async function loadData(){
 const get=async path=>{const r=await fetch(path);if(!r.ok)throw new Error('Statistics could not be loaded.');return r.json();};
 const values=await Promise.all(seasons.map(y=>get(`./data/${y}.json`)));const metadata=await get('./data/metrics.json');
 return {years:Object.fromEntries(values.map(d=>[d.season,d])),metadata};
}
export function belongs(row,category){if(category==='goalies')return row.position.split(',').includes('G')||Number(row.advanced.resolved_shots_faced)>0;if(category==='faceoffs')return row.position.split(',').includes('FO')||Number(row.traditional.faceoffs)>0;return true;}
/** Team filtering selects STINT rows. Unfiltered lists use SEASON totals exactly once. */
export function selectRows(data,state){
 let rows=state.category==='teams'?data.teams:data.players.filter(r=>state.team?r.level==='STINT'&&r.team===state.team:r.level==='SEASON');
 return rows.filter(r=>belongs(r,state.category)&&(!state.team||r.teams.includes(state.team))&&(!state.position||r.position.split(',').includes(state.position))&&`${r.name} ${r.teams.join(' ')}`.toLocaleLowerCase().includes(state.search.toLocaleLowerCase().trim()));
}
export function value(row,key,view){if(key==='name')return row.name;if(key==='team')return row.teams.join(' / ');if(key==='position')return row.position;return row[view][key]??null;}
export function sortRows(rows,key,view,direction='desc'){
 return [...rows].sort((a,b)=>{const x=value(a,key,view),y=value(b,key,view);if(x===null&&y!==null)return 1;if(y===null&&x!==null)return -1;let order=typeof x==='string'&&typeof y==='string'?x.localeCompare(y):Number(x)-Number(y);return (direction==='asc'?order:-order)||a.id.localeCompare(b.id);});
}
export function format(v,type='int'){
 if(v===null||v===undefined||typeof v==='number'&&!Number.isFinite(v))return '—';if(typeof v==='string')return v;
 if(type==='pct')return (v*100).toFixed(1)+'%';if(type==='signed')return (v>0?'+':'')+v.toFixed(2);if(type==='seconds')return v.toFixed(1)+' sec';if(type==='decimal')return v.toFixed(2);if(type==='ratio')return v.toFixed(3);return v.toLocaleString('en-US',{maximumFractionDigits:0});
}
export function playerSeason(data,id){return data.players.find(r=>r.id===id&&r.level==='SEASON');}
export function defaultSort(category,view){return view==='traditional'?({players:'points',teams:'points',goalies:'saves',faceoffs:'faceoffsWon'})[category]:({players:'shooting_value_above_expected',teams:'offensive_efficiency',goalies:'saves_above_average',faceoffs:'faceoff_wins_above_average'})[category];}

/** Combine dictionary descriptions without repeating shared sentences. */
export function metricDescription(metadata) {
 const seen=new Set();
 const sentences=[metadata.display_name,metadata.interpretation,metadata.limitation_summary]
  .filter(Boolean).flatMap(text=>text.trim().split(/(?<=[.!?])\s+/));
 return sentences.filter(sentence=>{
  const key=sentence.trim().replace(/[.!?]+$/, '').replace(/\s+/g,' ').toLowerCase();
  if(!key||seen.has(key))return false;
  seen.add(key);return true;
 }).map(sentence=>/[.!?]$/.test(sentence)?sentence:sentence+'.').join(' ');
}

export function seasonData(data,segment='combined'){return data.segments?.[segment]||data;}
