import os,sys,unittest
from collections import Counter
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_core import bridge_face_pairs
from test_edge_pairs import TestPairs
class FacePairs(unittest.TestCase):
 def test_multiple(self):
  p,f,e=TestPairs().shape();p2,f2,new,plans,kept=bridge_face_pairs(p,f,range(4),0,4,cuts=2)
  self.assertEqual(len(plans),2);self.assertEqual(len(new),24);self.assertEqual(len(p2),32);self.assertEqual(len(f2),24);self.assertEqual(kept,[])
  counts=Counter(tuple(sorted((a,b))) for face in f2 for a,b in zip(face,face[1:]+face[:1]))
  self.assertEqual(sum(v==1 for v in counts.values()),16);self.assertTrue(all(v<=2 for v in counts.values()))
 def test_odd(self):
  p,f,e=TestPairs().shape()
  with self.assertRaises(ValueError):bridge_face_pairs(p,f,range(3),0,4)
if __name__=='__main__':unittest.main(verbosity=2)
