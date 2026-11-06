"""Use the documented anonymous EDB minute-history service, honoring access errors."""
import argparse,csv,datetime,hashlib,json,pathlib,urllib.error,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
def download(contract,start,end):
    target=ROOT/'data/futures/full-history';target.mkdir(parents=True,exist_ok=True)
    path=target/f'{contract}-{start[:10]}-{end[:10]}-1min.csv';receipt=path.with_suffix('.receipt.json')
    if receipt.exists():
        cached=json.loads(receipt.read_text())
        if path.exists() or cached.get('status')=='access_denied':return cached
    params={'period':60,'symbol':'SHFE.'+contract.lower(),'start_time':start,'end_time':end}
    url='https://edb.shinnytech.com/md/kline?'+urllib.parse.urlencode(params)
    result={'contract':contract,'requestedStart':start,'requestedEnd':end,'source':'https://edb.shinnytech.com/md/kline','sourceDocumentation':'https://doc.shinnytech.com/edb/latest/md_server.html','timestampConvention':'bar start; Unix nanoseconds, Asia/Shanghai display','requestedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'*/*'})
        part=path.with_suffix('.part')
        with urllib.request.urlopen(request,timeout=90) as response,part.open('wb') as file:
            result['httpStatus']=response.status
            while True:
                block=response.read(1024*1024)
                if not block:break
                file.write(block)
        with part.open() as file:
            reader=csv.DictReader(file);fields=reader.fieldnames
            if not fields or 'datetime_nano' not in fields:raise ValueError('Response was not the documented minute CSV')
            rows=0;first=None;last=None
            for row in reader:
                rows+=1;first=first or row['datetime_nano'];last=row['datetime_nano']
        part.rename(path)
        def stamp(value):return datetime.datetime.fromtimestamp(int(value)/1e9,datetime.timezone(datetime.timedelta(hours=8))).isoformat() if value else None
        result.update({'status':'downloaded','rows':rows,'first':stamp(first),'last':stamp(last),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'path':str(path.resolve()),'columns':fields})
    except urllib.error.HTTPError as exc:
        result.update({'status':'access_denied' if exc.code in [401,403] else 'http_error','httpStatus':exc.code,'error':exc.read().decode('utf-8',errors='replace')[:1000]})
    except Exception as exc:result.update({'status':'error','error':str(exc)})
    receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--contract',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);a=p.parse_args()
    print(json.dumps(download(a.contract,a.start,a.end),ensure_ascii=False),flush=True)
