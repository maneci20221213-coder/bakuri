# PDF→HWPX 구역 목록 오류 수정

오류 지점: pdf_pages.paginate의 content.hpf manifest/spine 검색.
기존 상수: http://www.idpf.org/2007/opf
한컴의 실제 상수: http://www.idpf.org/2007/opf/

한컴 공식 구현: https://github.com/hancom-io/hwpx-owpml-model/blob/main/OWPML/Base/NamespacePrefix.cpp
공식 구조 설명: https://tech.hancom.com/hwpxformat/

기존 코드에 실제 네임스페이스를 가진 구역 목록을 입력해 사용자 화면과 동일한 오류를 재현했습니다. 이를 바탕으로 상수를 수정하고 입력 네임스페이스를 읽어 출력에도 유지합니다. 기존 슬래시 없는 네임스페이스는 호환 처리합니다.
재발 방지 검사에서는 앱의 OPF 상수를 가져와 입력을 만들지 않고, 실제 네임스페이스를 명시한 별도 입력으로 검증합니다. PDF 렌더링→한글 저장 모의 API→페이지별 구역 배치까지 연결한 검사도 포함합니다.
Windows에서 실제 한글을 실행한 검증은 아니며, 첨부된 PDF 원본이 없어 사용자 문서 자체를 변환한 것은 아닙니다.
