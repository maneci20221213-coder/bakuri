# 바꾸리 개발 인수인계

2026-11-12 기준. Claude Code와 Codex에서 같은 저장소를 이어서 작업하기 위한 문서입니다. 이후 변경 사항은 브랜치의 최신 코드와 CI 결과를 우선 확인하세요.

## 1. 바로 시작하기

```powershell
git clone --branch develop https://github.com/maneci20221213-coder/bakuri.git
cd bakuri
git status -sb
```

먼저 [AGENTS.md](../AGENTS.md)를 읽고, 수정할 기능의 소유 모듈만 확인하세요. 구조 변경이 필요하면 [ARCHITECTURE.md](ARCHITECTURE.md)를 참고하세요.

```powershell
python tools/context.py convert
python tools/context.py office
python tools/context.py window --symbol Window.start_sheets
```

Excel 시트 기능의 최신 소유 모듈은 `bakuri/conversion/spreadsheets.py`와 `bakuri/ui/sheets.py`입니다. 기존 `tools/context.py office` 목록만으로 이 두 파일을 빠뜨리지 않도록 확인하세요.

## 2. 브랜치와 배포 상태

| 구분 | 확인된 상태 |
|---|---|
| 저장소 | https://github.com/maneci20221213-coder/bakuri |
| 개발 브랜치 | `develop` |
| 이 문서 작성 직전 기능 커밋 | `d253425097aba387d4bee71fa528e8a146c6a1b6` |
| 정식 배포 브랜치 | `main` |
| 최신 공개 릴리스 | `v1.0.4`, 2026-11-05 게시 |
| 개발판 내부 버전 | `version.py`의 `1.0.0`, 표시와 ZIP 이름은 `1.0.0-dev.17` |
| 최신 개발판 Windows 검증 | 자동 테스트 287개와 팝업·결과 알림·드래그·패키징 실행 검증 성공 |

공개 릴리스와 개발판은 버전 문자열만으로 최신 여부를 판단하기 어렵습니다. 개발판 파일 이름이 계속 `dev.17`이므로 커밋과 빌드 실행 번호를 함께 확인하세요.

- [공개 릴리스 1.0.4](https://github.com/maneci20221213-coder/bakuri/releases/tag/v1.0.4)
- [최신 기능 개발판 빌드](https://github.com/maneci20221213-coder/bakuri/actions/runs/42975316639)
- [해당 빌드 다운로드](https://github.com/maneci20221213-coder/bakuri/actions/runs/42975316639/artifacts/13835700387)

위 다운로드는 GitHub 로그인이 필요합니다. 확인 당시 만료 예정은 2026-12-11이며, 삭제되거나 만료되면 개발판 workflow를 다시 실행하세요. 내려받은 artifact 안의 `Bakuri-Development-1.0.0-dev.17.zip`을 풀어 `BakuriDevelopment.exe`를 실행합니다.

현재 `develop`은 `DEVELOPMENT=True`, 기본 단축키 `F9`이며 설정·IPC가 정식판과 분리되어 있습니다. 개발판의 자동 업데이트 확인은 비활성화됩니다. 정식판 기본 단축키는 백틱입니다.

정식 배포 때는 개발판의 `version.py`, `build_channel.py`, 개발 브랜치의 패치노트·릴리스 안내를 그대로 덮어쓰지 않도록 검토해야 합니다. `main`의 배포 채널 설정을 유지하고, 기존 공개 버전보다 높은 버전과 사용자용 릴리스 안내를 준비하세요.

## 3. 기술 구성과 실행

- Windows x64용 Python 3.12 앱. UI는 PySide6, PDF는 PyMuPDF, 이미지는 Pillow를 사용합니다.
- 한글·Word·Excel·PowerPoint 관련 작업은 설치된 프로그램을 COM으로 제어합니다. 모든 변환에 모든 Office 프로그램이 필요한 것은 아닙니다. 예를 들어 이미지·PDF → Word와 ODT → DOCX는 Word를 사용합니다.
- CAD는 ezdxf와 번들 LibreDWG를 사용하고, DWG는 설치된 ODA File Converter가 있으면 우선 활용합니다.
- PyInstaller `onedir`로 패키징합니다. 정식 설치·업데이트는 Velopack과 GitHub Releases를 사용합니다.
- C# 전환과 PDF 엔진 교체 시험은 종료했고, 현재 개발은 Python 코드로 이어갑니다.
- 앱 소스 라이선스는 AGPL-3.0-or-later입니다. 구성요소별 고지는 `LICENSES/`와 `SOURCE-NOTICE.md`를 확인하세요.

Windows 개발 환경 예시입니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt pyinstaller==6.16.0
python app.py
```

로컬 개발판 빌드는 가상환경을 활성화한 상태에서 실행합니다. 번들 CAD 도구를 준비하는 과정에 인터넷 연결이 필요할 수 있습니다.

```powershell
powershell -NoProfile -File .\build_dev.ps1
```

GitHub의 `Developer test build` workflow는 `develop` push 또는 수동 실행으로 작동하며, 검사 후 Windows ZIP과 대응 소스를 artifact에 올립니다. 정식 릴리스 workflow는 `main`에서 수동 실행하며 `publish` 기본값은 false입니다. 자세한 정식 배포 절차는 `GITHUB-RELEASE.md`를 참고하세요.

## 4. 구현된 기능

| 영역 | 현재 동작 |
|---|---|
| 파일 변환 | 이미지·PDF·한글·Word·ODT·Excel·PowerPoint·DWG/DXF 입력. 정확한 입력/출력 조합은 `bakuri/domain/formats.py`가 기준 |
| 출력 형식 | PDF, PNG, JPEG, HWPX, DOCX, XLSX, PPTX |
| 문서·이미지 합치기 | PDF 통합, 한글 문서끼리 HWPX 통합, 이미지·PDF의 HWPX/PPTX 통합 등 지원 가능한 조합만 활성화 |
| 페이지 나누기 | PDF·HWP·HWPX·DOC·DOCX를 일정 쪽 수, 특정 쪽 시작, 입력 순서의 쪽 추출로 나눔. 원본 형식으로 저장 |
| 이미지·PDF 용량 축소 | 축소 프로필과 10% 단위 옵션. 결과가 작아진 파일만 저장. 실패·효과 없음·건너뜀은 요약의 실패 수에 합산하고 상세 이유 제공 |
| MPO 사진 | 여러 사진과 보조 이미지를 구분하고 대표만 처리하거나 모든 사진 각각 저장 |
| 파일명 변경 | 찾아 바꾸기, 문자열·파일별 문구·연번 추가, 파일명 새로 쓰기, 직접 편집, 여러 줄 붙여넣기, 직전 실행 취소 |
| 목록 | Ctrl+C/Ctrl+V 가져오기, 여러 파일 드래그 순서 변경, 끝에서 자동 스크롤, 탭별 열 너비 기억 |
| 빠른 변환 | 탐색기 선택 파일을 단축키·우클릭으로 처리. 유형별 네 방향 메뉴 사용자 설정과 비지원 동작 비활성화 |
| 작업 | 순차 대기열, 현재 작업 중지와 대기 작업 취소, 진행률·예상 시간, 트레이 완료 알림과 최근 결과 |

이미지 입력은 PNG/JPEG/MPO/BMP/GIF/TIFF/WebP/ICO를 포함합니다. Excel 입력은 XLS/XLSX/XLSM/XLSB/템플릿/CSV/TSV/ODS/DIF/SLK 등을 지원하지만, 시트 작업에는 아래의 별도 보존 제한이 적용됩니다.

PDF·이미지 → HWPX·DOCX·PPTX는 그림을 삽입하는 방식입니다. ODT → DOCX는 Word로 열어 편집 가능한 문서로 저장합니다. PDF → HWPX는 PDF 페이지 크기와 표시 방향을 유지해 용지에 맞는 그림을 넣습니다.

합친 파일명은 공통 이름이 있으면 `공통 이름_통합본.ext`, 없으면 첫 원본이 있는 `폴더명_통합본.ext`입니다. 이름 충돌 시 기존 파일을 보존하고 번호를 붙입니다.

## 5. 최근 작업과 소유 파일

| 커밋 | 변경 | 주요 파일 |
|---|---|---|
| `d04b2d5` | ODT·이미지·PDF → Word, 똑똑하게 저장, 설정 선택 표시와 호버 | `conversion/office.py`, `application/control.py`, `application/settings.py`, `settings_ui.py`, `ui/main_view.py`, `theme.py` |
| `82d9ae6` | 새 기본 저장 위치에 맞게 Windows MPO 검증 수정 | `verify_multi_image.py` |
| `7b149a6` | 여러 줄 결과 안내에 HTML 코드가 그대로 보이던 문제 수정 | `ui/results.py`, `test_completion_ui.py` |
| `d253425` | Excel 시트 합치기·나누기와 기본 팝업 배치 | `conversion/spreadsheets.py`, `ui/sheets.py`, `domain/models.py`, `domain/quick_actions.py`, `ui/quick_popup.py`, `ui/main_window.py`, `test_excel_sheets.py` |

표의 `conversion/`, `application/`, `domain/`, `ui/`는 모두 저장소의 `bakuri/` 아래에 있습니다.

### 똑똑하게 저장

`smart`가 새 기본값입니다. 실제 생성 결과가 하나면 해당 원본 폴더에 저장하고, 여러 개면 첫 입력 폴더 아래에 새 `바꾸리 변환` 폴더를 만듭니다. 폴더가 이미 있으면 번호를 붙입니다. 기존에 저장된 사용자의 다른 위치 설정은 유지합니다.

`application/control.py`의 `JobControl.save_to()`와 `_OutputLocation`이 첫 결과를 임시 보관해 실제 결과 개수를 판별합니다. `application/runner.py`가 변환·압축·페이지 나누기·시트 작업을 같은 저장 정책으로 실행합니다. 작업 중지 후 완료 파일 보존과 압축 결과의 경로 치환을 유지해야 합니다.

### Word 변환과 결과 안내

`OfficeSession.word_document()`는 PDF 페이지 또는 이미지를 DOCX에 그림으로 넣습니다. PDF는 Word 용지 크기 제한 안에서 원본 크기·방향을 반영하고, 이미지는 비율에 맞는 A4 가로/세로에 배치합니다. ODT → DOCX는 Word의 `SaveAs2`를 사용합니다.

하단 완료 안내는 `<html>`로 감싸 자동 텍스트 판별 문제를 피하고, 일반 문구는 HTML escape한 뒤 줄바꿈을 `<br>`로 바꿉니다. 링크는 저장 폴더 열기와 상세 결과로 연결합니다. 사용자 파일명·메모를 HTML에 직접 이어 붙이지 마세요.

### Excel 시트 작업

- 단축키 팝업 기본값은 파일 한 개에서 상단 `시트 나누기`, 여러 개에서 상단 `시트 합치기`입니다. 왼쪽 PDF, 오른쪽 PNG이며 사용자가 지정한 메뉴는 우선 적용합니다.
- 메인 출력 형식의 `시트 합치기`·`시트 나누기`, 그리고 XLSX의 `하나로 합치기`에서도 실행합니다.
- `SheetsDialog`가 별도 스레드로 시트 목록을 읽습니다. 선택 목록과 수식 옵션을 불변 `SheetsRequest`에 담아 대기열로 전달합니다.
- 파일 순서대로 각 원본의 시트를 한 묶음으로 복사합니다. 중복 시트명에는 파일명·번호를 붙이고 Excel의 31자 제한을 처리합니다.
- 나누기는 고른 시트만 `원본 파일명_시트명.xlsx`로 저장합니다. 선택한 숨김 시트는 독립 파일에서 표시되도록 처리합니다.
- 수식 유지가 기본입니다. `수식을 현재 값으로 저장`은 셀의 값을 유지하며 수식을 값으로 바꿉니다. 외부 참조가 남으면 결과에 안내합니다.
- 원본은 읽기 전용으로 열고 저장하지 않습니다. 시트 목록 확인 후 원본이 바뀌면 크기·수정 시각을 대조해 다시 선택하도록 안내합니다.
- VBA·Excel 4 매크로가 있으면 작업을 거부하고 매크로 없는 XLSX 사본을 안내합니다. 보호 설정 때문에 필요한 변경이 불가능하거나 서로 다른 전역 이름 정의가 충돌해도 이유를 표시합니다.
- 실제 Office 동작은 `OfficeSession.excel()`·`open_spreadsheet()`를 재사용합니다. COM 생성과 해제는 같은 작업 스레드에서 처리합니다.

## 6. 이어서 확인할 사항

1. 실제 Excel이 설치된 Windows에서 시트 합치기·나누기 결과를 확인해야 합니다. 모의 COM 테스트와 Windows UI/패키징 검증은 통과했지만, 실제 Excel 문서의 모든 서식·수식 검증을 완료한 상태는 아닙니다.
2. 우선 확인할 사례는 한글 시트명, 여러 시트의 교차 참조, 중복 시트명, 숨김 시트, 차트, 전역 이름 정의, 수식 유지/값 저장, 중지 후 부분 결과, 서로 다른 원본 폴더와 저장 위치입니다. 필요하면 비식별 예제 파일로 검증하세요.
3. Word의 새 DOCX 생성 경로와 한글의 페이지 배치는 실제 설치된 해당 프로그램에서도 확인이 필요합니다. COM 모의 테스트 성공을 실제 문서 전체 검증으로 표현하지 마세요.
4. CAD 글꼴·배치·외부 참조는 도면에 따라 차이가 날 수 있습니다. 진행률은 관측한 작업량이고 예상 시간은 추정입니다. 외부 COM 호출 도중에는 세밀한 진행률이나 즉시 취소를 제공하기 어렵습니다.
5. Excel → Word/HWPX의 편집 가능한 표 삽입은 구현 가능성 검토만 했으며 아직 구현하지 않았습니다. 사용자가 추가 구현을 요청하면 별도 범위를 정해 진행하세요.
6. SignPath 무료 서명 신청은 사용자가 제출했다고 알려 주었으며, 승인 결과와 인증서·서명 연동은 확인되지 않았습니다. 현재 배포 빌드에는 서명 단계가 없습니다. 한컴 `FilePathCheckerModuleExample.dll`과 의존성 허용 여부는 심사에서 확인할 항목입니다. 임의로 DLL을 제거하거나 승인되었다고 가정하지 마세요.
7. V3 격리 문제는 반복 보고되었습니다. 서명 후 탐지가 없어졌다는 검증 결과는 없습니다. 사용 통계·원격 오류 수집은 구현하지 않았고, 오류 진단은 `user_messages.py`의 로컬 로그를 사용합니다.

## 7. 검사와 다음 변경 절차

```powershell
python tools/check.py convert
python tools/check.py window
python tools/check.py all
python -m ruff check bakuri tools test_application.py test_architecture.py app.py engine.py compression.py jobs.py rename_engine.py file_list.py rename_ui.py work_ui.py
python -m black --check bakuri tools app.py engine.py compression.py jobs.py rename_engine.py file_list.py rename_ui.py work_ui.py prepare_source.py test_application.py test_architecture.py
```

`tools/check.py`가 Qt offscreen과 셸 등록 비활성 환경을 설정합니다. Linux에서는 Windows 전용 검사가 일부 건너뛰어질 수 있습니다. 최신 기능 커밋의 Linux 검사에서는 287개 중 286개가 통과하고 1개가 건너뛰어졌고, Windows CI에서는 287개가 통과했습니다.

변경 전 작업 트리와 브랜치를 확인하고 관련 검사부터 실행하세요. push 전 전체 검사와 저장소 필수 검사를 마치세요. Windows CI의 `verify_popup.py`, `verify_multi_image.py`, `verify_pdf_split.py`, `verify_completion_ui.py`, `verify_reorder.py`와 패키징 실행 확인도 통과해야 합니다.

개발판 push는 개발판 ZIP을 생성합니다. 정식 릴리스는 사용자 배포 요청 후 진행합니다. 사용자용 설명은 짧은 조작 방법과 실사용 제한 중심으로 작성하고, 개발 과정이나 내부 처리 개수는 개발 문서에 남기세요. 패치노트에는 공개 릴리스 내역만 적습니다.

## 8. 다른 도구에 전달할 시작 요청

```text
이 저장소의 바꾸리 파일 변환기 개발을 이어서 진행해 주세요.
먼저 AGENTS.md와 docs/HANDOFF.md를 읽고 develop 브랜치와 작업 트리 상태를 확인해 주세요.
현재 기능 기준 커밋은 d253425이고, 공개 릴리스는 1.0.4입니다.
최근 Word 변환, 똑똑하게 저장, 결과 안내 표시 수정, Excel 시트 합치기·나누기가 개발판에 반영되었습니다.
관련 소유 모듈과 검사만 먼저 살펴보고 기존 원본 보존·대기열·개발판 분리를 유지해 주세요.
답변은 한국어 존댓말로 작성해 주세요.

이번 요청은 아래와 같습니다.
[여기에 수정할 내용 또는 발견한 증상을 적으세요.]
```
