"""Sequential merge and weight mapping, mock-only host test."""
import os,runpy
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'));w=runpy.run_path(os.path.join(root,'test_weight_integration_stub.py'))
from test_merge import shape
c,D,Obj,Sel,Vec,Poly,mod=g['c'],g['doc'],g['Obj'],g['Sel'],g['Vec'],g['Polygon'],g['mod'];WeightTag=w['WeightTag']
class Model(Obj):
 def __init__(self):
  super().__init__();p,f=shape();p += [(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)];f += [(19,18,17,16)]
  self.pts=[Vec(*x) for x in p];self.fs=[Poly(*x) for x in f];self.ps=Sel((0,1,10));self.tag=WeightTag();self.tag.data=[0.]*8+[1.]*8+[.4]*4
 def GetTags(self):return [self.tag]
 def ResizeObject(self,p,v):
  ok=super().ResizeObject(p,v);n=len(self.tag.data);self.tag.data=self.tag.data[:p]+[0.]*max(0,p-n);return ok
D.obj=Model();D.undo=0;t=mod['Tool']();t.sequence_mode=2;t.merge=True;t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(2,16)]
t.make_preview();assert len(D.obj.pts)==20 and len(D.obj.fs)==11
t.apply();assert len(D.obj.pts)==12 and len(D.obj.fs)==8 and len(D.obj.tag.data)==12
assert all(abs(x-.6)<1e-8 for x in D.obj.tag.data[:4]);assert D.undo==2
print('PASS: sequential merge, weight interpolation and compaction in mocked host')
