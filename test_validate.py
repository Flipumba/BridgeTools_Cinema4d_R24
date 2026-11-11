import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_validate import validate_result
class ValidateResult(unittest.TestCase):
 def setUp(self):self.p=[(0,0,0),(1,0,0),(0,1,0),(1,1,0),(0,-1,0),(2,0,0)]
 def test_valid(self):validate_result(self.p,[(0,1,2),(1,0,4)],[1])
 def test_zero_area(self):
  with self.assertRaisesRegex(ValueError,'нулевой площади'):validate_result(self.p,[(0,1,5)],[0])
 def test_zero_edge(self):
  p=self.p+[(0,0,0)]
  with self.assertRaisesRegex(ValueError,'нулевой длины'):validate_result(p,[(0,6,2)],[0])
 def test_duplicate(self):
  with self.assertRaisesRegex(ValueError,'дублирующийся'):validate_result(self.p,[(0,1,2),(2,1,0)],[1])
 def test_wrong_winding(self):
  with self.assertRaisesRegex(ValueError,'направление'):validate_result(self.p,[(0,1,2),(0,1,4)],[1])
 def test_nonmanifold(self):
  with self.assertRaisesRegex(ValueError,'неманифолдное'):validate_result(self.p,[(0,1,2),(1,0,4),(0,1,3)],[2])
 def test_bow_tie(self):
  p=[(0,0,0),(1,1,0),(0,1,0),(1,0,0)]
  with self.assertRaisesRegex(ValueError,'самопересекающийся'):validate_result(p,[(0,1,2,3)],[0])
 def test_nonplanar_near_cross_is_not_crossing(self):
  p=[(0,0,0),(1,1,0),(0,1,1),(1,0,1)]
  validate_result(p,[(0,1,2,3)],[0])
 def test_unrelated_nonmanifold_does_not_block(self):
  p=self.p+[(10,0,0),(11,0,0),(10,1,0)]
  validate_result(p,[(0,1,2),(1,0,4),(0,1,3),(6,7,8)],[3])
if __name__=='__main__':unittest.main()
