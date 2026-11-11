import os,runpy
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
from test_merge import shape
c=g['c'];D=g['doc'];Obj=g['Obj'];Sel=g['Sel'];Vec=g['Vec'];P=g['Polygon'];mod=g['mod']
class Tag:
 def __init__(self,t,s):self.type=t;self.sel=Sel(s)
 def __getitem__(self,key):return False
 def GetType(self):return self.type
 def GetName(self):return 'Selection'
 def GetBaseSelect(self):return self.sel
 def Message(self,*args):pass
class TestObj(Obj):
 def __init__(self):
  super().__init__();p,f=shape();self.pts=[Vec(*v) for v in p];self.fs=[P(*v) for v in f]
  self.ts=[Tag(c.Tpolygonselection,[0,2,5]),Tag(c.Tpointselection,[0,1,8]),Tag(c.Tedgeselection,[0,8])]
  self.ph=Sel([2,3]);self.eh=Sel([8]);self.pth=Sel([2]);self.pb=Sel([9])
 def GetTags(self):return self.ts
 def GetPolygonH(self):return self.ph
 def GetEdgeH(self):return self.eh
 def GetPointH(self):return self.pth
 def GetPhongBreak(self):return self.pb
D.obj=TestObj();D.undo=0;t=mod['Tool']();t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(1,8)]
t.make_preview();t.apply()
assert D.obj.ts[0].sel.s=={0,3}
assert D.obj.ts[1].sel.s=={0,1,8}
assert D.obj.ph.s=={0,1};assert D.obj.pth.s=={2};assert D.obj.eh.s and D.obj.pb.s
assert D.undo==4
print('PASS: simulated polygon/point/edge tags, hidden components, Phong-break remapping; not tested in Cinema 4D.')
