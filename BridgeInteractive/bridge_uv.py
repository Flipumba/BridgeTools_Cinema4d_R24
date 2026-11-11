"""Pure-geometry UV planning; no Cinema 4D access. NOT validated in Cinema 4D.
Retained faces keep their individual corners and seam/pins. New bridge faces use
an independent rectangular UV island; continuity with old UVs is not implied.
"""
try:
    from bridge_interactive_core import find_islands,rotate_to
except ImportError:
    from bridge_core import find_islands,rotate_to

def create_uv_plan_with_point_count(faces,selected,anchor_a,anchor_b,twist,cuts,new_faces,point_count,merge=False,reverse_b=True):
    patches,loops=find_islands(faces,selected)
    if anchor_a in loops[1] and anchor_b in loops[0]:patches.reverse();loops.reverse()
    a=rotate_to(loops[0],anchor_a)
    b=rotate_to(list(reversed(loops[1])) if reverse_b else loops[1],anchor_b);b=b[twist%len(b):]+b[:twist%len(b)]
    retained=[i for i in range(len(faces)) if i not in patches[0] and i not in patches[1]]
    if merge:return retained,[]
    n,m=len(a),len(b); uv={}
    for i,v in enumerate(a):uv[v]=(i/n,0.0,0.0)
    for i,v in enumerate(b):uv[v]=(i/m,1.0,0.0)
    for k in range(1,cuts+1):
        for i in range(n):uv[point_count+(k-1)*n+i]=(i/n,k/(cuts+1),0.0)
    coords=[]
    for face in new_faces:
        raw=[uv[v] for v in face];us=[p[0] for p in raw]
        # Unwrap each polygon across the cyclic seam; never adjust the original retained UVs.
        if max(us)-min(us)>.5:raw=[(u+1.0 if u<.5 else u,v,w) for u,v,w in raw]
        if len(raw)==3:raw.append(raw[-1])
        coords.append(tuple(raw))
    return retained,coords

def remap_uv_pins(old_pin_indices,retained):
    """UV pin index format: four corners per source polygon."""
    out=set(); source_to_target={source:i for i,source in enumerate(retained)}
    for idx in old_pin_indices:
        face,corner=divmod(idx,4)
        if face in source_to_target:out.add(4*source_to_target[face]+corner)
    return out

def create_edge_uv_plan(faces,selected_edges,anchor_a,anchor_b,twist,cuts,new_faces,point_count,merge=False):
    try:import bridge_interactive_edges as edges
    except ImportError:import bridge_edges as edges
    if merge:return list(range(len(faces))),[]
    chains=edges.ordered_chains(selected_edges)
    if len(chains)!=2 or chains[0][1]!=chains[1][1]:raise ValueError('Invalid chains')
    if anchor_a in chains[1][0] and anchor_b in chains[0][0]:chains.reverse()
    (a,closed),(b,_)=chains
    a=edges.align_chain_to_anchor(a,closed,anchor_a);b=edges.align_chain_to_anchor(b,closed,anchor_b)
    inc={}
    for face in faces:
        face=tuple(face);face=face[:3] if len(face)==4 and face[2]==face[3] else face
        for x,y in edges.face_edges(face):inc.setdefault(edges.key(x,y),[]).append((x,y))
    a=edges.boundary_orient(a,closed,inc,+1);b=edges.boundary_orient(b,closed,inc,-1)
    if closed:b=b[twist%len(b):]+b[:twist%len(b)]
    n,m=len(a),len(b);na=n if closed else n-1;nb=m if closed else m-1
    uv={}
    for i,v in enumerate(a):uv[v]=(i/na,0.,0.)
    for i,v in enumerate(b):uv[v]=(i/nb,1.,0.)
    for k in range(1,cuts+1):
        for i in range(n):uv[point_count+(k-1)*n+i]=(i/na,k/(cuts+1),0.)
    result=[]
    for face in new_faces:
        row=[uv[v] for v in face]; us=[p[0] for p in row]
        if closed and max(us)-min(us)>.5:row=[(u+1 if u<.5 else u,v,w) for u,v,w in row]
        if len(row)==3:row.append(row[-1])
        result.append(tuple(row))
    return list(range(len(faces))),result

def interpolate_boundary_uv(faces, old_uv, selection, anchor_a, anchor_b, twist,
                            edge_mode, rectangular_uv,reverse_b=True):
    """Interpolate UV corners from the polygons adjoining each source boundary.

    The input UVs contain four triples per source polygon. A seam can give one
    vertex multiple UV coordinates: choosing the adjacent edge separately for
    each generated polygon preserves those discontinuities. When a boundary
    edge has no single retained polygon, callers may retain rectangular UVs.
    """
    try:
        import bridge_interactive_weights as weights
        import bridge_interactive_core as core
    except ImportError:
        import bridge_weights as weights
        import bridge_core as core
    left,right,closed=weights.source_chains(faces,selection,anchor_a,anchor_b,twist,edge_mode,reverse_b)
    excluded=set() if edge_mode else set(selection)
    lookup={}
    for fi,raw in enumerate(faces):
        if fi in excluded:continue
        face=core.face_vertices(raw)
        corners=old_uv[fi]
        for j,(a,b) in enumerate(zip(face,face[1:]+face[:1])):
            entry=(a,b,corners[j],corners[(j+1)%len(face)])
            lookup.setdefault(core.key(a,b),[]).append(entry)
    def boundary(chain):
        pairs=list(zip(chain,chain[1:]))+([(chain[-1],chain[0])] if closed else [])
        result=[]
        for a,b in pairs:
            entries=lookup.get(core.key(a,b),[])
            if len(entries)!=1:raise ValueError('UV boundary has no single adjacent retained polygon')
            x,y,ux,uy=entries[0]
            result.append((ux,uy) if (x,y)==(a,b) else (uy,ux))
        return result
    bounds=(boundary(left),boundary(right))
    def sample(items,u,mid):
        count=len(items)
        # At a vertex choose the edge lying inside the face's U interval.
        v=u*count;nearest=round(v)
        if abs(v-nearest)<1e-8:
            idx=int(nearest)-1 if mid<u else int(nearest)
        else:idx=int(v//1)
        if closed:
            t=v-idx;idx%=count
        else:
            idx=max(0,min(count-1,idx));t=max(0.,min(1.,v-idx))
        aa,bb=items[idx]
        return tuple(x*(1-t)+y*t for x,y in zip(aa,bb))
    out=[]
    for face in rectangular_uv:
        midpoint=sum(x[0] for x in face)/len(face)
        row=[]
        for u,v,_ in face:
            a=sample(bounds[0],u,midpoint);b=sample(bounds[1],u,midpoint)
            row.append(tuple(x*(1-v)+y*v for x,y in zip(a,b)))
        out.append(tuple(row))
    return out
