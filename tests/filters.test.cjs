const {test} = require('node:test');
const assert = require('node:assert/strict');
const {filterRepos} = require('../src/github_radar/resources/filters.js');
const items = [
  {full_name:'org/editor',trending_rank:1,category:'开发工具',language:'Rust',stars_today:20,stars_total:80,description_original:'A code editor'},
  {full_name:'org/agent',trending_rank:2,category:'AI / Agent',language:'Python',stars_today:10,stars_total:120,description_original:'Stateful workflows'},
  {full_name:'org/unknown',trending_rank:3,category:'其他',language:null,stars_today:null,stars_total:null,description_original:null},
  {full_name:'org/zero',trending_rank:4,category:'AI / Agent',language:'Rust',stars_today:0,stars_total:0,description_original:'MCP server'},
];
const names = state => filterRepos(items,state).map(repo=>repo.full_name);
test('raw source ranking',()=>assert.deepEqual(names({aiFirst:false}),items.map(r=>r.full_name)));
test('AI first preserves rank within groups',()=>assert.deepEqual(names({aiFirst:true}),['org/agent','org/zero','org/editor','org/unknown']));
test('case insensitive trimmed search',()=>assert.deepEqual(names({query:'  EDITOR '}),['org/editor']));
test('search covers descriptions',()=>assert.deepEqual(names({query:'workflows'}),['org/agent']));
test('combined category and language',()=>assert.deepEqual(names({category:'AI / Agent',language:'Rust'}),['org/zero']));
test('missing language can be filtered',()=>assert.deepEqual(names({language:'未标注'}),['org/unknown']));
test('no matching results',()=>assert.deepEqual(names({query:'absent'}),[]));
test('total Star places null after zero',()=>assert.deepEqual(names({sort:'stars'}),['org/agent','org/editor','org/zero','org/unknown']));
test('daily growth overrides AI mode',()=>assert.deepEqual(names({sort:'today',aiFirst:true}),['org/editor','org/agent','org/zero','org/unknown']));
test('stable rank tie breaker',()=>assert.equal(filterRepos([{...items[1],stars_today:20},items[0]],{sort:'today'})[0].trending_rank,1));
test('does not mutate inputs',()=>{const before=JSON.stringify(items);names({aiFirst:true});assert.equal(JSON.stringify(items),before);});
