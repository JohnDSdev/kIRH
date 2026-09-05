# SPDX-License-Identifier: GPL-3.0-or-later

from krita import Krita, Extension
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .rim import make_inner_highlight_bgra


PLUGIN_NAME = "Inner Rim Highlight"


class HighlightSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(390)

        outer = QVBoxLayout(self)

        intro = QLabel(
            "Creates a new white paint layer that fades inward from the "
            "transparent edge of the active layer. The original layer is not changed."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        form_host = QWidget(self)
        form = QFormLayout(form_host)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.width_box = QSpinBox(self)
        self.width_box.setRange(1, 500)
        self.width_box.setValue(34)
        self.width_box.setSuffix(" px")
        self.width_box.setToolTip("How far the white highlight fades inward from the edge.")
        form.addRow("Width:", self.width_box)

        self.opacity_box = QSpinBox(self)
        self.opacity_box.setRange(1, 100)
        self.opacity_box.setValue(82)
        self.opacity_box.setSuffix(" %")
        self.opacity_box.setToolTip("Maximum opacity of the generated white highlight.")
        form.addRow("Opacity:", self.opacity_box)

        self.softness_box = QSpinBox(self)
        self.softness_box.setRange(0, 100)
        self.softness_box.setValue(72)
        self.softness_box.setSuffix(" %")
        self.softness_box.setToolTip(
            "Higher values spread the fade farther inward; lower values keep it tighter to the edge."
        )
        form.addRow("Softness:", self.softness_box)

        self.threshold_box = QSpinBox(self)
        self.threshold_box.setRange(1, 128)
        self.threshold_box.setValue(8)
        self.threshold_box.setToolTip(
            "Pixels with alpha below this value count as transparent. Raise this if faint stray pixels create unwanted rims."
        )
        form.addRow("Alpha threshold:", self.threshold_box)

        self.selection_check = QCheckBox("Limit highlight to the current selection", self)
        self.selection_check.setChecked(False)
        self.selection_check.setToolTip(
            "Useful when you only want the automatic highlight on part of the character."
        )
        form.addRow("", self.selection_check)

        outer.addWidget(form_host)

        note = QLabel(
            "Tip: the result is a normal paint layer, so you can erase the places where you do not want a highlight."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        outer.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("Generate")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def values(self):
        return {
            "rim_width": self.width_box.value(),
            "opacity": self.opacity_box.value() / 100.0,
            "softness": self.softness_box.value() / 100.0,
            "threshold": self.threshold_box.value(),
            "limit_to_selection": self.selection_check.isChecked(),
        }


class EdgeHighlightExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(
            "soft_edge_highlight_generate",
            "Inner Rim Highlight…",
            "tools/scripts",
        )
        action.triggered.connect(self.run)

    def _parent_widget(self):
        win = Krita.instance().activeWindow()
        return win.qwindow() if win is not None else None

    def _warn(self, text):
        QMessageBox.warning(self._parent_widget(), PLUGIN_NAME, text)

    def run(self):
        app = Krita.instance()
        doc = app.activeDocument()
        if doc is None:
            self._warn("Open a document first.")
            return

        node = doc.activeNode()
        if node is None:
            self._warn("Select the layer you want to highlight first.")
            return

        # The implementation writes BGRA/U8 data. Keeping this restriction
        # explicit is much safer than silently corrupting a 16-bit/CMYK layer.
        if node.colorModel() != "RGBA" or node.colorDepth() != "U8":
            self._warn(
                "This version supports 8-bit RGBA layers only.\n\n"
                "Your active layer is {} / {}.".format(node.colorModel(), node.colorDepth())
            )
            return

        bounds = node.bounds()
        w = bounds.width()
        h = bounds.height()
        if w <= 0 or h <= 0:
            self._warn("The active layer has no visible pixels.")
            return

        pixel_count = w * h
        if pixel_count > 24_000_000:
            answer = QMessageBox.question(
                self._parent_widget(),
                PLUGIN_NAME,
                "The active layer's pixel bounds are very large ({:,} pixels).\n\n"
                "The plugin can still run, but it may take a while. Continue?".format(pixel_count),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        dialog = HighlightSettingsDialog(self._parent_widget())
        if dialog.exec_() != QDialog.Accepted:
            return
        settings = dialog.values()

        x = bounds.x()
        y = bounds.y()

        progress = QProgressDialog(
            "Generating soft edge highlight…",
            "Cancel",
            0,
            1000,
            self._parent_widget(),
        )
        progress.setWindowTitle(PLUGIN_NAME)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(250)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        cancelled = [False]

        def update_progress(fraction):
            if cancelled[0]:
                return
            progress.setValue(max(0, min(1000, int(fraction * 1000))))
            QApplication.processEvents()
            if progress.wasCanceled():
                cancelled[0] = True
                raise RuntimeError("cancelled")

        try:
            update_progress(0.01)
            raw = bytes(node.projectionPixelData(x, y, w, h))
            expected = w * h * 4
            if len(raw) < expected:
                self._warn(
                    "Krita returned less pixel data than expected. The layer may use a pixel format this plugin cannot read."
                )
                return

            alpha = raw[3:expected:4]
            del raw

            selection = None
            if settings["limit_to_selection"]:
                sel = doc.selection()
                if sel is None:
                    self._warn("There is no current selection to limit the highlight to.")
                    return
                selection = bytes(sel.pixelData(x, y, w, h))
                if len(selection) != w * h or not any(selection):
                    self._warn("The current selection does not overlap this layer.")
                    return

            pixels = make_inner_highlight_bgra(
                alpha,
                w,
                h,
                rim_width=settings["rim_width"],
                opacity=settings["opacity"],
                softness=settings["softness"],
                threshold=settings["threshold"],
                selection=selection,
                progress=update_progress,
            )

            if cancelled[0]:
                return

            out = doc.createNode("Inner Rim Highlight", "paintlayer")
            if out is None:
                self._warn("Krita could not create the output paint layer.")
                return

            # Match the source layer's exact colorspace/profile so the BGRA/U8
            # buffer is interpreted correctly.
            if not out.setColorSpace(node.colorModel(), node.colorDepth(), node.colorProfile()):
                out.remove()
                self._warn("Krita could not match the output layer's color space to the source layer.")
                return

            parent = node.parentNode()
            if parent is None:
                parent = doc.rootNode()

            if not parent.addChildNode(out, node):
                out.remove()
                self._warn("Krita could not insert the highlight layer above the active layer.")
                return

            ok = out.setPixelData(bytes(pixels), x, y, w, h)
            if not ok:
                out.remove()
                self._warn("Krita could not write the generated pixels to the highlight layer.")
                return

            doc.setActiveNode(out)
            doc.refreshProjection()
            progress.setValue(1000)

        except RuntimeError as exc:
            if str(exc) != "cancelled":
                self._warn("The plugin stopped unexpectedly:\n{}".format(exc))
        except Exception as exc:
            self._warn(
                "The plugin hit an unexpected error:\n\n{}\n\n"
                "The original layer was not modified.".format(exc)
            )
        finally:
            progress.close()


Krita.instance().addExtension(EdgeHighlightExtension(Krita.instance()))
