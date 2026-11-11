# -*- coding: utf-8 -*-
"""Experimental, application-independent bridge geometry. Python 3.9+.
Input and output coordinates are object-local triples. Does not manage UVs or tags.
"""
from collections import defaultdict, deque
from math import sqrt, sin, cos, pi, isfinite, atan2

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
def loop_center(points,loop):
    """Edge-length-weighted contour center, including the closing span."""
    if len(loop)<2:return points[loop[0]]
    coords=[points[i] for i in loop]
    distances=[length(sub(coords[(i+1)%len(coords)],coords[i])) for i in range(len(coords))]
    weights=[distances[i-1]+distances[i] for i in range(len(coords))]
    total=sum(weights)
    return tuple(sum(p[j]*w for p,w in zip(coords,weights))/total for j in range(3)) if total>1e-12 else centroid(coords)

def aligned_loop_normal(points,loop,align):
    coords=[points[i] for i in loop];n=(0.,0.,0.)
    for p,q in zip(coords,coords[1:]+coords[:1]):
        d=sub(q,p);n=add(n,cross(d,cross(align,d)))
    return unit(n) if length(n)>1e-12 else (0.,0.,1.)

def face_vertices(f):
    a=tuple(f)
    if len(a)==4 and a[2]==a[3]: a=a[:3]
    if len(a) not in (3,4) or len(set(a))!=len(a): raise ValueError('Degenerate or unsupported polygon')
    return a
def key(a,b): return (a,b) if a<b else (b,a)

def find_islands(faces, selected, allow_many=False):
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
    if len(patches)<2 or (not allow_many and len(patches)!=2): raise ValueError('Select exactly two separate face islands')
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
    seen=set()
    for loop in loops:
        if seen.intersection(loop):raise ValueError('Selections must not share vertices')
        seen.update(loop)
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

def boundary_tangents(points, faces, loop, excluded=(), fallback=(0.,0.,0.)):
    """Average neighbor-to-rim directions in one face pass.

    A face contributes when it has at least two vertices on the same rim.
    This is equivalent to searching all faces separately for each rim vertex,
    but avoids that repeated full-mesh scan during interactive previews.
    """
    rim=set(loop); excluded=set(excluded); totals={v:(0.,0.,0.) for v in rim}; counts={v:0 for v in rim}
    for index,face in enumerate(faces):
        if index in excluded:continue
        on_rim=rim.intersection(face)
        if len(on_rim)<2:continue
        center=centroid([points[v] for v in face])
        for v in on_rim:
            totals[v]=add(totals[v],sub(points[v],center));counts[v]+=1
    return {v:unit(totals[v]) if counts[v] else fallback for v in rim}

def surface_rim_tangents(points, faces, loop, closed=True, excluded=(), fallback=(0.,0.,0.)):
    """Estimate outward tangents from oriented, retained faces at rim edges."""
    rim=set(loop); excluded=set(excluded); totals={v:(0.,0.,0.) for v in rim}
    pairs=list(zip(loop,loop[1:]))+([(loop[-1],loop[0])] if closed else [])
    rim_edges={key(a,b) for a,b in pairs}
    for index,face in enumerate(faces):
        if index in excluded:continue
        eligible=[(a,b) for a,b in zip(face,face[1:]+face[:1]) if key(a,b) in rim_edges]
        if not eligible:continue
        normal=polygon_normal(points,list(face))
        for a,b in eligible:
            tangent=unit(cross(sub(points[b],points[a]),normal))
            totals[a]=add(totals[a],tangent);totals[b]=add(totals[b],tangent)
    return {v:unit(totals[v]) if length(totals[v])>1e-12 else fallback for v in rim}

def cubic_surface_point(a,b,normal_a,normal_b,t,smooth):
    """Cubic surface blend with Blender-style projected Bezier handle length."""
    n1=unit(normal_a);n2=unit(normal_b);dot_norm=max(-1.,min(1.,dot(n1,n2)))
    factor=1.333333 if dot_norm>=0 else 1.333333*(1+dot_norm)+0.75*(-dot_norm)
    axis=cross(n1,n2);delta=sub(b,a)
    if dot(axis,axis)>1.1920929e-7:
        axis=unit(axis);delta=sub(delta,mul(axis,dot(delta,axis)))
    handle=length(delta)*0.5*factor*smooth
    p1=add(a,mul(n1,handle));p2=add(b,mul(n2,handle));s=1-t
    return add(add(mul(a,s*s*s),mul(p1,3*s*s*t)),add(mul(p2,3*s*t*t),mul(b,t*t*t)))

def sample_loop(points,loop,t):
    n=len(loop); x=(t%1.0)*n; i=int(x); f=x-i
    return mix(points[loop[i]],points[loop[(i+1)%n]],f)

def rotate_axis(v, axis, angle):
    return add(add(mul(v,cos(angle)),mul(cross(axis,v),sin(angle))),mul(axis,dot(axis,v)*(1-cos(angle))))

def path_frames(points, a, b, cuts, smoothness, closed=True):
    """Compute center spline and minimum-twist frames for PATH interpolation."""
    ca=loop_center(points,a);cb=loop_center(points,b)
    axis=unit(sub(cb,ca))
    if length(axis)<1e-12:axis=polygon_normal(points,a) if closed else (0.,0.,1.)
    if length(axis)<1e-12:raise ValueError('Cannot determine bridge axis')
    na=polygon_normal(points,a);nb=polygon_normal(points,b)
    if length(na)<1e-12:na=aligned_loop_normal(points,a,axis)
    if length(nb)<1e-12:nb=aligned_loop_normal(points,b,axis)
    if dot(na,axis)<0:na=mul(na,-1)
    if dot(nb,axis)>0:nb=mul(nb,-1)
    centers=[cubic_surface_point(ca,cb,na,nb,i/(cuts+1.),smoothness) for i in range(cuts+2)]
    directions=[na]
    for i in range(1,cuts+1):
        d=unit(add(unit(sub(centers[i],centers[i-1])),unit(sub(centers[i+1],centers[i]))))
        directions.append(d if length(d)>1e-12 else directions[-1])
    directions.append(mul(nb,-1))
    ident=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
    def mm(a,b):return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    frames=[ident]
    for before,after in zip(directions,directions[1:]):
        cr=cross(before,after); size=length(cr); cosine=max(-1.,min(1.,dot(before,after)))
        if size>1e-12:
            rot_axis=mul(cr,1./size);angle=atan2(size,cosine)
        elif cosine<0:
            basis=(1.,0.,0.) if abs(before[0])<.9 else (0.,1.,0.)
            rot_axis=unit(cross(before,basis));angle=pi
        else:frames.append(frames[-1]);continue
        cols=[rotate_axis(v,rot_axis,angle) for v in ident]
        rot=tuple(tuple(cols[j][i] for j in range(3)) for i in range(3))
        frames.append(mm(rot,frames[-1]))
    return ca,cb,centers,directions,frames

def matrix_vec(matrix,vector):return tuple(dot(row,vector) for row in matrix)
def transpose(matrix):return tuple(zip(*matrix))

def path_point(pa,pb,ca,cb,center,frame,end_inverse,t):
    a=matrix_vec(frame,sub(pa,ca))
    b=matrix_vec(frame,matrix_vec(end_inverse,sub(pb,cb)))
    return add(center,mix(a,b,t))

def bridge(points,faces,selected,anchor_a,anchor_b,cuts=0,twist=0,smoothness=0.0,profile=0.0,angle=0.0,interpolation='LINEAR',merge=False,merge_factor=0.5,profile_shape='SMOOTH',reverse_b=True):
    """Return (points, faces, new-face-indices). Does not yet implement complete Blender parity."""
    points=[tuple(float(x) for x in p) for p in points]
    if any(len(p)!=3 or not all(isfinite(x) for x in p) for p in points): raise ValueError('Invalid point')
    faces=[face_vertices(f) for f in faces]
    if any(i<0 or i>=len(points) for f in faces for i in f): raise ValueError('Invalid point index')
    patches,loops=find_islands(faces,selected)
    if anchor_a in loops[1] and anchor_b in loops[0]: patches.reverse();loops.reverse()
    a=rotate_to(loops[0],anchor_a)
    # Reverse B's cap winding so that the bridge has matching orientation at both ends.
    b=rotate_to(list(reversed(loops[1])) if reverse_b else loops[1],anchor_b)
    b=b[twist%len(b):]+b[:twist%len(b)]
    if merge:
        if len(a)!=len(b): raise ValueError('Merge requires equal-sized boundary loops')
        factor=float(merge_factor)
        if not 0.0<=factor<=1.0: raise ValueError('Merge factor must be between 0 and 1')
        mapping=dict(zip(b,a)); newpoints=list(points)
        for ia,ib in zip(a,b): newpoints[ia]=mix(points[ia],points[ib],factor)
        out=[]; touched=[]; touched_vertices=set(a) | set(b)
        for idx,face in enumerate(faces):
            if idx in patches[0] or idx in patches[1]: continue
            replaced=tuple(mapping.get(i,i) for i in face)
            if len(set(replaced))!=len(replaced): raise ValueError('Merge would create a degenerate polygon')
            if any(v in touched_vertices for v in face):touched.append(len(out))
            out.append(replaced)
        used={v for face in out for v in face}
        if any(v not in used for v in a):
            raise ValueError('После Merge останутся несвязанные рёбра, которые полигональный объект Cinema 4D не хранит.')
        edge_counts=defaultdict(int)
        for f in out:
            for x,y in zip(f,f[1:]+f[:1]):edge_counts[key(x,y)]+=1
        if any(v>2 for v in edge_counts.values()):raise ValueError('Merge would produce non-manifold geometry')
        return newpoints,out,touched
    cuts=int(cuts)
    if cuts<0 or cuts>1000: raise ValueError('Cuts must be between 0 and 1000')
    if interpolation not in ('LINEAR','PATH','SURFACE'): raise ValueError('Unknown interpolation')
    if profile_shape not in ('SMOOTH','SPHERE','ROOT','SHARP','LINEAR','CONSTANT','INVERSE_SQUARE'): raise ValueError('Unknown profile shape')
    smoothness=max(0.,min(1000.,float(smoothness))); profile=float(profile); angle=float(angle)
    ca=loop_center(points,a);cb=loop_center(points,b);axis=unit(sub(cb,ca))
    if length(axis)<1e-12: axis=polygon_normal(points,a)
    if length(axis)<1e-12: raise ValueError('Cannot determine bridge axis')
    na=polygon_normal(points,a); nb=polygon_normal(points,list(reversed(b)))
    distance=length(sub(cb,ca))
    # The boundary tangent is estimated from the kept polygons next to each rim.
    # These vectors point away from their neighboring surface toward the gap.
    tangent_a=surface_rim_tangents(points,faces,a,excluded=patches[0],fallback=axis) if interpolation=='SURFACE' else {}
    tangent_b=surface_rim_tangents(points,faces,b,excluded=patches[1],fallback=mul(axis,-1)) if interpolation=='SURFACE' else {}
    if interpolation=='PATH':
        ca,cb,path_centers,path_directions,path_rotations=path_frames(points,a,b,cuts,smoothness)
        path_end_inverse=transpose(path_rotations[-1])
    elif interpolation=='SURFACE' and profile:
        _,_,profile_centers,_,_=path_frames(points,a,b,cuts,smoothness)
    newpts=list(points); rings=[a]; n=len(a); m=len(b)
    for k in range(1,cuts+1):
        t=k/(cuts+1.); ring=[]; x=1.0-abs(2*t-1.0)
        envelope={'SMOOTH':x*x*(3-2*x), 'SPHERE':sqrt(max(0.,1-(1-x)**2)),
                  'ROOT':sqrt(x),'SHARP':x*x,'LINEAR':x,'CONSTANT':1.,
                  'INVERSE_SQUARE':1-(1-x)**2}[profile_shape]
        # Smoothness changes a straight segment into a cubic Hermite path.
        for i,ia in enumerate(a):
            pa=points[ia];pb=sample_loop(points,b,i/n)
            base=mix(pa,pb,t)
            if interpolation=='SURFACE':
                ta=tangent_a[ia]; x=(i/n)*m; bi=int(x)%m; f=x-int(x)
                tb=unit(mix(tangent_b[b[bi]],tangent_b[b[(bi+1)%m]],f))
                base=cubic_surface_point(pa,pb,ta,tb,t,smoothness)
            elif interpolation=='PATH':
                base=path_point(pa,pb,ca,cb,path_centers[k],path_rotations[k],path_end_inverse,t)
            center=path_centers[k] if interpolation=='PATH' else (profile_centers[k] if interpolation=='SURFACE' and profile else mix(ca,cb,t))
            radial=sub(base,center)
            radial=rotate_axis(radial,path_directions[k] if interpolation=='PATH' else axis,angle*envelope)
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

def bridge_face_pairs(points,faces,selected,anchor_a,anchor_b,cuts=0,twist=0,smoothness=0.,profile=0.,angle=0.,interpolation='LINEAR',merge=False,merge_factor=.5,profile_shape='SMOOTH'):
    """Pair any even number of disjoint face islands; first pair uses clicked anchors.
    Subsequent pairs are paired by nearest boundary points. Returns pair plans for UV.
    """
    patches,loops=find_islands(faces,selected,allow_many=True)
    if len(patches)%2:raise ValueError('Select an even number of face islands')
    ia=next((i for i,loop in enumerate(loops) if anchor_a in loop),None)
    ib=next((i for i,loop in enumerate(loops) if anchor_b in loop),None)
    if ia is None or ib is None or ia==ib:raise ValueError('Anchors must be on two different islands')
    pairs=[(ia,ib,anchor_a,anchor_b)];remain=[i for i in range(len(loops)) if i not in (ia,ib)]
    while remain:
        proposal=min((sum((points[a][k]-points[b][k])**2 for k in range(3)),i,j,a,b)
                     for i in remain for j in remain if i<j for a in loops[i] for b in loops[j])
        _,i,j,a,b=proposal;pairs.append((i,j,a,b));remain.remove(i);remain.remove(j)
    outp=list(points);outf=list(faces);origin=list(range(len(faces)));marks=[False]*len(faces);plans=[]
    for i,j,a,b in pairs:
        original=patches[i]|patches[j]
        current=[idx for idx,x in enumerate(origin) if x in original]
        if len(current)!=len(original):raise ValueError('Selected islands overlap or changed during bridging')
        before=list(outf);face_origins=list(origin);pcount=len(outp);removed=set(current)
        pp,ff,changed=bridge(outp,outf,current,a,b,cuts,twist,smoothness,profile,angle,interpolation,merge,merge_factor,profile_shape)
        kept_origin=[x for idx,x in enumerate(origin) if idx not in removed]
        kept_marks=[x for idx,x in enumerate(marks) if idx not in removed]
        if merge:
            for idx in changed:kept_marks[idx]=True
            new_faces=[]
        else:
            new_faces=[ff[idx] for idx in changed]
            kept_origin += [None]*len(new_faces);kept_marks += [True]*len(new_faces)
        plans.append({'faces':before,'face_origins':face_origins,'selected':current,'a':a,'b':b,'point_count':pcount,'new_faces':new_faces})
        outp,outf,origin,marks=pp,ff,kept_origin,kept_marks
    return outp,outf,[i for i,x in enumerate(marks) if x],plans,[x for x in origin if x is not None]

def bridge_face_chain(points,faces,selected,anchor_a,anchor_b,cuts=0,twist=0,smoothness=0.,profile=0.,angle=0.,interpolation='LINEAR',merge=False,merge_factor=.5,profile_shape='SMOOTH',closed=False):
    """Build a single open or closed chain of selected face islands transactionally.

    Safety validation is still required by the caller. In particular, retained
    faces adjacent to an interior rim can make a chain non-manifold.
    """
    patches,loops=find_islands(faces,selected,allow_many=True)
    first=next((i for i,loop in enumerate(loops) if anchor_a in loop),None)
    second=next((i for i,loop in enumerate(loops) if anchor_b in loop),None)
    if first is None or second is None or first==second:raise ValueError('Выберите вершины двух разных групп.')
    order=[first,second];remaining=set(range(len(loops)))-set(order)
    while remaining:
        previous=loops[order[-1]]
        def distance(idx):return min((dot(sub(points[a],points[b]),sub(points[a],points[b])),idx) for a in previous for b in loops[idx])
        nxt=min(remaining,key=distance);order.append(nxt);remaining.remove(nxt)
    pairs=list(zip(order,order[1:]))
    if merge:
        return merge_face_chain(points,faces,selected,patches,loops,pairs,anchor_a,anchor_b,twist,merge_factor)
    if closed and len(order)>2:pairs.append((order[-1],order[0]))
    outpoints=list(points);retained=[i for i in range(len(faces)) if i not in set(selected)]
    outputfaces=[face_vertices(faces[i]) for i in retained];generated=[];plans=[];existing_directed={}
    for pair_index,(x,y) in enumerate(pairs):
        la,lb=loops[x],loops[y]
        if pair_index==0:a,b=anchor_a,anchor_b
        else:
            _,a,b=min((dot(sub(points[a],points[b]),sub(points[a],points[b])),a,b) for a in la for b in lb)
        selected_pair=sorted(patches[x]|patches[y]);point_count=len(outpoints)
        # For a closed chain, the final span sometimes needs the other B-rim
        # traversal to produce consistent orientations at both shared rims.
        choices=(True,False) if closed and pair_index==len(pairs)-1 else (True,)
        compatible=False
        for reverse_b in choices:
            pp,ff,idx=bridge(points,faces,selected_pair,a,b,cuts,twist,smoothness,profile,angle,interpolation,False,merge_factor,profile_shape,reverse_b)
            def mapped(v):return v if v<len(points) else point_count+(v-len(points))
            newfaces=[tuple(mapped(v) for v in ff[i]) for i in idx]
            orientation=None;compatible=True
            for face in newfaces:
                for u,v in zip(face,face[1:]+face[:1]):
                    k=key(u,v)
                    if k in existing_directed:
                        same=(u,v)==existing_directed[k]
                        if orientation is not None and orientation!=same:compatible=False;break
                        orientation=same
                if not compatible:break
            if compatible:break
        if not compatible:raise ValueError('Несовместимое направление контуров последовательности.')
        if orientation:newfaces=[tuple(reversed(f)) for f in newfaces]
        for face in newfaces:
            for u,v in zip(face,face[1:]+face[:1]):existing_directed.setdefault(key(u,v),(u,v))
        outpoints.extend(pp[len(points):]);generated.extend(newfaces)
        plans.append({'faces':list(faces),'face_origins':list(range(len(faces))),'selected':selected_pair,
                      'a':a,'b':b,'point_count':point_count,'new_faces':newfaces,'reverse_b':reverse_b})
    outputfaces.extend(generated);new=list(range(len(retained),len(outputfaces)))
    return outpoints,outputfaces,new,plans,retained


def merge_face_chain(points,faces,selected,patches,loops,pairs,anchor_a,anchor_b,twist,merge_factor):
    """Weld a sequence of equal-sized face boundaries in pair order.

    Every pair is merged into its left-hand representative. Applying pairs in
    sequence matters for non-central merge factors and vertex-map interpolation.
    """
    factor=float(merge_factor)
    if not 0.<=factor<=1.:raise ValueError('Merge factor must be between 0 and 1')
    if len({len(loop) for loop in loops})!=1:raise ValueError('Для Merge все контуры должны иметь одинаковое число вершин.')
    outpoints=[tuple(p) for p in points];parents=list(range(len(points)));plans=[]
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for index,(x,y) in enumerate(pairs):
        la,lb=loops[x],loops[y]
        if index==0:a,b=anchor_a,anchor_b
        else:
            _,a,b=min((dot(sub(outpoints[root(a)],outpoints[root(b)]),sub(outpoints[root(a)],outpoints[root(b)])),a,b)
                      for a in la for b in lb)
        reverse_b=(index%2==0)
        left=rotate_to(la,a);right=rotate_to(list(reversed(lb)) if reverse_b else lb,b)
        right=right[twist%len(right):]+right[:twist%len(right)]
        mapped=[]
        for va,vb in zip(left,right):
            ra,rb=root(va),root(vb)
            if ra==rb:raise ValueError('Контуры слияния уже соединены друг с другом.')
            mapped.append((ra,rb));outpoints[ra]=mix(outpoints[ra],outpoints[rb],factor);parents[rb]=ra
        plans.append({'faces':list(faces),'face_origins':list(range(len(faces))),
            'selected':sorted(patches[x]|patches[y]),'a':a,'b':b,'point_count':len(points),
            'new_faces':[],'reverse_b':reverse_b,'merge_vertex_pairs':mapped})
    retained=[i for i in range(len(faces)) if i not in set(selected)];outfaces=[];affected=[]
    touched={v for loop in loops for v in loop}
    for old in retained:
        face=face_vertices(faces[old]);mapped=tuple(root(v) for v in face)
        if len(set(mapped))!=len(mapped):raise ValueError('Слияние создаёт вырожденный полигон.')
        if any(v in touched for v in face):affected.append(len(outfaces))
        outfaces.append(mapped)
    used={v for face in outfaces for v in face}
    if any(root(v) not in used for loop in loops for v in loop):
        raise ValueError('После Merge останутся несвязанные рёбра, которые полигональный объект Cinema 4D не хранит.')
    return outpoints,outfaces,affected,plans,retained
