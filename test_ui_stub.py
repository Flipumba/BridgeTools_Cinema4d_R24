import os,runpy,types
G=runpy.run_path(os.path.join(os.path.dirname(__file__),'test_integration_stub.py'))
c=G['c'];m=G['mod']; c.BFH_SCALEFIT=1;c.BFH_LEFT=2
t=m['Tool']();d=m['Settings'](t);store={};children=[];calls=[]
for name in ('AddStaticText','GroupBegin','GroupEnd','AddComboBox','AddEditNumberArrows','AddEditSlider','AddCheckbox','AddButton'):
 setattr(d,name,lambda *args,_name=name,**kwargs:calls.append((_name,args,kwargs)))
d.AddChild=lambda i,idx,text:children.append((i,idx,text))
d.SetInt32=lambda i,v,*args:store.update({i:v});d.SetFloat=lambda i,v,*args:store.update({i:v});d.SetBool=lambda i,v:store.update({i:v})
d.GetInt32=lambda i:store[i];d.GetFloat=lambda i:store[i];d.GetBool=lambda i:store[i]
assert d.CreateLayout() and d.InitValues()
assert len(children)==21 and store[m['CUTS']]==0 and store[m['PREVIEW_SHADED']]
store[m['CUTS']]=4;store[m['PAIR_MODE']]=True;d.Command(m['CUTS'],None)
assert t.cuts==4 and t.pair_mode
print('PASS: simulated layout creation, control initialization and settings updates; no Cinema 4D runtime.')
