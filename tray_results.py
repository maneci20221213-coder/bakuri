"""Small completion summaries; never emit progress/start toast notifications."""
def size_text(value):return f'{value/1_000_000:.2f} MB' if value>=1_000_000 else f'{value/1000:.1f} KB'

def compression_savings(rows):
    saved=[r for r in rows if r.get('status')=='저장 완료' and r.get('output')]
    before=sum(max(0,r.get('before',0)) for r in saved);after=sum(max(0,r.get('after',0)) for r in saved)
    if not saved or not before:return ''
    reduction=max(0,before-after)
    return f'저장한 {len(saved)}개: {size_text(before)} → {size_text(after)} · {size_text(reduction)} 절감({reduction/before*100:.1f}%)'
