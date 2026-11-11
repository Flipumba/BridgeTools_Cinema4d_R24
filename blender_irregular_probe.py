import sys,math
sys.path[:0]=['/data/bridge_full_work/BridgeInteractive','/data/bridge_full_work']
from blender_compare_geometry import blender_reference,error
from bridge_core import bridge
from test_merge import shape
p0,f=shape();cases=0;failures=[]
for variant in ['irregular']:
 p=[]
 for i,(x,y,z) in enumerate(p0):
  if i in (1,5,9,13): x+=0.7
  if i in (2,6,10,14): y+=0.4
  if i>=8:
   if variant=='tilt':x,y,z=x, y*math.cos(.45)-z*math.sin(.45)+.87, y*math.sin(.45)+z*math.cos(.45)+.22
   if variant=='stretch':x,y=x*1.3,y*.7
   x+=.6;y+=.3
  p.append((x,y,z))
 for mode in ('LINEAR','PATH','SURFACE'):
  for sm in (0.,.5,1.,2.):
   for profile in (0.,.5):
    for sh in (('SMOOTH','SPHERE','ROOT','INVERSE_SQUARE','SHARP','LINEAR') if profile else ('SMOOTH',)):
     ref,count=blender_reference(p,f,3,mode,sm,profile,sh)
     candidate,ff,_=bridge(p,f,[0,1],0,8,cuts=3,smoothness=sm,profile=profile,interpolation=mode,profile_shape=sh)
     err=error(candidate,ref)
     cases+=1
     if err>1e-4 or len(ff)!=count:failures.append((variant,mode,sm,profile,sh,err,len(ff),count))
print('CASES',cases,'FAILURES',len(failures))
for case in failures:print('FAIL',case)
if failures:raise SystemExit(1)
