"""Rollback logic simulation, not a Cinema 4D runtime test."""
import os,runpy,copy
root=os.path.dirname(__file__);g=runpy.run_path(os.path.join(root,'test_integration_stub.py'));c=g['c'];Obj=g['Obj'];Vec=g['Vec'];P=g['Polygon'];mod=g['mod'];doc=g['doc']
class FailureObject(Obj):
 def SetPolygon(self,i,p):raise RuntimeError('Injected write failure')
class UndoDoc:
 def __init__(self):self.obj=FailureObject();self.undo_copy=None;self.rolled=False
 def GetActiveObject(self):return self.obj
 def StartUndo(self):return True
 def AddUndo(self,typ,obj):self.undo_copy=copy.deepcopy(self.obj);return True
 def EndUndo(self):return True
 def DoUndo(self):self.obj=self.undo_copy;self.rolled=True;return True
D=UndoDoc();c.documents.GetActiveDocument=lambda:D;t=mod['Tool']();t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(1,4)];t.make_preview()
before=t.snapshot
try:t.apply();raise AssertionError('Expected failure')
except RuntimeError as e:assert 'Injected' in str(e)
assert D.rolled and mod['read_object'](D.obj)==before
print('PASS: injected write failure triggers simulated rollback, source geometry restored. Not a Cinema 4D runtime test.')
