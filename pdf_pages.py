"""Split an embedded one-column image table into per-page HWPX sections."""
import copy,zipfile,xml.etree.ElementTree as ET
from hancom_images import unit
HP='http://www.hancom.co.kr/hwpml/2011/paragraph'
HS='http://www.hancom.co.kr/hwpml/2011/section'
OPF='http://www.idpf.org/2007/opf/'
def q(ns,name):return '{'+ns+'}'+name
def fit_page(width,height):
    landscape=width>height
    available=(277,190) if landscape else (190,277)
    scale=min(available[0]/width,available[1]/height)
    # Leave 1 mm for table border/paragraph rounding at the page edge.
    scale=min((available[0]-1)/width,(available[1]-1)/height)
    return landscape,unit(width*scale),unit(height*scale)
def paginate(path,entries):
    with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
    names=[n for n in files if n.startswith('Contents/section') and n.endswith('.xml')]
    if len(names)!=1:raise RuntimeError('PDF 페이지 배치용 기본 구역이 올바르지 않습니다.')
    base=ET.fromstring(files[names[0]])
    tables=list(base.iter(q(HP,'tbl')))
    if len(tables)!=1:raise RuntimeError('PDF 페이지 표를 찾지 못했습니다.')
    rows=tables[0].findall(q(HP,'tr'))
    if len(rows)!=len(entries):raise RuntimeError('PDF 페이지 수와 표의 행 수가 다릅니다.')
    content=ET.fromstring(files['Contents/content.hpf'])
    # Hancom's namespace includes the trailing slash (see official
    # OWPML/Base/NamespacePrefix.cpp). Keep legacy slashless fixtures readable.
    opf=content.tag[1:].split('}',1)[0] if content.tag.startswith('{') else ''
    if opf not in {OPF,OPF.rstrip('/')}:
        raise RuntimeError('지원하지 않는 HWPX 구역 목록 형식입니다.')
    manifest=content.find(q(opf,'manifest'));spine=content.find(q(opf,'spine'))
    if manifest is None or spine is None:raise RuntimeError('HWPX 구역 목록을 찾지 못했습니다.')
    oldids={i.get('id') for i in manifest if i.get('href') in names or i.get('href','').startswith('section')}
    for item in list(manifest):
        if item.get('id') in oldids:manifest.remove(item)
    for item in list(spine):
        if item.get('idref') in oldids:spine.remove(item)
    for name in names:del files[name]
    for index,(_,w,h) in enumerate(entries):
        section=copy.deepcopy(base);table=next(section.iter(q(HP,'tbl')))
        for row in list(table.findall(q(HP,'tr'))):table.remove(row)
        row=copy.deepcopy(rows[index]);table.append(row);table.set('rowCnt','1');table.set('id',str(100000+index))
        landscape,width,height=fit_page(w,h)
        page=next(section.iter(q(HP,'pagePr')))
        page.set('width',str(unit(210)));page.set('height',str(unit(297)))
        page.set('landscape','WIDELY' if landscape else 'NARROWLY')
        margin=page.find(q(HP,'margin'))
        if margin is not None:
            for key in ('left','right','top','bottom'):margin.set(key,str(unit(10)))
            for key in ('header','footer','gutter'):margin.set(key,'0')
        for cell in row.iter(q(HP,'cellAddr')):cell.set('rowAddr','0')
        for size in list(table.findall(q(HP,'sz')))+list(row.iter(q(HP,'cellSz'))):
            size.set('width',str(width));size.set('height',str(height))
        # Inline pictures also need the new cell's dimensions.
        for pic in row.iter(q(HP,'pic')):
            size=pic.find(q(HP,'sz'))
            if size is not None:size.set('width',str(width));size.set('height',str(height))
        section.set('id',str(index))
        name=f'Contents/section{index}.xml';files[name]=ET.tostring(section,encoding='utf-8',xml_declaration=True)
        ET.SubElement(manifest,q(opf,'item'),{'id':f'section{index}','href':name,'media-type':'application/xml'})
        ET.SubElement(spine,q(opf,'itemref'),{'idref':f'section{index}','linear':'yes'})
    files['Contents/content.hpf']=ET.tostring(content,encoding='utf-8',xml_declaration=True)
    header=ET.fromstring(files['Contents/header.xml']);header.set('secCnt',str(len(entries)))
    files['Contents/header.xml']=ET.tostring(header,encoding='utf-8',xml_declaration=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data,compress_type=zipfile.ZIP_STORED if name=='mimetype' else zipfile.ZIP_DEFLATED)
