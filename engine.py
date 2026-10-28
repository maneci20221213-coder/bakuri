from pathlib import Path
import tempfile, shutil, csv, codecs, io
from PIL import Image, ImageOps
from image_inputs import IMAGES, frames, white_rgb, stage_images
import fitz
from jobs import JobControl

SPREADSHEETS={'.xls','.xlsx','.xlsm','.xlsb','.xlt','.xltx','.xltm','.csv','.tsv','.ods','.dif','.slk'}
WORDS={'.doc','.docx'}
PRESENTATIONS={'.ppt','.pptx'}
SUPPORTED=IMAGES|{'.pdf','.hwp','.hwpx','.odt'}|SPREADSHEETS|WORDS|PRESENTATIONS
def can_convert(path,fmt):
    fmt='jpeg' if fmt.lower()=='jpg' else fmt.lower()
    ext=Path(path).suffix.lower()
    return ext in SUPPORTED and (fmt in {'pdf','png','jpeg'} or fmt=='hwpx' and ext in (IMAGES|{'.odt','.hwp','.pdf'}|WORDS) or fmt=='xlsx' and ext in SPREADSHEETS or fmt=='docx' and ext in {'.hwp','.hwpx'} or fmt=='pptx' and ext in (IMAGES|{'.pdf'}))
def text_import_options(src):
    with src.open('rb') as handle: sample=handle.read(65536)
    if sample.startswith((b'\xff\xfe',b'\xfe\xff')): encoding='utf-16'; origin=1200
    else:
        try: codecs.getincrementaldecoder('utf-8-sig')().decode(sample,final=False);encoding='utf-8-sig';origin=65001
        except UnicodeDecodeError: encoding='cp949';origin=949
    text=sample.decode(encoding,errors='replace')
    if src.suffix.lower()=='.tsv':delimiter='\t'
    else:
        try: delimiter=csv.Sniffer().sniff(text,delimiters=',;\t').delimiter
        except csv.Error: delimiter=','
    return dict(Origin=origin,DataType=1,TextQualifier=1,ConsecutiveDelimiter=False,Tab=delimiter=='\t',Semicolon=delimiter==';',Comma=delimiter==',',Space=False,Other=False,Local=True)

def save_new(src, desired):
    desired=Path(desired); n=0
    while True:
        p=desired if not n else desired.with_name(f'{desired.stem}_{n}{desired.suffix}')
        try:
            with p.open('xb') as out, open(src,'rb') as inp: shutil.copyfileobj(inp,out)
            return str(p)
        except FileExistsError: n+=1

class OfficeSession:
    def __init__(self): self.apps={}; self.com=None; self.control=None; self.advance=lambda fraction,text:None
    def __enter__(self): return self
    def check(self):
        if self.control:self.control.check()
    def hwp(self):
        self.check()
        import pythoncom,win32com.client
        if self.com is None: pythoncom.CoInitialize(); self.com=pythoncom
        app=self.apps.get('hwp')
        if app is None:
            app=win32com.client.DispatchEx('HWPFrame.HwpObject');self.apps['hwp']=app
            from windows import register_hancom
            register_hancom(app)
        return app
    def image_document(self,paths,dest,folder,mode,progress):
        from hancom_images import create_document, compact_document
        entries=stage_images(paths,folder,progress,checkpoint=self.check,advance=lambda fraction:self.advance(.35*fraction,'이미지 준비'))
        self.check()
        create_document(self.hwp(),entries,dest,mode,progress,checkpoint=self.check,advance=lambda fraction:self.advance(.35+.6*fraction,'한글 표 채우기'))
        if any(Path(p).suffix.lower()=='.pdf' for p in paths):
            self.check()
            from pdf_pages import paginate
            paginate(dest,entries)
            self.check()
        compact_document(dest,self.check)
    def powerpoint(self):
        self.check()
        import pythoncom, win32com.client
        if self.com is None: pythoncom.CoInitialize(); self.com=pythoncom
        if 'powerpoint' not in self.apps:
            app=win32com.client.DispatchEx('PowerPoint.Application')
            self.apps['powerpoint']=app
            app.AutomationSecurity=3
            app.DisplayAlerts=1
        return self.apps['powerpoint']
    def slides_document(self,paths,dest,folder,dpi=150):
        book=self.powerpoint().Presentations.Add(WithWindow=False)
        try:
            count=0
            for source in paths:
                self.check()
                if source.suffix.lower()=='.pdf':
                    with fitz.open(source) as document:
                        if document.needs_pass: raise ValueError('암호가 있는 PDF는 지원하지 않습니다.')
                        for page in document:
                            self.check()
                            image=folder/f'slide-{count}.png'
                            page.get_pixmap(dpi=dpi,alpha=False).save(str(image))
                            self.add_slide(book,image,page.rect.width,page.rect.height,count)
                            count+=1
                else:
                    for image in frames(source):
                        self.check()
                        path=folder/f'slide-{count}.png';image.save(path,'PNG')
                        self.add_slide(book,path,image.width,image.height,count)
                        count+=1
            self.check()
            if not count: raise ValueError('슬라이드로 만들 페이지가 없습니다.')
            book.SaveAs(str(dest),24)
            self.check()
            if not dest.exists(): raise RuntimeError('PPTX 저장에 실패했습니다.')
        finally: book.Close()
    def add_slide(self,book,image,width,height,index):
        if index==0:
            book.PageSetup.SlideWidth=720
            book.PageSetup.SlideHeight=max(72,min(4032,720*height/width))
        sw=float(book.PageSetup.SlideWidth);sh=float(book.PageSetup.SlideHeight)
        scale=min(sw/width,sh/height);w=width*scale;h=height*scale
        slide=book.Slides.Add(index+1,12)
        slide.Shapes.AddPicture(str(image),False,True,(sw-w)/2,(sh-h)/2,w,h)
        self.check()
    def export(self,src,dest,fmt):
        self.check()
        import pythoncom,win32com.client
        if self.com is None: pythoncom.CoInitialize(); self.com=pythoncom
        if src.suffix.lower() in PRESENTATIONS:
            book=self.powerpoint().Presentations.Open(str(src),ReadOnly=True,Untitled=False,WithWindow=False)
            try:
                self.check();book.SaveAs(str(dest),32);self.check()
                if not dest.exists(): raise RuntimeError('PowerPoint PDF 저장에 실패했습니다.')
            finally: book.Close()
            return
        if src.suffix.lower() in WORDS and fmt.upper()=='PDF':
            app=self.apps.get('word')
            if app is None:
                app=win32com.client.DispatchEx('Word.Application');self.apps['word']=app
                app.Visible=False;app.DisplayAlerts=0;app.AutomationSecurity=3
            book=app.Documents.Open(str(src),ReadOnly=True,AddToRecentFiles=False)
            try:
                self.check();book.ExportAsFixedFormat(str(dest),17);self.check()
                if not dest.exists(): raise RuntimeError('Word PDF 저장에 실패했습니다.')
            finally: book.Close(False)
            return
        excel=src.suffix.lower() in SPREADSHEETS; key='excel' if excel else 'hwp'
        app=self.apps.get(key)
        if app is None:
            app=win32com.client.DispatchEx('Excel.Application' if excel else 'HWPFrame.HwpObject'); self.apps[key]=app
            if excel: app.Visible=False; app.DisplayAlerts=False; app.AutomationSecurity=3
            else:
                from windows import register_hancom
                register_hancom(app)
        book=None
        try:
            if excel:
                if src.suffix.lower() in {'.csv','.tsv'}:
                    app.Workbooks.OpenText(str(src),**text_import_options(src));book=app.ActiveWorkbook
                else: book=app.Workbooks.Open(str(src),UpdateLinks=0,ReadOnly=True,IgnoreReadOnlyRecommended=True)
                self.check()
                if fmt.upper()=='XLSX': book.SaveAs(str(dest),FileFormat=51)
                else: book.ExportAsFixedFormat(0,str(dest),0,True,False)
            else:
                if not app.Open(str(src),'',''): raise RuntimeError('한글 문서 열기에 실패했습니다.')
                self.check()
                if not app.SaveAs(str(dest),'OOXML' if fmt.upper()=='DOCX' else fmt.upper(),''): raise RuntimeError('한글 저장에 실패했습니다.')
            self.check()
            if not dest.exists(): raise RuntimeError('변환 결과가 생성되지 않았습니다.')
        finally:
            if book is not None: book.Close(False)
            if not excel: app.Clear(1)
    def __exit__(self,*args):
        for app in self.apps.values():
            try: app.Quit()
            except Exception: pass
        self.apps.clear()
        if self.com is not None: self.com.CoUninitialize()

def office(src,dest,fmt):
    with OfficeSession() as session: session.export(src,dest,fmt)

def to_pdf(src,dest,session=None,control=None,advance=lambda f:None):
    ext=src.suffix.lower()
    if ext=='.pdf': shutil.copyfile(src,dest)
    elif ext in IMAGES:
        with fitz.open() as document:
            for index,image in enumerate(frames(src)):
                if control:control.check()
                page=document.new_page(width=image.width*72/150,height=image.height*72/150)
                original_jpeg=False
                if ext in {'.jpg','.jpeg'}:
                    with Image.open(src) as original:original_jpeg=original.getexif().get(274,1)==1
                if original_jpeg:page.insert_image(page.rect,filename=str(src))
                else:
                    data=io.BytesIO();image.save(data,'PNG',compress_level=1);page.insert_image(page.rect,stream=data.getvalue())
                advance(.25+.5*(index+1)/(index+2))
            if control:control.check()
            document.save(dest)
    else: (session.export if session else office)(src,dest,'PDF')

def convert(files,fmt,merge=False,progress=lambda s:None,dpi=150,image_mode='background',control=None):
    files=[Path(p).resolve() for p in files];fmt=fmt.lower();fmt='jpeg' if fmt=='jpg' else fmt
    control=control or JobControl();results=[]
    if not files:raise ValueError('파일을 추가해 주세요.')
    if fmt not in {'png','jpeg','pdf','hwpx','xlsx','docx','pptx'}:raise ValueError('지원하지 않는 출력 형식')
    if merge and fmt not in {'pdf','hwpx','pptx'}:raise ValueError('합치기는 PDF·PPTX 또는 이미지의 HWPX 변환만 가능합니다.')
    if merge and fmt=='hwpx' and any(p.suffix.lower() not in IMAGES|{'.pdf'} for p in files):raise ValueError('HWPX로 합치기는 이미지·PDF 파일만 가능합니다.')
    for path in files:
        control.check()
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:raise ValueError(f'지원하지 않는 파일: {path}')
        if not can_convert(path,fmt):raise ValueError('선택한 입력과 출력 형식의 조합을 지원하지 않습니다.')
    def message(text):control.check();progress(text)
    with OfficeSession() as session,tempfile.TemporaryDirectory() as td:
        session.control=control;td=Path(td);pdfs=[]
        if merge and fmt=='pptx':
            temp=td/'merged.pptx';session.slides_document(files,temp,td,dpi);control.check()
            results.append(control.publish(temp,files[0].parent/'합친슬라이드.pptx'))
        elif merge and fmt=='hwpx':
            session.advance=lambda f,t:control.update(f*95,t)
            temp=td/'merged.hwpx';session.image_document(files,temp,td,image_mode,message);control.check()
            results.append(control.publish(temp,files[0].with_suffix('.hwpx') if len(files)==1 else files[0].parent/'합친문서.hwpx'))
        else:
            for index,src in enumerate(files):
                base=index*90/len(files);width=90/len(files)
                def advance(fraction,text=''):
                    control.update(base+width*min(.98,fraction),text or src.name)
                session.advance=advance;advance(0);message(f'{index+1}/{len(files)} · {src.name}')
                temp=td/f'{index}.{fmt}'
                if fmt=='pptx':
                    session.slides_document([src],temp,td,dpi)
                elif fmt=='hwpx' and src.suffix.lower() in IMAGES|{'.pdf'}:
                    session.image_document([src],temp,td,image_mode,message)
                elif fmt in {'hwpx','xlsx','docx'}:
                    advance(.15);session.export(src,temp,fmt.upper());advance(.9)
                elif fmt in {'png','jpeg'} and src.suffix.lower() in IMAGES:
                    with Image.open(src) as image:pages=getattr(image,'n_frames',1) if src.suffix.lower() in {'.tif','.tiff'} else 1
                    for number,image in enumerate(frames(src)):
                        advance(.1+.7*number/pages)
                        if fmt=='jpeg':image=white_rgb(image)
                        image.save(temp,quality=95);control.check()
                        name=f'{src.stem}.{fmt}' if pages==1 else f'{src.stem}_{number+1:03}.{fmt}'
                        results.append(control.publish(temp,src.with_name(name)));advance(.1+.8*(number+1)/pages)
                    continue
                else:
                    pdf=src if src.suffix.lower()=='.pdf' else td/f'{index}.pdf'
                    advance(.05)
                    if pdf!=src:to_pdf(src,pdf,session,control,advance)
                    control.check();advance(.35)
                    if fmt=='pdf':temp=pdf
                    if merge:pdfs.append(pdf);advance(.98);continue
                    if fmt!='pdf':
                        with fitz.open(pdf) as document:
                            if document.needs_pass:raise ValueError('암호가 있는 PDF는 지원하지 않습니다.')
                            for number,page in enumerate(document):
                                advance(.35+.6*number/len(document));message(f'{index+1}/{len(files)} · {src.name} · {number+1}/{len(document)}페이지')
                                pix=page.get_pixmap(dpi=dpi,alpha=False);control.check()
                                if fmt=='jpeg':pix.save(str(temp),jpg_quality=95)
                                else:pix.save(str(temp))
                                name=f'{src.stem}.{fmt}' if len(document)==1 else f'{src.stem}_{number+1:03}.{fmt}'
                                results.append(control.publish(temp,src.with_name(name)));advance(.35+.6*(number+1)/len(document))
                        continue
                advance(.95);results.append(control.publish(temp,src.with_suffix('.'+fmt)))
            if merge:
                merged=td/'merged.pdf'
                with fitz.open() as document:
                    for number,pdf in enumerate(pdfs):
                        control.update(90+7*number/len(pdfs),'PDF 합치기')
                        with fitz.open(pdf) as part:
                            if part.needs_pass:raise ValueError('암호가 있는 PDF는 지원하지 않습니다.')
                            control.check();document.insert_pdf(part);control.check()
                    control.check();document.save(merged);control.check()
                results.append(control.publish(merged,files[0].with_suffix('.pdf') if len(files)==1 else files[0].parent/'합친문서.pdf'))
        control.update(99,'저장 확인')
    control.complete();return results
