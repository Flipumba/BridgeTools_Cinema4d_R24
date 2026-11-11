import os,sys,random,math,unittest
from collections import Counter
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_edges import bridge_edges
from bridge_core import bridge
from bridge_uv import create_edge_uv_plan
from test_bridge_core import rings
class RandomizedTopology(unittest.TestCase):
 def test_pairs_of_closed_loops(self):
  rnd=random.Random(8374)
  for iteration in range(200):
   n=rnd.randint(3,12);m=rnd.randint(3,12);cuts=rnd.randint(0,4);twist=rnd.randint(-10,10)
   p,f=rings(n,m)
   edges=[(i,(i+1)%n) for i in range(n)]+[(n+i,n+(i+1)%m) for i in range(m)]
   rnd.shuffle(edges);aa=rnd.randrange(n);bb=n+rnd.randrange(m)
   pp,ff,new=bridge_edges(p,f,edges,aa,bb,cuts=cuts,twist=twist,interpolation='SURFACE',smoothness=.5)
   uv_old,uv_new=create_edge_uv_plan(f,edges,aa,bb,twist,cuts,[ff[i] for i in new],len(p))
   self.assertEqual(len(uv_new),len(new));self.assertEqual(len(uv_old),len(f))
   directed=Counter((a,b) for poly in ff for a,b in zip(poly,poly[1:]+poly[:1]))
   for a,b in edges:self.assertEqual(directed[a,b],1);self.assertEqual(directed[b,a],1)
   self.assertTrue(all(math.isfinite(v) for pnt in pp for v in pnt))
 def test_face_islands(self):
  rnd=random.Random(227)
  for iteration in range(200):
   n=rnd.randint(3,12);m=rnd.randint(3,12);cuts=rnd.randint(0,4)
   p,f=rings(n,m); pp,ff,new=bridge(p,f,range(n+m),rnd.randrange(n),n+rnd.randrange(m),cuts=cuts,twist=rnd.randint(-8,8))
   counts=Counter(tuple(sorted((a,b))) for poly in ff for a,b in zip(poly,poly[1:]+poly[:1]))
   self.assertTrue(all(x<=2 for x in counts.values()));self.assertEqual(sum(x==1 for x in counts.values()),n+m)
if __name__=='__main__':unittest.main(verbosity=2)
