"""Assemble published diagnostics, downloads and source receipts; never select by OOS returns."""
import csv,hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';OUT=ROOT/'docs/futures/factor'
shutil.copyfile(D/'events.json',OUT/'events.json')
paths={'all_information':OUT/'selection-trials.csv','core':OUT/'ablation/core/selection-trials.csv','technical':OUT/'ablation/technical/selection-trials.csv'}
total=0
with (OUT/'all-factor-trials.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.writer(f);header=None
 for group,path in paths.items():
  with path.open(encoding='utf-8-sig',newline='') as inp:
   reader=csv.reader(inp);columns=next(reader)
   if header is None:header=['factorSet']+columns;header[4]='probabilityThreshold';writer.writerow(header)
   for row in reader:writer.writerow([group]+row);total+=1
source=json.loads((D/'factor-frame.json').read_text());result=json.loads((OUT/'ablation/combined/data.json').read_text())
info={'sourceMinutes':128115,'tradingDays':235,'opportunities':len(source['opportunities']),'features':len(source['features']),'patternEvaluations':source['patternEvaluations'],'patternDetections':source['patternDetections'],'dailyCandidatesRecorded':total,'frameSha256':hashlib.sha256((D/'factor-frame.json').read_bytes()).hexdigest(),'macroSourceSha256':source['macroSourceHash'],'versions':['v2.0','v2.1','v2.2','v2.3-core','v2.3-technical','v2.3-prior-validation-combined'],'currentDisplay':'v2.3 combined; each day chooses group using only prior validation, not OOS winner','qualification':'Research only; no prospective evidence yet','coverage':result['coverage']}
models=json.loads((OUT/'ablation/combined/daily-models.json').read_text())['models'];trades=json.loads((OUT/'ablation/combined/oos.json').read_text())['trades'];entered={t['opp'] for t in trades};prices=json.loads((D/'minute-input.json').read_text())['rows'];groups={}
for o in source['opportunities']:
    m=models.get(str(o['day']));prob=m['probabilities'].get(str(o['id'])) if m else None
    strength=min(99,max(60,round(60+40*(prob-m['breakEvenProbability'])/(1-m['breakEvenProbability'])))) if m and prob is not None and prob>=m['breakEvenProbability'] else None
    row={k:o[k] for k in ('id','t','direction','patterns','triggers')};row.update(probability=prob,strength=strength,threshold=m['threshold'] if m else None,price=prices[o['i']][2]*.02,entered=o['id'] in entered,featureSet=m.get('featureSet','all_information') if m else None)
    groups.setdefault(source['calendar'][o['day']],[]).append(row)
folder=OUT/'opportunities';folder.mkdir(exist_ok=True)
for day in source['calendar']:(folder/(day+'.json')).write_text(json.dumps(groups.get(day,[]),ensure_ascii=False,separators=(',',':')))
(OUT/'research-manifest.json').write_text(json.dumps(info,indent=2));print(json.dumps(info))
