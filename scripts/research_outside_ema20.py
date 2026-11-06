"""User's EMA20 + full-range outside bar, 120m, mirrored long/short, 3-bar extreme trail.
Reuse independently audited one-lot minute accounting; replace only signal/stop definitions.
"""
import csv,datetime as dt,hashlib,importlib.util,json,math,pathlib
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';OUT=ROOT/'docs/futures/outside';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('account',ROOT/'scripts/research_factors.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
M=r.M;CAL=r.CAL
def bars_for(mode):
    groups={}
    if mode=='trading_minutes':
        count={}
        for i,row in enumerate(M):
            day=int(row[1]);n=count.get(day,0);count[day]=n+1;groups.setdefault((day,n//120),[]).append(i)
    else:
        for i,row in enumerate(M):
            t=int(row[0]);clock=int((t+480)%1440);base=t-clock
            anchor=base+1260 if clock>=1260 else base-180 if clock<150 else base+540
            groups.setdefault((int(row[1]),anchor+(t-anchor)//120*120),[]).append(i)
    bars=[];ema=None
    for ids in groups.values():
        positive=[i for i in ids if M[i,6]>0];active=positive or ids;first=active[0];last=active[-1]
        b={'index':len(bars),'start':int(M[ids[0],0]),'end':int(M[ids[-1],0])+1,'firstIndex':ids[0],'lastIndex':ids[-1],'firstTradeIndex':positive[0] if positive else None,'day':int(M[ids[-1],1]),'open':int(M[first,2]),'high':int(M[active,3].max()),'low':int(M[active,4].min()),'close':int(M[last,5]),'volume':int(M[ids,6].sum()),'tradingMinutes':len(ids)}
        bars.append(b)
        if len(bars)==20:ema=sum(x['close'] for x in bars)/20
        elif len(bars)>20:ema=ema+2/21*(b['close']-ema)
        b['ema20']=ema
    return bars
def signals_for(bars):
    opp=[];raw=[]
    for j in range(19,len(bars)-1):
        b=bars[j];p=bars[j-1]
        if not(b['volume']>0 and p['volume']>0 and b['high']>p['high'] and b['low']<p['low']):continue
        d=1 if b['close']>b['open'] and b['close']>b['ema20'] else -1 if b['close']<b['open'] and b['close']<b['ema20'] else 0
        if not d:continue
        nextbar=bars[j+1];i=nextbar['firstTradeIndex'];row={'signalBar':j,'signalMinute':b['end'],'direction':d,'nextBar':j+1,'entryIndex':i,'signalHigh':b['high'],'signalLow':b['low'],'ema20':b['ema20'],'oppositePrevious':d*(p['close']-p['open'])<0}
        if i is None:raw.append({**row,'entryAvailable':False});continue
        entry=int(M[i,2])+d*2;stop=b['low'] if d==1 else b['high'];distance=d*(entry-stop);risk=(distance+2)*20+40
        raw.append({**row,'entryAvailable':True,'entryMinute':int(M[i,0]),'requiredRiskCny':risk,'within3000':0<distance and risk<=3000})
        opp.append({'id':len(opp),'i':i,'t':int(M[i,0]),'day':int(M[i,1]),'direction':d,'signalBar':j,'nextBar':j+1,'signalMinute':b['end'],'initialStopTicks':stop,'features':[],'patterns':['120分钟完整高低点外包线'],'triggers':['EMA20同向收盘','外包线收阳' if d==1 else '外包线收阴'],'macro':{},'oppositePrevious':row['oppositePrevious']})
    return opp,raw
def run_variant(mode,holding,stress=False):
    bars=bars_for(mode);opp,raw=signals_for(bars);closed=np.searchsorted(np.array([b['end'] for b in bars]),M[:,0],side='right')-1
    r.O=opp;r.N=len(opp);r.DAY=np.array([o['day'] for o in opp]);r.INDEX=np.array([o['i'] for o in opp]);r.PROFILES=[{'id':0,'aggregation':mode,'holding':holding,'period':120,'exitStyle':'three_completed_bar_trail'}]
    r.P={**r.P,'trainTradingDays':0,'validationTradingDays':0,'embargoTradingDays':0}
    def position(oi,profile,is_stress=False):
        o=opp[oi];i=o['i'];d=o['direction'];c=r.costs(is_stress);clock=int(r.CLOCK[i]);late=(885<=clock<1260) or(135<=clock<540)
        if late or r.EVENT_BLOCK[i]:return None
        entry=int(M[i,2])+d*c['slip'];stop=o['initialStopTicks'];distance=d*(entry-stop);risk=(distance+c['slip'])*20+c['open']+c['close']
        if distance<=0 or risk>3000:return None
        return {'opp':oi,'profile':0,'i':i,'direction':d,'entryTicks':entry,'stopTicks':stop,'initialStopTicks':stop,'targetTicks':None,'distance':distance,'plannedRisk':risk,'basisTicks':entry,'entryDay':o['day'],'fee':c['open'],'slip':c['slip'],'closeFee':c['close'],'forced':None,'carryEvents':[],'lastTrailedBar':o['signalBar'],'signalBar':o['signalBar'],'nextBar':o['nextBar'],'stopHistory':[{'minute':int(M[i,0]),'stopTicks':stop,'confirmedBar':o['signalBar'],'reason':'initial_outside_extreme'}]}
    def step(p,i):
        row=M[i];d=p['direction'];k=int(closed[i]);clock=int(r.CLOCK[i])
        if r.EVENT_BLOCK[i]:p['forced']='scheduled_event_exit'
        if CAL[int(row[1])]>='2026-11-30':p['forced']='pre_delivery_exit'
        if i>p['i'] and clock in (895,145):
            trend=k>=0 and bars[k]['ema20'] is not None and d*(bars[k]['close']-bars[k]['ema20'])>0
            hold=holding=='conditional_trend' and trend and not r.NO_CARRY[i]
            p['carryEvents'].append({'minute':int(row[0]),'hold':bool(hold),'trendAligned':bool(trend),'eventOrLongGap':bool(r.NO_CARRY[i]),'confirmedBar':k})
            if not hold:p['forced']='session_exit'
        if k>p['lastTrailedBar'] and k>=2:
            line=min(b['low'] for b in bars[k-2:k+1]) if d==1 else max(b['high'] for b in bars[k-2:k+1]);previous=p['stopTicks'];p['stopTicks']=max(previous,line) if d==1 else min(previous,line);p['lastTrailedBar']=k
            if p['stopTicks']!=previous:p['stopHistory'].append({'minute':int(row[0]),'stopTicks':p['stopTicks'],'confirmedBar':k,'reason':'min3_completed_lows' if d==1 else 'max3_completed_highs'})
        if not row[6]:return None
        if p['forced']:return(int(row[2]),p['forced'],'open')
        hit=row[4]<=p['stopTicks'] if d==1 else row[3]>=p['stopTicks']
        if hit:return(min(int(row[2]),p['stopTicks']) if d==1 else max(int(row[2]),p['stopTicks']),'stop','range')
        return None
    r.new_position=position;r.exit_step=step
    models={day:{'profile':0,'threshold':0,'breakEvenProbability':.5,'confidenceThreshold':60,'probabilities':{o['id']:1 for o in opp if o['day']==day}} for day in range(len(CAL))}
    run=r.oos_account(models,stress)
    # Rule-trigger placeholders are not win forecasts. Never publish artificial confidence100.
    for t in run['trades']:
        t['probability']=None;t['score']=None;t['confidenceStatus']='Raw-rule study; empirical prior frequency only';o=opp[t['opp']];t.update(signalMinute=o['signalMinute'],signalBar=o['signalBar'],nextBar=o['nextBar'])
    for e in run['ledger']:
        if 'probability'in e:e['probability']=None
    for j,t in enumerate(run['trades']):
        prior=[p for p in run['trades'][:j] if p['exitMinute']<t['entryMinute']];wins=sum(p['netPnl']>0 for p in prior);t['priorSample']=len(prior);t['priorWinRate']=wins/len(prior) if len(prior)>=30 else None;t['priorWinInterval']=r.wilson(wins,len(prior)) if len(prior)>=30 else None
    if run['position']:
        run['position']['probability']=None;run['position']['score']=None
    day_summary=[]
    for day in CAL:
        points=[p for p in run['curve'] if p['day']==day];entered=[e for e in run['ledger'] if e['type']=='open' and e['day']==day];finished=[t for t in run['trades'] if t['exitDay']==day]
        if points:day_summary.append({'day':day,'equity':points[-1]['equity'],'margin':points[-1]['margin'],'position':points[-1]['position'],'entries':len(entered),'closedTrades':len(finished),'closedPnl':sum(t['netPnl'] for t in finished)})
    run['daily']=day_summary;run['periods']={name:r.summary([t['netPnl'] for t in run['trades'] if (t['entryDay']<'2026-06-01' if name=='early' else '2026-06-01'<=t['entryDay']<'2026-09-01' if name=='middle' else t['entryDay']>='2026-09-01')]) for name in ('early','middle','recent')};run['directions']={str(d):r.summary([t['netPnl'] for t in run['trades'] if t['direction']==d]) for d in (1,-1)};run['sessions']={s:r.summary([t['netPnl'] for t in run['trades'] if t['entrySession']==s]) for s in ('day','night')}
    risk=[x['requiredRiskCny'] for x in raw if x.get('entryAvailable') and x['requiredRiskCny']>0];quality={'bars':len(bars),'shorterThan120TradingMinutes':sum(b['tradingMinutes']<120 for b in bars),'zeroVolumeBars':sum(b['volume']==0 for b in bars),'ruleSignals':len(raw),'initialRiskWithin3000':sum(x.get('within3000',False) for x in raw),'medianRequiredRisk':float(np.median(risk)) if risk else None,'riskP90':float(np.percentile(risk,90)) if risk else None}
    return run,quality,bars,raw
def main():
    protocol=json.loads((D/'outside-ema20-protocol.json').read_text());spec={'scriptSha256':r.digest(__file__),'accountEngineSha256':r.digest(ROOT/'scripts/research_factors.py'),'minuteInputSha256':r.digest(D/'minute-input.json'),'eventSha256':r.digest(D/'events.json'),'protocol':protocol}
    lock=D/'outside-ema20-freeze.json'
    if lock.exists():assert json.loads(lock.read_text())['specification']==spec
    else:lock.write_text(json.dumps({'createdAt':dt.datetime.now(dt.timezone.utc).isoformat(),'specification':spec},indent=2))
    trials=[];audit=[]
    for mode in ('trading_minutes','session_clock'):
        for holding in ('intraday','conditional_trend'):
            run,quality,bars,raw=run_variant(mode,holding);stress,_,_,_=run_variant(mode,holding,True);name=mode+'_'+holding
            trial={'id':name,'aggregation':mode,'holding':holding,'metrics':run['metrics'],'stressMetrics':stress['metrics'],'periods':run['periods'],'directions':run['directions'],'sessions':run['sessions'],'quality':quality,'skips':run['skips']};trials.append(trial)
            for cost,x in [('base',run),('stress',stress)]:audit.append({'id':name,'scenario':cost,'ledger':x['ledger'],'trades':x['trades'],'position':x['position'],'metrics':x['metrics'],'costs':x['costs']})
            run['curve']=run['curve'][::15]+run['curve'][-1:];(OUT/(name+'.json')).write_text(json.dumps(run,separators=(',',':')))
            (OUT/(mode+'-bars.json')).write_text(json.dumps(bars,separators=(',',':')));(OUT/(mode+'-signals.json')).write_text(json.dumps(raw,separators=(',',':')))
            print(json.dumps(trial),flush=True)
    with (OUT/'audit-input.ndjson').open('w') as f:
        for x in audit:f.write(json.dumps(x,separators=(',',':'))+'\n')
    data={'version':'EMA20-outside120-threebar-v1','protocol':protocol,'freeze':json.loads(lock.read_text()),'coverage':{'minutes':len(M),'days':len(CAL),'start':CAL[0],'end':CAL[-1],'calendar':CAL},'trials':trials,'notes':['Direct user-rule test; no learned weights or invented per-trade probability. Prior completed-trade frequency shown only from30 samples.','All signals use completed120m bars; no unfinished bar inEMA20 or3bartrail.','Classic full-range outside bar; no requirement that previous candle has opposite body color.','Intraday and conditional trend holding shown separately, same one-lot300kcontinuous account.','Portfolio15000CNY risk budget is research overlay, not guarantee; entries may stop when remaining drawdown allowance is too small.','Current-vintage event schedule and synthetic1m fills limit realism; oldAU2512data still absent.']}
    (OUT/'data.json').write_text(json.dumps(data,separators=(',',':')))
    with (OUT/'trials.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['id','trades','winRate','totalPnl','profitFactor','averageWin','averageLoss','maxDrawdown','stressPnl','signals','within3000'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for t in trials:w.writerow({'id':t['id'],**t['metrics'],'stressPnl':t['stressMetrics']['totalPnl'],'signals':t['quality']['ruleSignals'],'within3000':t['quality']['initialRiskWithin3000']})
if __name__=='__main__':main()
