import bpy,bmesh,sys
sys.path.insert(0,'/data/bridge_full_work');from test_merge import shape
p,f=shape()
for twist in (-2,-1,0,1,2):
 for cuts in (0,1,3):
  mesh=bpy.data.meshes.new('twist');mesh.from_pydata(p,[],f);mesh.update();obj=bpy.data.objects.new('twist',mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
  bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE');bm=bmesh.from_edit_mesh(mesh);bm.faces.ensure_lookup_table()
  for face in bm.faces:face.select_set(False)
  bm.faces[0].select_set(True);bm.faces[1].select_set(True);bmesh.update_edit_mesh(mesh)
  bpy.ops.mesh.bridge_edge_loops(type='SINGLE',number_cuts=cuts,interpolation='LINEAR',smoothness=0,twist_offset=twist)
  bpy.ops.object.mode_set(mode='OBJECT');faces=[tuple(face.vertices) for face in mesh.polygons if any(i<4 for i in face.vertices) and any(8<=i<12 for i in face.vertices)];new=sorted(set(tuple(round(c,2) for c in v.co) for v in mesh.vertices[16:]));print(twist,cuts,'faces',faces,'new',new)
  bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
