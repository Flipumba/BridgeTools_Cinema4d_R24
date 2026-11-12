# -*- coding: utf-8 -*-
"""Топология сетки: острова граней, цепочки рёбер, сопоставление контуров.

Модуль не знает о Cinema 4D. Все индексы — локальные индексы объекта.
"""
from collections import defaultdict

from bridge_math import EPS, sub, dot, length, edge_key, edges_of, rotate_to, mix


class Mesh(object):
    """Неизменяемый снимок полигональной сетки: точки + полигоны."""

    __slots__ = ('points', 'faces')

    def __init__(self, points, faces):
        self.points = [tuple(float(c) for c in p) for p in points]
        self.faces = [normalize_face(f) for f in faces]
        n = len(self.points)
        for f in self.faces:
            for v in f:
                if not isinstance(v, int) or v < 0 or v >= n:
                    raise ValueError('Полигон ссылается на несуществующую вершину %r.' % (v,))

    def __len__(self):
        return len(self.faces)

    def edge_incidence(self):
        """«Ребро -> [(индекс полигона, a, b)]» с сохранением направления обхода."""
        incidence = defaultdict(list)
        for index, face in enumerate(self.faces):
            for a, b in edges_of(list(face), True):
                incidence[edge_key(a, b)].append((index, a, b))
        return incidence


def normalize_face(face):
    """Приводит CPolygon к треугольнику или кваду, отбрасывая вырожденные."""
    f = tuple(face)
    if len(f) == 4 and f[2] == f[3]:
        f = f[:3]
    if len(f) not in (3, 4):
        raise ValueError('Поддерживаются только треугольники и квады.')
    if len(set(f)) != len(f):
        raise ValueError('Полигон с повторяющейся вершиной: операция отменена.')
    return f


# --------------------------------------------------------------------------
# Острова выделенных граней
# --------------------------------------------------------------------------
class Island(object):
    """Связная группа выделенных граней с единственным замкнутым контуром."""

    __slots__ = ('faces', 'loop')

    def __init__(self, faces, loop):
        self.faces = frozenset(faces)
        self.loop = list(loop)

    def __repr__(self):
        return '<Island %d faces, rim %d>' % (len(self.faces), len(self.loop))


def collect_islands(mesh, selected, allow_many=False):
    """Острова выделенных граней в устойчивом порядке."""
    selected = set(selected)
    if not selected:
        raise ValueError('Не выделено ни одной грани.')
    if any(i < 0 or i >= len(mesh.faces) for i in selected):
        raise ValueError('Индексы выделения выходят за пределы объекта.')

    incidence = mesh.edge_incidence()
    for key, ids in incidence.items():
        if len(ids) > 2:
            raise ValueError('В сетке есть неманифолдное ребро (%d,%d): к нему примыкает '
                             'больше двух полигонов. Мост требует манифолдную сетку.'
                             % key)

    adjacency = defaultdict(set)
    for ids in incidence.values():
        if len(ids) == 2 and ids[0][0] in selected and ids[1][0] in selected:
            a, b = ids[0][0], ids[1][0]
            adjacency[a].add(b)
            adjacency[b].add(a)

    groups = []
    pending = set(selected)
    while pending:
        seed = min(pending)
        pending.discard(seed)
        group = set()
        stack = [seed]
        while stack:
            index = stack.pop()
            group.add(index)
            for other in adjacency[index] & pending:
                pending.discard(other)
                stack.append(other)
        groups.append(group)

    if len(groups) < 2:
        raise ValueError('Нужно выделить минимум две отдельные группы граней.')
    if not allow_many and len(groups) != 2:
        raise ValueError('Нужно выделить ровно две отдельные группы граней, '
                         'а выделено %d.' % len(groups))
    return [Island(group, _island_boundary(mesh, group, incidence)) for group in groups]


def _island_boundary(mesh, group, incidence):
    """Единственный замкнутый контур острова с проверкой направления обхода."""
    directed = []
    for index in sorted(group):
        face = mesh.faces[index]
        for a, b in edges_of(list(face), True):
            shared = incidence[edge_key(a, b)]
            if sum(1 for entry in shared if entry[0] in group) == 1:
                directed.append((a, b))

    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for a, b in directed:
        outgoing[a].append(b)
        incoming[b].append(a)
    vertices = set(outgoing) | set(incoming)
    if not vertices:
        raise ValueError('Выделенная группа граней не имеет внешней границы. '
                         'Выберите участок поверхности, а не всю оболочку.')

    for v in vertices:
        if len(outgoing[v]) != 1 or len(incoming[v]) != 1:
            raise ValueError('Граница выделения не является одним замкнутым контуром: '
                             'выделение содержит дырку, ветвление или несогласованный '
                             'обход граней.')

    start = min(vertices)
    loop = [start]
    current = outgoing[start][0]
    while current != start:
        if current in loop:
            raise ValueError('Граница выделения распадается на несколько петель.')
        loop.append(current)
        current = outgoing[current][0]
    if len(loop) != len(vertices):
        raise ValueError('Граница выделения не является одним замкнутым контуром.')
    if len(loop) < 3:
        raise ValueError('Граница выделения содержит меньше трёх вершин.')

    # У каждого ребра границы должен быть ровно один сохраняемый сосед, и его
    # обход должен быть противоположным, иначе нормали новой грани окажутся
    # вывернутыми относительно соседней поверхности.
    for a, b in edges_of(loop, True):
        neighbours = [e for e in incidence[edge_key(a, b)] if e[0] not in group]
        if len(neighbours) > 1:
            raise ValueError('Ребро границы имеет несколько соседних полигонов вне выделения.')
        if neighbours:
            _, na, nb = neighbours[0]
            if (na, nb) == (a, b):
                raise ValueError('Несогласованное направление граней вдоль границы выделения.')
    return loop


def disjoint_loops(islands):
    """Проверяет, что контуры не пересекаются по вершинам."""
    seen = set()
    for island in islands:
        overlap = seen.intersection(island.loop)
        if overlap:
            raise ValueError('Выделенные группы используют общие вершины (%d).' % len(overlap))
        seen.update(island.loop)
    return True


# --------------------------------------------------------------------------
# Цепочки рёбер
# --------------------------------------------------------------------------
class Chain(object):
    __slots__ = ('vertices', 'closed')

    def __init__(self, vertices, closed):
        self.vertices = list(vertices)
        self.closed = bool(closed)

    def __len__(self):
        return len(self.vertices)

    def __repr__(self):
        return '<Chain %d verts %s>' % (len(self.vertices),
                                        'closed' if self.closed else 'open')


def ordered_chains(edge_list):
    """Разбивает набор рёбер на несвязные цепочки и циклы без ветвления."""
    adjacency = defaultdict(set)
    seen = set()
    for a, b in edge_list:
        if a == b:
            raise ValueError('Выделено вырожденное ребро нулевой длины.')
        k = edge_key(a, b)
        if k in seen:
            continue
        seen.add(k)
        adjacency[a].add(b)
        adjacency[b].add(a)
    if not seen:
        raise ValueError('Не выделено ни одного ребра.')

    branches = [v for v, ns in adjacency.items() if len(ns) > 2]
    if branches:
        raise ValueError('Выделенные рёбра ветвятся в вершине %d. '
                         'Выберите простые цепочки.' % branches[0])

    chains = []
    remaining = set(seen)
    while remaining:
        seed = min(remaining)
        nodes = set()
        stack = [seed[0]]
        while stack:
            v = stack.pop()
            if v in nodes:
                continue
            nodes.add(v)
            stack.extend(adjacency[v] - nodes)
        ends = sorted(v for v in nodes if len(adjacency[v]) == 1)
        if len(ends) not in (0, 2):
            raise ValueError('Некорректная топология цепочки рёбер.')
        closed = not ends
        start = ends[0] if ends else min(nodes)
        chain = [start]
        previous = None
        current = start
        while True:
            options = sorted(v for v in adjacency[current]
                             if v != previous and edge_key(current, v) in remaining)
            if not options:
                break
            nxt = options[0]
            remaining.discard(edge_key(current, nxt))
            previous, current = current, nxt
            if current == start:
                break
            chain.append(current)
        if len(chain) != len(nodes):
            raise ValueError('Выделенные рёбра не образуют одну цепочку.')
        if closed and len(chain) < 3:
            raise ValueError('Замкнутая цепочка содержит меньше трёх вершин.')
        chains.append(Chain(chain, closed))
    return chains


def align_chain(chain, anchor):
    """Ставит якорную вершину в начало; для открытой цепочки — только с конца."""
    loop = chain.vertices
    if anchor not in loop:
        raise ValueError('Якорная вершина не принадлежит выбранной цепочке.')
    if chain.closed:
        return rotate_to(loop, anchor)
    if anchor == loop[0]:
        return list(loop)
    if anchor == loop[-1]:
        return list(reversed(loop))
    raise ValueError('Для открытой цепочки выбирайте крайнюю вершину.')


def chain_sign(chain_vertices, closed, incidence):
    """Направление цепочки относительно соседнего полигона: +1, -1 или None.

    None означает, что направление по полигонам определить нельзя: у рёбер нет
    соседних полигонов (свободная кривая), их больше одного (петля посреди
    сетки) либо направления вдоль цепочки не согласованы. В Blender такие
    петли тоже соединяются, а направление подбирается по геометрии.
    """
    signs = set()
    for a, b in edges_of(chain_vertices, closed):
        entries = incidence.get(edge_key(a, b), [])
        if len(entries) != 1:
            return None
        _, x, y = entries[0]
        signs.add(1 if (x, y) == (a, b) else -1)
    if len(signs) != 1:
        return None
    return signs.pop()


def orient_chain(chain_vertices, closed, incidence, desired):
    """Разворачивает цепочку так, чтобы мост противостоял существующим граням.

    desired=+1 — обход моста совпадает с цепочкой, -1 — противоположен.
    Если направление по полигонам не определено, цепочка остаётся как есть.
    """
    sign = chain_sign(chain_vertices, closed, incidence)
    if sign is None:
        return list(chain_vertices)
    if sign * desired == 1:
        if closed:
            return [chain_vertices[0]] + list(reversed(chain_vertices[1:]))
        return list(reversed(chain_vertices))
    return list(chain_vertices)


def chain_pairs(chain, anchor, incidence, flip=False):
    """Готовит цепочку как кромку моста: к якорю, с правильной ориентацией.

    flip действует только на замкнутые цепочки без определённого направления:
    он разворачивает обход, оставляя якорь первым.
    """
    aligned = align_chain(chain, anchor)
    sign = chain_sign(aligned, chain.closed, incidence)
    if sign is None:
        if flip and chain.closed:
            return [aligned[0]] + list(reversed(aligned[1:]))
        return aligned
    return orient_chain(aligned, chain.closed, incidence, +1)


def chain_is_free(chain, incidence):
    """True, если направление цепочки задаётся не полигонами, а геометрией."""
    return chain_sign(list(chain.vertices), chain.closed, incidence) is None


# --------------------------------------------------------------------------
# Пересэмплирование контура
# --------------------------------------------------------------------------
def resample_loop(points, loop, count, closed=True):
    """Равномерно распределяет count точек по длине контура."""
    n = len(loop)
    if count == n:
        return [points[i] for i in loop]
    if count < 2:
        raise ValueError('Нельзя пересэмплировать контур меньше двух точек.')
    coords = [points[i] for i in loop]
    spans = [length(sub(coords[(i + 1) % n], coords[i])) for i in range(n)]
    total = sum(spans)
    if total <= EPS:
        raise ValueError('Контур вырожден: все вершины совпадают.')
    cumulative = [0.0]
    for s in spans:
        cumulative.append(cumulative[-1] + s)
    result = []
    for k in range(count):
        target = total * (k / float(count)) if closed else total * (k / float(count - 1))
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if cumulative[mid] <= target:
                lo = mid + 1
            else:
                hi = mid
        idx = max(0, lo - 1)
        if idx >= n:
            idx = n - 1
        span = cumulative[idx + 1] - cumulative[idx]
        local = 0.0 if span <= EPS else (target - cumulative[idx]) / span
        result.append(mix(coords[idx], coords[(idx + 1) % n], local))
    return result
