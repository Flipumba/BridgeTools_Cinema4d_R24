"""Validation of affected bridge polygons, independent of Cinema 4D."""
from collections import defaultdict
from math import isfinite
try:
    from bridge_interactive_core import face_vertices,key,sub,cross,dot
except ImportError:
    from bridge_core import face_vertices,key,sub,cross,dot

def canonical(face):
    """Ignore starting corner and orientation when detecting identical polygons."""
    f=tuple(face);r=tuple(reversed(f))
    return min(*(f[i:]+f[:i] for i in range(len(f))),*(r[i:]+r[:i] for i in range(len(r))))

def edges_cross(a,b,c,d,scale):
    """Detect a proper 3D intersection of two non-adjacent segments."""
    u=sub(b,a);v=sub(d,c);w=sub(a,c)
    uu=dot(u,u);uv=dot(u,v);vv=dot(v,v);uw=dot(u,w);vw=dot(v,w)
    den=uu*vv-uv*uv
    if den<=uu*vv*1e-20:return False
    s=(uv*vw-vv*uw)/den;t=(uu*vw-uv*uw)/den
    if not (1e-10<s<1-1e-10 and 1e-10<t<1-1e-10):return False
    diff=tuple(w[k]+s*u[k]-t*v[k] for k in range(3))
    return dot(diff,diff)<=scale*1e-20

def validate_result(points,faces,affected):
    """Reject unsafe results involving newly created or merge-modified polygons.

    Unrelated pre-existing defects are not rejected. This validates local topology
    and zero-area faces, not global mesh self-intersection or Blender parity.
    """
    affected=set(affected)
    if any(not isinstance(i,int) or i<0 or i>=len(faces) for i in affected):
        raise ValueError('Некорректные индексы полигонов моста.')
    incidence=defaultdict(list);polygons=defaultdict(list)
    for index,raw in enumerate(faces):
        f=face_vertices(raw)
        if any(not isinstance(v,int) or v<0 or v>=len(points) for v in f):
            raise ValueError('Некорректный индекс вершины полигона.')
        polygons[canonical(f)].append(index)
        for a,b in zip(f,f[1:]+f[:1]):incidence[key(a,b)].append((index,a,b))
        if index not in affected:continue
        vertices=[points[v] for v in f]
        if any(len(p)!=3 or not all(isfinite(x) for x in p) for p in vertices):
            raise ValueError('Некорректные координаты полигона моста.')
        edges=[sub(q,p) for p,q in zip(vertices,vertices[1:]+vertices[:1])]
        lengths=[dot(e,e) for e in edges];scale=max(lengths)
        if scale==0 or min(lengths)<=scale*1e-20:
            raise ValueError('Мост создаёт ребро нулевой длины. Измените соответствие вершин или настройки.')
        # Nonzero cross product in at least one triangle of either diagonal.
        origin=vertices[0]
        area=max(dot(cross(sub(vertices[i],origin),sub(vertices[j],origin)),
                     cross(sub(vertices[i],origin),sub(vertices[j],origin)))
                 for i in range(1,len(vertices)) for j in range(i+1,len(vertices)))
        if area<=scale*scale*1e-24:
            raise ValueError('Мост создаёт полигон нулевой площади. Измените соответствие или настройки.')
        if len(vertices)==4 and (edges_cross(*vertices,scale) or
                                 edges_cross(vertices[1],vertices[2],vertices[3],vertices[0],scale)):
            raise ValueError('Мост создаёт самопересекающийся полигон. Измените соответствие вершин.')
    for ids in polygons.values():
        if len(ids)>1 and affected.intersection(ids):
            raise ValueError('Мост создаёт дублирующийся полигон.')
    for entries in incidence.values():
        if not any(i in affected for i,_,_ in entries):continue
        if len(entries)>2:raise ValueError('Мост создаёт неманифолдное ребро.')
        if len(entries)==2 and entries[0][1:]==entries[1][1:]:
            raise ValueError('Несогласованное направление полигонов у моста.')
