"""Simulate edge selection, clicks, preview and UV writes without Cinema 4D."""
import os,runpy
p=os.path.dirname(__file__);g=runpy.run_path(os.path.join(p,'test_integration_stub.py'))
uvg=runpy.run_path(os.path.join(p,'test_uv_integration_stub.py'))
c=g['c'];D=g['doc'];BD=g['BD'];BC=g['BC'];Obj=g['Obj'];Sel=g['Sel'];mod=g['mod'];Tag=uvg['Tag']
c.BaseSelect=Sel
class EdgeObject(Obj):
 def __init__(self):super().__init__();self.es=Sel(range(8));self.tag=Tag(2)
 def GetTags(self):return [self.tag]
 def ResizeObject(self,p,v):
  ok=super().ResizeObject(p,v);n=len(self.tag.data)
  self.tag.data=self.tag.data[:v]+[{'a':g['Vec'](),'b':g['Vec'](),'c':g['Vec'](),'d':g['Vec']()} for _ in range(max(0,v-n))]
  return ok
D.obj=EdgeObject();D.undo=0;t=mod['Tool']();t.cuts=1;t.input_mode=1;bd=BD()
t.GetCursorInfo(D,None,bd,0,0,BC());t.MouseInput(D,None,bd,None,{c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT})
t.GetCursorInfo(D,None,bd,100,0,BC());t.MouseInput(D,None,bd,None,{c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT})
assert t.preview_data and len(D.obj.fs)==2
t.Draw(D,None,bd,None,None,0);assert bd.lines
t.apply();assert len(D.obj.fs)==10 and len(D.obj.tag.data)==10 and D.undo==2
print('PASS: simulated edge-mode clicks, preview and UV apply; not tested in Cinema 4D.')
