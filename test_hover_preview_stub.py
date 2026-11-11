"""Interactive provisional preview behavior with a mocked API, not Cinema 4D."""
import os,runpy
G=runpy.run_path(os.path.join(os.path.dirname(__file__),'test_integration_stub.py'))
c,mod=G['c'],G['mod']; doc=G['Doc'](); c.documents.GetActiveDocument=lambda:doc
t=mod['Tool'](); bd=G['BD'](); BC=G['BC']
def hover(x,y):t.GetCursorInfo(doc,None,bd,x,y,BC())
def click():t.MouseInput(doc,None,bd,None,{c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT})
hover(0,0);click();assert len(t.anchors)==1 and t.preview_data is None
hover(100,0);assert len(t.anchors)==1 and t.hover_anchor==(1,4) and t.preview_data is not None
try:t.apply();raise AssertionError('Unconfirmed hover must not apply')
except ValueError:pass
assert len(doc.obj.fs)==2
hover(110,0);assert t.hover_anchor==(1,5) and len(t.anchors)==1
hover(60,50);assert t.hover_anchor is None and t.preview_data is None
hover(100,0);click();assert len(t.anchors)==2 and t.preview_data is not None
t.apply();assert len(doc.obj.fs)>2
# An external geometry edit invalidates a provisional preview.
doc=G['Doc']();c.documents.GetActiveDocument=lambda:doc;t=mod['Tool']();hover(0,0);click();hover(100,0)
assert t.preview_data is not None
doc.obj.pts[0]=G['Vec'](5,5,5);hover(110,0)
assert not t.anchors and t.preview_data is None
print('PASS: hover preview, move, leave, confirm and invalidation. Mocked API only.')
