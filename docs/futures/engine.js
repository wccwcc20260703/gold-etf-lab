export const SPEC={contract:'AU2612',multiplier:1000,tick:.02,lots:1};
export const DEFAULTS={capital:300000,maxRiskCny:3000,riskFraction:.01,marginRate:.20,marginBuffer:.20,openFee:20,closeTodayFee:20,closeOvernightFee:20,slippageTicks:2,dailyLossFraction:.02,maxEntriesPerDay:2,minScore:60,carryScore:80,entryWindow:'any',macroMode:'off',noNewOnOrAfter:'2026-11-30',exitOnOrAfter:'2026-11-30'};
export const MODELS=['pullback','breakout','reversion'].flatMap(family=>[.8,1.5].map(targetR=>({id:`${family}_${targetR}`,family,targetR,name:({pullback:'顺势回踩',breakout:'区间突破',reversion:'布林回归'})[family]+` · ${targetR}R`,atrMultiple:1.5})));
export const SPLIT={trainEnd:'2026-05-29',validationEnd:'2026-08-31',testStart:'2026-09-01'};
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length, money=x=>Math.round((x+Number.EPSILON)*100)/100;
const up=x=>Math.ceil((x-1e-8)/.02)*.02,down=x=>Math.floor((x+1e-8)/.02)*.02;
export function stamp(t){return new Date((t+480)*60000).toISOString().slice(0,16).replace('T',' ');}
export function session(t){const m=((t+480)%1440+1440)%1440;return m>=1260||m<180?'night':'day';}
export function decode(input){return input.rows.map(r=>({t:r[0],day:input.calendar[r[1]],open:r[2]*.02,high:r[3]*.02,low:r[4]*.02,close:r[5]*.02,volume:r[6],oi:r[7]}));}
function segment(t){const m=((t+480)%1440+1440)%1440,base=t-m;
 if(m>=1260)return{start:base+1260,end:base+1590};if(m<150)return{start:base-180,end:base+150};
 for(const[a,b]of[[540,615],[630,690],[810,900]])if(m>=a&&m<b)return{start:base+a,end:base+b};throw Error('Outside exchange session '+stamp(t));}
export function aggregate(minutes,period){const out=[];let b;
 function finish(){if(b&&b.last+1===b.end&&b.count===b.end-b.t){const{last,count,...clean}=b;out.push(clean);}}
 for(const m of minutes){const s=segment(m.t),start=s.start+Math.floor((m.t-s.start)/period)*period,end=Math.min(start+period,s.end);
  if(b?.t!==start){finish();b={t:start,end,day:m.day,open:m.open,high:m.high,low:m.low,close:m.close,volume:0,oi:m.oi,positive:false,last:m.t,count:0};}
  b.last=m.t;b.count++;b.oi=m.oi;if(m.volume>0){if(!b.positive){b.open=m.open;b.high=m.high;b.low=m.low;}b.high=Math.max(b.high,m.high);b.low=Math.min(b.low,m.low);b.close=m.close;b.positive=true;}b.volume+=m.volume;
 }finish();return out;}
function indicators(a){const es=Object.fromEntries([8,21,10,30].map(n=>[n,[]])),trs=[];
 for(let i=0;i<a.length;i++){const b=a[i],p=a[i-1];for(const n of[8,21,10,30]){es[n][i]=i<n-1?null:i===n-1?mean(a.slice(0,n).map(x=>x.close)):es[n][i-1]+2/(n+1)*(b.close-es[n][i-1]);b['ema'+n]=es[n][i];}
  for(const n of[8,10])b['slope'+n]=i&&es[n][i]!=null&&es[n][i-1]!=null?es[n][i]-es[n][i-1]:null;
  trs.push(p?Math.max(b.high-b.low,Math.abs(b.high-p.close),Math.abs(b.low-p.close)):b.high-b.low);b.atr=i>=13?mean(trs.slice(i-13,i+1)):null;
  const w=a.slice(Math.max(0,i-19),i+1).map(x=>x.close);b.mid=i>=19?mean(w):null;b.sd=i>=19?Math.sqrt(mean(w.map(x=>(x-b.mid)**2))):null;
  if(i>=14){const ch=a.slice(i-13,i+1).map((x,k)=>x.close-a[i-14+k].close),gain=mean(ch.map(x=>Math.max(0,x))),loss=mean(ch.map(x=>Math.max(0,-x)));b.rsi=loss?100-100/(1+gain/loss):gain?100:50;}else b.rsi=null;
  b.previous=p??null;b.volume10=i>=10?mean(a.slice(i-10,i).map(x=>x.volume)):null;b.donchianHigh=i>=20?Math.max(...a.slice(i-20,i).map(x=>x.high)):null;b.donchianLow=i>=20?Math.min(...a.slice(i-20,i).map(x=>x.low)):null;
 }return a;}
function regression(a){const x=(a.length-1)/2,y=mean(a),s=a.reduce((s,v,i)=>s+(i-x)*(v-y),0)/a.reduce((s,v,i)=>s+(i-x)**2,0);return{slope:s,next:y+s*(a.length-x)};}
export function patterns(a,i){const out={long:[],short:[]};if(i<25)return out;const b=a[i],hist=a.slice(i-12,i),hi=regression(hist.map(x=>x.high)),lo=regression(hist.map(x=>x.low));
 if(hi.slope<0&&lo.slope>0&&hi.next>lo.next){if(b.close>hi.next&&b.previous.close<=hi.next)out.long.push('收敛三角向上突破');if(b.close<lo.next&&b.previous.close>=lo.next)out.short.push('收敛三角向下突破');}
 let piv=[];for(let j=Math.max(3,i-90);j<=i-4;j++){const n=a.slice(j-3,j+4),c=a[j],type=n.every((x,k)=>k===3||c.high>x.high)?'H':n.every((x,k)=>k===3||c.low<x.low)?'L':null;
  if(type){const p={type,j,price:type==='H'?c.high:c.low};if(piv.at(-1)?.type===type){if(type==='H'?p.price>piv.at(-1).price:p.price<piv.at(-1).price)piv[piv.length-1]=p;}else piv.push(p);}}
 const p=piv.slice(-5);if(p.length===5){const[a,v,h,w,c]=p,tol=(b.atr??1)*.7,neck=w.price+(w.price-v.price)/(w.j-v.j)*(i-w.j);
  if(p.map(x=>x.type).join('')==='HLHLH'&&h.price>Math.max(a.price,c.price)+tol&&Math.abs(a.price-c.price)<=tol&&b.close<neck&&b.previous.close>=neck)out.short.push('已确认头肩顶跌破颈线');
  if(p.map(x=>x.type).join('')==='LHLHL'&&h.price<Math.min(a.price,c.price)-tol&&Math.abs(a.price-c.price)<=tol&&b.close>neck&&b.previous.close<=neck)out.long.push('已确认头肩底突破颈线');}
 return out;}
export function prepare(minutes){const five=indicators(aggregate(minutes,5)),fifteen=indicators(aggregate(minutes,15)),hour=indicators(aggregate(minutes,60));let j=-1,k=-1;
 for(const f of five){while(j+1<fifteen.length&&fifteen[j+1].end<=f.end)j++;while(k+1<hour.length&&hour[k+1].end<=f.end)k++;f.medium=fifteen[j]??null;f.slow=hour[k]??null;f.pattern=j>=0?patterns(fifteen,j):{long:[],short:[]};}
 return{minutes,five,fifteen,hour,byEnd:new Map(five.map(f=>[f.end,f]))};}
export function macroAt(rows,t){let lo=0,hi=rows.length;while(lo<hi){const m=(lo+hi)>>1;if(rows[m].availableMinute<=t)lo=m+1;else hi=m;}const r=rows[lo-1];return r&&t-r.availableMinute<=14400?r:null;}
function factors(f,d,model,mac,mode,carry=false){const m=f.medium,h=f.slow,p=f.previous,aligned=d*(m.ema8-m.ema21)>0&&d*m.slope8>0,slow=d*(h.ema10-h.ema30)>0&&d*h.slope10>0;
 const trend=model.family==='reversion'?((d*(m.close-m.ema21)>=-m.atr*.5?15:0)+(d*(h.ema10-h.ema30)>=-h.atr*.5?15:0)):(aligned?15:0)+(slow?15:0),pat=f.pattern[d===1?'long':'short'];
 const momentum=(d*(f.close-f.ema8)>0?5:0)+(d*(f.close-p.close)>0?5:0)+((d===1?f.close>p.high:f.close<p.low)?5:0);
 const rows=[{key:'trend',label:'15/60分钟方向',points:trend,max:30},{key:'momentum',label:'5分钟动量',points:momentum,max:15},{key:'setup',label:carry?'持仓趋势延续':model.name,points:10+(pat.length?10:0),max:20},{key:'liquidity',label:'量与波动',points:(f.volume>=100?5:0)+(f.atr>0?5:0)+(f.high-f.low<=f.atr*1.5?5:0),max:15},{key:'auxiliary',label:'放量/增仓辅助',points:(f.volume10&&f.volume>=f.volume10*1.1?3:0)+(f.oi>p.oi?2:0),max:5}];
 const mp=mode==='lagged'&&mac?.realChange5!=null?(-d*mac.realChange5>=.03?10:0)+(-d*mac.nominalChange5>=.03?5:0):0;
 rows.push({key:'macro',label:mode==='off'?'美债因子关闭':mac?'滞后美债变化（当前历史版本）':'美债缺失/过期',points:mp,max:15});return rows;}
export function evaluate(f,d,model,mac=null,mode='off'){const m=f?.medium,h=f?.slow,p=f?.previous;if(!p||f.atr==null||m?.ema21==null||h?.ema30==null)return null;
 const aligned=d*(m.ema8-m.ema21)>0&&d*m.slope8>0,slow=d*(h.ema10-h.ema30)>0&&d*h.slope10>0;let event=false,reason='';
 if(model.family==='pullback'){event=aligned&&slow&&(d===1?p.low<=p.ema8&&f.close>p.high:p.high>=p.ema8&&f.close<p.low);reason='15/60分钟同向，5分钟回踩后突破前K线';}
 if(model.family==='breakout'){event=slow&&m.previous?.donchianHigh!=null&&(d===1?m.close>m.donchianHigh&&m.previous.close<=m.previous.donchianHigh:m.close<m.donchianLow&&m.previous.close>=m.previous.donchianLow);reason='15分钟突破此前20根区间，60分钟同向';}
 if(model.family==='reversion'){event=p.mid!=null&&(d===1?p.close<p.mid-2*p.sd&&f.close>f.mid-2*f.sd&&p.rsi<35:p.close>p.mid+2*p.sd&&f.close<f.mid+2*f.sd&&p.rsi>65)&&Math.abs(m.ema8-m.ema21)<m.atr*.5;reason='5分钟布林重新入轨、RSI极值且15分钟弱趋势';}
 if(!event)return null;const rows=factors(f,d,model,mac,mode);return{direction:d,score:rows.reduce((s,r)=>s+r.points,0),factors:rows,patterns:f.pattern[d===1?'long':'short'],reason,signalMinute:f.end,signalTime:stamp(f.end),atr:f.atr,mediumEnd:m.end,slowEnd:h.end,macro:mode==='lagged'?mac:null};}
export function wilson(w,n){if(!n)return null;const z=1.95996398454,p=w/n,den=1+z*z/n,c=(p+z*z/(2*n))/den,d=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;return[c-d,c+d];}
export function summarize(a){const w=a.filter(t=>t.netPnl>0),l=a.filter(t=>t.netPnl<0),gain=w.reduce((s,t)=>s+t.netPnl,0),loss=-l.reduce((s,t)=>s+t.netPnl,0);return{trades:a.length,wins:w.length,winRate:a.length?w.length/a.length:null,winInterval:wilson(w.length,a.length),netPnl:money(gain-loss),profitFactor:loss?gain/loss:null,averageWin:w.length?gain/w.length:null,averageLoss:l.length?loss/l.length:null,expectancy:a.length?(gain-loss)/a.length:null};}
export function calibrate(a){return[60,70,80,90].map(low=>{const high=low===90?100:low+9,b=a.filter(t=>t.score>=low&&t.score<=high);return{low,high,...summarize(b),status:b.length>=30?'descriptive_only':'insufficient_sample'};});}
export function simulate(prepared,settlements,model,overrides={}){
 const c={...DEFAULTS,...overrides};if(c.capital!==300000||!(c.maxRiskCny>0&&c.maxRiskCny<=3000)||!(c.marginRate>0)||!(c.riskFraction>0&&c.riskFraction<=.01))throw Error('Fixed 300k / 1 lot / max 3000 risk');
 const minutes=prepared.minutes.filter(m=>m.day>=(c.start??'')&&m.day<=(c.end??'9999'));let balance=c.capital,pos=null,day=null,dayEquity=c.capital,entries=0,blocked=false,cooldown=-Infinity,peak=c.capital,maxDD=0,maxDDfraction=0,minEquity=c.capital,maxMargin=0,exposure=0;
 const trades=[],ledger=[],curve=[],carryDecisions=[],skipCounts={};const skip=r=>skipCounts[r]=(skipCounts[r]??0)+1,slip=c.slippageTicks*.02;
 const equity=price=>balance+(pos?pos.direction*(price-pos.basis)*1000:0);
 const track=price=>{const e=equity(price);peak=Math.max(peak,e);maxDD=Math.max(maxDD,peak-e);maxDDfraction=Math.max(maxDDfraction,(peak-e)/peak);minEquity=Math.min(minEquity,e);maxMargin=Math.max(maxMargin,pos?price*1000*c.marginRate:0);};
 const close=(m,raw,reason)=>{const p=pos,price=p.direction===1?down(raw-slip):up(raw+slip),fee=p.entryDay===m.day?c.closeTodayFee:c.closeOvernightFee,variation=p.direction*(price-p.basis)*1000;balance=money(balance+variation-fee);
  const trade={...p,exit:stamp(m.t),exitMinute:m.t,exitDay:m.day,exitPrice:money(price),closeFee:fee,netPnl:money(p.direction*(price-p.entryPrice)*1000-p.openFee-fee),reason,overnight:p.entryDay!==m.day,carried:carryDecisions.some(x=>x.entryMinute===p.entryMinute&&x.hold)};trade.lossOverPlan=-trade.netPnl>p.plannedRisk+.01;trades.push(trade);
  ledger.push({time:stamp(m.t),t:m.t,day:m.day,type:'close',direction:p.direction,price:money(price),basis:money(p.basis),variation:money(variation),fee,balance,position:0,reason,entryMinute:p.entryMinute});pos=null;cooldown=m.t+5;track(price);};
 for(const m of minutes){if(m.day!==day){day=m.day;dayEquity=equity(m.open);entries=0;blocked=false;}const f=prepared.byEnd.get(m.t),hm=stamp(m.t).slice(11);let closed=false;
  track(m.open);
  if(pos){let why=pos.forcedExit??null;if(equity(m.open)<m.open*1000*c.marginRate){why='保证金不足强平模拟';blocked=true;}
   if(equity(m.open)<=dayEquity*(1-c.dailyLossFraction)){why='交易日亏损2%退出';blocked=true;}if(m.day>=c.exitOnOrAfter)why='交割月前保守退出';
   if(f&&model.family!=='reversion'&&f.medium?.ema21!=null&&pos.direction*(f.medium.ema8-f.medium.ema21)<0)why='15分钟趋势反转';
   if(hm==='14:55'||hm==='02:25'){const latest=f??prepared.five.findLast(b=>b.end<=m.t),mac=macroAt(c.macroRows??[],m.t);let score=0;
    if(latest?.medium?.ema21!=null&&latest?.slow?.ema30!=null){const rows=factors(latest,pos.direction,model,mac,c.macroMode,true);score=rows.reduce((s,r)=>s+r.points,0);}
    const hold=model.family!=='reversion'&&score>=c.carryScore&&!why&&equity(m.open)>m.open*1000*c.marginRate*(1+c.marginBuffer);carryDecisions.push({time:stamp(m.t),t:m.t,entryMinute:pos.entryMinute,score,hold});if(!hold)why='尾盘未通过80分跨时段门槛';}
   if(why){if(m.volume>0){close(m,m.open,why);closed=true;}else pos.forcedExit=why;}
   else if(f&&model.family!=='reversion'&&pos.direction*(f.close-pos.entryPrice)>=pos.initialDistance){const trail=pos.direction===1?down(f.close-f.atr*2):up(f.close+f.atr*2);pos.stop=pos.direction===1?Math.max(pos.stop,trail):Math.min(pos.stop,trail);}
  }
  if(!pos&&!closed&&f&&m.t>=cooldown&&m.day<c.noNewOnOrAfter){const allowed=c.entryWindow==='any'||session(m.t)===c.entryWindow,late=hm>='14:45'&&hm<'21:00'||hm>='02:15'&&hm<'09:00';
   if(allowed&&!late&&!blocked&&entries<c.maxEntriesPerDay){const mac=macroAt(c.macroRows??[],m.t),signals=[1,-1].map(d=>evaluate(f,d,model,mac,c.macroMode)).filter(Boolean).sort((a,b)=>b.score-a.score),s=signals[0];
    if(s){if(s.score<c.minScore)skip('score');else if(f.volume<100)skip('liquidity');else if(m.volume<1)skip('no_execution_volume');else{
     const price=s.direction===1?up(m.open+slip):down(m.open-slip),distance=Math.max(.02,f.atr*model.atrMultiple),stop=s.direction===1?down(f.close-distance):up(f.close+distance),diff=s.direction*(price-stop),plannedRisk=money((diff+slip)*1000+c.openFee+Math.max(c.closeTodayFee,c.closeOvernightFee)),budget=Math.min(c.maxRiskCny,Math.max(0,equity(m.open))*c.riskFraction);
     if(diff<=0)skip('gap_past_stop');else if(plannedRisk>budget+.001)skip('risk');else if(balance-c.openFee<price*1000*c.marginRate*(1+c.marginBuffer))skip('margin');else{
      balance=money(balance-c.openFee);pos={direction:s.direction,lots:1,entry:stamp(m.t),entryMinute:m.t,entryDay:m.day,entrySession:session(m.t),entryPrice:money(price),basis:money(price),stop:money(stop),initialStop:money(stop),initialDistance:diff,target:money(s.direction===1?up(price+diff*model.targetR):down(price-diff*model.targetR)),plannedRisk,riskBudget:money(budget),openFee:c.openFee,score:s.score,factors:s.factors,patterns:s.patterns,signalTime:s.signalTime,signalMinute:s.signalMinute,mediumEnd:s.mediumEnd,slowEnd:s.slowEnd,macro:s.macro};entries++;
      ledger.push({time:stamp(m.t),t:m.t,day:m.day,type:'open',direction:s.direction,price:money(price),basis:money(price),variation:0,fee:c.openFee,balance,position:s.direction,reason:s.reason,plannedRisk,score:s.score,entryMinute:m.t});
     }
    }}
   }}
  // All decisions above know only this minute's open and previously CLOSED indicators.
  // The unknown intraminute path is resolved conservatively: stop first if both touched.
  if(pos&&m.volume>0){const stop=pos.direction===1?m.low<=pos.stop:m.high>=pos.stop,target=pos.direction===1?m.high>=pos.target:m.low<=pos.target;
   if(stop)close(m,pos.direction===1?Math.min(m.open,pos.stop):Math.max(m.open,pos.stop),'保护止损（双触发先止损）');else if(target)close(m,pos.target,'固定R止盈');else{track(pos.direction===1?m.low:m.high);track(pos.direction===1?m.high:m.low);}}
  if(pos)exposure++;track(m.close);
  if(equity(m.close)<=dayEquity*(1-c.dailyLossFraction)){blocked=true;if(pos)pos.forcedExit='交易日亏损2%延迟退出';}
  if(hm==='14:59'&&pos){const settle=settlements[m.day];if(!Number.isFinite(settle))throw Error('Missing settlement '+m.day);const variation=pos.direction*(settle-pos.basis)*1000;balance=money(balance+variation);ledger.push({time:stamp(m.t+1),t:m.t+1,day:m.day,type:'settlement',direction:pos.direction,price:settle,basis:pos.basis,variation:money(variation),fee:0,balance,position:pos.direction,entryMinute:pos.entryMinute,reason:'逐日盯市'});pos.basis=settle;}
  const e=equity(m.close),margin=pos?m.close*1000*c.marginRate:0;curve.push({t:m.t,day:m.day,equity:money(e),balance:money(balance),margin:money(margin),available:money(e-margin),position:pos?.direction??0,stop:pos?.stop??null});
 }
 const last=minutes.at(-1),nav=last?equity(last.close):balance,realized=trades.reduce((s,t)=>s+t.netPnl,0),buckets={};
 for(const t of trades){const p=t.entryDay<=SPLIT.trainEnd?'train':t.entryDay<=SPLIT.validationEnd?'validation':'test';(buckets[p]??=[]).push(t);}
 return{config:{...c,macroRows:undefined},model,metrics:{...summarize(trades),totalPnl:money(nav-c.capital),unrealized:money(nav-c.capital-realized),finalEquity:money(nav),return:(nav-c.capital)/c.capital,maxDrawdown:money(maxDD),maxDrawdownFraction:maxDDfraction,minEquity:money(minEquity),maxMargin:money(maxMargin),openLots:pos?.direction??0,exposureMinutes:exposure,lossOverPlan:trades.filter(t=>t.lossOverPlan).length,daysWithEntries:new Set(ledger.filter(x=>x.type==='open').map(x=>x.day)).size},trades,ledger,curve,position:pos,skipCounts,carryDecisions,periods:Object.fromEntries(['train','validation','test'].map(p=>[p,summarize(buckets[p]??[])])),sessions:Object.fromEntries(['day','night'].map(p=>[p,summarize(trades.filter(t=>t.entrySession===p))])),directions:{long:summarize(trades.filter(t=>t.direction===1)),short:summarize(trades.filter(t=>t.direction===-1))},calibration:calibrate(trades),testCalibration:calibrate(buckets.test??[])};
}
