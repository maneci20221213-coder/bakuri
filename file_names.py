"""Three-line file names, with the same wrapping for painting and row height."""
from functools import lru_cache
from PySide6.QtCore import Qt,QRect,QSize
from PySide6.QtGui import QFont,QFontMetrics,QTextLayout,QTextOption,QPalette
from PySide6.QtWidgets import QStyledItemDelegate,QStyleOptionViewItem,QStyle

@lru_cache(maxsize=4096)
def name_lines(text,font_description,width):
    font=QFont();font.fromString(font_description);width=max(1,width)
    layout=QTextLayout(text,font);option=QTextOption();option.setWrapMode(QTextOption.WrapAnywhere);layout.setTextOption(option)
    raw=text.encode('utf-16-le');lines=[];layout.beginLayout()
    for index in range(3):
        line=layout.createLine()
        if not line.isValid():break
        line.setLineWidth(width);start=line.textStart()*2;end=start+line.textLength()*2
        value=raw[start:end].decode('utf-16-le')
        if index==2 and end<len(raw):value=QFontMetrics(font).elidedText(raw[start:].decode('utf-16-le'),Qt.ElideMiddle,width)
        lines.append(value)
    layout.endLayout();return tuple(lines) or ('',)

class FileNameDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        if index.column() not in {2,4}:return super().paint(painter,option,index)
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);style=opt.widget.style()
        rect=style.subElementRect(QStyle.SE_ItemViewItemText,opt,opt.widget).adjusted(2,0,-2,0)
        lines=name_lines(opt.text,opt.font.toString(),rect.width());opt.text='';style.drawControl(QStyle.CE_ItemViewItem,opt,painter,opt.widget)
        height=opt.fontMetrics.height();y=rect.top()+max(0,(rect.height()-height*len(lines))//2)
        painter.save();painter.setClipRect(rect);painter.setFont(opt.font)
        painter.setPen(opt.palette.color(QPalette.Text))
        for line in lines:painter.drawText(QRect(rect.left(),y,rect.width(),height),Qt.AlignLeft|Qt.AlignVCenter,line);y+=height
        painter.restore()
    def sizeHint(self,option,index):
        if index.column() not in {2,4}:return super().sizeHint(option,index)
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index)
        width=max(1,self.parent().columnWidth(index.column())-24)
        return QSize(width,max(48 if self.parent().property("compactRows") else 60,len(name_lines(opt.text,opt.font.toString(),width))*opt.fontMetrics.height()+16))
