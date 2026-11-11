import sys,math
sys.path[:0]=['/data/bridge_full_work/BridgeInteractive','/data/bridge_full_work'];import bridge_core as g

def candidate(points,faces,sel,a_anchor,b_anchor,cuts,mode="LINEAR",smoothness=1.,profile=0.):
 patches,loops=g.find_islands(faces,sel);a=g.rotate_to(loops[0],a_anchor);b=g.rotate_to(list(reversed(loops[1])),b_anchor)
 pp,fs,idx=g.bridge(points,faces,sel,a_anchor,b_anchor,cuts=0)
 crosspairs=set();tris=[]
 A=set(a);B=set(b)
 for i in idx:
  face=fs[i]
  if len(face)==3:parts=[face]
  else:
   p,q,r,s=face
   d1=g.length(g.sub(points[p],points[r]));d2=g.length(g.sub(points[q],points[s]))
   parts=[(p,q,r),(p,r,s)] if d1<=d2 else [(p,q,s),(q,r,s)]
  for tri in parts:
   tris.append(tri)
   for x,y in zip(tri,tri[1:]+tri[:1]):
    if (x in A and y in B) or (x in B and y in A):crosspairs.add((x,y) if x in A else (y,x))
 # Minimize dihedral angle by flipping only cross-rim edges.  This is an
 # approximation to Blender beautify_fill; it is not yet integrated into C4D.
 for _ in range(len(tris)*4):
  incidence={}
  for ti,tri in enumerate(tris):
   for j in range(3):
    u,v=tri[j],tri[(j+1)%3];incidence.setdefault(tuple(sorted((u,v))),[]).append((ti,u,v,tri[(j+2)%3]))
  improvements=[]
  for edge,entries in incidence.items():
   if len(entries)!=2:continue
   i,u,v,x=entries[0];j,w,z,y=entries[1]
   if (w,z)!=(v,u) or x==y or not ((x in A and y in B) or (x in B and y in A)):continue
   newedge=tuple(sorted((x,y)))
   if newedge in incidence:continue
   def normal(t):return g.unit(g.cross(g.sub(points[t[1]],points[t[0]]),g.sub(points[t[2]],points[t[0]])))
   n1,n2=normal(tris[i]),normal(tris[j]);m1,m2=normal((x,u,y)),normal((x,y,v))
   if min(g.length(n1),g.length(n2),g.length(m1),g.length(m2))<1e-12:continue
   gain=g.dot(m1,m2)-g.dot(n1,n2)
   if gain>1e-8 or (abs(gain)<=1e-8 and newedge>edge):improvements.append((gain,edge,i,j,x,u,y,v))
  if not improvements:break
  _,_,i,j,x,u,y,v=max(improvements);tris[i]=(x,u,y);tris[j]=(x,y,v)
 crosspairs=set()
 for tri in tris:
  for x,y in zip(tri,tri[1:]+tri[:1]):
   if (x in A and y in B) or (x in B and y in A):crosspairs.add((x,y) if x in A else (y,x))
 ordered=sorted(crosspairs);lookup={};outp=list(points)
 ca,cb,centers,directions,frames=g.path_frames(points,a,b,cuts,smoothness);inv=g.transpose(frames[-1]);axis=g.unit(g.sub(cb,ca))
 ta=g.surface_rim_tangents(points,faces,a,excluded=patches[0],fallback=axis)
 tb=g.surface_rim_tangents(points,faces,b,excluded=patches[1],fallback=g.mul(axis,-1))
 for k in range(1,cuts+1):
  t=k/(cuts+1);x=1-abs(2*t-1);envelope=x*x*(3-2*x)
  for a1,b1 in ordered:
   pa,pb=points[a1],points[b1]
   if mode=='PATH':q=g.path_point(pa,pb,ca,cb,centers[k],frames[k],inv,t);center=centers[k]
   elif mode=='SURFACE':q=g.cubic_surface_point(pa,pb,ta[a1],tb[b1],t,smoothness);center=centers[k]
   else:q=g.mix(pa,pb,t);center=g.mix(ca,cb,t)
   q=g.add(center,g.mul(g.sub(q,center),1+profile*envelope))
   lookup[(a1,b1,k)]=len(outp);outp.append(q)
 def get(a,b,k):return a if k==0 else b if k==cuts+1 else lookup[(a,b,k)]
 out=[f for i,f in enumerate(faces) if i not in patches[0] and i not in patches[1]]
 for tri in tris:
  for j in range(3):
   x,y,z=tri[j:]+tri[:j]
   if (x in A and y in A) or (x in B and y in B):break
  else:raise Exception('invalid')
  if x in A:
   for k in range(cuts+1):
    v1,v2=get(x,z,k),get(y,z,k);w1,w2=get(x,z,k+1),get(y,z,k+1)
    out.append((v1,v2,w2) if w1==w2 else (v1,v2,w2,w1))
  else:
   for k in range(cuts+1):
    v1,v2=get(z,x,cuts+1-k),get(z,y,cuts+1-k);w1,w2=get(z,x,cuts-k),get(z,y,cuts-k)
    out.append((v1,v2,w2) if w1==w2 else (v1,v2,w2,w1))
 return outp,out,ordered,tris
