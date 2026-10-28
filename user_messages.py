"""Actionable messages for users; technical diagnostics stay in a local log."""
import logging,os
from logging.handlers import RotatingFileHandler
from pathlib import Path

MESSAGES={
 'startup':'바꾸리를 시작하지 못했습니다. 실행 중인 바꾸리를 완전히 종료한 뒤 다시 열어 주세요. 계속되면 최신 설치 파일로 다시 설치해 주세요.',
 'menu':'우클릭 메뉴를 추가하지 못했습니다. 바꾸리를 다시 실행한 뒤 설정에서 ‘우클릭 메뉴 다시 등록’을 눌러 주세요. 그동안 파일 추가나 단축키로 변환할 수 있습니다.',
 'settings':'설정을 저장하지 못했습니다. 바꾸리를 다시 실행한 뒤 설정을 다시 선택해 주세요.',
 'selection':'선택한 파일을 확인하지 못했습니다. 탐색기에서 파일을 다시 선택해 주세요. 계속되면 바꾸리 창의 ‘파일 추가’를 이용해 주세요.',
 'update_check':'새 버전을 확인하지 못했습니다. 인터넷 연결을 확인하고 잠시 후 바꾸리를 다시 열어 주세요. 현재 버전의 변환 기능은 계속 사용할 수 있습니다.',
 'update_download':'업데이트 파일을 받지 못했습니다. 인터넷 연결과 저장 공간을 확인한 뒤 다시 시도해 주세요. 현재 버전은 계속 사용할 수 있습니다.',
 'update_install':'업데이트를 설치하지 못했습니다. 작업 중인 파일을 저장하고 바꾸리를 완전히 종료한 뒤 최신 설치 파일로 다시 설치해 주세요.',
 'permission':'파일을 읽거나 저장할 수 없습니다. 다른 프로그램에서 열어 둔 파일을 닫고, 해당 폴더에 파일을 저장할 수 있는지 확인해 주세요.',
 'missing':'파일을 찾을 수 없습니다. 이동하거나 삭제한 파일인지 확인한 뒤 목록에서 제거하고 다시 추가해 주세요.',
 'password':'암호로 보호된 PDF는 처리할 수 없습니다. PDF를 열어 암호 없이 저장한 사본으로 다시 시도해 주세요.',
 'damaged':'파일을 정상적으로 읽지 못했습니다. 원래 프로그램에서 파일이 열리는지 확인하고, 새 사본으로 저장한 뒤 다시 시도해 주세요.',
 'office':'문서 변환에 필요한 프로그램을 실행하지 못했습니다. 한글 문서는 한글, Word·Excel·PowerPoint 문서는 해당 Microsoft Office 프로그램이 설치되어 정상 실행되는지 확인해 주세요.',
 'hwp':'한글 문서를 만들지 못했습니다. 한글이 정상 실행되는지 확인하고, 여러 파일을 선택했다면 한 개씩 다시 시도해 주세요.',
 'format':'선택한 파일은 이 방식으로 변환할 수 없습니다. 파일 목록의 체크 표시를 확인하고, 선택 가능한 다른 출력 형식으로 다시 시도해 주세요.',
 'space':'저장 공간이 부족합니다. 원본 파일이 있는 드라이브와 Windows 드라이브의 여유 공간을 확보한 뒤 다시 시도해 주세요.',
 'memory':'파일을 처리할 메모리가 부족합니다. 다른 프로그램을 닫고 파일을 한 개씩 변환해 주세요. PDF를 그림으로 바꿀 때는 설정에서 해상도를 낮춰 보세요.',
 'compression':'이 파일의 용량을 줄이지 못했습니다. 파일이 정상적으로 열리는지 확인한 뒤 다시 시도해 주세요. 원본 파일은 그대로 남아 있습니다.',
 'conversion':'파일을 변환하지 못했습니다. 원본 파일이 정상적으로 열리는지 확인하고, 다른 프로그램에서 파일을 닫은 뒤 한 개씩 다시 시도해 주세요.',
}

def log_error(error,context):
    try:
        logger=logging.getLogger('bakuri.errors')
        if not logger.handlers:
            folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Bakuri';folder.mkdir(parents=True,exist_ok=True)
            handler=RotatingFileHandler(folder/'errors.log',maxBytes=524288,backupCount=1,encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'));logger.addHandler(handler);logger.setLevel(logging.ERROR);logger.propagate=False
        from version import VERSION
        info=(type(error),error,error.__traceback__) if isinstance(error,BaseException) else None
        logger.error('version=%s context=%s %s',VERSION,context,error,exc_info=info)
    except Exception:pass  # A diagnostic failure must not hide the user message.

def friendly_error(error,context='conversion'):
    text=str(error)
    if text in MESSAGES.values():return text
    log_error(error,context)
    if context in {'startup','menu','settings','selection','update_check','update_download','update_install'}:
        return MESSAGES[context]
    lower=text.lower()
    if isinstance(error,MemoryError) or 'out of memory' in lower:key='memory'
    elif getattr(error,'errno',None)==28 or getattr(error,'winerror',None)==112 or 'disk full' in lower:key='space'
    elif isinstance(error,PermissionError) or 'permission denied' in lower or 'access is denied' in lower or '액세스가 거부' in text:key='permission'
    elif isinstance(error,FileNotFoundError) or 'no such file' in lower:key='missing'
    elif '암호' in text or 'password' in lower or 'encrypted' in lower:key='password'
    elif '-2147221005' in text or '-2147221164' in text or 'class not registered' in lower or 'invalid class string' in lower:key='office'
    elif type(error).__name__ in {'FileDataError','EmptyFileError','UnidentifiedImageError','BadZipFile'} or any(s in lower for s in ['broken document','cannot identify image','not a zip file']):key='damaged'
    elif any(s in text for s in ['지원하지','지원하지 않는','합치기는','조합']):key='format'
    elif any(s in text for s in ['한글','HWPX','구역','셀','표의','페이지 크기','페이지 표']):key='hwp'
    else:key='compression' if context=='compression' else 'conversion'
    return MESSAGES[key]
