"""Tests plugin control flow with mocked API, not actual Cinema 4D."""
import sys,types,runpy,os
c=types.ModuleType('c4d')
class Vec:
 def __init__(self,x=0,y=0,z=0):self.x=x;self.y=y;self.z=z
class Matrix:
 def __mul__(self,v):return v
class Polygon:
 def __init__(self,a,b,c,d=None):self.a=a;self.b=b;self.c=c;self.d=c if d is None else d
class Sel:
 def __init__(self,v=()):self.s=set(v)
 def IsSelected(self,i):return i in self.s
 def DeselectAll(self):self.s.clear()
 def Select(self,i):self.s.add(i)
 def GetCount(self):return len(self.s)
class Obj:
 def __init__(self):
  self.pts=[Vec(0,0,0),Vec(10,0,0),Vec(10,10,0),Vec(0,10,0),Vec(100,0,3),Vec(110,0,3),Vec(110,10,3),Vec(100,10,3)]
  self.fs=[Polygon(0,3,2,1),Polygon(4,5,6,7)];self.ps=Sel((0,1));self.vs=Sel();self.es=Sel()
 def GetAllPoints(self):return self.pts[:]
 def GetAllPolygons(self):return self.fs[:]
 def GetPolygonS(self):return self.ps
 def GetPointS(self):return self.vs
 def GetEdgeS(self):return self.es
 def GetEdgeH(self):return Sel()
 def GetPolygonH(self):return Sel()
 def GetPointH(self):return Sel()
 def GetPhongBreak(self):return Sel()
 def GetNgonCount(self):return 0
 def GetTags(self):return []
 def CheckType(self,t):return True
 def IsAlive(self):return True
 def GetMg(self):return Matrix()
 def ResizeObject(self,p,v):
  self.pts=self.pts[:p]+[Vec()] * max(0,p-len(self.pts));self.fs=self.fs[:v]+[Polygon(0,0,0)]*max(0,v-len(self.fs));return True
 def SetAllPoints(self,p):self.pts=p
 def SetPolygon(self,i,p):self.fs[i]=p
 def Message(self,*args):pass
class Doc:
 def __init__(self):self.obj=Obj();self.undo=0
 def GetActiveObject(self):return self.obj
 def StartUndo(self):return True
 def AddUndo(self,*args):self.undo+=1;return True
 def EndUndo(self):pass
 def DoUndo(self):raise AssertionError('Unexpected undo')
class BD:
 def __init__(self):self.lines=[]
 def WS(self,p):return p
 def SetMatrix_Matrix(self,*a):pass
 def SetPen(self,*a):pass
 def DrawLine(self,a,b,flags):self.lines.append((a,b))
 def DrawHandle(self,*a):pass
 def DrawPolygon(self,*a):pass
 def DrawArrayEnd(self):pass
class BC(dict):
 def GetId(self):return 0
for i,name in enumerate(('Opolygon','Tphong','Tuvw','Ttexture','Tpolygonselection','Tpointselection','Tedgeselection','Tvertexmap','ID_TAGFIELD_ENABLE','POINTSELECTIONTAG_ENABLEFIELDS','POLYGONSELECTIONTAG_ENABLEFIELDS','EDGESELECTIONTAG_ENABLEFIELDS','BFM_INPUT_CHANNEL','BFM_INPUT_MOUSELEFT','BFM_CURSORINFO_REMOVE','RESULT_BUBBLEHELP','TOOLDRAW_NONE','DRAWHANDLE_BIG','UNDOTYPE_CHANGE','MSG_UPDATE','BFM_INPUT_X','BFM_INPUT_Y','KEY_ESC')):setattr(c,name,i+1)
c.Vector=Vec;c.Matrix=Matrix;c.CPolygon=Polygon;c.StopAllThreads=lambda:None;c.EventAdd=lambda:None
c.plugins=types.SimpleNamespace(ToolData=object);c.gui=types.SimpleNamespace(SubDialog=object,MessageDialog=lambda m:(_ for _ in ()).throw(AssertionError(m)))
c.bitmaps=types.SimpleNamespace();doc=Doc();c.documents=types.SimpleNamespace(GetActiveDocument=lambda:doc);sys.modules['c4d']=c
p=os.path.join(os.path.dirname(__file__),'BridgeInteractive','bridge_interactive.pyp');mod=runpy.run_path(p,run_name='test');t=mod['Tool']();t.cuts=1;bd=BD()
t.GetCursorInfo(doc,None,bd,0,0,BC());t.MouseInput(doc,None,bd,None,{c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT})
t.GetCursorInfo(doc,None,bd,100,0,BC());t.MouseInput(doc,None,bd,None,{c.BFM_INPUT_CHANNEL:c.BFM_INPUT_MOUSELEFT})
assert t.preview_data is not None and len(doc.obj.fs)==2
t.Draw(doc,None,bd,None,None,0);assert bd.lines
t.apply();assert doc.undo==1 and len(doc.obj.fs)==8 and len(doc.obj.pts)==12
print('PASS: simulated two clicks, preview draw, unchanged source, apply, undo registration. NOT a Cinema 4D runtime test.')
