# -*- coding: utf-8 -*-
"""Проверка результата операции до записи в объект.

Валидатор намеренно не ищет глобальные самопересечения всей сетки: это
дорого и на реальных моделях даёт ложные срабатывания. Проверяются локальные
свойства затронутых полигонов плюс общая манифолдность рёбер.
"""
from collections import defaultdict

from bridge_math import EPS, sub, dot, cross, length, edge_key, edges_of


class ValidationError(ValueError):
    pass


def check_plan(plan):
    """Бросает ValidationError, если результат нельзя записывать в объект."""
    points, faces = plan.points, plan.faces
    if not faces:
        raise ValidationError('Операция удалила бы все полигоны объекта.')
    n = len(points)
    for face in faces:
        if len(face) not in (3, 4):
            raise ValidationError('В результат попал полигон с %d вершинами.' % len(face))
        if len(set(face)) != len(face):
            raise ValidationError('Полигон с повторяющейся вершиной: результат отменён.')
        for v in face:
            if not isinstance(v, int) or v < 0 or v >= n:
                raise ValidationError('Полигон ссылается на несуществующую вершину.')

    counts = defaultdict(int)
    for face in faces:
        for a, b in edges_of(list(face), True):
            counts[edge_key(a, b)] += 1
    non_manifold = sum(1 for v in counts.values() if v > 2)
    if non_manifold:
        raise ValidationError(
            'Результат содержал бы %d рёбер с тремя и более полигонами. '
            'Такая сетка неманифолдна, поэтому операция отменена.' % non_manifold)

    # Дубликаты ищем только среди новых: у исходной модели могут быть свои
    # особенности, которые инструмент не обязан исправлять.
    seen = {}
    for index in plan.new_faces:
        key = _canonical(faces[index])
        if key in seen:
            raise ValidationError('Мост создаёт дублирующийся полигон '
                                  '(совпадает с %d).' % seen[key])
        seen[key] = index

    degenerate = [index for index in plan.new_faces
                  if _is_degenerate([points[v] for v in faces[index]])]
    if degenerate:
        raise ValidationError(
            'Мост создаёт вырожденные полигоны нулевой площади (%d шт.). '
            'Измените число разрезов, сдвиг или положение слияния.' % len(degenerate))

    flipped = _flipped_new_faces(plan)
    if flipped:
        raise ValidationError(
            'Мост создаёт полигоны с направлением, противоположным соседним (%d шт.). '
            'Обычно это значит, что направления граней вдоль контура несогласованы.'
            % len(flipped))
    return True


def _canonical(face):
    f = tuple(face)
    r = tuple(reversed(f))
    variants = [f[i:] + f[:i] for i in range(len(f))] + [r[i:] + r[:i] for i in range(len(r))]
    return min(variants)


def _is_degenerate(vertices, relative=1e-9):
    """Полигон вырожден, если у него нет площади при заметном размере.

    Абсолютный порог бесполезен: модели бывают и в миллиметрах, и в
    километрах. Поэтому площадь сравнивается с квадратом самого длинного ребра.
    """
    longest = 0.0
    shortest = float('inf')
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        d = length(sub(b, a))
        longest = max(longest, d)
        shortest = min(shortest, d)
    if longest <= EPS:
        return True
    if shortest <= longest * relative:
        return True
    origin = vertices[0]
    area2 = 0.0
    for i in range(1, len(vertices) - 1):
        area2 = max(area2, length(cross(sub(vertices[i], origin),
                                        sub(vertices[i + 1], origin))))
    return area2 <= longest * longest * relative


def _flipped_new_faces(plan):
    """Новые грани, чьё ребро идёт в ту же сторону, что и у сохранённого соседа.

    Для согласованной сетки два полигона на общем ребре обходят его в
    противоположных направлениях. Совпадение направления означает вывернутую
    грань.

    plan.retained хранит СТАРЫЕ индексы, а в новом списке уцелевшие полигоны
    идут первыми в том же порядке, поэтому их новые индексы — 0..N-1.
    """
    directed = {}
    for index in range(len(plan.retained)):
        face = plan.faces[index]
        for a, b in edges_of(list(face), True):
            directed[edge_key(a, b)] = (a, b, index)
    bad = []
    for index in plan.new_faces:
        face = plan.faces[index]
        for a, b in edges_of(list(face), True):
            entry = directed.get(edge_key(a, b))
            if entry is None:
                continue
            if (entry[0], entry[1]) == (a, b):
                bad.append(index)
                break
    return bad


def summarize(plan):
    return ('режим=%(mode)s полигонов+%(nf)d точек+%(np)d удалено=%(rm)d'
            % {'mode': plan.mode, 'nf': len(plan.new_faces),
               'np': len(plan.points) - plan.old_point_count,
               'rm': len(plan.removed_faces)})
