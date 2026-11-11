"""Overlapping projection selection; simulated API, not Cinema 4D."""
import os,runpy
root=os.path.dirname(__file__)
g=runpy.run_path(os.path.join(root,'test_integration_stub.py'))
c,Vec,mod=g['c'],g['Vec'],g['mod']
doc=g['Doc'](); c.documents.GetActiveDocument=lambda:doc
for j in range(4):
    p=doc.obj.pts[j]; doc.obj.pts[4+j]=Vec(p.x,p.y,3)
t=mod['Tool'](); bd=g['BD']()
def click(x,y):
    t.GetCursorInfo(doc,None,bd,x,y,g['BC']())
    t.MouseInput(doc,None,bd,None,{c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT})
click(0,0); assert len(t.anchors)==1
click(0,0); assert [a[0] for a in t.anchors]==[0,1]
assert t.preview_data is not None
print('PASS: projected-overlap anchors select different loops; mocked API only.')
