import sys, os, threading, json
from pathlib import Path
from build_channel import DEVELOPMENT,SETTINGS_APP,SERVER_NAME,BUILD_LABEL
from user_messages import friendly_error

def startup_error(kind,value,tb):
    running='QApplication' in globals() and QApplication.instance() is not None
    message=friendly_error(value,'conversion' if running else 'startup')
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,message,'바꾸리 안내',16)
sys.excepthook=startup_error
if __name__=='__main__' and not DEVELOPMENT:
    from velopack_bootstrap import bootstrap
    bootstrap()

from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSettings, QEvent, QUrl, QPoint
from PySide6.QtGui import QCursor, QDesktopServices, QColor, QBrush, QShortcut, QKeySequence
from PySide6.QtWidgets import *
from engine import convert, SUPPORTED, SPREADSHEETS, can_convert, can_merge, IMAGES, HANCOM
from file_list import Files
from settings_ui import SettingsDialog
from theme import icon, stylesheet
from version import VERSION
from jobs import JobControl,Cancelled
from compression import compress
from help_ui import HelpDialog
from work_ui import CompressionResults,add_profiles,read_options

class OutputFormatDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        if not index.flags() & Qt.ItemIsEnabled:
            opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index)
            painter.save();painter.fillRect(opt.rect,QColor('#F2F5F9'))
            painter.setPen(QColor('#A4AFBD'));painter.setFont(opt.font)
            painter.drawText(opt.rect.adjusted(6,0,-4,0),Qt.AlignVCenter|Qt.AlignLeft,opt.text)
            painter.restore()
        else:super().paint(painter,option,index)

class Events(QObject):
    message=Signal(str); done=Signal(object); error=Signal(str); selected=Signal(object); clicked=Signal(object); dismiss=Signal(); popup_key=Signal(int); progress=Signal(int,str)
class QuickPopup(QWidget):
    chosen=Signal(str); visibility=Signal(bool)
    def __init__(self,animate=None):
        super().__init__(None,Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setFixedSize(350,264);self.setFocusPolicy(Qt.StrongFocus);self.preparing=False
        self.setStyleSheet('QuickPopup {background:transparent;} QPushButton {background:rgba(255,255,255,225);color:#26354A;border:1px solid rgba(218,228,242,230);border-radius:12px;padding:0;} QPushButton:hover {background:rgba(239,246,255,245);border-color:#96C1F8;} QPushButton[selected="true"] {background:rgba(244,249,255,245);border:2px solid #2E83F2;} QLabel {background:transparent;border:0;color:#26354A;font-family:"Malgun Gothic","Noto Sans CJK KR",sans-serif;}')

        self.actions={}; self.origin=0; self.origin_tab=0; self.monitor=QTimer(self); self.monitor.setInterval(25); self.monitor.timeout.connect(self.check_source)

        grid=QGridLayout(self); grid.setContentsMargins(12,12,12,12); grid.setSpacing(8); self.buttons={}
        for key,label,arrow,pos in [('pdf','PDF','↑',(0,1)),('png','PNG','←',(1,0)),('jpeg','JPEG','→',(1,2)),('more','확장 기능','↓',(2,1)),('hwpx','HWPX','',(1,1)),('xlsx','XLSX','',(1,1)),('compress','용량 축소','',(1,1))]:
            button=QPushButton();button.setFocusPolicy(Qt.NoFocus);button.setAutoDefault(False);button.setDefault(False); button.setAccessibleName(label); button.setCursor(Qt.PointingHandCursor);button.setFixedSize(88 if key in {'hwpx','xlsx','compress'} else 100,68 if key in {'hwpx','xlsx','compress'} else 74)
            content=QVBoxLayout(button);content.setContentsMargins(6,5,6,6);content.setSpacing(1)
            image=QLabel();image.setAttribute(Qt.WA_TransparentForMouseEvents);image.setAlignment(Qt.AlignCenter);image.setPixmap(icon('plus' if key=='more' else key).pixmap(30,32));content.addWidget(image)
            text=QLabel(label);text.setAttribute(Qt.WA_TransparentForMouseEvents);text.setAlignment(Qt.AlignCenter);text.setStyleSheet('font-size:12px;font-weight:600;');content.addWidget(text)
            if arrow:
                indicator=QLabel(arrow,button);indicator.setAttribute(Qt.WA_TransparentForMouseEvents);indicator.setGeometry(button.width()-25,8,15,18);indicator.setStyleSheet('color:#60718A;font-size:14px;')
            shadow=QGraphicsDropShadowEffect(button);shadow.setBlurRadius(12);shadow.setOffset(0,3);shadow.setColor(__import__('PySide6.QtGui',fromlist=['QColor']).QColor(20,43,76,28));button.setGraphicsEffect(shadow)
            button.setProperty('selected',False);button.installEventFilter(self);button.clicked.connect(lambda checked=False,k=key:self.pick(k));grid.addWidget(button,*pos,Qt.AlignCenter);self.buttons[key]=button
        self.note=QLabel('방향키 → Enter · Esc 닫기'); self.note.setAlignment(Qt.AlignCenter); self.note.hide()
        from popup_motion import PopupMotion
        self.motion=PopupMotion(self,animate)
        self.current='pdf'; QApplication.instance().installEventFilter(self)
    def clicked_at(self,point):
        if not self.isVisible(): return
        if sys.platform=='win32':
            import win32gui
            x,y=win32gui.ScreenToClient(int(self.winId()),tuple(point)); rect=win32gui.GetClientRect(int(self.winId()));w=max(1,rect[2]);h=max(1,rect[3])
            position=QPoint(round(x*self.width()/w),round(y*self.height()/h))
        else: position=self.mapFromGlobal(QPoint(*point))
        if not any(b.isVisible() and b.geometry().contains(position) for b in self.buttons.values()): self.hide()
    def check_source(self):
        if sys.platform=='win32' and self.origin:
            from windows import source_active, escape_pressed
            if escape_pressed(): self.hide(); return
            if not source_active(self.origin,self.origin_tab,int(self.winId())): self.hide()
    def showEvent(self,event): super().showEvent(event); self.visibility.emit(True)
    def hideEvent(self,event): self.monitor.stop(); self.visibility.emit(False); super().hideEvent(event)
    def event(self,event):
        if event.type()==QEvent.WindowDeactivate and self.isVisible():
            if self.origin: self.check_source()
            else: self.hide()
        return super().event(event)
    def hide(self):
        self.motion.close()
    def present(self,paths,origin=0,tab=0):
        self.preparing=True
        self.motion.reset()
        self.current='pdf'
        for button in self.buttons.values():
            button.setProperty('selected',False);button.clearFocus();button.style().unpolish(button);button.style().polish(button);button.update()
        self.origin=origin; self.origin_tab=tab
        extensions={Path(p).suffix.lower() for p in paths}
        images=bool(paths) and extensions <= IMAGES
        pdfs=extensions=={'.pdf'}
        self.actions={}
        labels={'pdf':('PDF','pdf'),'png':('PNG','png'),'jpeg':('JPEG','jpeg')}
        if images:
            target='jpeg' if extensions=={'.png'} else 'png'
            self.actions={'png':target,'jpeg':'hwpx'}
            labels['png']=(target.upper(),target);labels['jpeg']=('한글','hwpx')
        elif pdfs:
            self.actions={'pdf':'pdf_merge','jpeg':'hwpx'}
            labels['pdf']=('PDF 합치기','pdf');labels['jpeg']=('한글','hwpx')
        elif extensions and extensions <= HANCOM and len(paths)>1:
            self.actions={'pdf':'hwp_merge'}
            labels['pdf']=('한글 합치기','hwpx')
        for key,(label,asset) in labels.items():
            button=self.buttons[key];button.setAccessibleName(label)
            button.layout().itemAt(0).widget().setPixmap(icon(asset).pixmap(30,32))
            button.layout().itemAt(1).widget().setText(label)
        self.buttons['pdf'].setEnabled(True)
        self.buttons['pdf'].setToolTip('PDF 파일을 두 개 이상 선택해 주세요.' if pdfs and len(paths)<2 else '')
        self.buttons['hwpx'].setVisible(bool(paths) and all(Path(p).suffix.lower()=='.hwp' for p in paths))
        self.buttons['xlsx'].setVisible(bool(paths) and all(Path(p).suffix.lower() in SPREADSHEETS- {'.xlsx'} for p in paths))
        self.buttons['compress'].setVisible(bool(paths) and all(Path(p).suffix.lower() in IMAGES|{'.pdf'} for p in paths))
        self.note.setText(f'{len(paths)}개 파일 · 방향키 → Enter · Esc 닫기')
        self.current='pdf'; point=QCursor.pos(); screen=QApplication.screenAt(point) or QApplication.primaryScreen(); rect=screen.availableGeometry()
        self.move(max(rect.left(),min(point.x()-self.width()//2,rect.right()-self.width()+1)),max(rect.top(),min(point.y()-self.height()//2,rect.bottom()-self.height()+1)))
        if self.motion.enabled:self.setWindowOpacity(0.)
        self.show();self.activateWindow();self.setFocus(Qt.PopupFocusReason);self.monitor.start();self.visibility.emit(True);self.motion.open();self.preparing=False
    def select(self,key):
        if key not in self.buttons or not self.buttons[key].isVisible() or not self.buttons[key].isEnabled(): return
        self.current=key
        for name,button in self.buttons.items():
            button.setProperty('selected',name==key);button.style().unpolish(button);button.style().polish(button);button.update()
        self.setFocus(Qt.OtherFocusReason)
    def native_key(self,vk):
        if not self.isVisible() or self.motion.closing: return
        mapping={0x26:Qt.Key_Up,0x28:Qt.Key_Down,0x25:Qt.Key_Left,0x27:Qt.Key_Right,0x0D:Qt.Key_Return,0x1B:Qt.Key_Escape,0x09:Qt.Key_Tab,0x20:Qt.Key_Space}
        key=mapping.get(vk)
        if key is not None:self.handle_key(key)
    def pick(self,key):
        if not self.isVisible() or self.motion.closing:return
        action=self.actions.get(key,key)
        self.motion.close(lambda:self.chosen.emit(action))
    def eventFilter(self,obj,event):
        if self.preparing or (hasattr(self,'motion') and self.motion.closing):return super().eventFilter(obj,event)
        if self.isVisible() and event.type()==QEvent.Enter:
            key=next((k for k,b in self.buttons.items() if b is obj),None)
            if key:self.select(key)
        if self.isVisible() and event.type()==QEvent.MouseButtonPress:
            point=self.mapFromGlobal(event.globalPosition().toPoint())
            if not any(b.isVisible() and b.geometry().contains(point) for b in self.buttons.values()): self.hide()
        if self.isVisible() and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Up,Qt.Key_Down,Qt.Key_Left,Qt.Key_Right,Qt.Key_Return,Qt.Key_Enter,Qt.Key_Escape,Qt.Key_Tab,Qt.Key_Space):
            self.keyPressEvent(event); return True
        return super().eventFilter(obj,event)
    def move_selection(self,key):
        center=next((name for name in ('hwpx','xlsx','compress') if self.buttons[name].isVisible()),None)
        middle=center or 'pdf'
        neighbors={
            'pdf':{Qt.Key_Left:'png',Qt.Key_Right:'jpeg',Qt.Key_Down:center or 'more'},
            'png':{Qt.Key_Up:'pdf',Qt.Key_Down:'more',Qt.Key_Right:center or 'jpeg'},
            'jpeg':{Qt.Key_Up:'pdf',Qt.Key_Down:'more',Qt.Key_Left:center or 'png'},
            'more':{Qt.Key_Up:middle,Qt.Key_Left:'png',Qt.Key_Right:'jpeg'},
        }
        if center:neighbors[center]={Qt.Key_Up:'pdf',Qt.Key_Down:'more',Qt.Key_Left:'png',Qt.Key_Right:'jpeg'}
        target=neighbors.get(self.current,{}).get(key)
        if target:self.select(target)
    def handle_key(self,key):
        if self.motion.closing:return
        if key in (Qt.Key_Up,Qt.Key_Down,Qt.Key_Left,Qt.Key_Right):self.move_selection(key)
        elif key==Qt.Key_Tab:
            visible=[k for k in ('pdf','png','hwpx','xlsx','compress','jpeg','more') if self.buttons[k].isVisible() and self.buttons[k].isEnabled()]
            self.select(visible[(visible.index(self.current)+1)%len(visible)])
        elif key in (Qt.Key_Return,Qt.Key_Enter,Qt.Key_Space):self.pick(self.current)
        elif key==Qt.Key_Escape:self.hide()
    def keyPressEvent(self,event):
        self.handle_key(event.key());event.accept()

class Window(QWidget):
    def __init__(self):
        super().__init__(); self.bus=Events(); self.busy=False;self.control=None;self.compression_rows=[];self.job_kind='convert'; self.settings=QSettings('Bakuri',SETTINGS_APP)
        first_run=not self.settings.allKeys() and not QSettings('Bakuri','Python Trial').allKeys()
        if not DEVELOPMENT and not self.settings.value('settings_migrated',False,type=bool):
            legacy=QSettings('Bakuri','Python Trial')
            for key in legacy.allKeys():
                if not self.settings.contains(key):self.settings.setValue(key,legacy.value(key))
            self.settings.setValue('settings_migrated',True);self.settings.sync()
        self.setWindowTitle(f'바꾸리 파일 변환기 {BUILD_LABEL}'); self.resize(840,650); self.setMinimumSize(760,540); self.setObjectName('mainWindow');self.setStyleSheet(stylesheet())
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        toolbar=QFrame();self.toolbar=toolbar;toolbar.setObjectName('toolbar');row=QHBoxLayout(toolbar);row.setContentsMargins(16,16,16,14);row.setSpacing(10)
        add=QPushButton('파일 추가');add.setObjectName('addFiles');add.setIcon(icon('plus'));add.clicked.connect(self.choose);row.addWidget(add)
        sort=QPushButton('이름순 정렬');sort.setIcon(icon('sort'));sort.clicked.connect(lambda:self.files.sort_names());row.addWidget(sort)
        remove=QPushButton('선택 제거');remove.setIcon(icon('delete'));remove.setToolTip('체크한 파일을 목록에서 제거합니다. 원본은 보존됩니다.');remove.clicked.connect(self.remove);row.addWidget(remove)
        row.addStretch();self.count_label=QLabel('0 / 0개 선택');self.count_label.setObjectName('selectionCount');row.addWidget(self.count_label)
        settings_button=QPushButton();settings_button.setObjectName('settings');settings_button.setIcon(icon('gear'));settings_button.setAccessibleName('설정');settings_button.setToolTip('설정');settings_button.clicked.connect(self.open_settings);row.addWidget(settings_button)
        self.help_button=QPushButton('?');self.help_button.setObjectName('help');self.help_button.setAccessibleName('사용 설명');self.help_button.setToolTip('사용 설명 (F1)');self.help_button.clicked.connect(self.open_help);row.addWidget(self.help_button)
        settings_button.setFixedSize(40,40);self.help_button.setFixedSize(40,40)
        self.help_shortcut=QShortcut('F1',self);self.help_shortcut.activated.connect(self.open_help)
        layout.addWidget(toolbar)
        self.mode_tabs=QTabBar();self.mode_tabs.setStyleSheet('QTabBar::tab {background:#FFFFFF;color:#60718A;padding:12px 24px;border-bottom:2px solid #E2E8F0;} QTabBar::tab:selected {color:#2E83F2;border-bottom:2px solid #2E83F2;font-weight:600;}');self.mode_tabs.addTab('파일 변환');self.mode_tabs.addTab('파일명 변경');layout.addWidget(self.mode_tabs)
        self.files=Files(allow_all=True);self.files.changed.connect(self.refresh_count);layout.addWidget(self.files,1)
        options=QFrame();options.setObjectName('options');row=QHBoxLayout(options);row.setContentsMargins(18,14,18,14);row.setSpacing(12)
        row.addWidget(QLabel('출력 형식'))
        self.fmt=QComboBox();self.fmt.setItemDelegate(OutputFormatDelegate(self.fmt));self.fmt.addItems(['PDF','PNG','JPEG','HWPX','DOCX','PPTX','XLSX','용량 축소']);self.fmt.setFixedWidth(150);self.fmt.setToolTip('XLSX 출력은 매크로를 저장하지 않습니다. 원본 파일은 보존됩니다.');row.addWidget(self.fmt);self.compression_profile=QComboBox();add_profiles(self.compression_profile);self.compression_profile.setMinimumWidth(140);self.compression_profile.setMaximumWidth(260);self.compression_profile.setCurrentIndex(self.compression_profile.findData(read_options(self.settings)['profile']));self.compression_profile.hide();row.addWidget(self.compression_profile);row.addStretch()
        self.individual=QPushButton('각각 저장');self.individual.setObjectName('separate');self.individual.setCheckable(True);self.individual.setChecked(True)
        self.merge=QPushButton('하나로 합치기');self.merge.setObjectName('merge');self.merge.setCheckable(True)
        self.save_mode=QButtonGroup(self);self.save_mode.setExclusive(True);self.save_mode.addButton(self.individual);self.save_mode.addButton(self.merge)
        segment=QHBoxLayout();segment.setSpacing(0);segment.addWidget(self.individual);segment.addWidget(self.merge);row.addLayout(segment)
        self.fmt.currentTextChanged.connect(self.output_changed);layout.addWidget(options)
        footer=QFrame();footer.setObjectName('footer');row=QHBoxLayout(footer);row.setContentsMargins(18,12,18,14);row.setSpacing(12)
        folder=QLabel();folder.setPixmap(icon('folder').pixmap(20,20));row.addWidget(folder)
        self.output_folders=[];self.notification_folders=[]
        self.status=QLabel('원본 폴더에 새 파일로 저장');self.status.setObjectName('status');self.status.setWordWrap(True);self.status.linkActivated.connect(self.status_link);row.addWidget(self.status,1)
        self.run=QPushButton('변환 시작  →');self.run.setObjectName('convert');self.run.setMinimumWidth(184);self.run.clicked.connect(self.start);row.addWidget(self.run);layout.addWidget(footer)
        self.files.setColumnCount(6);self.files.headerItem().setText(4,'변경될 이름');self.files.headerItem().setText(5,'상태');self.files.setColumnWidth(4,250);self.files.setColumnWidth(5,210)
        from rename_ui import RenamePanel
        self.rename_panel=RenamePanel(self);layout.insertWidget(layout.count()-2,self.rename_panel)
        self.files.header().moveSection(self.files.header().visualIndex(6),self.files.header().visualIndex(4))
        def change_mode(index):
            self.setMinimumWidth(1100 if index==1 else 760)
            self.rename_panel.setVisible(index==1);options.setVisible(index==0);footer.setVisible(index==0)
            for column in [4,5,6]:self.files.setColumnHidden(column,index==0)
            for column in [1,3]:self.files.setColumnHidden(column,index==1)
            self.rename_panel.refresh()
        self.mode_tabs.currentChanged.connect(change_mode);change_mode(0)
        app_icon=icon('app');self.setWindowIcon(app_icon)
        self.tray=QSystemTrayIcon(icon('tray'),self); menu=QMenu()
        menu.addAction('열기',lambda:self.open_main('tray')); menu.addAction('설정',self.open_settings); menu.addAction('사용 설명',self.open_help); self.tray.setContextMenu(menu)
        self.last_result=None
        self.tray_result_action=menu.addAction('최근 결과 보기',self.show_last_result);self.tray_result_action.setEnabled(False)
        self.tray_stop_action=menu.addAction('작업 중지',self.request_stop);self.tray_stop_action.setEnabled(False);menu.addSeparator();menu.addAction('완전 종료',self.quit)
        self.tray.setToolTip('바꾸리 개발용 · 대기 중')
        self.tray.messageClicked.connect(self.show_last_result)
        self.tray.activated.connect(lambda reason:self.open_main('tray') if reason==QSystemTrayIcon.Trigger else None); self.tray.show()
        from updater import UpdateController
        self.updater=UpdateController(self,self.settings,disabled=DEVELOPMENT)
        self.popup=QuickPopup(); self.bus.clicked.connect(self.popup.clicked_at); self.bus.dismiss.connect(self.popup.hide);self.bus.popup_key.connect(self.popup.native_key); self.popup.chosen.connect(self.quick_selected); self.quick_paths=[]
        self.bus.progress.connect(self.update_progress)
        self.files.paste_requested.connect(self.paste_files);QApplication.instance().installEventFilter(self)
        self.bus.message.connect(self.status.setText); self.bus.error.connect(self.failed); self.bus.done.connect(self.finished); self.bus.selected.connect(self.receive)
        if sys.platform=='win32' and not DEVELOPMENT and os.environ.get('BAKURI_DISABLE_SHELL_INTEGRATION')!='1':
            from windows import SelectionWatcher,MouseWatcher,migrate_menu,initialize_startup
            try:
                initialize_startup(self.settings,first_run=first_run)
                if migrate_menu(self.settings.value('explorer',True,type=bool)):
                    self.settings.setValue('explorer',True);self.settings.sync()
            except Exception as exc:self.status.setText(friendly_error(exc,'menu'))
            self.watcher=SelectionWatcher(self.bus.selected.emit,self.bus.message.emit,self.settings,self.bus.dismiss.emit,self.bus.popup_key.emit)
            self.popup.visibility.connect(self.popup_visibility);self.watcher.start()
            self.mouse_watcher=MouseWatcher(self.bus.clicked.emit); self.mouse_watcher.start()
    def eventFilter(self,obj,event):
        if event.type()==QEvent.KeyPress and event.matches(QKeySequence.Paste) and isinstance(obj,QWidget) and (obj is self or self.isAncestorOf(obj)):
            focus=QApplication.focusWidget() or obj
            if QApplication.activeModalWidget() or isinstance(focus,(QLineEdit,QTextEdit,QPlainTextEdit,QAbstractSpinBox)):return super().eventFilter(obj,event)
            mime=QApplication.clipboard().mimeData()
            if mime and mime.hasUrls():
                self.paste_files();event.accept();return True
        return super().eventFilter(obj,event)
    def paste_files(self):
        if self.busy or self.updater.installing:return
        mime=QApplication.clipboard().mimeData()
        paths=[u.toLocalFile() for u in mime.urls() if u.isLocalFile()] if mime else []
        before=self.files.count();self.files.add_paths(paths);added=self.files.count()-before
        if added:self.status.setText(f'{added}개 파일을 목록에 추가했습니다.')
    def show_completion(self,summary,folders,rows=None,warning=False):
        folders=list(dict.fromkeys(folders));self.notification_folders=folders[:]
        self.last_result=dict(summary=summary,folders=folders,rows=list(rows or []));self.tray_result_action.setEnabled(True)
        self.tray.setToolTip(('바꾸리 · '+summary)[:127])
        if self.settings.value('notify',True,type=bool):self.tray.showMessage('바꾸리 작업 결과',summary+'\n클릭하면 결과를 확인합니다.',QSystemTrayIcon.Warning if warning else QSystemTrayIcon.Information)
    def show_last_result(self):
        if not self.last_result:return
        result=self.last_result;dialog=QDialog(self);dialog.setWindowTitle('최근 작업 결과');dialog.setMinimumWidth(440);layout=QVBoxLayout(dialog)
        label=QLabel(result['summary']);label.setTextFormat(Qt.PlainText);label.setWordWrap(True);layout.addWidget(label)
        buttons=QHBoxLayout();folder=QPushButton('저장 폴더 열기');folder.setEnabled(bool(result['folders']));folder.clicked.connect(lambda:self.open_folders(result['folders']));buttons.addWidget(folder)
        if result['rows']:
            details=QPushButton('파일별 상세 결과');details.clicked.connect(lambda:CompressionResults(result['rows'],dialog).exec());buttons.addWidget(details)
        close=QPushButton('닫기');close.clicked.connect(dialog.accept);buttons.addWidget(close);layout.addLayout(buttons);dialog.exec()
    def popup_visibility(self,visible):
        self.watcher.popup_windows=(self.popup.origin,int(self.popup.winId()))
        self.watcher.popup_open=visible
    def refresh_count(self):
        self.count_label.setText(f'{len(self.files.checked_paths())} / {self.files.count()}개 선택');self.refresh_formats()
    def refresh_formats(self):
        paths=self.files.checked_paths()
        model=self.fmt.model()
        for index in range(self.fmt.count()):
            name=self.fmt.itemText(index)
            allowed=not paths or all(Path(p).suffix.lower() in IMAGES|{'.pdf'} for p in paths) if name=='용량 축소' else not paths or all(can_convert(p,name) for p in paths)
            item=model.item(index);item.setEnabled(allowed)
            item.setForeground(QBrush(QColor('#26354A' if allowed else '#A4AFBD')))
            item.setToolTip('' if allowed else '선택한 파일 중 이 형식으로 변환할 수 없는 파일이 있습니다.')
        current=self.fmt.currentIndex()
        if current<0 or not model.item(current).isEnabled():
            self.fmt.setCurrentIndex(next((i for i in range(self.fmt.count()) if model.item(i).isEnabled()),-1))
        self.output_changed(self.fmt.currentText())
    def output_changed(self,format):
        paths=self.files.checked_paths()
        allowed=can_merge(paths,format)
        self.merge.setEnabled(allowed and not self.busy)
        self.compression_profile.setVisible(format=='용량 축소')
        if not self.busy:self.run.setText('용량 축소 시작' if format=='용량 축소' else '변환 시작  →')
        if not allowed:self.individual.setChecked(True)
    def open_main(self,reason='expanded'):
        if self.isMinimized():self.showNormal()
        else:self.show()
        self.raise_();self.activateWindow()
        if hasattr(self,'updater'):self.updater.request(reason)
    def open_help(self):
        HelpDialog(self).exec()
    def open_settings(self):
        if self.busy:return
        SettingsDialog(self).exec();self.compression_profile.setCurrentIndex(self.compression_profile.findData(read_options(self.settings)['profile']))
    def receive(self,selection):
        if self.busy or (hasattr(self,'updater') and self.updater.installing): return
        paths,origin,tab=selection
        if sys.platform=='win32':
            import win32gui
            if win32gui.GetForegroundWindow()!=origin: return
        self.quick_paths=[str(p) for p in paths if Path(p).is_file() and Path(p).suffix.lower() in SUPPORTED]
        if not self.quick_paths:
            self.status.setText('지원하는 파일을 선택해 주세요.'); return
        self.popup.present(self.quick_paths,origin,tab)
    def quick_selected(self,key):
        if hasattr(self,'updater') and self.updater.installing:return
        if key=='more':
            if not self.busy:self.files.add_paths(self.quick_paths)
            self.open_main('expanded');return
        if self.busy:return
        if key=='hwp_merge':
            self.start_conversion(self.quick_paths,'hwpx',True,self.popup.geometry().center())
        elif key=='pdf_merge':
            if len(self.quick_paths)<2:
                QMessageBox.information(self,'PDF 합치기','PDF 파일을 두 개 이상 선택해 주세요.');return
            self.start_conversion(self.quick_paths,'pdf',True,self.popup.geometry().center())
        elif key=='compress':self.start_compression(self.quick_paths,self.popup.geometry().center())
        else:
            merge=len(self.quick_paths)>1 and key in {'pdf','hwpx'} and all(Path(p).suffix.lower() in IMAGES|{'.pdf'} for p in self.quick_paths)
            self.start_conversion(self.quick_paths,key,merge,self.popup.geometry().center())

    def choose(self):
        if self.busy:return
        self.files.add_paths(QFileDialog.getOpenFileNames(self,'파일 선택','','모든 파일 (*);;지원 변환 파일 ('+' '.join('*'+ext for ext in sorted(SUPPORTED))+')')[0])
    def remove(self):
        for i in range(self.files.count()-1,-1,-1):
            if self.files.item(i).checkState(0)==Qt.Checked: self.files.takeItem(i)
    def start(self):
        if self.busy:self.request_stop();return
        paths=self.files.checked_paths()
        if not paths:
            QMessageBox.information(self,'파일 선택','변환할 파일의 체크박스를 선택해 주세요.'); return
        if self.fmt.currentText()=='용량 축소':
            self.settings.setValue('compress_profile',self.compression_profile.currentData());self.start_compression(paths);return
        if self.fmt.currentIndex()<0 or not self.fmt.model().item(self.fmt.currentIndex()).isEnabled():return
        fmt=self.fmt.currentText().lower(); merge=self.merge.isChecked() and self.merge.isEnabled()
        self.start_conversion(paths,fmt,merge)
    def start_conversion(self,paths,fmt,merge,anchor=None):
        if self.busy:return
        if any(not can_convert(p,fmt) for p in paths):
            QMessageBox.information(self,'출력 형식 확인','선택한 파일에는 이 출력 형식을 사용할 수 없습니다. 파일의 체크 표시를 확인하고, 선택 가능한 다른 형식을 골라 주세요. 자세한 내용은 ? 버튼의 사용 설명에서 확인할 수 있습니다.');return
        dpi=self.settings.value('dpi',150,type=int);image_mode=self.settings.value('image_mode','background')
        self.begin_job(lambda control:convert(paths,fmt,merge,dpi=dpi,image_mode=image_mode,control=control),'convert',anchor)
    def start_compression(self,paths,anchor=None):
        if self.busy:return
        if any(Path(path).suffix.lower() not in IMAGES|{'.pdf'} for path in paths):
            QMessageBox.information(self,'파일 확인','용량 축소는 이미지와 PDF만 지원합니다.');return
        options=read_options(self.settings);self.compression_profile.setCurrentIndex(self.compression_profile.findData(options['profile']))
        self.begin_job(lambda control:compress(paths,control=control,**options),'compress',anchor)
    def begin_job(self,operation,kind,anchor=None):
        if self.busy or self.updater.installing:return
        self.mode_tabs.setEnabled(False);self.rename_panel.setEnabled(False);self.popup.hide();self.busy=True;self.job_kind=kind;self.control=JobControl(self.bus.progress.emit);control=self.control
        self.compression_rows=[];self.output_folders=[];self.notification_folders=[]
        self.run.setText('작업 중지');self.run.setEnabled(True);self.files.setEnabled(False);self.toolbar.setEnabled(False);self.fmt.setEnabled(False);self.compression_profile.setEnabled(False);self.individual.setEnabled(False);self.merge.setEnabled(False)
        self.status.setText('0% · 작업 준비')
        self.tray_stop_action.setEnabled(True);self.tray.setToolTip('바꾸리 · '+('용량 축소' if kind=='compress' else '파일 변환')+' 중 · 0%')
        def work():
            outcome='done';error=''
            try:operation(control)
            except Cancelled:outcome='cancelled'
            except Exception as exc:outcome='failed';error=friendly_error(exc,'compression' if kind=='compress' else 'conversion')
            self.bus.done.emit(dict(paths=list(control.outputs),rows=list(control.rows),outcome=outcome,error=error,kind=kind))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
    def update_progress(self,percent,text):
        if not self.busy:return
        if self.control and self.control.cancelled.is_set():return
        self.status.setText(f'{percent}% · {text}');label='용량 축소' if self.job_kind=='compress' else '파일 변환'
        self.tray.setToolTip(f'바꾸리 · {label} 중 · {percent}%\n{text}'[:127])
    def request_stop(self):
        if not self.busy or self.control is None:return
        self.control.cancel();self.run.setText('중지 요청 중');self.run.setEnabled(False);self.tray_stop_action.setEnabled(False);self.tray.setToolTip('바꾸리 · 중지 요청 중');self.status.setText('중지 요청 중 · 현재 처리 단계가 반환되면 중지합니다.')
    def reset(self):
        self.mode_tabs.setEnabled(True);self.rename_panel.setEnabled(True);self.busy=False;self.control=None;self.run.setEnabled(True);self.files.setEnabled(True);self.toolbar.setEnabled(True);self.fmt.setEnabled(True);self.compression_profile.setEnabled(True);self.individual.setEnabled(True);self.output_changed(self.fmt.currentText());self.tray_stop_action.setEnabled(False)
    def failed(self,text):
        self.reset();self.status.setText('변환을 완료하지 못했습니다.');self.show();QMessageBox.warning(self,'변환을 완료하지 못했어요',friendly_error(text)+'\n\n원본과 이미 저장된 결과는 그대로 남아 있습니다.')
    def finished(self,result):
        if isinstance(result,list):result=dict(paths=result,rows=[],outcome='done',error='',kind='convert')
        paths=result['paths'];outcome=result['outcome'];self.reset();self.compression_rows=result.get('rows',[])
        self.output_folders=list(dict.fromkeys(str(Path(p).parent) for p in paths));self.notification_folders=self.output_folders[:]
        saved=f'{len(paths)}개 저장 완료'
        summary='작업 중지 · '+saved if outcome=='cancelled' else '작업 실패 · '+saved if outcome=='failed' else saved
        if result.get('kind')=='compress':
            skipped=sum(row['status'] in ('건너뜀','축소 효과 없음') for row in self.compression_rows);failed=sum(row['status']=='실패' for row in self.compression_rows)
            summary+=f' · 건너뜀 {skipped}개 · 실패 {failed}개'
            from tray_results import compression_savings
            savings=compression_savings(self.compression_rows)
            if savings:summary+='\n'+savings
        links=[]
        if paths:links.append('<a style="color:#2E83F2;text-decoration:none" href="open">저장 폴더 열기</a>')
        if self.compression_rows:links.append('<a style="color:#2E83F2;text-decoration:none" href="details">상세 결과</a>')
        self.status.setText(summary+(' · '+' · '.join(links) if links else ''))
        if outcome=='failed':summary+='\n'+friendly_error(result.get('error',''))+'\n원본과 이미 저장된 결과는 그대로 남아 있습니다.'
        self.show_completion(summary,self.output_folders,self.compression_rows,warning=outcome=='failed' or any(r.get('status')=='실패' for r in self.compression_rows))
    def status_link(self,link):
        if link=='details':CompressionResults(self.compression_rows,self).exec()
        else:self.open_folders(self.output_folders)
    def open_folders(self,folders):
        if not folders: return
        def show(folder):
            if not Path(folder).is_dir(): QMessageBox.warning(self,'폴더 열기','저장 폴더가 이동되거나 삭제되었습니다.'); return
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        if len(folders)==1: show(folders[0]); return
        menu=QMenu(self)
        for folder in folders: menu.addAction(folder,lambda folder=folder:show(folder))
        menu.exec(QCursor.pos())
    def quit(self):
        if self.busy: QMessageBox.information(self,'변환 중','변환이 끝난 뒤 종료해 주세요.'); return
        QApplication.quit()
    def closeEvent(self,e):
        if self.tray.isSystemTrayAvailable(): self.files.clear();self.hide();e.ignore()
        elif self.busy: e.ignore()
        else:self.files.clear();e.accept()

if __name__=='__main__':
    app=QApplication(sys.argv);app.setApplicationName('BakuriDevelopment'); app.setQuitOnLastWindowClosed(False)
    if sys.platform=='win32' and not DEVELOPMENT:
        from windows import apply_install_options
        apply_install_options(sys.argv)
    from PySide6.QtNetwork import QLocalSocket, QLocalServer
    socket=QLocalSocket(); socket.connectToServer(SERVER_NAME)
    paths=sys.argv[sys.argv.index('--add-files')+1:] if '--add-files' in sys.argv else []
    if socket.waitForConnected(300):
        socket.write(json.dumps({'paths':paths,'direct':'--background' not in sys.argv and '--add-files' not in sys.argv}).encode()+b'\n'); socket.waitForBytesWritten(1000); socket.disconnectFromServer(); sys.exit(0)
    QLocalServer.removeServer(SERVER_NAME); server=QLocalServer()
    if not server.listen(SERVER_NAME): raise RuntimeError('다른 바꾸리가 실행 중입니다.')
    win=Window(); clients=[]
    def accept():
        while server.hasPendingConnections():
            client=server.nextPendingConnection(); clients.append(client); client.buffer=b''
            def read(client=client):
                client.buffer+=bytes(client.readAll())
                if b'\n' in client.buffer:
                    try:
                        payload=json.loads(client.buffer.split(b'\n',1)[0]);direct=isinstance(payload,dict) and payload.get('direct',False)
                        received=payload.get('paths',[]) if isinstance(payload,dict) else payload
                        if received:win.files.add_paths(received)
                        if direct:win.open_main('direct')
                        elif received:win.show();win.raise_();win.activateWindow()
                    except (ValueError,TypeError): pass
                    client.disconnectFromServer()
            def release(client=client):
                if client in clients:clients.remove(client)
                client.deleteLater()
            client.disconnected.connect(release)
            client.readyRead.connect(read); read()
    server.newConnection.connect(accept)
    if paths: win.files.add_paths(paths)
    if '--background' not in sys.argv:
        win.show()
        if '--add-files' not in sys.argv:QTimer.singleShot(0,lambda:win.updater.request('direct'))
    sys.exit(app.exec())
