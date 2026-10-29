import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QWidget
from app import QuickPopup
APP=QApplication.instance() or QApplication([])

class PopupMotionTests(unittest.TestCase):
 def popup(self,animate=True):
  popup=QuickPopup(animate=animate)
  self.addCleanup(lambda:QWidget.hide(popup));self.addCleanup(popup.motion.reset)
  popup.present(['a.png']);APP.processEvents();return popup
 def test_spring_open_and_shrink_close_emit_choice_once_after_closing(self):
  popup=self.popup();button=popup.buttons['pdf'];target=popup.motion.targets[button]
  popup.motion.animation.setCurrentTime(0);self.assertLess(button.width(),target.width())
  popup.motion.animation.setCurrentTime(240);self.assertEqual(button.geometry(),target)
  chosen=[];popup.chosen.connect(chosen.append);popup.pick('pdf');popup.pick('jpeg')
  self.assertFalse(popup.monitor.isActive());self.assertTrue(popup.motion.closing);self.assertEqual(chosen,[])
  popup.motion.animation.setCurrentTime(110);self.assertLess(button.width(),target.width())
  popup.motion.animation.setCurrentTime(180);self.assertFalse(popup.isVisible());self.assertEqual(chosen,['pdf'])
 def test_reopening_cancels_old_pending_choice_and_restores_sizes(self):
  popup=self.popup();popup.motion.animation.setCurrentTime(240)
  chosen=[];popup.chosen.connect(chosen.append);popup.pick('jpeg');popup.motion.animation.setCurrentTime(70)
  popup.present(['next.xls']);popup.motion.animation.setCurrentTime(240)
  self.assertTrue(popup.isVisible());self.assertTrue(popup.isEnabled());self.assertFalse(popup.motion.closing)
  self.assertEqual(chosen,[]);self.assertTrue(popup.buttons['xlsx'].isVisible());self.assertEqual(popup.buttons['pdf'].width(),100)
 def test_escape_during_opening_and_repeated_close_do_not_restart_animation(self):
  popup=self.popup();popup.motion.animation.setCurrentTime(60);popup.native_key(0x1B)
  popup.motion.animation.setCurrentTime(70);popup.hide();self.assertEqual(popup.motion.animation.currentTime(),70)
  popup.native_key(0x0D);popup.motion.animation.setCurrentTime(180);self.assertFalse(popup.isVisible())
 def test_disabled_motion_closes_and_selects_immediately(self):
  popup=self.popup(False);chosen=[];popup.chosen.connect(chosen.append);popup.pick('jpeg')
  self.assertEqual(chosen,['hwpx']);self.assertFalse(popup.isVisible())
 def test_show_never_preselects_top_button_for_images_or_pdf(self):
  from PySide6.QtCore import Qt
  popup=self.popup(False)
  for paths in [['a.png'],['a.pdf'],['a.jpg','b.png']]:
   popup.select('pdf');popup.hide();popup.present(paths)
   self.assertEqual(popup.current,'pdf');self.assertFalse(popup.buttons['pdf'].property('selected'))
   self.assertEqual(popup.buttons['pdf'].focusPolicy(),Qt.NoFocus)
   popup.native_key(0x27);self.assertEqual(popup.current,'jpeg');self.assertTrue(popup.buttons['jpeg'].property('selected'))
   self.assertFalse(popup.buttons['pdf'].property('selected'))
 def test_default_motion_does_not_depend_on_windows_system_effects(self):
  from unittest.mock import patch
  from popup_motion import motion_enabled
  with patch('popup_motion.QApplication.platformName',return_value='windows'):
   self.assertTrue(motion_enabled())
