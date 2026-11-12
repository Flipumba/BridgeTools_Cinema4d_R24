# -*- coding: utf-8 -*-
"""Диалог настроек инструмента."""
import c4d
from c4d import gui

from bridge_plan import PROFILE_SHAPES, INTERPOLATIONS


class Param(object):
    """Идентификаторы элементов управления.

    Начинаются с 1000: служебные ID Cinema 4D лежат ниже, и пересечение с ними
    приводит к «пропавшим» элементам в диалоге.
    """
    GROUP_TOP = 1000
    GROUP_SHAPE = 1001

    SOURCE = 1010
    INTERPOLATION = 1011
    CUTS = 1012
    TWIST = 1013
    SMOOTH = 1014
    PROFILE = 1015
    ANGLE = 1016
    PROFILE_SHAPE = 1017
    MERGE = 1018
    MERGE_FACTOR = 1019
    CONTOUR_MODE = 1020
    DRAG_TARGET = 1021
    SHOW_SURFACE = 1022
    SHOW_REMOVED = 1023
    ENGINE = 1024
    TENSION = 1025
    CURVE_MODE = 1026
    FLIP = 1027
    DELETE = 1028

    APPLY = 1030
    RESET = 1031

    LABEL_BASE = 1100


ENGINE_ITEMS = ('Встроенный Bridge Cinema 4D', 'Собственный (Blender-подобный)')
CURVE_ITEMS = ('Surface', 'Normal', 'Surface Average', 'Normal Average')
SOURCE_ITEMS = ('Авто (по режиму)', 'Выделенные грани', 'Выделенные рёбра')
INTERPOLATION_ITEMS = ('Линейная', 'По пути', 'По поверхности')
CONTOUR_ITEMS = ('Две группы', 'Попарно', 'Цепочка', 'Цепочка с замыканием')
DRAG_ITEMS = ('Разрезы', 'Сдвиг соответствия', 'Сглаживание', 'Выпуклость', 'Угол')
PROFILE_ITEMS = ('Smooth', 'Sphere', 'Root', 'Sharp', 'Linear', 'Constant',
                 'Inverse Square')


class Settings(gui.SubDialog):
    """Диалог инструмента. Читает и пишет значения прямо в tool."""

    def __init__(self, tool):
        self.tool = tool
        self._syncing = False

    # -- построение ---------------------------------------------------------
    def CreateLayout(self):
        self.SetTitle('Bridge Interactive')
        t = self.tool

        self.AddStaticText(Param.LABEL_BASE, c4d.BFH_SCALEFIT,
                           name='Выделите две группы граней или две цепочки рёбер —')
        self.AddStaticText(Param.LABEL_BASE + 1, c4d.BFH_SCALEFIT,
                           name='предпросмотр появится сам. Enter или кнопка ниже — применить.')

        self.GroupBegin(Param.GROUP_TOP, c4d.BFH_SCALEFIT, 2, 0)
        self.GroupBorderSpace(4, 4, 4, 4)
        self._combo(Param.ENGINE, 'Движок', ENGINE_ITEMS, t.engine)
        self._combo(Param.SOURCE, 'Источник', SOURCE_ITEMS, t.input_mode)
        self._combo(Param.INTERPOLATION, 'Интерполяция',
                    INTERPOLATION_ITEMS, INTERPOLATIONS.index(t.interpolation))
        self._combo(Param.CONTOUR_MODE, 'Контуры', CONTOUR_ITEMS, t.contour_mode)
        self._int(Param.CUTS, 'Разрезы', t.cuts, 0, 512)
        self._int(Param.TWIST, 'Сдвиг соответствия', t.twist, -4096, 4096)
        self._float(Param.SMOOTH, 'Сглаживание', t.smooth, 0.0, 100.0, 0.01)
        self._float(Param.PROFILE, 'Выпуклость', t.profile, -10.0, 10.0, 0.01)
        self._float(Param.ANGLE, 'Угол, градусы', t.angle, -360.0, 360.0, 0.1)
        self._combo(Param.PROFILE_SHAPE, 'Форма профиля', PROFILE_ITEMS,
                    PROFILE_SHAPES.index(t.profile_shape))
        self._check(Param.MERGE, 'Объединить контуры (Merge)', t.merge)
        self._float(Param.MERGE_FACTOR, 'Положение слияния', t.merge_factor, 0.0, 1.0, 0.01)
        self._float(Param.TENSION, 'Tension, % (встроенный)', t.tension, -100.0, 100.0, 1.0)
        self._combo(Param.CURVE_MODE, 'Кривизна (встроенный)', CURVE_ITEMS, t.curve_mode)
        self._check(Param.FLIP, 'Flip (встроенный)', t.flip)
        self._check(Param.DELETE, 'Удалить исходные грани (встроенный)', t.delete_faces)
        self.GroupEnd()

        self.GroupBegin(Param.GROUP_SHAPE, c4d.BFH_SCALEFIT, 2, 0)
        self.GroupBorderSpace(4, 4, 4, 4)
        self._combo(Param.DRAG_TARGET, 'Shift + перетаскивание', DRAG_ITEMS, t.drag_target)
        self._check(Param.SHOW_SURFACE, 'Показывать поверхность моста', t.show_surface)
        self._check(Param.SHOW_REMOVED, 'Показывать удаляемые грани', t.show_removed)
        self.GroupEnd()

        self.AddStaticText(Param.LABEL_BASE + 2, c4d.BFH_SCALEFIT,
                           name='Серые параметры не действуют в выбранном движке.')
        self.AddButton(Param.APPLY, c4d.BFH_SCALEFIT, name='Применить мост  (Enter)')
        self.AddButton(Param.RESET, c4d.BFH_SCALEFIT, name='Сбросить ручной выбор вершин  (Esc)')
        self.refresh_enabled()
        return True

    def _label(self, ident, text):
        self.AddStaticText(Param.LABEL_BASE + ident, c4d.BFH_LEFT, 130, 0, name=text)

    def _combo(self, ident, text, items, current):
        self._label(ident, text)
        self.AddComboBox(ident, c4d.BFH_SCALEFIT, 0, 0)
        for index, item in enumerate(items):
            self.AddChild(ident, index, item)
        self.SetInt32(ident, int(current), 0, len(items) - 1)

    def _int(self, ident, text, value, low, high):
        self._label(ident, text)
        # AddEditSlider удобен, но перетаскивание параметра всё равно делается
        # мышью во вьюпорте, поэтому слайдер здесь — просто отображение.
        self.AddEditNumberArrows(ident, c4d.BFH_SCALEFIT, 0, 0)
        self.SetInt32(ident, int(value), int(low), int(high))

    def _float(self, ident, text, value, low, high, step):
        self._label(ident, text)
        self.AddEditNumberArrows(ident, c4d.BFH_SCALEFIT, 0, 0)
        self.SetFloat(ident, float(value), float(low), float(high), float(step))

    def _check(self, ident, text, value):
        self.AddStaticText(Param.LABEL_BASE + ident, c4d.BFH_LEFT, 130, 0, name='')
        self.AddCheckbox(ident, c4d.BFH_LEFT, 0, 0, text)
        self.SetBool(ident, bool(value))

    def refresh_enabled(self):
        """Гасит параметры, которые не действуют в текущем движке."""
        try:
            native = (self.tool.effective_engine() == 'native')
        except Exception:
            native = True
        own_only = (Param.INTERPOLATION, Param.SMOOTH, Param.PROFILE, Param.ANGLE,
                    Param.PROFILE_SHAPE, Param.MERGE, Param.MERGE_FACTOR)
        native_only = (Param.TENSION, Param.CURVE_MODE, Param.FLIP, Param.DELETE)
        for ident in own_only:
            self.Enable(ident, not native)
        for ident in native_only:
            self.Enable(ident, native)

    # -- синхронизация ------------------------------------------------------
    def InitValues(self):
        return True

    def Command(self, ident, msg):
        if self._syncing:
            return True
        try:
            if ident == Param.APPLY:
                self.tool.apply()
                return True
            if ident == Param.RESET:
                self.tool.reset_selection()
                return True
            self._pull()
            self.refresh_enabled()
            self.tool.on_options_changed(ident)
        except Exception as error:
            self.tool.report(error)
        return True

    def _pull(self):
        """Переносит значения из диалога в tool."""
        t = self.tool
        t.cuts = self.GetInt32(Param.CUTS)
        t.twist = self.GetInt32(Param.TWIST)
        t.smooth = self.GetFloat(Param.SMOOTH)
        t.profile = self.GetFloat(Param.PROFILE)
        t.angle = self.GetFloat(Param.ANGLE)
        t.merge_factor = self.GetFloat(Param.MERGE_FACTOR)
        t.merge = self.GetBool(Param.MERGE)
        t.show_surface = self.GetBool(Param.SHOW_SURFACE)
        t.show_removed = self.GetBool(Param.SHOW_REMOVED)
        t.interpolation = INTERPOLATIONS[max(0, min(2, self.GetInt32(Param.INTERPOLATION)))]
        t.profile_shape = PROFILE_SHAPES[max(0, min(len(PROFILE_SHAPES) - 1,
                                                   self.GetInt32(Param.PROFILE_SHAPE)))]
        t.input_mode = max(0, min(2, self.GetInt32(Param.SOURCE)))
        t.engine = max(0, min(1, self.GetInt32(Param.ENGINE)))
        t.tension = self.GetFloat(Param.TENSION)
        t.curve_mode = max(0, min(3, self.GetInt32(Param.CURVE_MODE)))
        t.flip = self.GetBool(Param.FLIP)
        t.delete_faces = self.GetBool(Param.DELETE)
        t.contour_mode = max(0, min(3, self.GetInt32(Param.CONTOUR_MODE)))
        t.drag_target = max(0, min(4, self.GetInt32(Param.DRAG_TARGET)))

    def push(self, ident=None):
        """Обновляет диалог из tool — например, после перетаскивания мышью."""
        if self._syncing:
            return
        self._syncing = True
        try:
            t = self.tool
            if ident is None or ident == Param.CUTS:
                self.SetInt32(Param.CUTS, int(t.cuts), 0, 512)
            if ident is None or ident == Param.TWIST:
                self.SetInt32(Param.TWIST, int(t.twist), -4096, 4096)
            if ident is None or ident == Param.SMOOTH:
                self.SetFloat(Param.SMOOTH, float(t.smooth), 0.0, 100.0, 0.01)
            if ident is None or ident == Param.PROFILE:
                self.SetFloat(Param.PROFILE, float(t.profile), -10.0, 10.0, 0.01)
            if ident is None or ident == Param.ANGLE:
                self.SetFloat(Param.ANGLE, float(t.angle), -360.0, 360.0, 0.1)
            if ident is None or ident == Param.MERGE_FACTOR:
                self.SetFloat(Param.MERGE_FACTOR, float(t.merge_factor), 0.0, 1.0, 0.01)
            if ident is None:
                self.SetBool(Param.MERGE, bool(t.merge))
                self.SetInt32(Param.SOURCE, int(t.input_mode), 0, 2)
                self.SetInt32(Param.ENGINE, int(t.engine), 0, 1)
                self.SetFloat(Param.TENSION, float(t.tension), -100.0, 100.0, 1.0)
                self.SetInt32(Param.CURVE_MODE, int(t.curve_mode), 0, 3)
                self.SetBool(Param.FLIP, bool(t.flip))
                self.SetBool(Param.DELETE, bool(t.delete_faces))
                self.SetInt32(Param.CONTOUR_MODE, int(t.contour_mode), 0, 3)
                self.SetInt32(Param.INTERPOLATION, INTERPOLATIONS.index(t.interpolation), 0, 2)
        except (AttributeError, RuntimeError):
            # Диалог мог быть уже закрыт — это не повод падать.
            pass
        finally:
            self._syncing = False
