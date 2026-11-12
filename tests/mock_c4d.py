# -*- coding: utf-8 -*-
"""Минимальная имитация API Cinema 4D для проверки плагина без хоста.

Здесь нет «умной» эмуляции: мок повторяет ровно те вызовы, которые
использует плагин. Это ловит опечатки в именах API, но НЕ доказывает
работу в Cinema 4D.
"""
import sys
import types


class Vector(object):
    __slots__ = ('x', 'y', 'z')

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __repr__(self):
        return 'Vector(%g, %g, %g)' % (self.x, self.y, self.z)

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        if isinstance(scalar, Vector):
            return Vector(self.x * scalar.x, self.y * scalar.y, self.z * scalar.z)
        return Vector(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def Cross(self, other):
        return Vector(self.y * other.z - self.z * other.y,
                      self.z * other.x - self.x * other.z,
                      self.x * other.y - self.y * other.x)

    def Dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def GetLength(self):
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5

    def Normalize(self):
        n = self.GetLength()
        if n > 0:
            self.x /= n
            self.y /= n
            self.z /= n
        return self

    def GetNormalized(self):
        return Vector(self.x, self.y, self.z).Normalize()


class Matrix(object):
    def __init__(self, offset=None):
        self.offset = offset or Vector()

    def __mul__(self, v):
        return v + self.offset


class CPolygon(object):
    def __init__(self, a=0, b=0, c=0, d=0):
        self.a, self.b, self.c, self.d = a, b, c, d

    def __repr__(self):
        return 'CPolygon(%d,%d,%d,%d)' % (self.a, self.b, self.c, self.d)


class BaseSelect(object):
    def __init__(self):
        self._sel = set()

    def IsSelected(self, index):
        return index in self._sel

    def Select(self, index):
        self._sel.add(index)

    def Deselect(self, index):
        self._sel.discard(index)

    def DeselectAll(self):
        self._sel.clear()

    def GetCount(self):
        return len(self._sel)

    def GetAll(self, count):
        return [i for i in range(count) if i in self._sel]


class UVWTag(object):
    def __init__(self, count):
        self._data = [[Vector(), Vector(), Vector(), Vector()] for _ in range(count)]
        self._pins = BaseSelect()
        self.name = 'UVW'

    def GetType(self):
        return sys.modules['c4d'].Tuvw

    def GetName(self):
        return self.name

    def GetDataCount(self):
        return len(self._data)

    def GetSlow(self, index):
        d = self._data[index]
        return {'a': d[0], 'b': d[1], 'c': d[2], 'd': d[3]}

    def SetSlow(self, index, a, b, c, d):
        self._data[index] = [Vector(a.x, a.y, a.z), Vector(b.x, b.y, b.z),
                             Vector(c.x, c.y, c.z), Vector(d.x, d.y, d.z)]

    def GetPinSelection(self):
        return self._pins

    def SetPinSelection(self, selection):
        self._pins = selection
        return True

    def Message(self, ident):
        return True

    def resize(self, count):
        while len(self._data) < count:
            self._data.append([Vector(), Vector(), Vector(), Vector()])
        self._data = self._data[:count]


class VariableTag(object):
    def __init__(self, tag_type, count):
        self.tag_type = tag_type
        self.values = [0.0] * count
        self.name = 'Vertex Map'

    def GetType(self):
        return self.tag_type

    def GetName(self):
        return self.name

    def GetDataCount(self):
        return len(self.values)

    def GetAllHighlevelData(self):
        return list(self.values)

    def SetAllHighlevelData(self, values):
        self.values = list(values)

    def Message(self, ident):
        return True

    def __getitem__(self, key):
        return False

    def __setitem__(self, key, value):
        pass


class SelectionTag(object):
    def __init__(self, tag_type, count):
        self.tag_type = tag_type
        self.base = BaseSelect()
        self.name = 'Selection'

    def GetType(self):
        return self.tag_type

    def GetName(self):
        return self.name

    def GetBaseSelect(self):
        return self.base

    def Message(self, ident):
        return True

    def __getitem__(self, key):
        return False


class PolygonObject(object):
    def __init__(self, point_count, polygon_count):
        self._points = [Vector() for _ in range(point_count)]
        self._polygons = [CPolygon() for _ in range(polygon_count)]
        self._tags = []
        self._polygon_selection = BaseSelect()
        self._point_selection = BaseSelect()
        self._edge_selection = BaseSelect()
        self._hidden = {'GetPointH': BaseSelect(), 'GetPolygonH': BaseSelect(),
                        'GetEdgeH': BaseSelect()}
        self.name = 'Mesh'
        self._alive = True
        self._matrix = Matrix()

    def GetAllPoints(self):
        return list(self._points)

    def GetAllPolygons(self):
        return list(self._polygons)

    def GetPointCount(self):
        return len(self._points)

    def GetPolygonCount(self):
        return len(self._polygons)

    def GetNgonCount(self):
        return getattr(self, '_ngons', 0)

    def ResizeObject(self, points, polygons):
        while len(self._points) < points:
            self._points.append(Vector())
        self._points = self._points[:points]
        while len(self._polygons) < polygons:
            self._polygons.append(CPolygon())
        self._polygons = self._polygons[:polygons]
        for tag in self._tags:
            if hasattr(tag, 'resize'):
                tag.resize(polygons)
        return True

    def SetAllPoints(self, points):
        self._points = list(points)

    def SetPolygon(self, index, polygon):
        self._polygons[index] = polygon

    def GetPolygonS(self):
        return self._polygon_selection

    def GetPointS(self):
        return self._point_selection

    def GetEdgeS(self):
        return self._edge_selection

    def GetPointH(self):
        return self._hidden['GetPointH']

    def GetPolygonH(self):
        return self._hidden['GetPolygonH']

    def GetEdgeH(self):
        return self._hidden['GetEdgeH']

    def GetTags(self):
        return list(self._tags)

    def InsertTag(self, tag):
        self._tags.append(tag)

    def CheckType(self, ident):
        return ident == sys.modules['c4d'].Opolygon

    def IsAlive(self):
        return self._alive

    def GetMg(self):
        return self._matrix

    def GetName(self):
        return self.name

    def SetName(self, name):
        self.name = name

    def Message(self, ident):
        return True


class Document(object):
    def __init__(self):
        self._objects = []
        self._active = None
        self.undo_depth = 0
        self.undo_registered = []
        self.undo_calls = 0
        self.redo_calls = 0
        self._snapshot = None
        self.undo_started = 0
        self.mode = 5000 + 2   # Mpolygons по умолчанию

    def GetMode(self):
        return self.mode

    def SetMode(self, mode):
        self.mode = mode

    def InsertObject(self, obj, parent=None, pred=None):
        self._objects.append(obj)
        if self._active is None:
            self._active = obj

    def GetFirstObject(self):
        return self._objects[0] if self._objects else None

    def GetActiveObject(self):
        return self._active

    def SetActiveObject(self, obj, mode=0):
        self._active = obj

    def StartUndo(self):
        self.undo_depth += 1
        self.undo_started += 1
        self._snapshot = _capture(self)
        return True

    def AddUndo(self, undotype, obj):
        self.undo_registered.append(obj)
        return True

    def EndUndo(self):
        self.undo_depth = max(0, self.undo_depth - 1)

    def DoUndo(self):
        self.undo_calls += 1
        if self._snapshot is None:
            return False
        _restore(self, self._snapshot)
        return True

    def DoRedo(self):
        self.redo_calls += 1
        return True


def _capture(doc):
    state = []
    for obj in doc._objects:
        state.append({
            'points': [(p.x, p.y, p.z) for p in obj._points],
            'polygons': [(p.a, p.b, p.c, p.d) for p in obj._polygons],
            'poly_sel': set(obj._polygon_selection._sel),
            'tags': [(getattr(t, '_data', None), getattr(t, 'values', None),
                      set(getattr(t, '_pins', BaseSelect())._sel),
                      set(getattr(t, 'base', BaseSelect())._sel)) for t in obj._tags],
        })
    return state


def _restore(doc, state):
    for obj, saved in zip(doc._objects, state):
        obj._points = [Vector(*p) for p in saved['points']]
        obj._polygons = [CPolygon(*p) for p in saved['polygons']]
        obj._polygon_selection._sel = set(saved['poly_sel'])
        for tag, (data, values, pins, base) in zip(obj._tags, saved['tags']):
            if data is not None:
                tag._data = [[Vector(c.x, c.y, c.z) for c in corner] for corner in data]
            if values is not None:
                tag.values = list(values)
            if hasattr(tag, '_pins'):
                tag._pins._sel = set(pins)
            if hasattr(tag, 'base'):
                tag.base._sel = set(base)


class BaseDraw(object):
    def __init__(self):
        self.lines = []
        self.handles = []
        self.polygons = []
        self.pen = None

    def WS(self, point):
        return point

    def SetPen(self, colour):
        self.pen = colour

    def SetMatrix_Matrix(self, obj, matrix):
        pass

    def DrawLine(self, a, b, flags):
        self.lines.append((a, b))

    def DrawHandle(self, position, handle_type, flags):
        self.handles.append(position)

    def DrawPolygon(self, points, colours):
        self.polygons.append((list(points), list(colours)))


def install():
    c4d = types.ModuleType('c4d')
    c4d.Vector = Vector
    c4d.Matrix = Matrix
    c4d.CPolygon = CPolygon
    c4d.BaseSelect = BaseSelect
    c4d.PolygonObject = PolygonObject
    c4d.UVWTag = UVWTag
    c4d.VariableTag = VariableTag
    c4d.BaseDraw = BaseDraw

    constants = {
        'Opolygon': 5100, 'Mpoints': 5000 + 0, 'Medges': 5000 + 1, 'Mpolygons': 5000 + 2, 'Tphong': 5612, 'Tuvw': 5671, 'Ttexture': 5616,
        'Tvertexmap': 5682, 'Tpolygonselection': 5673, 'Tpointselection': 5672,
        'Tedgeselection': 5674,
        'ID_TAGFIELD_ENABLE': 1000, 'POINTSELECTIONTAG_ENABLEFIELDS': 1000,
        'POLYGONSELECTIONTAG_ENABLEFIELDS': 1000, 'EDGESELECTIONTAG_ENABLEFIELDS': 1000,
        'BFM_INPUT_CHANNEL': 1001, 'BFM_INPUT_MOUSELEFT': 1002,
        'BFM_INPUT_QUALIFIER': 1003, 'BFM_INPUT_X': 1004, 'BFM_INPUT_Y': 1005,
        'BFM_CURSORINFO_REMOVE': 1006, 'RESULT_BUBBLEHELP': 1007,
        'QUALIFIER_SHIFT': 0x0001, 'TOOLDRAW_NONE': 0, 'DRAWHANDLE_BIG': 2,
        'UNDOTYPE_CHANGE': 500, 'MSG_UPDATE': 100,
        'KEY_ESC': 2001, 'KEY_ENTER': 2002, 'KEY_RETURN': 2002, 'KEY_MLEFT': 3001,
        'MOUSEDRAGFLAGS_NONE': 0, 'MOUSEDRAGRESULT_CONTINUE': 1,
        'MOUSEDRAGRESULT_ESCAPE': 2, 'MOUSEDRAGRESULT_FINISHED': 3,
        'DRAWFLAGS_ONLY_ACTIVE_VIEW': 1, 'DRAWFLAGS_NO_THREAD': 2,
        'DRAWFLAGS_NO_ANIMATION': 4, 'IMAGERESULT_OK': 0, 'CMD_ENABLED': 1,
    }
    for name, value in constants.items():
        setattr(c4d, name, value)

    # --- встроенный Bridge: константы, BaseContainer и SendModelingCommand ------------
    native_constants = {
        'ID_MODELING_BRIDGE_TOOL': 450000008,
        'MDATA_BRIDGE_ELEMENT1': 1100, 'MDATA_BRIDGE_ELEMENT2': 1101,
        'MDATA_BRIDGE_ELEMENT3': 1102, 'MDATA_BRIDGE_ELEMENT4': 1103,
        'MDATA_BRIDGE_OBJINDEX1': 1104, 'MDATA_BRIDGE_OBJINDEX2': 1105,
        'MDATA_BRIDGE_OBJINDEX3': 1106, 'MDATA_BRIDGE_OBJINDEX4': 1107,
        'MDATA_BRIDGE_DELETE': 1108, 'MDATA_BRIDGE_SUBDIVISION': 1110,
        'MDATA_BRIDGE_TENSION': 1111, 'MDATA_BRIDGE_BOTH_MODE': 1112,
        'MDATA_BRIDGE_BOTH_FLIP': 1113, 'MDATA_BRIDGE_FIRST_SELECT_ONLY': 1114,
        'MDATA_BRIDGE_SECOND_SELECT_ONLY': 1115,
        'MDATA_BRIDGE_MODE_SURFACE': 0, 'MDATA_BRIDGE_MODE_NORMAL': 1,
        'MDATA_BRIDGE_MODE_SURFACE_AVERAGE': 2, 'MDATA_BRIDGE_MODE_NORMAL_AVERAGE': 3,
        'MODELINGCOMMANDMODE_POINTSELECTION': 0, 'MODELINGCOMMANDMODE_EDGESELECTION': 1,
        'MODELINGCOMMANDMODE_POLYGONSELECTION': 2,
    }
    for name, value in native_constants.items():
        setattr(c4d, name, value)
    c4d.native_constants = native_constants

    class BaseContainer(dict):
        def SetBool(self, ident, value):
            self[ident] = bool(value)

        def SetInt32(self, ident, value):
            self[ident] = int(value)

    c4d.BaseContainer = BaseContainer

    utils = types.ModuleType('c4d.utils')
    utils.calls = []
    utils.fail = False
    utils.noop = False

    def send_modeling_command(command=None, list=None, mode=None, bc=None, doc=None,
                              flags=0):
        utils.calls.append({'command': command, 'list': list, 'mode': mode,
                            'bc': dict(bc), 'doc': doc})
        if utils.fail:
            return False
        if utils.noop:
            return True
        obj = list[0]
        # Имитация результата: мост добавляет точки и полигоны.
        count = obj.GetPolygonCount()
        obj.ResizeObject(obj.GetPointCount() + 4, count + 4)
        for k in range(4):
            obj.SetPolygon(count + k, CPolygon(0, 1, 2, 3))
        return True

    utils.SendModelingCommand = send_modeling_command
    c4d.utils = utils
    sys.modules['c4d.utils'] = utils

    c4d.StopAllThreads = lambda: None
    c4d.EventAdd = lambda: None
    c4d.DrawViews = lambda flags=0: None

    plugins = types.ModuleType('c4d.plugins')
    plugins.ToolData = object
    plugins.RegisterToolPlugin = lambda *args, **kwargs: True
    c4d.plugins = plugins
    sys.modules['c4d.plugins'] = plugins

    gui = types.ModuleType('c4d.gui')
    messages = []
    gui.MessageDialog = lambda text: messages.append(text)
    gui.messages = messages
    gui.SubDialog = object
    c4d.gui = gui
    sys.modules['c4d.gui'] = gui

    bitmaps = types.ModuleType('c4d.bitmaps')

    class BaseBitmap(object):
        def InitWith(self, path):
            return (0,)

    bitmaps.BaseBitmap = BaseBitmap
    c4d.bitmaps = bitmaps
    sys.modules['c4d.bitmaps'] = bitmaps

    documents = types.ModuleType('c4d.documents')
    active = {'doc': None}
    documents.GetActiveDocument = lambda: active['doc']
    documents.SetActiveDocument = lambda doc: active.__setitem__('doc', doc)
    c4d.documents = documents
    sys.modules['c4d.documents'] = documents

    sys.modules['c4d'] = c4d
    return c4d, documents, gui


def make_grid_scene():
    """Две квадратные заглушки, соединённые боковой стенкой — эталонный случай.

    Заглушки ориентированы «наружу» от общего объёма, поэтому мост между ними
    должен получить согласованные нормали без ручной правки.
    """
    points = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0),
              (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
              (-1, -1, 2), (1, -1, 2), (1, 1, 2), (-1, 1, 2),
              (-1, -1, 3), (1, -1, 3), (1, 1, 3), (-1, 1, 3)]
    faces = [(0, 1, 2, 3), (11, 10, 9, 8)]
    faces += [(i + 4, (i + 1) % 4 + 4, (i + 1) % 4, i) for i in range(4)]
    faces += [(8 + i, 8 + (i + 1) % 4, 12 + (i + 1) % 4, 12 + i) for i in range(4)]
    return points, faces


def build_object(points, faces, uv=True, weights=True, pins=()):
    c4d = sys.modules['c4d']
    obj = c4d.PolygonObject(len(points), len(faces))
    obj.SetAllPoints([Vector(*p) for p in points])
    for index, face in enumerate(faces):
        if len(face) == 3:
            obj.SetPolygon(index, CPolygon(face[0], face[1], face[2], face[2]))
        else:
            obj.SetPolygon(index, CPolygon(*face))
    if uv:
        tag = UVWTag(len(faces))
        for i in range(len(faces)):
            tag.SetSlow(i, Vector(i, 0, 0), Vector(i, 1, 0), Vector(i, 1, 1), Vector(i, 0, 1))
        selection = BaseSelect()
        for index in pins:
            selection.Select(index)
        tag.SetPinSelection(selection)
        obj.InsertTag(tag)
    if weights:
        tag = VariableTag(c4d.Tvertexmap, len(points))
        tag.SetAllHighlevelData([float(i) for i in range(len(points))])
        obj.InsertTag(tag)
    return obj
