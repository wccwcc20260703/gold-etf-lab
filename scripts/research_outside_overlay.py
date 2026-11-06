"""Separate sensitivity: remove ONLY the additional portfolio drawdown allowance.
Fixed one lot, 300k, max3000/equity1%, event and intraday rules are retained.
"""
import datetime as dt,hashlib,importlib.util,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';OUT=ROOT/'docs/futures/outside/no_portfolio_cap';OUT.mkdir(exist_ok=True)
sp=importlib.util.spec_from_file_location('outside',ROOT/'scripts/research_outside_ema20.py');s=importlib.util.module_from_spec(sp);sp.loader.exec_module(s)
spec={'driverSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'strategySha256':s.r.digest(ROOT/'scripts/research_outside_ema20.py'),'overlay':'No aggregate15000CNYportfolio budget; one-lot3000/equity1%risk remains.','createdAt':dt.datetime.now(dt.timezone.utc).isoformat()};trials=[];audits=[]
for mode in ('trading_minutes','session_clock'):
 for holding in ('intraday','conditional_trend'):
  s.r.P['accountDrawdownStopCny']=1e99;base,q,bars,raw=s.run_variant(mode,holding);stress,_,_,_=s.run_variant(mode,holding,True);name=mode+'_'+holding
  t={'id':name,'aggregation':mode,'holding':holding,'metrics':base['metrics'],'stressMetrics':stress['metrics'],'quality':q,'periods':base['periods'],'directions':base['directions'],'skips':base['skips']};trials.append(t)
  for cost,r in [('base',base),('stress',stress)]:audits.append({'id':name,'scenario':cost,'ledger':r['ledger'],'trades':r['trades'],'position':r['position'],'metrics':r['metrics'],'costs':r['costs']})
  base['curve']=base['curve'][::15]+base['curve'][-1:];(OUT/(name+'.json')).write_text(json.dumps(base,separators=(',',':')));(OUT/(mode+'-bars.json')).write_text(json.dumps(bars,separators=(',',':')));print(json.dumps(t),flush=True)
data=json.loads((OUT.parent/'data.json').read_text());data.update(sensitivity=spec,trials=trials)
(OUT/'data.json').write_text(json.dumps(data,separators=(',',':')))
with (OUT/'audit-input.ndjson').open('w') as f:
 for r in audits:f.write(json.dumps(r,separators=(',',':'))+'\n')
