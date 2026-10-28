# 바꾸리 0.14.2 설치·업데이트

GitHub Releases를 배포 공간으로 사용합니다. Windows 설치본은 build_release.ps1로 제작합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1 -RepositoryUrl https://github.com/maneci20221213-coder/bakuri
```

앱 버전은 version.py에서 읽습니다. stable 채널, 고정 packId Bakuri.FileConverter, Python/CLI Velopack 1.2.161을 유지합니다. 인증 토큰을 앱에 포함하지 않습니다. 실제 공개 단계와 검증은 GITHUB-RELEASE.md를 참고하세요. 기존 ZIP 사용자는 처음 한 번 설치본으로 전환해야 합니다.
