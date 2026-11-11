"""Simulated UV update. Does NOT validate Cinema 4D APIs or Undo behavior."""
import os,runpy,sys
root=os.path.dirname(__file__)
g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
from test_merge import shape
from test_uv_boundary import assert_rim_matches
import unittest
c=g['c'];Vec=g['Vec'];Polygon=g['Polygon'];Sel=g['Sel'];Obj=g['Obj'];Doc=g['Doc'];toolmodule=g['mod']
c.BaseSelect=Sel
class Tag:
 def __init__(self,n):
  self.data=[{'a':Vec(i,0,0),'b':Vec(i,1,0),'c':Vec(i,1,1),'d':Vec(i,0,1)} for i in range(n)]
  self.pins=Sel([8,11,39])
 def GetType(self):return c.Tuvw
 def GetName(self):return 'UV'
 def GetDataCount(self):return len(self.data)
 def GetSlow(self,i):return self.data[i].copy()
 def SetSlow(self,i,a,b,c,d):self.data[i]={'a':a,'b':b,'c':c,'d':d}
 def GetPinSelection(self):return self.pins
 def SetPinSelection(self,s):self.pins=s;return True
 def Message(self,*a):pass
class ObjectWithUV(Obj):
 def __init__(self):
  super().__init__();p,f=shape();self.pts=[Vec(*v) for v in p];self.fs=[Polygon(*v) for v in f];self.tag=Tag(len(f))
 def GetTags(self):return [self.tag]
 def ResizeObject(self,p,v):
  out=super().ResizeObject(p,v);n=len(self.tag.data)
  self.tag.data=self.tag.data[:v]+[{'a':Vec(),'b':Vec(),'c':Vec(),'d':Vec()} for _ in range(max(0,v-n))]
  return out
D=g['doc'];D.undo=0;D.obj=ObjectWithUV();tool=toolmodule['Tool']();tool.cuts=1;tool.doc=D;tool.obj=D.obj;tool.snapshot=toolmodule['read_object'](D.obj)
old_faces=[(v.a,v.b,v.c,v.d) for v in D.obj.fs]
old_uv=[tuple((u[k].x,u[k].y,u[k].z) for k in ('a','b','c','d')) for u in D.obj.tag.data]
tool.anchors=[(0,0),(1,8)];tool.make_preview();tool.apply()
assert len(D.obj.fs)==16 and len(D.obj.tag.data)==16
for i in range(8):assert D.obj.tag.data[i]['a'].x==i+2
assert D.obj.tag.pins.s=={0,3,31}
assert D.undo==2
new_faces=[(v.a,v.b,v.c,v.d) for v in D.obj.fs[8:]]
new_uv=[tuple((u[k].x,u[k].y,u[k].z) for k in ('a','b','c','d')) for u in D.obj.tag.data[8:]]
rims=[(i,(i+1)%4) for i in range(4)]+[(8+i,8+(i+1)%4) for i in range(4)]
assert_rim_matches(unittest.TestCase(),old_faces,old_uv,new_faces,new_uv,rims,{0,1})
print('PASS: simulated retained UV corners, pin remapping, generated UVs, and undo registration; NOT a Cinema 4D runtime test.')
