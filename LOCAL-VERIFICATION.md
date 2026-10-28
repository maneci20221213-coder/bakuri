# 로컬 검증

## 0.14.4
로컬 자동 검사 98개 통과. 설정 옆 ? 버튼과 F1으로 도움말 열기, 도움말을 열 때 업데이트 확인을 하지 않는 동작, 오프라인 설명서 내용과 스크롤, 오류 안내의 기술 정보 차단 및 로컬 진단 기록을 확인했습니다. 기존 개발용 README는 DEVELOPER-README.md에 보관했습니다.

## 0.14.3
로컬 자동 검사 92개 통과. PNG→PDF의 무손실 압축·투명도, PNG 재저장 용량, 합치기, PDF의 회전·표시 영역·원본 페이지 크기와 한글의 여백 없는 그림 개체 배치를 검사했습니다.
1200×1600 단색/도형 PNG 시험: 기존 PDF 5,763,510바이트 → 수정 후 13,064바이트. 렌더링 픽셀 동일. 모든 이미지에서 같은 축소율을 보장하지는 않습니다.
실제 한글·Office에서 열기·출력·화면 배치는 별도 확인이 필요합니다.

## 0.14.2

버전 0.14.2. 자동 검사 87개 통과.
공개 GithubSource 생성은 실제 Velopack 1.2.161 SDK로 확인했습니다. 토큰은 포함하지 않습니다.
GitHub workflow YAML과 버전 리소스 문법, 소스 ZIP 포함 범위를 검사했습니다.
2026-10-28 GitHub Actions의 Windows Server 2022 / Python 3.12 x64에서 87개 검사를 통과했습니다.
PyInstaller 실행 파일이 Qt와 메인 창을 초기화하고 IPC 서버를 여는 시작 검사도 통과했습니다.
win-x64 설치본·stable 업데이트 피드·소스 ZIP 생성 및 GitHub v0.14.2 게시를 확인했습니다.
공개 설치본 다운로드의 SHA256과 Windows 실행 파일 헤더, 업데이트 피드의 버전·패키지명을 확인했습니다.
빌드: https://github.com/maneci20221213-coder/bakuri/actions/runs/40661789184
릴리스: https://github.com/maneci20221213-coder/bakuri/releases/tag/v0.14.2
실제 설치·제거·두 버전 간 업데이트·한글/Office 실행과 화면 배치는 아직 별도 확인이 필요합니다.


## 0.14.5 refactoring

- 102 local regression tests passed (Linux/offscreen; Office automation uses doubles).
- Settings UI and file-list UI extracted; removed unused save_new and obsolete runtime-folder launcher/build/emulation/self-test scripts. Git history retains these scripts. Legacy registry/IPC names and migrations remain for compatibility.
- File duplicate lookup is one set per added batch, instead of scanning all existing rows per input. Disconnected IPC clients are released.
- Tray matte is generated at build time; no per-pixel work at startup.
- Removed only unused Pillow AVIF decoder from frozen build (7,833,600 bytes in previous package). PDF engine and software OpenGL fallback retained. Final archive sizes are measured in Windows CI.
- PNG-to-PDF benchmark: 1800×2400 images, median of 3 runs on the same Linux host. Document 0.2750 → 0.1632 seconds; synthetic photo/noise 1.3191 → 0.5942; transparent 0.3269 → 0.2445. All rendered pixels identical; output sizes unchanged except one byte in document PDF metadata. These are sample conversion results, not a general speed guarantee.
- Windows CI additionally compiles the installer UI, checks its checkbox/cancellation, installs the real frozen app in an isolated folder, and exercises desktop shortcut creation/removal with the stable launcher. The tiny .NET Framework UI wraps the existing Velopack payload; update packages keep using Velopack directly.
- Default startup applies only to new preferences; prior disabled users and later explicit opt-outs are preserved. Windows shell integration remains disabled in ordinary automated tests to protect the runner.
