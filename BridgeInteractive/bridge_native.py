# -*- coding: utf-8 -*-
"""Запуск встроенного Bridge Cinema 4D (ID_MODELING_BRIDGE_TOOL).

Зачем это нужно. Встроенный Bridge — код самой Cinema 4D: он корректно работает
с N-гонами, тегами (UV, Vertex Map, выделения, Phong и любыми другими), правилами
Undo и точками, которых Python не видит. Собственный движок плагина переписывает
полигоны сам и поэтому вынужден отказываться от всего, что не умеет переносить.
Здесь плагин берёт на себя интерфейс (автоподбор соответствия вершин, предпросмотр,
параметры), а топологическую работу и теги отдаёт встроенному инструменту.

Что передаётся в команду (по документации Maxon, toolbridge.h):
  ELEMENT1/2 — по одному выделенному полигону (ребру) в каждом острове;
  ELEMENT3/4 — вершины, которые пользователь протянул бы мышью: пара,
               которую встроенный Bridge соединяет друг с другом;
  FIRST/SECOND_SELECT_ONLY — режим «острова»: инструмент сам обходит
               выделение и соединяет контуры целиком.
"""
import c4d
from c4d import utils

from bridge_host import BridgeError, edge_pairs
from bridge_topology import Mesh, collect_islands, ordered_chains

# Без этих имён встроенный Bridge из Python в режиме островов не запустить.
REQUIRED = (
    'ID_MODELING_BRIDGE_TOOL',
    'MDATA_BRIDGE_ELEMENT1', 'MDATA_BRIDGE_ELEMENT2',
    'MDATA_BRIDGE_ELEMENT3', 'MDATA_BRIDGE_ELEMENT4',
    'MDATA_BRIDGE_OBJINDEX1', 'MDATA_BRIDGE_OBJINDEX2',
    'MDATA_BRIDGE_SUBDIVISION',
    'MDATA_BRIDGE_FIRST_SELECT_ONLY', 'MDATA_BRIDGE_SECOND_SELECT_ONLY',
    'MODELINGCOMMANDMODE_POLYGONSELECTION', 'MODELINGCOMMANDMODE_EDGESELECTION',
)

# Эти параметры используются, если версия Cinema 4D их знает.
OPTIONAL = (
    'MDATA_BRIDGE_OBJINDEX3', 'MDATA_BRIDGE_OBJINDEX4',
    'MDATA_BRIDGE_TENSION', 'MDATA_BRIDGE_BOTH_MODE', 'MDATA_BRIDGE_BOTH_FLIP',
    'MDATA_BRIDGE_DELETE',
)

CURVE_MODES = ('Surface', 'Normal', 'Surface Average', 'Normal Average')
_CURVE_MODE_NAMES = ('MDATA_BRIDGE_MODE_SURFACE', 'MDATA_BRIDGE_MODE_NORMAL',
                     'MDATA_BRIDGE_MODE_SURFACE_AVERAGE', 'MDATA_BRIDGE_MODE_NORMAL_AVERAGE')


class NativeParams(object):
    """Параметры, которые понимает встроенный Bridge."""

    __slots__ = ('cuts', 'twist', 'tension', 'curve_mode', 'flip', 'delete')

    def __init__(self, cuts=0, twist=0, tension=0.0, curve_mode=0, flip=False,
                 delete=True):
        self.cuts = max(0, int(cuts))
        self.twist = int(twist)
        self.tension = max(-100.0, min(100.0, float(tension)))
        self.curve_mode = max(0, min(3, int(curve_mode)))
        self.flip = bool(flip)
        self.delete = bool(delete)


def availability():
    """(отсутствующие обязательные, отсутствующие необязательные) имена."""
    required = [name for name in REQUIRED if not hasattr(c4d, name)]
    optional = [name for name in OPTIONAL if not hasattr(c4d, name)]
    return required, optional


def is_available():
    return not availability()[0]


def describe_availability():
    """Строка для консоли: что поддерживает эта версия Cinema 4D."""
    required, optional = availability()
    if required:
        return ('встроенный Bridge из Python недоступен, нет констант: %s'
                % ', '.join(required))
    if optional:
        return ('встроенный Bridge доступен; не поддерживаются параметры: %s'
                % ', '.join(optional))
    return 'встроенный Bridge доступен, все параметры поддерживаются'


# --------------------------------------------------------------------------
# Перевод якорных вершин в индексы элементов
# --------------------------------------------------------------------------
def _shift(loop, vertex, steps):
    index = loop.index(vertex)
    return loop[(index + steps) % len(loop)]


def _polygon_with_vertex(faces, polygons, vertex):
    for index in sorted(polygons):
        if vertex in faces[index]:
            return index
    return None


def _selected_edge_index(obj, faces, vertices, vertex):
    """Индекс выделенного ребра цепочки, содержащего вершину."""
    selection = obj.GetEdgeS()
    members = set(vertices)
    for index in range(len(faces) * 4):
        if not selection.IsSelected(index):
            continue
        a, b = edge_pairs(faces[index // 4])[index % 4]
        if a != b and vertex in (a, b) and a in members and b in members:
            return index
    return None


def _select_edges(obj, faces, edges):
    """Выделяет рёбра сетки в самом объекте (нужно в режиме «Точки»)."""
    wanted = set((min(a, b), max(a, b)) for a, b in edges)
    selection = obj.GetEdgeS()
    selection.DeselectAll()
    for index, face in enumerate(faces):
        for slot, (a, b) in enumerate(edge_pairs(face)):
            if a != b and (min(a, b), max(a, b)) in wanted:
                selection.Select(4 * index + slot)


def resolve_elements(obj, source, snapshot, anchors, twist, point_mode):
    """Возвращает (режим_команды, e1, e2, v1, v2) для встроенного Bridge."""
    points, faces, selected, edges = snapshot[0], snapshot[1], snapshot[2], snapshot[3]
    mesh = Mesh(points, faces)
    va, vb = anchors

    if source == 0:
        islands = collect_islands(mesh, selected, allow_many=False)
        ia = _owner([i.loop for i in islands], va)
        ib = _owner([i.loop for i in islands], vb)
        if ia is None or ib is None or ia == ib:
            raise BridgeError('Опорные вершины должны лежать на границах двух разных '
                              'групп граней.')
        loop_b = islands[ib].loop
        if twist:
            vb = _shift(loop_b, vb, twist)
        e1 = _polygon_with_vertex(faces, islands[ia].faces, va)
        e2 = _polygon_with_vertex(faces, islands[ib].faces, vb)
        if e1 is None or e2 is None:
            raise BridgeError('Не найден полигон выделения для опорной вершины.')
        return c4d.MODELINGCOMMANDMODE_POLYGONSELECTION, e1, e2, va, vb

    chains = ordered_chains(edges)
    ia = _owner([c.vertices for c in chains], va)
    ib = _owner([c.vertices for c in chains], vb)
    if ia is None or ib is None or ia == ib:
        raise BridgeError('Опорные вершины должны лежать на двух разных цепочках рёбер.')
    if twist and chains[ib].closed:
        vb = _shift(list(chains[ib].vertices), vb, twist)
    if point_mode:
        _select_edges(obj, faces, edges)
    e1 = _selected_edge_index(obj, faces, chains[ia].vertices, va)
    e2 = _selected_edge_index(obj, faces, chains[ib].vertices, vb)
    if e1 is None or e2 is None:
        raise BridgeError('Не найдено выделенное ребро для опорной вершины.')
    return c4d.MODELINGCOMMANDMODE_EDGESELECTION, e1, e2, va, vb


def _owner(loops, vertex):
    for index, loop in enumerate(loops):
        if vertex in loop:
            return index
    return None


# --------------------------------------------------------------------------
# Настройки и запуск
# --------------------------------------------------------------------------
def build_settings(obj, e1, e2, v1, v2, params):
    bc = c4d.BaseContainer()
    for name in ('MDATA_BRIDGE_OBJINDEX1', 'MDATA_BRIDGE_OBJINDEX2',
                 'MDATA_BRIDGE_OBJINDEX3', 'MDATA_BRIDGE_OBJINDEX4'):
        ident = getattr(c4d, name, None)
        if ident is not None:
            bc[ident] = obj
    bc[c4d.MDATA_BRIDGE_ELEMENT1] = int(e1)
    bc[c4d.MDATA_BRIDGE_ELEMENT2] = int(e2)
    bc[c4d.MDATA_BRIDGE_ELEMENT3] = int(v1)
    bc[c4d.MDATA_BRIDGE_ELEMENT4] = int(v2)
    bc.SetBool(c4d.MDATA_BRIDGE_FIRST_SELECT_ONLY, True)
    bc.SetBool(c4d.MDATA_BRIDGE_SECOND_SELECT_ONLY, True)
    bc[c4d.MDATA_BRIDGE_SUBDIVISION] = int(params.cuts)

    ident = getattr(c4d, 'MDATA_BRIDGE_TENSION', None)
    if ident is not None:
        bc[ident] = float(params.tension) / 100.0
    ident = getattr(c4d, 'MDATA_BRIDGE_BOTH_MODE', None)
    if ident is not None:
        bc[ident] = getattr(c4d, _CURVE_MODE_NAMES[params.curve_mode], params.curve_mode)
    ident = getattr(c4d, 'MDATA_BRIDGE_BOTH_FLIP', None)
    if ident is not None:
        bc.SetBool(ident, bool(params.flip))
    ident = getattr(c4d, 'MDATA_BRIDGE_DELETE', None)
    if ident is not None:
        bc.SetBool(ident, bool(params.delete))
    return bc


def _fingerprint(obj):
    polygons = tuple((p.a, p.b, p.c, p.d) for p in obj.GetAllPolygons())
    return obj.GetPointCount(), len(polygons), hash(polygons)


def apply_native(doc, obj, source, snapshot, anchors, params, point_mode=False):
    """Вызывает встроенный Bridge одной операцией Undo. Возвращает сообщение."""
    required, _ = availability()
    if required:
        raise BridgeError('Эта версия Cinema 4D не открывает встроенный Bridge для '
                          'Python в режиме островов (нет: %s). Выберите «Собственный» '
                          'движок.' % ', '.join(required))

    command_mode, e1, e2, v1, v2 = resolve_elements(
        obj, source, snapshot, anchors, params.twist, point_mode)
    settings = build_settings(obj, e1, e2, v1, v2, params)

    before = _fingerprint(obj)
    doc.StartUndo()
    doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
    try:
        ok = utils.SendModelingCommand(command=c4d.ID_MODELING_BRIDGE_TOOL,
                                       list=[obj], mode=command_mode,
                                       bc=settings, doc=doc)
    except Exception as error:
        doc.EndUndo()
        doc.DoUndo()
        raise BridgeError('Встроенный Bridge вернул ошибку: %s' % error)
    doc.EndUndo()

    if not ok or _fingerprint(obj) == before:
        doc.DoUndo()
        raise BridgeError(
            'Встроенный Bridge ничего не построил. Проверьте, что выделены две '
            'группы граней (или две цепочки рёбер) без пересечений, и попробуйте '
            'задать опорные вершины вручную.')
    obj.Message(c4d.MSG_UPDATE)
    return 'мост создан встроенным Bridge Cinema 4D.'
