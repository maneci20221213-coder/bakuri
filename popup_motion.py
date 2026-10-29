"""Short, interruptible popup motion; window bounds and native coordinates stay fixed."""
from PySide6.QtCore import QObject,QVariantAnimation,QEasingCurve,QRect,QPointF
from PySide6.QtWidgets import QApplication,QWidget

def motion_enabled():
    if QApplication.platformName()=='offscreen':return False
    return True

class PopupMotion(QObject):
    def __init__(self,owner,enabled=None):
        super().__init__(owner);self.owner=owner;self.enabled=motion_enabled() if enabled is None else enabled
        self.animation=QVariantAnimation(self);self.animation.valueChanged.connect(self.frame);self.animation.finished.connect(self.finished)
        self.closing=False;self.value=1.;self.targets={};self.callback=None
    def reset(self):
        self.animation.stop();self.callback=None;self.closing=False
        for button,rect in self.targets.items():button.move(rect.topLeft())
        self.targets={};self.owner.layout().setEnabled(True);self.owner.setEnabled(True)
        if self.enabled:self.owner.setWindowOpacity(1.)
    def open(self):
        if not self.enabled:return
        self.owner.layout().invalidate();self.owner.layout().activate()
        self.targets={b:QRect(b.geometry()) for b in self.owner.buttons.values() if b.isVisible()}
        self.owner.layout().setEnabled(False);self.closing=False
        self.frame(0.);self.animation.setStartValue(0.);self.animation.setEndValue(1.)
        curve=QEasingCurve(QEasingCurve.OutCubic)
        self.animation.setEasingCurve(curve);self.animation.setDuration(180);self.animation.start()
    def frame(self,value):
        self.value=max(0.,min(1.,float(value)));center=QPointF(self.owner.rect().center());spread=.65+.35*self.value
        for button,rect in self.targets.items():
            # Translate from the exact target top-left; QRect.center rounds
            # even-sized rectangles and otherwise causes a final pixel jump.
            target_center=QPointF(rect.x()+rect.width()/2,rect.y()+rect.height()/2)
            offset=(center-target_center)*(1.-spread)
            button.move(rect.x()+round(offset.x()),rect.y()+round(offset.y()))
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
        self.animation.setEasingCurve(QEasingCurve.InCubic);self.animation.setDuration(180);self.animation.start()
    def finished(self):
        if self.closing:
            callback=self.callback;self.callback=None
            QWidget.hide(self.owner);self.reset()
            if callback:callback()
        else:
            # Keep the settled layout frozen while visible. Re-enabling it
            # here applies queued hover/style layout requests after the motion.
            self.frame(1.)
