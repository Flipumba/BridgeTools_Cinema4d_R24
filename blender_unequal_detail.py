import bpy,bmesh,sys,math
sys.path[:0]=['/data/bridge_full_work/BridgeInteractive','/data/bridge_full_work']
from bridge_core import bridge
from blender_compare_geometry import error
p=[(-1,-1,0),(1,-1,0),(0,1,0),(-1,-1,2),(1,-1,2),(1,1,2),(-1,1,2)]
p += [(x,y,z-1) for x,y,z in p[:3]]+[(x,y,z+1) for x,y,z in p[3:7]]
f=[(0,1,2),(6,5,4,3)]
f += [(7+i,7+(i+1)%3,(i+1)%3,i) for i in range(3)]
f += [(3+i,3+(i+1)%4,10+(i+1)%4,10+i) for i in range(4)]
for cuts in (0,1,2,3):
 for mode in ('LINEAR','PATH','SURFACE'):
  mesh=bpy.data.meshes.new('uneq');mesh.from_pydata(p,[],f);mesh.update();obj=bpy.data.objects.new('uneq',mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
  bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE');bm=bmesh.from_edit_mesh(mesh);bm.faces.ensure_lookup_table()
  for face in bm.faces:face.select_set(False)
  bm.faces[0].select_set(True);bm.faces[1].select_set(True);bmesh.update_edit_mesh(mesh)
  try:status=bpy.ops.mesh.bridge_edge_loops(type='SINGLE',number_cuts=cuts,interpolation=mode,smoothness=1)
  except RuntimeError as e:print('blender error',e);status={}
  bpy.ops.object.mode_set(mode='OBJECT');ref=[tuple(v.co) for v in mesh.vertices];fs=len(mesh.polygons);print("DEBUG",[tuple(z.vertices) for z in mesh.polygons])
  bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
  out,faces,_=bridge(p,f,[0,1],0,3,cuts=cuts,interpolation=mode,smoothness=1)
  print(cuts,mode,'blender vertices/faces',len(ref),fs,'plugin',len(out),len(faces),'difference',round(error(ref,out),4))
