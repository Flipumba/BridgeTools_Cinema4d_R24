import os,runpy
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
from test_merge import shape
c=g['c'];D=g['doc'];Obj=g['Obj'];Vec=g['Vec'];Poly=g['Polygon'];mod=g['mod']
class WeightTag:
 def __init__(self):self.data=[0.]*8+[1.]*8
 def __getitem__(self,key):return False
 def GetType(self):return c.Tvertexmap
 def GetName(self):return 'Weights'
 def GetAllHighlevelData(self):return self.data[:]
 def GetDataCount(self):return len(self.data)
 def SetAllHighlevelData(self,data):self.data=list(data)
 def Message(self,*args):pass
class Model(Obj):
 def __init__(self):
  super().__init__();p,f=shape();self.pts=[Vec(*x) for x in p];self.fs=[Poly(*x) for x in f];self.tag=WeightTag()
 def GetTags(self):return [self.tag]
 def ResizeObject(self,p,v):
  ok=super().ResizeObject(p,v);n=len(self.tag.data);self.tag.data=self.tag.data[:p]+[0.]*max(0,p-n);return ok
D.obj=Model();D.undo=0;t=mod['Tool']();t.cuts=1;t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(1,8)];t.make_preview();t.apply()
assert len(D.obj.tag.data)==20 and all(abs(v-.5)<1e-9 for v in D.obj.tag.data[16:]);assert D.undo==2
print('PASS: simulated static Vertex Map interpolation and undo registration; not tested in Cinema 4D.')
