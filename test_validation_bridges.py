"""The validator must accept untwisted ordinary bridges of various sizes."""
import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_core import bridge
from bridge_validate import validate_result
from test_bridge_core import rings
class ValidationBridges(unittest.TestCase):
 def test_400_regular_bridge_results(self):
  for n in range(3,13):
   for m in range(3,13):
    points,faces=rings(n,m)
    for cuts in (0,1,2,4):
     with self.subTest(n=n,m=m,cuts=cuts):
      validate_result(*bridge(points,faces,range(n+m),0,n,cuts=cuts))
if __name__=='__main__':unittest.main()
