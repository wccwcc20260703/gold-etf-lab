export const FAMILIES={vwap_revert:'均价偏离回归',vwap_reclaim:'均价收复确认',orb:'早盘区间突破',ema_pullback:'顺势回踩',bollinger_rsi:'布林带 / RSI反转'};
export const MODELS=Object.keys(FAMILIES).flatMap(family=>['balanced','high_hit'].map(profile=>({id:`${family}_${profile}`,family,profile,name:`${FAMILIES[family]} · ${profile==='balanced'?'均衡止盈':'小目标对照'}`})));
export const DEFAULTS={capital:100000,commission:.00025,minCommission:5,slippage:.0002,maxAllocation:.5,riskPerTrade:.0015,dailyLossLimit:.006,maxTrades:3,maxConsecutiveLosses:2,participation:.01};
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const floorLot=n=>Math.floor((n+1e-9)/100)*100;
const tradable=(b,session)=>b[5]>0&&!(b[2]===b[3]&&session.prevClose&&Math.abs(b[1]/session.prevClose-1)>=.099);
export function fillPrice(p,buy,slippage){return (buy?Math.ceil((p*(1+slippage))/.001-1e-8):Math.floor((p*(1-slippage))/.001+1e-8))*.001;}
export function startTime(end){const [date,clock]=end.split(' ');const [h,m]=clock.split(':').map(Number);const n=h*60+m-5;return `${date} ${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;}
export function features(bars){
 let v=0,a=0,ema5=0,ema13=0;const result=[];
 for(let i=0;i<bars.length;i++){
  const b=bars[i];v+=b[5];a+=b[6];ema5=i?ema5+(b[4]-ema5)/3:b[4];ema13=i?ema13+(b[4]-ema13)/7:b[4];
  const window=bars.slice(Math.max(0,i-11),i+1).map(x=>x[4]);const mid=mean(window);const sd=Math.sqrt(mean(window.map(x=>(x-mid)**2)));
  const tr=bars.slice(Math.max(0,i-13),i+1).map((x,j)=>{const k=Math.max(0,i-13)+j;return Math.max(x[2]-x[3],k?Math.abs(x[2]-bars[k-1][4]):0,k?Math.abs(x[3]-bars[k-1][4]):0);});
  let gain=0,loss=0;for(let k=Math.max(1,i-5);k<=i;k++){const d=bars[k][4]-bars[k-1][4];gain+=Math.max(0,d);loss+=Math.max(0,-d);}
  const vwap=v?a/v:b[4];result.push({vwap,ema5,ema13,mid,lower:mid-2*sd,rsi:loss?100-100/(1+gain/loss):gain?100:50,atr:mean(tr),slope:i>=3?vwap/result[i-3].vwap-1:0});
 }
 return result;
}
export function entrySignal(model,bars,f,i){
 if(i<6||bars[i][0].slice(11)>'14:20')return false;
 const b=bars[i],p=bars[i-1],x=f[i],y=f[i-1];
 if(model.family==='vwap_revert')return b[4]<x.vwap*.998&&b[4]>p[4]&&Math.abs(x.slope)<.001;
 if(model.family==='vwap_reclaim')return p[4]<=y.vwap&&b[4]>x.vwap*1.0002&&x.slope>0;
 if(model.family==='orb'){const hi=Math.max(...bars.slice(0,6).map(v=>v[2]));return p[4]<=hi&&b[4]>hi&&b[4]>x.vwap&&b[5]>=mean(bars.slice(i-5,i).map(v=>v[5]))*1.1;}
 if(model.family==='ema_pullback')return x.ema5>x.ema13&&x.slope>0&&p[3]<=y.ema5&&b[4]>p[2]&&b[4]>=x.vwap;
 if(model.family==='bollinger_rsi')return i>=12&&p[4]<y.lower&&b[4]>x.lower&&x.rsi<40&&b[4]>p[4];
 return false;
}
export function metrics(trades,curve,capital,days,failed=false){
 const profits=trades.map(t=>t.pnl),wins=profits.filter(x=>x>0).length,n=profits.length,p=n?wins/n:0,z=1.96;
 const denom=1+z*z/Math.max(1,n),center=(p+z*z/(2*Math.max(1,n)))/denom,rad=z*Math.sqrt(p*(1-p)/Math.max(1,n)+z*z/(4*Math.max(1,n)**2))/denom;
 const sumWin=profits.filter(x=>x>0).reduce((s,x)=>s+x,0),sumLoss=-profits.filter(x=>x<0).reduce((s,x)=>s+x,0);let peak=capital,dd=0;
 for(const point of curve){peak=Math.max(peak,point.nav);dd=Math.max(dd,1-point.nav/peak);}
 const end=curve.at(-1)?.nav??capital;
 return {trades:n,wins,winRate:n?p:null,winLow:n?Math.max(0,center-rad):null,winHigh:n?Math.min(1,center+rad):null,totalPnl:end-capital,return:end/capital-1,maxDrawdown:dd,meanPnl:n?mean(profits):0,profitFactor:sumLoss?sumWin/sumLoss:null,fees:trades.reduce((s,t)=>s+t.fees,0),days,failed,meanTradeReturn:n?mean(trades.map(t=>t.pnl/t.entryNotional)):0};
}
export function simulate(sessions,model,options={}){
 const cfg={...DEFAULTS,...options};let cash=cfg.capital,shares=0,position=null,pendingEntry=null,pendingExit=null,failed=false;
 const fills=[],trades=[],curve=[],daySummaries=[];
 for(const session of sessions){
  const bars=session.bars;if(bars.length!==48)continue;const f=features(bars);const dayStart=cash;let count=0,lossStreak=0,locked=false;
  for(let i=0;i<bars.length;i++){
   const b=bars[i],time=startTime(b[0]),clock=time.slice(11),prior=i?bars[i-1]:null;
   if(shares&&(pendingExit||clock>='14:50')){
    const quantity=prior&&tradable(b,session)?Math.min(shares,floorLot(prior[5]*cfg.participation)):0;
    if(quantity>0){
     const price=fillPrice(b[1],false,cfg.slippage),fee=Math.max(cfg.minCommission,quantity*price*cfg.commission),beforeCash=cash,beforeShares=shares;
     cash+=quantity*price-fee;shares-=quantity;position.proceeds+=quantity*price-fee;position.fees+=fee;position.exitQuantity+=quantity;
     fills.push({time,signalTime:pendingExit?.signalTime??`${session.date} 14:50`,side:'sell',quantity,price,fee,cashBefore:beforeCash,cashAfter:cash,sharesBefore:beforeShares,sharesAfter:shares,reason:pendingExit?.reason??'收盘清仓'});
     if(!shares){const pnl=position.proceeds-position.cost;const trade={date:session.date,entryTime:position.time,exitTime:time,quantity:position.quantity,entryPrice:position.entryPrice,exitPrice:(position.proceeds+position.fees-position.entryFee)/position.quantity,entryNotional:position.entryNotional,pnl,fees:position.fees,reason:pendingExit?.reason??'收盘清仓'};trades.push(trade);lossStreak=pnl<0?lossStreak+1:0;if(lossStreak>=cfg.maxConsecutiveLosses)locked=true;position=null;pendingExit=null;}
    }
   }
   if(pendingEntry&&!shares&&!locked&&clock<'14:30'){
    const price=fillPrice(b[1],true,cfg.slippage),stopFraction=pendingEntry.stopFraction;
    const perShareRisk=price*(stopFraction+2*cfg.slippage+2*cfg.commission)+.002;
    let q=floorLot(Math.min(cash*cfg.maxAllocation/price,cash*cfg.riskPerTrade/perShareRisk,(prior?.[5]??0)*cfg.participation));
    while(q>0&&q*price+Math.max(cfg.minCommission,q*price*cfg.commission)>cash)q-=100;
    if(q>0&&tradable(b,session)){const fee=Math.max(cfg.minCommission,q*price*cfg.commission),beforeCash=cash;cash-=q*price+fee;shares=q;count++;
     position={time,index:i,quantity:q,entryPrice:price,entryNotional:q*price,cost:q*price+fee,entryFee:fee,fees:fee,proceeds:0,exitQuantity:0,stopFraction,targetFraction:stopFraction*(model.profile==='balanced'?1.5:.8),maxBars:model.profile==='balanced'?12:6};
     fills.push({time,signalTime:pendingEntry.signalTime,side:'buy',quantity:q,price,fee,cashBefore:beforeCash,cashAfter:cash,sharesBefore:0,sharesAfter:q,reason:FAMILIES[model.family]});
    }
   }
   pendingEntry=null;
   const nav=cash+shares*b[4];curve.push({time:b[0],nav,shares,cash});
   if(nav/dayStart-1<=-cfg.dailyLossLimit){locked=true;if(shares)pendingExit={reason:'日亏损熔断',signalTime:b[0]};}
   if(shares&&!pendingExit){const change=b[4]/position.entryPrice-1;let reason=null;
    if(change<=-position.stopFraction)reason='止损';else if(change>=position.targetFraction)reason='止盈';else if(i-position.index+1>=position.maxBars)reason='时间止损';
    if(reason)pendingExit={reason,signalTime:b[0]};
   }
   if(!shares&&!locked&&count<cfg.maxTrades&&entrySignal(model,bars,f,i)){
    const multiplier=model.profile==='balanced'?1.5:2;
    pendingEntry={signalTime:b[0],stopFraction:Math.max(.0015,Math.min(.006,f[i].atr/b[4]*multiplier))};
   }
  }
  daySummaries.push({date:session.date,startNav:dayStart,endNav:curve.at(-1).nav,roundTrips:count,locked,closingShares:shares});
  pendingEntry=null;
  if(shares){failed=true;break;} // Keep the exposure visible; never reset an unfilled exit.
 }
 return {model:model.id,config:cfg,fills,trades,curve,daySummaries,metrics:metrics(trades,curve,cfg.capital,daySummaries.length,failed)};
}
export function admission(result,stress){const m=result.metrics;return {passed:!m.failed&&m.days>=60&&m.trades>=100&&m.winRate>=.6&&m.totalPnl>0&&m.profitFactor>=1.2&&m.maxDrawdown<=.03&&stress.metrics.totalPnl>0,checks:{flat:!m.failed,days:m.days>=60,trades:m.trades>=100,winRate:m.winRate>=.6,profitable:m.totalPnl>0,profitFactor:m.profitFactor>=1.2,drawdown:m.maxDrawdown<=.03,costStress:stress.metrics.totalPnl>0}};}
