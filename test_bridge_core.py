import math, unittest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "BridgeInteractive"))
from collections import Counter
from bridge_core import bridge,find_islands

def edges(fs):
    c=Counter()
    for f in fs:
        for a,b in zip(f,f[1:]+f[:1]):c[tuple(sorted((a,b)))]+=1
    return c

def rings(n,m):
    pts=[(math.cos(i*2*math.pi/n),math.sin(i*2*math.pi/n),0) for i in range(n)]
    pts += [(math.cos(i*2*math.pi/m),math.sin(i*2*math.pi/m),3) for i in range(m)]
    # C4D faces are triangles/quads, create triangle fans for arbitrary ring sizes.
    pts += [(0,0,0),(0,0,3)]; ca=n+m;cb=ca+1
    faces=[(ca,(i+1)%n,i) for i in range(n)]
    faces += [(cb,n+i,n+(i+1)%m) for i in range(m)]
    return pts,faces
class Test(unittest.TestCase):
    def test_counts_and_manifold(self):
        for n in range(3,9):
            for m in range(3,9):
                pts,fs=rings(n,m)
                for cuts in (0,1,3):
                    pp,ff,new=bridge(pts,fs,range(len(fs)),0,n,cuts=cuts,twist=1,smoothness=.6,profile=.2,angle=.3,interpolation='SURFACE')
                    self.assertEqual(len(pp),len(pts)+n*cuts)
                    self.assertTrue(all(v<=2 for v in edges(ff).values()))
                    expected=set(tuple(sorted((i,(i+1)%n))) for i in range(n)) | set(tuple(sorted((n+i,n+(i+1)%m))) for i in range(m))
                    self.assertEqual({e for e,c in edges(ff).items() if c==1},expected)
                    self.assertTrue(all(len(set(f))==len(f) for f in ff))
    def test_cap_direction(self):
        pts,fs=rings(4,4);_,ff,_=bridge(pts,fs,range(8),0,4)
        directed=[edge for f in ff for edge in zip(f,f[1:]+f[:1])]
        for f in fs:
            for a,b in zip(f,f[1:]+f[:1]):
                if a<8 and b<8:self.assertIn((a,b),directed)
    def test_invalid(self):
        pts,fs=rings(4,4)
        with self.assertRaises(ValueError):bridge(pts,fs,[],0,4)
        with self.assertRaises(ValueError):bridge(pts,fs,range(8),99,4)
        with self.assertRaises(ValueError):bridge(pts,fs,range(8),0,4,cuts=1001)
    def test_parameters_change_interior_only(self):
        pts,fs=rings(4,4);args=(pts,fs,range(8),0,4)
        p0,_,_=bridge(*args,cuts=2);p1,_,_=bridge(*args,cuts=2,profile=.5,angle=1.)
        self.assertEqual(p0[:len(pts)],p1[:len(pts)])
        self.assertNotEqual(p0[len(pts):],p1[len(pts):])
if __name__=='__main__':unittest.main(verbosity=2)
