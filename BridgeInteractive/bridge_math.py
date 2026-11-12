# -*- coding: utf-8 -*-
"""Векторная математика и профили моста. Без зависимости от Cinema 4D.

Координаты здесь всегда «локальные тройки» float. c4d.Vector появляется
только на границе модуля bridge_host.
"""
from math import sqrt, sin, cos, pi, isfinite, atan2

EPS = 1e-12


# --------------------------------------------------------------------------
# Базовые операции над тройками
# --------------------------------------------------------------------------
def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def length(a):
    return sqrt(dot(a, a))


def unit(a):
    n = length(a)
    return mul(a, 1.0 / n) if n > EPS else (0.0, 0.0, 0.0)


def mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def centroid(points):
    n = float(len(points))
    return (sum(p[0] for p in points) / n,
            sum(p[1] for p in points) / n,
            sum(p[2] for p in points) / n)


def is_finite_point(p):
    return len(p) == 3 and all(isfinite(float(x)) for x in p)


def edge_key(a, b):
    return (a, b) if a < b else (b, a)


def edges_of(loop, closed):
    """Пары индексов вдоль контура; для замкнутого добавляет замыкающее ребро."""
    pairs = list(zip(loop, loop[1:]))
    if closed and len(loop) > 1:
        pairs.append((loop[-1], loop[0]))
    return pairs


# --------------------------------------------------------------------------
# Геометрия контуров
# --------------------------------------------------------------------------
def loop_center(points, loop, closed=True):
    """Центр контура со взвешиванием по длинам рёбер.

    Взвешивание нужно, чтобы изогнутый контур не «тянуло» к густо
    нарезанной части, как это делает простой центроид.
    """
    if len(loop) < 2:
        return points[loop[0]]
    coords = [points[i] for i in loop]
    n = len(coords)
    spans = [length(sub(coords[(i + 1) % n], coords[i])) for i in range(n)]
    if not closed:
        weights = [0.0] * n
        weights[0] = spans[0]
        weights[-1] = spans[-1]
        for i in range(1, n - 1):
            weights[i] = spans[i - 1] + spans[i]
    else:
        weights = [spans[i - 1] + spans[i] for i in range(n)]
    total = sum(weights)
    if total <= EPS:
        return centroid(coords)
    return (sum(p[0] * w for p, w in zip(coords, weights)) / total,
            sum(p[1] * w for p, w in zip(coords, weights)) / total,
            sum(p[2] * w for p, w in zip(coords, weights)) / total)


def polygon_normal(points, loop):
    """Нормаль методом Ньюэлла — устойчива на вогнутых и n-сторонних контурах."""
    n = (0.0, 0.0, 0.0)
    for a, b in edges_of(list(loop), True):
        pa, pb = points[a], points[b]
        n = add(n, ((pa[1] - pb[1]) * (pa[2] + pb[2]),
                    (pa[2] - pb[2]) * (pa[0] + pb[0]),
                    (pa[0] - pb[0]) * (pa[1] + pb[1])))
    return unit(n)


def aligned_loop_normal(points, loop, align, closed=True):
    """Нормаль контура, повёрнутая так, чтобы быть примерно вдоль align."""
    coords = [points[i] for i in loop]
    normal = (0.0, 0.0, 0.0)
    for a, b in edges_of(list(range(len(coords))), closed):
        d = sub(coords[b], coords[a])
        normal = add(normal, cross(d, cross(align, d)))
    return unit(normal) if length(normal) > EPS else (0.0, 0.0, 1.0)


def rim_tangents(points, faces, loop, closed=True, excluded=(), fallback=(0.0, 0.0, 0.0)):
    """Внешние касательные у кромки, оценённые по сохранённым полигонам.

    Эти векторы смотрят от соседней поверхности в сторону зазора, и именно
    они дают правильные ручки Безье в режиме «по поверхности».
    """
    rim = set(loop)
    excluded = set(excluded)
    totals = dict((v, (0.0, 0.0, 0.0)) for v in rim)
    rim_edges = set(edge_key(a, b) for a, b in edges_of(list(loop), closed))
    for index, face in enumerate(faces):
        if index in excluded:
            continue
        eligible = [(a, b) for a, b in edges_of(list(face), True) if edge_key(a, b) in rim_edges]
        if not eligible:
            continue
        normal = polygon_normal(points, list(face))
        for a, b in eligible:
            tangent = unit(cross(sub(points[b], points[a]), normal))
            totals[a] = add(totals[a], tangent)
            totals[b] = add(totals[b], tangent)
    return dict((v, unit(totals[v]) if length(totals[v]) > EPS else fallback) for v in rim)


def rotate_to(loop, anchor):
    try:
        i = list(loop).index(anchor)
    except ValueError:
        raise ValueError('Якорная вершина не принадлежит выбранному контуру.')
    return list(loop[i:]) + list(loop[:i])


def rotate_by(loop, offset):
    if not loop:
        return list(loop)
    n = offset % len(loop)
    return list(loop[n:]) + list(loop[:n])


def sample_contour(points, loop, t, closed=True):
    """Точка на контуре по нормированному параметру t."""
    n = len(loop)
    if n == 1:
        return points[loop[0]]
    if closed:
        x = (t % 1.0) * n
    else:
        x = max(0.0, min(1.0, t)) * (n - 1)
    i = int(x)
    if i >= n - 1:
        return points[loop[-1]]
    return mix(points[loop[i]], points[loop[i + 1]], x - i)


# --------------------------------------------------------------------------
# Профили: форма поперечного сечения моста
# --------------------------------------------------------------------------
PROFILE_SHAPES = ('SMOOTH', 'SPHERE', 'ROOT', 'SHARP', 'LINEAR', 'CONSTANT', 'INVERSE_SQUARE')


def profile_envelope(shape, t):
    """Множитель 0..1 по параметру вдоль моста.

    Форма профиля применяется к сглаживанию и углу: на концах моста влияние
    нулевое, в середине — максимальное. Так ведёт себя Blender.
    """
    x = 1.0 - abs(2.0 * t - 1.0)
    if shape == 'SMOOTH':
        return x * x * (3.0 - 2.0 * x)
    if shape == 'SPHERE':
        return sqrt(max(0.0, 1.0 - (1.0 - x) * (1.0 - x)))
    if shape == 'ROOT':
        return sqrt(x)
    if shape == 'SHARP':
        return x * x
    if shape == 'LINEAR':
        return x
    if shape == 'CONSTANT':
        return 1.0
    if shape == 'INVERSE_SQUARE':
        return 1.0 - (1.0 - x) * (1.0 - x)
    raise ValueError('Неизвестная форма профиля: %s' % shape)


def cubic_surface_point(a, b, normal_a, normal_b, t, smooth):
    """Кубический Безье между кромками с ручками по нормалям поверхностей."""
    n1 = unit(normal_a)
    n2 = unit(normal_b)
    cos_angle = max(-1.0, min(1.0, dot(n1, n2)))
    # Длина ручки как в Blender: при развороте нормалей ручка длиннее,
    # иначе мост «схлопывается» на резком угле.
    factor = 1.333333 if cos_angle >= 0 else 1.333333 * (1.0 + cos_angle) + 0.75 * (-cos_angle)
    axis = cross(n1, n2)
    delta = sub(b, a)
    if dot(axis, axis) > 1.1920929e-7:
        axis = unit(axis)
        delta = sub(delta, mul(axis, dot(delta, axis)))
    handle = length(delta) * 0.5 * factor * smooth
    p1 = add(a, mul(n1, handle))
    p2 = add(b, mul(n2, handle))
    s = 1.0 - t
    return add(add(mul(a, s * s * s), mul(p1, 3.0 * s * s * t)),
               add(mul(p2, 3.0 * s * t * t), mul(b, t * t * t)))


def rotate_axis(v, axis, angle):
    """Поворот вектора вокруг оси (формула Родрига)."""
    if abs(angle) < 1e-15:
        return v
    c, s = cos(angle), sin(angle)
    return add(add(mul(v, c), mul(cross(axis, v), s)), mul(axis, dot(axis, v) * (1.0 - c)))


# --------------------------------------------------------------------------
# Транспорт системы координат вдоль пути (minimum twist, как в Blender)
# --------------------------------------------------------------------------
_IDENT = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def mat_vec(m, v):
    return (dot(m[0], v), dot(m[1], v), dot(m[2], v))


def mat_transpose(m):
    return tuple(zip(*m))


def path_frames(points, loop_a, loop_b, cuts, smoothness, closed=True):
    """Центральная кривая моста и кадры без накопления кручения.

    Возвращает (центр_a, центр_b, центры, направления, матрицы_поворота).
    """
    center_a = loop_center(points, loop_a, closed)
    center_b = loop_center(points, loop_b, closed)
    axis = unit(sub(center_b, center_a))
    normal_a = polygon_normal(points, loop_a)
    normal_b = polygon_normal(points, loop_b)
    if length(normal_a) <= EPS:
        normal_a = aligned_loop_normal(points, loop_a, axis, closed)
    if length(normal_b) <= EPS:
        normal_b = aligned_loop_normal(points, loop_b, axis, closed)
    if length(axis) <= EPS:
        axis = normal_a
    if length(axis) <= EPS:
        raise ValueError('Не удалось определить ось моста: контуры совпадают.')
    if dot(normal_a, axis) < 0.0:
        normal_a = mul(normal_a, -1.0)
    if dot(normal_b, axis) > 0.0:
        normal_b = mul(normal_b, -1.0)
    centers = [cubic_surface_point(center_a, center_b, normal_a, normal_b,
                                   i / float(cuts + 1), smoothness)
               for i in range(cuts + 2)]
    directions = [normal_a]
    for i in range(1, cuts + 1):
        d = unit(add(unit(sub(centers[i], centers[i - 1])),
                     unit(sub(centers[i + 1], centers[i]))))
        directions.append(d if length(d) > EPS else directions[-1])
    directions.append(mul(normal_b, -1.0))
    frames = [_IDENT]
    for before, after in zip(directions, directions[1:]):
        axis_r = cross(before, after)
        size = length(axis_r)
        cosine = max(-1.0, min(1.0, dot(before, after)))
        if size > EPS:
            rot_axis = mul(axis_r, 1.0 / size)
            angle = atan2(size, cosine)
        elif cosine < 0.0:
            basis = (1.0, 0.0, 0.0) if abs(before[0]) < 0.9 else (0.0, 1.0, 0.0)
            rot_axis = unit(cross(before, basis))
            angle = pi
        else:
            frames.append(frames[-1])
            continue
        cols = [rotate_axis(v, rot_axis, angle) for v in _IDENT]
        rot = tuple(tuple(cols[j][i] for j in range(3)) for i in range(3))
        frames.append(mat_mul(rot, frames[-1]))
    return center_a, center_b, centers, directions, frames


def path_point(pa, pb, center_a, center_b, center, frame, end_inverse, t):
    a = mat_vec(frame, sub(pa, center_a))
    b = mat_vec(frame, mat_vec(end_inverse, sub(pb, center_b)))
    return add(center, mix(a, b, t))
