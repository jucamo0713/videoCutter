#!/usr/bin/env python3
"""PySide6 GUI to preview and trim videos using ffmpeg helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from video_cutter import cut_video, format_timestamp, parse_timestamp

PREVIEW_LOOP_MARGIN_MS = 120
SESSION_FILE = Path.home() / ".video_cutter_session.json"


class VideoCutterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Cutter")
        self.resize(960, 640)

        self.file_path: Path | None = None
        self.last_dir: Path = Path.home()
        self.duration_cache: dict[Path, float | None] = {}
        self.start_ms = 0
        self.end_ms = 1000
        self.slider_max_range = 1000
        self.preview_paused = False
        self.slider_dragging = False
        self.pending_preview_restart = False
        self._normalizing_times = False

        self._build_ui()
        self._setup_player()
        self._connect_ui()
        self._update_controls(False)
        self._load_session()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)

        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Archivo:"))
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        file_layout.addWidget(self.file_edit, stretch=1)
        select_btn = QPushButton("Seleccionar…")
        select_btn.clicked.connect(self.select_file)
        file_layout.addWidget(select_btn)
        main_layout.addLayout(file_layout)

        self.start_edit = self._add_time_input(main_layout, "Inicio (seg o HH:MM:SS):")
        self.end_edit = self._add_time_input(main_layout, "Fin (seg o HH:MM:SS):")

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(320)
        main_layout.addWidget(self.video_widget, stretch=1)

        slider_layout = QHBoxLayout()
        self.preview_slider = QSlider(Qt.Horizontal)
        self.preview_slider.setRange(0, 1)
        self.preview_slider.setEnabled(False)
        slider_layout.addWidget(self.preview_slider)
        main_layout.addLayout(slider_layout)

        controls_layout = QHBoxLayout()
        self.rewind_button = QPushButton("⟲ -1s")
        self.play_button = QPushButton("Pausar")
        self.forward_button = QPushButton("+1s ⟳")
        controls_layout.addWidget(self.rewind_button)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.forward_button)
        main_layout.addLayout(controls_layout)

        self.cut_button = QPushButton("Generar recorte")
        main_layout.addWidget(self.cut_button)

        self.status_label = QLabel("Selecciona un video para comenzar.")
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

    def _add_time_input(self, layout: QVBoxLayout, label: str) -> QLineEdit:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        edit = QLineEdit()
        row.addWidget(edit, stretch=1)
        layout.addLayout(row)
        return edit

    # -------------------------------------------------------------- Player ---
    def _setup_player(self) -> None:
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_media_error)

    def _connect_ui(self) -> None:
        self.start_edit.editingFinished.connect(lambda: self._on_time_input("start"))
        self.end_edit.editingFinished.connect(lambda: self._on_time_input("end"))

        self.preview_slider.sliderPressed.connect(lambda: self._set_slider_dragging(True))
        self.preview_slider.sliderReleased.connect(lambda: self._set_slider_dragging(False))
        self.preview_slider.valueChanged.connect(self._on_slider_value_changed)

        self.play_button.clicked.connect(self._toggle_playback)
        self.rewind_button.clicked.connect(lambda: self._seek_by_ms(-1000))
        self.forward_button.clicked.connect(lambda: self._seek_by_ms(1000))
        self.cut_button.clicked.connect(self.on_cut_click)

    # ----------------------------------------------------------- File Flow ---
    def select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecciona un video",
            str(self.last_dir) if self.last_dir else "",
            "Videos (*.mp4 *.mov *.mkv *.avi *.webm);;Todos los archivos (*.*)",
        )
        if not path:
            return
        video_path = Path(path)
        self.file_path = video_path
        self.last_dir = video_path.parent
        self.file_edit.setText(str(video_path))
        self.status_label.setText("Cargando vista previa…")
        self._populate_default_times(video_path)
        self.player.setSource(QUrl.fromLocalFile(str(video_path)))
        self.pending_preview_restart = True
        self._update_controls(True)
        self._save_session()

    def _populate_default_times(self, video_path: Path) -> None:
        self.start_edit.setText("00:00:00")
        duration = self._get_cached_duration(video_path)
        if duration is not None:
            self.end_edit.setText(format_timestamp(duration))
        else:
            self.end_edit.setText("00:00:10")
        self._normalize_times("start")

    # ---------------------------------------------------------- Validation ---
    def _on_time_input(self, field: str) -> None:
        if self._normalizing_times:
            return
        self._normalizing_times = True
        try:
            self._normalize_times(field)
        finally:
            self._normalizing_times = False

    def _normalize_times(self, field: str) -> None:
        start_text = self.start_edit.text().strip()
        end_text = self.end_edit.text().strip()
        try:
            start_ms = int(parse_timestamp(start_text) * 1000) if start_text else 0
        except ValueError:
            start_ms = 0
        try:
            end_ms = int(parse_timestamp(end_text) * 1000) if end_text else start_ms + 1000
        except ValueError:
            end_ms = start_ms + 1000

        if start_ms < 0:
            start_ms = 0
        duration = self._get_cached_duration(self.file_path)
        if duration is not None:
            duration_ms = int(duration * 1000)
            end_ms = min(end_ms, duration_ms)
            if start_ms >= duration_ms:
                start_ms = max(0, duration_ms - 1000)
                end_ms = duration_ms

        if start_ms >= end_ms:
            if field == "start":
                end_ms = start_ms + 1
            else:
                start_ms = max(0, end_ms - 1)

        self.start_ms = start_ms
        self.end_ms = end_ms
        self.start_edit.setText(format_timestamp(start_ms / 1000))
        self.end_edit.setText(format_timestamp(end_ms / 1000))
        self._configure_slider()
        self._restart_preview_if_ready()
        if self.file_path:
            self._save_session()

    # -------------------------------------------------------------- Slider ---
    def _configure_slider(self) -> None:
        duration = max(1, self.end_ms - self.start_ms)
        self.slider_max_range = duration
        self.preview_slider.setRange(0, duration)
        self.preview_slider.setSingleStep(max(1, duration // 250))
        self.preview_slider.setValue(0)

    def _set_slider_dragging(self, dragging: bool) -> None:
        self.slider_dragging = dragging
        if not dragging:
            self._apply_slider_value()

    def _on_slider_value_changed(self, _value: int) -> None:
        if self.slider_dragging:
            self._apply_slider_value()

    def _apply_slider_value(self) -> None:
        if not self.file_path:
            return
        relative = int(self.preview_slider.value())
        target = self.start_ms + relative
        upper_bound = max(self.start_ms, self.end_ms - PREVIEW_LOOP_MARGIN_MS)
        target = min(upper_bound, max(self.start_ms, target))
        self.player.setPosition(target)
        if not self.preview_paused:
            self.player.play()

    # ------------------------------------------------------------ Playback ---
    def _toggle_playback(self) -> None:
        if not self.file_path:
            return
        self.preview_paused = not self.preview_paused
        if self.preview_paused:
            self.play_button.setText("Reanudar")
            self.player.pause()
            self.status_label.setText("Vista previa en pausa")
        else:
            self.play_button.setText("Pausar")
            self.player.play()
            self.status_label.setText("Reproduciendo vista previa…")

    def _seek_by_ms(self, delta: int) -> None:
        if not self.file_path:
            return
        position = self.player.position()
        target = position + delta
        upper_bound = max(self.start_ms, self.end_ms - PREVIEW_LOOP_MARGIN_MS)
        target = min(upper_bound, max(self.start_ms, target))
        self.player.setPosition(target)
        if not self.slider_dragging:
            self.preview_slider.setValue(max(0, target - self.start_ms))
        if not self.preview_paused:
            self.player.play()

    def _on_position_changed(self, position: int) -> None:
        if not self.file_path:
            return
        if not self.preview_paused and position >= self.end_ms - PREVIEW_LOOP_MARGIN_MS:
            self.player.setPosition(self.start_ms)
            position = self.start_ms
        if not self.slider_dragging:
            relative = max(0, min(self.slider_max_range, position - self.start_ms))
            self.preview_slider.blockSignals(True)
            self.preview_slider.setValue(relative)
            self.preview_slider.blockSignals(False)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if self.pending_preview_restart and status in (
            QMediaPlayer.BufferingMedia,
            QMediaPlayer.BufferedMedia,
            QMediaPlayer.LoadedMedia,
        ):
            self.pending_preview_restart = False
            self._restart_preview(auto_play=True)

    def _on_media_error(self, error: QMediaPlayer.Error, message: str) -> None:
        if error == QMediaPlayer.NoError:
            return
        QMessageBox.critical(self, "Error", f"No se pudo cargar el video:\n{message}")
        self.status_label.setText("Error cargando el video.")

    def _restart_preview_if_ready(self) -> None:
        if not self.file_path:
            return
        if self.player.mediaStatus() in (
            QMediaPlayer.BufferingMedia,
            QMediaPlayer.BufferedMedia,
            QMediaPlayer.LoadedMedia,
        ):
            self._restart_preview(auto_play=not self.preview_paused)
        else:
            self.pending_preview_restart = True

    def _restart_preview(self, auto_play: bool) -> None:
        self.player.setPosition(self.start_ms)
        self.preview_slider.setValue(0)
        if auto_play:
            self.preview_paused = False
            self.play_button.setText("Pausar")
            self.player.play()
            self.status_label.setText("Reproduciendo vista previa…")
        else:
            self.player.pause()
            self.preview_paused = True
            self.play_button.setText("Reanudar")
            self.status_label.setText("Vista previa lista (pausada)")

    def _update_controls(self, enabled: bool) -> None:
        for widget in (
            self.preview_slider,
            self.play_button,
            self.rewind_button,
            self.forward_button,
        ):
            widget.setEnabled(enabled)
        self.cut_button.setEnabled(enabled)

    # ------------------------------------------------------------ Cutting ---
    def on_cut_click(self) -> None:
        if not self.file_path:
            QMessageBox.warning(self, "Falta archivo", "Selecciona un archivo de video.")
            return
        start = self.start_edit.text().strip()
        end = self.end_edit.text().strip()
        if not start or not end:
            QMessageBox.warning(self, "Faltan tiempos", "Introduce inicio y fin.")
            return
        suggested = (
            self.file_path.with_name(f"{self.file_path.stem}_recorte{self.file_path.suffix}")
            if self.file_path
            else Path("")
        )
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar recorte",
            str(suggested),
            "Videos (*.mp4 *.mov *.mkv *.avi *.webm);;Todos los archivos (*.*)",
        )
        if not output_path:
            return

        self.cut_button.setEnabled(False)
        self.status_label.setText("Procesando recorte…")
        threading.Thread(
            target=self._run_cut,
            args=(self.file_path, start, end, Path(output_path)),
            daemon=True,
        ).start()

    def _run_cut(self, input_path: Path, start: str, end: str, output: Path) -> None:
        try:
            result = cut_video(input_path, start, end, output)
        except Exception as exc:  # noqa: BLE001
            QTimer.singleShot(0, lambda: self._on_cut_failed(str(exc)))
        else:
            QTimer.singleShot(0, lambda: self._on_cut_success(str(result)))

    def _on_cut_success(self, path: str) -> None:
        self.cut_button.setEnabled(True)
        self.status_label.setText(f"Recorte listo: {path}")
        QMessageBox.information(self, "Recorte listo", f"Video generado en:\n{path}")
        self._save_session()

    def _on_cut_failed(self, message: str) -> None:
        self.cut_button.setEnabled(True)
        self.status_label.setText("Error generando el recorte.")
        QMessageBox.critical(self, "Error", message)

    # ------------------------------------------------------------- Helpers ---
    def _get_cached_duration(self, video_path: Path | None) -> float | None:
        if not video_path or not video_path.exists():
            return None
        if video_path in self.duration_cache:
            return self.duration_cache[video_path]
        duration = self._probe_duration(video_path)
        self.duration_cache[video_path] = duration
        return duration

    def _probe_duration(self, video_path: Path) -> float | None:
        ffprobe_path = shutil.which("ffprobe")
        if not ffprobe_path:
            return None
        command = [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            return None
        try:
            return float(result.stdout.strip())
        except (ValueError, AttributeError):
            return None

    def closeEvent(self, event):  # type: ignore[override]
        self.player.stop()
        self._save_session()
        super().closeEvent(event)

    # -------------------------------------------------------- Session I/O ---
    def _load_session(self) -> None:
        if not SESSION_FILE.exists():
            return
        try:
            data = json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return

        last_dir = data.get("last_dir")
        if last_dir:
            self.last_dir = Path(last_dir)

        file_str = data.get("file")
        start = data.get("start")
        end = data.get("end")
        if not file_str:
            return

        path = Path(file_str)
        self.last_dir = path.parent
        if not path.exists():
            return

        self.file_path = path
        self.file_edit.setText(str(path))
        if start:
            self.start_edit.setText(start)
        if end:
            self.end_edit.setText(end)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.pending_preview_restart = True
        self._update_controls(True)
        self._normalize_times("start")
        self.status_label.setText("Vista previa lista.")

    def _save_session(self) -> None:
        data = {
            "file": str(self.file_path) if self.file_path else "",
            "start": self.start_edit.text().strip(),
            "end": self.end_edit.text().strip(),
            "last_dir": str(self.last_dir) if self.last_dir else "",
        }
        try:
            SESSION_FILE.write_text(json.dumps(data))
        except OSError:
            pass


def main() -> None:
    app = QApplication(sys.argv)
    window = VideoCutterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
