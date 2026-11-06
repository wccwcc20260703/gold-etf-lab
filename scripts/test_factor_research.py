import copy,importlib.util,pathlib,unittest
import numpy as np
spec=importlib.util.spec_from_file_location('research',pathlib.Path(__file__).with_name('research_factors.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Factors(unittest.TestCase):
 def setUp(self):self.old={k:getattr(r,k) for k in ['M','O','N','DAY','INDEX','CLOCK','MG','CARRY','EVENT_BLOCK','NO_CARRY']}
 def tearDown(self):
  for k,v in self.old.items():setattr(r,k,v)
 def fixture(self,gap=False):
  t=int(__import__('datetime').datetime(2026,5,11,1,tzinfo=__import__('datetime').timezone.utc).timestamp()//60)
  r.M=np.array([[t,112,5000,5001,4999,5000,100,100],[t+1,112,4800 if gap else 5000,5100 if gap else 5001,4700 if gap else 4999,4800 if gap else 5001,100,100]])
  r.O=[{'id':0,'i':0,'day':112,'t':t,'direction':1,'atr':.1,'features':[0]*len(r.F['features']),'patterns':[],'triggers':['unit_fixture'],'macro':{}}];r.N=1;r.DAY=np.array([112]);r.INDEX=np.array([0]);r.CLOCK=(r.M[:,0]+480)%1440;r.MG={};r.CARRY={};r.EVENT_BLOCK=np.zeros(2,bool);r.NO_CARRY=np.zeros(2,bool)
 def test_gap_and_same_minute_dual_touch_stop_first(self):
  self.fixture(True);leg=r.leg(0,r.PROFILES[0]);self.assertEqual(leg[0],1);self.assertEqual(leg[3],-4120);self.assertEqual(leg[4],200);self.assertEqual(r.REASONS[int(leg[10])],'stop')
 def test_unclosed_interval_not_used_to_refuse_an_entry(self):
  self.fixture();self.assertEqual(r.leg(0,r.PROFILES[0])[0],2);a=r.oos_account({112:{'profile':0,'threshold':.6,'breakEvenProbability':.5,'confidenceThreshold':60,'probabilities':{0:.8}}});self.assertEqual(a['metrics']['openLots'],1);self.assertEqual(a['metrics']['finalEquity'],299960);self.assertEqual(a['metrics']['trades'],0)
 def test_planned_event_forces_exit_and_prohibits_entry(self):
  self.fixture();r.EVENT_BLOCK[1]=True;v=r.leg(0,r.PROFILES[0]);self.assertEqual(r.REASONS[int(v[10])],'scheduled_event_exit');r.EVENT_BLOCK[0]=True;self.assertIsNone(r.new_position(0,r.PROFILES[0]))
 def test_carry_forbidden_before_event_even_at_100technical_score(self):
  self.fixture();r.CLOCK[1]=895;r.CARRY={1:{'1':100,'featureMinute':int(r.M[1,0])}};r.NO_CARRY[1]=True;v=r.leg(0,r.PROFILES[1]);self.assertEqual(r.REASONS[int(v[10])],'session_exit')
 def test_breakeven_stop_includes_both_fees_and_exit_slippage(self):
  self.fixture();r.M[1,2:6]=[5010,5011,5005,5006];r.MG={1:{'atr':.1,'close':100.2,'mediumBias':1,'featureMinute':int(r.M[1,0])}};q=next(p for p in r.PROFILES if p['exitStyle']=='breakeven_then_ATR_trail');v=r.leg(0,q);self.assertEqual(v[3],0);self.assertEqual(r.REASONS[int(v[10])],'stop')
 def test_logit_training_prunes_correlation_and_does_not_claim_a_probability_floor(self):
  x=np.array([[i/100,i/100,(i%3)/2] for i in range(100)],float);y=np.array([int(i>50) for i in range(100)]);m=r.logistic_fit(x,y,.1);self.assertFalse(m['active'][1]);p=r.predict(m,x);self.assertGreater(p[-1],p[0]);self.assertLess(p[0],.6);self.assertTrue(np.isfinite(m['weights']).all())
 def test_actual_frame_has_only_causal_macro_and_daily_references(self):
  for o in self.old['O']:
   self.assertLessEqual(o['signalMinute'],o['t']);self.assertLessEqual(o['mediumEnd'],o['t']);self.assertLessEqual(o['slowEnd'],o['t']);self.assertTrue(o['dailyClosedDay'] is None or o['dailyClosedDay']<r.CAL[o['day']])
   for m in o['macro'].values():self.assertTrue(m is None or m['availableMinute']<=o['t'])
   self.assertFalse(self.old['EVENT_BLOCK'][o['i']])
if __name__=='__main__':unittest.main()
