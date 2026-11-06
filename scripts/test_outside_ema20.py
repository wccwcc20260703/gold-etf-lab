import importlib.util,pathlib,unittest
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];sp=importlib.util.spec_from_file_location('outside',ROOT/'scripts/research_outside_ema20.py');s=importlib.util.module_from_spec(sp);sp.loader.exec_module(s)
class Outside(unittest.TestCase):
 def test_threebar_stop_first_can_ratchet_after_outside_bar_leaves_window(self):
  names=['M','CAL','O','N','DAY','INDEX','CLOCK','MG','CARRY','EVENT_BLOCK','NO_CARRY','SETTLES','P','PROFILES','new_position','exit_step'];saved={k:getattr(s.r,k) for k in names};oldM=s.M;oldCal=s.CAL;oldBars=s.bars_for
  try:
   t=30000000;m=np.array([[t+i,0,5000,5001,4990,5000,100,100] for i in range(481)],dtype=np.int64)
   m[119,4]=4970;m[239,4]=4975;m[359,4]=4980;m[360,2:6]=[4965,4966,4960,4965]
   s.M=s.r.M=m;s.CAL=s.r.CAL=['2026-05-11'];s.r.CLOCK=np.zeros(481,dtype=int)+600;s.r.EVENT_BLOCK=np.zeros(481,bool);s.r.NO_CARRY=np.zeros(481,bool);s.r.CARRY={};s.r.SETTLES={0:5000}
   bars=[]
   for j in range(20):bars.append({'index':j,'start':t-(20-j)*120,'end':t-(19-j)*120,'firstIndex':0,'lastIndex':0,'firstTradeIndex':0,'day':0,'open':5000,'high':5020,'low':4975,'close':4990,'volume':100,'tradingMinutes':120,'ema20':4990})
   bars[19].update(open=4980,high=5050,low=4950,close=5020)
   for j,low in enumerate([4970,4975,4980,4960]):bars.append({'index':20+j,'start':t+j*120,'end':t+(j+1)*120,'firstIndex':j*120,'lastIndex':min(480,(j+1)*120-1),'firstTradeIndex':j*120,'day':0,'open':5000,'high':5050+j,'low':low,'close':5020,'volume':12000,'tradingMinutes':120,'ema20':4990})
   s.bars_for=lambda mode:bars
   run,_,_,_=s.run_variant('trading_minutes','conditional_trend');self.assertEqual(run['metrics']['trades'],1);trade=run['trades'][0];self.assertEqual(len(trade['stopHistory']),2);move=trade['stopHistory'][1];self.assertEqual(move['confirmedBar'],22);self.assertEqual(move['stopTicks'],4970);self.assertEqual(move['minute'],t+360);self.assertEqual(trade['exitTicks'],4963);self.assertEqual(trade['netPnl'],-820)
  finally:
   s.M=oldM;s.CAL=oldCal;s.bars_for=oldBars
   for k,v in saved.items():setattr(s.r,k,v)
if __name__=='__main__':unittest.main()
