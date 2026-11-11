import os,sys,unittest,importlib.util
root=os.path.join(os.path.dirname(__file__),'BridgeInteractive');sys.path.insert(0,root)
spec=importlib.util.spec_from_file_location('bridge_interactive_core',os.path.join(root,'bridge_core.py'));mod=importlib.util.module_from_spec(spec);sys.modules['bridge_interactive_core']=mod;spec.loader.exec_module(mod)
from bridge_uv import create_uv_plan_with_point_count,remap_uv_pins
from test_merge import shape
class UVTests(unittest.TestCase):
 def test_retained_pins_and_seam(self):
  p,f=shape();p.append((999,999,999)) # unused point before new rings
  pp,ff,new=mod.bridge(p,f,[0,1],0,8,cuts=2)
  old,uv=create_uv_plan_with_point_count(f,[0,1],0,8,0,2,[ff[i] for i in new],len(p))
  self.assertEqual(old,list(range(2,10)));self.assertEqual(len(uv),len(new))
  self.assertTrue(all(len(c)==4 for c in uv));self.assertTrue(all(max(x[0] for x in face)-min(x[0] for x in face)<=.5 for face in uv))
  self.assertEqual(remap_uv_pins([0,7,8,11,36,39],old),{0,3,28,31})
 def test_merge(self):
  p,f=shape();pp,ff,new=mod.bridge(p,f,[0,1],0,8,merge=True)
  old,uv=create_uv_plan_with_point_count(f,[0,1],0,8,0,0,[],len(p),True)
  self.assertEqual(len(old),8);self.assertEqual(uv,[])
if __name__=='__main__':unittest.main(verbosity=2)
