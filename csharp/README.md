# 바꾸리 C# 시험판 · 0.16.0-exp.1

Windows 10/11 64비트에서 실행하는 **비교용 시험판**입니다. Python 정식판을 제거하거나 덮어쓰지 않습니다. Python 실행 환경은 사용하지 않습니다.

## 실행
- **SelfContained** ZIP: 압축을 모두 풀고 `BakuriCSharpTrial.exe`를 실행합니다. .NET을 별도로 설치하지 않아도 됩니다.
- **FrameworkDependent** ZIP: **.NET 10 Desktop Runtime x64**가 이미 설치된 PC에서 사용합니다. 런타임을 제외한 크기입니다.
- 파일을 추가하거나 탐색기에서 복사한 파일을 Ctrl+V로 넣으세요. 파일명 변경 탭에서는 미리보기를 확인한 뒤 적용합니다.
- 간편메뉴 기본 단축키는 **Ctrl+Alt+F9**입니다. 정식판·Python 개발판과 겹치지 않도록 분리했습니다. 설정에서 바꿀 수 있습니다.
- 창을 닫으면 목록을 비우고 트레이에 남습니다. 종료하려면 트레이 우클릭 → 완전 종료를 선택하세요.

## 구현 범위와 확인이 필요한 부분
- 이미지 → PDF/PNG/JPEG, PDF 합치기·PNG/JPEG 변환, 이미지/PDF 용량 축소, 파일명 변경·되돌리기를 C#에서 처리합니다.
- PDF의 픽셀 유지 압축만 구현했습니다. PDF 이미지의 비율별 재압축은 아직 이전하지 않았습니다. 이미지 비율은 10~100%로 선택합니다.
- 이미지·PDF → 한글/PPTX, 한글 합치기, 한글·Office 내보내기는 해당 프로그램의 COM 자동화를 사용합니다. **CI에는 한글·Office가 없어 실제 설치 PC 검증이 남아 있습니다.**
- 이미지 → 한글은 표 안에 그림을 넣습니다. PDF → 한글은 원래 크기·방향과 여백 0의 용지에 선택 가능한 그림을 넣도록 변환합니다.
- WIC와 SkiaSharp를 사용하므로 지원 코덱·색상 프로필·EXIF 처리 결과는 Pillow와 다를 수 있습니다. 중요한 원본 대신 복사본으로 비교하세요. 움직이는 이미지의 압축은 건너뜁니다.
- Windows 11의 여러 탐색기 탭·다중 모니터 간편메뉴는 실제 PC 확인이 필요합니다. 간편메뉴의 표/한글 전용 중앙 버튼, 마지막 결과 폴더 바로 열기 등 UI 세부 동작은 정식판과 차이가 있습니다.
- 자동 업데이트·로그인 시 실행·탐색기 우클릭 등록·설치기는 이 시험판에서 사용하지 않습니다. 설정·기록은 `%LOCALAPPDATA%\BakuriCSharpTrial`에 따로 저장합니다.

## 유지보수 구조

| 프로젝트 | 담당 | 의존성 |
| --- | --- | --- |
| Bakuri.Core | 파일 ID, 요청/결과/진행률 모델, 변환 지원표, 이름 규칙, 미리보기, 변경 트랜잭션 | .NET 기본 라이브러리 |
| Bakuri.Infrastructure | 파일 시스템, 원자 저장, JSON 설정/기록, STA 작업 실행, MuPDF/WIC/Office 어댑터 | Core |
| Bakuri.Desktop | WPF 화면, 목록 ViewModel, 트레이, 단축키·간편메뉴 | Core, Infrastructure |
| Bakuri.Checks | 실제 파일 변경/롤백/취소와 이미지/PDF 검증, 비교 측정 | Core, Infrastructure |

파일은 경로 대신 **안정적인 Guid ID**로 연결합니다. 미리보기는 불변 `RenameItem` 목록, 작업은 불변 `JobRequest`, 결과는 `JobReport/FileResult`로 주고받습니다. 화면 모델만 알림 가능한 객체입니다. 중복 추가는 대소문자를 무시하는 사전으로 조회합니다.

이름 변경은 원본 식별자·크기·수정 시각을 확인하고 같은 폴더의 임시 이름을 거치는 2단계 이동으로 처리합니다. 기존 파일을 덮어쓰지 않습니다. 단계마다 디스크에 기록하고 실패하면 롤백합니다. 프로세스 중단 등으로 복구가 필요한 기록은 보존하며 추가 이름 변경을 막습니다. **자동 재해 복구 UI는 아직 없습니다.**

변환은 직렬 STA 작업 스레드에서 실행하고 화면과 분리합니다. 취소는 처리 단계 사이에 적용합니다. 멈춘 Office COM 호출을 강제로 중단하지는 못합니다. PDF 페이지는 디스크의 임시 이미지 경로로 전달하고 HWPX 재압축은 스트림으로 복사해 모든 페이지의 비트맵·바이너리를 한꺼번에 보관하지 않습니다.

MuPDF 계열은 유지하되 Python 정식판의 PyMuPDF 1.26.7과 C#의 MuPDF.NET 3.28.2.4 / native MuPDF 1.28.2는 **버전과 래퍼가 다릅니다.** 비교 결과를 언어 하나의 효과로 해석하면 안 됩니다. AGPL-3.0-or-later 공개 소스 배포 조건을 유지합니다.

## 빌드와 검사
.NET 10 SDK x64와 Windows가 필요합니다.

```powershell
dotnet build csharp/src/Bakuri.Desktop -c Release -r win-x64
dotnet run --project csharp/tests/Bakuri.Checks -c Release -r win-x64
./csharp/scripts/build.ps1
```

GitHub `experiment/csharp` 브랜치의 **CSharp experiment** Actions에서 ZIP 두 종류, 소스, 실제 측정 JSON과 화면을 받습니다. 정식 릴리즈와 업데이트 피드에 게시하지 않습니다. 압축 크기는 측정 JSON의 `Packages`, 변환 비교는 `native-benchmark.json`과 `python-benchmark.json`을 확인하세요. CI의 합성 PNG 12개를 합치는 한 가지 시나리오이므로 실제 한글·Office 성능이나 모든 PDF의 성능을 대표하지 않습니다. V3 검사 결과는 빌드 검사로 보장할 수 없습니다.
