"""Merge editable HWP/HWPX with Hancom's InsertFile action."""
from hancom_images import action,execute,compact_document

def merge_documents(app,files,dest,checkpoint=lambda:None,advance=lambda fraction,text:None):
    try:
        checkpoint();app.Clear(1)
        if not app.Open(str(files[0]),'',''):raise RuntimeError('첫 번째 한글 문서를 열지 못했습니다.')
        checkpoint();advance(1/len(files)*.85,files[0].name)
        for index,source in enumerate(files[1:],1):
            checkpoint()
            if app.HAction.Run('MoveDocEnd') is False:raise RuntimeError('한글 문서 끝으로 이동하지 못했습니다.')
            act,params=action(app,'InsertFile')
            for key,value in {'FileName':str(source),'FileFormat':'','FileArg':'','KeepSection':1,'KeepStyle':1,'KeepCharshape':1,'KeepParashape':1}.items():params.SetItem(key,value)
            execute(act,params,'한글 문서를 합치지 못했습니다: '+source.name)
            checkpoint();advance((index+1)/len(files)*.85,source.name)
        checkpoint()
        if not app.SaveAs(str(dest),'HWPX','') or not dest.is_file():raise RuntimeError('합친 한글 문서를 저장하지 못했습니다.')
        checkpoint();compact_document(dest,checkpoint);advance(.98,'한글 통합본 저장')
    finally:app.Clear(1)
