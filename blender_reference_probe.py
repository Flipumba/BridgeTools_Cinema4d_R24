"""Blender background reference probe; requires local bpy runtime, not a Cinema 4D test."""
import bpy,bmesh,os,sys,collections
sys.path.insert(0,os.path.dirname(__file__))
from test_merge import shape
p,f=shape(); mesh=bpy.data.meshes.new('reference_mesh'); mesh.from_pydata(p,[],f);mesh.update()
obj=bpy.data.objects.new('reference',mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='FACE')
bm=bmesh.from_edit_mesh(mesh)
for face in bm.faces:face.select_set(False)
bm.faces.ensure_lookup_table();bm.faces[0].select_set(True);bm.faces[1].select_set(True);bmesh.update_edit_mesh(mesh)
status=bpy.ops.mesh.bridge_edge_loops(type='SINGLE',number_cuts=1,interpolation='LINEAR',smoothness=0)
bpy.ops.object.mode_set(mode='OBJECT');print('status',status,'vertices',len(mesh.vertices),'faces',len(mesh.polygons))
print('coords',sorted(tuple(round(c,5) for c in v.co) for v in mesh.vertices))
