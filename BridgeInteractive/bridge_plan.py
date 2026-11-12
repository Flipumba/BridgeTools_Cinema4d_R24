# -*- coding: utf-8 -*-
"""Планировщик операции моста — единственный источник истины.

Предпросмотр, отрисовка и применение читают один и тот же Plan, поэтому они
не могут разойтись между собой. Обращений к Cinema 4D здесь нет.

Почему цепочки граней ограничены
--------------------------------
Кромка группы граней — это рёбра, каждое из которых уже делится с
сохраняемым полигоном сетки. Один мост добавляет к такому ребру ровно один
полигон, и получается два полигона на ребро — корректно. Последовательное
соединение P1→P2→P3 использует кромку P2 дважды и даёт три полигона на
ребро, то есть неманифолдную сетку.

Blender допускает цепочку потому, что работает с одномерными петлями рёбер,
у которых кромка свободна. Поэтому здесь:
  * цепочки и замыкание последовательности реализованы для цепочек рёбер;
  * для групп граней цепочка разрешена только если остаётся манифолдной,
    иначе операция отклоняется с объяснением, а не портит модель молча.
"""
from collections import defaultdict

from bridge_math import (EPS, add, sub, mul, dot, length, unit, mix, edge_key,
                         polygon_normal, loop_center, edges_of, sample_contour,
                         rim_tangents, cubic_surface_point, profile_envelope,
                         path_frames, path_point, mat_transpose, rotate_axis,
                         rotate_to, PROFILE_SHAPES)
from bridge_topology import (Mesh, collect_islands, disjoint_loops, ordered_chains,
                             chain_pairs, chain_is_free, normalize_face)

INTERPOLATIONS = ('LINEAR', 'PATH', 'SURFACE')
MAX_CUTS = 512


class BridgeOptions(object):
    """Параметры моста. Значения молча нормализуются, ошибок конструктор не бросает."""

    __slots__ = ('cuts', 'twist', 'smooth', 'profile', 'angle', 'interpolation',
                 'merge', 'merge_factor', 'profile_shape')

    def __init__(self, cuts=0, twist=0, smooth=0.0, profile=0.0, angle=0.0,
                 interpolation='LINEAR', merge=False, merge_factor=0.5,
                 profile_shape='SMOOTH'):
        try:
            cuts = int(cuts)
        except (TypeError, ValueError):
            cuts = 0
        self.cuts = max(0, min(MAX_CUTS, cuts))
        try:
            self.twist = int(twist)
        except (TypeError, ValueError):
            self.twist = 0
        self.smooth = _safe_float(smooth, 0.0, 0.0, 1000.0)
        self.profile = _safe_float(profile, 0.0, -100.0, 100.0)
        self.angle = _safe_float(angle, 0.0, -360.0, 360.0)
        self.interpolation = interpolation if interpolation in INTERPOLATIONS else 'LINEAR'
        self.merge = bool(merge)
        self.merge_factor = _safe_float(merge_factor, 0.5, 0.0, 1.0)
        self.profile_shape = profile_shape if profile_shape in PROFILE_SHAPES else 'SMOOTH'

    def replace(self, **kwargs):
        data = dict(cuts=self.cuts, twist=self.twist, smooth=self.smooth,
                    profile=self.profile, angle=self.angle,
                    interpolation=self.interpolation, merge=self.merge,
                    merge_factor=self.merge_factor, profile_shape=self.profile_shape)
        data.update(kwargs)
        return BridgeOptions(**data)

    def key(self):
        return (self.cuts, self.twist, round(self.smooth, 6), round(self.profile, 6),
                round(self.angle, 6), self.interpolation, self.merge,
                round(self.merge_factor, 6), self.profile_shape)


def _safe_float(value, default, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value != value:  # NaN
        return default
    return max(low, min(high, value))


class Plan(object):
    """Результат операции.

    points / faces        — полное новое содержимое объекта
    new_faces             — индексы созданных полигонов
    removed_faces         — индексы исходных полигонов, которые удаляются
    retained              — «новый индекс -> старый индекс» для сохранённых граней;
                            сохранённые грани всегда идут первыми, в исходном порядке
    point_map             — «старый индекс -> новый индекс, или None»
    rings                 — уровни моста для переноса UV и весов
    merge_pairs           — «новая слитая вершина -> (цель, фактор)»
    """

    __slots__ = ('points', 'faces', 'new_faces', 'removed_faces', 'retained',
                 'point_map', 'rings', 'warnings', 'old_point_count', 'mode',
                 'face_origins', 'old_points', 'old_faces', 'reverse_point_map',
                 'merge_pairs')

    def __init__(self, points, faces, new_faces, removed_faces, retained, point_map,
                 rings, old_point_count, mode, warnings=None, face_origins=None,
                 old_points=None, old_faces=None, reverse_point_map=None):
        self.points = points
        self.faces = faces
        self.new_faces = list(new_faces)
        self.removed_faces = list(removed_faces)
        self.retained = list(retained)
        self.point_map = point_map
        self.rings = rings
        self.old_point_count = old_point_count
        self.mode = mode
        self.warnings = list(warnings or [])
        self.face_origins = list(face_origins or [])
        self.old_points = list(old_points or [])
        self.old_faces = list(old_faces or [])
        if reverse_point_map is None:
            reverse_point_map = {}
            for old, new in point_map.items():
                if new is not None:
                    reverse_point_map[new] = old
        self.reverse_point_map = dict(reverse_point_map)
        self.merge_pairs = {}

    @property
    def is_noop(self):
        return not self.new_faces and not self.removed_faces


# --------------------------------------------------------------------------
# Построитель результата
# --------------------------------------------------------------------------
class _Builder(object):
    def __init__(self, mesh, removed_faces):
        self.mesh = mesh
        self.removed = set(removed_faces)
        self.points = [tuple(p) for p in mesh.points]
        # Порядок Cinema 4D сохраняется: сначала уцелевшие грани, затем новые.
        self.retained = [i for i in range(len(mesh.faces)) if i not in self.removed]
        self.faces = [tuple(mesh.faces[i]) for i in self.retained]
        self.face_origins = list(self.retained)
        self.generated = []
        self.rings = []
        self.old_point_count = len(mesh.points)
        self.merge_weights = {}

    def add_point(self, p):
        self.points.append(tuple(float(c) for c in p))
        return len(self.points) - 1

    def add_face(self, face):
        face = normalize_face(face)
        self.faces.append(face)
        self.face_origins.append(None)
        self.generated.append(len(self.faces) - 1)
        return len(self.faces) - 1


def _ring(builder, vertices, params, level, rim=None):
    """Регистрирует уровень моста. vertices — готовые индексы точек."""
    indices = []
    for v in vertices:
        indices.append(builder.add_point(v) if not isinstance(v, int) else v)
    builder.rings.append({'indices': indices, 'params': list(params),
                          'level': level, 'rim': rim})
    return indices


def _zip_rings(builder, lower, upper, closed):
    """Сшивает два уровня полигонами.

    Порядок вершин в полигоне — (нижняя i, нижняя i+1, верхняя j+1, верхняя j).
    Именно такой обход даёт нормаль, согласованную с удерживаемыми полигонами:
    ребро нижнего уровня при этом обходится навстречу соседней поверхности.
    """
    na, nb = len(lower), len(upper)
    if na == 0 or nb == 0:
        return
    if closed:
        i = j = 0
        steps = 0
        guard = (na + nb) * 2 + 8
        while i < na or j < nb:
            steps += 1
            if steps > guard:
                raise ValueError('Сшивание уровней моста не сошлось.')
            a0 = lower[i % na]
            b0 = upper[j % nb]
            lhs = (i + 1) * nb if i < na else float('inf')
            rhs = (j + 1) * na if j < nb else float('inf')
            if lhs == rhs:
                builder.add_face((a0, lower[(i + 1) % na], upper[(j + 1) % nb], b0))
                i += 1
                j += 1
            elif lhs < rhs:
                builder.add_face((a0, lower[(i + 1) % na], b0))
                i += 1
            else:
                builder.add_face((a0, upper[(j + 1) % nb], b0))
                j += 1
        return

    i = j = 0
    steps = 0
    guard = (na + nb) * 2 + 8
    while i < na - 1 or j < nb - 1:
        steps += 1
        if steps > guard:
            raise ValueError('Сшивание открытых уровней не сошлось.')
        a0 = lower[i]
        b0 = upper[j]
        lhs = (i + 1) * (nb - 1) if i < na - 1 else float('inf')
        rhs = (j + 1) * (na - 1) if j < nb - 1 else float('inf')
        if lhs == rhs:
            builder.add_face((a0, lower[i + 1], upper[j + 1], b0))
            i += 1
            j += 1
        elif lhs < rhs:
            builder.add_face((a0, lower[i + 1], b0))
            i += 1
        else:
            builder.add_face((a0, upper[j + 1], b0))
            j += 1


def _params(count, closed):
    if count <= 1:
        return [0.0]
    if closed:
        return [i / float(count) for i in range(count)]
    return [i / float(count - 1) for i in range(count)]


def _twist(loop, twist):
    if not loop:
        return list(loop)
    n = twist % len(loop)
    return list(loop[n:]) + list(loop[:n])



def _prepare_rims(rim_a, rim_b, closed, twist=0):
    """Приводит две кромки к виду «a[i] соответствует b[i]».

    Кромка B разворачивается: полигон моста обходит её навстречу кромке A.
    У замкнутых контуров якорная вершина B остаётся первой, поэтому якоря
    A и B действительно оказываются парой.
    """
    a = list(rim_a)
    if closed:
        b = [rim_b[0]] + list(reversed(rim_b[1:]))
        b = _twist(b, twist)
    else:
        b = list(reversed(rim_b))
    return a, b


# --------------------------------------------------------------------------
# Построение моста между двумя кромками
# --------------------------------------------------------------------------
def build_bridge(builder, rim_a, rim_b, opts, closed=True):
    """Создаёт мост между кромками внутри builder.

    Вызывающий код отвечает за удаление исходных граней и порядок
    последовательных соединений.
    """
    # Контур группы граней обходится в направлении самих удерживаемых
    # полигонов. Полигон моста на общем ребре обязан обходить его навстречу,
    # поэтому кромка B разворачивается, а кромка A остаётся как есть:
    # встречный обход получается из порядка вершин в самом полигоне моста.
    if not closed and opts.twist:
        raise ValueError('Сдвиг соответствия (Twist) применим только к замкнутым контурам.')
    a, b = _prepare_rims(rim_a, rim_b, closed, opts.twist)

    if len(a) < 2 or len(b) < 2:
        raise ValueError('Кромка моста содержит меньше двух вершин.')

    if opts.merge:
        return _merge_rims(builder, a, b, opts)

    points = builder.points
    n, m = len(a), len(b)
    cuts = opts.cuts
    center_a = loop_center(points, a, closed)
    center_b = loop_center(points, b, closed)
    axis = unit(sub(center_b, center_a))
    normal_a = polygon_normal(points, a)
    normal_b = polygon_normal(points, b)
    if length(axis) <= EPS:
        axis = normal_a
    if length(axis) <= EPS:
        raise ValueError('Контуры совпадают в пространстве: ось моста не определена.')

    tangents_a = tangents_b = None
    frames = path_centers = end_inverse = profile_centers = None

    if opts.interpolation == 'SURFACE':
        tangents_a = rim_tangents(points, builder.mesh.faces, a, closed,
                                  builder.removed, mul(axis, -1.0))
        tangents_b = rim_tangents(points, builder.mesh.faces, b, closed,
                                  builder.removed, axis)
    elif opts.interpolation == 'PATH':
        center_a, center_b, path_centers, _directions, frames = path_frames(
            points, a, b, cuts, opts.smooth, closed)
        end_inverse = mat_transpose(frames[-1])
    elif opts.profile:
        _, _, profile_centers, _, _ = path_frames(points, a, b, cuts, opts.smooth, closed)

    params_a = _params(n, closed)
    params_b = _params(m, closed)

    lower = _ring(builder, a, params_a, 0.0, 'a')
    for k in range(1, cuts + 1):
        t = k / float(cuts + 1)
        envelope = profile_envelope(opts.profile_shape, t)
        coords = []
        for i, va in enumerate(a):
            pa = points[va]
            param = params_a[i]
            pb = sample_contour(points, b, param, closed)
            if opts.interpolation == 'PATH':
                base = path_point(pa, pb, center_a, center_b, path_centers[k],
                                  frames[k], end_inverse, t)
                center = path_centers[k]
                if k < cuts:
                    spin_axis = unit(sub(path_centers[k + 1], path_centers[k]))
                else:
                    spin_axis = unit(sub(path_centers[k], path_centers[k - 1]))
                if length(spin_axis) <= EPS:
                    spin_axis = axis
            elif opts.interpolation == 'SURFACE':
                ta = tangents_a[va]
                # Касательная второй кромки берётся с той же долей вдоль
                # контура, иначе при разном числе вершин мост «ведёт».
                x = param * m
                bi = int(x) % m
                frac = x - int(x)
                tb = unit(mix(tangents_b[b[bi]], tangents_b[b[(bi + 1) % m]], frac))
                base = cubic_surface_point(pa, pb, ta, tb, t, opts.smooth)
                center = (profile_centers[k] if profile_centers is not None
                          else mix(center_a, center_b, t))
                spin_axis = axis
            else:
                base = mix(pa, pb, t)
                center = mix(center_a, center_b, t)
                spin_axis = axis

            radial = sub(base, center)
            if abs(opts.angle) > 1e-12:
                radial = rotate_axis(radial, spin_axis, opts.angle * envelope)
            if opts.profile:
                radial = mul(radial, 1.0 + opts.profile * envelope)
            coords.append(add(center, radial))

        upper = _ring(builder, coords, params_a, t)
        _zip_rings(builder, lower, upper, closed)
        lower = upper

    final = _ring(builder, b, params_b, 1.0, 'b')
    _zip_rings(builder, lower, final, closed)
    return builder.rings


def _merge_rims(builder, a, b, opts):
    """Сваривает две кромки: контуры объединяются, полигоны не создаются."""
    if len(a) != len(b):
        raise ValueError(
            'Merge требует одинакового числа вершин в контурах (%d и %d). '
            'Пересэмплирование здесь недопустимо: оно изменило бы форму '
            'сохраняемых граней.' % (len(a), len(b)))
    factor = opts.merge_factor
    mapping = {}
    for va, vb in zip(a, b):
        builder.points[va] = mix(builder.points[va], builder.points[vb], factor)
        mapping[vb] = va
        builder.merge_weights[vb] = (va, factor)

    touched = set(a) | set(b)
    for index, face in enumerate(builder.faces):
        if not touched.intersection(face):
            continue
        replaced = tuple(mapping.get(v, v) for v in face)
        if len(set(replaced)) != len(replaced):
            raise ValueError('Merge схлопывает полигон %d в вырожденный. '
                             'Измените положение слияния или выбор.' % index)
        builder.faces[index] = replaced

    used = set()
    for face in builder.faces:
        used.update(face)
    dangling = set(a) - used
    if dangling:
        raise ValueError(
            'После Merge останутся несвязанные вершины (%d), которые полигональный '
            'объект Cinema 4D не отобразит. Обычно это значит, что контуры не '
            'образуют замкнутую оболочку.' % len(dangling))
    return builder.rings


# --------------------------------------------------------------------------
# Автоматическое соответствие кромок (как в Blender)
# --------------------------------------------------------------------------
_SAMPLES = 48
_COARSE = 120


def _dist2(p, q):
    d = sub(p, q)
    return dot(d, d)


def _rim_cost(points, a, b, closed):
    """Сумма квадратов расстояний между соответствующими вершинами кромок."""
    n, m = len(a), len(b)
    if n < 2 or m < 2:
        return float('inf')
    step = max(1, n // _SAMPLES)
    total = 0.0
    for i in range(0, n, step):
        if closed:
            j = (i * m) // n
        else:
            j = int(round(i * (m - 1) / float(n - 1)))
        total += _dist2(points[a[i]], points[b[j]])
    return total


def _unique(items):
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _align_pair(points, loop_a, loop_b, closed, make, flip_ok):
    """Подбирает (va, vb, flip), при которых мост не перекручен.

    Перебираются вершины кромки B (грубо, затем уточнение вокруг лучшей) и,
    для замкнутых контуров без заданного полигонами направления, оба
    направления обхода. Критерий — минимальная сумма квадратов расстояний
    между соответствующими вершинами, то есть ровно то, что делает Blender,
    когда пользователь вообще не выбирает вершины.
    """
    if closed:
        centre = loop_center(points, loop_b, True)
        va = min(loop_a, key=lambda v: _dist2(points[v], centre))
        va_choices = [va]
        flips = (False, True) if flip_ok else (False,)
    else:
        va_choices = _unique([loop_a[0], loop_a[-1]])
        flips = (False,)

    def evaluate(va, vb, flip):
        rim_a, rim_b = make(va, vb, flip)
        a, b = _prepare_rims(rim_a, rim_b, closed)
        return _rim_cost(points, a, b, closed)

    if not closed:
        best = None
        for va in va_choices:
            for vb in _unique([loop_b[0], loop_b[-1]]):
                cost = evaluate(va, vb, False)
                if best is None or cost < best[0]:
                    best = (cost, va, vb, False)
        return best[1], best[2], best[3]

    m = len(loop_b)
    step = max(1, m // _COARSE)
    best = None
    for index in range(0, m, step):
        for flip in flips:
            cost = evaluate(va, loop_b[index], flip)
            if best is None or cost < best[0]:
                best = (cost, va, loop_b[index], flip, index)
    if step > 1:
        centre_index = best[4]
        for k in range(centre_index - step + 1, centre_index + step):
            index = k % m
            for flip in flips:
                cost = evaluate(va, loop_b[index], flip)
                if cost < best[0]:
                    best = (cost, va, loop_b[index], flip, index)
    return best[1], best[2], best[3]


def _centre(points, loop):
    n = float(len(loop))
    return tuple(sum(points[v][axis] for v in loop) / n for axis in range(3))


def _gap_matrix(points, loops):
    centres = [_centre(points, loop) for loop in loops]
    count = len(loops)
    gaps = {}
    for i in range(count):
        for j in range(i + 1, count):
            gaps[(i, j)] = gaps[(j, i)] = _dist2(centres[i], centres[j])
    return gaps


def _greedy_pairs(points, loops, fixed=None):
    """Разбивает контуры на пары по близости. fixed — уже заданная пара."""
    gaps = _gap_matrix(points, loops)
    remaining = list(range(len(loops)))
    pairs = []
    if fixed is not None:
        pairs.append(tuple(fixed))
        remaining = [i for i in remaining if i not in fixed]
    while remaining:
        best = None
        for x in range(len(remaining)):
            for y in range(x + 1, len(remaining)):
                i, j = remaining[x], remaining[y]
                key = (gaps[(i, j)], i, j)
                if best is None or key < best:
                    best = key
        if best is None:
            raise ValueError('Не удалось разбить контуры на пары.')
        _, i, j = best
        pairs.append((i, j))
        remaining.remove(i)
        remaining.remove(j)
    return pairs


def _path_order(gaps, count, start):
    order = [start]
    remaining = set(range(count)) - set(order)
    while remaining:
        last = order[-1]
        nxt = min(remaining, key=lambda i: (gaps[(last, i)], i))
        order.append(nxt)
        remaining.discard(nxt)
    return order


def _auto_chain_order(points, loops, closed):
    """Порядок последовательного соединения: кратчайший обход по ближайшим."""
    count = len(loops)
    gaps = _gap_matrix(points, loops)
    best = None
    for start in range(count):
        order = _path_order(gaps, count, start)
        total = sum(gaps[(order[k], order[k + 1])] for k in range(count - 1))
        if closed:
            total += gaps[(order[-1], order[0])]
        if best is None or total < best[0] - 1e-12:
            best = (total, order)
    return best[1]


def _chain_order(points, loops, first, second):
    """Порядок цепочки: от first к second, затем к ближайшим по расстоянию."""
    gaps = _gap_matrix(points, loops)
    order = [first, second]
    remaining = set(range(len(loops))) - set(order)
    while remaining:
        last = order[-1]
        nxt = min(remaining, key=lambda i: (gaps[(last, i)], i))
        order.append(nxt)
        remaining.discard(nxt)
    return order


def _island_of(islands, vertex):
    for i, island in enumerate(islands):
        if vertex in island.loop:
            return i
    return None


def _nearest_pair(points, loop_a, loop_b):
    best = None
    for a in loop_a:
        pa = points[a]
        for b in loop_b:
            d = dot(sub(pa, points[b]), sub(pa, points[b]))
            if best is None or d < best[0]:
                best = (d, a, b)
    return best[1], best[2]


# --------------------------------------------------------------------------
# Группы граней
# --------------------------------------------------------------------------
def _face_alignment(mesh, islands, i, j):
    def make(va, vb, flip):
        return rotate_to(islands[i].loop, va), rotate_to(islands[j].loop, vb)
    va, vb, _ = _align_pair(mesh.points, islands[i].loop, islands[j].loop, True,
                            make, False)
    return va, vb


def _face_pairs_plan(mesh, islands, order_pairs, first_anchors):
    """order_pairs — [(i, j), ...]; первой паре можно задать якоря вручную."""
    pairs = []
    for k, (i, j) in enumerate(order_pairs):
        if k == 0 and first_anchors is not None:
            va, vb = first_anchors
        else:
            va, vb = _face_alignment(mesh, islands, i, j)
        pairs.append((i, j, va, vb))
    return pairs


def auto_anchors_faces(mesh, selected, mode=0):
    """Якоря первой пары, которые инструмент выберет сам: (va, vb, False)."""
    islands = collect_islands(mesh, selected, allow_many=(mode != 0))
    loops = [island.loop for island in islands]
    if mode == 0 or len(loops) == 2:
        i, j = 0, 1
    elif mode == 1:
        i, j = _greedy_pairs(mesh.points, loops)[0]
    else:
        order = _auto_chain_order(mesh.points, loops, mode == 3)
        i, j = order[0], order[1]
    va, vb = _face_alignment(mesh, islands, i, j)
    return va, vb, False


def plan_face_bridge(mesh, selected, anchor_a, anchor_b, opts):
    islands = collect_islands(mesh, selected, allow_many=False)
    if anchor_a is None or anchor_b is None:
        ia, ib = 0, 1
        anchors = None
    else:
        ia = _island_of(islands, anchor_a)
        ib = _island_of(islands, anchor_b)
        if ia is None or ib is None:
            raise ValueError('Якорная вершина не принадлежит границе выделенных граней.')
        if ia == ib:
            raise ValueError('Якорные вершины должны принадлежать двум разным группам.')
        anchors = (anchor_a, anchor_b)
    pairs = _face_pairs_plan(mesh, islands, [(ia, ib)], anchors)
    return _plan_face_pairs(mesh, islands, pairs, opts, 'faces')


def plan_face_pairs(mesh, selected, anchor_a, anchor_b, opts):
    islands = collect_islands(mesh, selected, allow_many=True)
    if len(islands) % 2:
        raise ValueError('Для парного соединения нужно чётное число групп граней, '
                         'а выделено %d.' % len(islands))
    loops = [island.loop for island in islands]
    if anchor_a is None or anchor_b is None:
        order_pairs = _greedy_pairs(mesh.points, loops)
        anchors = None
    else:
        ia = _island_of(islands, anchor_a)
        ib = _island_of(islands, anchor_b)
        if ia is None or ib is None:
            raise ValueError('Якорная вершина не принадлежит границе выделенных граней.')
        if ia == ib:
            raise ValueError('Якорные вершины должны принадлежать двум разным группам.')
        order_pairs = _greedy_pairs(mesh.points, loops, fixed=(ia, ib))
        anchors = (anchor_a, anchor_b)
    pairs = _face_pairs_plan(mesh, islands, order_pairs, anchors)
    return _plan_face_pairs(mesh, islands, pairs, opts, 'face_pairs')


def plan_face_chain(mesh, selected, anchor_a, anchor_b, opts, closed=False):
    islands = collect_islands(mesh, selected, allow_many=True)
    if len(islands) < 3:
        raise ValueError('Для последовательного соединения нужно минимум три группы граней.')
    loops = [island.loop for island in islands]
    if anchor_a is None or anchor_b is None:
        order = _auto_chain_order(mesh.points, loops, closed)
        anchors = None
    else:
        first = _island_of(islands, anchor_a)
        second = _island_of(islands, anchor_b)
        if first is None or second is None:
            raise ValueError('Якорная вершина не принадлежит границе выделенных граней.')
        if first == second:
            raise ValueError('Якорные вершины должны принадлежать двум разным группам.')
        order = _chain_order(mesh.points, loops, first, second)
        anchors = (anchor_a, anchor_b)
    order_pairs = [(order[k], order[k + 1]) for k in range(len(order) - 1)]
    if closed:
        order_pairs.append((order[-1], order[0]))
    pairs = _face_pairs_plan(mesh, islands, order_pairs, anchors)
    return _plan_face_pairs(mesh, islands, pairs, opts,
                            'face_chain_closed' if closed else 'face_chain')


def _plan_face_pairs(mesh, islands, pairs, opts, mode):
    disjoint_loops(islands)
    removed = set()
    for island in islands:
        removed.update(island.faces)
    builder = _Builder(mesh, removed)

    for i, j, va, vb in pairs:
        a = rotate_to(islands[i].loop, va)
        b = rotate_to(islands[j].loop, vb)
        build_bridge(builder, a, b, opts, closed=True)

    plan = _finalize(builder, mesh, mode)
    _reject_non_manifold(plan)
    return plan


def _reject_non_manifold(plan):
    """Ловит случай, когда кромка используется мостом дважды.

    Так бывает при последовательном соединении групп граней: рёбра кромки уже
    имеют соседа в сохраняемой сетке, и второй мост даёт три полигона на ребро.
    """
    counts = defaultdict(int)
    for face in plan.faces:
        for a, b in edges_of(list(face), True):
            counts[edge_key(a, b)] += 1
    bad = [k for k, v in counts.items() if v > 2]
    if bad:
        raise ValueError(
            'Последовательное соединение этих групп граней дало бы неманифолдную '
            'сетку: рёбер с тремя и более полигонами — %d. В отличие от Blender, '
            'где цепочки строятся по свободным петлям рёбер, кромка группы граней '
            'уже занята соседней поверхностью. Используйте режим «две группы», '
            'парное соединение либо цепочки рёбер.' % len(bad))


# --------------------------------------------------------------------------
# Цепочки рёбер
# --------------------------------------------------------------------------
def _edge_rims(chains, incidence, i, j, va, vb, flip):
    """Кромки пары цепочек. flip разворачивает ту из них, чьё направление
    не задано полигонами."""
    free_i = chain_is_free(chains[i], incidence)
    free_j = chain_is_free(chains[j], incidence)
    a = chain_pairs(chains[i], va, incidence, flip and free_i and not free_j)
    b = chain_pairs(chains[j], vb, incidence, flip and free_j)
    return a, b


def _edge_alignment(mesh, chains, incidence, i, j):
    if chains[i].closed != chains[j].closed:
        raise ValueError('Обе цепочки должны быть либо замкнутыми, либо открытыми.')
    free = (chain_is_free(chains[i], incidence)
            or chain_is_free(chains[j], incidence))

    def make(va, vb, flip):
        return _edge_rims(chains, incidence, i, j, va, vb, flip)
    return _align_pair(mesh.points, chains[i].vertices, chains[j].vertices,
                       chains[i].closed, make, free)


def _edge_pairs_plan(mesh, chains, incidence, order_pairs, first_anchors):
    pairs = []
    for k, (i, j) in enumerate(order_pairs):
        if k == 0 and first_anchors is not None:
            va, vb, flip = first_anchors
        else:
            va, vb, flip = _edge_alignment(mesh, chains, incidence, i, j)
        pairs.append((i, j, va, vb, flip))
    return pairs


def auto_anchors_edges(mesh, selected_edges, mode=0):
    """Якоря первой пары цепочек: (va, vb, flip)."""
    chains = ordered_chains(selected_edges)
    incidence = mesh.edge_incidence()
    loops = [chain.vertices for chain in chains]
    if mode == 0 or len(chains) == 2:
        i, j = 0, 1
    elif mode == 1:
        i, j = _greedy_pairs(mesh.points, loops)[0]
    else:
        order = _auto_chain_order(mesh.points, loops, mode == 3)
        i, j = order[0], order[1]
    return _edge_alignment(mesh, chains, incidence, i, j)


def plan_edge_bridge(mesh, selected_edges, anchor_a, anchor_b, opts, flip=False):
    chains = ordered_chains(selected_edges)
    if len(chains) != 2:
        raise ValueError('Выберите ровно две цепочки рёбер, а выделено %d.' % len(chains))
    incidence = mesh.edge_incidence()
    anchors = None if anchor_a is None or anchor_b is None else (anchor_a, anchor_b, flip)
    pairs = _edge_pairs_plan(mesh, chains, incidence, [(0, 1)], anchors)
    return _plan_edge_chains(mesh, chains, pairs, opts, 'edges')


def plan_edge_pairs(mesh, selected_edges, anchor_a, anchor_b, opts, flip=False):
    chains = ordered_chains(selected_edges)
    if len(chains) < 2 or len(chains) % 2:
        raise ValueError('Для парного соединения нужно чётное число цепочек рёбер.')
    incidence = mesh.edge_incidence()
    loops = [chain.vertices for chain in chains]
    if anchor_a is None or anchor_b is None:
        order_pairs = _greedy_pairs(mesh.points, loops)
        anchors = None
    else:
        ia = _chain_of(chains, anchor_a)
        ib = _chain_of(chains, anchor_b)
        if ia is None or ib is None:
            raise ValueError('Якорная вершина не принадлежит выбранной цепочке.')
        if ia == ib:
            raise ValueError('Якорные вершины должны принадлежать двум разным цепочкам.')
        order_pairs = _greedy_pairs(mesh.points, loops, fixed=(ia, ib))
        anchors = (anchor_a, anchor_b, flip)
    pairs = _edge_pairs_plan(mesh, chains, incidence, order_pairs, anchors)
    return _plan_edge_chains(mesh, chains, pairs, opts, 'edge_pairs')


def plan_edge_chain(mesh, selected_edges, anchor_a, anchor_b, opts, closed=False,
                    flip=False):
    chains = ordered_chains(selected_edges)
    if len(chains) < 3:
        raise ValueError('Для последовательного соединения нужно минимум три цепочки рёбер.')
    incidence = mesh.edge_incidence()
    loops = [chain.vertices for chain in chains]
    if anchor_a is None or anchor_b is None:
        order = _auto_chain_order(mesh.points, loops, closed)
        anchors = None
    else:
        first = _chain_of(chains, anchor_a)
        second = _chain_of(chains, anchor_b)
        if first is None or second is None:
            raise ValueError('Якорная вершина не принадлежит выбранной цепочке.')
        if first == second:
            raise ValueError('Якорные вершины должны принадлежать двум разным цепочкам.')
        order = _chain_order(mesh.points, loops, first, second)
        anchors = (anchor_a, anchor_b, flip)
    order_pairs = [(order[k], order[k + 1]) for k in range(len(order) - 1)]
    if closed:
        order_pairs.append((order[-1], order[0]))
    pairs = _edge_pairs_plan(mesh, chains, incidence, order_pairs, anchors)
    return _plan_edge_chains(mesh, chains, pairs, opts,
                             'edge_chain_closed' if closed else 'edge_chain')


def _chain_of(chains, vertex):
    for i, chain in enumerate(chains):
        if vertex in chain.vertices:
            return i
    return None


def _plan_edge_chains(mesh, chains, pairs, opts, mode):
    incidence = mesh.edge_incidence()
    builder = _Builder(mesh, ())
    used = {}

    for i, j, va, vb, flip in pairs:
        if chains[i].closed != chains[j].closed:
            raise ValueError('Обе цепочки должны быть либо замкнутыми, либо открытыми.')
        a, b = _edge_rims(chains, incidence, i, j, va, vb, flip)
        # Повторное использование цепочки возможно только с тем же направлением,
        # иначе мост наложится сам на себя.
        for index, rim in ((i, a), (j, b)):
            if index in used and used[index] != rim:
                raise ValueError(
                    'Цепочка используется дважды в разных направлениях. '
                    'Для этого выберите другие якорные вершины.')
            used[index] = rim
        build_bridge(builder, a, b, opts, chains[i].closed)

    plan = _finalize(builder, mesh, mode)
    return plan


# --------------------------------------------------------------------------
# Сведение результата
# --------------------------------------------------------------------------
def _finalize(builder, mesh, mode):
    points = builder.points
    faces = builder.faces

    used = set()
    for face in faces:
        used.update(face)

    before_used = set()
    for face in mesh.faces:
        before_used.update(face)

    # Удаляются только те точки, которые операция сделала ненужными. Заранее
    # свободные точки объекта сохраняются: их не должно «съедать» мостом.
    keep = []
    for index in range(len(points)):
        if index in used:
            keep.append(index)
        elif index >= builder.old_point_count:
            continue
        elif index not in before_used:
            keep.append(index)
    remap = dict((old, new) for new, old in enumerate(keep))
    new_points = [points[i] for i in keep]

    new_faces = []
    for face in faces:
        try:
            new_faces.append(tuple(remap[v] for v in face))
        except KeyError:
            raise ValueError('Операция оставила полигон, ссылающийся на удалённую вершину.')

    point_map = {}
    for old in range(len(points)):
        point_map[old] = remap.get(old)

    rings = []
    for ring in builder.rings:
        indices = [remap.get(i) for i in ring['indices']]
        if any(i is None for i in indices):
            continue
        rings.append({'indices': indices, 'params': ring['params'],
                      'level': ring['level'], 'rim': ring['rim']})

    # Индексы новых граней после компакции точек не меняются: грани уже
    # переупорядочены как «сохранённые, затем новые».
    plan = Plan(new_points, new_faces, builder.generated, sorted(builder.removed),
                builder.retained, point_map, rings, builder.old_point_count, mode,
                None, builder.face_origins,
                old_points=[tuple(p) for p in mesh.points],
                old_faces=[tuple(f) for f in mesh.faces])

    for old_source, (old_target, factor) in builder.merge_weights.items():
        new_source = remap.get(old_source)
        new_target = remap.get(old_target)
        if new_source is not None and new_target is not None and new_source != new_target:
            plan.merge_pairs[new_source] = (new_target, factor)
    return plan
