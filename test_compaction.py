import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_core import bridge
from bridge_selections import compact_newly_orphaned_points
from test_bridge_core import rings
class Tests(unittest.TestCase):
 def test_island_interiors_removed_but_old_loose_preserved(self):
  p,f=rings(4,4);p.append((99,99,99));out,faces,new=bridge(p,f,range(8),0,4,cuts=1)
  compact,remapped,m=compact_newly_orphaned_points(f,faces,out,len(p))
  self.assertNotIn(8,m);self.assertNotIn(9,m);self.assertIn(10,m)
  self.assertEqual(len(compact),13);self.assertEqual(compact[m[10]],(99,99,99))
  self.assertTrue(all(i<len(compact) for f in remapped for i in f))
 def test_no_deletion(self):
  p=[(0,0,0)]*6; f=[(0,1,2,3)];p2,f2,m=compact_newly_orphaned_points(f,f,p,len(p))
  self.assertEqual(len(p2),6);self.assertEqual(f2,[(0,1,2,3)])
if __name__=='__main__':unittest.main(verbosity=2)
