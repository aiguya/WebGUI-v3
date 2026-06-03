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

### 템플릿 미리보기 컷 포커스 이동

- 목표: 적용 미리보기에서 컷을 클릭하면 해당 컷 편집 카드로 바로 이동할 수 있게 한다.
- 결정:
  - 미리보기 컷 카드를 클릭/키보드 접근 가능한 항목으로 만들고, 편집 카드로 부드럽게 스크롤한다.
  - 이동한 편집 카드는 짧게 강조 표시하고 컷 이름 입력창에 포커스를 둔다.
- 변경:
  - `static/app.js`: 미리보기 컷 인덱스, 클릭/키보드 이벤트, `focusTemplateShot` 추가.
  - `static/styles.css`: 미리보기 hover/focus 스타일과 편집 컷 강조 스타일 추가.
  - `templates/index.html`: 정적 캐시 버전 `20260603-v3-11`로 갱신.
- 백업: `backups/before-template-preview-focus-20260603-111732`

### 즐겨찾기 버튼 아이콘화

- 목표: 즐겨찾기 버튼의 외곽 박스를 제거하고 별 아이콘 자체가 버튼처럼 동작하게 한다.
- 결정:
  - 텍스트 별 대신 CSS SVG 마스크 아이콘을 사용한다.
  - 비활성은 빈 별 아이콘, 활성은 노란 채운 별 아이콘으로 표시한다.
- 변경:
  - `static/styles.css`: `.favorite-button`, `.template-favorite-filter`를 아이콘 전용 버튼 스타일로 변경.
  - `templates/index.html`: 정적 캐시 버전 `20260603-v3-12`로 갱신.
- 백업: `backups/before-favorite-icon-buttons-20260603-114230`

### 즐겨찾기 아이콘 최종 오버라이드

- 목표: 일부 화면에서 즐겨찾기 버튼이 회색 둥근 버튼처럼 보이는 문제를 제거한다.
- 결정: CSS 마지막에 즐겨찾기 전용 최종 오버라이드를 추가해 일반 버튼 스타일이 덮지 못하게 한다.
- 변경:
  - `static/styles.css`: `button.favorite-button`, `button.template-favorite-filter` 최종 오버라이드 추가.
  - `templates/index.html`: 정적 캐시 버전 `20260603-v3-13`으로 갱신.
- 백업: `backups/before-favorite-icon-final-override-20260603-115309`

### 즐겨찾기 버튼 텍스트/캐시 제거

- 목표: 즐겨찾기 버튼이 여전히 회색 둥근 버튼처럼 보이는 문제를 완전히 제거한다.
- 원인: 버튼 내부의 실제 `★` 텍스트와 오래된 서비스워커 셸 캐시가 남아 있었다.
- 변경:
  - `static/app.js`, `templates/index.html`: 즐겨찾기 버튼 내부 텍스트 제거.
  - `static/styles.css`: 기본 버튼 appearance 제거와 텍스트 숨김 최종 오버라이드 보강.
  - `static/service-worker.js`: 캐시 이름과 셸 자산 버전을 `v3-14`로 갱신.
  - `templates/index.html`: 정적 캐시 버전 `20260603-v3-14`로 갱신.
- 백업: `backups/before-favorite-icon-text-cache-20260603-120158`

### 즐겨찾기 아이콘 캐시 갱신 보강

- 목표: 완전 재실행 후에도 즐겨찾기 별 아이콘이 회색 버튼처럼 보이는 오래된 화면 캐시 문제를 줄인다.
- 원인 판단: Chrome 앱 모드/서비스워커가 이전 HTML, CSS, JS 묶음이나 `/sw.js` 응답을 계속 사용할 수 있었다.
- 변경:
  - `app.py`: `/`, `/settings`, `/sw.js` 응답에 `Cache-Control: no-store`를 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`: 정적 버전과 셸 캐시를 `20260603-v3-16` / `webgui-shell-v3-16`으로 갱신.
  - `static/app.js`: 앱 로드 시 오래된 `webgui-shell-*` 캐시를 삭제하고 서비스워커를 `updateViaCache: "none"`으로 등록.
  - `static/styles.css`: 일반 버튼 규칙보다 높은 우선순위로 즐겨찾기 별 아이콘 전용 배경/색상 오버라이드를 추가.
  - `run_webgork_app.bat`: Chrome 앱 실행 URL에 버전 쿼리를 붙여 오래된 앱 창 재사용 가능성을 낮춤.
- 백업: `backups/before-favorite-cache-hardening-20260603-121225`

### 템플릿 컷 블록 드래그 정렬

- 목표: 영상 템플릿 편집 화면에서 컷 블록 순서를 마우스 드래그로 바꿀 수 있게 한다.
- 결정:
  - 입력창 텍스트 선택을 방해하지 않도록 컷 카드 전체가 아니라 헤더의 전용 순서 이동 핸들만 드래그 대상으로 둔다.
  - 기존 위/아래 버튼은 유지해 키보드/클릭 기반 순서 변경도 계속 가능하게 한다.
- 변경:
  - `static/app.js`: 컷 헤더 드래그 핸들, 드래그 중 DOM 재정렬, 드롭 후 컷 번호와 적용 미리보기 갱신 로직 추가.
  - `static/styles.css`: 드래그 핸들, 드롭 활성 영역, 드래그 중 컷 카드 상태 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-17` / `webgui-shell-v3-17`로 갱신.
- 백업: `backups/before-template-shot-dnd-20260603-122957`
