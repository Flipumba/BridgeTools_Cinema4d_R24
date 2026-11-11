import os,runpy
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
from test_bridge_core import rings
D=g['doc'];Obj=g['Obj'];Sel=g['Sel'];Vec=g['Vec'];Poly=g['Polygon'];m=g['mod']
class FanObj(Obj):
 def __init__(self):
  super().__init__();p,f=rings(4,4);p.append((99,99,99));self.pts=[Vec(*v) for v in p];self.fs=[Poly(*x) for x in f];self.ps=Sel(range(8))
D.obj=FanObj();D.undo=0;t=m['Tool']();t.cuts=1;t.doc=D;t.obj=D.obj;t.snapshot=m['read_object'](D.obj);t.anchors=[(0,0),(1,4)]
t.make_preview();t.apply()
assert len(D.obj.pts)==13 and len(D.obj.fs)==8
assert any((v.x,v.y,v.z)==(99,99,99) for v in D.obj.pts)
assert all(max(f.a,f.b,f.c,f.d)<13 for f in D.obj.fs)
print('PASS: simulated cap interior cleanup and preservation of preexisting loose points; not Cinema 4D.')
