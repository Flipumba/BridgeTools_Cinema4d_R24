"""Chain preview and application, mocked host only."""
import os,runpy
R=os.path.dirname(__file__);g=runpy.run_path(os.path.join(R,'test_integration_stub.py'));u=runpy.run_path(os.path.join(R,'test_uv_integration_stub.py'))
c,D,Obj,Sel,Vec,Poly,mod=g['c'],g['doc'],g['Obj'],g['Sel'],g['Vec'],g['Polygon'],g['mod'];Tag=u['Tag'];c.BaseSelect=Sel
class ThreeCaps(Obj):
 def __init__(self):
  super().__init__();self.pts=[Vec(x,y,z) for z in (0,2,4) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
  self.fs=[Poly(0,1,2,3),Poly(7,6,5,4),Poly(8,9,10,11)];self.ps=Sel((0,1,2));self.tag=Tag(3);self.tag.pins=Sel()
 def GetTags(self):return [self.tag]
 def ResizeObject(self,p,v):
  ok=super().ResizeObject(p,v);n=len(self.tag.data)
  self.tag.data=self.tag.data[:v]+[{'a':Vec(),'b':Vec(),'c':Vec(),'d':Vec()} for _ in range(max(0,v-n))];return ok
for mode,expected in ((2,16),(3,24)):
 D.obj=ThreeCaps();D.undo=0;t=mod['Tool']();t.sequence_mode=mode;t.cuts=1;t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(1,4)]
 t.make_preview();assert t.preview_data is not None and len(D.obj.fs)==3
 t.apply();assert len(D.obj.fs)==expected and len(D.obj.tag.data)==expected
 print('PASS mode',mode,'mesh and UV apply, mocked host only')
