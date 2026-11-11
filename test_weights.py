import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_weights import apply_pair_weights
from test_merge import shape
from test_edge_pairs import TestPairs
class WeightTests(unittest.TestCase):
 def test_face_bridge_weights(self):
  p,f=shape();weights=[0.]*8+[1.]*8
  out=apply_pair_weights(weights,f,[0,1],0,8,0,3)
  self.assertEqual(len(out),28)
  self.assertTrue(all(abs(v-.25)<1e-9 for v in out[16:20]));self.assertTrue(all(abs(v-.75)<1e-9 for v in out[24:28]))
 def test_face_merge_weights(self):
  p,f=shape();w=[0.]*8+[1.]*8
  out=apply_pair_weights(w,f,[0,1],0,8,0,0,merge=True,merge_factor=.3)
  self.assertTrue(all(abs(out[i]-.3)<1e-9 for i in range(4)))
 def test_edge_weights(self):
  p,f,e=TestPairs().shape();w=[0.]*4+[1.]*12
  out=apply_pair_weights(w,f,e[:8],0,4,0,1,edge_mode=True)
  self.assertTrue(all(abs(v-.5)<1e-9 for v in out[16:20]))
if __name__=='__main__':unittest.main(verbosity=2)
