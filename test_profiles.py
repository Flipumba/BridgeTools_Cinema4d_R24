import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_core import bridge
from test_merge import shape
class ProfileTest(unittest.TestCase):
 def test_all_profiles(self):
  pts,fs=shape();names=('SMOOTH','SPHERE','ROOT','SHARP','LINEAR','CONSTANT','INVERSE_SQUARE')
  outputs=[]
  for name in names:
   result,_,_=bridge(pts,fs,[0,1],0,8,cuts=3,profile=.5,profile_shape=name);outputs.append(result[len(pts)])
  self.assertGreaterEqual(len(set(outputs)),5)
 def test_invalid(self):
  p,f=shape()
  with self.assertRaises(ValueError):bridge(p,f,[0,1],0,8,profile_shape='wrong')
if __name__=='__main__':unittest.main(verbosity=2)
