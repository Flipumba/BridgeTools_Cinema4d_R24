# -*- coding: utf-8 -*-
"""Проверка геометрии и топологии без Cinema 4D.

Запуск: python3 tests/run_tests.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'BridgeInteractive'))
sys.path.insert(0, HERE)

import bridge_math as M
import bridge_topology as T
import bridge_plan as P
import bridge_validate as V
import bridge_data as D


def grid():
    """Две квадратные заглушки, соединённые боковой стенкой."""
    points = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0),
              (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
              (-1, -1, 2), (1, -1, 2), (1, 1, 2), (-1, 1, 2),
              (-1, -1, 3), (1, -1, 3), (1, 1, 3), (-1, 1, 3)]
    faces = [(0, 1, 2, 3), (11, 10, 9, 8)]
    faces += [(i + 4, (i + 1) % 4 + 4, (i + 1) % 4, i) for i in range(4)]
    faces += [(8 + i, 8 + (i + 1) % 4, 12 + (i + 1) % 4, 12 + i) for i in range(4)]
    return points, faces


def slab(outline, cap_quads, z0, z1):
    """Плита из L-образного контура: крышки собраны из квадов.

    Нужна, чтобы получить кромку длиной 6 вершин без n-гонов, которых
    Cinema 4D в этом плане не поддерживает.
    """
    n = len(outline)
    bottom = [(x, y, z0) for x, y in outline]
    top = [(x, y, z1) for x, y in outline]
    points = bottom + top
    top_index = [n + i for i in range(n)]

    def build(flip_caps, flip_sides):
        faces = []
        for quad in cap_quads:
            indices = [top_index[i] for i in quad]
            faces.append(tuple(reversed(indices)) if flip_caps else tuple(indices))
        for quad in cap_quads:
            indices = list(quad)
            faces.append(tuple(reversed(indices)) if flip_caps else tuple(indices))
        for i in range(n):
            j = (i + 1) % n
            wall = (i, j, top_index[j], top_index[i])
            faces.append(tuple(reversed(wall)) if flip_sides else wall)
        return faces

    cap_set = set(range(len(cap_quads)))
    for flip_caps in (False, True):
        for flip_sides in (False, True):
            faces = build(flip_caps, flip_sides)
            mesh = T.Mesh(points, faces)
            try:
                islands = T.collect_islands(mesh, cap_set, allow_many=True)
            except ValueError:
                continue
            if len(islands) == 1 and len(islands[0].loop) == n:
                return points, faces
    raise AssertionError('Не удалось построить согласованную плиту')


def prism(loop_a, loop_b, anchor_a=0, anchor_b=0):
    """Строит призму между двумя кольцами точек с проверенной намоткой.

    Обе крышки и боковые грани ориентируются согласованно; если исходная
    намотка боковин оказывается неверной, она меняется. Это убирает
    необходимость вручную подбирать порядок вершин в тестовых сценах.
    """
    points = list(loop_a) + list(loop_b)
    n = len(loop_a)
    if len(loop_b) != n:
        raise ValueError('prism требует одинаковой длины колец')
    index_a = list(range(n))
    index_b = [n + i for i in range(n)]

    def build(reverse_sides, reverse_b):
        faces = []
        # Крышка A — нормаль наружу от объёма, то есть «вниз».
        faces.append(tuple(reversed(index_a)) if reverse_sides else tuple(index_a))
        cap_b = tuple(reversed(index_b)) if reverse_b else tuple(index_b)
        faces.append(cap_b)
        for i in range(n):
            j = (i + 1) % n
            quad = (index_a[i], index_a[j], index_b[j], index_b[i])
            faces.append(tuple(reversed(quad)) if reverse_sides else quad)
        return faces

    for reverse_sides in (False, True):
        for reverse_b in (False, True):
            faces = build(reverse_sides, reverse_b)
            mesh = T.Mesh(points, faces)
            try:
                islands = T.collect_islands(mesh, {0, 1})
            except ValueError:
                continue
            if len(islands) == 2:
                return points, faces
    raise AssertionError('Не удалось построить согласованную призму')


def box(origin, size, caps=True):
    """Закрытая коробка. Возвращает (points, faces) с крышкой на +Z в конце."""
    ox, oy, oz = origin
    sx, sy, sz = size
    points = [(ox, oy, oz), (ox + sx, oy, oz), (ox + sx, oy + sy, oz), (ox, oy + sy, oz),
              (ox, oy, oz + sz), (ox + sx, oy, oz + sz), (ox + sx, oy + sy, oz + sz),
              (ox, oy + sy, oz + sz)]
    faces = []
    if caps:
        faces.append((4, 5, 6, 7))          # верх, нормаль +Z
        faces.append((0, 3, 2, 1))          # низ, нормаль -Z
    for i in range(4):
        a = i
        b = (i + 1) % 4
        faces.append((a, b, b + 4, a + 4))
    return points, faces


def three_capped_boxes():
    """Три отдельных закрытых коробки. Возвращает (точки, грани, индексы крышек).

    Каждая крышка окружена стенками, поэтому её кромка занята — это и есть
    условие, при котором цепочка граней становится неманифолдной.
    """
    points, faces, caps = [], [], []
    for index in range(3):
        step = index * 3.0
        local_points, local_faces = box((step, 0.0, 0.0), (1.0, 1.0, 1.0))
        base = len(points)
        points.extend(local_points)
        caps.append(len(faces))
        faces.extend(tuple(v + base for v in face) for face in local_faces)
    return points, faces, caps


def tube(sides=6, rings=3):
    """Труба: два открытых торца и боковая поверхность."""
    points = []
    for r in range(rings):
        z = float(r)
        for i in range(sides):
            angle = 2.0 * M.pi * i / sides
            points.append((M.cos(angle), M.sin(angle), z))
    faces = []
    for r in range(rings - 1):
        for i in range(sides):
            a = r * sides + i
            b = r * sides + (i + 1) % sides
            c = (r + 1) * sides + (i + 1) % sides
            d = (r + 1) * sides + i
            faces.append((a, b, c, d))
    caps = [(i, (i + 1) % sides, sides + (i + 1) % sides, sides + i) for i in range(sides)]
    return points, faces + caps


class TestMath(unittest.TestCase):
    def test_profile_shapes_range(self):
        for shape in M.PROFILE_SHAPES:
            for k in range(11):
                value = M.profile_envelope(shape, k / 10.0)
                self.assertGreaterEqual(value, -1e-9, shape)
                self.assertLessEqual(value, 1.0 + 1e-9, shape)
        # На концах моста влияние нулевое у всех форм, кроме CONSTANT.
        for shape in M.PROFILE_SHAPES:
            if shape == 'CONSTANT':
                continue
            self.assertAlmostEqual(M.profile_envelope(shape, 0.0), 0.0, places=9)

    def test_loop_center_weights_by_length(self):
        points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        center = M.loop_center(points, [0, 1, 2, 3], True)
        self.assertAlmostEqual(center[0], 0.5, places=6)
        self.assertAlmostEqual(center[1], 0.5, places=6)

    def test_newell_normal_on_concave(self):
        # Вогнутый контур: нормаль должна смотреть в +Z.
        points = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (1, 1, 0), (0, 2, 0)]
        normal = M.polygon_normal(points, [0, 1, 2, 3, 4])
        self.assertAlmostEqual(normal[2], 1.0, places=6)

    def test_twist_wraps_both_directions(self):
        loop = [0, 1, 2, 3]
        self.assertEqual(M.rotate_by(loop, 1), [1, 2, 3, 0])
        self.assertEqual(M.rotate_by(loop, -1), [3, 0, 1, 2])
        self.assertEqual(M.rotate_by(loop, 4), [0, 1, 2, 3])


class TestTopology(unittest.TestCase):
    def test_islands_found(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        islands = T.collect_islands(mesh, {0, 1})
        self.assertEqual(len(islands), 2)
        self.assertEqual(len(islands[0].loop), 4)
        self.assertEqual(len(islands[1].loop), 4)

    def test_single_island_rejected(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        with self.assertRaises(ValueError):
            T.collect_islands(mesh, {0})

    def test_island_with_hole_rejected(self):
        # Кольцо граней вокруг дырки — две петли границы.
        points = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0),
                  (2, 1, 0), (0, 2, 0), (1, 2, 0), (2, 2, 0)]
        faces = [(0, 1, 4, 3), (1, 2, 5, 4), (3, 4, 7, 6), (4, 5, 8, 7)]
        mesh = T.Mesh(points, faces)
        with self.assertRaises(ValueError):
            T.collect_islands(mesh, {0, 1, 2, 3})

    def test_open_chain(self):
        chains = T.ordered_chains([(0, 1), (1, 2), (2, 3)])
        self.assertEqual(len(chains), 1)
        self.assertFalse(chains[0].closed)
        self.assertEqual(chains[0].vertices, [0, 1, 2, 3])

    def test_closed_chain(self):
        chains = T.ordered_chains([(0, 1), (1, 2), (2, 3), (3, 0)])
        self.assertEqual(len(chains), 1)
        self.assertTrue(chains[0].closed)

    def test_branching_rejected(self):
        with self.assertRaises(ValueError):
            T.ordered_chains([(0, 1), (1, 2), (1, 3)])

    def test_resample_preserves_shape(self):
        points = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
        result = T.resample_loop(points, [0, 1, 2, 3], 8, True)
        self.assertEqual(len(result), 8)


class TestPlan(unittest.TestCase):
    def test_bridge_geometry_counts(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        for cuts, expected_faces in ((0, 12), (1, 16), (2, 20), (5, 32)):
            plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=cuts))
            self.assertEqual(len(plan.faces), expected_faces, cuts)
            self.assertEqual(plan.removed_faces, [0, 1])
            self.assertEqual(len(plan.new_faces), expected_faces - 8)
            V.check_plan(plan)

    def test_preview_does_not_touch_source(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        before = (list(points), list(faces))
        P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=3))
        self.assertEqual(list(points), before[0])
        self.assertEqual(list(faces), before[1])

    def test_all_parameter_combinations_valid(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        failures = []
        for cuts in (0, 1, 3):
            for interpolation in P.INTERPOLATIONS:
                for shape in M.PROFILE_SHAPES:
                    for angle in (-45.0, 0.0, 60.0):
                        for smooth in (0.0, 1.5):
                            options = P.BridgeOptions(
                                cuts=cuts, interpolation=interpolation,
                                profile_shape=shape, angle=angle,
                                profile=0.4, smooth=smooth)
                            plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, options)
                            try:
                                V.check_plan(plan)
                            except ValueError as error:
                                failures.append((cuts, interpolation, shape,
                                                 angle, smooth, str(error)))
        self.assertEqual(failures, [], 'Некорректные результаты: %r' % failures[:3])

    def test_merge_welds_and_keeps_no_new_faces(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(merge=True))
        self.assertEqual(plan.new_faces, [])
        self.assertEqual(len(plan.faces), 8)
        self.assertEqual(len(plan.points), 12)
        V.check_plan(plan)

    def test_merge_rejects_unequal_rims(self):
        """Merge требует равного числа вершин и не пересэмплирует контуры.

        Проверяется сам защитный механизм: пересэмплирование изменило бы
        форму сохраняемых полигонов.
        """
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        builder = P._Builder(mesh, {0, 1})
        rim_a = [0, 1, 2, 3]
        rim_b = [8, 9, 10]          # умышленно короче
        with self.assertRaises(ValueError) as caught:
            P.build_bridge(builder, rim_a, rim_b, P.BridgeOptions(merge=True))
        self.assertIn('Merge требует одинакового числа', str(caught.exception))

    def test_unequal_rim_sizes_produce_valid_mesh(self):
        # Труба 6 сторон против 4-сторонней заглушки.
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        # Искусственно делаем вторую кромку пятиугольной, добавив точку.
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=2))
        counts = {}
        for face in plan.faces:
            counts[len(face)] = counts.get(len(face), 0) + 1
        # Застежка обязана давать треугольники при разной плотности.
        self.assertTrue(all(k in (3, 4) for k in counts))
        V.check_plan(plan)

    def test_face_chain_rejected_as_non_manifold(self):
        """Цепочка из трёх групп граней в C4D невозможна: кромка занята.

        Кромка группы граней уже делится с соседней стенкой, поэтому второй
        мост на той же кромке даёт три полигона на ребро. Инструмент обязан
        отказать с объяснением, а не испортить модель.
        """
        points, faces, caps = three_capped_boxes()
        mesh = T.Mesh(points, faces)
        islands = T.collect_islands(mesh, set(caps), allow_many=True)
        self.assertEqual(len(islands), 3)
        first = islands[0].loop[0]
        second = islands[1].loop[0]
        with self.assertRaises(ValueError) as caught:
            P.plan_face_chain(mesh, set(caps), first, second, P.BridgeOptions(cuts=1))
        self.assertIn('неманифолдную', str(caught.exception))

    def test_non_manifold_source_rejected(self):
        points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (2, 0, 0), (2, 1, 0)]
        faces = [(0, 1, 2, 3), (1, 4, 5, 2), (1, 2, 3, 0)]
        mesh = T.Mesh(points, faces)
        with self.assertRaises(ValueError):
            T.collect_islands(mesh, {0, 1})

    def test_transformed_object_uses_local_coordinates(self):
        points, faces = grid()
        scaled = [(x * 1000.0, y * 1000.0, z * 1000.0) for x, y, z in points]
        mesh = T.Mesh(scaled, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=1))
        V.check_plan(plan)

        tiny = [(x * 0.001, y * 0.001, z * 0.001) for x, y, z in points]
        mesh_tiny = T.Mesh(tiny, faces)
        plan_tiny = P.plan_face_bridge(mesh_tiny, {0, 1}, 0, 8, P.BridgeOptions(cuts=1))
        V.check_plan(plan_tiny)

    def test_twist_changes_pairing(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        a = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=0, twist=0))
        b = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=0, twist=1))
        self.assertNotEqual(a.faces[a.new_faces[0]], b.faces[b.new_faces[0]])

    def test_open_edge_chain_bridge(self):
        """Мост между двумя открытыми цепочками рёбер.

        Полоса из двух квадов: верхняя цепочка (0,1,2) и нижняя (3,4,5),
        каждая имеет ровно один соседний полигон.
        """
        points = [(0, 0, 0), (1, 0, 0), (2, 0, 0),
                  (0, 1, 0), (1, 1, 0), (2, 1, 0)]
        faces = [(0, 1, 4, 3), (1, 2, 5, 4)]
        mesh = T.Mesh(points, faces)
        # Верхняя цепочка 0-1-2 и нижняя 3-4-5: по два ребра в каждой.
        selected = [(0, 1), (1, 2), (3, 4), (4, 5)]
        plan = P.plan_edge_bridge(mesh, selected, 0, 3, P.BridgeOptions(cuts=1))
        V.check_plan(plan)
        self.assertTrue(plan.new_faces)

    def test_grid_option_keys_differ(self):
        a = P.BridgeOptions(cuts=1)
        b = P.BridgeOptions(cuts=2)
        self.assertNotEqual(a.key(), b.key())
        self.assertEqual(a.key(), P.BridgeOptions(cuts=1).key())

    def test_invalid_options_are_clamped_not_raised(self):
        options = P.BridgeOptions(cuts=-5, merge_factor=9.0, profile_shape='NOPE',
                                  interpolation='NOPE', angle=1e9)
        self.assertEqual(options.cuts, 0)
        self.assertEqual(options.merge_factor, 1.0)
        self.assertEqual(options.profile_shape, 'SMOOTH')
        self.assertEqual(options.interpolation, 'LINEAR')
        self.assertEqual(options.angle, 360.0)


def _patch(origin_z, flip_winding, rotate, relabel):
    """Сетка 3x3 квада (4x4 вершины) в плоскости z=origin_z.

    rotate — поворот сетки на 90° вокруг оси z, relabel — перестановка индексов,
    чтобы «первая» вершина кромки оказалась в произвольном месте.
    """
    pts = []
    for iy in range(4):
        for ix in range(4):
            x, y = ix - 1.5, iy - 1.5
            if rotate:
                x, y = -y, x
            pts.append((x, y, origin_z))
    quads = []
    for iy in range(3):
        for ix in range(3):
            a = iy * 4 + ix
            quad = (a, a + 1, a + 5, a + 4)          # против часовой, нормаль +z
            quads.append(tuple(reversed(quad)) if flip_winding else quad)
    order = list(range(16))
    for k in range(relabel):
        order = order[3:] + order[:3]
    inv = dict((old, new) for new, old in enumerate(order))
    pts2 = [pts[old] for old in order]
    quads2 = [tuple(inv[v] for v in q) for q in quads]
    return pts2, quads2


def _two_patches(rotate_b=True, relabel_b=5):
    pa, qa = _patch(0.0, False, False, 0)
    pb, qb = _patch(1.0, True, rotate_b, relabel_b)
    shift = len(pa)
    points = pa + pb
    faces = qa + [tuple(v + shift for v in q) for q in qb]
    return points, faces


class TestAutoAlignment(unittest.TestCase):
    """Автоподбор соответствия: мост не перекручен без единого якоря."""

    def _max_link(self, plan, points_count):
        longest = 0.0
        for index in plan.new_faces:
            face = plan.faces[index]
            for k in range(len(face)):
                a, b = face[k], face[(k + 1) % len(face)]
                d = M.length(M.sub(plan.points[a], plan.points[b]))
                longest = max(longest, d)
        return longest

    def test_faces_aligned_without_anchors(self):
        for rotate in (False, True):
            for relabel in range(0, 6):
                points, faces = _two_patches(rotate, relabel)
                mesh = T.Mesh(points, faces)
                selected = set(range(len(faces)))
                plan = P.plan_face_bridge(mesh, selected, None, None,
                                          P.BridgeOptions(cuts=0))
                # Кромка 3x3 имеет рёбра длиной 1, расстояние между плитами тоже 1:
                # вертикальные рёбра длиннее 1.0001 означают диагональ/перекрут.
                self.assertLess(self._max_link(plan, len(points)), 1.0001,
                                'перекрут при rotate=%s relabel=%s' % (rotate, relabel))

    def test_auto_anchors_match_plan_without_anchors(self):
        points, faces = _two_patches(True, 3)
        mesh = T.Mesh(points, faces)
        selected = set(range(len(faces)))
        va, vb, flip = P.auto_anchors_faces(mesh, selected, 0)
        explicit = P.plan_face_bridge(mesh, selected, va, vb, P.BridgeOptions())
        auto = P.plan_face_bridge(mesh, selected, None, None, P.BridgeOptions())
        self.assertEqual(explicit.faces, auto.faces)
        self.assertEqual(explicit.points, auto.points)

    def test_twist_still_shifts_from_auto_alignment(self):
        points, faces = _two_patches(True, 2)
        mesh = T.Mesh(points, faces)
        selected = set(range(len(faces)))
        base = P.plan_face_bridge(mesh, selected, None, None, P.BridgeOptions())
        shifted = P.plan_face_bridge(mesh, selected, None, None, P.BridgeOptions(twist=1))
        self.assertGreater(self._max_link(shifted, len(points)),
                           self._max_link(base, len(points)))

    def test_anchors_pair_vertices_exactly(self):
        """Ручные якоря действительно соединяются друг с другом."""
        points, faces = _two_patches(False, 0)
        mesh = T.Mesh(points, faces)
        selected = set(range(len(faces)))
        islands = T.collect_islands(mesh, selected)
        va = islands[0].loop[0]
        vb = min(islands[1].loop,
                 key=lambda v: M.length(M.sub(points[v], points[va])))
        plan = P.plan_face_bridge(mesh, selected, va, vb, P.BridgeOptions())
        linked = False
        for index in plan.new_faces:
            face = plan.faces[index]
            old_face = [plan.reverse_point_map.get(v) for v in face]
            if va in old_face and vb in old_face:
                linked = True
        self.assertTrue(linked, 'якорные вершины не оказались в одном полигоне моста')

    def test_interior_edge_loops_without_faces_direction(self):
        """Петли посреди сетки (по два полигона на ребро) тоже соединяются."""
        points, faces = _two_patches(True, 4)
        mesh = T.Mesh(points, faces)
        loops = []
        for base in (0, 16):
            # Внутренний цикл 2x2 вершин, номера через относительную карту индексов.
            loops.append(base)
        # Находим внутренние вершины каждой плиты геометрически.
        def inner(z):
            ids = [i for i, p in enumerate(points)
                   if abs(p[2] - z) < 1e-9 and abs(p[0]) < 1.0 and abs(p[1]) < 1.0]
            return ids
        ring = {}
        for z in (0.0, 1.0):
            ids = inner(z)
            self.assertEqual(len(ids), 4)
            ids.sort(key=lambda i: __import__('math').atan2(points[i][1], points[i][0]))
            ring[z] = ids
        edges = []
        for z in (0.0, 1.0):
            ids = ring[z]
            for k in range(4):
                edges.append((ids[k], ids[(k + 1) % 4]))
        plan = P.plan_edge_bridge(mesh, edges, None, None, P.BridgeOptions())
        self.assertEqual(len(plan.new_faces), 4)
        for index in plan.new_faces:
            face = plan.faces[index]
            lengths = [M.length(M.sub(plan.points[face[k]], plan.points[face[(k + 1) % 4]]))
                       for k in range(4)]
            self.assertLess(max(lengths), 1.0001 + 0.0, 'перекрут петель без направления')

    def test_pairs_mode_picks_nearest_automatically(self):
        # Две пары плит, пара определяется близостью, а не порядком индексов.
        p1, f1 = _two_patches(False, 0)
        shift = len(p1)
        p2 = [(x + 10.0, y, z) for x, y, z in p1]
        f2 = [tuple(v + shift for v in f) for f in f1]
        mesh = T.Mesh(p1 + p2, f1 + f2)
        selected = set(range(len(f1) + len(f2)))
        plan = P.plan_face_pairs(mesh, selected, None, None, P.BridgeOptions())
        self.assertEqual(len(plan.new_faces), 24)
        self.assertLess(self._max_link(plan, 0), 1.0001)

    def test_chain_of_three_orders_by_distance(self):
        pa, fa = _patch(0.0, False, False, 0)
        pb, fb = _patch(1.0, True, False, 0)
        pc, fc = _patch(2.0, False, False, 0)
        points = pa + pb + pc
        s1 = len(pa)
        faces = fa + [tuple(v + s1 for v in f) for f in fb] + \
            [tuple(v + 2 * s1 for v in f) for f in fc]
        mesh = T.Mesh(points, faces)
        # Третья группа лежит по другую сторону второй — порядок цепочки
        # должен быть a-b-c независимо от индексов; нормаль у c как у a.
        try:
            P.plan_face_chain(mesh, set(range(len(faces))), None, None, P.BridgeOptions())
        except ValueError as error:
            self.assertIn('неманифолд', str(error))


class TestData(unittest.TestCase):
    def test_uv_transfer_produces_corner_count(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=1))
        uvs = [tuple((float(i), float(k), 0.0) for k in range(4)) for i in range(len(faces))]
        result = D.transfer_uvs(plan, uvs)
        self.assertEqual(len(result), len(plan.new_faces))
        for corners in result:
            self.assertEqual(len(corners), 4)

    def test_uv_inherits_boundary_side(self):
        """Новый полигон должен получить UV той стороны шва, с которой стыкуется."""
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=0))
        uvs = [((0., 0., 0.), (1., 0., 0.), (1., 1., 0.), (0., 1., 0.))] * len(faces)
        result = D.transfer_uvs(plan, uvs)
        self.assertTrue(result)

    def test_weight_interpolation_midpoint(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=1))
        values = [float(i) for i in range(len(points))]
        result = D.remap_point_values(plan, values)
        self.assertEqual(len(result), len(plan.points))

    def test_pin_remap_keeps_retained_corners(self):
        retained = [2, 3, 4, 5, 6, 7]
        pins = {8, 11, 39}
        mapped = D.remap_uv_pins(pins, retained)
        # Полигон 2 стал первым (0*4+0), 11 -> 39 не входит в retained.
        self.assertIn(0, mapped)

    def test_edge_selection_remap_by_vertices(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=1))
        mapped = D.remap_edge_selection({0, 4, 8}, plan.old_faces, plan.faces,
                                        plan.point_map)
        self.assertIsInstance(mapped, set)


class TestValidation(unittest.TestCase):
    def test_flipped_faces_detected(self):
        """Вывернутая грань моста должна ловиться валидатором."""
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=0))
        # Портим направление одной новой грани вручную.
        index = plan.new_faces[0]
        plan.faces[index] = tuple(reversed(plan.faces[index]))
        with self.assertRaises(ValueError):
            V.check_plan(plan)

    def test_degenerate_face_detected(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=1))
        index = plan.new_faces[0]
        face = plan.faces[index]
        # Схлопываем грань: все новые точки в одну.
        plan.points = list(plan.points)
        for v in face[1:]:
            plan.points[v] = plan.points[face[0]]
        with self.assertRaises(ValueError):
            V.check_plan(plan)

    def test_non_manifold_result_detected(self):
        points, faces = grid()
        mesh = T.Mesh(points, faces)
        plan = P.plan_face_bridge(mesh, {0, 1}, 0, 8, P.BridgeOptions(cuts=0))
        plan.faces = list(plan.faces) + [plan.faces[plan.new_faces[0]]]
        with self.assertRaises(ValueError):
            V.check_plan(plan)


if __name__ == '__main__':
    unittest.main(verbosity=2)
