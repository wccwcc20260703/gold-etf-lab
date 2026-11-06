import {MODELS,simulate,features,startTime,DEFAULTS} from './engine.js';
const $=id=>document.getElementById(id),pct=n=>n==null?'—':`${(n*100).toFixed(2)}%`,money=n=>Number(n).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});
await new Promise(resolve=>document.readyState==='loading'?document.addEventListener('DOMContentLoaded',resolve,{once:true}):resolve());
const data=await fetch('data.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(`数据读取失败 ${r.status}`);return r.json();}).catch(e=>{$('error').textContent=e.message;throw e;});
let result,currentFund,charts={};
const chartTheme={textStyle:{fontFamily:'-apple-system,PingFang SC,sans-serif',fontSize:10,color:'#7e8992'},animation:false,grid:{left:55,right:18,top:25,bottom:40},tooltip:{trigger:'axis'},xAxis:{type:'category',axisLine:{lineStyle:{color:'#dfe5de'}},axisTick:{show:false},axisLabel:{fontSize:9}},yAxis:{scale:true,axisLine:{show:false},axisLabel:{fontSize:9},splitLine:{lineStyle:{color:'#eff1ec'}}}};
function draw(id,options){charts[id]??=window.echarts.init($(id));charts[id].setOption({...chartTheme,...options},true);}
function candlesticks(bars){return bars.map(b=>[b[1],b[4],b[3],b[2]]);}
function currentDay(){return currentFund.sessions.find(s=>s.date===$('day').value)??currentFund.sessions.at(-1);}
function renderDay(){
 const session=currentDay();if(!session)return;$('day').value=session.date;$('day-title').textContent=`${session.date} · 日内成交复盘`;
 const bars=session.bars,x=bars.map(b=>startTime(b[0]).slice(11)),f=features(bars),fills=result.fills.filter(v=>v.time.startsWith(session.date));
 draw('intraday',{xAxis:{...chartTheme.xAxis,data:x},series:[{name:'价格',type:'candlestick',data:candlesticks(bars),itemStyle:{color:'#b8665c',color0:'#4c8b7c',borderColor:'#b8665c',borderColor0:'#4c8b7c'}},{name:'当日均价',type:'line',data:f.map(v=>v.vwap),showSymbol:false,lineStyle:{color:'#b39455',width:1.2}},{name:'买入',type:'scatter',symbol:'triangle',symbolSize:10,itemStyle:{color:'#c16e51'},data:fills.filter(t=>t.side==='buy').map(t=>[t.time.slice(11),t.price])},{name:'卖出',type:'scatter',symbol:'triangle',symbolRotate:180,symbolSize:10,itemStyle:{color:'#347e77'},data:fills.filter(t=>t.side==='sell').map(t=>[t.time.slice(11),t.price])}]});
 $('fills').innerHTML=fills.length?fills.map(t=>`<tr><td>${t.time.slice(11)}</td><td class="${t.side==='buy'?'negative':'positive'}">${t.side==='buy'?'买入':'卖出'}</td><td>${t.quantity.toLocaleString()}</td><td>${t.price.toFixed(3)}</td><td>${money(t.fee)}</td><td>${money(t.cashAfter)}</td><td>${t.sharesAfter.toLocaleString()}</td><td>${t.reason}</td></tr>`).join(''):'<tr><td colspan="8">本交易日没有模拟成交。</td></tr>';
}
function ranking(){
 const trials=data.trials.filter(t=>t.code===currentFund.code);
 $('ranking').innerHTML=trials.map(t=>{const a=t.periods.all,b=t.periods.test;return `<tr><td><a href="#research" data-model="${t.model}">${t.name}</a></td><td>${a.trades}</td><td>${pct(a.winRate)}</td><td class="${a.totalPnl>=0?'positive':'negative'}">${money(a.totalPnl)}</td><td>${b.trades}</td><td>${pct(b.winRate)}</td><td class="${b.totalPnl>=0?'positive':'negative'}">${money(b.totalPnl)}</td><td class="${b.stressPnl>=0?'positive':'negative'}">${money(b.stressPnl)}</td></tr>`;}).join('');
 $('ranking').querySelectorAll('[data-model]').forEach(a=>a.addEventListener('click',()=>{$('model').value=a.dataset.model;run();}));
}
function run(){
 $('error').textContent='';currentFund=data.funds.find(f=>f.code===$('fund').value);
 const start=$('start').value,end=$('end').value;if(start>end){$('error').textContent='开始日期不能晚于结束日期。';return;}
 const sessions=currentFund.sessions.filter(s=>s.date>=start&&s.date<=end);if(!sessions.length){$('error').textContent='所选区间没有完整的真实5分钟行情。';return;}
 const config={capital:+$('capital').value,commission:+$('commission').value/10000,minCommission:+$('minimum').value,slippage:+$('slip').value};
 if(config.capital<1000||config.commission<0||config.minCommission<0){$('error').textContent='请输入有效的本金和费用。';return;}
 const model=MODELS.find(m=>m.id===$('model').value);result=simulate(sessions,model,config);const m=result.metrics;
 const cells=[['区间净收益',money(m.totalPnl),pct(m.return)],['扣费胜率',pct(m.winRate),m.trades?`${m.wins}胜 / ${m.trades}轮`:'没有完成交易'],['5分钟最大回撤',pct(m.maxDrawdown),'按收盘估值'],['每轮平均净收益',money(m.meanPnl),pct(m.meanTradeReturn)],['累计佣金',money(m.fees),'成交滑点已计入价格'],['期末持仓',`${result.curve.at(-1)?.shares??0} 份`,m.failed?'清仓失败，模拟停止':'收盘现金账户']];
 $('metrics').innerHTML=cells.map(([label,value,note],i)=>`<article><span>${label}</span><strong class="${(i===0||i===3)&&m.totalPnl<0?'negative':''}">${value}</strong><small>${note}</small></article>`).join('');
 $('run-note').textContent=`${sessions.length}个交易日 · 无年化推断`;
 const sampled=result.curve.map(p=>[p.time,p.nav/config.capital*100]);
 draw('equity',{xAxis:{...chartTheme.xAxis,data:sampled.map(p=>p[0]),axisLabel:{formatter:v=>v.slice(5,10),fontSize:9}},yAxis:{...chartTheme.yAxis,axisLabel:{formatter:v=>`${v.toFixed(1)}`,fontSize:9}},dataZoom:[{type:'inside',start:0,end:100}],series:[{name:'研究候选净值',type:'line',data:sampled.map(p=>p[1]),showSymbol:false,lineStyle:{color:'#b18b43',width:1.8},areaStyle:{color:'rgba(177,139,67,.06)'},markLine:{silent:true,symbol:'none',label:{show:false},lineStyle:{color:'#bec7c5',type:'dashed',width:1},data:[{yAxis:100}]}}]});
 const daily=currentFund.daily.filter(b=>b[0]>=sessions[0].date&&b[0]<=sessions.at(-1).date);
 draw('daily',{xAxis:{...chartTheme.xAxis,data:daily.map(b=>b[0]),axisLabel:{formatter:v=>v.slice(5),fontSize:9}},series:[{type:'candlestick',data:candlesticks(daily),itemStyle:{color:'#b8665c',color0:'#4c8b7c',borderColor:'#b8665c',borderColor0:'#4c8b7c'}}]});
 charts.daily.off('click');charts.daily.on('click',event=>{if(currentFund.sessions.some(s=>s.date===event.name)){$('day').value=event.name;renderDay();}});
 const firstTrade=result.trades[0]?.date;$('day').value=firstTrade??sessions.at(-1).date;$('day').min=sessions[0].date;$('day').max=sessions.at(-1).date;
 renderDay();ranking();
}
$('fund').innerHTML=data.funds.map(f=>`<option value="${f.code}">${f.code} ${f.name}</option>`).join('');
$('model').innerHTML=MODELS.map(m=>`<option value="${m.id}">${m.name}</option>`).join('');$('model').value=data.freeze.model;
$('start').value=data.coverage.start;$('end').value=data.coverage.end;$('days').textContent=`${data.coverage.dates} 个交易日`;$('range').textContent=`${data.coverage.start} — ${data.coverage.end}`;
$('forward-count').textContent=`${data.forward.find(f=>f.code==='518880').days} 个交易日`;
$('coverage-warning').textContent=`真实分钟目前仅覆盖${data.coverage.dates}个交易日，首版属于方法筛选。日线覆盖更长，但没有用日线补造分钟成交；暂无足够证据支持“高胜率模型”。`;
$('build-time').textContent=`行情截至 ${data.coverage.end}`;
$('split-note').textContent=`按时间顺序划分：训练段 ${data.coverage.start}至${data.coverage.trainEnd}；选择段截至${data.coverage.validationEnd}；其后为后段观察。候选参数与规则在查看首轮回测结果前确定，仍属于本轮历史探索。`;
$('freeze-title').textContent=`冻结候选：${MODELS.find(m=>m.id===data.freeze.model).name}`;
$('freeze-note').textContent=`冻结截止 ${data.freeze.frozenAfter}。训练与选择段没有候选满足最小样本和盈利筛选，本版预先指定的顺势回踩基线仅用于后续影子记录，默认状态为空仓。`;
$('freeze-hash').textContent=`规则哈希 ${data.freeze.hash}`;
const forward=data.forward.find(f=>f.code==='518880');const g=forward.gate.checks;
$('gate-list').innerHTML=[['新增完整交易日 ≥ 60',`${forward.days} / 60`],['新增完成交易 ≥ 100',`${forward.trades.length} / 100`],['扣费胜率 ≥ 60%，盈利因子 ≥ 1.2',g.winRate&&g.profitFactor?'已达到':'待积累'],['最大回撤 ≤ 3%，成本压力后仍盈利',g.drawdown&&g.costStress?'已达到':'待验证'],['清仓执行完整',g.flat?'当前无失败':'未通过']].map(([a,b])=>`<div class="gate"><span>${a}</span><span>${b}</span></div>`).join('');
$('quality').innerHTML=data.quality.map(q=>`<span class="quality-chip">${q.code} · ${q.completeDays}日 / ${q.rows}根 · 收盘差异超过1跳 ${q.closeMismatchOverOneTick}日</span>`).join('');
$('sources').innerHTML=data.sources.map(s=>`<a href="${s.url}" target="_blank" rel="noreferrer">${s.title} ↗</a>`).join('');
$('controls').addEventListener('submit',e=>{e.preventDefault();run();});$('fund').addEventListener('change',run);$('day').addEventListener('change',renderDay);
$('export').addEventListener('click',()=>{if(!result)return;const fields=['time','signalTime','side','quantity','price','fee','cashBefore','cashAfter','sharesBefore','sharesAfter','reason'];const lines=[fields.join(','),...result.fills.map(t=>fields.map(k=>JSON.stringify(t[k]??'')).join(','))];const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`${currentFund.code}-${result.model}-fills.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));run();
