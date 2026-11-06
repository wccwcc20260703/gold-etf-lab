import contextlib,datetime as dt,importlib.util,io,json,pathlib,tempfile,unittest
from zoneinfo import ZoneInfo
spec=importlib.util.spec_from_file_location('acq',pathlib.Path(__file__).with_name('fetch_futures_forward.py'));acq=importlib.util.module_from_spec(spec);spec.loader.exec_module(acq)
class Acquisition(unittest.TestCase):
    def run_case(self,night=False,incomplete=False):
        with tempfile.TemporaryDirectory() as folder:
            acq.D=pathlib.Path(folder);base={'calendar':['2026-04-10'],'daily':[],'rows':[]};(acq.D/'minute-input.json').write_text(json.dumps(base));checkpoint={**base,'receipts':[]};p=acq.D/'forward-input.json';p.write_text(json.dumps(checkpoint));before=p.read_bytes()
            day='2026-04-13';dates=[]
            if night:
                first=dt.datetime(2026,4,10,21,tzinfo=ZoneInfo('Asia/Shanghai'));dates.extend(first+dt.timedelta(minutes=i) for i in range(330))
            for hour,minute,length in [(9,0,75),(10,30,60),(13,30,90)]:
                first=dt.datetime(2026,4,13,hour,minute,tzinfo=ZoneInfo('Asia/Shanghai'));dates.extend(first+dt.timedelta(minutes=i) for i in range(length))
            n=len(dates);daily=[{'d':day,'o':'100','h':'100','l':'100','c':'100','s':'100','v':str(n)}]
            if incomplete:dates.pop()
            csv='datetime_nano,open,high,low,close,volume,open_oi,close_oi\n'+''.join(f'{int(d.timestamp())*1000000000},100,100,100,100,1,1,1\n' for d in dates)
            acq.get=lambda url:('=('+json.dumps(daily)+');').encode() if 'sina' in url else csv.encode()
            with contextlib.redirect_stdout(io.StringIO()):
                if incomplete:
                    with self.assertRaises(ValueError):acq.main()
                    self.assertEqual(before,p.read_bytes());return
                acq.main()
            result=json.loads(p.read_text());self.assertEqual(len(result['rows']),n);self.assertEqual(result['calendar'],['2026-04-10',day]);self.assertTrue(all(row[1]==1 for row in result['rows']));self.assertTrue(result['receipts'][0]['days'][0]['ohlcMatched'])
    def test_holiday_day_without_night(self):self.run_case()
    def test_friday_night_maps_to_monday(self):self.run_case(night=True)
    def test_incomplete_day_preserves_checkpoint(self):self.run_case(incomplete=True)
if __name__=='__main__':unittest.main()
