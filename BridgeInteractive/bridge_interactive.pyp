# -*- coding: utf-8 -*-
"""EXPERIMENTAL: Cinema 4D S24 interactive bridge. Not verified in Cinema 4D."""
import os, sys, math, importlib.util, traceback
import c4d
from c4d import plugins, gui, documents, bitmaps
ROOT=os.path.dirname(os.path.abspath(__file__))
_spec=importlib.util.spec_from_file_location('bridge_interactive_core',os.path.join(ROOT,'bridge_core.py'))
core=importlib.util.module_from_spec(_spec); sys.modules[_spec.name]=core; _spec.loader.exec_module(core)
_uv_spec=importlib.util.spec_from_file_location('bridge_interactive_uv',os.path.join(ROOT,'bridge_uv.py'))
uvmap=importlib.util.module_from_spec(_uv_spec); _uv_spec.loader.exec_module(uvmap)
_edge_spec=importlib.util.spec_from_file_location('bridge_interactive_edges',os.path.join(ROOT,'bridge_edges.py'))
edges=importlib.util.module_from_spec(_edge_spec);sys.modules[_edge_spec.name]=edges;_edge_spec.loader.exec_module(edges)
_sel_spec=importlib.util.spec_from_file_location('bridge_interactive_selections',os.path.join(ROOT,'bridge_selections.py'))
selectionmap=importlib.util.module_from_spec(_sel_spec);_sel_spec.loader.exec_module(selectionmap)
_weight_spec=importlib.util.spec_from_file_location('bridge_interactive_weights',os.path.join(ROOT,'bridge_weights.py'))
weightmap=importlib.util.module_from_spec(_weight_spec);sys.modules[_weight_spec.name]=weightmap;_weight_spec.loader.exec_module(weightmap)
_validate_spec=importlib.util.spec_from_file_location('bridge_interactive_validate',os.path.join(ROOT,'bridge_validate.py'))
validator=importlib.util.module_from_spec(_validate_spec);_validate_spec.loader.exec_module(validator)
PLUGIN_ID=1000002 # local development ID, not a registered ID
CUTS,TWIST,SMOOTH,PROFILE,ANGLE,INTERP,APPLY,RESET,MERGE,MERGE_FACTOR,PROFILE_SHAPE,INPUT_MODE,PAIR_MODE,PREVIEW_SHADED,DRAG_PARAM=range(2001,2016)
PROFILES=('SMOOTH','SPHERE','ROOT','SHARP','LINEAR','CONSTANT','INVERSE_SQUARE')

def read_object(obj):
    pts=[(p.x,p.y,p.z) for p in obj.GetAllPoints()]
    faces=[(p.a,p.b,p.c,p.d) for p in obj.GetAllPolygons()]
    select=obj.GetPolygonS(); chosen=tuple(i for i in range(len(faces)) if select.IsSelected(i))
    return pts,faces,chosen

def read_selected_edges(obj,faces):
    sel=obj.GetEdgeS(); selected=set()
    for i,f in enumerate(faces):
        for j,(a,b) in enumerate(zip(f,f[1:]+f[:1])):
            if a!=b and sel.IsSelected(4*i+j):selected.add(edges.key(a,b))
    return tuple(sorted(selected))

def safe_object(obj):
    if obj.GetNgonCount(): raise ValueError('N-gons пока не поддерживаются. Отменено без изменения объекта.')
    # Variable / indexed tags require topology and UV remapping; reject instead of corrupting them.
    allowed=(c4d.Tphong,c4d.Tuvw,c4d.Ttexture,c4d.Tpolygonselection,c4d.Tpointselection,c4d.Tedgeselection,c4d.Tvertexmap)
    bad=[tag.GetName() for tag in obj.GetTags() if tag.GetType() not in allowed]
    if bad: raise ValueError('Пока не поддерживаются теги объекта: %s. Операция отменена.' % ', '.join(bad))
    field_parameters={c4d.Tvertexmap:c4d.ID_TAGFIELD_ENABLE,
                      c4d.Tpointselection:c4d.POINTSELECTIONTAG_ENABLEFIELDS,
                      c4d.Tpolygonselection:c4d.POLYGONSELECTIONTAG_ENABLEFIELDS,
                      c4d.Tedgeselection:c4d.EDGESELECTIONTAG_ENABLEFIELDS}
    for tag in obj.GetTags():
        field_id=field_parameters.get(tag.GetType())
        if field_id is not None and tag[field_id]:raise ValueError('Тег с активными Fields пока не поддерживается; операция отменена.')

class Settings(gui.SubDialog):
    def __init__(self,tool): self.tool=tool
    def CreateLayout(self):
        self.AddStaticText(2090,c4d.BFH_SCALEFIT,name='Выберите две вершины; Shift + перетаскивание меняет настройку.')
        self.GroupBegin(2091,c4d.BFH_SCALEFIT,2,0)
        def label(i,text):self.AddStaticText(3000+i,c4d.BFH_LEFT,name=text)
        def combo(i,text,items):
            label(i,text);self.AddComboBox(i,c4d.BFH_SCALEFIT)
            for k,item in enumerate(items):self.AddChild(i,k,item)
        def number(i,text,slider=False):
            label(i,text)
            if slider:self.AddEditSlider(i,c4d.BFH_SCALEFIT)
            else:self.AddEditNumberArrows(i,c4d.BFH_SCALEFIT)
        combo(INPUT_MODE,'Источник',('Выделенные грани','Выделенные рёбра'))
        combo(INTERP,'Интерполяция',('Линейная','По пути','По поверхности'))
        number(CUTS,'Разрезы');number(TWIST,'Сдвиг соответствия')
        number(SMOOTH,'Сглаживание');number(PROFILE,'Выпуклость');number(ANGLE,'Угол, градусы')
        combo(PROFILE_SHAPE,'Форма профиля',('Smooth','Sphere','Root','Sharp','Linear','Constant','Inverse Square'))
        label(MERGE,'Объединение');self.AddCheckbox(MERGE,c4d.BFH_LEFT,0,0,'Merge')
        number(MERGE_FACTOR,'Положение слияния',True)
        combo(PAIR_MODE,'Режим контуров',('Два контура','Попарно','Последовательно','Замкнуть последовательность'))
        combo(DRAG_PARAM,'Shift + перетаскивание',('Разрезы','Сдвиг соответствия','Сглаживание','Выпуклость','Угол'))
        label(PREVIEW_SHADED,'Предпросмотр');self.AddCheckbox(PREVIEW_SHADED,c4d.BFH_LEFT,0,0,'Показывать поверхность')
        self.GroupEnd()
        self.AddButton(APPLY,c4d.BFH_SCALEFIT,name='Применить мост')
        self.AddButton(RESET,c4d.BFH_SCALEFIT,name='Сбросить выбор')
        return True
    def InitValues(self):
        t=self.tool
        self.SetInt32(CUTS,t.cuts,0,1000,1);self.SetInt32(TWIST,t.twist,-1000,1000,1)
        self.SetFloat(SMOOTH,t.smooth,0.,1000.,.05);self.SetFloat(PROFILE,t.profile,-1000.,1000.,.05)
        self.SetFloat(ANGLE,t.angle,-3600.,3600.,5.);self.SetInt32(INTERP,t.interp)
        self.SetInt32(PROFILE_SHAPE,t.profile_shape);self.SetBool(MERGE,t.merge);self.SetFloat(MERGE_FACTOR,t.merge_factor,0.,1.,.05)
        self.SetInt32(INPUT_MODE,t.input_mode);self.SetInt32(PAIR_MODE,1 if t.pair_mode else t.sequence_mode);self.SetInt32(DRAG_PARAM,t.drag_param);self.SetBool(PREVIEW_SHADED,t.preview_shaded)
        return True
    def Command(self,id,msg):
        try:
            t=self.tool
            if id in (CUTS,TWIST,SMOOTH,PROFILE,ANGLE,INTERP,MERGE,MERGE_FACTOR,PROFILE_SHAPE,INPUT_MODE,PAIR_MODE,PREVIEW_SHADED,DRAG_PARAM):
                t.cuts=self.GetInt32(CUTS);t.twist=self.GetInt32(TWIST);t.smooth=self.GetFloat(SMOOTH)
                t.profile=self.GetFloat(PROFILE);t.angle=self.GetFloat(ANGLE);t.interp=self.GetInt32(INTERP)
                t.profile_shape=self.GetInt32(PROFILE_SHAPE);t.merge=self.GetBool(MERGE);t.merge_factor=self.GetFloat(MERGE_FACTOR)
                mode=self.GetInt32(INPUT_MODE);multimode=self.GetInt32(PAIR_MODE);pair=multimode==1;sequence=multimode if multimode>=2 else 0;t.preview_shaded=self.GetBool(PREVIEW_SHADED);t.drag_param=self.GetInt32(DRAG_PARAM)
                if mode!=t.input_mode or pair!=t.pair_mode or sequence!=t.sequence_mode:
                    t.clear();t.input_mode=mode;t.pair_mode=pair;t.sequence_mode=sequence
                if len(t.anchors)==1 and t.cursor is not None and t.cursor_bd is not None:
                    t.hover_anchor=None
                    t.update_hover(t.cursor_bd,*t.cursor)
                else:t.make_preview()
            elif id==APPLY:t.apply()
            elif id==RESET:t.clear();c4d.EventAdd()
        except Exception as e: traceback.print_exc();gui.MessageDialog(str(e))
        return True

class Tool(plugins.ToolData):
    def __init__(self):
        self.cuts=0;self.twist=0;self.smooth=1.;self.profile=0.;self.angle=0.;self.interp=1
        self.merge=False;self.merge_factor=.5;self.profile_shape=0;self.input_mode=0;self.pair_mode=False;self.sequence_mode=0;self.preview_shaded=True
        self.cursor=None;self.cursor_bd=None;self.drag_param=1;self.dialog=None;self.clear()
    def clear(self):
        self.doc=None;self.obj=None;self.snapshot=None;self.edge_selection=None;self.loops=None;self.anchors=[];self.hover_first=None;self.hover_anchor=None;self.preview_data=None;self.preview_plans=None;self.preview_kept=None
    def InitTool(self,doc,data,bt): self.clear();return True
    def FreeTool(self,doc,data):self.clear()
    def AllocSubDialog(self,bc):
        self.dialog=Settings(self)
        return self.dialog
    def GetCursorInfo(self,doc,data,bd,x,y,bc):
        if bc.GetId()==c4d.BFM_CURSORINFO_REMOVE:
            self.cursor=None;self.cursor_bd=None
            if not self.anchors and self.hover_first is not None:
                self.hover_first=None;c4d.EventAdd()
            if len(self.anchors)==1 and self.hover_anchor is not None:
                self.hover_anchor=None;self.preview_data=None;self.preview_plans=None;self.preview_kept=None;c4d.EventAdd()
            return True
        self.cursor=(x,y);self.cursor_bd=bd
        bc[c4d.RESULT_BUBBLEHELP]='Нажмите вершину границы каждой из двух выделенных групп полигонов.'
        if not self.anchors:
            try:
                self.capture_context(doc)
                self.update_first_hover(bd,x,y)
            except Exception:
                had_highlight=self.hover_first is not None
                self.clear()
                if had_highlight:c4d.EventAdd()
        if doc==self.doc and len(self.anchors)==1:
            try:self.update_hover(bd,x,y)
            except Exception:
                had_preview=self.preview_data is not None
                self.hover_anchor=None;self.preview_data=None;self.preview_plans=None;self.preview_kept=None
                if had_preview:c4d.EventAdd()
        return True
    def capture_context(self,doc):
        obj=doc.GetActiveObject()
        if obj is None or not obj.CheckType(c4d.Opolygon):raise ValueError('Выберите один редактируемый полигональный объект.')
        safe_object(obj);snap=read_object(obj)
        selected_edges=read_selected_edges(obj,snap[1]) if self.input_mode else None
        if self.obj==obj and self.doc==doc and self.snapshot==snap and self.edge_selection==selected_edges and self.loops is not None:
            return snap,self.loops
        if self.input_mode:
            chains=edges.ordered_chains(selected_edges)
            if self.pair_mode:
                if len(chains)<2 or len(chains)%2:raise ValueError('Для режима пар требуется чётное число контуров.')
            elif self.sequence_mode and len(chains)>2:
                raise ValueError('Последовательное соединение более двух граничных цепочек рёбер создаёт неманифолдные рёбра; используйте группы граней.')
            elif len(chains)!=2 or chains[0][1]!=chains[1][1]:raise ValueError('Выделите две открытые цепочки либо два замкнутых контура.')
            loops=[ch if closed else [ch[0],ch[-1]] for ch,closed in chains]
        else:
            _,loops=core.find_islands(snap[1],snap[2],allow_many=self.pair_mode or bool(self.sequence_mode))
            if self.pair_mode and len(loops)%2:raise ValueError('Для режима пар нужно чётное число групп граней.')
        self.clear();self.obj=obj;self.doc=doc;self.snapshot=snap;self.edge_selection=selected_edges;self.loops=loops
        return snap,loops
    def update_first_hover(self,bd,x,y):
        mg=self.obj.GetMg();pts=self.snapshot[0];candidates=[]
        for side,loop in enumerate(self.loops):
            for i in loop:
                p=bd.WS(mg*c4d.Vector(*pts[i]));d=(p.x-x)**2+(p.y-y)**2
                if d<=24**2:candidates.append((d,side,i))
        candidate=None if not candidates else min(candidates)[1:]
        if candidate!=self.hover_first:self.hover_first=candidate;c4d.EventAdd()
    def update_hover(self,bd,x,y):
        if len(self.anchors)!=1:return
        if not self.valid():self.clear();c4d.EventAdd();return
        mg=self.obj.GetMg();pts=self.snapshot[0];first_side=self.anchors[0][0];candidates=[]
        for side,loop in enumerate(self.loops):
            if side==first_side:continue
            for i in loop:
                p=bd.WS(mg*c4d.Vector(*pts[i]));d=(p.x-x)**2+(p.y-y)**2
                if d<=24**2:candidates.append((d,side,i))
        candidate=None if not candidates else min(candidates)[1:]
        if candidate==self.hover_anchor:return
        self.hover_anchor=candidate
        if candidate is None:
            self.preview_data=None;self.preview_plans=None;self.preview_kept=None;c4d.EventAdd();return
        # Build the same preview as a committed second click, without
        # committing the anchor until the user actually clicks.
        self.anchors.append(candidate)
        try:self.make_preview()
        finally:self.anchors.pop()
    def MouseInput(self,doc,data,bd,win,msg):
        if msg[c4d.BFM_INPUT_CHANNEL]!=c4d.BFM_INPUT_MOUSELEFT:return True
        if len(self.anchors)==2 and msg[c4d.BFM_INPUT_QUALIFIER]&c4d.QUALIFIER_SHIFT:
            try:self.drag_parameter(win,msg)
            except Exception as e:traceback.print_exc();gui.MessageDialog(str(e))
            return True
        try:
            c4d.StopAllThreads();snap,loops=self.capture_context(doc);obj=self.obj
            if self.cursor is None or self.cursor_bd!=bd:raise ValueError('Наведите курсор на вершину и нажмите ещё раз.')
            x,y=self.cursor;mg=obj.GetMg();pts=snap[0]; candidates=[]
            for side,loop in enumerate(loops):
                for i in loop:
                    p=bd.WS(mg*c4d.Vector(*pts[i]));d=(p.x-x)**2+(p.y-y)**2
                    if d<=24**2:candidates.append((d,side,i))
            if not candidates:raise ValueError('Нажмите ближе к вершине границы выделенных граней.')
            # Projected loops may overlap exactly. After choosing the first
            # anchor, favor another loop when it is also under the cursor.
            if self.anchors:
                best=min(candidate[0] for candidate in candidates)
                other=[candidate for candidate in candidates
                       if candidate[1]!=self.anchors[0][0] and candidate[0]<=best+16]
                if other:candidates=other
            _,side,i=min(candidates)
            self.hover_first=None;self.hover_anchor=None
            if not self.anchors or side==self.anchors[0][0]:self.anchors=[(side,i)];self.preview_data=None
            else:self.anchors=[self.anchors[0],(side,i)];self.make_preview()
            c4d.EventAdd()
        except Exception as e:traceback.print_exc();gui.MessageDialog(str(e))
        return True
    def drag_parameter(self,win,msg):
        """Adjust one parameter from relative mouse deltas, restoring on Escape.

        MOUSEDRAGFLAGS_NONE lets Cinema 4D own the hidden-pointer drag; cursor
        wrapping and actual event behaviour still require host verification.
        """
        if not self.valid() or self.preview_data is None:raise ValueError('Сначала выберите две вершины и постройте предпросмотр.')
        fields=('cuts','twist','smooth','profile','angle')
        limits=((0,1000),(-1000,1000),(0.,1000.),(-1000.,1000.),(-3600.,3600.))
        scales=(.125,.125,.01,.01,.5)
        field=fields[self.drag_param];initial=getattr(self,field);accum=0.;end=None
        win.MouseDragStart(c4d.KEY_MLEFT,msg[c4d.BFM_INPUT_X],msg[c4d.BFM_INPUT_Y],c4d.MOUSEDRAGFLAGS_NONE)
        try:
            while True:
                result,dx,dy,channels=win.MouseDrag()
                if result!=c4d.MOUSEDRAGRESULT_CONTINUE:break
                accum+=dx
                low,high=limits[self.drag_param];value=max(low,min(high,initial+accum*scales[self.drag_param]))
                if self.drag_param in (0,1):value=int(round(value))
                prior=getattr(self,field)
                if value==prior:continue
                setattr(self,field,value)
                try:self.make_preview()
                except ValueError:
                    setattr(self,field,prior);self.make_preview()
                self.sync_drag_control()
                c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW|c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION)
        finally:
            end=win.MouseDragEnd()
            if end==c4d.MOUSEDRAGRESULT_ESCAPE:
                setattr(self,field,initial);self.make_preview();self.sync_drag_control()
                c4d.EventAdd()

    def sync_drag_control(self):
        if self.dialog is None:return
        i=self.drag_param
        try:
            if i==0:self.dialog.SetInt32(CUTS,self.cuts,0,1000,1)
            elif i==1:self.dialog.SetInt32(TWIST,self.twist,-1000,1000,1)
            elif i==2:self.dialog.SetFloat(SMOOTH,self.smooth,0.,1000.,.05)
            elif i==3:self.dialog.SetFloat(PROFILE,self.profile,-1000.,1000.,.05)
            else:self.dialog.SetFloat(ANGLE,self.angle,-3600.,3600.,5.)
        except (AttributeError,RuntimeError):pass

    def valid(self):
        return (self.obj is not None and self.obj.IsAlive() and self.doc==documents.GetActiveDocument()
                and self.doc.GetActiveObject()==self.obj and read_object(self.obj)==self.snapshot
                and (not self.input_mode or read_selected_edges(self.obj,self.snapshot[1])==self.edge_selection))
    def make_preview(self):
        self.preview_data=None
        if len(self.anchors)!=2:c4d.EventAdd();return
        if not self.valid():self.clear();raise ValueError('Объект или выделение изменены: выберите вершины заново.')
        pts,faces,sel=self.snapshot
        args=(pts,faces,self.edge_selection if self.input_mode else sel,self.anchors[0][1],self.anchors[1][1],
            self.cuts,self.twist,self.smooth,self.profile,math.radians(self.angle),('LINEAR','PATH','SURFACE')[self.interp],
            self.merge,self.merge_factor,PROFILES[self.profile_shape])
        self.preview_plans=None;self.preview_kept=None
        if self.sequence_mode and not self.input_mode:
            p,f,idx,self.preview_plans,self.preview_kept=core.bridge_face_chain(*args,closed=self.sequence_mode==3)
        elif self.pair_mode and self.input_mode:
            p,f,idx,self.preview_plans=edges.bridge_edge_pairs(*args)
        elif self.pair_mode:
            p,f,idx,self.preview_plans,self.preview_kept=core.bridge_face_pairs(*args)
        else:p,f,idx=edges.bridge_edges(*args) if self.input_mode else core.bridge(*args)
        validator.validate_result(p,f,idx)
        self.preview_data=(p,f,idx)
        c4d.EventAdd()
    def Draw(self,doc,data,bd,bh,bt,flags):
        try:
            if self.obj is None or not self.obj.IsAlive() or self.doc!=doc:return c4d.TOOLDRAW_NONE
            bd.SetMatrix_Matrix(None,c4d.Matrix());mg=self.obj.GetMg();bd.SetPen(c4d.Vector(1.,.6,.05))
            if self.preview_data:
                pts,faces,new=self.preview_data;done=set()
                if self.preview_shaded:
                    for i in new:
                        f=faces[i];p=[mg*c4d.Vector(*pts[j]) for j in f]
                        normal=core.unit(core.cross(core.sub(pts[f[1]],pts[f[0]]),core.sub(pts[f[2]],pts[f[0]])))
                        brightness=.28+.35*abs(core.dot(normal,core.unit((.3,.7,1.))))
                        color=c4d.Vector(brightness,brightness*.66,brightness*.25)
                        bd.DrawPolygon(p,[color]*len(p))
                    bd.DrawArrayEnd()
                for i in new:
                    f=faces[i]
                    for a,b in zip(f,f[1:]+f[:1]):
                        k=core.key(a,b)
                        if k not in done:
                            bd.DrawLine(mg*c4d.Vector(*pts[a]),mg*c4d.Vector(*pts[b]),0);done.add(k)
            if self.snapshot:
                if self.hover_first:bd.DrawHandle(mg*c4d.Vector(*self.snapshot[0][self.hover_first[1]]),c4d.DRAWHANDLE_BIG,0)
                for _,i in self.anchors:bd.DrawHandle(mg*c4d.Vector(*self.snapshot[0][i]),c4d.DRAWHANDLE_BIG,0)
                if self.hover_anchor:bd.DrawHandle(mg*c4d.Vector(*self.snapshot[0][self.hover_anchor[1]]),c4d.DRAWHANDLE_BIG,0)
        except Exception:traceback.print_exc()
        return c4d.TOOLDRAW_NONE
    def KeyboardInput(self,doc,data,bd,win,msg):
        key=msg[c4d.BFM_INPUT_CHANNEL]
        if not self.anchors or doc!=self.doc:return False
        if key==c4d.KEY_ESC:
            self.clear();c4d.EventAdd();return True
        if key==c4d.KEY_ENTER and len(self.anchors)==2:
            try:self.apply()
            except Exception as e:traceback.print_exc();gui.MessageDialog(str(e))
            return True
        return False
    def apply(self):
        if len(self.anchors)!=2 or not self.preview_data:raise ValueError('Сначала выберите две вершины и постройте предпросмотр.')
        if not self.valid():self.clear();raise ValueError('Объект или выделение изменены. Выберите вершины заново.')
        safe_object(self.obj)
        pts,faces,new=self.preview_data;obj=self.obj;doc=self.doc;c4d.StopAllThreads()
        oldpts,oldfaces,selection=self.snapshot
        uv_tags=[tag for tag in obj.GetTags() if tag.GetType()==c4d.Tuvw]
        # Snapshot before geometry resizing. The old polygon index -> new one mapping
        # is explicit so seams and pins on retained polygons do not move.
        if self.preview_plans is not None:
            retained=list(range(len(oldfaces))) if self.input_mode else self.preview_kept;generated=[];uv_fragments=[]
            for plan in self.preview_plans:
                if self.input_mode:
                    _,uvs=uvmap.create_edge_uv_plan(plan['faces'],plan['edges'],plan['a'],plan['b'],self.twist,self.cuts,
                        [] if self.merge else [faces[i] for i in plan['new_indices']],plan['point_count'],self.merge)
                else:
                    _,uvs=uvmap.create_uv_plan_with_point_count(plan['faces'],plan['selected'],plan['a'],plan['b'],self.twist,self.cuts,
                        plan['new_faces'],plan['point_count'],self.merge,plan.get('reverse_b',True))
                generated.extend(uvs);uv_fragments.append((plan,uvs))
        else:
            uv_builder=uvmap.create_edge_uv_plan if self.input_mode else uvmap.create_uv_plan_with_point_count
            retained,generated=uv_builder(oldfaces,self.edge_selection if self.input_mode else selection,
                self.anchors[0][1],self.anchors[1][1],self.twist,self.cuts,
                [] if self.merge else [faces[i] for i in new],len(oldpts),self.merge)
        weight_data=[]
        for tag in obj.GetTags():
            if tag.GetType()!=c4d.Tvertexmap:continue
            values=tag.GetAllHighlevelData()
            if len(values)!=len(oldpts):raise ValueError('Размер Vertex Map не соответствует числу вершин.')
            if self.preview_plans is not None:
                for plan in self.preview_plans:
                    if self.merge and 'merge_vertex_pairs' in plan:
                        values=list(values)
                        for a,b in plan['merge_vertex_pairs']:
                            values[a]=values[a]*(1-self.merge_factor)+values[b]*self.merge_factor
                    else:
                        values=weightmap.apply_pair_weights(values,plan['faces'],plan['edges'] if self.input_mode else plan['selected'],
                            plan['a'],plan['b'],self.twist,self.cuts,self.input_mode,self.merge,self.merge_factor,plan.get('reverse_b',True))
            else:
                values=weightmap.apply_pair_weights(values,oldfaces,self.edge_selection if self.input_mode else selection,
                    self.anchors[0][1],self.anchors[1][1],self.twist,self.cuts,self.input_mode,self.merge,self.merge_factor)
            if len(values)!=len(pts):raise RuntimeError('Ошибка переноса весов вершин.')
            weight_data.append((tag,values))
        pre_point_map=selectionmap.vertex_remap(oldfaces,faces,retained,len(oldpts))
        pts,faces,compact=selectionmap.compact_newly_orphaned_points(oldfaces,faces,pts,len(oldpts))
        point_map={old:compact[new] for old,new in pre_point_map.items() if new in compact}
        weight_data=[(tag,[values[i] for i in sorted(compact,key=compact.get)]) for tag,values in weight_data]
        def selected_set(base,count):return {i for i in range(count) if base.IsSelected(i)}
        selection_data=[]
        for tag in obj.GetTags():
            typ=tag.GetType()
            if typ not in (c4d.Tpolygonselection,c4d.Tpointselection,c4d.Tedgeselection):continue
            base=tag.GetBaseSelect()
            if typ==c4d.Tpolygonselection:
                mapped=selectionmap.remap_polygons(selected_set(base,len(oldfaces)),retained)
            elif typ==c4d.Tpointselection:
                mapped=selectionmap.remap_points(selected_set(base,len(oldpts)),point_map)
            else:
                mapped=selectionmap.remap_edges(selected_set(base,4*len(oldfaces)),oldfaces,faces,point_map)
            selection_data.append((tag,mapped))
        hidden_data=[]
        for getter,kind in (('GetPointH','point'),('GetPolygonH','polygon'),('GetEdgeH','edge'),('GetPhongBreak','edge')):
            fn=getattr(obj,getter,None)
            base=fn() if fn else None
            if base is None:continue
            count=len(oldpts) if kind=='point' else len(oldfaces) if kind=='polygon' else 4*len(oldfaces)
            old=selected_set(base,count)
            mapped=(selectionmap.remap_points(old,point_map) if kind=='point' else
                    selectionmap.remap_polygons(old,retained) if kind=='polygon' else
                    selectionmap.remap_edges(old,oldfaces,faces,point_map))
            hidden_data.append((getter,mapped))
        uv_data=[]
        for tag in uv_tags:
            if tag.GetDataCount()!=len(oldfaces):raise ValueError('Размер UV-тега не совпадает с числом полигонов.')
            all_corners=[tag.GetSlow(i) for i in range(len(oldfaces))]
            corners=[all_corners[i] for i in retained]
            generated_for_tag=generated
            if generated:
                uv_triples=[tuple((corner[k].x,corner[k].y,corner[k].z) for k in ('a','b','c','d')) for corner in all_corners]
                def transfer(source_faces,source_uv,selected,a,b,rect,reverse_b=True):
                    try:
                        return uvmap.interpolate_boundary_uv(source_faces,source_uv,selected,a,b,
                            self.twist,bool(self.input_mode),rect,reverse_b)
                    except ValueError:
                        # Isolated source faces have no retained UV boundary.
                        return rect
                if self.preview_plans is None:
                    generated_for_tag=transfer(oldfaces,uv_triples,self.edge_selection if self.input_mode else selection,
                                               self.anchors[0][1],self.anchors[1][1],generated)
                else:
                    generated_for_tag=[]
                    empty_uv=((0.,0.,0.),)*4
                    for plan,rect in uv_fragments:
                        source_uv=[uv_triples[i] if i is not None else empty_uv for i in plan['face_origins']]
                        generated_for_tag.extend(transfer(plan['faces'],source_uv,
                            plan['edges'] if self.input_mode else plan['selected'],plan['a'],plan['b'],rect,plan.get('reverse_b',True)))
            pins=tag.GetPinSelection()
            oldpins=[i for i in range(len(oldfaces)*4) if pins.IsSelected(i)] if pins else []
            uv_data.append((tag,corners,uvmap.remap_uv_pins(oldpins,retained),generated_for_tag))
        if not doc.StartUndo():raise RuntimeError('Не удалось начать Undo.')
        undo=False;failed=False
        try:
            if not doc.AddUndo(c4d.UNDOTYPE_CHANGE,obj):raise RuntimeError('Не удалось создать Undo.')
            undo=True
            for tag,_,_,_ in uv_data:
                if not doc.AddUndo(c4d.UNDOTYPE_CHANGE,tag):raise RuntimeError('Не удалось создать Undo для UV.')
            for tag,_ in selection_data:
                if not doc.AddUndo(c4d.UNDOTYPE_CHANGE,tag):raise RuntimeError('Не удалось создать Undo для выделения.')
            for tag,_ in weight_data:
                if not doc.AddUndo(c4d.UNDOTYPE_CHANGE,tag):raise RuntimeError('Не удалось создать Undo для весов.')
            if not obj.ResizeObject(len(pts),len(faces)):raise RuntimeError('Не удалось изменить размер объекта.')
            obj.SetAllPoints([c4d.Vector(*p) for p in pts])
            for i,f in enumerate(faces):
                if len(f)==3:obj.SetPolygon(i,c4d.CPolygon(f[0],f[1],f[2],f[2]))
                else:obj.SetPolygon(i,c4d.CPolygon(*f))
            for tag,old_uv,pins,generated_for_tag in uv_data:
                if tag.GetDataCount()!=len(faces):raise RuntimeError('Cinema 4D не изменил размер UV-тега.')
                for i,uv in enumerate(old_uv):tag.SetSlow(i,uv['a'],uv['b'],uv['c'],uv['d'])
                for j,uv in enumerate(generated_for_tag):tag.SetSlow(len(old_uv)+j,*[c4d.Vector(*v) for v in uv])
                pin_sel=c4d.BaseSelect()
                for index in pins:pin_sel.Select(index)
                if not tag.SetPinSelection(pin_sel):raise RuntimeError('Не удалось восстановить закреплённые UV-точки.')
                tag.Message(c4d.MSG_UPDATE)
            for tag,values in weight_data:
                if tag.GetDataCount()!=len(pts):raise RuntimeError('Cinema 4D не изменил размер Vertex Map.')
                tag.SetAllHighlevelData(values);tag.Message(c4d.MSG_UPDATE)
            for tag,selected in selection_data:
                bs=tag.GetBaseSelect();bs.DeselectAll()
                for i in selected:bs.Select(i)
                tag.Message(c4d.MSG_UPDATE)
            for getter,selected in hidden_data:
                bs=getattr(obj,getter)();bs.DeselectAll()
                for i in selected:bs.Select(i)
            obj.GetPolygonS().DeselectAll()
            for i in new:obj.GetPolygonS().Select(i)
            obj.GetPointS().DeselectAll();obj.GetEdgeS().DeselectAll();obj.Message(c4d.MSG_UPDATE)
        except Exception:failed=True;raise
        finally:
            doc.EndUndo()
            if failed and undo:doc.DoUndo()
            c4d.EventAdd()
        self.clear()

if __name__=='__main__':
    try:
        icon=bitmaps.BaseBitmap()
        if icon.InitWith(os.path.join(ROOT,'res','icon.png'))[0]!=c4d.IMAGERESULT_OK:icon=None
        ok=plugins.RegisterToolPlugin(PLUGIN_ID,'Bridge Interactive (experimental)',0,icon,'Bridge face islands.',Tool())
        print('[Bridge Interactive experimental] registered:',ok)
    except Exception:traceback.print_exc()
