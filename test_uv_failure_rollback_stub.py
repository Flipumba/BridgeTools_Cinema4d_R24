"""Mock-only check: a rejected UV pin update triggers rollback."""
import copy,os,runpy
base=runpy.run_path(os.path.join(os.path.dirname(__file__),'test_uv_integration_stub.py'))
g=base['g'];c=g['c'];mod=g['mod'];Model=base['ObjectWithUV'];Tag=base['Tag']
class FailPinTag(Tag):
 def SetPinSelection(self,s):return False
class FailModel(Model):
 def __init__(self):
  super().__init__();self.tag=FailPinTag(len(self.fs))
class Doc:
 def __init__(self):self.obj=FailModel();self.backup=None;self.rolled=False
 def GetActiveObject(self):return self.obj
 def StartUndo(self):return True
 def AddUndo(self,*a):
  if self.backup is None:self.backup=copy.deepcopy(self.obj)
  return True
 def EndUndo(self):return True
 def DoUndo(self):self.obj=self.backup;self.rolled=True;return True
D=Doc();c.documents.GetActiveDocument=lambda:D
t=mod['Tool']();t.doc=D;t.obj=D.obj;t.snapshot=mod['read_object'](D.obj);t.anchors=[(0,0),(1,8)]
t.make_preview();before=t.snapshot
try:t.apply();raise AssertionError('Expected UV pin update failure')
except RuntimeError as e:assert 'UV' in str(e)
assert D.rolled and mod['read_object'](D.obj)==before
assert D.obj.tag.pins.s=={8,11,39}
print('PASS: rejected pin update restores original mesh and UV pins in mock undo.')
