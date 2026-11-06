import {decode,prepare,simulate,MODELS} from './engine.js';
import {annotatePriorWinRates} from './win-rate.js';
let cached;
self.onmessage=async e=>{try{if(!cached)cached=Promise.all([fetch('minute-input.json').then(r=>{if(!r.ok)throw Error('行情加载失败');return r.json();}),fetch('macro.json').then(r=>r.json())]).then(([input,macro])=>({prepared:prepare(decode(input)),settlements:Object.fromEntries(input.daily.map(d=>[d.d,+d.s])),macro}));
 const p=await cached,model=MODELS.find(m=>m.id===e.data.model);if(!model)throw Error('未知模型');const run=annotatePriorWinRates(simulate(p.prepared,p.settlements,model,{...e.data.config,macroRows:p.macro.rows}));run.curve=run.curve.filter((x,i,a)=>i%10===0||a[i+1]?.day!==x.day||a[i-1]?.position!==x.position||a[i+1]?.position!==x.position);self.postMessage({run});
 }catch(err){self.postMessage({error:err.message});}};
