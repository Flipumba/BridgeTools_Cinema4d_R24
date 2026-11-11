"""Mock-only tests of apply/cancel keyboard routing."""
import os,runpy
G=runpy.run_path(os.path.join(os.path.dirname(__file__),'test_integration_stub.py'))
c,mod=G['c'],G['mod'];c.KEY_ENTER=5555;doc=G['Doc']();c.documents.GetActiveDocument=lambda:doc
bd=G['BD']();t=mod['Tool']();t.cuts=1
def key(k):return t.KeyboardInput(doc,None,bd,None,{c.BFM_INPUT_CHANNEL:k})
def click(x,y):
 t.GetCursorInfo(doc,None,bd,x,y,G['BC']());t.MouseInput(doc,None,bd,None,{c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT})
assert key(c.KEY_ENTER) is False and key(c.KEY_ESC) is False
click(0,0); assert key(c.KEY_ENTER) is False
assert key(c.KEY_ESC) is True and not t.anchors and len(doc.obj.fs)==2
click(0,0);click(100,0)
assert key(c.KEY_ENTER) is True and len(doc.obj.fs)==8 and not t.anchors
print('PASS: mock Enter applies, Esc cancels, keys pass through when idle.')
