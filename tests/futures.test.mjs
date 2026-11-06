import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {decode,prepare,aggregate,simulate,MODELS,macroAt,wilson,calibrate} from '../docs/futures/engine.js';
import {annotatePriorWinRates} from '../docs/futures/win-rate.js';
const input=JSON.parse(fs.readFileSync(new URL('../data/futures/minute-input.json',import.meta.url))),macro=JSON.parse(fs.readFileSync(new URL('../data/futures/macro.json',import.meta.url))).rows;
const minutes=decode(input),settles=Object.fromEntries(input.daily.map(x=>[x.d,+x.s]));
test('minute aggregation closes only full scheduled buckets, never crosses a session break',()=>{
 const a=minutes.slice(0,17),bars=aggregate(a,5);assert.equal(bars.length,3);assert.equal(bars.at(-1).end,a[14].t+1);
 for(const b of aggregate(minutes.slice(0,2000),60)){assert.ok(b.end-b.t<=60);assert.ok(b.end>b.t);const children=minutes.filter(m=>m.t>=b.t&&m.t<b.end);assert.equal(children.length,b.end-b.t);assert.equal(b.volume,children.reduce((s,m)=>s+m.volume,0));}
});
test('appending future minutes cannot alter previous indicators, signals or execution ledger',()=>{
 const cut=100007,prefix=prepare(minutes.slice(0,cut)),extended=prepare(minutes.slice(0,110000));const last=minutes[cut-1].t;
 const a=simulate(prefix,settles,MODELS[1],{macroRows:macro,macroMode:'lagged'}),b=simulate(extended,settles,MODELS[1],{macroRows:macro,macroMode:'lagged'});
 assert.ok(a.trades.length>=30);assert.deepEqual(a.ledger,b.ledger.filter(e=>e.t<=last));assert.deepEqual(a.curve,b.curve.slice(0,cut));
 assert.deepEqual(prefix.five.map(f=>[f.end,f.ema8,f.atr,f.medium?.end,f.slow?.end,f.pattern]),extended.five.filter(f=>f.end<=last+1).map(f=>[f.end,f.ema8,f.atr,f.medium?.end,f.slow?.end,f.pattern]));
});
test('macro as-of lookup does not backfill unreleased data and refuses stale observations',()=>{
 const m=[{availableMinute:100,real10:2},{availableMinute:200,real10:3}];assert.equal(macroAt(m,99),null);assert.equal(macroAt(m,199).real10,2);assert.equal(macroAt(m,200).real10,3);assert.equal(macroAt(m,14601),null);
});
function fixture({gap=98,zero=false,both=false,settle=false}={}){const t=Math.floor(Date.parse('2026-04-08T01:00:00Z')/60000);const day='2026-04-08';
 const p={close:99,low:98,high:99.5,ema8:99,oi:100,volume:300},f={end:t,close:100,high:100,low:99,ema8:99.5,atr:1,previous:p,volume:300,volume10:200,oi:110,medium:{end:t,ema8:100,ema21:99,slope8:.1,atr:1},slow:{end:t,ema10:100,ema30:99,slope10:.1,atr:1},pattern:{long:[],short:[]}};
 const m=[{t,day,open:100,high:100.2,low:99.8,close:100,volume:zero?0:100,oi:110},{t:t+1,day,open:gap,high:both?110:Math.max(gap,100),low:Math.min(gap,98),close:gap,volume:100,oi:110}];
 if(settle){m[1]={...m[1],t:t+359,open:100,low:99.8,high:100.2,close:100};m.push({...m[1],t:t+1440,day:'2026-04-09',open:102,high:102.2,low:101.8,close:102});}
 return{prepared:{minutes:m,byEnd:new Map([[t,f]]),five:[f]},settlements:{[day]:101,'2026-04-09':102},model:{...MODELS[1],targetR:settle?10:1.5}};
}
test('gap loss may exceed 3000 plan and target+stop in same minute is conservative',()=>{
 const f=fixture({gap:95,both:true}),r=simulate(f.prepared,f.settlements,f.model);assert.equal(r.trades.length,1);assert.ok(r.trades[0].plannedRisk<=3000);assert.ok(r.trades[0].netPnl < -3000);assert.equal(r.trades[0].lossOverPlan,true);assert.equal(r.metrics.openLots,0);assert.ok(r.trades[0].reason.includes('止损'));
});
test('no one-lot order fills on a zero-volume entry minute',()=>{const f=fixture({zero:true}),r=simulate(f.prepared,f.settlements,f.model);assert.equal(r.ledger.length,0);assert.equal(r.skipCounts.no_execution_volume,1);});
test('daily settlement moves cash and basis but preserves equity and whole-trade economics',()=>{
 const f=fixture({settle:true}),r=simulate(f.prepared,f.settlements,f.model);const event=r.ledger.find(x=>x.type==='settlement');assert.ok(event);assert.equal(event.variation,960);assert.equal(r.position.basis,101);assert.equal(r.metrics.finalEquity,301940);assert.equal(r.metrics.totalPnl,1940);assert.equal(r.metrics.openLots,1);
});
test('risk and margin constraints cannot be relaxed into fractional or extra lots',()=>{
 const f=fixture();const r=simulate(f.prepared,f.settlements,f.model,{maxRiskCny:1000});assert.equal(r.trades.length,0);assert.equal(r.skipCounts.risk,1);
 const m=simulate(f.prepared,f.settlements,f.model,{marginRate:3});assert.equal(m.ledger.length,0);assert.equal(m.skipCounts.margin,1);
 assert.throws(()=>simulate(f.prepared,f.settlements,f.model,{maxRiskCny:5000}));assert.throws(()=>simulate(f.prepared,f.settlements,f.model,{capital:500000}));
});
test('win intervals reflect uncertainty and empty scores remain uncalibrated',()=>{assert.equal(wilson(0,0),null);assert.ok(wilson(6,10)[0]<.6&&wilson(6,10)[1]>.6);});
test('score100 belongs in90-100 and pre-entry frequencies exclude open/later trades',()=>{const r={trades:[{score:100,entryMinute:1,exitMinute:5,netPnl:10},{score:95,entryMinute:3,exitMinute:6,netPnl:-5},{score:100,entryMinute:7,exitMinute:8,netPnl:10}]};annotatePriorWinRates(r);assert.equal(r.trades[1].empirical.pastCompleted,0);assert.equal(r.trades[2].empirical.pastCompleted,2);assert.equal(r.trades[2].empirical.pastWins,1);assert.equal(calibrate(r.trades).at(-1).trades,3);});
