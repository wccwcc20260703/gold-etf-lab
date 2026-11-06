import decimal,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';OUT=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'docs/futures/outside');Dec=lambda x:decimal.Decimal(str(x));source=json.loads((D/'minute-input.json').read_text());raw={r[0]:r for r in source['rows']};result=json.loads((OUT/'data.json').read_text());receipt=[]
freeze=result['freeze']['specification'];assert freeze['scriptSha256']==hashlib.sha256((ROOT/'scripts/research_outside_ema20.py').read_bytes()).hexdigest();assert freeze['minuteInputSha256']==hashlib.sha256((D/'minute-input.json').read_bytes()).hexdigest()
for line in (OUT/'audit-input.ndjson').open():
 r=json.loads(line);mode=r['id'].removesuffix('_intraday').removesuffix('_conditional_trend');bars=json.loads((OUT/(mode+'-bars.json')).read_text());balance=Dec(300000);pos=0;basis=None;entry=None;fee=None;trades={t['opp']:t for t in r['trades']}
 for e in r['ledger']:
  if e['type']=='open':
   assert pos==0 and e['direction'] in (-1,1) and raw[e['minute']][6]>0
   assert e['plannedRisk']<=min(3000,e['riskBudget'])+.01 and e['plannedRisk']<=float(balance)*.01+.01
   pos=e['direction'];basis=entry=Dec(e['tick']);fee=Dec(e['fee']);balance-=fee
  elif e['type']=='settlement':
   assert pos==e['direction']!=0;change=Dec(pos)*(Dec(e['tick'])-basis)*Dec(20);assert change==Dec(e['variation']);balance+=change;basis=Dec(e['tick'])
  elif e['type']=='close':
   assert pos==e['direction']!=0 and raw[e['minute']][6]>0;change=Dec(pos)*(Dec(e['tick'])-basis)*Dec(20);assert change==Dec(e['variation']);balance+=change-Dec(e['fee']);t=trades[e['opp']]
   assert Dec(t['netPnl'])==Dec(pos)*(Dec(e['tick'])-entry)*Dec(20)-fee-Dec(e['fee'])
   b=bars[t['signalBar']];p=bars[t['signalBar']-1];n=bars[t['nextBar']]
   assert t['lots']==1 and b['high']>p['high'] and b['low']<p['low'];assert pos*(b['close']-b['open'])>0 and pos*(b['close']-b['ema20'])>0
   assert t['initialStopTicks']==(b['low'] if pos==1 else b['high']);assert t['i']==n['firstTradeIndex'] and t['signalMinute']<=t['entryMinute']
   risk=(abs(t['entryTicks']-t['initialStopTicks'])+r['costs']['slip'])*20+r['costs']['open']+r['costs']['close'];assert risk==t['plannedRisk']
   previous=t['initialStopTicks']
   for move in t['stopHistory'][1:]:
    k=move['confirmedBar'];assert k>=2 and bars[k]['end']<=move['minute'];line=min(x['low'] for x in bars[k-2:k+1]) if pos==1 else max(x['high'] for x in bars[k-2:k+1]);expected=max(previous,line) if pos==1 else min(previous,line);assert move['stopTicks']==expected;previous=expected
   assert t['probability'] is None and t['score'] is None
   pos=0;basis=None
  else:raise AssertionError(e['type'])
  assert balance==Dec(e['balance']) and e['position']==pos
 equity=balance+(Dec(pos)*(Dec(source['rows'][-1][5])-basis)*Dec(20) if pos else 0);assert equity==Dec(r['metrics']['finalEquity']);receipt.append({'id':r['id'],'cost':r['scenario'],'trades':len(r['trades']),'finalEquity':float(equity),'trailAdjustments':sum(len(t['stopHistory'])-1 for t in r['trades']),'passed':True})
report={'passed':True,'scenarios':len(receipt),'receipts':receipt,'checks':['Full-range outside andEMA20 direction','Next bar first positive-volume open','Outside extreme initialstop','Closed3bar extremes and one-way trail','No invented confidence probabilities','One-lot planned risk inclfees/slip','Decimal variationmargin/cash/NAV']};(OUT/'account-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
