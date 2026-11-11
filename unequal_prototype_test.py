import bpy,bmesh,sys
sys.path[:0]=['/data/bridge_full_work/BridgeInteractive','/data/bridge_full_work'];from unequal_prototype import candidate
from blender_compare_geometry import error
p=[(-1,-1,0),(1,-1,0),(0,1,0),(-1,-1,2),(1,-1,2),(1,1,2),(-1,1,2)]
p += [(x,y,z-1) for x,y,z in p[:3]]+[(x,y,z+1) for x,y,z in p[3:7]]
f=[(0,1,2),(6,5,4,3)]+[(7+i,7+(i+1)%3,(i+1)%3,i) for i in range(3)]+[(3+i,3+(i+1)%4,10+(i+1)%4,10+i) for i in range(4)]
for cuts in (0,1,2,3):
 mesh=bpy.data.meshes.new('unequal');mesh.from_pydata(p,[],f);mesh.update();obj=bpy.data.objects.new('unequal',mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE');bm=bmesh.from_edit_mesh(mesh);bm.faces.ensure_lookup_table()
 for face in bm.faces:face.select_set(False)
 bm.faces[0].select_set(True);bm.faces[1].select_set(True);bmesh.update_edit_mesh(mesh)
 bpy.ops.mesh.bridge_edge_loops(type='SINGLE',number_cuts=cuts,interpolation='LINEAR',smoothness=0)
 bpy.ops.object.mode_set(mode='OBJECT');ref=[tuple(v.co) for v in mesh.vertices];n=len(mesh.polygons)
 pp,ff,pairs,tris=candidate(p,f,[0,1],0,3,cuts)
 print('cuts',cuts,'vertex diff',error(pp,ref),'face counts',len(ff),n,'cross pairs',pairs)
 bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
