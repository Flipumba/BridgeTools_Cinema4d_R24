import os, sys, unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_core import bridge
# Two capped square tubes: each has four side quads and a cap facing outwards.
def shape():
 p=[(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
    (-1,-1,2),(1,-1,2),(1,1,2),(-1,1,2),(-1,-1,3),(1,-1,3),(1,1,3),(-1,1,3)]
 f=[(0,1,2,3),(11,10,9,8)]
 f.extend((i+4,(i+1)%4+4,(i+1)%4,i) for i in range(4))
 f.extend((8+i,8+(i+1)%4,12+(i+1)%4,12+i) for i in range(4))
 return p,f
class MergeTests(unittest.TestCase):
 def test_join(self):
  p,f=shape(); pts,faces,new=bridge(p,f,[0,1],0,8,merge=True,merge_factor=.25)
  assert len(new)==8 and len(faces)==8
  self.assertAlmostEqual(pts[0][2],.5)
  self.assertTrue(all(i not in (8,9,10,11) for face in faces for i in face))
  counts={}
  for face in faces:
   for a,b in zip(face,face[1:]+face[:1]):
    edge=tuple(sorted((a,b)));counts[edge]=counts.get(edge,0)+1
  self.assertTrue(all(v<=2 for v in counts.values()))
  for a in range(4):self.assertEqual(counts[tuple(sorted((a,(a+1)%4)))],2)
 def test_invalid_factor(self):
  p,f=shape()
  with self.assertRaises(ValueError):bridge(p,f,[0,1],0,8,merge=True,merge_factor=2)
if __name__=='__main__':unittest.main(verbosity=2)
