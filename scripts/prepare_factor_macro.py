import bisect,csv,datetime as dt,hashlib,io,json,pathlib,zipfile
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures'
holidays=set('2025-09-01 2025-10-13 2025-11-11 2025-11-27 2025-12-25 2026-01-01 2026-01-19 2026-02-16 2026-05-25 2026-06-19 2026-07-03 2026-09-07 2026-10-12 2026-11-11 2026-11-26 2026-12-25'.split())
def business(d):return d.weekday()<5 and d.isoformat() not in holidays
def next_business(d):
    d+=dt.timedelta(days=1)
    while not business(d):d+=dt.timedelta(days=1)
    return d
p=D/'fred-factor-rates.zip';series={k:[] for k in ('DGS10','DFII10','DGS2','DFEDTARU','DEXCHUS')}
with zipfile.ZipFile(p) as z:
    for n in z.namelist():
        if not n.endswith('.csv'):continue
        for row in csv.DictReader(io.StringIO(z.read(n).decode('utf-8-sig'))):
            date=row['observation_date']
            if date<'2025-09-01':continue
            d=dt.date.fromisoformat(date)
            for k in series:
                if not row.get(k) or row[k]=='.':continue
                if k=='DEXCHUS':
                    release=d-dt.timedelta(days=d.weekday())+dt.timedelta(days=7)
                    while not business(release):release+=dt.timedelta(days=1)
                    available=dt.datetime.combine(release,dt.time(17,15),ZoneInfo('America/New_York'))
                elif k=='DFEDTARU':
                    release=d
                    for _ in range(3):release=next_business(release)
                    available=dt.datetime.combine(release,dt.time(9),ZoneInfo('Asia/Shanghai'))
                else:available=dt.datetime.combine(next_business(d),dt.time(17,15),ZoneInfo('America/New_York'))
                series[k].append({'observation':date,'value':float(row[k]),'availableMinute':int(available.timestamp()//60),'availableAt':available.astimezone(ZoneInfo('Asia/Shanghai')).isoformat()})
for k,rows in series.items():
    for i,r in enumerate(rows):
        r['change5']=round(r['value']-rows[i-5]['value'],6) if i>=5 else None
        r['return5']=(r['value']/rows[i-5]['value']-1) if i>=5 else None
        j=bisect.bisect_right([x['observation'] for x in rows],(dt.date.fromisoformat(r['observation'])-dt.timedelta(days=20)).isoformat())-1
        r['change20calendar']=round(r['value']-rows[j]['value'],6) if j>=0 else None
    rows.sort(key=lambda r:(r['availableMinute'],r['observation']))
result={'sourceSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'downloadedAt':'2026-11-06','vintage':'Current historical vintage, not original release vintages. Only future captured snapshots can remove this limitation.','availability':{'DGS10_DFII10_DGS2':'Next US federal business day17:15 New York (H15 observed next-day publication plus1h buffer), DST aware','DFEDTARU':'Conservative3 US federal business-day delay09:00 China; policy-level proxy, not announcement surprise','DEXCHUS':'Following US business-week H10 Monday publication, holiday adjusted,17:15 New York; not real-time FX'},'series':series}
(D/'factor-macro.json').write_text(json.dumps(result,separators=(',',':')))
print(json.dumps({k:{'rows':len(v),'last':v[-1]} for k,v in series.items()}))
