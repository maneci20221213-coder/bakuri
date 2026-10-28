"""Lossless image decoding shared by raster, PDF, and HWPX routes."""
from pathlib import Path
from PIL import Image, ImageOps
import shutil

IMAGES={'.png','.jpg','.jpeg','.bmp','.gif','.tif','.tiff','.webp','.ico'}

def frames(path):
    """TIFF: every page; animated images: first displayed frame only."""
    path=Path(path)
    with Image.open(path) as source:
        count=getattr(source,'n_frames',1) if path.suffix.lower() in {'.tif','.tiff'} else 1
        for index in range(count):
            source.seek(index)
            yield ImageOps.exif_transpose(source).convert('RGBA')

def white_rgb(image):
    result=Image.new('RGB',image.size,'white')
    result.paste(image,mask=image.getchannel('A'))
    return result

def save_png(image,target,original=None):
    """Lossless PNG output: avoid an unnecessary opaque alpha channel."""
    if image.mode=='RGBA' and image.getchannel('A').getextrema()==(255,255):
        image=image.convert('RGB')
    image.save(target,'PNG',optimize=True,compress_level=9)
    if original is not None:
        with Image.open(original) as source:
            reusable=(source.format=='PNG' and source.getexif().get(274,1)==1
                      and getattr(source,'n_frames',1)==1)
        if reusable and Path(original).stat().st_size<Path(target).stat().st_size:
            shutil.copyfile(original,target)

def page_sizes(paths):
    """Displayed PDF crop-box dimensions, including rotation, in HWPUNIT."""
    import fitz
    sizes=[]
    for path in paths:
        if Path(path).suffix.lower()=='.pdf':
            with fitz.open(path) as document:
                if document.needs_pass:raise ValueError('암호가 있는 PDF는 지원하지 않습니다.')
                sizes.extend((round(page.rect.width*100),round(page.rect.height*100)) for page in document)
        else:
            sizes.extend((round(image.width*48),round(image.height*48)) for image in frames(path))
    return sizes

def stage_images(paths,folder,progress=lambda text:None,checkpoint=lambda:None,advance=lambda fraction:None):
    """Reuse compatible JPEG/PNG bytes; normalize only when required, in input order."""
    folder=Path(folder); entries=[]
    for path_index,path in enumerate(paths):
        checkpoint()
        if Path(path).suffix.lower()=='.pdf':
            import fitz
            with fitz.open(path) as document:
                if document.needs_pass: raise ValueError('암호가 있는 PDF는 지원하지 않습니다.')
                for number,page in enumerate(document):
                    checkpoint()
                    target=folder/f'image_{len(entries):06}.png'
                    page.get_pixmap(dpi=300,alpha=False).save(str(target))
                    checkpoint()
                    with Image.open(target) as image: entries.append((target,image.width,image.height))
                    progress(f'{Path(path).name} · {number+1}/{len(document)}페이지 준비')
            advance((path_index+1)/len(paths))
            continue
        source=Path(path)
        with Image.open(source) as original:
            reusable=(original.format in {'JPEG','PNG'} and original.getexif().get(274,1)==1
                      and getattr(original,'n_frames',1)==1 and original.mode in {'RGB','RGBA','L','LA','P','1'})
            size=original.size;extension='.jpeg' if original.format=='JPEG' else '.png'
        if reusable:
            target=folder/f'image_{len(entries):06}{extension}'
            shutil.copyfile(source,target)
            entries.append((target,*size));progress(f'{source.name} · 원본 이미지 압축 유지')
            checkpoint();advance((path_index+1)/len(paths));continue
        for number,image in enumerate(frames(path)):
            checkpoint()
            target=folder/f'image_{len(entries):06}.png'
            image.save(target,'PNG',optimize=True)
            if source.suffix.lower() in {'.jpg','.jpeg'}:
                # EXIF rotation/CMYK requires normalized pixels. Avoid expanding
                # photographic JPEGs to large PNGs even on this fallback path.
                candidate=target.with_suffix('.jpeg')
                with Image.open(source) as original:icc=original.info.get('icc_profile') if original.mode!='CMYK' else None
                white_rgb(image).save(candidate,'JPEG',quality=95,subsampling=0,optimize=True,**({'icc_profile':icc} if icc else {}))
                if candidate.stat().st_size<target.stat().st_size:
                    target.unlink();target=candidate
                else:candidate.unlink()
            entries.append((target,image.width,image.height))
            progress(f'{Path(path).name} · {number+1}번째 이미지 준비')
        advance((path_index+1)/len(paths))
    return entries
