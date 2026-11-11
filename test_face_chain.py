import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
import bridge_core as g,bridge_validate as v
class ChainTests(unittest.TestCase):
 def setUp(self):
  self.p=[];self.f=[]
  for z in (0.,2.,4.):
   self.p.extend([(-1.,-1.,z),(1.,-1.,z),(1.,1.,z),(-1.,1.,z)])
  self.f=[(0,1,2,3),(7,6,5,4),(8,9,10,11)]
 def test_open_chain(self):
  p,f,new,plans,retained=g.bridge_face_chain(self.p,self.f,[0,1,2],0,4,cuts=2)
  self.assertEqual((len(p),len(f),len(new),len(plans)),(28,24,24,2));self.assertFalse(retained)
  v.validate_result(p,f,new)
 def test_closed_attempt(self):
  p,f,new,plans,retained=g.bridge_face_chain(self.p,self.f,[0,1,2],0,4,cuts=0,closed=True)
  self.assertEqual(len(plans),3)
  v.validate_result(p,f,new)
 def test_even_closed(self):
  p=self.p+[(-1.,-1.,6.),(1.,-1.,6.),(1.,1.,6.),(-1.,1.,6.)]
  f=self.f+[(15,14,13,12)]
  pp,ff,new,plans,retained=g.bridge_face_chain(p,f,[0,1,2,3],0,4,cuts=0,closed=True)
  self.assertEqual((len(ff),len(plans)),(16,4));v.validate_result(pp,ff,new)
 def test_middle_with_retained_face_fails_safely(self):
  from test_merge import shape
  p,f=shape();base=len(p);p+= [(x,y,z+6) for x,y,z in p[:8]];f.append(tuple(base+i for i in (0,1,2,3)));f += [(base+i+4,base+(i+1)%4+4,base+(i+1)%4,base+i) for i in range(4)]
  pp,ff,new,plans,retained=g.bridge_face_chain(p,f,[0,1,10],0,8,cuts=1)
  with self.assertRaises(ValueError):v.validate_result(pp,ff,new)
 def test_merge_chain(self):
  from test_merge import shape
  points,faces=shape();points += [(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)];faces += [(19,18,17,16)]
  p,f,new,plans,kept=g.bridge_face_chain(points,faces,[0,1,10],0,16,merge=True,merge_factor=.5)
  self.assertEqual((len(f),len(plans),len(kept)),(8,2,8));v.validate_result(p,f,new)
  self.assertAlmostEqual(p[0][2],1.25)
  self.assertEqual(len({i for face in f for i in face}),12)
 def test_merge_without_retained_surface_is_rejected(self):
  with self.assertRaises(ValueError):g.bridge_face_chain(self.p,self.f,[0,1,2],0,4,merge=True)
 def test_merge_unequal_rejected(self):
  points=self.p+[(0,0,3)];faces=self.f+[(4,5,12)]
  with self.assertRaises(ValueError):g.bridge_face_chain(points,faces,[0,1,2,3],0,4,merge=True)

if __name__=='__main__':unittest.main(verbosity=2)
