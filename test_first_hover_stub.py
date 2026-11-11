"""Mock-only test for first-vertex highlighting and context refresh."""
import os,runpy
G=runpy.run_path(os.path.join(os.path.dirname(__file__),'test_integration_stub.py'))
c,mod=G['c'],G['mod'];doc=G['Doc']();c.documents.GetActiveDocument=lambda:doc
bd=G['BD']();handles=[];bd.DrawHandle=lambda p,*a:handles.append((p.x,p.y,p.z))
t=mod['Tool']()
def hover(x,y):t.GetCursorInfo(doc,None,bd,x,y,G['BC']())
hover(0,0);assert t.hover_first==(0,0) and t.anchors==[]
t.Draw(doc,None,bd,None,None,0);assert handles==[(0,0,0)]
hover(100,0);assert t.hover_first==(1,4)
hover(50,50);assert t.hover_first is None
# Losing the selection removes stale state instead of retaining a false target.
hover(0,0);doc.obj.ps.DeselectAll();hover(0,0)
assert t.obj is None and t.hover_first is None
print('PASS: first-vertex highlight and invalidated selection. Mock API only.')
