"""Freeze a lossless tick-price minute input and conservative macro availability map."""
import bisect, csv, datetime as dt, hashlib, json, pathlib, shutil
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/'data/futures'; OUT=ROOT/'docs/futures'; OUT.mkdir(exist_ok=True)
raw=D/'full-history/AU2612-2025-11-17-2026-11-06-1min.csv'
daily=json.loads((D/'AU2612-daily.json').read_text()); calendar=sorted(x['d'] for x in daily)
packed=[]
for r in csv.DictReader(raw.open()):
    minute=int(r['datetime_nano'])//60_000_000_000
    clock=dt.datetime.fromtimestamp(minute*60,dt.timezone.utc).astimezone(ZoneInfo('Asia/Shanghai'))
    date=clock.strftime('%Y-%m-%d'); hm=clock.strftime('%H:%M')
    idx=bisect.bisect_right(calendar,date) if hm>='21:00' else bisect.bisect_left(calendar,date)
    if idx>=len(calendar) or (hm>='03:00' and hm<'21:00' and calendar[idx]!=date):raise ValueError(date)
    assert float(r['volume']).is_integer() and float(r['close_oi']).is_integer()
    packed.append([minute,idx,*[round(float(r[k])*50) for k in ('open','high','low','close')],int(float(r['volume'])),int(float(r['close_oi']))])
result={'schema':2,'contract':'AU2612','encoding':['epoch_minute_UTC','trade_day_index','open_ticks','high_ticks','low_ticks','close_ticks','volume_lots','close_oi_lots'],'price_tick':.02,'calendar':calendar,'daily':daily,'rows':packed,'rawSha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
(D/'minute-input.json').write_text(json.dumps(result,separators=(',',':')))

# Current-vintage observations are deliberately delayed three US federal business days,
# then until 09:00 China. This is a conservative proxy, NOT an ALFRED vintage guarantee.
holidays={'2025-10-13','2025-11-11','2025-11-27','2025-12-25','2026-01-01','2026-01-19','2026-02-16','2026-05-25','2026-06-19','2026-07-03','2026-09-07','2026-10-12','2026-11-11','2026-11-26','2026-12-25'}
macro=[]; f=ROOT.parents[1]/'work/fred-rates-probe.csv'
for row in csv.DictReader(f.open()):
    date=row['observation_date']
    if date<'2025-10-01' or not row['DGS10'] or not row['DFII10']:continue
    day=dt.date.fromisoformat(date); n=0
    while n<3:
        day+=dt.timedelta(days=1)
        if day.weekday()<5 and day.isoformat() not in holidays:n+=1
    available=dt.datetime.combine(day,dt.time(9),ZoneInfo('Asia/Shanghai'))
    macro.append({'observation':date,'availableAt':available.isoformat(),'availableMinute':int(available.timestamp()//60),'nominal10':float(row['DGS10']),'real10':float(row['DFII10'])})
for i,r in enumerate(macro):
    r['nominalChange5']=round(r['nominal10']-macro[i-5]['nominal10'],4) if i>=5 else None
    r['realChange5']=round(r['real10']-macro[i-5]['real10'],4) if i>=5 else None
md={'source':['https://fred.stlouisfed.org/series/DGS10','https://fred.stlouisfed.org/series/DFII10'],'vintage':'downloaded 2026-11-06; current revised history, not point-in-time vintages','availabilityPolicy':'3 US federal business days after observation, 09:00 Asia/Shanghai; stale after 10 calendar days; conservative proxy only','rawSha256':hashlib.sha256(f.read_bytes()).hexdigest(),'rows':macro}
(D/'macro.json').write_text(json.dumps(md,ensure_ascii=False,separators=(',',':')))
shutil.copyfile(D/'macro.json',OUT/'macro.json')
audit=json.loads((D/'data-audit.json').read_text())
readiness=json.loads((D/'data-readiness.json').read_text());readiness.update(status='AU2612_ready_with_volume_caveat',currentPhase='Full AU2612 since listing; AU2512 early 2025 deferred by user',backtestPublished=False)
(D/'data-readiness.json').write_text(json.dumps(readiness,ensure_ascii=False,indent=2))
(OUT/'quality.json').write_text(json.dumps(next(x for x in audit if x['contract']=='AU2612'),ensure_ascii=False,indent=2))
print(json.dumps({'minutes':len(packed),'days':len(calendar),'macroObservations':len(macro),'macroLast':macro[-1]}))
