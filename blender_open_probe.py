import sys,os,math
sys.path[:0]=['/data/bridge_full_work/BridgeInteractive','/data/bridge_full_work']
import bpy,bmesh
from bridge_edges import bridge_edges
from blender_compare_geometry import error

def reference(points,faces,selection,cuts,mode,smooth,profile,shape):
 mesh=bpy.data.meshes.new('open_ref');mesh.from_pydata(points,[],faces);mesh.update();obj=bpy.data.objects.new('openref',mesh)
 bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
 try:
  bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='EDGE');bm=bmesh.from_edit_mesh(mesh)
  for f in bm.faces:f.select_set(False)
  for e in bm.edges:e.select_set(False)
  for v in bm.verts:v.select_set(False)
  selected={frozenset(e) for e in selection}
  for edge in bm.edges:
   if frozenset(v.index for v in edge.verts) in selected:edge.select_set(True)
  bmesh.update_edit_mesh(mesh)
  status=bpy.ops.mesh.bridge_edge_loops(type='SINGLE',number_cuts=cuts,interpolation=mode,smoothness=smooth,profile_shape_factor=profile,profile_shape=shape)
  bpy.ops.object.mode_set(mode='OBJECT')
  return [tuple(v.co) for v in mesh.vertices],len(mesh.polygons),status
 finally:
  if obj.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)

cases=0;fails=[]
for kind in ('single','polyline'):
 if kind=='single':
  pts=[(0,0,0),(1,0,0),(1,-1,0),(0,-1,0),(0.3,0.1,2),(1.3,0.1,2),(1.3,-1,2),(.3,-1,2)]
  faces=[(0,1,2,3),(5,4,7,6)];selected=[(0,1),(4,5)];a,b=1,5
 else:
  pts=[(0,0,0),(1,.3,0),(2,0,0),(0,-1,0),(1,-1,0),(2,-1,0),(.3,.1,2),(1.3,.4,2),(2.3,.1,2),(.3,-1,2),(1.3,-1,2),(2.3,-1,2)]
  faces=[(0,1,4,3),(1,2,5,4),(7,6,9,10),(8,7,10,11)];selected=[(0,1),(1,2),(6,7),(7,8)];a,b=2,8
 for mode in ('LINEAR','PATH','SURFACE'):
  for sm in (0.,.5,1.,2.):
   for profile in (0.,.5):
    for shape in (('SMOOTH','SPHERE','ROOT','INVERSE_SQUARE','SHARP','LINEAR') if profile else ('SMOOTH',)):
     ref,count,status=reference(pts,faces,selected,3,mode,sm,profile,shape)
     candidate,ff,_=bridge_edges(pts,faces,selected,a,b,cuts=3,smoothness=sm,profile=profile,interpolation=mode,profile_shape=shape)
     err=error(candidate,ref); cases+=1
     if err>1e-4 or len(ff)!=count:fails.append((kind,mode,sm,profile,shape,round(err,6),len(ff),count,status))
print('OPEN CASES',cases,'FAILURES',len(fails))
for x in fails:print('FAIL',x)
