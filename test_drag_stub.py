"""Relative drag and Escape behavior; fake event packets, not a C4D test."""
import os,runpy
G=runpy.run_path(os.path.join(os.path.dirname(__file__),'test_integration_stub.py'))
c=G['c'];m=G['mod'];doc=G['Doc']();c.documents.GetActiveDocument=lambda:doc
for i,name in enumerate(('BFM_INPUT_QUALIFIER','QUALIFIER_SHIFT','KEY_MLEFT','MOUSEDRAGFLAGS_NONE','MOUSEDRAGRESULT_CONTINUE','MOUSEDRAGRESULT_FINISHED','MOUSEDRAGRESULT_ESCAPE','DRAWFLAGS_ONLY_ACTIVE_VIEW','DRAWFLAGS_NO_THREAD','DRAWFLAGS_NO_ANIMATION'),100):setattr(c,name,i)
c.QUALIFIER_SHIFT=1;c.MOUSEDRAGFLAGS_NONE=0;c.DrawViews=lambda flags:True
class Window:
 def __init__(self,packets,end):self.packets=list(packets);self.end=end;self.start=None
 def MouseDragStart(self,*args):self.start=args
 def MouseDrag(self):
  if self.packets:return c.MOUSEDRAGRESULT_CONTINUE,self.packets.pop(0),0,None
  return self.end,0,0,None
 def MouseDragEnd(self):return self.end

t=m['Tool']();t.cuts=1;t.doc=doc;t.obj=doc.obj;t.snapshot=m['read_object'](doc.obj);t.anchors=[(0,0),(1,4)];t.drag_param=3;t.make_preview();before=m['read_object'](doc.obj)
def drag(end,packets):
 win=Window(packets,end);msg={c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT,c.BFM_INPUT_QUALIFIER:c.QUALIFIER_SHIFT,c.BFM_INPUT_X:50,c.BFM_INPUT_Y:60}
 assert t.MouseInput(doc,None,None,win,msg);assert win.start[-1]==0
 assert m['read_object'](doc.obj)==before and t.preview_data

drag(c.MOUSEDRAGRESULT_FINISHED,[3.,4.,5.]);assert abs(t.profile-.12)<1e-8
drag(c.MOUSEDRAGRESULT_ESCAPE,[2.,3.]);assert abs(t.profile-.12)<1e-8
print('PASS relative drag, commit and cancellation; mocked host only')
