import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {MODELS,DEFAULTS,simulate,features,entrySignal,fillPrice,admission} from '../docs/engine.js';
const data=JSON.parse(fs.readFileSync(new URL('../docs/data.json',import.meta.url)));
test('all real-data trials conserve cash, hold only nonnegative lots, and close intraday',()=>{
 let fills=0;
 for(const fund of data.funds)for(const model of MODELS){
  const r=simulate(fund.sessions,model);let cash=DEFAULTS.capital,shares=0;
  for(const t of r.fills){assert.ok(t.time>=t.signalTime);assert.ok(t.quantity>0&&t.quantity%100===0);assert.ok(t.price>0);assert.ok(Math.abs(t.price*1000-Math.round(t.price*1000))<1e-6);assert.ok(Math.abs(t.cashBefore-cash)<1e-7);assert.equal(t.sharesBefore,shares);
   cash+=t.side==='buy'?-t.quantity*t.price-t.fee:t.quantity*t.price-t.fee;shares+=t.side==='buy'?t.quantity:-t.quantity;
   assert.ok(cash>=-1e-7&&shares>=0);assert.ok(Math.abs(cash-t.cashAfter)<1e-7);assert.equal(shares,t.sharesAfter);fills++;
  }
  assert.equal(r.metrics.failed,false);assert.equal(shares,0);assert.ok(r.daySummaries.every(d=>d.closingShares===0&&d.roundTrips<=3));
  assert.ok(Math.abs(r.trades.reduce((s,t)=>s+t.pnl,0)-(cash-DEFAULTS.capital))<1e-6);
 }
 assert.ok(fills>100);
});
test('signals and indicators are invariant to future bars',()=>{
 let checked=0;for(const s of data.funds[0].sessions){const full=features(s.bars);for(let i=6;i<s.bars.length;i++){const prefix=s.bars.slice(0,i+1),f=features(prefix);assert.deepEqual(full[i],f[i]);for(const m of MODELS){assert.equal(entrySignal(m,s.bars,full,i),entrySignal(m,prefix,f,i));checked++;}}}assert.ok(checked>10000);
});
test('higher transaction costs cannot improve the same frozen signal execution return',()=>{
 const sessions=data.funds[0].sessions;const model=MODELS[0];const normal=simulate(sessions,model),cost=simulate(sessions,model,{commission:.001});assert.ok(cost.metrics.totalPnl<normal.metrics.totalPnl);
 assert.ok(fillPrice(8.123,true,.0002)>=8.123&&fillPrice(8.123,false,.0002)<=8.123);
});
test('failed mandatory close remains visible and stops the simulation',()=>{
 const original=data.funds[0].sessions.find(s=>simulate([s],MODELS.find(m=>m.id==='vwap_reclaim_balanced')).fills.length>0);assert.ok(original);
 const session=structuredClone(original),model=MODELS.find(m=>m.id==='vwap_reclaim_balanced');const first=simulate([session],model).fills.find(f=>f.side==='buy');
 const entryIndex=session.bars.findIndex(b=>b[0]===first.signalTime)+1;for(let i=entryIndex+1;i<48;i++)session.bars[i][5]=0;
 const r=simulate([session],model);assert.equal(r.metrics.failed,true);assert.ok(r.curve.at(-1).shares>0);assert.equal(r.daySummaries[0].closingShares,r.curve.at(-1).shares);
});
test('no tiny historical sample can pass the forward admission policy',()=>{
 for(const f of data.funds)for(const m of MODELS){const sample=f.sessions.slice(0,32),r=simulate(sample,m),stress=simulate(sample,m,{slippage:.0007});assert.equal(admission(r,stress).passed,false);}
 assert.equal(data.forward[0].days,data.funds[0].sessions.filter(s=>s.date>data.freeze.frozenAfter).length);assert.equal(data.freeze.frozenAfter,'2026-11-06');
});
test('opening range uses only the completed first half-hour and never permits shorts',()=>{
 const s=data.funds[0].sessions[0],f=features(s.bars),m=MODELS.find(m=>m.family==='orb');for(let i=0;i<6;i++)assert.equal(entrySignal(m,s.bars,f,i),false);
 for(const fund of data.funds)for(const model of MODELS){const r=simulate(fund.sessions,model,{capital:1000});assert.ok(r.fills.every(t=>t.sharesAfter>=0&&t.cashAfter>=0));}
});
