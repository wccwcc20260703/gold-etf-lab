"""Independent Decimal audit of published frozen-model fills."""
import datetime,json,pathlib
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
ROOT=pathlib.Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'docs/data.json').read_text());D=lambda x:Decimal(str(x))
count=0;max_error=Decimal(0)
for fund in data['funds']:
    result=data['replays'][fund['code']];cfg=result['config'];cash=D(cfg['capital']);shares=0
    lookup={b[0]:b for s in fund['sessions'] for b in s['bars']}
    for fill in result['fills']:
        stamp=datetime.datetime.strptime(fill['time'],'%Y-%m-%d %H:%M')+datetime.timedelta(minutes=5)
        bar=lookup[stamp.strftime('%Y-%m-%d %H:%M')]
        buy=fill['side']=='buy';raw=D(bar[1])*(1+D(cfg['slippage']) if buy else 1-D(cfg['slippage']))
        expected_price=raw.quantize(D('.001'),rounding=ROUND_CEILING if buy else ROUND_FLOOR)
        assert abs(expected_price-D(fill['price']))<D('.000000001')
        expected_fee=max(D(cfg['minCommission']),D(fill['quantity'])*expected_price*D(cfg['commission']))
        assert abs(expected_fee-D(fill['fee']))<D('.000000001')
        value=expected_price*D(fill['quantity']);cash+=(-value-expected_fee) if buy else value-expected_fee;shares+=fill['quantity'] if buy else -fill['quantity']
        error=abs(cash-D(fill['cashAfter']));max_error=max(max_error,error);assert error<D('.000001')
        assert cash>=0 and shares==fill['sharesAfter'] and shares>=0
        count+=1
    assert shares==0
    assert abs(cash-D(cfg['capital'])-D(result['metrics']['totalPnl']))<D('.000001')
receipt={'engine':'Independent Python Decimal accounting','funds':len(data['funds']),'auditedFills':count,'maximumCashDifferenceCny':str(max_error),'checks':['price tick and adverse slippage','minimum and proportional commission','cash conservation','nonnegative shares','closing position zero'],'passed':True}
(ROOT/'docs/account-audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))
