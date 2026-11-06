import fs from 'node:fs';import path from 'node:path';import {decode} from '../docs/futures/engine.js';import {decorate} from './factor_indicators.mjs';
const root=path.resolve(import.meta.dirname,'..'),input=JSON.parse(fs.readFileSync(path.join(root,'data/futures/minute-input.json'))),out=path.join(root,'docs/futures/factor/charts');fs.mkdirSync(out,{recursive:true});
const round=(n,d=4)=>n==null?null:Math.round(n*10**d)/10**d;
const one=decorate(decode(input)),groups=Object.groupBy(one,m=>m.day);
for(const[day,bars]of Object.entries(groups))fs.writeFileSync(path.join(out,day+'.json'),JSON.stringify(bars.map(m=>[m.t,round(m.ema8),round(m.ema21),round(m.mid==null?null:m.mid+2*m.sd),round(m.mid==null?null:m.mid-2*m.sd),round(m.macdHist),round(m.rsi,2),round(m.adx,2)])));
const daily=decorate(input.daily.map(d=>({day:d.d,open:+d.o,close:+d.c,low:+d.l,high:+d.h,volume:+d.v})));fs.writeFileSync(path.join(out,'daily.json'),JSON.stringify(daily.map(m=>[m.day,m.open,m.close,m.low,m.high,round(m.ema20),round(m.ema60),round(m.macdHist),round(m.rsi,2),round(m.adx,2)])));
console.log(JSON.stringify({days:Object.keys(groups).length,minuteIndicatorRows:one.length,dailyRows:daily.length,source:'Same indicator function as factor generation; price overlays for historical replay.'}));
