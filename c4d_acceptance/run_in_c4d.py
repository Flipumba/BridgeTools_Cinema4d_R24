# Run inside Cinema 4D S24's Python environment, on the main thread.
# This isolated-document diagnostic has NOT been executed in Cinema 4D.
# It tests data and undo/redo, not real viewport picking or drawing.
import os,runpy
import c4d
from c4d import documents

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plugin=runpy.run_path(os.path.join(ROOT,'BridgeInteractive','bridge_interactive.pyp'),run_name='bridge_acceptance')
P=[(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
   (-1,-1,2),(1,-1,2),(1,1,2),(-1,1,2),(-1,-1,3),(1,-1,3),(1,1,3),(-1,1,3)]
F=[(0,1,2,3),(11,10,9,8)]
F += [(i+4,(i+1)%4+4,(i+1)%4,i) for i in range(4)]
F += [(8+i,8+(i+1)%4,12+(i+1)%4,12+i) for i in range(4)]

def selected(selection,n):return {i for i in range(n) if selection.IsSelected(i)}
def near(a,b):return abs(a-b)<1e-5

def main():
 original=documents.GetActiveDocument(); d=documents.BaseDocument()
 if d is None:raise RuntimeError('Could not create temporary document')
 documents.InsertBaseDocument(d); documents.SetActiveDocument(d)
 try:
  obj=c4d.PolygonObject(len(P),len(F))
  if obj is None:raise RuntimeError('Could not create test object')
  obj.SetName('Bridge Acceptance Test');obj.SetAllPoints([c4d.Vector(*v) for v in P])
  for i,f in enumerate(F):obj.SetPolygon(i,c4d.CPolygon(*f))
  obj.GetPolygonS().Select(0);obj.GetPolygonS().Select(1)
  uv=c4d.UVWTag(len(F));obj.InsertTag(uv)
  for i in range(len(F)):
   uv.SetSlow(i,c4d.Vector(i,0,0),c4d.Vector(i,1,0),c4d.Vector(i,1,1),c4d.Vector(i,0,1))
  pins=c4d.BaseSelect()
  for i in (8,11,39):pins.Select(i)
  if not uv.SetPinSelection(pins):raise RuntimeError('Test setup: UV pins rejected')
  weight=c4d.VariableTag(c4d.Tvertexmap,len(P));obj.InsertTag(weight)
  weight[c4d.ID_TAGFIELD_ENABLE]=False
  weight.SetAllHighlevelData([0.]*8+[1.]*8)
  d.InsertObject(obj);d.SetActiveObject(obj);obj.Message(c4d.MSG_UPDATE)
  t=plugin['Tool']();t.cuts=1;t.doc=d;t.obj=obj;t.snapshot=plugin['read_object'](obj);t.anchors=[(0,0),(1,8)]
  before=t.snapshot;t.make_preview()
  assert t.preview_data is not None and plugin['read_object'](obj)==before, 'Preview modified source geometry'
  t.apply();obj=d.GetFirstObject();uv=obj.GetTag(c4d.Tuvw);weight=obj.GetTag(c4d.Tvertexmap)
  assert obj.GetPolygonCount()==16 and obj.GetPointCount()==20, 'Wrong output mesh dimensions'
  assert uv.GetDataCount()==16 and near(uv.GetSlow(0)['a'].x,2), 'Retained UV data lost or wrong size'
  assert selected(uv.GetPinSelection(),64)=={0,3,31}, 'UV pins incorrectly remapped'
  w=weight.GetAllHighlevelData();assert len(w)==20 and all(near(x,.5) for x in w[16:]), 'Weights not interpolated'
  if not d.DoUndo():raise RuntimeError('Undo failed')
  obj=d.GetFirstObject();uv=obj.GetTag(c4d.Tuvw);weight=obj.GetTag(c4d.Tvertexmap)
  assert plugin['read_object'](obj)==before, 'Undo did not restore source geometry/selection'
  assert uv.GetDataCount()==10 and selected(uv.GetPinSelection(),40)=={8,11,39}, 'Undo did not restore UV pins'
  assert len(weight.GetAllHighlevelData())==16, 'Undo did not restore weight tag'
  if not d.DoRedo():raise RuntimeError('Redo failed')
  obj=d.GetFirstObject();uv=obj.GetTag(c4d.Tuvw);weight=obj.GetTag(c4d.Tvertexmap)
  assert obj.GetPolygonCount()==16 and uv.GetDataCount()==16 and len(weight.GetAllHighlevelData())==20, 'Redo did not restore bridge'
  assert selected(uv.GetPinSelection(),64)=={0,3,31}, 'Redo did not restore pin mapping'
  print('PASS: C4D geometry, UV pins, weights, undo and redo (viewport not tested)')
 finally:
  if original is not None:documents.SetActiveDocument(original)
  documents.KillDocument(d);c4d.EventAdd()

if __name__=='__main__':main()
