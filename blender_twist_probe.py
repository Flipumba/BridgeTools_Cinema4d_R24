import bpy,bmesh,sys,os
sys.path[:0]=['/data/bridge_full_work/BridgeInteractive','/data/bridge_full_work']
from bridge_core import bridge
from blender_compare_geometry import error
from test_merge import shape
p,f=shape()
for twist in (-3,-2,-1,0,1,2,3):
 mesh=bpy.data.meshes.new('twist');mesh.from_pydata(p,[],f);mesh.update();obj=bpy.data.objects.new('twist',mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE');bm=bmesh.from_edit_mesh(mesh);bm.faces.ensure_lookup_table()
 for face in bm.faces:face.select_set(False)
 bm.faces[0].select_set(True);bm.faces[1].select_set(True);bmesh.update_edit_mesh(mesh)
 bpy.ops.mesh.bridge_edge_loops(type='SINGLE',number_cuts=3,interpolation='LINEAR',smoothness=0,twist_offset=twist)
 bpy.ops.object.mode_set(mode='OBJECT');ref=[tuple(v.co) for v in mesh.vertices];bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
 for candidate_twist in (twist,-twist):
  out,_,_=bridge(p,f,[0,1],0,8,cuts=3,twist=candidate_twist)
  print('blender',twist,'candidate',candidate_twist,'error',error(ref,out))
