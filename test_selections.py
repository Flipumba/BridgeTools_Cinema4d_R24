import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_selections import vertex_remap,remap_points,remap_polygons,remap_edges
class Tests(unittest.TestCase):
 def test_face_and_edge_selection(self):
  old=[(0,1,2,3),(3,2,4,5)];new=[old[1],(0,1,2,3)];retained=[1,0]
  m=vertex_remap(old,new,retained,6)
  self.assertEqual(remap_polygons({0},retained),{1})
  self.assertEqual(remap_points({1,4},m),{1,4})
  self.assertEqual(remap_edges({2},old,new,m),{0,6})
 def test_merge_point_remap(self):
  old=[(0,1,2),(3,4,5)];new=[(0,1,2),(0,4,5)];m=vertex_remap(old,new,[0,1],6)
  self.assertEqual(remap_points({0,3,4},m),{0,4})
  self.assertEqual(remap_edges({4},old,new,m),{4})
 def test_conflicting(self):
  with self.assertRaises(ValueError):vertex_remap([(0,1,2),(0,3,4)],[(1,2,3),(2,3,4)],[0,1],5)
if __name__=='__main__':unittest.main(verbosity=2)
