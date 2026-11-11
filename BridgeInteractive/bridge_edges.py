"""Boundary edge chain discovery, ordering and bridge generation.
This module has no Cinema 4D dependency; integration is not yet complete.
"""
from collections import defaultdict
from math import isfinite, sqrt, sin, cos, pi
try:
    import bridge_interactive_core as g
except ImportError:
    import bridge_core as g

def key(a,b): return (a,b) if a<b else (b,a)
def face_edges(f):return list(zip(f,f[1:]+f[:1]))
def ordered_chains(edges):
    """Split unique undirected edges into non-branching open chains or cycles."""
    adj=defaultdict(set);seen=set()
    for a,b in edges:
        if a==b:raise ValueError('Degenerate edge')
        e=key(a,b)
        if e in seen:continue
        seen.add(e);adj[a].add(b);adj[b].add(a)
    if not seen:raise ValueError('No selected edges')
    if any(len(ns)>2 for ns in adj.values()):raise ValueError('Selected edges branch')
    chains=[];remaining=set(seen)
    while remaining:
        startedge=min(remaining);nodes=set();todo=[startedge[0]]
        while todo:
            x=todo.pop()
            if x in nodes:continue
            nodes.add(x);todo.extend(adj[x]-nodes)
        ends=sorted(x for x in nodes if len(adj[x])==1)
        if len(ends) not in (0,2):raise ValueError('Invalid chain')
        closed=not ends;start=ends[0] if ends else min(nodes);chain=[start];prev=None;cur=start
        while True:
            options=sorted(x for x in adj[cur] if x!=prev and key(cur,x) in remaining)
            if not options:break
            nxt=options[0];remaining.remove(key(cur,nxt));prev,cur=cur,nxt
            if cur==start:break
            chain.append(cur)
        if len(chain)!=len(nodes):raise ValueError('Invalid chain topology')
        if closed and len(chain)<3:raise ValueError('Cycle too small')
        chains.append((chain,closed))
    return chains

def align_chain_to_anchor(chain,closed,anchor):
    if anchor not in chain:raise ValueError('Anchor is outside the chosen chain')
    if closed:
        i=chain.index(anchor);return chain[i:]+chain[:i]
    if anchor==chain[0]:return chain[:]
    if anchor==chain[-1]:return list(reversed(chain))
    raise ValueError('For an open chain, choose an endpoint')

def boundary_orient(chain,closed,incidence,desired):
    """Order vertices so the bridge's corresponding rim opposes existing faces.
    desired=+1 means bridge traversal follows chain, -1 means opposite.
    """
    pairs=list(zip(chain,chain[1:]))+([(chain[-1],chain[0])] if closed else [])
    signs=[]
    for a,b in pairs:
        entries=incidence.get(key(a,b),[])
        if len(entries)!=1:raise ValueError('Each edge must have exactly one adjacent polygon')
        x,y=entries[0];signs.append(1 if (x,y)==(a,b) else -1)
    if len(set(signs))!=1:raise ValueError('Inconsistent polygon winding along boundary')
    # Bridge rim must oppose existing face rim.
    if signs[0] * desired == 1:
        if closed:return [chain[0]]+list(reversed(chain[1:]))
        return list(reversed(chain))
    return chain

def bridge_edges(points,faces,selected_edges,anchor_a,anchor_b,cuts=0,twist=0,smoothness=0.,profile=0.,angle=0.,interpolation="LINEAR",merge=False,merge_factor=.5,profile_shape="SMOOTH"):
    """Bridge exactly two selected boundary chains without altering old faces.
    Returns points, faces and new polygon indices. Open chains need endpoint anchors.
    """
    points=[tuple(float(v) for v in p) for p in points]
    if any(len(p)!=3 or not all(isfinite(v) for v in p) for p in points):raise ValueError('Invalid point')
    fs=[];inc=defaultdict(list)
    for raw in faces:
        f=tuple(raw); f=f[:3] if len(f)==4 and f[2]==f[3] else f
        if len(f) not in (3,4) or len(set(f))!=len(f):raise ValueError('Invalid polygon')
        if any(i<0 or i>=len(points) for i in f):raise ValueError('Invalid polygon point')
        fs.append(f)
        for a,b in face_edges(f):inc[key(a,b)].append((a,b))
    selected_edges=list(selected_edges)
    if any(a<0 or b<0 or a>=len(points) or b>=len(points) for a,b in selected_edges):raise ValueError('Invalid edge point')
    chains=ordered_chains(selected_edges)
    if len(chains)!=2:raise ValueError('Select exactly two edge chains')
    if chains[0][1]!=chains[1][1]:raise ValueError('Both chains must be open or both closed')
    if anchor_a in chains[1][0] and anchor_b in chains[0][0]:chains.reverse()
    (left,closed),(right,_)=chains
    if set(left)&set(right):raise ValueError('Chains must not share vertices')
    left=align_chain_to_anchor(left,closed,anchor_a);right=align_chain_to_anchor(right,closed,anchor_b)
    left=boundary_orient(left,closed,inc,+1);right=boundary_orient(right,closed,inc,-1)
    if not closed:
        if twist:raise ValueError('Twist is only supported for closed loops')
        # The orientation necessary for manifold faces determines endpoint matching.
        # If chosen endpoints are opposite, report rather than silently ignoring input.
        if left[0]!=anchor_a or right[0]!=anchor_b:raise ValueError('Chosen endpoints conflict with polygon winding; choose opposite endpoints')
    else:
        right=right[twist%len(right):]+right[:twist%len(right)]
    if merge:
        if len(left)!=len(right):raise ValueError('Merge requires equally sized chains')
        if not 0.<=merge_factor<=1.:raise ValueError('Invalid merge factor')
        mapping=dict(zip(right,left)); updated=list(points)
        for a,b in zip(left,right):updated[a]=g.mix(points[a],points[b],merge_factor)
        merged=[];affected=[];touched=set(left)|set(right)
        for face in fs:
            f=tuple(mapping.get(i,i) for i in face)
            if len(set(f))!=len(f):raise ValueError('Merge would create a degenerate polygon')
            if any(v in touched for v in face):affected.append(len(merged))
            merged.append(f)
        counts=defaultdict(int)
        for face in merged:
            for a,b in face_edges(face):counts[key(a,b)]+=1
        if any(n>2 for n in counts.values()):raise ValueError('Merge would create non-manifold geometry')
        return updated,merged,affected
    if interpolation not in ('LINEAR','PATH','SURFACE'):raise ValueError('Unknown interpolation')
    if profile_shape not in ('SMOOTH','SPHERE','ROOT','SHARP','LINEAR','CONSTANT','INVERSE_SQUARE'):raise ValueError('Unknown profile shape')
    smoothness=max(0.,min(1000.,float(smoothness)))
    cuts=int(cuts)
    if cuts<0 or cuts>1000:raise ValueError('Cuts must be between 0 and 1000')
    n,m=len(left),len(right);na=n if closed else n-1;nb=m if closed else m-1
    def sample(chain,t):
        size=len(chain) if closed else len(chain)-1;u=min(t*size,size);i=min(int(u),size-1);alpha=u-i
        a=points[chain[i]];b=points[chain[(i+1)%len(chain)]]
        return tuple(x*(1-alpha)+y*alpha for x,y in zip(a,b))
    ca=g.loop_center(points,left);cb=g.loop_center(points,right);axis=g.unit(g.sub(cb,ca));distance=g.length(g.sub(cb,ca))
    if g.length(axis)<1e-12:axis=(0.,0.,1.)
    # Surface tangents are fixed for the preview. Compute them once per rim
    # instead of re-scanning the entire mesh for every point on every cut.
    if interpolation=='SURFACE':
        tangent_left=g.surface_rim_tangents(points,fs,left,closed,fallback=axis)
        tangent_right=g.surface_rim_tangents(points,fs,right,closed,fallback=g.mul(axis,-1))
    if interpolation=='PATH':
        ca,cb,path_centers,path_directions,path_rotations=g.path_frames(points,left,right,cuts,smoothness,closed)
        path_end_inverse=g.transpose(path_rotations[-1])
    elif interpolation=='SURFACE' and profile:
        _,_,profile_centers,_,_=g.path_frames(points,left,right,cuts,smoothness,closed)
    outpoints=list(points);rings=[left]
    for k in range(1,cuts+1):
        t=k/(cuts+1);ring=[];x=1.-abs(2*t-1.)
        envelope={'SMOOTH':x*x*(3-2*x),'SPHERE':sqrt(max(0.,1-(1-x)**2)),
                  'ROOT':sqrt(x),'SHARP':x*x,'LINEAR':x,'CONSTANT':1.,'INVERSE_SQUARE':1-(1-x)**2}[profile_shape]
        for i,v in enumerate(left):
            p=points[v];q=sample(right,i/na);base=g.mix(p,q,t)
            if interpolation=='SURFACE':
                x=(i/na)*nb;bi=min(int(x),nb-1);f=x-bi
                tb=g.unit(g.mix(tangent_right[right[bi]],tangent_right[right[(bi+1)%len(right)]],f))
                base=g.cubic_surface_point(p,q,tangent_left[v],tb,t,smoothness)
            elif interpolation=='PATH':
                base=g.path_point(p,q,ca,cb,path_centers[k],path_rotations[k],path_end_inverse,t)
            center=path_centers[k] if interpolation=='PATH' else (profile_centers[k] if interpolation=='SURFACE' and profile else g.mix(ca,cb,t))
            radial=g.sub(base,center)
            base=g.add(center,g.mul(g.rotate_axis(radial,path_directions[k] if interpolation=='PATH' else axis,angle*envelope),1+profile*envelope))
            ring.append(len(outpoints));outpoints.append(base)
        rings.append(ring)
    rings.append(right);outfaces=list(fs);start=len(outfaces)
    for one,two in zip(rings,rings[1:]):
        x=y=0;nx=len(one) if closed else len(one)-1;ny=len(two) if closed else len(two)-1
        while x<nx or y<ny:
            p=one[x%len(one)];q=two[y%len(two)]
            lhs=(x+1)*ny if x<nx else float('inf');rhs=(y+1)*nx if y<ny else float('inf')
            if lhs==rhs:
                outfaces.append((p,one[(x+1)%len(one)],two[(y+1)%len(two)],q));x+=1;y+=1
            elif lhs<rhs:outfaces.append((p,one[(x+1)%len(one)],q));x+=1
            else:outfaces.append((p,two[(y+1)%len(two)],q));y+=1
    return outpoints,outfaces,list(range(start,len(outfaces)))

def bridge_edge_pairs(points,faces,selected_edges,anchor_a,anchor_b,cuts=0,twist=0,smoothness=0.,profile=0.,angle=0.,interpolation='LINEAR',merge=False,merge_factor=.5,profile_shape='SMOOTH'):
    """Bridge 2N disconnected boundary chains in pairs.
    First pair is specified by clicked anchors. Remaining pairs are chosen by minimum
    endpoint distance; all must be orientable as manifold surfaces. Returns per-pair
    metadata for UV planning. No mutations occur on input collections.
    """
    groups=ordered_chains(selected_edges)
    if len(groups)<2 or len(groups)%2:raise ValueError('Select an even number of at least two chains')
    ia=next((i for i,(ch,_) in enumerate(groups) if anchor_a in ch),None)
    ib=next((i for i,(ch,_) in enumerate(groups) if anchor_b in ch),None)
    if ia is None or ib is None or ia==ib:raise ValueError('Anchors must belong to different chains')
    chosen=[(groups[ia],groups[ib],anchor_a,anchor_b)]
    remaining=[g for i,g in enumerate(groups) if i not in (ia,ib)]
    def dist(a,b):return sum((points[a][k]-points[b][k])**2 for k in range(3))
    while remaining:
        candidate=None
        for i,(one,closed1) in enumerate(remaining):
            for j in range(i+1,len(remaining)):
                two,closed2=remaining[j]
                if closed1!=closed2:continue
                aa=one if closed1 else (one[0],one[-1]);bb=two if closed2 else (two[0],two[-1])
                d,a,b=min((dist(a,b),a,b) for a in aa for b in bb)
                proposal=(d,i,j,a,b)
                if candidate is None or proposal<candidate:candidate=proposal
        if candidate is None:raise ValueError('Each pair must contain two open chains or two closed loops')
        _,i,j,a,b=candidate;left=remaining[i];right=remaining[j]
        chosen.append((left,right,a,b));remaining=[g for k,g in enumerate(remaining) if k not in (i,j)]
    outp=list(points);outf=list(faces);all_indices=[];plans=[]
    edge_set=set(key(a,b) for a,b in selected_edges)
    for (left,lc),(right,rc),a,b in chosen:
        pairnodes=set(left)|set(right)
        pair=[e for e in edge_set if e[0] in pairnodes and e[1] in pairnodes]
        beforefaces=list(outf);pcount=len(outp)
        # Open chains can only be bridged with the winding-compatible endpoints.
        # For automatically chosen pairs, try other endpoint combinations as needed.
        attempts=[(a,b)]
        if not lc and (a,b)!=(anchor_a,anchor_b):
            attempts += [(x,y) for x in (left[0],left[-1]) for y in (right[0],right[-1]) if (x,y)!=(a,b)]
        last_error=None
        for aa,bb in attempts:
            try:
                pp,ff,idx=bridge_edges(outp,outf,pair,aa,bb,cuts,twist,smoothness,profile,angle,interpolation,merge,merge_factor,profile_shape)
                a,b=aa,bb;break
            except ValueError as e:last_error=e
        else:raise last_error
        plans.append({'faces':beforefaces,'face_origins':list(range(len(faces)))+[None]*(len(beforefaces)-len(faces)),'edges':pair,'a':a,'b':b,'point_count':pcount,'new_indices':idx[:]})
        outp,outf=pp,ff;all_indices.extend(idx)
    return outp,outf,sorted(set(all_indices)),plans
