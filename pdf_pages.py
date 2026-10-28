"""Turn staged pictures into borderless, original-size PDF pages in HWPX."""
import copy,zipfile,xml.etree.ElementTree as ET
HP='http://www.hancom.co.kr/hwpml/2011/paragraph'
HS='http://www.hancom.co.kr/hwpml/2011/section'
OPF='http://www.idpf.org/2007/opf/'
def q(ns,name):return '{'+ns+'}'+name
def fit_page(width,height):
    # Raster callers without PDF geometry use the converter's 150 DPI.
    return width>height,round(width*48),round(height*48)

def full_page_picture(picture,width,height):
    """Keep the original image coordinates; scale its object to paper bounds."""
    # A normal selectable picture in front of text avoids reserving a full
    # page plus an anchor line (which can create a trailing blank page).
    picture.set('textWrap','IN_FRONT_OF_TEXT')
    picture.set('textFlow','BOTH_SIDES')
    size=picture.find(q(HP,'sz'))
    if size is None:size=ET.SubElement(picture,q(HP,'sz'))
    size.attrib.update(width=str(width),height=str(height),widthRelTo='ABSOLUTE',heightRelTo='ABSOLUTE',protect='0')
    pos=picture.find(q(HP,'pos'))
    if pos is None:pos=ET.SubElement(picture,q(HP,'pos'))
    pos.attrib.update(treatAsChar='0',affectLSpacing='0',flowWithText='0',allowOverlap='1',holdAnchorAndSO='1',vertRelTo='PAPER',horzRelTo='PAPER',vertAlign='TOP',horzAlign='LEFT',vertOffset='0',horzOffset='0')
    for name in ('outMargin','inMargin'):
        margin=picture.find(q(HP,name))
        if margin is not None:margin.attrib.update(left='0',right='0',top='0',bottom='0')
    current=picture.find(q(HP,'curSz'))
    if current is not None:current.attrib.update(width=str(width),height=str(height))
    offset=picture.find(q(HP,'offset'))
    if offset is not None:offset.attrib.update(x='0',y='0')
    original=picture.find(q(HP,'orgSz'))
    if original is not None:
        ow=int(original.get('width','0'));oh=int(original.get('height','0'))
        if ow<=0 or oh<=0:raise RuntimeError('PDF 그림의 원래 크기가 올바르지 않습니다.')
        rendering=picture.find(q(HP,'renderingInfo'))
        if rendering is not None:
            for matrix in rendering:
                kind=matrix.tag.rsplit('}',1)[-1]
                if kind in {'transMatrix','scaMatrix','rotMatrix'}:
                    sx,sy=(width/ow,height/oh) if kind=='scaMatrix' else (1,1)
                    matrix.attrib.update(e1=str(sx),e2='0',e3='0',e4='0',e5=str(sy),e6='0')
    rotation=picture.find(q(HP,'rotationInfo'))
    if rotation is not None:rotation.set('angle','0')
    line=picture.find(q(HP,'lineShape'))
    if line is not None:line.attrib.update(style='NONE',width='0')

def paginate(path,entries,sizes=None):
    sizes=sizes if sizes is not None else [fit_page(w,h)[1:] for _,w,h in entries]
    if len(sizes)!=len(entries) or any(w<=0 or h<=0 for w,h in sizes):
        raise RuntimeError('PDF 페이지 크기 정보가 올바르지 않습니다.')
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
    for index,(width,height) in enumerate(sizes):
        section=copy.deepcopy(base);table=next(section.iter(q(HP,'tbl')))
        pictures=list(rows[index].iter(q(HP,'pic')))
        if len(pictures)!=1:raise RuntimeError('PDF 페이지에 넣을 그림을 찾지 못했습니다.')
        picture=copy.deepcopy(pictures[0]);picture.set('id',str(100000+index))
        full_page_picture(picture,width,height)
        parents={child:parent for parent in section.iter() for child in parent}
        parent=parents[table];position=list(parent).index(table)
        parent.remove(table);parent.insert(position,picture)
        # Keep only the section anchor paragraph, discarding the staging table's
        # trailing paragraphs and cached line positions from the A4 template.
        anchor=parent
        while anchor in parents and parents[anchor] is not section:anchor=parents[anchor]
        for child in list(section):
            if child is not anchor:section.remove(child)
        for node in section.iter():
            for child in list(node):
                if child.tag==q(HP,'linesegarray'):node.remove(child)
        page=next(section.iter(q(HP,'pagePr')))
        # Hancom stores portrait paper dimensions separately from orientation.
        # Its serialized enum is WIDELY=portrait, NARROWLY=landscape.
        # https://forum.developer.hancom.com/t/pagepr-width-height/1693
        page.set('width',str(min(width,height)));page.set('height',str(max(width,height)))
        page.set('landscape','NARROWLY' if width>height else 'WIDELY')
        margin=page.find(q(HP,'margin'))
        if margin is None:margin=ET.SubElement(page,q(HP,'margin'))
        for key in ('left','right','top','bottom','header','footer','gutter'):margin.set(key,'0')
        section.set('id',str(index))
        name=f'Contents/section{index}.xml';files[name]=ET.tostring(section,encoding='utf-8',xml_declaration=True)
        ET.SubElement(manifest,q(opf,'item'),{'id':f'section{index}','href':name,'media-type':'application/xml'})
        ET.SubElement(spine,q(opf,'itemref'),{'idref':f'section{index}','linear':'yes'})
    files['Contents/content.hpf']=ET.tostring(content,encoding='utf-8',xml_declaration=True)
    header=ET.fromstring(files['Contents/header.xml']);header.set('secCnt',str(len(entries)))
    files['Contents/header.xml']=ET.tostring(header,encoding='utf-8',xml_declaration=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data,compress_type=zipfile.ZIP_STORED if name=='mimetype' else zipfile.ZIP_DEFLATED)
