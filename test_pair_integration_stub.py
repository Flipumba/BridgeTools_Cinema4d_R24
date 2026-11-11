import os,runpy
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
uvg=runpy.run_path(os.path.join(root,'test_uv_integration_stub.py'))
from test_edge_pairs import TestPairs
c=g['c'];D=g['doc'];Obj=g['Obj'];Sel=g['Sel'];Vec=g['Vec'];Poly=g['Polygon'];Tag=uvg['Tag'];mod=g['mod'];c.BaseSelect=Sel
class PairObject(Obj):
 def __init__(self):
  super().__init__();p,f,e=TestPairs().shape();self.pts=[Vec(*v) for v in p];self.fs=[Poly(*x) for x in f];self.es=Sel(range(16));self.tag=Tag(len(f))
 def GetTags(self):return [self.tag]
 def ResizeObject(self,p,v):
  ok=super().ResizeObject(p,v);n=len(self.tag.data)
  self.tag.data=self.tag.data[:v]+[{'a':Vec(),'b':Vec(),'c':Vec(),'d':Vec()} for _ in range(max(0,v-n))]
  return ok
D.obj=PairObject();D.undo=0;t=mod['Tool']();t.cuts=1;t.input_mode=1;t.pair_mode=True;t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.edge_selection=mod['read_selected_edges'](D.obj,t.snapshot[1]);t.anchors=[(0,0),(1,4)];t.make_preview()
assert len(t.preview_plans)==2 and len(D.obj.fs)==4
t.apply();assert len(D.obj.fs)==20 and len(D.obj.tag.data)==20 and D.undo==2
print('PASS: simulated multi-pair bridge with UV; not tested in Cinema 4D.')
