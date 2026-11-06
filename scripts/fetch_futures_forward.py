"""Append only new complete AU2612 trading days, without revising the frozen history."""
import bisect,csv,datetime as dt,hashlib,io,json,pathlib,sys,urllib.parse,urllib.request
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures'
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'*/*'})
    with urllib.request.urlopen(req,timeout=90) as r:return r.read()
def main():
    frozen=json.loads((D/'minute-input.json').read_text());path=D/'forward-input.json'
    current=json.loads(path.read_text()) if path.exists() else {'calendar':frozen['calendar'],'daily':[],'rows':[],'receipts':[]}
    today=dt.datetime.now(ZoneInfo('Asia/Shanghai'));cutoff=(today.date() if today.hour>=15 else today.date()-dt.timedelta(days=1)).isoformat()
    if '--offline' in sys.argv:daily=frozen['daily']
    else:
        raw=get('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/=/InnerFuturesNewService.getDailyKLine?symbol=AU2612').decode()
        daily=json.loads(raw.split('=(',1)[1].rsplit(');',1)[0])
    last=current['calendar'][-1];new=sorted([d for d in daily if last<d['d']<=cutoff],key=lambda d:d['d'])
    if not new:print(json.dumps({'status':'no_new_complete_day','last':last}));return
    calendar=current['calendar']+[d['d'] for d in new]
    query=urllib.parse.urlencode({'symbol':'SHFE.au2612','period':60,'start_time':last+' 15:01:00','end_time':new[-1]['d']+' 15:00:00'})
    payload=get('https://edb.shinnytech.com/md/kline?'+query)
    if not payload.startswith(b'datetime_nano,'):raise ValueError('Unexpected EDB schema')
    groups={d['d']:[] for d in new}
    for r in csv.DictReader(io.StringIO(payload.decode())):
        t=int(r['datetime_nano'])//60_000_000_000;clock=dt.datetime.fromtimestamp(t*60,dt.timezone.utc).astimezone(ZoneInfo('Asia/Shanghai'));date=clock.strftime('%Y-%m-%d');hm=clock.strftime('%H:%M')
        idx=bisect.bisect_right(calendar,date) if hm>='21:00' else bisect.bisect_left(calendar,date)
        if idx>=len(calendar):continue
        day=calendar[idx]
        if day not in groups:continue
        prices=[float(r[k]) for k in ('open','high','low','close')];o,h,l,c=prices;v=float(r['volume']);oi=float(r['close_oi'])
        if min(prices)<=0 or l>min(o,c)+1e-8 or h<max(o,c)-1e-8 or not v.is_integer() or v<0 or not oi.is_integer() or any(abs(p*50-round(p*50))>1e-6 for p in prices):raise ValueError('Invalid minute')
        groups[day].append([t,idx,*[round(p*50) for p in prices],int(v),int(oi)])
    comparisons=[]
    for d in new:
        if not float(d.get('s',0))>0:raise ValueError('Missing valid daily settlement '+d['d'])
        rows=sorted(groups[d['d']]);active=[r for r in rows if r[6]>0]
        if len(rows) not in (225,555) or len({r[0] for r in rows})!=len(rows) or not active:raise ValueError('Incomplete or duplicate day '+d['d'])
        if dt.datetime.fromtimestamp(rows[-1][0]*60,dt.timezone.utc).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%H:%M')!='14:59':raise ValueError('Missing day close')
        obs=[active[0][2]*.02,max(r[3] for r in active)*.02,min(r[4] for r in active)*.02,active[-1][5]*.02]
        if any(abs(a-float(d[k]))>.02001 for a,k in zip(obs,('o','h','l','c'))):raise ValueError('Daily OHLC reconciliation failed '+d['d'])
        comparisons.append({'day':d['d'],'minutes':len(rows),'ohlcMatched':True,'volumeDifference':sum(r[6] for r in rows)-float(d['v'])})
        current['rows'].extend(rows)
    current['calendar']=calendar;current['daily'].extend(new);current['receipts'].append({'fetchedAt':today.isoformat(),'source':'https://edb.shinnytech.com/md/kline','sha256':hashlib.sha256(payload).hexdigest(),'days':comparisons})
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(current,separators=(',',':')));temporary.replace(path)
    print(json.dumps({'status':'appended_verified_days','days':len(new),'newMinutes':sum(len(g) for g in groups.values()),'last':calendar[-1]}))
if __name__=='__main__':main()
