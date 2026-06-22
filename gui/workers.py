"""后台工作线程与信号管理"""
from typing import Any, Callable, Optional
from PySide6.QtCore import QThread, Signal, QObject


class WorkerSignal(QObject):
    """Worker 信号集合"""
    progress = Signal(float, str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QThread):
    """通用后台工作线程"""

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignal()
        self._progress_cb_enabled = False

    def run(self):
        try:
            if "progress_cb" in self.kwargs:
                self.kwargs["progress_cb"] = self._progress_callback
                self._progress_cb_enabled = True
            result = self.func(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

    def _progress_callback(self, *args):
        try:
            if len(args) >= 2 and isinstance(args[1], str):
                pct = float(args[0])
                msg = str(args[1])
            elif len(args) >= 1:
                pct = float(args[0])
                msg = ""
            else:
                return
            pct = max(0.0, min(1.0, pct))
            self.signals.progress.emit(pct, msg)
        except (ValueError, TypeError):
            return
