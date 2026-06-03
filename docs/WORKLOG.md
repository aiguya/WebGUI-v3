# WebGUI.v3 작업 회의록

이 문서는 WebGUI.v3에서 진행한 주요 작업을 회의록처럼 남기기 위한 기록입니다.
앞으로 기능 단위 작업이 끝날 때마다 아래 형식으로 이어서 작성합니다.

## 기록 원칙

- 날짜와 시간은 가능하면 KST 기준으로 적는다.
- 작업 목표, 결정 사항, 변경 파일, 검증 결과, 커밋 해시를 함께 남긴다.
- 실패하거나 대체한 검증도 숨기지 않고 적는다.
- 후속 작업이 있으면 다음 단계에 남긴다.

## 2026-06-03

### 템플릿 리스트 즐겨찾기 필터

- 목표: 템플릿 리스트 검색 입력 오른쪽에 즐겨찾기 필터 버튼을 추가한다.
- 결정: 별 버튼을 토글 버튼으로 두고, 활성화 시 즐겨찾기 템플릿만 표시한다.
- 변경:
  - `templates/index.html`: `templateFavoriteOnly` 버튼 추가, 정적 캐시 버전 갱신.
  - `static/app.js`: `templateFavoriteOnly` 상태, 필터링, 버튼 상태 동기화 추가.
  - `static/styles.css`: 검색줄 2열 배치와 필터 버튼 스타일 추가.
- 검증:
  - `node --check static/app.js` 통과.
  - `git diff --check` 통과.
  - Flask test client로 메인 HTML, `/health`, `/api/video-templates` 확인.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/` 응답에서 캐시 버전과 버튼 확인.
- 백업: `backups/before-template-favorite-filter-20260603-104225`
- 커밋: `6e3fdbd Add template favorite filter`

### 재사용 가능한 템플릿 블록 보관함

- 목표: 템플릿 컷 블록을 따로 저장하고 다시 불러와 현재 템플릿에 추가할 수 있게 한다.
- 결정:
  - 템플릿과 별도의 `video-template-blocks.json` 저장소를 둔다.
  - 오른쪽 적용 미리보기 패널 아래에 블록 보관함을 배치한다.
  - 각 컷 카드에는 `블록 저장` 버튼을 둔다.
- 변경:
  - `app.py`: `video-template-blocks.json` 초기화, 정규화 함수, 조회/저장/삭제 API 추가.
  - `templates/index.html`: 블록 보관함 UI, 검색, 즐겨찾기 필터, 새로고침 영역 추가.
  - `static/app.js`: 블록 로드/렌더링/검색/즐겨찾기/삭제/현재 템플릿 추가/컷 저장 로직 추가.
  - `static/styles.css`: 블록 보관함 카드, 버튼, 반응형 스타일 추가.
- 검증:
  - `node --check static/app.js` 통과.
  - `py_compile app.py` 통과.
  - `git diff --check` 통과.
  - Flask test client로 블록 저장, 즐겨찾기 변경, 조회, 삭제 흐름 확인.
  - v3 서버 재시작 후 `/health`, `/`, `/api/video-template-blocks` 확인.
  - Codex 브라우저 자동 확인은 환경 오류로 실패했고 서버/API 검증으로 대체했다.
- 백업: `backups/before-template-block-library-20260603-104831`
- 커밋: `06ae0f6 Add reusable video template blocks`

### 작업 회의록 도입

- 목표: 앞으로 진행하는 작업을 참조 가능한 회의록 형태로 남긴다.
- 결정: `docs/WORKLOG.md`를 기준 기록 파일로 사용한다.
- 변경:
  - `docs/WORKLOG.md`: 기록 원칙과 2026-06-03 템플릿 작업 기록 추가.
- 백업: `backups/before-worklog-20260603-105541`
- 다음 단계: 이후 기능 작업 완료 시 이 파일에 작업 목표, 결정, 변경, 검증, 커밋을 계속 누적한다.

### 아이콘 포함 EXE 런처

- 목표: `run_webgork_app.bat`을 더블클릭용 아이콘 포함 실행파일로 실행할 수 있게 한다.
- 결정:
  - 앱 전체를 단일 파일로 패킹하지 않고, 기존 배포 폴더 옆에서 배치파일을 실행하는 작은 Windows 런처를 만든다.
  - 실행파일 이름은 `WebGUI.v3.exe`로 둔다.
  - 런처는 같은 폴더의 `run_webgork_app.bat`을 찾고, 없으면 오류 메시지 창을 띄운다.
- 변경:
  - `tools/WebGuiLauncher.cs`: 배치파일 실행용 WinForms 런처 소스 추가.
  - `tools/build_webgui_launcher.ps1`: 아이콘 생성과 EXE 컴파일 스크립트 추가.
  - `static/icon.ico`: EXE에 삽입할 ICO 아이콘 생성.
  - `WebGUI.v3.exe`: `run_webgork_app.bat` 실행용 Windows 런처 생성.
- 검증:
  - `tools/build_webgui_launcher.ps1` 실행 성공.
  - `WebGUI.v3.exe` 생성 확인.
  - `static/icon.ico` 생성 확인.
  - `System.Drawing.Icon.ExtractAssociatedIcon`으로 EXE 아이콘 추출 확인.
- 백업: `backups/before-exe-launcher-20260603-105919`
- 주의: 이 EXE는 단독 패키징 파일이 아니라 같은 폴더의 `run_webgork_app.bat`을 실행하는 런처다.

### 템플릿 즐겨찾기 필터 시각 상태 개선

- 목표: 템플릿 검색창 옆 즐겨찾기 필터 버튼의 활성/비활성 상태를 더 명확하게 구분한다.
- 결정: 비활성은 외곽 별 `☆`, 활성은 노란 배경의 채운 별 `★`로 표시한다.
- 변경:
  - `static/styles.css`: `.template-favorite-filter` 상태별 아이콘/색/배경 스타일 강화.
  - `templates/index.html`: 정적 캐시 버전 `20260603-v3-10`으로 갱신.
- 백업: `backups/before-favorite-filter-visual-20260603-111144`
