# -*- coding: utf-8 -*-
"""Перенос UV, весов вершин и выделений на результат операции.

Модуль не обращается к Cinema 4D: на вход идут подготовленные словари, на
выходе — значения, готовые к записи. Поэтому перенос тестируется без хоста.

Формат UV — четыре тройки (a, b, c, d) на полигон, как в UVWTag.
"""
from bridge_math import EPS, mix, edge_key, edges_of


# --------------------------------------------------------------------------
# UV
# --------------------------------------------------------------------------
def _uv_table(plan, uvs, excluded):
    """«Ребро -> UV его концов» по сохраняемым полигонам.

    Нужна, чтобы новый полигон унаследовал UV именно той стороны шва, с
    которой он стыкуется: у одной вершины может быть несколько UV.
    """
    table = {}
    for index, face in enumerate(plan.old_faces):
        if index in excluded:
            continue
        corners = uvs[index]
        pairs = edges_of(list(face), True)
        for j, (a, b) in enumerate(pairs):
            table.setdefault(edge_key(a, b), []).append(
                (a, b, corners[j % len(corners)], corners[(j + 1) % len(corners)]))
    return table


def _vertex_uv(table, vertex, fallback):
    """UV вершины, взятая с той стороны шва, где ребро действительно общее."""
    for values in table.values():
        for a, b, ua, ub in values:
            if a == vertex:
                return ua
            if b == vertex:
                return ub
    return fallback


def _sample_track(track, param):
    if not track:
        return None
    return min(track, key=lambda item: abs(item[1] - param))[0]


def transfer_uvs(plan, uvs):
    """UV для новых полигонов в порядке plan.new_faces."""
    if not plan.new_faces or not plan.rings:
        return []
    excluded = set(plan.removed_faces)
    table = _uv_table(plan, uvs, excluded)

    first = plan.rings[0]
    last = plan.rings[-1]
    track_first = [(_vertex_uv(table, v, (p, 0.0, 0.0)), p)
                   for v, p in zip(first['indices'], first['params'])]
    track_last = [(_vertex_uv(table, v, (p, 1.0, 0.0)), p)
                  for v, p in zip(last['indices'], last['params'])]

    rim_uv = {}
    for level in plan.rings:
        t = level['level']
        for vertex, param in zip(level['indices'], level['params']):
            if level is plan.rings[0]:
                rim_uv[vertex] = _vertex_uv(table, vertex, (param, 0.0, 0.0))
            elif level is plan.rings[-1]:
                rim_uv[vertex] = _vertex_uv(table, vertex, (param, 1.0, 0.0))
            else:
                ua = _sample_track(track_first, param)
                ub = _sample_track(track_last, param)
                if ua is None or ub is None:
                    rim_uv[vertex] = (param, t, 0.0)
                else:
                    rim_uv[vertex] = mix(ua, ub, t)

    result = []
    for index in plan.new_faces:
        face = plan.faces[index]
        n = len(face)
        corners = [rim_uv.get(v, (i / float(n), 0.0, 0.0)) for i, v in enumerate(face)]
        if n == 3:
            corners.append(corners[-1])
        result.append(tuple(corners))
    return result


def remap_uv_pins(old_pins, retained):
    """Закреплённые UV-точки. Индекс точки: полигон * 4 + угол."""
    mapping = {}
    for new_index, old_index in enumerate(retained):
        mapping[old_index] = new_index
    out = set()
    for index in old_pins:
        face, corner = divmod(index, 4)
        if face in mapping:
            out.add(4 * mapping[face] + corner)
    return out


def widen(uvs, count, default=((0., 0., 0.), (1., 0., 0.), (1., 1., 0.), (0., 1., 0.))):
    out = list(uvs)
    while len(out) < count:
        out.append(default)
    return out[:count]


# --------------------------------------------------------------------------
# Веса вершин (Vertex Maps)
# --------------------------------------------------------------------------
def remap_point_values(plan, values):
    """Значения по вершинам для всей новой сетки.

    * сохранённые вершины переносятся через point_map;
    * вершины внутренних уровней моста интерполируются по параметру;
    * при Merge слитая вершина получает смешанное значение.
    """
    count = len(plan.points)
    out = [0.0] * count

    for old_index, value in enumerate(values):
        new_index = plan.point_map.get(old_index)
        if new_index is not None and 0 <= new_index < count:
            out[new_index] = float(value)

    if len(plan.rings) < 2:
        return out

    track_first = _track(plan, plan.rings[0], values)
    track_last = _track(plan, plan.rings[-1], values)

    for vertex in plan.rings[0]['indices'] + plan.rings[-1]['indices']:
        if vertex < count:
            out[vertex] = _value_at(plan, vertex, values)

    for level in plan.rings[1:-1]:
        t = level['level']
        for vertex, param in zip(level['indices'], level['params']):
            if vertex >= count:
                continue
            a = _sample_track(track_first, param) or 0.0
            b = _sample_track(track_last, param) or 0.0
            out[vertex] = a + (b - a) * t
    return out


def _track(plan, level, values):
    return [(_value_at(plan, vertex, values), param)
            for vertex, param in zip(level['indices'], level['params'])]


def _value_at(plan, vertex, values):
    old = plan.reverse_point_map.get(vertex)
    if old is None or not (0 <= old < len(values)):
        return 0.0
    return float(values[old])


def merge_values(plan, values):
    """Смешивает значения слитых вершин по фактору Merge."""
    out = list(values)
    for source_new, (target_new, factor) in plan.merge_pairs.items():
        if target_new < len(out) and source_new < len(out):
            out[target_new] = out[target_new] * (1.0 - factor) + out[source_new] * factor
    return out


# --------------------------------------------------------------------------
# Выделения
# --------------------------------------------------------------------------
def remap_polygon_selection(selected, retained):
    target = {}
    for new_index, old_index in enumerate(retained):
        target[old_index] = new_index
    return set(target[i] for i in selected if i in target)


def remap_point_selection(selected, point_map):
    out = set()
    for old in selected:
        new = point_map.get(old)
        if new is not None:
            out.add(new)
    return out


def remap_edge_selection(selected_raw, old_faces, new_faces, point_map):
    """Выделение рёбер переносится по парам вершин, а не по сырым индексам.

    Сырой индекс ребра (полигон * 4 + слот) после удаления граней указывает
    на другой полигон, поэтому ребро ищется по его концам.
    """
    wanted = set()
    for index in selected_raw:
        face, slot = divmod(index, 4)
        if face < 0 or face >= len(old_faces):
            continue
        pairs = edges_of(list(old_faces[face]), True)
        if slot >= len(pairs):
            continue
        a, b = pairs[slot]
        if a == b:
            continue
        na = point_map.get(a)
        nb = point_map.get(b)
        if na is None or nb is None or na == nb:
            continue
        wanted.add(edge_key(na, nb))
    out = set()
    for index, face in enumerate(new_faces):
        for slot, (a, b) in enumerate(edges_of(list(face), True)):
            if slot >= 4:
                break
            if a != b and edge_key(a, b) in wanted:
                out.add(index * 4 + slot)
    return out
