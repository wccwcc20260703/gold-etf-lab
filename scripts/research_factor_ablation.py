"""Predeclared factor-set comparison; combined choice uses each day's PRIOR validation only."""
import csv,datetime as dt,hashlib,importlib.util,json,pathlib,sys,time
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';OUT=ROOT/'docs/futures/factor'
spec=importlib.util.spec_from_file_location('engine',ROOT/'scripts/research_factors.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
CORE=['trend15','trend60','slope15','momentum1','rsi1','macd1','di1','atrPercent','volumeExpansion','night','isShort','dailyTrend5_20','dailyTrend20_60']
MACRO={'realYieldChange5','nominalYieldChange5','curve10minus2','policyChange20d','usdCnyReturn5','ratesMissing','fxMissing'}
GROUPS={'core':CORE,'technical':[x for x in r.F['features'] if x not in MACRO],'all_information':r.F['features']}
def lock():
 p=D/'factor-ablation-freeze-v2.3.json';spec={'version':'factor-ablation-v2.3','baseEngineHash':r.digest(ROOT/'scripts/research_factors.py'),'wrapperHash':r.digest(__file__),'frameHash':r.digest(D/'factor-frame.json'),'protocolHash':r.digest(r.PROTOCOL),'groups':GROUPS,'combinedSelection':'Prior validation Wilson lower bound thenPnl/DD, intraday preference unchanged. Never select by next-day OOS results.','knownPriorResults':'Full53factorv2.2 lost12580CNY/47trades. This expanded same-history study is exploratory, not pristine prospective evidence.'}
 if p.exists():assert json.loads(p.read_text())['specification']==spec
 else:p.write_text(json.dumps({'createdAt':dt.datetime.now(dt.timezone.utc).isoformat(),'specification':spec},indent=2))
 return json.loads(p.read_text())
def write_run(folder,daily,models,freeze,variant):
 folder.mkdir(parents=True,exist_ok=True);base=r.oos_account(models);stress=r.oos_account(models,True);source=json.loads((OUT/'data.json').read_text());source.update(version='factor-ablation-v2.3',variant=variant,freeze=freeze,daily=daily,metrics=base['metrics'],stressMetrics=stress['metrics']);source['coverage']={**source['coverage'],'selectedDays':len(models)}
 bins=[]
 for low,high in [(60,69),(70,79),(80,89),(90,100)]:
  ts=[t for t in base['trades'] if low<=t['score']<=high];bins.append({'low':low,'high':high,**r.summary([t['netPnl'] for t in ts]),'meanPredictedProbability':sum(t['probability'] for t in ts)/len(ts) if ts else None})
 source['calibration']=bins;(folder/'data.json').write_text(json.dumps(source,separators=(',',':')));(folder/'daily-models.json').write_text(json.dumps({'daily':daily,'models':models},separators=(',',':')))
 for name,run in [('oos',base),('stress',stress)]:
  (folder/(name+'-ledger.json')).write_text(json.dumps({'ledger':run['ledger'],'position':run['position'],'metrics':run['metrics'],'costs':run['costs']},separators=(',',':')));run['curve']=run['curve'][::5]+run['curve'][-1:];(folder/(name+'.json')).write_text(json.dumps(run,separators=(',',':')))
 fields=['entry','exit','direction','score','probability','profile','plannedRisk','netPnl','reason','entrySession','overnight']
 with (folder/'trades.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(base['trades'])
 print(json.dumps({'phase':'complete','variant':variant,'selectedDays':len(models),'base':base['metrics'],'stress':stress['metrics']}),flush=True)
def main():
 freeze=lock();variant=sys.argv[1];start=r.P['trainTradingDays']+r.P['validationTradingDays']+r.P['embargoTradingDays'];folder=OUT/'ablation'/variant
 if variant=='combined':
  sources={k:json.loads((OUT/('daily-models.json' if k=='all_information' else f'ablation/{k}/daily-models.json')).read_text()) for k in GROUPS};models={};daily=[]
  for day in range(start,len(r.CAL)):
   options=[]
   for name,source in sources.items():
    m=source['models'].get(str(day))
    if m:
     m={**m,'featureSet':name,'probabilities':{int(k):v for k,v in m['probabilities'].items()}};options.append(m)
   best=max(options,key=lambda m:r.rank(m['validation'])) if options else None
   intraday=[m for m in options if r.PROFILES[m['profile']]['carry']=='intraday'];intra=max(intraday,key=lambda m:r.rank(m['validation'])) if intraday else None
   if intra and best and r.rank(best['validation'])[0]<r.rank(intra['validation'])[0]+r.P['intradayPreferenceWilsonTolerance']:best=intra
   if best:models[day]=best
   daily.append({'day':r.CAL[day],'dayIndex':day,'status':'selected' if best else 'no_candidate_passed','search':{'candidates':sum(next(x['search']['candidates'] for x in s['daily'] if x['dayIndex']==day) for s in sources.values())},'selected':{k:v for k,v in best.items() if k!='probabilities'} if best else None})
  write_run(folder,daily,models,freeze,variant);return
 ids=[r.F['features'].index(k) for k in GROUPS[variant]];original=r.logistic_fit
 def fit(x,y,l2):
  m=original(x[:,ids],y,l2);mean=x.mean(axis=0);scale=np.ones(x.shape[1]);active=np.zeros(x.shape[1],bool);weights=np.zeros(x.shape[1]+1);scale[ids]=m['scale'];active[ids]=m['active'];weights[0]=m['weights'][0];weights[np.array(ids)+1]=m['weights'][1:];return{**m,'mean':mean,'scale':scale,'active':active,'weights':weights,'featureSet':variant}
 r.logistic_fit=fit;metadata=json.loads((OUT/'data.json').read_text());legs=np.load(D/'cache'/f"{metadata['cacheKey']}.npz")['legs'];models={};daily=[];folder.mkdir(parents=True,exist_ok=True);started=time.time()
 with (folder/'selection-trials.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['decisionDay','profile','lambda','probabilityThreshold','trainTrades','trainWinRate','trainPnl','trainPF','trainDD','trainStress','validationTrades','validationWinRate','validationPnl','validationPF','validationDD','validationStress'])
  for day in range(start,len(r.CAL)):
   model,search=r.select_day(day,legs,w)
   if model:model['featureSet']=variant;models[day]=model
   daily.append({'day':r.CAL[day],'dayIndex':day,'status':'selected' if model else 'no_candidate_passed','search':search,'selected':{k:v for k,v in model.items() if k!='probabilities'} if model else None})
   print(json.dumps({'variant':variant,'day':r.CAL[day],'selected':model['profile'] if model else None,'elapsedSeconds':round(time.time()-started,1)}),flush=True)
 write_run(folder,daily,models,freeze,variant)
if __name__=='__main__':main()
