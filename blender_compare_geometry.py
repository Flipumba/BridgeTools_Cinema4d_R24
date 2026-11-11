"""Reference comparisons against Blender bpy 5.2.4 in background; never tests Cinema 4D."""
import bpy,bmesh,sys,os,math
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'BridgeInteractive'))
from bridge_core import bridge
from test_merge import shape

def blender_reference(points,faces,cuts,mode,smooth,profile,shape):
 mesh=bpy.data.meshes.new('bm_ref');mesh.from_pydata(points,[],faces);mesh.update()
 obj=bpy.data.objects.new('ref',mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
 try:
  bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE');bm=bmesh.from_edit_mesh(mesh)
  for face in bm.faces:face.select_set(False)
  bm.faces.ensure_lookup_table();bm.faces[0].select_set(True);bm.faces[1].select_set(True);bmesh.update_edit_mesh(mesh)
  bpy.ops.mesh.bridge_edge_loops(type='SINGLE',number_cuts=cuts,interpolation=mode,smoothness=smooth,profile_shape_factor=profile,profile_shape=shape)
  bpy.ops.object.mode_set(mode='OBJECT');return [tuple(v.co) for v in mesh.vertices],len(mesh.polygons)
 finally:
  if obj.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
  bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)

def error(a,b):
 if len(a)!=len(b):return float('inf')
 remaining=list(b);maxerr=0
 for p in a:
  d,i=min((sum((p[k]-q[k])**2 for k in range(3)),i) for i,q in enumerate(remaining));maxerr=max(maxerr,math.sqrt(d));remaining.pop(i)
 return maxerr

p,f=shape();p=[(x+(0.6 if i>=8 else 0),y+(0.3 if i>=8 else 0),z) for i,(x,y,z) in enumerate(p)]
cases=[('LINEAR',0,0,'SMOOTH'),('PATH',1,0,'SMOOTH'),('SURFACE',1,0,'SMOOTH'),
       ('LINEAR',0,.5,'SMOOTH'),('LINEAR',0,-.5,'SMOOTH'),('LINEAR',0,.5,'SPHERE'),('LINEAR',0,.5,'SHARP')]
for mode,smooth,profile,profshape in cases:
 ref,count=blender_reference(p,f,3,mode,smooth,profile,profshape)
 candidate,ff,_=bridge(p,f,[0,1],0,8,cuts=3,smoothness=smooth,profile=profile,interpolation=mode,profile_shape=profshape)
 print(mode,smooth,profile,profshape,'vertex_error',round(error(candidate,ref),6),'face_counts',len(ff),count)
