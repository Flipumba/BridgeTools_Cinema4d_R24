# -*- coding: utf-8 -*-
"""Интеграционные тесты плагина на имитации API Cinema 4D.

Проверяют поведение инструмента целиком: клики, подсветку, предпросмотр,
применение, Undo, перенос UV/весов и отсутствие изменений при отмене.

ЭТО НЕ ТЕСТ CINEMA 4D. Имитация повторяет только те вызовы, которые делает
плагин, и падает при обращении к несуществующим методам.
"""
import os
import runpy
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'BridgeInteractive'))

import mock_c4d

c4d, documents, gui = mock_c4d.install()

PLUGIN = os.path.join(ROOT, 'BridgeInteractive', 'bridge_interactive.pyp')
MODULE = runpy.run_path(PLUGIN, run_name='bridge_test')
BridgeTool = MODULE['BridgeTool']


class Context(dict):
    def GetId(self):
        return 0


def scene(pins=(8, 11, 39)):
    """Документ с эталонной сценой: две заглушки и соединительная стенка."""
    doc = mock_c4d.Document()
    documents.SetActiveDocument(doc)
    points, faces = mock_c4d.make_grid_scene()
    obj = mock_c4d.build_object(points, faces, pins=pins)
    doc.InsertObject(obj)
    doc.SetActiveObject(obj)
    obj.GetPolygonS().Select(0)
    obj.GetPolygonS().Select(1)
    return doc, obj


def click(tool, doc, bd, x, y):
    tool.GetCursorInfo(doc, None, bd, x, y, Context())
    tool.MouseInput(doc, None, bd, None, {
        c4d.BFM_INPUT_CHANNEL: c4d.BFM_INPUT_MOUSELEFT,
        c4d.BFM_INPUT_X: x, c4d.BFM_INPUT_Y: y,
    })


def tag_of(obj, tag_type):
    for tag in obj.GetTags():
        if tag.GetType() == tag_type:
            return tag
    return None


class TestToolFlow(unittest.TestCase):

    def setUp(self):
        gui.messages.clear()
        self.doc, self.obj = scene()
        self.tool = BridgeTool()
        self.tool.engine = 1          # собственный движок: тесты ниже проверяют его
        self.tool.InitTool(self.doc, None, None)
        self.bd = mock_c4d.BaseDraw()

    def test_two_clicks_build_preview_without_touching_object(self):
        before_faces = self.obj.GetPolygonCount()
        before_points = self.obj.GetPointCount()
        click(self.tool, self.doc, self.bd, 0, 0)
        self.assertEqual(self.tool.anchors, [0])
        click(self.tool, self.doc, self.bd, 0, 3)
        self.assertEqual(len(self.tool.anchors), 2)
        self.assertIsNotNone(self.tool.plan)
        self.assertEqual(self.obj.GetPolygonCount(), before_faces)
        self.assertEqual(self.obj.GetPointCount(), before_points)

    def test_hover_highlights_candidate(self):
        self.tool.cuts = 1
        click(self.tool, self.doc, self.bd, 0, 0)
        self.tool.GetCursorInfo(self.doc, None, self.bd, 0, 3, Context())
        self.assertIsNotNone(self.tool.hover_second)
        self.assertIsNotNone(self.tool.plan)

    def test_preview_draws_removed_and_new_geometry(self):
        self.tool.cuts = 1
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.tool.Draw(self.doc, None, self.bd, None, None, 0)
        self.assertTrue(self.bd.lines, 'предпросмотр не нарисовал рёбра')
        self.assertTrue(self.bd.polygons, 'предпросмотр не нарисовал поверхность')
        # Удаляемые грани тоже должны попасть в отрисовку (красным пером).
        reds = [pen for pen in (self.bd.pen,) if pen is not None]
        self.assertTrue(reds)

    def test_removed_faces_shown_when_enabled(self):
        self.tool.cuts = 1
        self.tool.show_removed = True
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        bd = mock_c4d.BaseDraw()
        self.tool.Draw(self.doc, None, bd, None, None, 0)
        # Красные линии удаляемых граней идут первыми: 2 заглушки * 4 ребра.
        self.assertGreaterEqual(len(bd.lines), 8)

    def test_escape_clears_selection_and_keeps_object(self):
        click(self.tool, self.doc, self.bd, 0, 0)
        before = self.obj.GetPolygonCount()
        handled = self.tool.KeyboardInput(self.doc, None, self.bd, None,
                                         {c4d.BFM_INPUT_CHANNEL: c4d.KEY_ESC})
        self.assertTrue(handled)
        self.assertEqual(self.tool.anchors, [])
        self.assertEqual(self.obj.GetPolygonCount(), before)

    def test_apply_creates_bridge_and_single_undo(self):
        self.tool.cuts = 1
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), 16)
        self.assertEqual(self.obj.GetPointCount(), 20)
        self.assertEqual(self.doc.undo_started, 1)
        self.assertGreaterEqual(len(self.doc.undo_registered), 3)

    def test_undo_restores_geometry(self):
        self.tool.cuts = 1
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), 16)
        self.assertTrue(self.doc.DoUndo())
        self.assertEqual(self.obj.GetPolygonCount(), 10)

    def test_uv_tag_grows_with_new_faces(self):
        self.tool.cuts = 2
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.tool.apply()
        uv = tag_of(self.obj, c4d.Tuvw)
        self.assertEqual(uv.GetDataCount(), self.obj.GetPolygonCount())
        # Сохранённый полигон 2 стал первым и обязан сохранить свои UV.
        self.assertAlmostEqual(uv.GetSlow(0)['a'].x, 2.0, places=6)

    def test_weight_tag_matches_point_count(self):
        self.tool.cuts = 1
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.tool.apply()
        weights = tag_of(self.obj, c4d.Tvertexmap)
        self.assertEqual(len(weights.values), self.obj.GetPointCount())

    def test_pins_remapped_not_lost(self):
        self.tool.cuts = 1
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.tool.apply()
        uv = tag_of(self.obj, c4d.Tuvw)
        pins = uv.GetPinSelection()
        self.assertIsNotNone(pins)
        # Закрепления пересчитаны на новые индексы полигонов: старый полигон 8
        # (углы 8, 11) стал полигоном 0, старый 9 (угол 39) — полигоном 7.
        self.assertEqual(sorted(pins._sel), [0, 3, 31])

    def test_ngon_object_rejected_without_changes(self):
        self.obj.GetNgonCount = lambda: 3
        self.tool.InitTool(self.doc, None, None)
        self.assertIsNotNone(self.tool.preview_error)
        with self.assertRaises(Exception):
            self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), 10)

    def test_field_driven_tag_rejected(self):
        class FieldVariableTag(mock_c4d.VariableTag):
            """Тег с включёнными полями: плагин обязан отказать."""

            def __getitem__(self, key):
                return True

        self.obj.InsertTag(FieldVariableTag(c4d.Tvertexmap, 16))
        with self.assertRaises(Exception):
            self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), 10)
        self.tool.InitTool(self.doc, None, None)
        self.assertIsNotNone(self.tool.preview_error)

    def test_unknown_tag_rejected(self):
        class Custom(object):
            def GetType(self):
                return 999999

            def GetName(self):
                return 'Spline Tag'

        self.obj.InsertTag(Custom())
        with self.assertRaises(Exception):
            self.tool.apply()
        self.tool.InitTool(self.doc, None, None)
        self.assertIsNotNone(self.tool.preview_error)
        self.assertEqual(self.obj.GetPolygonCount(), 10)

    def test_stale_selection_invalidates_context(self):
        click(self.tool, self.doc, self.bd, 0, 0)
        # Меняем количество полигонов — контекст должен сброситься.
        self.obj.ResizeObject(16, 11)
        self.tool.refresh_if_stale(self.doc)
        self.assertEqual(self.tool.anchors, [])

    def test_navigation_mouse_is_not_swallowed(self):
        handled = self.tool.MouseInput(self.doc, None, self.bd, None, {
            c4d.BFM_INPUT_CHANNEL: 9999,
        })
        self.assertFalse(handled, 'навигация вьюпорта не должна перехватываться')

    def test_apply_without_selection_reports_error(self):
        self.obj.GetPolygonS().DeselectAll()
        with self.assertRaises(Exception):
            self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), 10)

    def test_third_click_restarts_selection(self):
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.assertEqual(len(self.tool.anchors), 2)
        click(self.tool, self.doc, self.bd, 0, 0)
        self.assertEqual(len(self.tool.anchors), 1)

    def test_mode_change_resets_anchors(self):
        import bridge_dialog
        click(self.tool, self.doc, self.bd, 0, 0)
        self.tool.on_options_changed(bridge_dialog.Param.SOURCE)
        self.assertEqual(self.tool.anchors, [])

    def test_drag_without_clamp_at_value_limit(self):
        """Перетаскивание упирается в предел параметра, а не в край экрана.

        Значение должно дойти до верхней границы и остаться там, а не
        «отскочить» или застрять на малом смещении.
        """
        self.tool.drag_target = 0     # Разрезы
        self.tool.cuts = 0
        self.tool.drag_parameter(FakeWindow([500]), {
            c4d.BFM_INPUT_X: 0, c4d.BFM_INPUT_Y: 0})
        self.assertEqual(self.tool.cuts, 125)

    def test_drag_escape_restores_value(self):
        self.tool.drag_target = 0
        self.tool.cuts = 3
        self.tool.drag_parameter(FakeWindow([50], escape=True), {
            c4d.BFM_INPUT_X: 0, c4d.BFM_INPUT_Y: 0})
        self.assertEqual(self.tool.cuts, 3)


class TestAutoFlow(unittest.TestCase):
    """Мост строится по выделению без единого щелчка по вершинам."""

    def setUp(self):
        gui.messages.clear()
        self.doc, self.obj = scene()
        self.tool = BridgeTool()
        self.tool.engine = 1          # собственный движок: тесты ниже проверяют его
        self.tool.InitTool(self.doc, None, None)
        self.bd = mock_c4d.BaseDraw()

    def test_preview_appears_on_activation(self):
        self.assertIsNotNone(self.tool.plan)
        self.assertIsNone(self.tool.preview_error)
        self.assertEqual(self.tool.anchors, [])

    def test_apply_without_clicks(self):
        self.tool.cuts = 1
        self.tool.request_preview()
        self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), 16)
        self.assertEqual(self.obj.GetPointCount(), 20)
        self.assertTrue(self.doc.DoUndo())
        self.assertEqual(self.obj.GetPolygonCount(), 10)

    def test_enter_key_applies(self):
        handled = self.tool.KeyboardInput(self.doc, None, self.bd, None,
                                         {c4d.BFM_INPUT_CHANNEL: c4d.KEY_ENTER})
        self.assertTrue(handled)
        self.assertEqual(self.obj.GetPolygonCount(), 8 + 4)
        self.assertEqual(gui.messages, [])

    def test_click_away_from_vertices_is_silent(self):
        self.tool.MouseInput(self.doc, None, self.bd, None, {
            c4d.BFM_INPUT_CHANNEL: c4d.BFM_INPUT_MOUSELEFT,
            c4d.BFM_INPUT_X: 9999, c4d.BFM_INPUT_Y: 9999})
        self.assertEqual(gui.messages, [])
        self.assertIsNotNone(self.tool.plan)

    def test_param_change_rebuilds_preview(self):
        import bridge_dialog
        before = len(self.tool.plan.faces)
        self.tool.cuts = 2
        self.tool.on_options_changed(bridge_dialog.Param.CUTS)
        self.assertGreater(len(self.tool.plan.faces), before)

    def test_selection_change_updates_preview(self):
        self.obj.GetPolygonS().DeselectAll()
        self.tool.refresh_if_stale(self.doc)
        self.assertIsNone(self.tool.plan)
        self.assertIsNotNone(self.tool.preview_error)
        self.obj.GetPolygonS().Select(0)
        self.obj.GetPolygonS().Select(1)
        self.tool.refresh_if_stale(self.doc)
        self.assertIsNotNone(self.tool.plan)

    def test_manual_anchors_override_and_escape_restores_auto(self):
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.assertEqual(len(self.tool.anchors), 2)
        self.tool.KeyboardInput(self.doc, None, self.bd, None,
                                {c4d.BFM_INPUT_CHANNEL: c4d.KEY_ESC})
        self.assertEqual(self.tool.anchors, [])
        self.assertIsNotNone(self.tool.plan)

    def test_source_follows_document_mode(self):
        self.doc.SetMode(c4d.Medges)
        self.tool.refresh_if_stale(self.doc)
        self.assertEqual(self.tool.source, 1)
        self.assertIsNotNone(self.tool.preview_error)   # рёбра не выделены
        self.doc.SetMode(c4d.Mpolygons)
        self.tool.refresh_if_stale(self.doc)
        self.assertEqual(self.tool.source, 0)
        self.assertIsNotNone(self.tool.plan)

    def test_status_text_explains_state(self):
        self.assertIn('Enter', self.tool.status_text())
        self.obj.GetPolygonS().DeselectAll()
        self.tool.refresh_if_stale(self.doc)
        self.assertTrue(self.tool.status_text().startswith('Bridge:'))


class FakeWindow(object):
    """Окно с заранее заданной последовательностью горизонтальных смещений."""

    def __init__(self, deltas, escape=False):
        self._deltas = list(deltas)
        self._index = 0
        self._escape = escape

    def MouseDragStart(self, button, x, y, flags):
        return True

    def MouseDrag(self):
        if self._index < len(self._deltas):
            delta = self._deltas[self._index]
            self._index += 1
            return c4d.MOUSEDRAGRESULT_CONTINUE, delta, 0, {}
        return c4d.MOUSEDRAGRESULT_FINISHED, 0, 0, {}

    def MouseDragEnd(self):
        return c4d.MOUSEDRAGRESULT_ESCAPE if self._escape else c4d.MOUSEDRAGRESULT_FINISHED




class TestEdgeMode(unittest.TestCase):
    """Режим «выделенные рёбра»: открытые цепочки поверх существующих полигонов."""

    def setUp(self):
        gui.messages.clear()
        points = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0)]
        faces = [(0, 1, 4, 3), (1, 2, 5, 4)]
        self.doc = mock_c4d.Document()
        documents.SetActiveDocument(self.doc)
        self.obj = mock_c4d.PolygonObject(len(points), len(faces))
        self.obj.SetAllPoints([c4d.Vector(*p) for p in points])
        for index, face in enumerate(faces):
            self.obj.SetPolygon(index, c4d.CPolygon(*face))
        self.doc.InsertObject(self.obj)
        self.doc.SetActiveObject(self.obj)
        # Верхняя цепочка (0,1,2) и нижняя (4,3)... (5,4) — слоты 0 и 2.
        for slot in (0, 2):
            self.obj.GetEdgeS().Select(4 * 0 + slot)
            self.obj.GetEdgeS().Select(4 * 1 + slot)
        self.tool = BridgeTool()
        self.tool.engine = 1          # собственный движок: тесты ниже проверяют его
        self.tool.InitTool(self.doc, None, None)
        self.tool.input_mode = 2
        self.tool.cuts = 1
        self.bd = mock_c4d.BaseDraw()
        self.tool.capture(self.doc, force=True)

    def test_two_open_chains_detected(self):
        self.assertEqual(len(self.tool.rims), 2)
        self.assertFalse(self.tool.rims[0][1])
        self.assertEqual(len(self.tool.rims[0][0]), 3)

    def test_bridge_between_chains_creates_faces(self):
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 1)
        self.assertIsNotNone(self.tool.plan)
        self.assertEqual(len(self.tool.plan.new_faces), 4)
        self.assertEqual(self.tool.plan.removed_faces, [])
        self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), 6)

    def test_branching_edges_rejected(self):
        self.obj.GetEdgeS().Select(4 * 0 + 1)   # лишнее ребро даёт ветвление
        with self.assertRaises(Exception):
            self.tool.capture(self.doc, force=True)

class TestNativeEngine(unittest.TestCase):
    """Встроенный Bridge Cinema 4D: N-гоны и теги, которых собственный движок не умеет."""

    def setUp(self):
        gui.messages.clear()
        c4d.utils.calls.clear()
        c4d.utils.fail = False
        c4d.utils.noop = False
        self.doc, self.obj = scene()
        self.tool = BridgeTool()                 # движок по умолчанию — встроенный
        self.tool.InitTool(self.doc, None, None)
        self.bd = mock_c4d.BaseDraw()

    def call(self):
        self.assertEqual(len(c4d.utils.calls), 1)
        return c4d.utils.calls[0]

    def test_native_is_default_engine(self):
        self.assertEqual(self.tool.engine, 0)
        self.assertEqual(self.tool.effective_engine(), 'native')

    def test_ngon_object_works(self):
        self.obj.GetNgonCount = lambda: 3
        self.tool.InitTool(self.doc, None, None)
        self.assertIsNone(self.tool.preview_error)
        self.assertIsNotNone(self.tool.plan)
        self.tool.apply()
        self.assertEqual(self.call()['command'], c4d.ID_MODELING_BRIDGE_TOOL)
        self.assertEqual(gui.messages, [])

    def test_any_tag_is_accepted(self):
        class Custom(object):
            def GetType(self):
                return 424242

            def GetName(self):
                return 'Чужой тег'
        class FieldDriven(mock_c4d.VariableTag):
            def __getitem__(self, key):
                return True      # поля включены: собственный движок такой тег отклонил бы
        tags_before = len(self.obj.GetTags())
        self.obj.InsertTag(Custom())
        self.obj.InsertTag(FieldDriven(c4d.Tvertexmap, 16))
        self.tool.InitTool(self.doc, None, None)
        self.assertIsNone(self.tool.preview_error)
        self.tool.apply()
        self.assertEqual(len(self.obj.GetTags()), tags_before + 2)
        self.assertEqual(len(c4d.utils.calls), 1)

    def test_own_engine_still_refuses_ngons_and_explains_how_to_continue(self):
        self.tool.engine = 1
        self.obj.GetNgonCount = lambda: 3
        self.tool.InitTool(self.doc, None, None)
        self.assertIn('Встроенный Bridge', self.tool.preview_error)

    def test_settings_passed_to_native_bridge(self):
        self.tool.cuts = 3
        self.tool.tension = 50.0
        self.tool.curve_mode = 1
        self.tool.flip = True
        self.tool.delete_faces = False
        self.tool.apply()
        bc = self.call()['bc']
        self.assertEqual(self.call()['mode'], c4d.MODELINGCOMMANDMODE_POLYGONSELECTION)
        self.assertEqual(self.call()['list'], [self.obj])
        self.assertEqual(bc[c4d.MDATA_BRIDGE_SUBDIVISION], 3)
        self.assertAlmostEqual(bc[c4d.MDATA_BRIDGE_TENSION], 0.5)
        self.assertEqual(bc[c4d.MDATA_BRIDGE_BOTH_MODE], c4d.MDATA_BRIDGE_MODE_NORMAL)
        self.assertTrue(bc[c4d.MDATA_BRIDGE_BOTH_FLIP])
        self.assertFalse(bc[c4d.MDATA_BRIDGE_DELETE])
        self.assertTrue(bc[c4d.MDATA_BRIDGE_FIRST_SELECT_ONLY])
        self.assertTrue(bc[c4d.MDATA_BRIDGE_SECOND_SELECT_ONLY])
        for ident in (c4d.MDATA_BRIDGE_OBJINDEX1, c4d.MDATA_BRIDGE_OBJINDEX2):
            self.assertIs(bc[ident], self.obj)

    def test_elements_belong_to_the_two_islands(self):
        self.tool.apply()
        bc = self.call()['bc']
        faces = [(p.a, p.b, p.c, p.d) for p in self.obj.GetAllPolygons()]
        e1, e2 = bc[c4d.MDATA_BRIDGE_ELEMENT1], bc[c4d.MDATA_BRIDGE_ELEMENT2]
        self.assertEqual(sorted((e1, e2)), [0, 1])
        v1, v2 = bc[c4d.MDATA_BRIDGE_ELEMENT3], bc[c4d.MDATA_BRIDGE_ELEMENT4]
        self.assertIn(v1, faces[e1])
        self.assertIn(v2, faces[e2])

    def test_twist_moves_second_anchor_along_rim(self):
        self.tool.apply()
        base = self.call()['bc'][c4d.MDATA_BRIDGE_ELEMENT4]
        c4d.utils.calls.clear()
        self.doc, self.obj = scene()
        self.tool.InitTool(self.doc, None, None)
        self.tool.twist = 1
        self.tool.apply()
        shifted = self.call()['bc'][c4d.MDATA_BRIDGE_ELEMENT4]
        self.assertNotEqual(base, shifted)
        faces = [(p.a, p.b, p.c, p.d) for p in self.obj.GetAllPolygons()]
        e2 = self.call()['bc'][c4d.MDATA_BRIDGE_ELEMENT2]
        self.assertIn(shifted, faces[e2])

    def test_manual_anchors_are_used(self):
        click(self.tool, self.doc, self.bd, 0, 0)
        click(self.tool, self.doc, self.bd, 0, 3)
        self.assertEqual(len(self.tool.anchors), 2)
        first, second = self.tool.anchors
        self.tool.apply()
        bc = self.call()['bc']
        self.assertEqual(bc[c4d.MDATA_BRIDGE_ELEMENT3], first)
        self.assertEqual(bc[c4d.MDATA_BRIDGE_ELEMENT4], second)

    def test_single_undo_step_registers_object(self):
        before = self.doc.undo_started
        self.tool.apply()
        self.assertEqual(self.doc.undo_started, before + 1)
        self.assertIn(self.obj, self.doc.undo_registered)

    def test_failed_command_is_rolled_back(self):
        count = self.obj.GetPolygonCount()
        c4d.utils.fail = True
        with self.assertRaises(Exception):
            self.tool.apply()
        self.assertEqual(self.obj.GetPolygonCount(), count)
        self.assertGreaterEqual(self.doc.undo_calls, 1)

    def test_command_that_builds_nothing_is_reported(self):
        c4d.utils.noop = True
        with self.assertRaises(Exception) as ctx:
            self.tool.apply()
        self.assertIn('ничего не построил', str(ctx.exception))
        self.assertGreaterEqual(self.doc.undo_calls, 1)

    def test_pair_and_chain_modes_fall_back_to_own_engine(self):
        self.tool.contour_mode = 1
        self.assertEqual(self.tool.effective_engine(), 'own')
        self.assertIn('Попарно', self.tool.engine_note())

    def test_missing_constants_fall_back_to_own_engine(self):
        saved = c4d.MDATA_BRIDGE_FIRST_SELECT_ONLY
        del c4d.MDATA_BRIDGE_FIRST_SELECT_ONLY
        try:
            self.assertEqual(self.tool.effective_engine(), 'own')
            self.assertIn('недоступен', self.tool.engine_note())
        finally:
            c4d.MDATA_BRIDGE_FIRST_SELECT_ONLY = saved

    def test_status_text_mentions_native_engine(self):
        self.assertIn('встроенный', self.tool.status_text())

    def test_after_apply_status_confirms_native_bridge(self):
        self.tool.apply()
        self.assertIn('встроенным Bridge', self.tool.status_text())


class TestNativeEdges(unittest.TestCase):
    """Встроенный Bridge в режиме рёбер и точек."""

    def setUp(self):
        gui.messages.clear()
        c4d.utils.calls.clear()
        c4d.utils.fail = False
        c4d.utils.noop = False
        points = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0)]
        faces = [(0, 1, 4, 3), (1, 2, 5, 4)]
        self.doc = mock_c4d.Document()
        documents.SetActiveDocument(self.doc)
        self.obj = mock_c4d.PolygonObject(len(points), len(faces))
        self.obj.SetAllPoints([c4d.Vector(*p) for p in points])
        for index, face in enumerate(faces):
            self.obj.SetPolygon(index, c4d.CPolygon(*face))
        self.doc.InsertObject(self.obj)
        self.doc.SetActiveObject(self.obj)
        self.doc.SetMode(c4d.Medges)
        for slot in (0, 2):
            self.obj.GetEdgeS().Select(4 * 0 + slot)
            self.obj.GetEdgeS().Select(4 * 1 + slot)
        self.tool = BridgeTool()
        self.tool.cuts = 1
        self.tool.InitTool(self.doc, None, None)

    def test_edge_mode_uses_edge_selection_command(self):
        self.assertEqual(self.tool.source, 1)
        self.tool.apply()
        call = c4d.utils.calls[0]
        self.assertEqual(call['mode'], c4d.MODELINGCOMMANDMODE_EDGESELECTION)
        bc = call['bc']
        selected = self.obj.GetEdgeS()
        e1, e2 = bc[c4d.MDATA_BRIDGE_ELEMENT1], bc[c4d.MDATA_BRIDGE_ELEMENT2]
        self.assertTrue(selected.IsSelected(e1))
        self.assertTrue(selected.IsSelected(e2))
        self.assertNotEqual(e1, e2)

    def test_point_mode_selects_edges_between_chosen_points(self):
        self.obj.GetEdgeS().DeselectAll()
        self.doc.SetMode(c4d.Mpoints)
        for point in (0, 1, 2, 3, 4, 5):
            self.obj.GetPointS().Select(point)
        # В режиме точек рёбрами считаются рёбра сетки между выбранными вершинами:
        # здесь это одна замкнутая цепочка, а значит две цепочки не получаются.
        self.tool.refresh_if_stale(self.doc)
        self.assertIsNotNone(self.tool.preview_error)
        self.obj.GetPointS().DeselectAll()
        for point in (0, 1, 2):
            self.obj.GetPointS().Select(point)
        self.tool.refresh_if_stale(self.doc)
        self.assertEqual(self.tool.source, 1)



if __name__ == '__main__':
    unittest.main(verbosity=2)
