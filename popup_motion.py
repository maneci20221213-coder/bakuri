"""Short, interruptible popup motion; window bounds and native coordinates stay fixed."""
import ctypes,sys
from PySide6.QtCore import QObject,QVariantAnimation,QEasingCurve,QRect,QPointF
from PySide6.QtWidgets import QApplication,QWidget

def motion_enabled():
    if QApplication.platformName()=='offscreen':return False
    if sys.platform=='win32':
        enabled=ctypes.c_int(1)
        try:
            if ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(enabled),0):return bool(enabled.value)
        except (OSError,AttributeError):pass
    return True

class PopupMotion(QObject):
    def __init__(self,owner,enabled=None):
        super().__init__(owner);self.owner=owner;self.enabled=motion_enabled() if enabled is None else enabled
        self.animation=QVariantAnimation(self);self.animation.valueChanged.connect(self.frame);self.animation.finished.connect(self.finished)
        self.closing=False;self.value=1.;self.targets={};self.callback=None
    def reset(self):
        self.animation.stop();self.callback=None;self.closing=False
        for button,rect in self.targets.items():button.setFixedSize(rect.size());button.move(rect.topLeft())
        self.targets={};self.owner.layout().setEnabled(True);self.owner.setEnabled(True)
        if self.enabled:self.owner.setWindowOpacity(1.)
    def open(self):
        if not self.enabled:return
        self.owner.layout().activate()
        self.targets={b:QRect(b.geometry()) for b in self.owner.buttons.values() if b.isVisible()}
        self.owner.layout().setEnabled(False);self.closing=False
        self.frame(0.);self.animation.setStartValue(0.);self.animation.setEndValue(1.)
        curve=QEasingCurve(QEasingCurve.OutBack);curve.setOvershoot(1.1)
        self.animation.setEasingCurve(curve);self.animation.setDuration(190);self.animation.start()
    def frame(self,value):
        self.value=float(value);center=QPointF(self.owner.rect().center());spread=.76+.24*self.value;scale=.86+.14*self.value
        for button,rect in self.targets.items():
            size=rect.size()*scale;position=center+(QPointF(rect.center())-center)*spread
            button.setFixedSize(size);button.move(round(position.x()-(size.width()-1)/2),round(position.y()-(size.height()-1)/2))
        self.owner.setWindowOpacity(max(0.,min(1.,self.value*1.5)))
    def close(self,callback=None):
        if self.closing:return
        if not self.owner.isVisible():return
        self.owner.monitor.stop();self.callback=callback
        if not self.enabled:
            QWidget.hide(self.owner)
            self.callback=None
            if callback:callback()
            return
        self.animation.stop();self.owner.layout().setEnabled(False);self.closing=True;self.owner.visibility.emit(False)
        self.animation.setStartValue(self.value);self.animation.setEndValue(0.)
        self.animation.setEasingCurve(QEasingCurve.InCubic);self.animation.setDuration(140);self.animation.start()
    def finished(self):
        if self.closing:
            callback=self.callback;self.callback=None
            QWidget.hide(self.owner);self.reset()
            if callback:callback()
        else:
            targets=self.targets;self.reset();self.targets=targets;self.value=1.
