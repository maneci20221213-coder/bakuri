"""Developer-only native Windows timer/paint check; no product test flags."""
import os,sys
os.environ['QT_QPA_PLATFORM']='windows'
from PySide6.QtCore import Qt,QAbstractAnimation
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from app import QuickPopup

app=QApplication([]);popup=QuickPopup()
previous_cursor=QCursor.pos();QCursor.setPos(app.primaryScreen().availableGeometry().center())
assert popup.motion.enabled,'Popup motion must be enabled on native Windows'
frames=[];popup.motion.animation.valueChanged.connect(lambda value:frames.append(popup.buttons['pdf'].y()))
for source in ['a.png','a.pdf']:
 frames.clear();popup.present([source]);assert not popup.buttons['pdf'].property('selected')
 QTest.qWait(320)
 assert popup.isVisible() and popup.motion.animation.state()==QAbstractAnimation.Stopped
 assert len(set(frames))>=3,frames
 assert popup.buttons['pdf'].width()==100
 assert not popup.buttons['pdf'].property('selected'),'Initial PDF focus flash'
 popup.grab().save('native-popup-preview.png')
 popup.hide();assert popup.motion.closing
 QTest.qWait(240);assert not popup.isVisible()
QCursor.setPos(previous_cursor)
print('Native Windows popup timer animation and initial focus verification passed.')
