"""Tests for transfer from adjacent UV corners, independent of Cinema 4D."""
import sys,os,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
import bridge_core as core, bridge_uv as uv, bridge_edges as edges
from test_merge import shape

def existing_uv(faces):
    # Deliberately create discontinuous UVs at every polygon edge.
    return [tuple((10.*i+j,100.*i-j,0.) for j in range(4)) for i in range(len(faces))]

def assert_rim_matches(test,old_faces,old_uv,new_faces,new_uv,rim,excluded):
    wanted={core.key(a,b) for a,b in rim}
    baseline={}
    for fi,f in enumerate(old_faces):
        if fi in excluded:continue
        f=core.face_vertices(f)
        for j,(a,b) in enumerate(zip(f,f[1:]+f[:1])):
            k=core.key(a,b)
            if k in wanted:baseline[k]={a:old_uv[fi][j],b:old_uv[fi][(j+1)%len(f)]}
    found=set()
    for face,coords in zip(new_faces,new_uv):
        for j,(a,b) in enumerate(zip(face,face[1:]+face[:1])):
            k=core.key(a,b)
            if k not in wanted:continue
            found.add(k)
            for v,coord in ((a,coords[j]),(b,coords[(j+1)%len(face)])):
                test.assertTrue(all(abs(x-y)<1e-8 for x,y in zip(coord,baseline[k][v])),(k,v,coord,baseline[k][v]))
    test.assertEqual(found,wanted)

class TestUVBoundary(unittest.TestCase):
 def test_face_mode_seams_and_intermediate_rows(self):
    p,f=shape();old=existing_uv(f);pp,ff,new=core.bridge(p,f,[0,1],0,8,cuts=3)
    newf=[ff[i] for i in new];_,rect=uv.create_uv_plan_with_point_count(f,[0,1],0,8,0,3,newf,len(p))
    result=uv.interpolate_boundary_uv(f,old,[0,1],0,8,0,False,rect)
    rims=[(i,(i+1)%4) for i in range(4)]+[(8+i,8+(i+1)%4) for i in range(4)]
    assert_rim_matches(self,f,old,newf,result,rims,{0,1})
    self.assertNotEqual(result,rect)
 def test_edge_open(self):
    p=[(0,0,0),(1,0,0),(1,-1,0),(0,-1,0),(0,0,2),(1,0,2),(1,-1,2),(0,-1,2)]
    f=[(0,1,2,3),(5,4,7,6)];selected=[(0,1),(4,5)];old=existing_uv(f)
    pp,ff,new=edges.bridge_edges(p,f,selected,1,5,cuts=2);newf=[ff[i] for i in new]
    _,rect=uv.create_edge_uv_plan(f,selected,1,5,0,2,newf,len(p))
    result=uv.interpolate_boundary_uv(f,old,selected,1,5,0,True,rect)
    assert_rim_matches(self,f,old,newf,result,selected,set())
 def test_isolated_boundary_is_rejected_for_safe_fallback(self):
    p,f=shape();old=existing_uv(f)
    with self.assertRaises(ValueError):uv.interpolate_boundary_uv(f,old,[0,1,2,3,4],0,8,0,False,[])
if __name__=='__main__':unittest.main(verbosity=2)
