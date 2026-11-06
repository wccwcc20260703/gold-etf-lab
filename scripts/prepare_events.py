import datetime as dt,hashlib,json,pathlib,re
from html import unescape
from zoneinfo import ZoneInfo
D=pathlib.Path(__file__).resolve().parents[1]/'data/futures'
rows=json.loads((D/'event-rows-bls.json').read_text())+json.loads((D/'event-rows-bea.json').read_text())
rows=[r for r in rows if not(r['type']=='GDP' and r['date'] in ('2026-01-23','2026-02-05'))]
fed=(D/'event-sources/fed.html').read_text();url='https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
for day in sorted(set(re.findall(r'pressreleases/monetary(20\d{6})a\.htm',fed))):
    if day>='20251117':rows.append({'date':f'{day[:4]}-{day[4:6]}-{day[6:]}','timeET':'14:00','type':'FOMC','source':url})
plain=' '.join(unescape(re.sub('<[^>]+>',' ',fed)).split())
for m,d,y in re.findall(r'Released (\w+) (\d+), (202[56])',plain):
    date=dt.datetime.strptime(f'{m} {d} {y}','%B %d %Y').date().isoformat()
    if date>='2025-11-17':rows.append({'date':date,'timeET':'14:00','type':'FOMC_minutes','source':url})
for date,kind in [('2026-11-18','FOMC_minutes'),('2026-12-09','FOMC')]:rows.append({'date':date,'timeET':'14:00','type':kind,'source':'https://www.federalreserve.gov/monetarypolicy.htm'})
for date,kind,time,source in [
 ('2026-12-04','NFP','08:30','https://www.bls.gov/schedule/news_release/empsit.htm'),
 ('2026-12-10','CPI','08:30','https://www.bls.gov/schedule/news_release/cpi.htm'),
 ('2026-02-06','NFP_original_schedule','08:30','https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm'),
 ('2026-02-11','CPI_original_schedule','08:30','https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm'),
 ('2026-01-29','PCE_original_schedule','08:30','https://www.bea.gov/news/2026/personal-income-and-outlays-december-2025'),
 ('2025-11-26','GDP_original_schedule','08:30','https://apps.bea.gov/scb/issues/2026/01-january/0126-charting-economy.htm'),
 ('2025-12-19','GDP_original_schedule','08:30','https://apps.bea.gov/scb/issues/2026/01-january/0126-charting-economy.htm')]:rows.append({'date':date,'timeET':time,'type':kind,'source':source})
unique={}
for r in rows:
    date=dt.datetime.fromisoformat(r['date']+'T'+r['timeET']).replace(tzinfo=ZoneInfo('America/New_York'));r['minute']=int(date.timestamp()//60);r['chinaTime']=date.astimezone(ZoneInfo('Asia/Shanghai')).isoformat();r['beforeMinutes']=120 if r['type'].startswith('FOMC') else 60;r['afterMinutes']=120 if r['type'].startswith('FOMC') else 60;unique[(r['minute'],r['type'])]=r
events=sorted(unique.values(),key=lambda r:r['minute']);output={'snapshot':'2026-11-06','timezone':'America/New_York converted to Asia/Shanghai with DST','policy':'FOMC/minutes block2h before/after; CPI/NFP/PCE/GDP1h before/after; no carry when next24h contains event; original plus revised dates where verified','limitation':'Historical calendars are current archival snapshots, not daily vintage schedules; original+revised dates conservatively retained where verified. Unscheduled shocks and all official speeches are not covered.','events':events}
(D/'events.json').write_text(json.dumps(output,ensure_ascii=False,indent=2));print(json.dumps({'events':len(events),'types':{k:sum(r['type']==k for r in events) for k in sorted(set(r['type'] for r in events))},'first':events[0],'last':events[-1]}))
