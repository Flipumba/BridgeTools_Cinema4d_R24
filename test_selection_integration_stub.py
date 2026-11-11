import os,runpy
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
from test_merge import shape
c=g['c'];Doc=g['Doc'];Obj=g['Obj'];Sel=g['Sel'];Vec=g['Vec'];Poly=g['Polygon'];mod=g['mod'];D=g['doc']
class SelectTag:
 def __init__(self):self.sel=Sel([0,2,5,9])
 def __getitem__(self,key):return False
 def GetType(self):return c.Tpolygonselection
 def GetName(self):return 'Material regions'
 def GetBaseSelect(self):return self.sel
 def Message(self,*a):pass
class NamedObject(Obj):
 def __init__(self):
  super().__init__();p,f=shape();self.pts=[Vec(*v) for v in p];self.fs=[Poly(*v) for v in f];self.tag=SelectTag()
 def GetTags(self):return [self.tag]
D.obj=NamedObject();D.undo=0;t=mod['Tool']();t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(1,8)]
t.make_preview();t.apply();assert D.obj.tag.sel.s=={0,3,7};assert D.undo==2
print('PASS: simulated polygon selection tag remapping and undo registration.')
