"""Create a genuine Hancom table, including a single-cell table for one image.
API references: Hancom HwpAutomation_2504.pdf / ParameterSetTable_2504.pdf.
"""

def unit(mm): return round(mm*7200/25.4)

def table_dimensions(entries):
    # All rows share one column width. Choose it so every row fits on A4,
    # retaining image aspect ratios even for portrait scans. No pixel resizing.
    width=min([170.0]+[245.0*w/h for _,w,h in entries])
    return unit(width),[unit(width*h/w) for _,w,h in entries]

def action(app,name):
    act=app.CreateAction(name); params=act.CreateSet(); act.GetDefault(params)
    return act,params

def execute(act,params,message):
    if act.Execute(params) is False: raise RuntimeError(message)

def create_document(app,entries,dest,mode='background',progress=lambda text:None,checkpoint=lambda:None,advance=lambda fraction:None):
    if not entries: raise ValueError('문서에 넣을 이미지가 없습니다.')
    if mode not in {'background','inline'}: raise ValueError('잘못된 한글 이미지 배치 설정입니다.')
    if len(entries)>65535: raise ValueError('표의 최대 행 수를 초과했습니다.')
    try:
        checkpoint();app.Clear(1)
        act,params=action(app,'PageSetup'); page=params.CreateItemSet('PageDef','PageDef')
        for key,mm in {'PaperWidth':210,'PaperHeight':297,'LeftMargin':20,'RightMargin':20,'TopMargin':20,'BottomMargin':20,'HeaderLen':0,'FooterLen':0,'GutterLen':0}.items():page.SetItem(key,unit(mm))
        page.SetItem('Landscape',0);params.SetItem('ApplyTo',2)
        execute(act,params,'A4 용지 설정에 실패했습니다.')
        width,heights=table_dimensions(entries)
        act,params=action(app,'TableCreate')
        params.SetItem('Rows',len(entries));params.SetItem('Cols',1)
        params.SetItem('WidthType',2);params.SetItem('HeightType',1)
        params.CreateItemArray('ColWidth',1).SetItem(0,width)
        rows=params.CreateItemArray('RowHeight',len(entries))
        for index,height in enumerate(heights): rows.SetItem(index,height)
        props=params.CreateItemSet('TableProperties','Table')
        for key,value in {'TreatAsChar':0,'PageBreak':1,'RepeatHeader':0,'CellSpacing':0,'CellMarginLeft':0,'CellMarginRight':0,'CellMarginTop':0,'CellMarginBottom':0,'HorzRelTo':2,'HorzAlign':1,'VertRelTo':2,'VertAlign':0,'FlowWithText':1,'TextWrap':1,'WidthRelTo':4,'Width':width,'HeightRelTo':2,'Height':sum(heights),'HoldAnchorObj':0,'OutsideMarginLeft':0,'OutsideMarginRight':0,'OutsideMarginTop':0,'OutsideMarginBottom':0}.items():props.SetItem(key,value)
        execute(act,params,'이미지 표 생성에 실패했습니다.')
        for index,(path,_,_) in enumerate(entries):
            checkpoint();progress(f'한글 표 채우기 · {index+1}/{len(entries)}')
            if mode=='background':
                if app.HAction.Run('TableCellBlock') is False:raise RuntimeError('표 셀을 선택하지 못했습니다.')
                # SelectedCell requires a cell block, embedded=True and fill=5.
                result=app.InsertBackgroundPicture('SelectedCell',str(path),True,5,False,0,0,0)
                if result is False or result==0:raise RuntimeError('셀 배경 이미지 삽입에 실패했습니다.')
                app.HAction.Run('Cancel')
            else:
                picture=app.InsertPicture(str(path),True,3,False,False,0,0,0)
                if picture is None or picture is False:raise RuntimeError('셀 안에 이미지 삽입을 실패했습니다.')
                # Keep the image inside the cell's text flow, not floating.
                properties=picture.Properties;properties.SetItem('TreatAsChar',1);picture.Properties=properties
                app.HAction.Run('Cancel')
            if index+1<len(entries) and app.HAction.Run('TableRightCell') is False:raise RuntimeError('다음 표 셀로 이동하지 못했습니다.')
            advance(.9*(index+1)/len(entries))
        checkpoint();advance(.95)
        if not app.SaveAs(str(dest),'HWPX','') or not dest.exists():raise RuntimeError('한글 이미지 문서를 저장하지 못했습니다.')
        checkpoint();verify_document(dest,len(entries),mode);checkpoint();advance(1)
    finally:
        app.Clear(1)

def verify_document(path,count,mode):
    """Reject a silent automation failure before publishing an incomplete result."""
    import zipfile,xml.etree.ElementTree as ET
    hp='{http://www.hancom.co.kr/hwpml/2011/paragraph}'
    hc='{http://www.hancom.co.kr/hwpml/2011/core}'
    hh='{http://www.hancom.co.kr/hwpml/2011/head}'
    try:
        with zipfile.ZipFile(path) as archive:
            sections=[ET.fromstring(archive.read(name)) for name in archive.namelist() if name.startswith('Contents/section') and name.endswith('.xml')]
            tables=[table for section in sections for table in section.iter(hp+'tbl')]
            if len(tables)!=1 or int(tables[0].get('rowCnt','0'))!=count or tables[0].get('colCnt')!='1':raise ValueError('이미지 개수와 표의 행/열 개수가 다릅니다.')
            cells=list(tables[0].iter(hp+'tc'))
            if len(cells)!=count:raise ValueError('이미지를 넣을 셀 개수가 맞지 않습니다.')
            if mode=='inline':
                if any(not list(cell.iter(hp+'pic')) for cell in cells):raise ValueError('그림이 없는 셀이 있습니다.')
            else:
                header=ET.fromstring(archive.read('Contents/header.xml'))
                fills={fill.get('id') for fill in header.iter(hh+'borderFill') if list(fill.iter(hc+'img'))}
                if any(cell.get('borderFillIDRef') not in fills for cell in cells):raise ValueError('배경 그림이 없는 셀이 있습니다.')
            if not any(name.startswith('BinData/') for name in archive.namelist()):raise ValueError('이미지가 문서 안에 포함되지 않았습니다.')
    except (ValueError,KeyError,zipfile.BadZipFile,ET.ParseError) as exc:
        raise RuntimeError('한글 표/이미지 저장 검증 실패: '+str(exc)) from exc

def compact_document(path,checkpoint=lambda:None):
    """Losslessly deflate HWPX entries; keep all names, XML and image bytes intact."""
    import zipfile
    from pathlib import Path
    temp=Path(str(path)+'.compact')
    try:
        with zipfile.ZipFile(path) as source,zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as target:
            target.comment=source.comment
            for entry in source.infolist():
                checkpoint()
                target.writestr(entry,source.read(entry),compress_type=zipfile.ZIP_STORED if entry.filename=='mimetype' else zipfile.ZIP_DEFLATED,compresslevel=9)
        checkpoint()
        if temp.stat().st_size<path.stat().st_size:temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
