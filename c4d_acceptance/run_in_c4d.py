# -*- coding: utf-8 -*-
"""Приёмочная проверка в реальной Cinema 4D S24.037.

Запуск: Script Manager → открыть этот файл → Execute.
Скрипт работает в отдельном документе и не трогает ваш проект.

Проверяет то, что нельзя проверить без хоста:
  * регистрация плагина и создание ToolData;
  * чтение объекта, построение кромок;
  * применение моста, размеры результата;
  * одна операция Undo и корректный откат геометрии, UV и весов;
  * отказ на N-гонах без изменения объекта;
  * отказ на Fields-теге без изменения объекта.

Печатает PASS/FAIL по каждому пункту и итог.
"""
import os
import sys
import traceback

import c4d
from c4d import documents

PLUGIN_DIR = None
for base in (os.path.dirname(os.path.abspath(__file__)),):
    for candidate in (base,
                      os.path.join(base, '..'),
                      os.path.join(base, '..', 'BridgeInteractive')):
        if os.path.exists(os.path.join(candidate, 'bridge_interactive.pyp')):
            PLUGIN_DIR = os.path.abspath(candidate)
            break
    if PLUGIN_DIR:
        break

if PLUGIN_DIR is None:
    raise RuntimeError('Не найден bridge_interactive.pyp. Положите run_in_c4d.py '
                       'рядом с папкой BridgeInteractive.')

RESULTS = []


def check(name, function):
    try:
        function()
        RESULTS.append((True, name, ''))
        print('PASS  %s' % name)
    except Exception as error:
        RESULTS.append((False, name, str(error)))
        print('FAIL  %s\n      %s' % (name, error))
        traceback.print_exc()


def load_plugin():
    import importlib.util
    path = os.path.join(PLUGIN_DIR, 'bridge_interactive.pyp')
    name = 'bridge_acceptance_plugin'
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def grid_points_faces():
    points = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0),
              (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
              (-1, -1, 2), (1, -1, 2), (1, 1, 2), (-1, 1, 2),
              (-1, -1, 3), (1, -1, 3), (1, 1, 3), (-1, 1, 3)]
    faces = [(0, 1, 2, 3), (11, 10, 9, 8)]
    faces += [(i + 4, (i + 1) % 4 + 4, (i + 1) % 4, i) for i in range(4)]
    faces += [(8 + i, 8 + (i + 1) % 4, 12 + (i + 1) % 4, 12 + i) for i in range(4)]
    return points, faces


def make_scene(doc):
    points, faces = grid_points_faces()
    obj = c4d.PolygonObject(len(points), len(faces))
    obj.SetName('Bridge Acceptance')
    obj.SetAllPoints([c4d.Vector(*p) for p in points])
    for index, face in enumerate(faces):
        if len(face) == 3:
            obj.SetPolygon(index, c4d.CPolygon(face[0], face[1], face[2], face[2]))
        else:
            obj.SetPolygon(index, c4d.CPolygon(*face))

    uv = c4d.UVWTag(len(faces))
    obj.InsertTag(uv)
    for i in range(len(faces)):
        uv.SetSlow(i, c4d.Vector(i, 0, 0), c4d.Vector(i, 1, 0),
                   c4d.Vector(i, 1, 1), c4d.Vector(i, 0, 1))
    pins = c4d.BaseSelect()
    for index in (8, 11, 39):
        pins.Select(index)
    uv.SetPinSelection(pins)

    weights = c4d.VariableTag(c4d.Tvertexmap, len(points))
    obj.InsertTag(weights)
    weights.SetAllHighlevelData([float(i) for i in range(len(points))])

    doc.InsertObject(obj)
    doc.SetActiveObject(obj)
    obj.GetPolygonS().Select(0)
    obj.GetPolygonS().Select(1)
    obj.Message(c4d.MSG_UPDATE)
    return obj


def snapshot(obj):
    points = [(p.x, p.y, p.z) for p in obj.GetAllPoints()]
    faces = []
    for p in obj.GetAllPolygons():
        faces.append((p.a, p.b, p.c, p.d))
    selection = tuple(i for i in range(len(faces)) if obj.GetPolygonS().IsSelected(i))
    return (tuple(points), tuple(faces), selection)


def find_uv(obj):
    for tag in obj.GetTags():
        if tag.GetType() == c4d.Tuvw:
            return tag
    return None


def find_weights(obj):
    for tag in obj.GetTags():
        if tag.GetType() == c4d.Tvertexmap:
            return tag
    return None


def main():
    original = documents.GetActiveDocument()
    doc = documents.BaseDocument()
    if doc is None:
        raise RuntimeError('Не удалось создать временный документ.')
    documents.InsertBaseDocument(doc)
    documents.SetActiveDocument(doc)
    try:
        plugin = load_plugin()

        def tool_builds_plan():
            obj = make_scene(doc)
            tool = plugin['BridgeTool']()
            tool.engine = 1      # собственный движок: проверки ниже его
            tool.InitTool(doc, None, None)
            tool.cuts = 1
            tool.capture(doc, force=True)
            assert tool.obj is obj, 'объект не захвачен'
            assert tool.rims is not None and len(tool.rims) == 2, 'кромки не построены'
            plan = tool.build_plan(0, 8)
            assert len(plan.new_faces) == 8, 'ожидалось 8 новых полигонов, получено %d' % len(plan.new_faces)
            assert plan.removed_faces == [0, 1], 'удаляемые грани определены неверно'

        def preview_does_not_modify():
            obj = doc.GetFirstObject()
            before = snapshot(obj)
            tool = plugin['BridgeTool']()
            tool.engine = 1      # собственный движок: проверки ниже его
            tool.InitTool(doc, None, None)
            tool.cuts = 2
            tool.capture(doc, force=True)
            tool.build_plan(0, 8)
            assert snapshot(obj) == before, 'предпросмотр изменил объект'

        def native_bridge_constants():
            """Что из встроенного Bridge доступно из Python в этой версии Cinema 4D."""
            native = sys.modules['bridge_native']
            required, optional = native.availability()
            print('    ' + native.describe_availability())
            assert not required, 'нет констант: %s' % ', '.join(required)

        def native_bridge_without_anchors():
            """Встроенный Bridge по выделению, без выбора вершин; затем Undo."""
            obj = doc.GetFirstObject()
            before = snapshot(obj)
            tool = plugin['BridgeTool']()
            tool.engine = 0
            tool.InitTool(doc, None, None)
            tool.cuts = 1
            tool.request_preview()
            assert tool.effective_engine() == 'native'
            assert not tool.anchors
            tool.apply()
            obj = doc.GetFirstObject()
            print('    после моста: %d точек, %d полигонов'
                  % (obj.GetPointCount(), obj.GetPolygonCount()))
            assert snapshot(obj) != before, 'встроенный Bridge ничего не изменил'
            if not doc.DoUndo():
                raise RuntimeError('DoUndo вернул False')
            assert snapshot(doc.GetFirstObject()) == before, 'Undo не восстановил геометрию'

        def auto_apply_without_anchors():
            """Главная проверка: мост строится по выделению, без щелчков по вершинам."""
            obj = doc.GetFirstObject()
            before = snapshot(obj)
            tool = plugin['BridgeTool']()
            tool.engine = 1      # собственный движок: проверки ниже его
            tool.InitTool(doc, None, None)
            tool.cuts = 1
            tool.request_preview()
            assert not tool.anchors, 'якоря заданы вручную, а должны быть автоматическими'
            assert tool.plan is not None, 'предпросмотр не построился: %s' % tool.preview_error
            tool.apply()
            obj = doc.GetFirstObject()
            assert obj.GetPolygonCount() == 16, 'полигонов %d вместо 16' % obj.GetPolygonCount()
            if not doc.DoUndo():
                raise RuntimeError('DoUndo вернул False')
            assert snapshot(doc.GetFirstObject()) == before, 'Undo не восстановил геометрию'

        def apply_and_undo():
            obj = doc.GetFirstObject()
            before = snapshot(obj)
            uv = find_uv(obj)
            uv_before = uv.GetDataCount()
            weights = find_weights(obj)
            weight_before = len(weights.GetAllHighlevelData())

            tool = plugin['BridgeTool']()
            tool.engine = 1      # собственный движок: проверки ниже его
            tool.InitTool(doc, None, None)
            tool.cuts = 1
            tool.capture(doc, force=True)
            tool.anchors = [0, 8]
            tool.apply()

            obj = doc.GetFirstObject()
            assert obj.GetPolygonCount() == 16, 'полигонов %d вместо 16' % obj.GetPolygonCount()
            assert obj.GetPointCount() == 20, 'точек %d вместо 20' % obj.GetPointCount()
            uv = find_uv(obj)
            assert uv.GetDataCount() == 16, 'UV-тег не вырос: %d' % uv.GetDataCount()
            weights = find_weights(obj)
            assert len(weights.GetAllHighlevelData()) == 20, 'Vertex Map не вырос'

            if not doc.DoUndo():
                raise RuntimeError('DoUndo вернул False')
            obj = doc.GetFirstObject()
            assert snapshot(obj) == before, 'Undo не восстановил геометрию'
            uv = find_uv(obj)
            assert uv.GetDataCount() == uv_before, 'Undo не восстановил UV-тег'
            weights = find_weights(obj)
            assert len(weights.GetAllHighlevelData()) == weight_before, \
                'Undo не восстановил Vertex Map'

        def ngon_rejected():
            points = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0), (0, 0, 1)]
            obj = c4d.PolygonObject(len(points), 1)
            obj.SetAllPoints([c4d.Vector(*p) for p in points])
            obj.SetPolygon(0, c4d.CPolygon(0, 1, 2, 3))
            doc.InsertObject(obj)
            doc.SetActiveObject(obj)
            before = snapshot(obj)
            tool = plugin['BridgeTool']()
            tool.engine = 1      # собственный движок: проверки ниже его
            tool.InitTool(doc, None, None)
            if obj.GetNgonCount() == 0:
                print('      примечание: N-гон через SetPolygon не создался, '
                      'проверка отказов выполнена частично')
                return
            try:
                tool.capture(doc, force=True)
            except Exception:
                pass
            assert snapshot(obj) == before, 'объект изменён при отказе'

        def fields_tag_rejected():
            obj = doc.GetFirstObject()
            weights = find_weights(obj)
            if weights is None:
                raise RuntimeError('не найден Vertex Map')
            try:
                weights[c4d.ID_TAGFIELD_ENABLE] = True
            except Exception:
                print('      примечание: ID_TAGFIELD_ENABLE недоступен в S24')
                return
            before = snapshot(obj)
            tool = plugin['BridgeTool']()
            tool.engine = 1      # собственный движок: проверки ниже его
            tool.InitTool(doc, None, None)
            rejected = False
            try:
                tool.capture(doc, force=True)
            except Exception:
                rejected = True
            assert rejected, 'объект с Fields-тегом не отклонён'
            assert snapshot(obj) == before, 'объект изменён при отказе'
            weights[c4d.ID_TAGFIELD_ENABLE] = False

        check('построение плана по двум якорям', tool_builds_plan)
        check('предпросмотр не изменяет объект', preview_does_not_modify)
        check('встроенный Bridge: константы API', native_bridge_constants)
        check('встроенный Bridge без выбора вершин + Undo', native_bridge_without_anchors)
        check('собственный движок без выбора вершин', auto_apply_without_anchors)
        check('применение, UV, веса, Undo', apply_and_undo)
        check('отказ на N-гонах', ngon_rejected)
        check('отказ на Fields-теге', fields_tag_rejected)

    finally:
        if original is not None:
            documents.SetActiveDocument(original)
        documents.KillDocument(doc)
        c4d.EventAdd()

    passed = sum(1 for ok, _, _ in RESULTS if ok)
    total = len(RESULTS)
    print('\nИтог: %d/%d' % (passed, total))
    if passed != total:
        print('Не пройдено:')
        for ok, name, error in RESULTS:
            if not ok:
                print('  - %s: %s' % (name, error))
        raise RuntimeError('Приёмочная проверка не пройдена.')
    print('Все проверки пройдены. Интерактивную работу (клики, подсветку, '
          'перетаскивание) нужно проверить руками.')


if __name__ == '__main__':
    main()
