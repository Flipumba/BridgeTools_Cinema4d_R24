# -*- coding: utf-8 -*-
"""Интерактивный инструмент Bridge для Cinema 4D S24.

Решения, отличающиеся от предыдущей версии:

1. Актуальность снимка проверяется дешёвой подписью (счётчики точек и
   полигонов), а не полным чтением объекта на каждое движение мыши. Полная
   сверка нужна только перед применением.
2. Предпросмотр и применение используют ОДИН Plan: логика построения живёт
   в одном месте, поэтому они не могут разойтись.
3. Удаляемые грани отрисовываются отдельным цветом, а не остаются висеть
   как обычная геометрия.
4. Перетаскивание параметра мышью не упирается в край экрана и не
   сбрасывается каждый кадр.
5. MouseInput не перехватывает навигацию вьюпорта.
"""
import os
import sys
import traceback
import importlib.util

import c4d
from c4d import documents, gui, bitmaps, plugins

PLUGIN_ID = 1055741
PLUGIN_NAME = 'Bridge Interactive'

# Шаг перетаскивания на пиксель и допустимые пределы для каждого параметра.
DRAG_STEP = (0.25, 0.05, 0.02, 0.01, 0.5)
DRAG_LIMITS = ((0, 512), (-4096, 4096), (0.0, 100.0), (-10.0, 10.0), (-360.0, 360.0))
DRAG_IDS = ('CUTS', 'TWIST', 'SMOOTH', 'PROFILE', 'ANGLE')

HANDLE_RADIUS = 12


def _load(filename):
    """Загружает соседний модуль по пути, не полагаясь на sys.path.

    Имя модуля берётся из имени файла (`bridge_math`, `bridge_plan`, ...).
    Приставку «bridge_» здесь добавить нельзя, а перекрывать стандартные
    имена (`math`, `plan`) — тем более: это ломает импорт внутри модулей.
    """
    module_name = os.path.splitext(os.path.basename(filename))[0]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if module_name in sys.modules:
        module = sys.modules[module_name]
        # При перезагрузке плагина Cinema 4D модуль надо выполнить заново,
        # иначе останется код предыдущей версии.
        if getattr(module, '__file__', None) == path:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is not None and spec.loader is not None:
                spec.loader.exec_module(module)
            return module
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError('Не удалось загрузить модуль плагина: %s' % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


bridge_math = _load('bridge_math.py')
bridge_topology = _load('bridge_topology.py')
bridge_plan = _load('bridge_plan.py')
bridge_validate = _load('bridge_validate.py')
bridge_data = _load('bridge_data.py')
bridge_host = _load('bridge_host.py')
bridge_native = _load('bridge_native.py')
bridge_dialog = _load('bridge_dialog.py')

BridgeOptions = bridge_plan.BridgeOptions
BridgeError = bridge_host.BridgeError


class BridgeTool(plugins.ToolData):

    def __init__(self):
        self.InitParameters()
        self.doc = None
        self.dialog = None
        self.reset()

    # ------------------------------------------------------------------
    # Параметры
    # ------------------------------------------------------------------
    def InitParameters(self):
        self.cuts = 0
        self.twist = 0
        self.smooth = 0.0
        self.profile = 0.0
        self.angle = 0.0
        self.merge = False
        self.merge_factor = 0.5
        self.interpolation = 'LINEAR'
        self.profile_shape = 'SMOOTH'
        # Движок: 0 — встроенный Bridge Cinema 4D (N-гоны, любые теги), 1 — собственный
        # (Twist, Merge, интерполяция, профиль; только треугольники и квады).
        self.engine = 0
        # Параметры встроенного Bridge.
        self.tension = 0.0          # Tension, проценты (-100..100)
        self.curve_mode = 0         # Surface / Normal / Surface Average / Normal Average
        self.flip = False
        self.delete_faces = True
        # 0 — авто (по режиму Cinema 4D), 1 — грани, 2 — рёбра.
        self.input_mode = 0
        # Источник, определённый при последнем захвате: 0 — грани, 1 — рёбра.
        self.source = 0
        self.status = None
        self.contour_mode = 0
        self.drag_target = 0
        self.show_surface = True
        self.show_removed = True

    def options(self):
        return BridgeOptions(self.cuts, self.twist, self.smooth, self.profile,
                             self.angle, self.interpolation, self.merge,
                             self.merge_factor, self.profile_shape)

    def reset(self):
        """Сбрасывает контекст операции, не трогая настройки и диалог."""
        self.obj = None
        self.snapshot = None
        self.signature = None
        self.rims = None
        self.anchors = []
        self.auto = None
        self._point_mode = False
        self._engine = None
        self._fail_key = None
        self.hover_first = None
        self.hover_second = None
        self.plan = None
        self.preview_error = None
        self._cache_key = None

    # ------------------------------------------------------------------
    # Хуки ToolData
    # ------------------------------------------------------------------
    def InitTool(self, doc, data, bt):
        self.doc = doc
        self.reset()
        self.status = None
        print('[Bridge Interactive] ' + bridge_native.describe_availability())
        # Предпросмотр строится сразу по текущему выделению: никаких щелчков
        # по вершинам для обычного моста не требуется.
        self.refresh_if_stale(doc)
        c4d.EventAdd()
        return True

    def FreeTool(self, doc, data):
        self.reset()

    def AllocSubDialog(self, bc):
        self.dialog = bridge_dialog.Settings(self)
        return self.dialog

    def GetState(self, doc):
        return c4d.CMD_ENABLED

    # ------------------------------------------------------------------
    # Контекст
    # ------------------------------------------------------------------
    def effective_engine(self):
        """'native' — встроенный Bridge, 'own' — собственный движок."""
        if self.engine == 1:
            return 'own'
        if not bridge_native.is_available():
            return 'own'
        if self.contour_mode != 0:
            return 'own'
        return 'native'

    def engine_note(self):
        """Пояснение, если выбранный движок пришлось заменить."""
        if self.engine == 0 and not bridge_native.is_available():
            return 'встроенный Bridge недоступен в этой версии, работает собственный движок'
        if self.engine == 0 and self.contour_mode != 0:
            return 'режимы «Попарно» и «Цепочка» есть только у собственного движка'
        return None

    def native_params(self):
        return bridge_native.NativeParams(self.cuts, self.twist, self.tension,
                                          self.curve_mode, self.flip, self.delete_faces)

    def resolve_source(self, doc, obj):
        """0 — грани, 1 — рёбра. В режиме «Авто» решает режим Cinema 4D."""
        if self.input_mode == 1:
            return 0
        if self.input_mode == 2:
            return 1
        mode = doc.GetMode()
        if mode == getattr(c4d, 'Mpolygons', None):
            return 0
        if mode in (getattr(c4d, 'Medges', None), getattr(c4d, 'Mpoints', None)):
            return 1
        # Режим модели или объекта: смотрим, что выделено.
        polygons = obj.GetPolygonS()
        if polygons is not None and polygons.GetCount():
            return 0
        return 1

    def capture(self, doc, force=False):
        """Читает объект и строит кромки. Дорогая операция, идёт по событию."""
        obj = doc.GetActiveObject()
        if obj is None:
            raise BridgeError('Нет активного объекта. Выберите полигональный объект.')
        source = self.resolve_source(doc, obj)
        point_mode = (source == 1 and doc.GetMode() == getattr(c4d, 'Mpoints', None))
        engine = self.effective_engine()
        strict = (engine == 'own')
        points, faces, selected, edges_selected, snapshot = bridge_host.read_object(
            obj, point_mode, strict)

        if (not force and self.obj is obj and self.doc is doc
                and self.snapshot == snapshot and self.rims is not None
                and self.source == source and self._engine == engine):
            return

        if strict:
            # Собственный движок переписывает теги сам и отклоняет то, что не умеет
            # переносить. Встроенный Bridge этого ограничения не имеет.
            bridge_host.check_object_supported(obj)

        self.obj = obj
        self.source = source
        self._engine = engine
        self._point_mode = point_mode
        self.snapshot = snapshot
        self.signature = bridge_host.Signature(obj, doc)
        self.preview_error = None
        self._cache_key = None
        self._fail_key = None
        self.auto = None

        try:
            mesh = bridge_topology.Mesh(points, faces)
            self.rims = self._build_rims(mesh, selected, edges_selected)
            self.auto = self._auto_anchors(mesh, selected, edges_selected)
        except ValueError as error:
            # Топология бросает ValueError; наружу должен уходить BridgeError,
            # иначе ошибка не будет показана пользователю как понятный текст.
            self.rims = None
            self.auto = None
            raise BridgeError(str(error))

    def _auto_anchors(self, mesh, selected, edges_selected):
        """Соответствие кромок, подобранное автоматически (как в Blender)."""
        mode = self.contour_mode
        if self.source == 1:
            return bridge_plan.auto_anchors_edges(mesh, edges_selected, mode)
        return bridge_plan.auto_anchors_faces(mesh, selected, mode)

    def _build_rims(self, mesh, selected, edges_selected):
        """Список кромок: [(индексы вершин, замкнута), ...]."""
        mode = self.contour_mode
        if self.source == 1:
            if not edges_selected:
                raise BridgeError('Выделите две цепочки рёбер (или две группы граней в '
                                  'режиме полигонов) и нажмите Enter.')
            chains = bridge_topology.ordered_chains(edges_selected)
            if mode == 0 and len(chains) != 2:
                raise BridgeError('Выберите ровно две цепочки рёбер, а выделено %d.'
                                  % len(chains))
            if mode == 1 and (len(chains) < 2 or len(chains) % 2):
                raise BridgeError('Парное соединение требует чётного числа цепочек рёбер.')
            if mode in (2, 3) and len(chains) < 3:
                raise BridgeError('Последовательное соединение требует минимум трёх '
                                  'цепочек рёбер.')
            return [([v for v in chain.vertices], chain.closed) for chain in chains]

        if not selected:
            raise BridgeError('Выделите две группы граней (или две цепочки рёбер в '
                              'режиме рёбер) и нажмите Enter.')
        islands = bridge_topology.collect_islands(mesh, selected, allow_many=(mode != 0))
        if mode == 0 and len(islands) != 2:
            raise BridgeError('Выделите ровно две группы граней.')
        if mode == 1 and len(islands) % 2:
            raise BridgeError('Парное соединение требует чётного числа групп граней.')
        if mode in (2, 3) and len(islands) < 3:
            raise BridgeError('Последовательное соединение требует минимум трёх групп граней.')
        return [(list(island.loop), True) for island in islands]

    def is_stale(self, doc):
        """Дешёвая проверка: объект и документ те же, что при захвате."""
        if self.obj is None or self.doc is not doc:
            return True
        if not self.obj.IsAlive():
            return True
        if doc.GetActiveObject() is not self.obj:
            return True
        if self.signature is None:
            return True
        return not self.signature.matches(self.obj, doc)

    def refresh_if_stale(self, doc):
        if not self.is_stale(doc):
            self.ensure_plan()
            return
        self.anchors = []
        self.hover_first = None
        self.hover_second = None
        self.plan = None
        self.status = None
        try:
            self.capture(doc, force=True)
        except BridgeError as error:
            self.preview_error = str(error)
            self.rims = None
            self.auto = None
            return
        self.ensure_plan()

    def current_anchors(self):
        """(первая, вторая, flip): ручные, если заданы обе, иначе автоматические."""
        if len(self.anchors) == 2:
            return self.anchors[0], self.anchors[1], False
        return self.auto

    def ensure_plan(self):
        """Строит предпросмотр по автоматическому (или ручному) соответствию."""
        if self.plan is not None or self.obj is None or self.rims is None:
            return
        pair = self.current_anchors()
        if pair is None:
            return
        key = (self._plan_key(pair[0], pair[1], pair[2]))
        if self._fail_key == key:
            return
        try:
            self.build_plan(pair[0], pair[1], pair[2])
            self.preview_error = None
        except BridgeError as error:
            self.preview_error = str(error)
            self.plan = None
            self._fail_key = key

    # ------------------------------------------------------------------
    # Предпросмотр
    # ------------------------------------------------------------------
    def _plan_key(self, first, second, flip=False):
        return (id(self.obj), tuple(sorted(self.snapshot[2])), tuple(self.snapshot[3]),
                first, second, bool(flip), self.options().key(), self.contour_mode,
                self.source)

    def build_plan(self, first, second, flip=False):
        """Строит план по двум якорям. Результат кэшируется по параметрам."""
        if self.obj is None or self.rims is None:
            raise BridgeError('Сначала выберите полигональный объект и группы.')
        key = self._plan_key(first, second, flip)
        if self._cache_key == key and self.plan is not None:
            return self.plan

        mesh = bridge_topology.Mesh(self.snapshot[0], self.snapshot[1])
        opts = self.options()
        mode = self.contour_mode
        try:
            if self.source == 1:
                edges = self.snapshot[3]
                if mode == 0:
                    plan = bridge_plan.plan_edge_bridge(mesh, edges, first, second, opts,
                                                        flip=flip)
                elif mode == 1:
                    plan = bridge_plan.plan_edge_pairs(mesh, edges, first, second, opts,
                                                       flip=flip)
                else:
                    plan = bridge_plan.plan_edge_chain(mesh, edges, first, second, opts,
                                                       closed=(mode == 3), flip=flip)
            else:
                selected = self.snapshot[2]
                if mode == 0:
                    plan = bridge_plan.plan_face_bridge(mesh, selected, first, second, opts)
                elif mode == 1:
                    plan = bridge_plan.plan_face_pairs(mesh, selected, first, second, opts)
                else:
                    plan = bridge_plan.plan_face_chain(mesh, selected, first, second, opts,
                                                       closed=(mode == 3))
        except ValueError as error:
            raise BridgeError(str(error))

        try:
            bridge_validate.check_plan(plan)
        except bridge_validate.ValidationError as error:
            raise BridgeError(str(error))
        self.plan = plan
        self._cache_key = key
        return plan

    def request_preview(self):
        self.plan = None
        self._cache_key = None
        self._fail_key = None
        self.ensure_plan()
        c4d.EventAdd()

    # ------------------------------------------------------------------
    # Наведение
    # ------------------------------------------------------------------
    def pick(self, bd, x, y, exclude_rim=None):
        """Ближайшая вершина кромки под курсором.

        Расстояние считается в экранных координатах, поэтому подсветка
        одинаково работает при любом масштабе и на преобразованных объектах.
        """
        if self.obj is None or self.rims is None:
            return None
        matrix = self.obj.GetMg()
        points = self.snapshot[0]
        best = None
        for rim_index, (loop, _closed) in enumerate(self.rims):
            if rim_index == exclude_rim:
                continue
            for vertex in loop:
                screen = bd.WS(matrix * c4d.Vector(points[vertex][0],
                                                  points[vertex][1],
                                                  points[vertex][2]))
                dx = screen.x - x
                dy = screen.y - y
                dist = dx * dx + dy * dy
                if dist <= HANDLE_RADIUS * HANDLE_RADIUS and (best is None or dist < best[0]):
                    best = (dist, rim_index, vertex)
        return None if best is None else (best[1], best[2])

    def rim_index_of(self, vertex):
        if self.rims is None:
            return None
        for index, (loop, _closed) in enumerate(self.rims):
            if vertex in loop:
                return index
        return None

    def GetCursorInfo(self, doc, data, bd, x, y, bc):
        try:
            if bc is not None and bc.GetId() == c4d.BFM_CURSORINFO_REMOVE:
                changed = self.hover_first is not None or self.hover_second is not None
                self.hover_first = None
                self.hover_second = None
                if changed:
                    c4d.EventAdd()
                return True

            self.refresh_if_stale(doc)
            if self.obj is not None and bc is not None:
                bc[c4d.RESULT_BUBBLEHELP] = self._bubble_text()
            if self.rims is None:
                return True

            if len(self.anchors) == 0:
                candidate = self.pick(bd, x, y)
                if candidate != self.hover_first:
                    self.hover_first = candidate
                    c4d.EventAdd()
            elif len(self.anchors) == 1:
                exclude = self.rim_index_of(self.anchors[0])
                candidate = self.pick(bd, x, y, exclude_rim=exclude)
                if candidate != self.hover_second:
                    self.hover_second = candidate
                    if candidate is None:
                        # Возвращаемся к автоматическому соответствию.
                        self.plan = None
                        self._cache_key = None
                        self.ensure_plan()
                    else:
                        # Предпросмотр строится от «временной» второй вершины,
                        # не фиксируя её до щелчка.
                        try:
                            self.build_plan(self.anchors[0], candidate[1])
                            self.preview_error = None
                        except BridgeError as error:
                            self.preview_error = str(error)
                            self.plan = None
                    c4d.EventAdd()
        except Exception as error:
            self.preview_error = str(error)
            traceback.print_exc()
        return True

    def _bubble_text(self):
        if len(self.anchors) == 1:
            return 'Щёлкните соответствующую вершину второй кромки. Esc — вернуть авто.'
        if self.plan is not None:
            return ('Предпросмотр готов. Enter — применить. Соответствие подобрано '
                    'автоматически; при желании задайте его вручную щелчками по вершинам.')
        return 'Выделите две группы граней или две цепочки рёбер.'

    def status_text(self):
        """Строка состояния для вьюпорта."""
        if self.plan is not None:
            extra = ''
            if len(self.anchors) == 1:
                extra = ' Щёлкните вершину на второй кромке.'
            if self.effective_engine() == 'native':
                head = ('Bridge [встроенный Cinema 4D]: предпросмотр приблизительный, '
                        'форму моста построит встроенный Bridge.')
            else:
                head = 'Bridge [собственный движок]: предпросмотр готов.'
            note = self.engine_note()
            if note:
                head += ' (' + note + ')'
            return (head + ' Enter — применить, Esc — сброс ручного выбора, '
                    'Shift+перетаскивание — менять параметр.' + extra)
        if self.preview_error:
            return 'Bridge: ' + self.preview_error
        if self.status:
            return 'Bridge: ' + self.status
        return 'Bridge: выделите две группы граней или две цепочки рёбер.'

    # ------------------------------------------------------------------
    # Мышь
    # ------------------------------------------------------------------
    def MouseInput(self, doc, data, bd, win, msg):
        channel = msg[c4d.BFM_INPUT_CHANNEL]
        if channel != c4d.BFM_INPUT_MOUSELEFT:
            # Всё остальное — навигация вьюпорта; её перехватывать нельзя.
            return False
        qualifier = msg.get(c4d.BFM_INPUT_QUALIFIER, 0) if hasattr(msg, 'get') else 0
        try:
            self.refresh_if_stale(doc)
            if self.plan is not None and (qualifier & c4d.QUALIFIER_SHIFT):
                self.drag_parameter(win, msg)
                return True
            if self.obj is None or self.rims is None:
                # Нечего выбирать: причина показана в строке состояния.
                c4d.EventAdd()
                return True
            x = msg[c4d.BFM_INPUT_X]
            y = msg[c4d.BFM_INPUT_Y]
            # Щелчки по вершинам — необязательная ручная подстройка соответствия.
            # Мимо вершины щелчок ничего не делает и не вызывает диалогов.
            if len(self.anchors) == 0:
                candidate = self.pick(bd, x, y)
                if candidate is not None:
                    self.anchors = [candidate[1]]
                    self.hover_first = None
            elif len(self.anchors) == 1:
                exclude = self.rim_index_of(self.anchors[0])
                candidate = self.pick(bd, x, y, exclude_rim=exclude)
                if candidate is not None:
                    self.anchors = [self.anchors[0], candidate[1]]
                    self.hover_second = None
                    self.request_preview()
                    return True
            else:
                # Третий щелчок начинает ручной выбор заново.
                candidate = self.pick(bd, x, y)
                if candidate is not None:
                    self.plan = None
                    self._cache_key = None
                    self.hover_second = None
                    self.anchors = [candidate[1]]
                    self.ensure_plan()
            c4d.EventAdd()
        except BridgeError as error:
            self.preview_error = str(error)
            c4d.EventAdd()
        except Exception as error:
            traceback.print_exc()
            self.report(error)
        return True

    def KeyboardInput(self, doc, data, bd, win, msg):
        key = msg[c4d.BFM_INPUT_CHANNEL]
        if key == c4d.KEY_ESC:
            self.reset_selection()
            return True
        if key in (c4d.KEY_ENTER, getattr(c4d, 'KEY_RETURN', c4d.KEY_ENTER)):
            try:
                self.apply()
            except BridgeError as error:
                self.report(error)
            return True
        return False

    def reset_selection(self):
        """Сбрасывает ручной выбор вершин и возвращает автоматическое соответствие."""
        self.anchors = []
        self.hover_first = None
        self.hover_second = None
        self.status = None
        self.request_preview()

    # ------------------------------------------------------------------
    # Перетаскивание параметра
    # ------------------------------------------------------------------
    def drag_parameter(self, win, msg):
        """Меняет параметр по горизонтальному смещению мыши.

        Значение НЕ ограничивается размером экрана: накопленное смещение может
        быть любым, а пределы берутся только из допустимого диапазона самого
        параметра. Escape возвращает исходное значение.
        """
        index = self.drag_target
        field = DRAG_IDS[index].lower()
        initial = getattr(self, field)
        accum = 0.0
        low, high = DRAG_LIMITS[index]
        step = DRAG_STEP[index]
        integer = index in (0, 1)

        mouse_x = msg.get(c4d.BFM_INPUT_X, 0) if hasattr(msg, 'get') else 0
        mouse_y = msg.get(c4d.BFM_INPUT_Y, 0) if hasattr(msg, 'get') else 0

        if not win.MouseDragStart(c4d.KEY_MLEFT, mouse_x, mouse_y,
                                  c4d.MOUSEDRAGFLAGS_NONE):
            return
        changed = False
        try:
            while True:
                result, dx, dy, channels = win.MouseDrag()
                if result != c4d.MOUSEDRAGRESULT_CONTINUE:
                    break
                accum += dx
                value = max(low, min(high, initial + accum * step))
                if integer:
                    value = int(round(value))
                if value == getattr(self, field):
                    continue
                previous = getattr(self, field)
                setattr(self, field, value)
                try:
                    self.request_preview()
                except BridgeError:
                    setattr(self, field, previous)
                    self.request_preview()
                changed = True
                if self.dialog is not None:
                    self.dialog.push(getattr(bridge_dialog.Param, DRAG_IDS[index]))
                c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW
                              | c4d.DRAWFLAGS_NO_THREAD
                              | c4d.DRAWFLAGS_NO_ANIMATION)
        finally:
            outcome = win.MouseDragEnd()
            if outcome == c4d.MOUSEDRAGRESULT_ESCAPE and changed:
                setattr(self, field, initial)
                self.request_preview()
                if self.dialog is not None:
                    self.dialog.push(None)
                c4d.EventAdd()

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def Draw(self, doc, data, bd, bh, bt, flags):
        try:
            if self.doc is not doc:
                self.doc = doc
            self.refresh_if_stale(doc)
            self._draw_status(bd)
            if self.obj is None or not self.obj.IsAlive() or self.rims is None:
                return c4d.TOOLDRAW_NONE
            matrix = self.obj.GetMg()
            points = self.snapshot[0]

            if self.plan is not None:
                self._draw_preview(bd, matrix, points, self.plan)
            self._draw_handles(bd, matrix, points)
        except Exception:
            traceback.print_exc()
        return c4d.TOOLDRAW_NONE

    def _draw_status(self, bd):
        """Текст состояния в углу вьюпорта: что выделить или почему мост не строится."""
        if not hasattr(bd, 'DrawHUDText'):
            return
        try:
            bd.SetPen(c4d.Vector(1.0, 1.0, 1.0))
            bd.DrawHUDText(12, 44, self.status_text())
        except Exception:
            pass

    def _world(self, matrix, point):
        return matrix * c4d.Vector(point[0], point[1], point[2])

    def _draw_preview(self, bd, matrix, points, plan):
        # Удаляемые полигоны показываются отдельно: иначе предпросмотр
        # выглядит так, будто старая геометрия остаётся на месте.
        if self.show_removed and plan.removed_faces:
            bd.SetPen(c4d.Vector(0.9, 0.15, 0.15))
            for index in plan.removed_faces:
                face = plan.old_faces[index]
                coords = [self._world(matrix, points[v]) for v in face]
                for a, b in zip(coords, coords[1:] + coords[:1]):
                    bd.DrawLine(a, b, 0)

        if self.show_surface and plan.new_faces:
            bd.SetPen(c4d.Vector(1.0, 0.6, 0.05))
            for index in plan.new_faces:
                face = plan.faces[index]
                coords = [self._world(matrix, plan.points[v]) for v in face]
                if len(coords) < 3:
                    continue
                normal = (coords[1] - coords[0]).Cross(coords[2] - coords[0])
                if normal.GetLength() <= 1e-9:
                    continue
                normal.Normalize()
                view = c4d.Vector(0.3, 0.7, 1.0).GetNormalized()
                shade = 0.30 + 0.35 * abs(normal.Dot(view))
                colour = c4d.Vector(shade, shade * 0.66, shade * 0.28)
                if hasattr(bd, 'DrawPolygon'):
                    bd.DrawPolygon(coords, [colour] * len(coords))

        bd.SetPen(c4d.Vector(1.0, 0.75, 0.15))
        drawn = set()
        for index in plan.new_faces:
            face = plan.faces[index]
            coords = [self._world(matrix, plan.points[v]) for v in face]
            for slot in range(len(face)):
                a = coords[slot]
                b = coords[(slot + 1) % len(face)]
                key = (round(a.x, 4), round(a.y, 4), round(a.z, 4),
                       round(b.x, 4), round(b.y, 4), round(b.z, 4))
                mirror = (key[3], key[4], key[5], key[0], key[1], key[2])
                if key in drawn or mirror in drawn:
                    continue
                drawn.add(key)
                bd.DrawLine(a, b, 0)

    def _draw_handles(self, bd, matrix, points):
        if self.hover_first is not None:
            bd.SetPen(c4d.Vector(0.3, 1.0, 0.4))
            bd.DrawHandle(self._world(matrix, points[self.hover_first[1]]),
                          c4d.DRAWHANDLE_BIG, 0)
        if self.hover_second is not None:
            bd.SetPen(c4d.Vector(0.3, 1.0, 0.4))
            bd.DrawHandle(self._world(matrix, points[self.hover_second[1]]),
                          c4d.DRAWHANDLE_BIG, 0)
        for index, vertex in enumerate(self.anchors):
            colour = c4d.Vector(1.0, 0.85, 0.2) if index == 0 else c4d.Vector(0.2, 0.7, 1.0)
            bd.SetPen(colour)
            bd.DrawHandle(self._world(matrix, points[vertex]),
                          c4d.DRAWHANDLE_BIG, 0)

    # ------------------------------------------------------------------
    # Настройки
    # ------------------------------------------------------------------
    def on_options_changed(self, ident):
        """Реакция на изменение настроек в диалоге."""
        # Смена источника или режима контуров меняет смысл кромок.
        if ident in (bridge_dialog.Param.SOURCE, bridge_dialog.Param.CONTOUR_MODE,
                     bridge_dialog.Param.ENGINE):
            self.anchors = []
            self.plan = None
            self.preview_error = None
            self.status = None
            if self.doc is not None:
                try:
                    self.capture(self.doc, force=True)
                except BridgeError as error:
                    self.preview_error = str(error)
                    self.rims = None
                    self.auto = None
            self.request_preview()
            return
        self.request_preview()

    # ------------------------------------------------------------------
    # Применение
    # ------------------------------------------------------------------
    def apply(self):
        """Проверяет и записывает результат. Единственная точка изменения модели."""
        doc = documents.GetActiveDocument()
        if doc is None or self.doc is not doc:
            self.doc = doc
        if doc is None:
            raise BridgeError('Нет активного документа.')
        # Выделение могло измениться с момента последнего предпросмотра.
        self.refresh_if_stale(doc)
        if self.obj is None or not self.obj.IsAlive():
            raise BridgeError(self.preview_error or 'Нет активного полигонального объекта.')
        pair = self.current_anchors()
        if pair is None or self.rims is None:
            raise BridgeError(self.preview_error or
                              'Выделите две группы граней или две цепочки рёбер.')

        engine = self.effective_engine()
        strict = (engine == 'own')
        # Перед записью объект сверяется полностью: подпись ловит не всё.
        if strict:
            bridge_host.check_object_supported(self.obj)
        points, faces, selected, edges_selected, snapshot = bridge_host.read_object(
            self.obj, self._point_mode, strict)
        if snapshot != self.snapshot:
            self.reset_snapshot_state()
            try:
                self.capture(doc, force=True)
                self.ensure_plan()
            except BridgeError:
                pass
            raise BridgeError('Выделение или объект изменились. Проверьте предпросмотр '
                              'и нажмите Enter ещё раз.')

        if engine == 'native':
            message = bridge_native.apply_native(
                doc, self.obj, self.source, snapshot, (pair[0], pair[1]),
                self.native_params(), self._point_mode)
        else:
            message = self._apply_own(doc, pair, snapshot)

        c4d.EventAdd()
        self.reset()
        self.status = message + ' Выделите следующие кромки.'
        try:
            self.capture(doc, force=True)
        except BridgeError:
            pass
        else:
            self.status = None
            self.ensure_plan()

    def _apply_own(self, doc, pair, snapshot):
        """Собственный движок: строит план и переписывает геометрию и теги."""
        plan = self.build_plan(pair[0], pair[1], pair[2])
        if plan.is_noop:
            raise BridgeError('Операция не создаёт и не удаляет полигоны. '
                              'Проверьте выбор и режим.')
        tag_data = bridge_host.capture_tag_data(self.obj, len(snapshot[1]), len(snapshot[0]))
        transfer = bridge_host.compute_transfer(plan, tag_data)
        bridge_host.apply_plan(doc, self.obj, plan, transfer)
        return 'мост создан.'

    def reset_snapshot_state(self):
        self.anchors = []
        self.hover_first = None
        self.hover_second = None
        c4d.EventAdd()

    # ------------------------------------------------------------------
    # Прочее
    # ------------------------------------------------------------------
    def report(self, error):
        """Показывает ошибку и не даёт исключению уронить инструмент."""
        text = str(error) if error else 'Неизвестная ошибка.'
        self.preview_error = text
        if sys.exc_info()[0] is not None and not isinstance(error, BridgeError):
            traceback.print_exc()
        try:
            gui.MessageDialog(text)
        except Exception:
            pass
        c4d.EventAdd()


def register():
    icon = bitmaps.BaseBitmap()
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'res', 'icon.png')
    if not os.path.exists(icon_path) or icon.InitWith(icon_path)[0] != c4d.IMAGERESULT_OK:
        icon = None
    return plugins.RegisterToolPlugin(
        PLUGIN_ID, PLUGIN_NAME, 0, icon,
        'Мост между группами граней или цепочками рёбер.', BridgeTool())


if __name__ == '__main__':
    register()
