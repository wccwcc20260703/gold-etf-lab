const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
export function decorate(a){const buffers={},tr=[],dx=[];let previousMacdSignal=null,avgGain=0,avgLoss=0,smTR=0,smUp=0,smDown=0,adx=null;
 for(let i=0;i<a.length;i++){const b=a[i],p=a[i-1];for(const n of[5,8,10,12,20,21,26,30,60]){const e=buffers[n]??=[];e[i]=i<n-1?null:i===n-1?mean(a.slice(0,n).map(x=>x.close)):e[i-1]+2/(n+1)*(b.close-e[i-1]);b['ema'+n]=e[i];}
  b.previous=p??null;for(const n of[8,10])b['slope'+n]=i&&buffers[n][i]!=null&&buffers[n][i-1]!=null?buffers[n][i]-buffers[n][i-1]:0;
  tr.push(p?Math.max(b.high-b.low,Math.abs(b.high-p.close),Math.abs(b.low-p.close)):b.high-b.low);b.atr=i<13?null:i===13?mean(tr.slice(0,14)):(p.atr*13+tr[i])/14;
  const w=a.slice(Math.max(0,i-19),i+1).map(x=>x.close);b.mid=i>=19?mean(w):null;b.sd=i>=19?Math.sqrt(mean(w.map(v=>(v-b.mid)**2))):null;
  if(i>=14){if(i===14){const c=a.slice(1,15).map((x,k)=>x.close-a[k].close);avgGain=mean(c.map(v=>Math.max(0,v)));avgLoss=mean(c.map(v=>Math.max(0,-v)));}else{avgGain=(avgGain*13+Math.max(0,b.close-p.close))/14;avgLoss=(avgLoss*13+Math.max(0,p.close-b.close))/14;}b.rsi=avgLoss?100-100/(1+avgGain/avgLoss):avgGain?100:50;}else b.rsi=null;
  b.macd=b.ema12!=null&&b.ema26!=null?b.ema12-b.ema26:null;
  if(b.macd!=null){previousMacdSignal=previousMacdSignal==null?b.macd:previousMacdSignal+.2*(b.macd-previousMacdSignal);b.macdHist=b.macd-previousMacdSignal;}else b.macdHist=null;
  b.plusDM=p&&b.high-p.high>p.low-b.low?Math.max(0,b.high-p.high):0;b.minusDM=p&&p.low-b.low>b.high-p.high?Math.max(0,p.low-b.low):0;
  if(i>=14){if(i===14){smTR=tr.slice(1,15).reduce((s,x)=>s+x,0);smUp=a.slice(1,15).reduce((s,x)=>s+x.plusDM,0);smDown=a.slice(1,15).reduce((s,x)=>s+x.minusDM,0);}else{smTR=smTR-smTR/14+tr[i];smUp=smUp-smUp/14+b.plusDM;smDown=smDown-smDown/14+b.minusDM;}b.di=(smUp-smDown)/Math.max(smUp+smDown,1e-9);dx.push(100*Math.abs(b.di));adx=dx.length<14?null:dx.length===14?mean(dx):((adx*13+dx.at(-1))/14);b.adx=adx;}else{b.adx=null;b.di=0;}
  b.donchianHigh=i>=20?Math.max(...a.slice(i-20,i).map(x=>x.high)):null;b.donchianLow=i>=20?Math.min(...a.slice(i-20,i).map(x=>x.low)):null;
  b.volume10=i>=10?mean(a.slice(i-10,i).map(x=>x.volume)):null;
 }return a;}
