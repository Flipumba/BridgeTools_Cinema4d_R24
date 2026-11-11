"""Compute selection remapping plans for retained polygon geometry."""
def corners(f):
    f=tuple(f)
    return f[:3] if len(f)==4 and f[2]==f[3] else f

def vertex_remap(oldfaces,newfaces,retained,point_count):
    """Build old->new point map from surviving unchanged-order polygons."""
    mapping={i:i for i in range(point_count)}; found={}
    for new_idx,old_idx in enumerate(retained):
        before=corners(oldfaces[old_idx]);after=corners(newfaces[new_idx])
        if len(before)!=len(after):raise ValueError('Retained polygon changed corner count')
        for a,b in zip(before,after):
            if a in found and found[a]!=b:raise ValueError('Conflicting point mapping')
            found[a]=b
    mapping.update(found);return mapping

def remap_points(selected,mapping):return {mapping[i] for i in selected if i in mapping}
def remap_polygons(selected,retained):return {j for j,i in enumerate(retained) if i in selected}
def raw_edges(face):
    a=tuple(face)
    if len(a)==3:a=a+(a[-1],)
    return list(zip(a,a[1:]+a[:1]))
def remap_edges(selected_raw,oldfaces,newfaces,mapping):
    chosen=set()
    for i in selected_raw:
        face,slot=divmod(i,4)
        if face<0 or face>=len(oldfaces):continue
        a,b=raw_edges(oldfaces[face])[slot]
        if a==b:continue
        if a not in mapping or b not in mapping:continue
        a=mapping[a];b=mapping[b]
        if a!=b:chosen.add(tuple(sorted((a,b))))
    out=set()
    for i,face in enumerate(newfaces):
        for j,(a,b) in enumerate(raw_edges(face)):
            if a!=b and tuple(sorted((a,b))) in chosen:out.add(4*i+j)
    return out

def compact_newly_orphaned_points(oldfaces,newfaces,newpoints,old_point_count):
    """Remove points made unused by the operation, preserving pre-existing loose points.
    Returns compact points, reindexed faces and a pre->post mapping.
    """
    before={v for face in oldfaces for v in corners(face)}
    after={v for face in newfaces for v in corners(face)}
    keep=[i for i in range(len(newpoints)) if i in after or (i<old_point_count and i not in before)]
    remap={old:new for new,old in enumerate(keep)}
    return [newpoints[i] for i in keep],[tuple(remap[v] for v in corners(face)) for face in newfaces],remap
