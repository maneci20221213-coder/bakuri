"""A light design: exact sRGB accent #2E83F2, shared by window and popup."""
from pathlib import Path
from functools import lru_cache
from PySide6.QtGui import QIcon
ACCENT='#2E83F2'
ASSETS=Path(__file__).resolve().parent/'assets'
@lru_cache(maxsize=32)
def icon(name):
    if name=='app':return QIcon(str(ASSETS/'app.ico'))
    if name=='tray':return QIcon(str(ASSETS/'tray.png'))
    return QIcon(str(ASSETS/(name+'.svg')))

def stylesheet():
    check=(ASSETS/'check.svg').as_posix();minus=(ASSETS/'minus.svg').as_posix();arrow=(ASSETS/'chevron.svg').as_posix()
    return f'''
    QWidget {{ font-family: "Malgun Gothic", "Noto Sans CJK KR", sans-serif; font-size: 13px; color:#26354A; }}
    QWidget#mainWindow {{ background:#F6F8FC; }}
    QFrame#toolbar, QFrame#options, QFrame#footer {{ background:#FFFFFF; border:0; }}
    QFrame#toolbar {{ border-bottom:1px solid #E2E8F0; }}
    QFrame#options {{ border-top:1px solid #E2E8F0; border-bottom:1px solid #E2E8F0; }}
    QPushButton {{ background:#FFFFFF; border:1px solid #DCE3EE; border-radius:7px; padding:9px 15px; min-height:20px; color:#334155; }}
    QPushButton:hover {{ background:#F1F6FE; border-color:#AECDF6; }}
    QPushButton:pressed {{ background:#E3EFFF; }}
    QPushButton:focus {{ border:2px solid {ACCENT}; padding:8px 14px; }}
    QPushButton:disabled {{ background:#F2F5F9; color:#A4AFBD; border-color:#E5EAF1; }}
    QPushButton#addFiles {{ color:{ACCENT}; border-color:{ACCENT}; font-weight:600; }}
    QPushButton#convert {{ background:{ACCENT}; border-color:{ACCENT}; color:white; font-weight:600; padding:11px 24px; }}
    QPushButton#convert:hover {{ background:#2475DF; border-color:#2475DF; }}
    QPushButton#convert:pressed {{ background:#1F68CA; }}
    QPushButton#convert:disabled {{ background:#ABCDF8; border-color:#ABCDF8; color:#F8FBFF; }}
    QPushButton#settings, QPushButton#help {{ min-width:20px; padding:9px; }}
    QPushButton#help {{ font-weight:700; font-size:18px; color:{ACCENT}; }}
    QPushButton#separate, QPushButton#merge {{ background:#FFFFFF; border:1px solid #DCE3EE; padding:9px 15px; border-radius:0; min-width:92px; }}
    QPushButton#separate {{ border-top-left-radius:7px; border-bottom-left-radius:7px; }}
    QPushButton#merge {{ border-top-right-radius:7px; border-bottom-right-radius:7px; }}
    QPushButton#separate:checked, QPushButton#merge:checked {{ background:{ACCENT}; color:white; border-color:{ACCENT}; }}
    QPushButton#merge:disabled {{ color:#A4AFBD; background:#F5F7FB; }}
    QComboBox {{ background:white; border:1px solid #DCE3EE; border-radius:7px; padding:9px 14px; min-height:20px; min-width:110px; }}
    QComboBox:focus {{ border:1px solid {ACCENT}; }}
    QComboBox::drop-down {{ border:0; width:30px; }}
    QComboBox::down-arrow {{ image:url("{arrow}"); width:12px; height:12px; }}
    QComboBox QAbstractItemView {{ background:white; selection-background-color:#E9F2FF; selection-color:#1E4C83; border:1px solid #DCE3EE; padding:4px; }}
    QComboBox QAbstractItemView::item:disabled {{ color:#A4AFBD; background:#F2F5F9; }}
    QTreeWidget {{ background:#FFFFFF; border:0; outline:0; show-decoration-selected:1; }}
    QTreeWidget::item {{ border-bottom:1px solid #EDF1F6; padding:6px 8px; color:#26354A; }}
    QTreeWidget::item:hover {{ background:#F6F9FF; }}
    QTreeWidget::item:selected {{ background:#EAF3FF; color:#193C68; }}
    QTreeWidget::indicator, QCheckBox::indicator {{ width:18px; height:18px; border:1px solid #A7B4C5; border-radius:4px; background:white; }}
    QTreeWidget::indicator:checked, QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; image:url("{check}"); }}
    QCheckBox::indicator:indeterminate {{ background:{ACCENT}; border-color:{ACCENT}; image:url("{minus}"); }}
    QHeaderView {{ background:#F7F9FC; }}
    QHeaderView::section {{ background:#F7F9FC; color:#65758D; padding:12px 8px; border:0; border-right:1px solid #EDF1F6; border-bottom:1px solid #E2E8F0; font-size:12px; }}
    QLabel#selectionCaption, QLabel#selectionCount {{ color:#65758D; font-size:12px; background:transparent; }}
    QLabel#status {{ color:#718096; font-size:12px; background:transparent; }}
    QScrollBar:vertical {{ background:#F7F9FC; width:10px; margin:0; }}
    QScrollBar::handle:vertical {{ background:#CED7E4; min-height:30px; border-radius:5px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QMenu {{ background:white; border:1px solid #DCE3EE; padding:5px; }}
    QMenu::item {{ padding:8px 20px; border-radius:4px; }}
    QMenu::item:selected {{ background:#EAF3FF; }}
    QDialog {{ background:#F8FAFD; }}
    QCheckBox {{ spacing:9px; }}
    '''
