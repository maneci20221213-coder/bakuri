# GitHub 배포 절차

계정 maneci20221213-coder의 공개 bakuri 저장소 한 곳에 앱 소스와 GitHub Releases를 둡니다. 계정·저장소가 달라지면 update-config.json, README의 다운로드 링크와 build_release.ps1 기본 RepositoryUrl을 함께 변경합니다. Actions 빌드 시에는 실제 github.repository 주소를 사용합니다.

## 최초 배포
1. 이 폴더의 내용을 공개 bakuri 저장소 루트에 커밋합니다. runtime, 기존 EXE, 개인 파일과 로그는 올리지 않습니다.
2. Actions의 Windows installer and GitHub Release를 수동 실행합니다. 기본 publish=false는 릴리즈 초안을 생성합니다.
3. 테스트와 빌드가 성공한 뒤 Actions artifact 또는 초안에서 BakuriSetup.exe를 내려받습니다.
4. 실제 Windows에서 설치·실행·삭제, 한글·Office 변환과 우클릭 메뉴를 확인합니다.
5. 릴리즈의 모든 파일을 유지한 채 초안을 게시합니다. README 다운로드 버튼은 최신 정식 릴리즈의 BakuriSetup.exe를 가리킵니다.

## 다음 버전
version.py와 RELEASE-NOTES.md를 수정해 커밋하고 같은 workflow를 실행합니다. 버전 번호를 재사용하지 않습니다. 설치본·전체 업데이트 패키지·releases.stable.json·원저작자 고지·동일 버전 소스를 함께 보관합니다. 업데이트용 nupkg 이름을 임의로 바꾸지 않습니다. 단일 다운로드 버튼을 위해 Setup.exe 복사본만 BakuriSetup.exe라는 고정 이름으로 제공합니다.

## 앱 업데이트 정책
- GithubSource(public repository, no token, prerelease=false)를 사용합니다.
- stable 채널에 정식 게시된 릴리즈만 확인합니다. 초안/프리릴리즈는 일반 사용자에게 안내하지 않습니다.
- 직접 실행/트레이 열기/확장 창만 확인합니다. 5분 이내의 반복 확인은 줄입니다.
- 사용자 승인 후 다운로드·적용합니다. 버전 건너뛰기를 저장하며 다음 새 버전은 다시 안내합니다.
- 자동 시작/간편 팝업/우클릭 호출은 확인하지 않습니다. 다운로드된 업데이트 자동 적용은 시작 시 비활성화합니다.
- GitHub API 제한이나 네트워크 오류가 생겨도 문서 변환은 계속 사용할 수 있습니다. 앱에 개인 GitHub 토큰을 넣지 마세요.
- 기존 포터블 ZIP에는 Velopack 설치 정보가 없으므로 최초 한 번 설치본으로 전환해야 합니다.

## 현재 검증 범위
이 구성의 Python 논리·회귀 검사는 로컬에서 실행할 수 있습니다. Windows의 실제 설치·제거·두 버전 간 업데이트·Office 변환은 Windows 빌드 결과로 확인해야 합니다. 코드 서명 인증서는 설정하지 않았습니다. GitHub 업로드와 Windows 빌드가 끝나기 전에는 설치본이 준비됐다고 안내하지 마세요.

## 라이선스
앱은 AGPL 방식으로 소스를 제공합니다. 제3자 원저작자 고지와 대응 소스 조건은 SOURCE-NOTICE.md를 확인합니다. 한컴 오토메이션의 상업 이용 조건은 별도로 적용됩니다.
