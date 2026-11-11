"""Multi-pair UV source remapping using a mocked API, NOT Cinema 4D."""
import os,runpy,unittest
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
u=runpy.run_path(os.path.join(root,'test_uv_integration_stub.py'))
from test_merge import shape
from test_uv_boundary import assert_rim_matches
c,D,Obj,Sel,Vec,Poly,mod=g['c'],g['doc'],g['Obj'],g['Sel'],g['Vec'],g['Polygon'],g['mod'];Tag=u['Tag'];c.BaseSelect=Sel
class DoubleTube(Obj):
 def __init__(self):
  super().__init__();p,f=shape();p2=[(x+10,y,z) for x,y,z in p];f2=[tuple(v+len(p) for v in face) for face in f]
  self.pts=[Vec(*v) for v in p+p2];self.fs=[Poly(*v) for v in f+f2];self.ps=Sel((0,1,10,11));self.tag=Tag(len(self.fs))
 def GetTags(self):return [self.tag]
 def ResizeObject(self,p,v):
  ok=super().ResizeObject(p,v);n=len(self.tag.data)
  self.tag.data=self.tag.data[:v]+[{'a':Vec(),'b':Vec(),'c':Vec(),'d':Vec()} for _ in range(max(0,v-n))]
  return ok
D.obj=DoubleTube();D.undo=0;old_faces=[(f.a,f.b,f.c,f.d) for f in D.obj.fs]
old_uv=[tuple((u[k].x,u[k].y,u[k].z) for k in ('a','b','c','d')) for u in D.obj.tag.data]
t=mod['Tool']();t.cuts=1;t.pair_mode=True;t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(1,8)];t.make_preview();t.apply()
new_faces=[(f.a,f.b,f.c,f.d) for f in D.obj.fs[16:]]
new_uv=[tuple((u[k].x,u[k].y,u[k].z) for k in ('a','b','c','d')) for u in D.obj.tag.data[16:]]
rims=[]
for offset in (0,16):
 rims += [(offset+i,offset+(i+1)%4) for i in range(4)]
 rims += [(offset+8+i,offset+8+(i+1)%4) for i in range(4)]
assert_rim_matches(unittest.TestCase(),old_faces,old_uv,new_faces,new_uv,rims,{0,1,10,11})
print('PASS: multi-pair per-tag UV boundaries; mocked API only.')
