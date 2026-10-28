# 로컬 검증

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
