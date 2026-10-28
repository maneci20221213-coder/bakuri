# 바꾸리

파일을 선택하고 원하는 형식으로 간편하게 변환하는 Windows용 도구입니다.

[**Windows용 바꾸리 다운로드**](https://github.com/maneci20221213-coder/bakuri/releases/latest/download/BakuriSetup.exe)

첫 정식 Release를 게시하기 전에는 위 다운로드 링크가 작동하지 않습니다.

## 사용
1. 기존 바꾸리가 실행 중이면 트레이에서 완전히 종료합니다.
2. BakuriSetup.exe를 내려받아 설치합니다.
3. 탐색기에서 지원 파일을 선택하고 단축키·우클릭 메뉴 또는 확장 기능 창으로 변환합니다.

이미지·PDF·한글·Word·PowerPoint·스프레드시트 변환, 여러 파일 합치기와 이미지·PDF 용량 축소를 지원합니다. 한글·Office 관련 변환에는 해당 프로그램 설치가 필요합니다. PDF·이미지→한글/PPT는 페이지 그림으로 삽입되므로 본문 글자를 개별 편집할 수 없습니다. 원본은 보존하며 이름 충돌 시 숫자 접미사를 붙입니다.

## 업데이트
직접 실행·트레이 열기·확장 기능 창에서 새 버전을 확인하고 알림을 표시합니다. 사용자 승인 후에만 다운로드·설치합니다. '이 버전 건너뛰기'를 지원합니다. Windows 자동 시작·간편 팝업·우클릭 호출에서는 확인하지 않으며, 시작 시 자동 적용도 끕니다. 5분 이내의 반복 확인은 줄입니다. 업데이트 서버에 연결되지 않아도 변환 기능은 사용할 수 있습니다.
앱에는 GitHub 개인 토큰을 포함하지 않습니다. 사용 통계 수집 기능은 없습니다. 업데이트 확인·다운로드 시 GitHub와 통신합니다.

## 지원·검증
Windows x64용입니다. 자동 검사는 실제 파일 처리와 모의 한글·Office API를 포함하며 실제 설치된 한글·Office의 페이지 배치와 서식 전체를 보증하지 않습니다. 코드 서명 인증서는 아직 설정하지 않았습니다. 한글의 상업적 오토메이션 이용 조건은 LICENSES/Hancom-Automation-Module.txt와 공식 안내를 확인하세요.

## 빌드·배포
Python 3.12 x64와 .NET SDK가 설치된 Windows에서 다음을 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

GitHub의 Actions → Windows installer and GitHub Release → Run workflow에서도 Windows 설치본을 빌드할 수 있습니다. 기본은 비공개 릴리즈 초안입니다. 검증 후 게시하거나 publish 입력을 켜서 빌드 성공 시 게시합니다. 이미 게시한 버전은 덮어쓰지 말고 version.py의 버전을 올려 빌드하세요. 자세한 절차는 GITHUB-RELEASE.md를 참고하세요.

## 라이선스·소스
앱 소스는 AGPL-3.0-or-later로 제공합니다. PyMuPDF는 AGPL 조건으로 사용합니다. 제3자 구성요소의 조건과 고지는 LICENSES/ 및 배포 패키지의 third-party-notices/를 참고하세요. 대응 소스와 라이브러리 소스 안내는 SOURCE-NOTICE.md에 있습니다. 소스 공개가 한글 오토메이션의 별도 상업 이용 승인을 대신하지 않습니다.
