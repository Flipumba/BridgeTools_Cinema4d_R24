import os,sys,unittest
from collections import Counter
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_edges import bridge_edge_pairs
class TestPairs(unittest.TestCase):
 def shape(self):
  pts=[];faces=[];edges=[]
  for k in range(4):
   base=len(pts);x=(k//2)*10;z=(k%2)*3
   pts.extend([(x,0,z),(x+1,0,z),(x+1,1,z),(x,1,z)])
   faces.append(tuple(base+i for i in ((0,3,2,1) if k%2==0 else (0,1,2,3))))
   edges.extend((base+i,base+(i+1)%4) for i in range(4))
  return pts,faces,edges
 def test_pairs(self):
  p,f,e=self.shape();pp,ff,new,plans=bridge_edge_pairs(p,f,e,0,4,cuts=2)
  self.assertEqual(len(plans),2);self.assertEqual(len(new),24);self.assertEqual(len(pp),32);self.assertEqual(len(ff),28)
  counts=Counter(tuple(sorted((a,b))) for face in ff for a,b in zip(face,face[1:]+face[:1]))
  self.assertTrue(all(x==2 for x in counts.values()))
 def test_odd(self):
  p,f,e=self.shape()
  with self.assertRaises(ValueError):bridge_edge_pairs(p,f,e[:12],0,4)
 def test_merge(self):
  p,f,e=self.shape();pp,ff,new,plans=bridge_edge_pairs(p,f,e,0,4,merge=True)
  self.assertEqual(len(ff),4);self.assertEqual(len(plans),2)
if __name__=='__main__':unittest.main(verbosity=2)
