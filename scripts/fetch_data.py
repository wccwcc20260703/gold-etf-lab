"""Low-rate public ETF data acquisition. Never fabricate unavailable minute bars."""
import argparse,csv,datetime,hashlib,json,pathlib,time,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
FUNDS=[('518880','sh','华安黄金ETF'),('518800','sh','国泰黄金ETF'),('159934','sz','易方达黄金ETF'),('159937','sz','博时黄金ETF')]
def fetch(url,params,path):
    if path.exists(): return json.loads(path.read_text())
    request=urllib.request.Request(url+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
    with urllib.request.urlopen(request,timeout=25) as response: body=response.read().decode('utf-8')
    result=json.loads(body);path.write_text(json.dumps(result,ensure_ascii=False));time.sleep(1)
    return result
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--asof',default=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat());args=parser.parse_args()
    directory=ROOT/'data/raw'/args.asof;directory.mkdir(parents=True,exist_ok=True)
    manifest={'asof':args.asof,'fetchedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'Eastmoney public kline API','volumeInputUnit':'hands; converted to ETF shares by ×100','funds':[],'errors':[]}
    for code,exchange,name in FUNDS:
        info={'code':code,'exchange':exchange,'name':name}
        for frequency in ['5','101']:
            path=directory/f'{code}-{frequency}.json'
            try:
                raw=fetch('https://push2his.eastmoney.com/api/qt/stock/kline/get',{'secid':('1.' if exchange=='sh' else '0.')+code,'klt':frequency,'fqt':'0','beg':'20200101','end':args.asof.replace('-',''),'lmt':'100000','fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'},path)
                lines=(raw.get('data') or {}).get('klines',[])
                if not lines: raise ValueError('Source returned no bars')
                info['minuteRows' if frequency=='5' else 'dailyRows']=len(lines)
                info['minuteStart' if frequency=='5' else 'dailyStart']=lines[0].split(',')[0]
                info['minuteEnd' if frequency=='5' else 'dailyEnd']=lines[-1].split(',')[0]
            except Exception as exc: manifest['errors'].append({'code':code,'frequency':frequency,'error':str(exc)})
        manifest['funds'].append(info)
        print(json.dumps(info,ensure_ascii=False),flush=True)
    (ROOT/'data/acquisition.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({'funds':len(manifest['funds']),'errors':manifest['errors']},ensure_ascii=False))
    if manifest['errors']: raise SystemExit(1)
if __name__=='__main__':main()
