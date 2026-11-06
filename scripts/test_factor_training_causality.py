"""Future labels/features cannot affect a model selected before their availability."""
import copy,importlib.util,json,pathlib
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('research',ROOT/'scripts/research_factors.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
result=json.loads((ROOT/'docs/futures/factor/data.json').read_text());legs=np.load(ROOT/'data/futures/cache'/f"{result['cacheKey']}.npz")['legs'];day=190
first,search=r.select_day(day,legs);future=r.DAY>=day-2;changed=legs.copy();changed[:,:,future,3]*=-100
originalX=r.X;r.X=r.X.copy();r.X[future]=1000
try:second,search2=r.select_day(day,changed)
finally:r.X=originalX
def prior_only(x):return {k:v for k,v in x.items() if k!='probabilities'} if x else None
assert first is not None and prior_only(first)==prior_only(second) and search==search2
report={'passed':True,'decisionDay':r.CAL[day],'trainedThrough':r.CAL[first['trainedThrough']],'candidates':search['candidates'],'checks':['Embargo/test/future feature mutation does not alter selected profile/threshold/weights','Embargo/test/future exit-PnL label mutation does not alter daily selection','Current-day predictions excluded from comparison because current market observations legitimately change predictions']}
(ROOT/'docs/futures/factor/training-causality-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
