"""Daily nested walk-forward. Learned logistic weights; exact minute exits and one-lot ledger.
No data/network fetching here. Frozen input, protocol and every daily selection are auditable.
"""
import csv,datetime as dt,hashlib,itertools,json,math,pathlib,sys,time
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';OUT=ROOT/'docs/futures/factor';OUT.mkdir(exist_ok=True)
PROTOCOL=D/'factor-protocol-v2.1.json'
P=json.loads(PROTOCOL.read_text());SRC=json.loads((D/'minute-input.json').read_text());F=json.loads((D/'factor-frame.json').read_text());EVENTS=json.loads((D/'events.json').read_text())
M=np.array(SRC['rows'],dtype=np.int64);O=F['opportunities'];X=np.array([o['features'] for o in O],dtype=float);DAY=np.array([o['day'] for o in O]);INDEX=np.array([o['i'] for o in O]);CAL=SRC['calendar'];N=len(O)
assert X.shape[1]==len(F['features']) and np.isfinite(X).all()
MG={int(k):v for k,v in F['management'].items()};CARRY={int(k):v for k,v in F['carryChecks'].items()};CLOCK=(M[:,0]+480)%1440
EVENT_BLOCK=np.zeros(len(M),bool);NO_CARRY=np.zeros(len(M),bool)
for e in EVENTS['events']:
    EVENT_BLOCK|=(M[:,0]>=e['minute']-e['beforeMinutes'])&(M[:,0]<=e['minute']+e['afterMinutes'])
    NO_CARRY|=(M[:,0]<=e['minute'])&(M[:,0]>=e['minute']-1440)
for i in CARRY:
    next_i=int(np.searchsorted(M[:,0],M[i,0]+5))
    if next_i<len(M) and M[next_i,0]-(M[i,0]+5)>720:NO_CARRY[i]=True
PROFILES=[{'id':i,'stopPct':s,'exitStyle':e,'maxHold':h,'carry':c} for i,(s,e,h,c) in enumerate(itertools.product(P['candidateStopsPct'],P['exits'],P['maxHoldingTradingMinutes'],P['carryModes']))]
SETTLES={i:round(float(d['s'])*50) for i,d in enumerate(SRC['daily'])}
def stamp(t):return dt.datetime.fromtimestamp((int(t)+480)*60,dt.timezone.utc).strftime('%Y-%m-%d %H:%M')
def digest(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def costs(stress=False):return {'slip':4 if stress else 2,'open':40 if stress else 20,'close':40 if stress else 20,'margin':.25 if stress else .2}
def new_position(oi,profile,stress=False):
    o=O[oi];i=o['i'];d=o['direction'];c=costs(stress);entry=int(M[i,2])+d*c['slip'];distance=math.ceil(entry*profile['stopPct']-1e-10);risk=(distance+c['slip'])*20+c['open']+c['close']
    if EVENT_BLOCK[i] or risk>3000 or distance*.02<o['atr']*.5:return None
    stop=entry-d*distance;style=profile['exitStyle'];target=None if style=='breakeven_then_ATR_trail' else entry+d*math.ceil(distance*float(style[5:-1])-1e-10)
    return {'opp':oi,'profile':profile['id'],'i':i,'direction':d,'entryTicks':entry,'stopTicks':stop,'initialStopTicks':stop,'targetTicks':target,'distance':distance,'plannedRisk':risk,'basisTicks':entry,'entryDay':o['day'],'fee':c['open'],'slip':c['slip'],'closeFee':c['close'],'forced':None,'carryEvents':[]}
def exit_step(p,i):
    """All open-time management reads only already-closed indicators; range stops first."""
    row=M[i];d=p['direction'];profile=PROFILES[p['profile']];vol=int(row[6]);raw=None;reason=None;stage='open'
    if EVENT_BLOCK[i]:p['forced']='scheduled_event_exit'
    if i>p['i']:
        if int(CLOCK[i]) in (895,145):
            check=CARRY.get(i,{});score=check.get(str(d),0);hold=profile['carry']=='conditional_trend' and score>=80 and not NO_CARRY[i]
            p['carryEvents'].append({'minute':int(row[0]),'score':score,'hold':hold,'eventOrLongGap':bool(NO_CARRY[i]),'featureMinute':check.get('featureMinute')})
            if not hold:p['forced']='session_exit'
        if CAL[int(row[1])]>='2026-11-30':p['forced']='pre_delivery_exit'
        f=MG.get(i)
        if profile['exitStyle']=='breakeven_then_ATR_trail' and f and f['atr'] is not None:
            if d*f['mediumBias']<0:p['forced']='trend_reversal'
            profit=d*(f['close']*50-p['entryTicks'])
            if profit>=p['distance']:
                be=p['entryTicks']+d*math.ceil((p['fee']+p['closeFee'])/20+p['slip'])
                candidate=be
                if profit>=p['distance']*1.5:
                    tr=math.floor(f['close']*50-f['atr']*100+1e-9) if d==1 else math.ceil(f['close']*50+f['atr']*100-1e-9)
                    candidate=max(be,tr) if d==1 else min(be,tr)
                p['stopTicks']=max(p['stopTicks'],candidate) if d==1 else min(p['stopTicks'],candidate)
    if not vol:return None
    if p['forced']:return (int(row[2]),p['forced'],'open')
    stop=row[4]<=p['stopTicks'] if d==1 else row[3]>=p['stopTicks']
    target=p['targetTicks'] is not None and (row[3]>=p['targetTicks'] if d==1 else row[4]<=p['targetTicks'])
    if stop:return (min(int(row[2]),p['stopTicks']) if d==1 else max(int(row[2]),p['stopTicks']),'stop','range')
    if target:return (p['targetTicks'],'target','range')
    if i-p['i']+1>=profile['maxHold']:return (int(row[5]),'time_exit','close')
    return None
REASONS=['stop','target','trend_reversal','time_exit','session_exit','pre_delivery_exit','scheduled_event_exit']
# cache columns: status(0invalid1closed2open),exitIndex,exitDay,pnl,risk,entryTicks,exitTicks,minPath,maxPath,internalDD,reason
def leg(oi,profile,stress=False):
    p=new_position(oi,profile,stress)
    if p is None:return np.zeros(11)
    base=-p['fee'];peak=0.;low=0.;high=0.;dd=0.
    def mark(tick):
        nonlocal peak,low,high,dd
        v=p['direction']*(tick-p['entryTicks'])*20+base;peak=max(peak,v);low=min(low,v);high=max(high,v);dd=max(dd,peak-v)
    for i in range(p['i'],len(M)):
        mark(M[i,2]);action=exit_step(p,i)
        if action:
            if action[2]=='close':mark(M[i,4] if p['direction']==1 else M[i,3]);mark(M[i,3] if p['direction']==1 else M[i,4])
            elif action[1]=='target':mark(M[i,4] if p['direction']==1 else M[i,3])
            tick=action[0]-p['direction']*p['slip'];net=p['direction']*(tick-p['entryTicks'])*20-p['fee']-p['closeFee'];mark(tick);low=min(low,net);high=max(high,net);dd=max(dd,peak-net)
            return np.array([1,i,int(M[i,1]),net,p['plannedRisk'],p['entryTicks'],tick,low,high,dd,REASONS.index(action[1])],float)
        if M[i,6]>0:
            mark(M[i,4] if p['direction']==1 else M[i,3]);mark(M[i,3] if p['direction']==1 else M[i,4]);mark(M[i,5])
    return np.array([2,len(M)-1,int(M[-1,1]),p['direction']*(int(M[-1,5])-p['entryTicks'])*20-p['fee'],p['plannedRisk'],p['entryTicks'],0,low,high,dd,-1],float)
def precompute():
    key=hashlib.sha256((PROTOCOL.read_text()+digest(D/'factor-frame.json')+digest(__file__)+digest(D/'events.json')).encode()).hexdigest();folder=ROOT/'data/futures/cache';folder.mkdir(exist_ok=True);path=folder/(key+'.npz')
    if path.exists():a=np.load(path)['legs'];print('Cached legs '+key,flush=True);return a,key
    a=np.zeros((2,len(PROFILES),N,11))
    for cost in range(2):
        for q,profile in enumerate(PROFILES):
            for oi in range(N):a[cost,q,oi]=leg(oi,profile,bool(cost))
            print(json.dumps({'phase':'outcomes','cost':cost,'profile':q+1,'profiles':len(PROFILES)}),flush=True)
    np.savez_compressed(path,legs=a);return a,key
def logistic_fit(x,y,l2):
    mean=x.mean(axis=0);sd=x.std(axis=0);active=(sd>1e-8)&((np.abs(x)>1e-10).sum(axis=0)>=20)
    scale=np.where(active,sd,1);z=np.clip((x-mean)/scale,-5,5)
    # Remove near-duplicates using TRAINING rows only, in fixed feature order.
    corr=np.corrcoef(z[:,active],rowvar=False) if active.sum()>1 else np.array([[1.]])
    indices=np.where(active)[0]
    for a,j in enumerate(indices):
        if any(active[k] and abs(corr[a,b])>=.95 for b,k in enumerate(indices[:a])):active[j]=False
    z[:,~active]=0;z=np.column_stack((np.ones(len(z)),z));w=np.zeros(z.shape[1]);penalty=np.eye(len(w))*l2;penalty[0,0]=0
    for _ in range(25):
        prob=1/(1+np.exp(-np.clip(z@w,-30,30)));gradient=z.T@(prob-y)/len(y)+penalty@w;h=(z.T*(prob*(1-prob)))@z/len(y)+penalty+np.eye(len(w))*1e-7
        step=np.linalg.solve(h,gradient);w-=step
        if np.max(np.abs(step))<1e-6:break
    return {'mean':mean,'scale':scale,'active':active,'weights':w,'lambda':l2,'samples':len(y),'labelWinRate':float(y.mean())}
def predict(model,x):
    z=np.clip((x-model['mean'])/model['scale'],-5,5);z[:,~model['active']]=0;return 1/(1+np.exp(-np.clip(model['weights'][0]+z@model['weights'][1:],-30,30)))
def wilson(w,n):
    if not n:return None
    z=1.95996398454;p=w/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;return [center-delta,center+delta]
def summary(pnls,dd=0):
    p=np.array(pnls,float);n=len(p);wins=int((p>0).sum());gain=float(p[p>0].sum());loss=-float(p[p<0].sum());net=float(p.sum())
    return {'trades':n,'wins':wins,'winRate':wins/n if n else None,'winInterval':wilson(wins,n),'netPnl':net,'profitFactor':gain/loss if loss else None,'averageWin':float(p[p>0].mean()) if wins else None,'averageLoss':float(-p[p<0].mean()) if (p<0).any() else None,'expectancy':net/n if n else None,'maxDrawdown':dd,'surchargeStress':net-n*120}
def passes(m,min_trades):return m['trades']>=min_trades and m['netPnl']>0 and (m['profitFactor'] or 0)>=P['minProfitFactor'] and m['maxDrawdown']<=P['maxSelectionDrawdownCny'] and m['surchargeStress']>0 and (m['averageWin'] or 0)>=P['minAverageWinLossRatio']*(m['averageLoss'] or 0)
def rank(m):return (m['winInterval'][0],m['netPnl']/max(m['maxDrawdown'],1))
def fast_account(outcomes,prob,threshold,start,entry_end,label_end):
    balance=300000.;peak=balance;dd=0.;busy=-1;cooldown=-1;pnls=[];counts={};day_losses={};ids=[]
    eligible=np.where((DAY>=start)&(DAY<=entry_end))[0];ordered=sorted(eligible,key=lambda k:(INDEX[k],-prob[k]))
    for k in ordered:
        o=O[k];v=outcomes[k];i=o['i'];d=o['day']
        if i<=busy or int(M[i,0])<cooldown or prob[k]<threshold or not v[0] or counts.get(d,0)>=2 or day_losses.get(d,0)<=-6000:continue
        if v[4]>min(3000,balance*.01)+.001 or balance-20<v[5]*20*.2*1.2:continue
        # Entry embargo is fixed in advance; labels crossing the known boundary cannot be used.
        if v[0]!=1 or v[2]>label_end:continue
        dd=max(dd,peak-(balance+v[7]),v[9]);peak=max(peak,balance+v[8]);balance+=v[3];peak=max(peak,balance);dd=max(dd,peak-balance)
        busy=int(v[1]);cooldown=int(M[busy,0])+5;pnls.append(v[3]);ids.append(int(k));counts[d]=counts.get(d,0)+1;day_losses[int(v[2])]=day_losses.get(int(v[2]),0)+v[3]
    return summary(pnls,dd),ids
def serial_model(m):return {k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in m.items()}
def select_day(day,legs,trial_writer=None):
    ve=day-P['embargoTradingDays']-1;vs=ve-P['validationTradingDays']+1;te=vs-1;ts=te-P['trainTradingDays']+1;train=(DAY>=ts)&(DAY<=te-P['labelPurgeTradingDays']);chosen=None;intraday=None;fit_count=0;candidate_count=0;pass_train=0
    for q,profile in enumerate(PROFILES):
        outcomes=legs[0,q];mask=train&(outcomes[:,0]==1)&(outcomes[:,2]<=te);eligible=np.where(mask)[0]
        if len(eligible)<60:continue
        y=(outcomes[eligible,3]>0).astype(float)
        if min(y.sum(),len(y)-y.sum())<15:continue
        for l2 in P['l2']:
            model=logistic_fit(X[eligible],y,l2);prob=predict(model,X);fit_count+=1
            for threshold in P['entryProbabilityThresholds']:
                candidate_count+=1;tr,train_ids=fast_account(outcomes,prob,threshold,ts,te-P['labelPurgeTradingDays'],te);valid=None
                if passes(tr,P['trainMinTrades']):
                    pass_train+=1;valid,val_ids=fast_account(outcomes,prob,threshold,vs,ve-P['labelPurgeTradingDays'],ve)
                    required=P['validationMinTrades'] if profile['carry']=='intraday' else P['conditionalCarryMinValidationTrades']
                    if passes(valid,required):
                        candidate={'profile':q,'threshold':threshold,'model':serial_model(model),'train':tr,'validation':valid,'trainTrades':train_ids,'validationTrades':val_ids,'trainRange':[ts,te],'validationRange':[vs,ve],'trainedThrough':ve,'day':day,'probabilities':{int(k):float(prob[k]) for k in np.where(DAY==day)[0]}}
                        if chosen is None or rank(valid)>rank(chosen['validation']):chosen=candidate
                        if profile['carry']=='intraday' and (intraday is None or rank(valid)>rank(intraday['validation'])):intraday=candidate
                if trial_writer:trial_writer.writerow([CAL[day],q,l2,threshold,tr['trades'],tr['winRate'],tr['netPnl'],tr['profitFactor'],tr['maxDrawdown'],tr['surchargeStress'],valid['trades'] if valid else '',valid['winRate'] if valid else '',valid['netPnl'] if valid else '',valid['profitFactor'] if valid else '',valid['maxDrawdown'] if valid else '',valid['surchargeStress'] if valid else ''])
    if intraday and chosen and (PROFILES[chosen['profile']]['carry']=='intraday' or rank(chosen['validation'])[0]<rank(intraday['validation'])[0]+P['intradayPreferenceWilsonTolerance']):chosen=intraday
    return chosen,{'fits':fit_count,'candidates':candidate_count,'trainingPassed':pass_train,'trainRange':[ts,te],'validationRange':[vs,ve]}
def oos_account(daily_models,stress=False):
    c=costs(stress);balance=300000.;position=None;peak=300000.;dd=0.;ddf=0.;curve=[];ledger=[];trades=[];day_state={};current_day=None;day_equity=300000.;blocked=False;cooldown=-1;skips={};last=None;halted=False;halt_day=None
    by_i={};start=P['trainTradingDays']+P['validationTradingDays']+P['embargoTradingDays']
    for o in O:by_i.setdefault(o['i'],[]).append(o['id'])
    def equity(tick):return balance+(position['direction']*(tick-position['basisTicks'])*20 if position else 0)
    def track(tick):
        nonlocal peak,dd,ddf
        e=equity(tick);peak=max(peak,e);dd=max(dd,peak-e);ddf=max(ddf,(peak-e)/peak)
    def close(i,raw,reason,stage):
        nonlocal balance,position,cooldown
        p=position;tick=int(raw)-p['direction']*p['slip'];variation=p['direction']*(tick-p['basisTicks'])*20;balance+=variation-p['closeFee'];o=O[p['opp']];net=p['direction']*(tick-p['entryTicks'])*20-p['fee']-p['closeFee'];end_day=int(M[i,1]);t={**p,'exitIndex':i,'exitMinute':int(M[i,0]),'exitDay':CAL[end_day],'exitTicks':tick,'netPnl':net,'reason':reason,'executionStage':stage,'entryDay':CAL[p['entryDay']],'entryMinute':o['t'],'entry':stamp(o['t']),'exit':stamp(M[i,0]),'lossOverPlan':-net>p['plannedRisk']+.01,'overnight':end_day!=p['entryDay'],'entrySession':'night' if (CLOCK[p['i']]>=1260 or CLOCK[p['i']]<180) else 'day','features':o['features'],'patterns':o['patterns'],'triggers':o['triggers'],'macro':o['macro']};trades.append(t)
        ledger.append({'type':'close','minute':int(M[i,0]),'day':CAL[end_day],'direction':p['direction'],'tick':tick,'basisTicks':p['basisTicks'],'variation':variation,'fee':p['closeFee'],'balance':balance,'position':0,'opp':p['opp'],'reason':reason});position=None;cooldown=int(M[i,0])+5;track(tick)
    def apply_action(i,action):
        if action[2]=='close':track(int(M[i,4] if position['direction']==1 else M[i,3]));track(int(M[i,3] if position['direction']==1 else M[i,4]))
        elif action[1]=='target':track(int(M[i,4] if position['direction']==1 else M[i,3]))
        close(i,*action)
    previous_equity=300000.
    for i,row in enumerate(M):
        day=int(row[1]);minute=int(row[0])
        if day<start:continue
        if day!=current_day:current_day=day;day_equity=previous_equity;blocked=False
        track(int(row[2]));closed=False
        if peak-equity(int(row[2]))>=P['accountDrawdownStopCny']:halted=True;halt_day=halt_day or CAL[day]
        if position:
            if halted:position['forced']='account_drawdown_halt'
            if equity(int(row[2]))<row[2]*20*c['margin']:position['forced']='margin_call'
            if equity(int(row[2]))<=day_equity*.98:position['forced']='daily_loss';blocked=True
            # exit_step below handles open actions BEFORE the intraminute range.
            action=exit_step(position,i)
            if action:
                apply_action(i,action);closed=True
        daily=daily_models.get(day)
        if position is None and not closed and daily and not blocked and not halted and minute>=cooldown and day_state.get(day,0)<2:
            opts=sorted(by_i.get(i,[]),key=lambda k:-daily['probabilities'].get(k,0))
            for oi in opts:
                probability=daily['probabilities'].get(oi,0)
                if probability<daily['threshold']:continue
                p=new_position(oi,PROFILES[daily['profile']],stress)
                if p is None:skips['profile_risk']=skips.get('profile_risk',0)+1;continue
                budget=min(3000,balance*.01,max(0,P['accountDrawdownStopCny']-(peak-balance)))
                if p['plannedRisk']>budget+.001:skips['equity_risk']=skips.get('equity_risk',0)+1;continue
                if balance-p['fee']<p['entryTicks']*20*c['margin']*1.2:skips['margin']=skips.get('margin',0)+1;continue
                p.update(probability=probability,score=min(99,round(probability*100)),riskBudget=budget,modelDay=CAL[day],lots=1);position=p;balance-=p['fee'];day_state[day]=day_state.get(day,0)+1;track(int(row[2]))
                ledger.append({'type':'open','minute':minute,'day':CAL[day],'direction':p['direction'],'tick':p['entryTicks'],'variation':0,'fee':p['fee'],'balance':balance,'position':p['direction'],'opp':oi,'plannedRisk':p['plannedRisk'],'riskBudget':budget,'probability':probability,'modelDay':CAL[day]})
                action=exit_step(position,i)
                if action:apply_action(i,action)
                break
        if position and row[6]>0:track(int(row[4] if position['direction']==1 else row[3]));track(int(row[3] if position['direction']==1 else row[4]))
        track(int(row[5]));e=equity(int(row[5]))
        if e<=day_equity*.98:blocked=True
        if peak-e>=P['accountDrawdownStopCny']:halted=True;halt_day=halt_day or CAL[day]
        if position and blocked:position['forced']='daily_loss'
        if position and CLOCK[i]==899:
            settle=SETTLES[day];variation=position['direction']*(settle-position['basisTicks'])*20;balance+=variation;ledger.append({'type':'settlement','minute':minute+1,'day':CAL[day],'direction':position['direction'],'tick':settle,'basisTicks':position['basisTicks'],'variation':variation,'fee':0,'balance':balance,'position':position['direction'],'opp':position['opp']});position['basisTicks']=settle
        margin=float(row[5]*20*c['margin']) if position else 0.;previous_equity=equity(int(row[5]));curve.append({'minute':minute,'day':CAL[day],'equity':previous_equity,'balance':balance,'margin':margin,'position':position['direction'] if position else 0});last=int(row[5])
    s=summary([t['netPnl'] for t in trades],dd);s.update(totalPnl=equity(last)-300000 if last is not None else 0,finalEquity=equity(last) if last is not None else balance,maxDrawdownFraction=ddf,openLots=position['direction'] if position else 0,lossOverPlan=sum(t['lossOverPlan'] for t in trades),daysWithEntries=len(day_state),halted=halted,haltDay=halt_day);return {'metrics':s,'trades':trades,'ledger':ledger,'curve':curve,'position':position,'skips':skips,'costs':c}
def main():
    started=time.time();spec={'protocolHash':digest(PROTOCOL),'frameHash':digest(D/'factor-frame.json'),'minuteInputHash':digest(D/'minute-input.json'),'engineHash':digest(__file__),'eventHash':digest(D/'events.json'),'profiles':PROFILES,'features':F['features']};lock=D/'factor-research-freeze-v2.1.json'
    if lock.exists():
        if json.loads(lock.read_text())['specification']!=spec:raise ValueError('V2 freeze differs; archive/version a disclosed correction')
    else:lock.write_text(json.dumps({'specification':spec,'createdAt':dt.datetime.now(dt.timezone.utc).isoformat(),'note':'Daily protocol frozen before firstv2 results;v1 history already inspected.'},indent=2))
    legs,cache_key=precompute();models={};daily=[];start=P['trainTradingDays']+P['validationTradingDays']+P['embargoTradingDays']
    with (OUT/'selection-trials.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['decisionDay','profile','lambda','threshold','trainTrades','trainWinRate','trainPnl','trainPF','trainDD','trainStress','validationTrades','validationWinRate','validationPnl','validationPF','validationDD','validationStress'])
        for day in range(start,len(CAL)):
            model,search=select_day(day,legs,w)
            if model:models[day]=model
            daily.append({'day':CAL[day],'dayIndex':day,'status':'selected' if model else 'no_candidate_passed','search':search,'selected':{k:v for k,v in model.items() if k!='probabilities'} if model else None})
            print(json.dumps({'phase':'daily_fit','day':CAL[day],'candidates':search['candidates'],'selected':model['profile'] if model else None,'elapsedSeconds':round(time.time()-started,1)}),flush=True)
    base=oos_account(models);stress=oos_account(models,True)
    serial_daily={str(k):{**v,'probabilities':{str(i):p for i,p in v['probabilities'].items()}} for k,v in models.items()}
    (OUT/'daily-models.json').write_text(json.dumps({'daily':daily,'models':serial_daily},separators=(',',':')))
    for name,r in [('oos',base),('stress',stress)]:
        # Keep every minute in the audit, decimate only the visible curve artifact.
        (OUT/(name+'-ledger.json')).write_text(json.dumps({'ledger':r['ledger'],'position':r['position'],'metrics':r['metrics'],'costs':r['costs']},separators=(',',':')))
        r['curve']=r['curve'][::5]+(r['curve'][-1:] if r['curve'] else []);(OUT/(name+'.json')).write_text(json.dumps(r,separators=(',',':')))
    with (OUT/'trades.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['entry','exit','direction','score','probability','profile','plannedRisk','riskBudget','netPnl','reason','entrySession','overnight','lossOverPlan'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(base['trades'])
    bins=[]
    for lo,hi in [(60,69),(70,79),(80,89),(90,100)]:
        t=[t for t in base['trades'] if lo<=t['score']<=hi];s=summary([x['netPnl'] for x in t]);bins.append({'low':lo,'high':hi,**s,'meanPredictedProbability':sum(x['probability'] for x in t)/len(t) if t else None})
    result={'protocol':P,'freeze':json.loads(lock.read_text()),'features':F['features'],'featureNames':F['featureNames'],'profiles':PROFILES,'coverage':{'days':len(CAL),'start':CAL[0],'end':CAL[-1],'minutes':len(M),'opportunities':N,'oosStart':CAL[start],'oosDays':len(CAL)-start,'selectedDays':len(models)},'metrics':base['metrics'],'stressMetrics':stress['metrics'],'calibration':bins,'daily':daily,'cacheKey':cache_key,'elapsedSeconds':time.time()-started,'status':'Research only; inspect out-of-sample economics and calibration before calling any model reliable.'}
    (OUT/'data.json').write_text(json.dumps(result,separators=(',',':')));print(json.dumps({'phase':'complete','coverage':result['coverage'],'base':base['metrics'],'stress':stress['metrics'],'elapsedSeconds':result['elapsedSeconds']}),flush=True)
if __name__=='__main__':main()
