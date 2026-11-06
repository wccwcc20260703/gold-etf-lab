"""Appending/changing future minutes AND the unfinished daily OHLC must not change prior factors."""
import copy,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1];W=ROOT/'data/futures/cache/causality';W.mkdir(parents=True,exist_ok=True)
source=json.loads((ROOT/'data/futures/minute-input.json').read_text());frame=json.loads((ROOT/'data/futures/factor-frame.json').read_text());cut=45007
prefix=copy.deepcopy(source);prefix['rows']=prefix['rows'][:cut];future=copy.deepcopy(source);current_day=future['rows'][cut-1][1]
for row in future['rows'][cut:]:
    for j in (2,3,4,5):row[j]+=1000
for row in future['daily'][current_day:]:
    for key in ('o','h','l','c'):row[key]=str(float(row[key])+20)
expected=[o for o in frame['opportunities'] if o['i']<cut]
for name,data in [('prefix',prefix),('changed_future',future)]:
    path=W/(name+'.json');result=W/(name+'-frame.json');path.write_text(json.dumps(data,separators=(',',':')))
    r=subprocess.run(['node','scripts/export_factor_frame.mjs',str(path),str(result)],cwd=ROOT,capture_output=True,text=True,check=True)
    observed=[o for o in json.loads(result.read_text())['opportunities'] if o['i']<cut]
    assert len(expected)>100
    assert expected==observed,(name,len(expected),len(observed))
report={'passed':True,'cutMinuteIndex':cut,'comparedOpportunities':len(expected),'features':len(frame['features']),'checks':['future append invariance','future minute price mutation invariance','unfinished and future daily OHLC mutation invariance','one-minute, multi-timeframe, developing-day, chart-pattern and delayed macro factors unchanged']}
(ROOT/'docs/futures/factor/causality-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
