"""Plan vertex-map values for bridge/merge; independent of Cinema 4D.
For plain vertex maps only. Field-driven tags need separate validation.
"""
try:
 import bridge_interactive_core as core
 import bridge_interactive_edges as edges
except ImportError:
 import bridge_core as core
 import bridge_edges as edges

def source_chains(faces,selection,a,b,twist,edge_mode,reverse_b=True):
 if edge_mode:
  pairs=edges.ordered_chains(selection)
  if len(pairs)!=2 or pairs[0][1]!=pairs[1][1]:raise ValueError('Invalid chains')
  if a in pairs[1][0] and b in pairs[0][0]:pairs.reverse()
  (left,closed),(right,_)=pairs
  left=edges.align_chain_to_anchor(left,closed,a);right=edges.align_chain_to_anchor(right,closed,b)
  incidence={}
  for face in faces:
   f=core.face_vertices(face)
   for x,y in edges.face_edges(f):incidence.setdefault(edges.key(x,y),[]).append((x,y))
  left=edges.boundary_orient(left,closed,incidence,+1);right=edges.boundary_orient(right,closed,incidence,-1)
  if closed:right=right[twist%len(right):]+right[:twist%len(right)]
  return left,right,closed
 patches,loops=core.find_islands(faces,selection)
 if a in loops[1] and b in loops[0]:loops.reverse()
 left=core.rotate_to(loops[0],a);right=core.rotate_to(list(reversed(loops[1])) if reverse_b else loops[1],b)
 right=right[twist%len(right):]+right[:twist%len(right)]
 return left,right,True

def apply_pair_weights(weights,faces,selection,a,b,twist,cuts,edge_mode=False,merge=False,merge_factor=.5,reverse_b=True):
 """Return weights with appended new ring values / interpolated merged values."""
 out=list(weights);left,right,closed=source_chains(faces,selection,a,b,twist,edge_mode,reverse_b)
 if merge:
  if len(left)!=len(right):raise ValueError('Merge requires equal-sized boundaries')
  original=list(out)
  for x,y in zip(left,right):out[x]=original[x]*(1-merge_factor)+original[y]*merge_factor
  return out
 n=len(left);m=len(right);na=n if closed else n-1;nb=m if closed else m-1
 for k in range(1,cuts+1):
  t=k/(cuts+1)
  for i,v in enumerate(left):
   x=(i/na)*nb;j=min(int(x),nb-1);frac=x-j
   u=out[right[j]]*(1-frac)+out[right[(j+1)%m]]*frac
   out.append(out[v]*(1-t)+u*t)
 return out
