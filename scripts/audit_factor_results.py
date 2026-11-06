import decimal,hashlib,json,pathlib,sys
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';OUT=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'docs/futures/factor');Dec=lambda x:decimal.Decimal(str(x))
frame=json.loads((D/'factor-frame.json').read_text());source=json.loads((D/'minute-input.json').read_text());result=json.loads((OUT/'data.json').read_text());models=json.loads((OUT/'daily-models.json').read_text())['models'];opps=frame['opportunities'];raw={r[0]:r for r in source['rows']};receipts=[]
spec=result['freeze']['specification'];sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
assert spec['frameHash']==sha(D/'factor-frame.json')
assert spec.get('engineHash',spec.get('baseEngineHash'))==sha(ROOT/'scripts/research_factors.py')
for name in ('oos','stress'):
 r=json.loads((OUT/(name+'.json')).read_text());balance=Dec(300000);pos=0;basis=None;entry=None;openfee=None;trades_by_opp={t['opp']:t for t in r['trades']}
 for e in r['ledger']:
  if e['type']=='open':
   assert pos==0 and e['position'] in (-1,1);assert raw[e['minute']][6]>0
   assert e['plannedRisk']<=min(3000,e['riskBudget'])+.01 and e['plannedRisk']<=float(balance)*.01+.01
   o=opps[e['opp']];day=models[str(o['day'])];assert day['trainedThrough']<=o['day']-3
   assert o['signalMinute']<=e['minute'] and o['mediumEnd']<=e['minute'] and o['slowEnd']<=e['minute'];assert o['dailyClosedDay'] is None or o['dailyClosedDay']<e['day']
   for m in o['macro'].values():assert m is None or m['availableMinute']<=e['minute']
   assert e['probability']>=day['threshold']
   pos=e['direction'];basis=Dec(e['tick']);entry=basis;openfee=Dec(e['fee']);balance-=openfee
   assert balance>=Dec(e['tick'])*Dec(20)*Dec(r['costs']['margin'])*Dec('1.2')
  elif e['type']=='settlement':
   assert pos==e['direction']!=0;variation=Dec(pos)*(Dec(e['tick'])-basis)*Dec(20);assert variation==Dec(e['variation']);balance+=variation;basis=Dec(e['tick'])
  elif e['type']=='close':
   assert pos==e['direction']!=0;assert raw[e['minute']][6]>0
   variation=Dec(pos)*(Dec(e['tick'])-basis)*Dec(20);assert variation==Dec(e['variation']);balance+=variation-Dec(e['fee'])
   t=trades_by_opp[e['opp']];pnl=Dec(pos)*(Dec(e['tick'])-entry)*Dec(20)-openfee-Dec(e['fee']);assert pnl==Dec(t['netPnl'])
   assert t['lots']==1 and 60<=t['score']<=99
   profile=result['profiles'][t['profile']];distance=abs(t['entryTicks']-t['initialStopTicks']);assert distance==int(np.ceil(t['entryTicks']*profile['stopPct']-1e-10));assert t['plannedRisk']==(distance+r['costs']['slip'])*20+r['costs']['open']+r['costs']['close']
   for c in t['carryEvents']:assert not(c['hold'] and c['eventOrLongGap'])
   pos=0;basis=None
  else:raise AssertionError(e['type'])
  assert balance==Dec(e['balance']) and pos==e['position']
 final=balance+(Dec(pos)*(Dec(source['rows'][-1][5])-basis)*Dec(20) if pos else 0);assert final==Dec(r['metrics']['finalEquity']);assert final-Dec(300000)==Dec(r['metrics']['totalPnl'])
 receipts.append({'scenario':name,'trades':len(r['trades']),'ledgerEvents':len(r['ledger']),'finalEquity':float(final),'passed':True})
# Independently verify every selected model's standardization uses only training labels known by cutoff.
legs=np.load(D/'cache'/f"{result['cacheKey']}.npz")['legs'];X=np.array([o['features'] for o in opps]);days=np.array([o['day'] for o in opps]);checked=0
for day,m in models.items():
 day=int(day);ts,te=m['trainRange'];vs,ve=m['validationRange'];assert te<vs<=ve<=day-3
 q=m['profile'];v=legs[0,q];mask=(days>=ts)&(days<=te-2)&(v[:,0]==1)&(v[:,2]<=te)
 assert int(mask.sum())==m['model']['samples'];assert np.allclose(X[mask].mean(axis=0),m['model']['mean'],atol=1e-10)
 for k in m['trainTrades']:assert opps[k]['day']<=te-2 and v[k,2]<=te
 for k in m['validationTrades']:assert opps[k]['day']<=ve-2 and v[k,2]<=ve
 checked+=1
base=json.loads((OUT/'oos.json').read_text());trades=base['trades'];brier=sum((t['probability']-int(t['netPnl']>0))**2 for t in trades)/len(trades) if trades else None
report={'passed':True,'selectedDailyModelsAudited':checked,'receipts':receipts,'oosBrierScore':brier,'constant50PercentBrierReference':.25,'checks':['Decimal cash/settlement/NAV','one signed lot','planned risk including fees/slippage','zero-volume fill prohibition','causal macro/daily/minute features','daily train/validation purge ordering','train-only feature mean','probability entry threshold','stop percentage and cost identity','no carry through protected events or long closure gaps'],'notes':['Event schedule historical vintage and macro revisions remain imperfect; audit does not establish predictive skill.','OOS is retrospective walk-forward over an already inspected instrument; no prospective trades yet.']}
(OUT/'account-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
