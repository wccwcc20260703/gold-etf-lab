"""Independent Decimal audit of every candidate's position, settlements and round trips."""
import decimal as dec, hashlib, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]; OUT=ROOT/'docs/futures'
D=lambda x:dec.Decimal(str(x))
source=json.loads((ROOT/'data/futures/minute-input.json').read_text())
minutes={r[0]:r for r in source['rows']}
forward_path=ROOT/'data/futures/forward-input.json'
if forward_path.exists():minutes.update({r[0]:r for r in json.loads(forward_path.read_text())['rows']})
receipts=[];count=0
for line in (OUT/'audit-input.ndjson').open():
    r=json.loads(line);cfg=r['config'];balance=D(cfg['capital']);position=0;basis=None;open_price=None;open_fee=None;open_day=None;planned=None
    for row in r['ledger']:
        assert row['position'] in (-1,0,1)
        if row['type']=='open':
            assert position==0 and row['direction'] in (-1,1)
            assert minutes[row['t']][6]>0
            position=row['direction'];basis=D(row['price']);open_price=basis;open_fee=D(row['fee']);open_day=row['day'];planned=D(row['plannedRisk'])
            assert planned<=D(3000) and planned<=balance*D('.01')+D('.01')
            assert row['fee']==cfg['openFee'];balance-=open_fee
            assert balance>=basis*D(1000)*D(cfg['marginRate'])*(1+D(cfg['marginBuffer']))-D('.01')
        elif row['type']=='settlement':
            assert position==row['direction'] and position!=0
            variation=D(position)*(D(row['price'])-basis)*D(1000)
            assert abs(variation-D(row['variation']))<=D('.01');balance+=variation;basis=D(row['price'])
        elif row['type']=='close':
            assert position==row['direction'] and position!=0
            assert minutes[row['t']][6]>0
            fee=D(cfg['closeTodayFee'] if open_day==row['day'] else cfg['closeOvernightFee'])
            assert fee==D(row['fee'])
            variation=D(position)*(D(row['price'])-basis)*D(1000)
            assert abs(variation-D(row['variation']))<=D('.01');balance+=variation-fee;position=0;basis=None
        else:raise AssertionError(row['type'])
        assert abs(balance-D(row['balance']))<=D('.011'),(r['id'],row)
        assert row['position']==position
    for t in r['trades']:
        assert t['lots']==1 and t['plannedRisk']<=min(3000,t['riskBudget'])+.01
        assert t['signalMinute']<=t['entryMinute'] and t['mediumEnd']<=t['signalMinute'] and t['slowEnd']<=t['signalMinute']
        assert 60<=t['score']<=100 and sum(f['points'] for f in t['factors'])==t['score']
        assert t['macro'] is None or t['macro']['availableMinute']<=t['signalMinute']
        low,high=t['empirical']['bucket']
        prior=[p for p in r['trades'] if p['exitMinute']<t['entryMinute'] and low<=p['score']<=high]
        assert len(prior)==t['empirical']['pastCompleted']
        assert sum(p['netPnl']>0 for p in prior)==t['empirical']['pastWins']
        assert (t['empirical']['winRate'] is None)==(len(prior)<30)
        pnl=D(t['direction'])*(D(t['exitPrice'])-D(t['entryPrice']))*D(1000)-D(t['openFee'])-D(t['closeFee'])
        assert abs(pnl-D(t['netPnl']))<=D('.011')
        risk=(D(t['direction'])*(D(t['entryPrice'])-D(t['initialStop']))+D(cfg['slippageTicks'])*D('.02'))*D(1000)+D(cfg['openFee'])+max(D(cfg['closeTodayFee']),D(cfg['closeOvernightFee']))
        assert abs(risk-D(t['plannedRisk']))<=D('.011')
        count+=1
    equity=balance+(D(position)*(D(r['lastPrice'])-basis)*D(1000) if position else 0)
    assert abs(equity-D(r['metrics']['finalEquity']))<=D('.02')
    assert abs(equity-D(cfg['capital'])-D(r['metrics']['totalPnl']))<=D('.02')
    assert r['metrics']['openLots']==position
    receipts.append({'id':r['id'],'cost':r['cost'],'trades':len(r['trades']),'events':len(r['ledger']),'finalEquity':float(equity),'passed':True})
report={'status':'passed','candidatesIncludingStress':len(receipts),'roundTripsAudited':count,'auditInputSha256':hashlib.sha256((OUT/'audit-input.ndjson').read_bytes()).hexdigest(),'checks':['signed one-lot position','no fills on zero volume','planned risk inclusive of costs','signal availability ordering','fee by trading day','daily variation margin and basis resets','Decimal balance and NAV','round-trip PnL'],'receipts':receipts}
(OUT/'account-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='receipts'}))
