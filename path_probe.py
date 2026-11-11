import sys
sys.path[:0]=['/data/bridge_full_work/BridgeInteractive','/data/bridge_full_work']
import bridge_core as g
from test_merge import shape
from blender_compare_geometry import blender_reference,error
from math import atan2
p,f=shape();p=[(x+(0.6 if i>=8 else 0),y+(0.3 if i>=8 else 0),z) for i,(x,y,z) in enumerate(p)]
_,loops=g.find_islands(f,[0,1]);a=g.rotate_to(loops[0],0);b=g.rotate_to(list(reversed(loops[1])),8)
ca=g.centroid([p[i] for i in a]);cb=g.centroid([p[i] for i in b]);axis=g.unit(g.sub(cb,ca));na=g.polygon_normal(p,a);nb=g.polygon_normal(p,b)
if g.dot(na,axis)<0:na=g.mul(na,-1)
if g.dot(nb,axis)>0:nb=g.mul(nb,-1)
print('loops',a,b,'centers',ca,cb,'normals',na,nb)
def rotate(v,a,b):
 cr=g.cross(a,b);l=g.length(cr)
 return g.rotate_axis(v,g.mul(cr,1/l),atan2(l,g.dot(a,b))) if l>1e-12 else v
for sm in [0,0.5,1,2]:
 cuts=3;cs=[g.cubic_surface_point(ca,cb,na,nb,i/(cuts+1),sm) for i in range(cuts+2)]
 ds=[na]+[g.unit(g.add(g.unit(g.sub(cs[i],cs[i-1])),g.unit(g.sub(cs[i+1],cs[i])))) for i in range(1,cuts+1)]+[g.mul(nb,-1)]
 out=p[:]
 for k in range(1,cuts+1):
  t=k/(cuts+1)
  for i,ia in enumerate(a):
   va=g.sub(p[ia],ca);vb=g.sub(p[b[i]],cb)
   for j in range(len(ds)-1,0,-1):vb=rotate(vb,ds[j],ds[j-1])
   for j in range(1,k+1):va=rotate(va,ds[j-1],ds[j]);vb=rotate(vb,ds[j-1],ds[j])
   out.append(g.add(cs[k],g.mix(va,vb,t)))
 ref,_=blender_reference(p,f,cuts,'PATH',sm,0,'SMOOTH');print('smooth',sm,'error',error(out,ref));print('sample',out[16],ref[16])
