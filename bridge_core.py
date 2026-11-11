# -*- coding: utf-8 -*-
"""Experimental, application-independent bridge geometry. Python 3.9+.
Input and output coordinates are object-local triples. Does not manage UVs or tags.
"""
from collections import defaultdict, deque
from math import sqrt, sin, cos, pi, isfinite

def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,s): return tuple(x*s for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def length(a): return sqrt(dot(a,a))
def unit(a):
    n=length(a)
    return mul(a,1.0/n) if n>1e-12 else (0.,0.,0.)
def mix(a,b,t): return add(mul(a,1-t),mul(b,t))
def centroid(points): return mul(tuple(map(sum,zip(*points))),1.0/len(points))
def face_vertices(f):
    a=tuple(f)
    if len(a)==4 and a[2]==a[3]: a=a[:3]
    if len(a) not in (3,4) or len(set(a))!=len(a): raise ValueError('Degenerate or unsupported polygon')
    return a
def key(a,b): return (a,b) if a<b else (b,a)

def find_islands(faces, selected):
    """Two face-connected selected patches, each with exactly one simple boundary."""
    selected=set(selected)
    if not selected or any(i<0 or i>=len(faces) for i in selected): raise ValueError('Invalid or empty face selection')
    incidence=defaultdict(list); fs=[face_vertices(f) for f in faces]
    for i,f in enumerate(fs):
        for a,b in zip(f, f[1:]+f[:1]): incidence[key(a,b)].append(i)
    if any(len(v)>2 for v in incidence.values()): raise ValueError('Non-manifold mesh edge')
    adjacency=defaultdict(set)
    for ids in incidence.values():
        if len(ids)==2 and ids[0] in selected and ids[1] in selected:
            a,b=ids; adjacency[a].add(b); adjacency[b].add(a)
    patches=[]; remain=set(selected)
    while remain:
        todo=[min(remain)]; remain.remove(todo[0]); patch=set()
        while todo:
            i=todo.pop(); patch.add(i)
            for j in adjacency[i] & remain: remain.remove(j);todo.append(j)
        patches.append(patch)
    if len(patches)!=2: raise ValueError('Select exactly two separate face islands')
    loops=[]
    for patch in patches:
        ordered=[]
        for i in sorted(patch):
            f=fs[i]
            for a,b in zip(f, f[1:]+f[:1]):
                if sum(j in patch for j in incidence[key(a,b)])==1: ordered.append((a,b))
        outgoing=defaultdict(list); incoming=defaultdict(list)
        for a,b in ordered: outgoing[a].append(b);incoming[b].append(a)
        vertices=set(outgoing)|set(incoming)
        if not vertices or any(len(outgoing[v])!=1 or len(incoming[v])!=1 for v in vertices):
            raise ValueError('Selection boundary is open, branched, or has inconsistent face winding')
        start=min(vertices); loop=[start]; cur=outgoing[start][0]
        while cur!=start:
            if cur in loop: raise ValueError('Invalid boundary cycle')
            loop.append(cur); cur=outgoing[cur][0]
        if len(loop)!=len(vertices) or len(loop)<3: raise ValueError('Each selection must have exactly one closed boundary')
        # An edge may have at most one retained neighbour; its retained winding must oppose the cap.
        for a,b in zip(loop,loop[1:]+loop[:1]):
            for j in incidence[key(a,b)]:
                if j not in patch:
                    f=fs[j]
                    if (a,b) in list(zip(f,f[1:]+f[:1])): raise ValueError('Inconsistent winding across selected boundary')
        loops.append(loop)
    if set(loops[0]) & set(loops[1]): raise ValueError('Selections must not share vertices')
    return patches,loops

def rotate_to(loop,anchor):
    try: i=loop.index(anchor)
    except ValueError: raise ValueError('Anchor is not on selection boundary')
    return loop[i:]+loop[:i]

def polygon_normal(points, loop):
    # Newell's method, stable for concave faces and many-sided contours.
    n=[0.,0.,0.]
    for a,b in zip(loop,loop[1:]+loop[:1]):
        x,y,z=points[a]; X,Y,Z=points[b]
        n[0]+=(y-Y)*(z+Z);n[1]+=(z-Z)*(x+X);n[2]+=(x-X)*(y+Y)
    return unit(tuple(n))

def sample_loop(points,loop,t):
    n=len(loop); x=(t%1.0)*n; i=int(x); f=x-i
    return mix(points[loop[i]],points[loop[(i+1)%n]],f)

def rotate_axis(v, axis, angle):
    return add(add(mul(v,cos(angle)),mul(cross(axis,v),sin(angle))),mul(axis,dot(axis,v)*(1-cos(angle))))

def bridge(points,faces,selected,anchor_a,anchor_b,cuts=0,twist=0,smoothness=0.0,profile=0.0,angle=0.0,interpolation='LINEAR'):
    """Return (points, faces, new-face-indices). Does not implement merge or Blender parity."""
    points=[tuple(float(x) for x in p) for p in points]
    if any(len(p)!=3 or not all(isfinite(x) for x in p) for p in points): raise ValueError('Invalid point')
    faces=[face_vertices(f) for f in faces]
    if any(i<0 or i>=len(points) for f in faces for i in f): raise ValueError('Invalid point index')
    patches,loops=find_islands(faces,selected)
    if anchor_a in loops[1] and anchor_b in loops[0]: patches.reverse();loops.reverse()
    a=rotate_to(loops[0],anchor_a)
    # Reverse B's cap winding so that the bridge has matching orientation at both ends.
    b=rotate_to(list(reversed(loops[1])),anchor_b)
    b=b[twist%len(b):]+b[:twist%len(b)]
    cuts=int(cuts)
    if cuts<0 or cuts>128: raise ValueError('Cuts must be between 0 and 128')
    if interpolation not in ('LINEAR','PATH','SURFACE'): raise ValueError('Unknown interpolation')
    smoothness=max(0.,min(1.,float(smoothness))); profile=float(profile); angle=float(angle)
    ca=centroid([points[i] for i in a]);cb=centroid([points[i] for i in b]);axis=unit(sub(cb,ca))
    if length(axis)<1e-12: axis=polygon_normal(points,a)
    if length(axis)<1e-12: raise ValueError('Cannot determine bridge axis')
    na=polygon_normal(points,a); nb=polygon_normal(points,list(reversed(b)))
    distance=length(sub(cb,ca))
    newpts=list(points); rings=[a]; n=len(a); m=len(b)
    for k in range(1,cuts+1):
        t=k/(cuts+1.); ring=[]; envelope=sin(pi*t)
        # Smoothness changes a straight segment into a cubic Hermite path.
        for i,ia in enumerate(a):
            pa=points[ia];pb=sample_loop(points,b,i/n)
            base=mix(pa,pb,t)
            if interpolation!='LINEAR' and smoothness:
                if interpolation=='PATH':
                    tangent_a=mul(axis,distance); tangent_b=tangent_a
                else:
                    tangent_a=mul(na,-distance); tangent_b=mul(nb,distance)
                h00=2*t**3-3*t*t+1;h10=t**3-2*t*t+t;h01=-2*t**3+3*t*t;h11=t**3-t*t
                curved=add(add(mul(pa,h00),mul(tangent_a,h10)),add(mul(pb,h01),mul(tangent_b,h11)))
                base=mix(base,curved,smoothness)
            center=mix(ca,cb,t); radial=sub(base,center)
            radial=rotate_axis(radial,axis,angle*envelope)
            base=add(center,mul(radial,1+profile*envelope))
            ring.append(len(newpts));newpts.append(base)
        rings.append(ring)
    rings.append(b)
    out=[f for i,f in enumerate(faces) if i not in patches[0] and i not in patches[1]]; first=len(out)
    for r,s in zip(rings,rings[1:]):
        i=j=0; nr=len(r);ns=len(s)
        # Zipper triangulates unequal loops without splitting existing boundary edges.
        while i<nr or j<ns:
            ai=r[i%nr]; bj=s[j%ns]
            lhs=(i+1)*ns if i<nr else float('inf')
            rhs=(j+1)*nr if j<ns else float('inf')
            if lhs==rhs:
                out.append((ai,r[(i+1)%nr],s[(j+1)%ns],bj));i+=1;j+=1
            elif lhs<rhs:
                out.append((ai,r[(i+1)%nr],bj));i+=1
            else:
                out.append((ai,s[(j+1)%ns],bj));j+=1
    return newpts,out,list(range(first,len(out)))
