import sys,os,unittest
from collections import Counter
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_edges import bridge_edges,ordered_chains
class EdgeTests(unittest.TestCase):
 def test_discovery(self):
  a=ordered_chains([(2,3),(1,2),(8,9),(9,10),(10,8)])
  self.assertEqual(len(a),2);self.assertEqual(sorted(len(v) for v,_ in a),[3,3]);self.assertEqual(sum(c for _,c in a),1)
  with self.assertRaises(ValueError):ordered_chains([(0,1),(1,2),(1,3)])
 def test_closed(self):
  pts=[(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,2),(1,0,2),(1,1,2),(0,1,2)]
  faces=[(0,3,2,1),(4,5,6,7)]; edges=[(i,(i+1)%4) for i in range(4)]+[(4+i,4+(i+1)%4) for i in range(4)]
  p,f,new=bridge_edges(pts,faces,edges,0,4,cuts=2)
  self.assertEqual((len(p),len(f),len(new)),(16,14,12))
  directed=Counter((a,b) for face in f for a,b in zip(face,face[1:]+face[:1]))
  for a,b in edges:self.assertEqual(directed[a,b],1);self.assertEqual(directed[b,a],1)
 def test_open(self):
  pts=[(0,0,0),(1,0,0),(1,-1,0),(0,-1,0),(0,0,2),(1,0,2),(1,-1,2),(0,-1,2)]
  fs=[(0,1,2,3),(5,4,7,6)]
  p,f,new=bridge_edges(pts,fs,[(0,1),(4,5)],1,5,cuts=1)
  self.assertEqual(len(new),2);self.assertEqual(len(p),10)
  with self.assertRaises(ValueError):bridge_edges(pts,fs,[(0,1),(4,5)],1,5,twist=1)
 def test_internal_edge_rejected(self):
  p=[(0,0,0),(1,0,0),(0,1,0),(0,-1,0),(0,0,2),(1,0,2),(0,1,2)]
  with self.assertRaises(ValueError):bridge_edges(p,[(0,1,2),(1,0,3),(4,5,6)],[(0,1),(4,5)],0,5)
if __name__=='__main__':unittest.main(verbosity=2)
