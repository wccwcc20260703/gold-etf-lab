import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {MODELS,DEFAULTS,simulate,admission} from '../docs/engine.js';
const root=path.resolve(import.meta.dirname,'..'),read=p=>JSON.parse(fs.readFileSync(p,'utf8')),write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x));
const hash=x=>crypto.createHash('sha256').update(typeof x==='string'?x:JSON.stringify(x)).digest('hex');
const archive=path.join(root,'data/archive'),dailyArchive=path.join(root,'data/daily');fs.mkdirSync(archive,{recursive:true});fs.mkdirSync(dailyArchive,{recursive:true});
const acquisition=read(path.join(root,'data/acquisition.json'));
const previousQuality=fs.existsSync(path.join(root,'data/quality.json'))?read(path.join(root,'data/quality.json')):[];
const expected=[...Array.from({length:24},(_,i)=>{const m=9*60+35+i*5;return `${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;}),...Array.from({length:24},(_,i)=>{const m=13*60+5+i*5;return `${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;})];
const funds=[],quality=[];
for(const info of acquisition.funds){
 const rawPath=path.join(root,'data/raw',acquisition.asof,`${info.code}-5.json`),dailyPath=path.join(root,'data/raw',acquisition.asof,`${info.code}-101.json`);
 const oldPath=path.join(archive,`${info.code}.json`),oldDailyPath=path.join(dailyArchive,`${info.code}.json`);
 if((!fs.existsSync(rawPath)&&!fs.existsSync(oldPath))||(!fs.existsSync(dailyPath)&&!fs.existsSync(oldDailyPath))){quality.push({code:info.code,error:'Missing source response and archive; no synthetic substitute'});continue;}
 const bars=fs.existsSync(rawPath)?read(rawPath).data?.klines?.map(s=>{const a=s.split(',');return [a[0],+a[1],+a[3],+a[4],+a[2],+a[5]*100,+a[6]];})??[]:[];
 const old=fs.existsSync(oldPath)?read(oldPath):[],all=new Map(old.map(b=>[b[0],b]));let revisions=0;
 for(const b of bars){if(all.has(b[0])){if(JSON.stringify(all.get(b[0]))!==JSON.stringify(b))revisions++;}else all.set(b[0],b);}
 const merged=[...all.values()].sort((a,b)=>a[0].localeCompare(b[0]));write(oldPath,merged);
 const daily=fs.existsSync(dailyPath)?read(dailyPath).data.klines.map(s=>{const a=s.split(',');return [a[0],+a[1],+a[3],+a[4],+a[2],+a[5]*100,+a[6]];}):read(oldDailyPath);write(oldDailyPath,daily);
 const groups=Map.groupBy(merged,b=>b[0].slice(0,10)),sessions=[],excluded=[];
 for(const [date,rows]of groups){
  if(rows.length!==48||rows.some((b,i)=>b[0].slice(11)!==expected[i])||rows.some(b=>!b.slice(1).every(Number.isFinite)||b[3]>Math.min(b[1],b[4])+.00001||b[2]<Math.max(b[1],b[4])-.00001||b[3]<=0)){excluded.push(date);continue;}
  const dailyBar=daily.find(b=>b[0]===date),previous=daily.filter(b=>b[0]<date).at(-1);
  const amount=rows.reduce((s,b)=>s+b[6],0),volume=rows.reduce((s,b)=>s+b[5],0),vwap=amount/volume;
  if(vwap<Math.min(...rows.map(b=>b[3]))*.99||vwap>Math.max(...rows.map(b=>b[2]))*1.01)throw Error(`Volume/amount unit mismatch ${info.code} ${date}`);
  sessions.push({date,bars:rows,prevClose:previous?.[4],officialClose:dailyBar?.[4]});
 }
 const mismatches=sessions.filter(s=>Math.abs(s.bars.at(-1)[4]-(s.officialClose??s.bars.at(-1)[4]))>.0011).length;
 const q={code:info.code,rows:merged.length,completeDays:sessions.length,excludedDays:excluded,sourceRevisionsKeptFrozen:revisions,closeMismatchOverOneTick:mismatches,sourceHash:fs.existsSync(rawPath)?hash(fs.readFileSync(rawPath,'utf8')):previousQuality.find(q=>q.code===info.code)?.sourceHash,start:sessions[0]?.date,end:sessions.at(-1)?.date};quality.push(q);
 funds.push({...info,sessions,daily,quality:q});
}
if(!funds.length)throw Error('No real minute dataset is available');
const freezePath=path.join(root,'data/freeze.json'),oldFreeze=fs.existsSync(freezePath)?read(freezePath):null;
const dates=funds[0].sessions.map(s=>s.date),trainEnd=oldFreeze?.split?.trainEnd??dates[Math.max(0,Math.floor(dates.length*.6)-1)],validationEnd=oldFreeze?.split?.validationEnd??dates[Math.max(0,Math.floor(dates.length*.8)-1)];
const split=s=>s.date<=trainEnd?'train':s.date<=validationEnd?'validation':'test';
const trials=[];
for(const fund of funds)for(const model of MODELS){
 const periods={};
 for(const period of ['train','validation','test','all']){
  const sessions=period==='all'?fund.sessions:fund.sessions.filter(s=>split(s)===period);
  const result=simulate(sessions,model),stress=simulate(sessions,model,{slippage:DEFAULTS.slippage+.0005});
  periods[period]={...result.metrics,stressPnl:stress.metrics.totalPnl,admission:admission(result,stress)};
 }
 trials.push({code:fund.code,model:model.id,name:model.name,periods});
}
const engineHash=hash(fs.readFileSync(path.join(root,'docs/engine.js'),'utf8'));let freeze;
if(fs.existsSync(freezePath)){freeze=read(freezePath);if(freeze.engineHash!==engineHash)throw Error('Frozen engine changed: create and disclose a new research version before advancing forward simulation.');}
else{
 const candidates=trials.filter(t=>t.code==='518880'&&t.periods.train.trades>=10&&t.periods.validation.trades>=5&&t.periods.train.totalPnl>0&&t.periods.validation.totalPnl>0).sort((a,b)=>b.periods.validation.meanTradeReturn-a.periods.validation.meanTradeReturn);
 const selected=candidates[0]?.model??'ema_pullback_balanced';
 freeze={version:'v0.1',frozenAfter:acquisition.asof,split:{trainEnd,validationEnd},model:selected,selection:candidates.length?'Training-profit and validation-profit screen, then validation mean return. Test segment not used for selection.':'No training/validation candidate passed the sample screen. Fixed trend-pullback baseline is frozen for shadow observation; deployment remains cash.',engineHash,config:DEFAULTS,admissionPolicy:{forwardDays:60,forwardTrades:100,winRate:.6,profitFactor:1.2,maxDrawdown:.03,extraRoundTripCost:.001}};
 freeze.hash=hash(freeze);write(freezePath,freeze);
}
const model=MODELS.find(m=>m.id===freeze.model),forward=[],replays={};
for(const fund of funds){
 const result=simulate(fund.sessions.filter(s=>s.date>freeze.frozenAfter),model,freeze.config),stress=simulate(fund.sessions.filter(s=>s.date>freeze.frozenAfter),model,{...freeze.config,slippage:freeze.config.slippage+.0005});
 forward.push({code:fund.code,model:freeze.model,...result.metrics,gate:admission(result,stress),trades:result.trades,curve:result.curve});
 replays[fund.code]=simulate(fund.sessions,model);
}
const data={schemaVersion:1,builtAt:new Date().toISOString(),asof:acquisition.asof,status:'research_only_no_qualified_forward_model',coverage:{dates:dates.length,start:dates[0],end:dates.at(-1),trainEnd,validationEnd},funds,trials,freeze,forward,replays,quality,errors:acquisition.errors,sources:[{title:'上交所ETF交易规则与0.001元价格单位',url:'https://www.sse.com.cn/assortment/fund/etf/question/'},{title:'华安黄金ETF产品与黄金现货跟踪标的',url:'https://www.huaan.com.cn/funds/518880/index.shtml'},{title:'深交所场内基金佣金与免印花税说明',url:'https://investor.szse.cn/warning/activities/fundIntroduction/t20210104_584079.html'},{title:'世界黄金协会：金价影响因素',url:'https://www.gold.org/goldhub/research/what-drives-gold'},{title:'AKShare：分钟行情仅近期覆盖',url:'https://akshare.akfamily.xyz/data/fund/fund_public.html'},{title:'国泰黄金ETF份额合并公告',url:'https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-04-09/518800_20260409_QXKL.pdf'}]};
write(path.join(root,'docs/data.json'),data);write(path.join(root,'data/quality.json'),quality);
const columns=['code','model','period','trades','wins','winRate','meanTradeReturn','totalPnl','maxDrawdown','profitFactor','stressPnl'];const csv=[columns.join(',')];
for(const trial of trials)for(const [period,m]of Object.entries(trial.periods))csv.push(columns.map(c=>({code:trial.code,model:trial.model,period,...m})[c]??'').join(','));
fs.writeFileSync(path.join(root,'docs/all-trials.csv'),'\ufeff'+csv.join('\n'));
console.log(JSON.stringify({funds:funds.length,coverage:data.coverage,trials:trials.length,freeze:{model:freeze.model,hash:freeze.hash,selection:freeze.selection},forwardDays:forward[0].days,quality}));
