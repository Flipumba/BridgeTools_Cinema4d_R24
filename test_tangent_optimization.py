"""Reference comparison for one-pass boundary tangent calculation."""
import math,os,random,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
import bridge_core as g

def reference(points,faces,loop,excluded,fallback):
 rim=set(loop);result={}
 for v in rim:
  total=(0.,0.,0.);count=0
  for i,face in enumerate(faces):
   if i in excluded or v not in face:continue
   if not any(x in rim and x!=v for x in face):continue
   total=g.add(total,g.sub(points[v],g.centroid([points[x] for x in face])));count+=1
  result[v]=g.unit(total) if count else fallback
 return result

class TangentTests(unittest.TestCase):
 def test_random_reference_equivalence(self):
  rng=random.Random(2026)
  for trial in range(100):
   points=[tuple(rng.uniform(-10,10) for _ in range(3)) for _ in range(50)]
   faces=[tuple(rng.sample(range(50),rng.choice([3,4]))) for _ in range(90)]
   rim=rng.sample(range(50),rng.randint(3,18)); excluded=set(rng.sample(range(90),15));fallback=(0.,0.,1.)
   actual=g.boundary_tangents(points,faces,rim,excluded,fallback);expected=reference(points,faces,rim,excluded,fallback)
   self.assertEqual(actual,expected)
 def test_no_faces(self):
  self.assertEqual(g.boundary_tangents([(0,0,0),(1,0,0),(0,1,0)],[],[0,1,2],fallback=(0,0,1)),{0:(0,0,1),1:(0,0,1),2:(0,0,1)})
if __name__=='__main__':unittest.main()
