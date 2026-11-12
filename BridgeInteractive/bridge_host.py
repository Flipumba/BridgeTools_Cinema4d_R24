# -*- coding: utf-8 -*-
"""Слой Cinema 4D: чтение объекта, разрешения, перенос данных, запись, Undo.

Только этот модуль импортирует c4d. Всё остальное работает с обычными
кортежами, поэтому геометрию, UV и веса можно проверять без хоста.
"""
import traceback

import c4d


class BridgeError(Exception):
    """Ошибка, текст которой можно показать пользователю как есть."""


# --------------------------------------------------------------------------
# Чтение объекта
# --------------------------------------------------------------------------
def read_object(obj, point_mode=False, strict=True):
    """Возвращает (points, faces, selected_polygons, selected_edges, snapshot).

    point_mode — режим «Точки»: выделенными рёбрами считаются рёбра сетки, оба
    конца которых выделены (так же Blender работает в режиме вершин).

    strict=True отклоняет объекты с N-гонами: собственный движок переписывает
    полигоны сам и повредил бы описание N-гонов. При strict=False N-гоны
    читаются как обычные треугольники и квады (внутренние рёбра N-гона —
    просто рёбра), чего достаточно для предпросмотра и для вызова встроенного
    Bridge, который сам корректно работает с N-гонами.
    """
    if obj is None:
        raise BridgeError('Нет активного объекта. Выберите полигональный объект.')
    if not obj.CheckType(c4d.Opolygon):
        raise BridgeError('Активный объект не полигональный. Выберите объект типа '
                          'Polygon и включите режим редактирования.')
    ngons = obj.GetNgonCount() if strict else 0
    if ngons:
        raise BridgeError(
            'Объект содержит N-гоны (%d). Python API Cinema 4D не даёт доступа к '
            'описанию N-гонов, поэтому собственный движок их не изменяет. '
            'Переключите «Движок» на «Встроенный Bridge Cinema 4D» — он работает '
            'с N-гонами — или разбейте N-гоны на треугольники и квады.' % ngons)

    points = [(p.x, p.y, p.z) for p in obj.GetAllPoints()]
    polygons = obj.GetAllPolygons()
    faces = []
    for p in polygons:
        if p.c == p.d:
            faces.append((p.a, p.b, p.c))
        else:
            faces.append((p.a, p.b, p.c, p.d))

    polygon_selection = obj.GetPolygonS()
    selected = set(i for i in range(len(faces)) if polygon_selection.IsSelected(i))

    edge_selection = obj.GetEdgeS()
    selected_edges = []
    if edge_selection is not None:
        for index, face in enumerate(faces):
            for slot, (a, b) in enumerate(edge_pairs(face)):
                if a != b and edge_selection.IsSelected(4 * index + slot):
                    selected_edges.append((a, b))

    if point_mode:
        point_selection = obj.GetPointS()
        chosen = set(i for i in range(len(points)) if point_selection.IsSelected(i))
        seen = set()
        selected_edges = []
        for face in faces:
            for a, b in edge_pairs(face):
                key = (min(a, b), max(a, b))
                if a != b and key not in seen and a in chosen and b in chosen:
                    seen.add(key)
                    selected_edges.append((a, b))

    snapshot = (tuple(points), tuple(tuple(f) for f in faces),
                frozenset(selected), tuple(sorted(selected_edges)))
    return points, faces, selected, selected_edges, snapshot


def edge_pairs(face):
    """Четыре «сырых» слота ребра, как их хранит Cinema 4D.

    У треугольника слот 3 вырожден (d == c), и редактор считает его ребром
    (c, a) — здесь повторяется это поведение.
    """
    if len(face) == 3:
        a, b, c = face
        return [(a, b), (b, c), (c, a), (c, a)]
    a, b, c, d = face
    return [(a, b), (b, c), (c, d), (d, a)]


# --------------------------------------------------------------------------
# Проверки, которые нельзя выполнить без Cinema 4D
# --------------------------------------------------------------------------
_SUPPORTED = None


def _supported_tag_types():
    global _SUPPORTED
    if _SUPPORTED is None:
        types = [c4d.Tphong, c4d.Tuvw, c4d.Ttexture, c4d.Tvertexmap]
        for name in ('Tpolygonselection', 'Tpointselection', 'Tedgeselection'):
            value = getattr(c4d, name, None)
            if value is not None:
                types.append(value)
        _SUPPORTED = tuple(types)
    return _SUPPORTED


def _field_enabled(tag):
    """True, если у тега включены поля (Fields)."""
    checks = (
        ('Tvertexmap', 'ID_TAGFIELD_ENABLE'),
        ('Tpointselection', 'POINTSELECTIONTAG_ENABLEFIELDS'),
        ('Tpolygonselection', 'POLYGONSELECTIONTAG_ENABLEFIELDS'),
        ('Tedgeselection', 'EDGESELECTIONTAG_ENABLEFIELDS'),
    )
    tag_type = tag.GetType()
    for name, flag in checks:
        candidate = getattr(c4d, name, None)
        if candidate is None or tag_type != candidate:
            continue
        flag_id = getattr(c4d, flag, None)
        if flag_id is None:
            continue
        try:
            return bool(tag[flag_id])
        except Exception:
            return False
    return False


def check_object_supported(obj):
    """Отклоняет объекты, которые нельзя изменить, не испортив данные.

    Единственное место, где принимается решение «поддерживается или нет».
    Всё неопознанное отклоняется с указанием причины: понятная ошибка лучше
    молча испорченной модели.
    """
    allowed = _supported_tag_types()
    unsupported = []
    for tag in obj.GetTags():
        if tag.GetType() not in allowed:
            unsupported.append(tag.GetName() or str(tag.GetType()))
            continue
        if _field_enabled(tag):
            raise BridgeError(
                'Тег «%s» управляется полями (Fields). Перенос значений такого '
                'тега на новую топологию не определён, поэтому операция отменена '
                'без изменения объекта.' % (tag.GetName() or 'без имени'))
    if unsupported:
        raise BridgeError(
            'На объекте есть теги, которые этот инструмент не умеет переносить '
            'без риска потери данных: %s. Операция отменена, объект не изменён.'
            % ', '.join(unsupported))
    return True


# --------------------------------------------------------------------------
# Снимок тегов до изменения
# --------------------------------------------------------------------------
def capture_tag_data(obj, old_face_count, old_point_count):
    """Считывает UV, веса и выделения до изменения объекта.

    Читать надо заранее: после ResizeObject содержимое тегов уже не описывает
    исходную топологию.
    """
    uv_entries = []
    weight_entries = []
    selection_entries = []
    for tag in obj.GetTags():
        tag_type = tag.GetType()
        if tag_type == c4d.Tuvw:
            count = tag.GetDataCount()
            if count != old_face_count:
                raise BridgeError('UV-тег «%s» имеет %d полигонов вместо %d. '
                                  'Операция отменена.'
                                  % (tag.GetName(), count, old_face_count))
            corners = []
            for i in range(count):
                slow = tag.GetSlow(i)
                corners.append((_triple(slow['a']), _triple(slow['b']),
                                _triple(slow['c']), _triple(slow['d'])))
            base = tag.GetPinSelection()
            pins = set(i for i in range(count * 4) if base and base.IsSelected(i))
            uv_entries.append((tag, corners, pins))
        elif tag_type == c4d.Tvertexmap:
            values = list(tag.GetAllHighlevelData())
            if len(values) != old_point_count:
                raise BridgeError('Vertex Map «%s» содержит %d значений вместо %d '
                                  'вершин. Операция отменена.'
                                  % (tag.GetName(), len(values), old_point_count))
            weight_entries.append((tag, values))

    for tag in obj.GetTags():
        tag_type = tag.GetType()
        if tag_type == getattr(c4d, 'Tpolygonselection', None):
            count = old_face_count
        elif tag_type == getattr(c4d, 'Tpointselection', None):
            count = old_point_count
        elif tag_type == getattr(c4d, 'Tedgeselection', None):
            count = old_face_count * 4
        else:
            continue
        base = tag.GetBaseSelect()
        if base is None:
            continue
        selection_entries.append((tag, tag_type,
                                  set(i for i in range(count) if base.IsSelected(i))))

    hidden = []
    for getter, count in (('GetPointH', old_point_count),
                          ('GetPolygonH', old_face_count),
                          ('GetEdgeH', old_face_count * 4)):
        fn = getattr(obj, getter, None)
        if fn is None:
            continue
        base = fn()
        if base is None:
            continue
        hidden.append((getter, set(i for i in range(count) if base.IsSelected(i))))

    return {'uv': uv_entries, 'weights': weight_entries,
            'selections': selection_entries, 'hidden': hidden}


def _triple(v):
    return (float(v.x), float(v.y), float(v.z))


# --------------------------------------------------------------------------
# Расчёт переноса
# --------------------------------------------------------------------------
def compute_transfer(plan, tag_data):
    """Считает всё, что будет записано в теги. Чистая функция поверх plan."""
    import bridge_data

    result = {'uv': [], 'weights': [], 'selections': [], 'hidden': []}

    for tag, corners, pins in tag_data['uv']:
        new_corners = bridge_data.transfer_uvs(plan, corners)
        # Сохранённые полигоны в объекте переезжают на новые индексы, поэтому
        # их UV надо переписать, а не оставить «на месте»: иначе данные UV
        # окажутся привязаны к чужим граням. ResizeObject этого не делает.
        full = [corners[old] for old in plan.retained] + list(new_corners)
        if len(full) != len(plan.faces):
            raise BridgeError('Перенос UV дал %d записей вместо %d полигонов. '
                              'Операция отменена.' % (len(full), len(plan.faces)))
        result['uv'].append((tag, full,
                             bridge_data.remap_uv_pins(pins, plan.retained)))

    for tag, values in tag_data['weights']:
        mapped = bridge_data.remap_point_values(plan, values)
        if plan.merge_pairs:
            mapped = bridge_data.merge_values(plan, mapped)
        if len(mapped) != len(plan.points):
            raise BridgeError('Перенос весов дал %d значений вместо %d вершин. '
                              'Операция отменена.' % (len(mapped), len(plan.points)))
        result['weights'].append((tag, mapped))

    for tag, tag_type, selected in tag_data['selections']:
        if tag_type == getattr(c4d, 'Tpolygonselection', None):
            mapped = bridge_data.remap_polygon_selection(selected, plan.retained)
        elif tag_type == getattr(c4d, 'Tpointselection', None):
            mapped = bridge_data.remap_point_selection(selected, plan.point_map)
        else:
            mapped = bridge_data.remap_edge_selection(selected, plan.old_faces,
                                                      plan.faces, plan.point_map)
        result['selections'].append((tag, mapped))

    for getter, selected in tag_data['hidden']:
        if getter == 'GetPointH':
            mapped = bridge_data.remap_point_selection(selected, plan.point_map)
        elif getter == 'GetPolygonH':
            mapped = bridge_data.remap_polygon_selection(selected, plan.retained)
        else:
            mapped = bridge_data.remap_edge_selection(selected, plan.old_faces,
                                                      plan.faces, plan.point_map)
        result['hidden'].append((getter, mapped))
    return result


# --------------------------------------------------------------------------
# Запись результата — одна транзакция Undo
# --------------------------------------------------------------------------
def apply_plan(doc, obj, plan, transfer):
    """Записывает план в объект одной операцией Undo.

    При ошибке откатывает документ, поэтому объект не может остаться в
    половинчатом состоянии.
    """
    if doc is None or obj is None:
        raise BridgeError('Нет документа или объекта для применения моста.')

    if not doc.StartUndo():
        raise BridgeError('Cinema 4D отказал в создании операции Undo. '
                          'Изменения не применены.')
    registered = False
    try:
        if not doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj):
            raise BridgeError('Не удалось зарегистрировать объект в Undo. '
                              'Изменения не применены.')
        registered = True
        for tag, _uvs, _pins in transfer['uv']:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, tag)
        for tag, _values in transfer['weights']:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, tag)
        for tag, _mapped in transfer['selections']:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, tag)

        _write_geometry(obj, plan)
        _write_uv(plan, transfer)
        _write_weights(transfer)
        _write_selections(transfer)
        _write_hidden(obj, transfer)
        _write_view_selection(obj, plan)

        obj.Message(c4d.MSG_UPDATE)
        for tag, _uvs, _pins in transfer['uv']:
            tag.Message(c4d.MSG_UPDATE)
        for tag, _values in transfer['weights']:
            tag.Message(c4d.MSG_UPDATE)
        for tag, _mapped in transfer['selections']:
            tag.Message(c4d.MSG_UPDATE)
        doc.EndUndo()
        return True
    except Exception as error:
        try:
            doc.EndUndo()
        except Exception:
            pass
        if registered:
            try:
                doc.DoUndo()
            except Exception:
                traceback.print_exc()
        raise BridgeError(str(error))


def _write_geometry(obj, plan):
    if not obj.ResizeObject(len(plan.points), len(plan.faces)):
        raise BridgeError('Cinema 4D не позволил изменить размер объекта.')
    obj.SetAllPoints([c4d.Vector(p[0], p[1], p[2]) for p in plan.points])
    for index, face in enumerate(plan.faces):
        if len(face) == 3:
            obj.SetPolygon(index, c4d.CPolygon(face[0], face[1], face[2], face[2]))
        else:
            obj.SetPolygon(index, c4d.CPolygon(face[0], face[1], face[2], face[3]))


def _write_uv(plan, transfer):
    for tag, corners, pins in transfer['uv']:
        if tag.GetDataCount() != len(plan.faces):
            raise BridgeError('Cinema 4D не изменил размер UV-тега до %d полигонов.'
                              % len(plan.faces))
        for index in range(len(plan.faces)):
            corner = corners[index]
            tag.SetSlow(index, c4d.Vector(*corner[0]), c4d.Vector(*corner[1]),
                        c4d.Vector(*corner[2]), c4d.Vector(*corner[3]))
        selection = c4d.BaseSelect()
        if selection is not None:
            for index in sorted(pins):
                selection.Select(index)
            tag.SetPinSelection(selection)


def _write_weights(transfer):
    for tag, values in transfer['weights']:
        tag.SetAllHighlevelData(values)


def _write_selections(transfer):
    for tag, mapped in transfer['selections']:
        base = tag.GetBaseSelect()
        if base is None:
            continue
        base.DeselectAll()
        for index in sorted(mapped):
            base.Select(index)


def _write_hidden(obj, transfer):
    """Восстанавливает скрытые компоненты (скрытые точки, полигоны, рёбра)."""
    for getter, mapped in transfer['hidden']:
        fn = getattr(obj, getter, None)
        if fn is None:
            continue
        base = fn()
        if base is None:
            continue
        base.DeselectAll()
        for index in sorted(mapped):
            base.Select(index)


def _write_view_selection(obj, plan):
    polygon_selection = obj.GetPolygonS()
    if polygon_selection is not None:
        polygon_selection.DeselectAll()
        for index in plan.new_faces:
            polygon_selection.Select(index)
    point_selection = obj.GetPointS()
    if point_selection is not None:
        point_selection.DeselectAll()
    edge_selection = obj.GetEdgeS()
    if edge_selection is not None:
        edge_selection.DeselectAll()


# --------------------------------------------------------------------------
# Дешёвая проверка актуальности
# --------------------------------------------------------------------------
class Signature(object):
    """Лёгкая подпись состояния объекта для проверки актуальности снимка.

    Полный read_object на каждом движении мыши недопустим: на плотной сетке
    это десятки тысяч операций за кадр. Здесь сравниваются счётчики, счётчики
    выделения и идентичность объекта/документа; полная сверка выполняется
    перед применением. Счётчики выделения нужны, чтобы предпросмотр
    обновлялся, когда пользователь меняет выделение, не трогая геометрию.
    """

    __slots__ = ('point_count', 'polygon_count', 'doc_id', 'selection', 'mode')

    def __init__(self, obj, doc):
        self.point_count = obj.GetPointCount()
        self.polygon_count = obj.GetPolygonCount()
        self.doc_id = id(doc)
        self.selection = self._selection(obj)
        self.mode = doc.GetMode()

    @staticmethod
    def _selection(obj):
        counts = []
        for getter in (obj.GetPointS, obj.GetEdgeS, obj.GetPolygonS):
            select = getter()
            counts.append(select.GetCount() if select is not None else 0)
        return tuple(counts)

    def matches(self, obj, doc):
        return (self.point_count == obj.GetPointCount()
                and self.polygon_count == obj.GetPolygonCount()
                and self.doc_id == id(doc)
                and self.mode == doc.GetMode()
                and self.selection == self._selection(obj))
