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

### 템플릿 컷 드래그 애니메이션과 자동 스크롤

- 목표: 컷 블록 드래그 정렬이 더 자연스럽게 움직이고, 긴 템플릿에서 위/아래 끝으로 끌 때 자동 스크롤되게 한다.
- 결정:
  - DOM 재정렬 직전에 카드 위치를 저장하고 재정렬 후 이동 차이를 짧게 애니메이션하는 FLIP 방식을 사용한다.
  - 드래그 포인터가 템플릿 편집 스크롤 영역의 위/아래 가장자리에 가까워지면 자동 스크롤한다.
- 변경:
  - `static/app.js`: 컷 카드 위치 애니메이션 헬퍼, 드래그 자동 스크롤 루프, 드롭/드래그 종료 시 상태 정리 추가.
  - `static/styles.css`: 드래그 중 카드 축소/투명도, 드롭 영역, 자동 스크롤 방향 힌트 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-18` / `webgui-shell-v3-18`로 갱신.
- 백업: `backups/before-template-dnd-motion-scroll-20260603-123825`

### 적용 미리보기 컷 드래그 정렬

- 목표: 적용 미리보기 패널에서도 컷 카드를 드래그해 순서를 바꿀 수 있게 하고, 변경된 순서를 실제 템플릿 컷 블록에 반영한다.
- 결정:
  - 미리보기 카드 전체가 아니라 카드 헤더의 전용 `↕` 핸들을 드래그 대상으로 둬서 기존 클릭 시 편집 위치 이동 동작과 충돌하지 않게 한다.
  - 미리보기에서 순서를 바꾸면 가운데 컷 블록 목록도 같은 순서로 다시 렌더링한다.
- 변경:
  - `static/app.js`: 미리보기 카드 드래그 핸들, 미리보기 순서 수집, 실제 컷 블록 재정렬, 드래그 애니메이션/자동 스크롤 연결 추가.
  - `static/styles.css`: 미리보기 드래그 핸들, 드래그 중 카드 상태, 드롭 영역/자동 스크롤 힌트 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-19` / `webgui-shell-v3-19`로 갱신.
- 백업: `backups/before-template-preview-dnd-20260603-124718`

### Grok 이미지 remote_url 우선 재사용

- 목표: Grok/xAI 이미지 생성·편집 결과가 보유한 `https://imgen.x.ai/...` 실제 이미지 URL을 라이브러리 재사용 시 우선 입력으로 보내도록 한다.
- 결정:
  - 공개 `remote_url`이 metadata `extra.remote_url`에 있으면 이미지 편집, 이미지->영상, reference-to-video 요청에서 data URI 대신 URL을 먼저 사용한다.
  - 텍스트->이미지 생성은 xAI가 URL을 반환할 수 있도록 `response_format=b64_json` 강제 지정을 제거한다.
  - 로컬 업로드나 stitched reference처럼 remote URL이 없는 입력은 기존 data URI 방식을 유지한다.
- 변경:
  - `app.py`: metadata에서 remote URL을 찾는 helper와 xAI 이미지 입력 payload helper 추가.
  - `app.py`: `live_image`, batch image edit helpers, `live_video`, `live_video_from_reference_images`가 remote URL을 우선 사용하도록 변경.
  - `app.py`: 결과 metadata extra에 `input_remote_urls`, `input_image_mode`, `used_remote_reference_images` 등 추적값 추가.
- 검증:
  - `python -m py_compile app.py` 통과.
  - 가짜 `requests` payload 테스트로 이미지 편집, 이미지 생성, 이미지->영상, reference-to-video payload 확인.
  - `git diff --check` 통과.
- 백업: `backups/before-remote-url-input-20260603-144117`

### 템플릿 순차 실행기 1차

- 목표: 저장된 영상 템플릿을 단순 미리보기에서 끝내지 않고, 변수와 레퍼런스 슬롯을 채워 실제 작업 큐에 등록할 수 있게 한다.
- 결정:
  - 서버 생성 API는 바꾸지 않고 프론트 큐에 `template-run` 특수 작업을 추가한다.
  - 템플릿 작업은 큐 카드 하나로 표시하되 내부 컷은 순차 실행한다.
  - 컷 결과가 이미지면 다음 이미지 편집/이미지->영상 컷의 입력으로, 영상이면 공식/프레임 연장 컷의 입력으로 이어받는다.
  - 슬롯 레퍼런스는 이번 실행 상태로만 저장하고 템플릿 원본 JSON은 바꾸지 않는다.
- 변경:
  - `templates/index.html`: 템플릿 오른쪽 패널에 실행 준비 카드, 변수 입력, 슬롯 선택, 실행 계획 복사, 큐 등록 버튼 추가.
  - `static/app.js`: 템플릿 런타임 상태, 라이브러리 슬롯 선택, 실행 계획 생성, 순차 실행 큐 작업, 결과 보기 fallback 추가.
  - `static/styles.css`: 실행 준비 카드, 변수 입력, 슬롯 미리보기/버튼 스타일 추가.
  - `templates/index.html`, `static/app.js`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-20` / `webgui-shell-v3-20`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - Flask test client로 `/`, `/api/video-templates`, `/api/video-template-blocks` 확인.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-20`에서 새 HTML/JS 반영 확인.
  - headless Chrome 스크린샷 생성 확인. 단, Chrome crashpad 경고가 출력되어 스크린샷은 임시 검증 후 삭제.
- 백업: `backups/before-template-runner-20260603-150131`

### 템플릿 슬롯 미디어 타입 검증
- 목표: 템플릿 실행 중 공식 연장/프레임 연장 컷에서 이미지 슬롯이 영상 입력으로 전달되어 "선택한 파일은 영상이 아닙니다." 오류가 나는 문제를 막는다.
- 원인:
  - 템플릿 슬롯 조회가 지정한 슬롯 이름을 우선 반환하면서 이미지/영상 타입을 먼저 확인하지 않았다.
  - 그 결과 영상 레퍼런스가 필요한 컷에서 이미지 슬롯 경로가 `library_video_path`로 전달될 수 있었다.
- 변경:
  - `static/app.js`: `templateSlotMatchesKind`를 추가하고, `templateSlotEntry`가 슬롯 타입을 확인한 뒤 반환하도록 수정.
  - `static/app.js`: 영상 레퍼런스가 없을 때 서버 호출 전에 "앞 컷에서 영상을 생성하거나 영상 슬롯을 연결"하라는 명확한 오류를 표시하도록 변경.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-21` / `webgui-shell-v3-21`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-21`에서 새 HTML/JS 반영 확인.
- 백업: `backups/before-template-slot-type-check-20260603-153620`

### 템플릿 수동 확인·재시도 모드
- 목표: 템플릿 실행을 완전 자동으로만 넘기지 않고, 컷마다 결과를 확인한 뒤 다음 컷으로 진행하거나 같은 컷을 재시도할 수 있게 한다.
- 결정:
  - 기존 서버 생성 API는 바꾸지 않고 프론트 큐의 `template-run` 작업 상태에 `review` 단계를 추가한다.
  - 실행 준비 패널에서 `자동`/`수동 확인` 모드를 선택한다.
  - 수동 확인 모드에서는 컷 결과를 받은 뒤 큐 카드가 `확인 대기` 상태가 되고, `다음 컷`/`재시도`/`중단` 버튼을 표시한다.
  - 재시도 시 해당 컷 이전의 이미지/영상 전달 상태로 되돌려 다시 요청하고, 큐 카드에는 최신 시도 결과만 이어받는다.
- 변경:
  - `templates/index.html`: 템플릿 실행 준비 영역에 실행 모드 선택 UI 추가.
  - `static/app.js`: 템플릿 실행 모드 상태, `review` 큐 상태, 컷별 확인 대기 Promise, 다음 컷/재시도/중단 액션 처리 추가.
  - `static/styles.css`: 확인 대기 큐 카드 강조와 수동 모드 선택 UI 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-22` / `webgui-shell-v3-22`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-22`에서 새 HTML/JS 반영 확인.
- 백업: `backups/before-template-manual-review-20260603-160000`

### 템플릿 컷 박스 방식별 UI 전환
- 목표: 컷 블록 박스에서 생성 방식을 선택하면 해당 방식에 필요한 입력만 보이도록 한다.
- 결정:
  - `이미지 생성`: 프롬프트, 재시도 프롬프트, 메모만 표시한다.
  - `이미지 편집`: 이미지 슬롯, 프롬프트, 재시도 프롬프트, 메모를 표시하고 길이/전환/카메라는 숨긴다.
  - `이미지→영상`, `공식 연장`, `프레임 연장`: 길이, 참조 슬롯, 전환, 프롬프트, 카메라, 재시도 프롬프트, 메모를 표시한다.
  - 숨겨진 값은 삭제하지 않고 유지해서 방식을 다시 바꿔도 기존 입력을 잃지 않게 한다.
- 변경:
  - `static/app.js`: 방식별 필드 표시 규칙, 컷 박스 안내문, 참조 슬롯 라벨/placeholder 자동 변경, 방식 변경 이벤트 처리 추가.
  - `static/styles.css`: 컷 방식 안내문과 필드 래퍼 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-23` / `webgui-shell-v3-23`으로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-23`에서 새 HTML/JS 반영 확인.
- 백업: `backups/before-template-method-aware-shot-box-20260603-161500`

### 이미지 편집 컷 다중 레퍼런스 슬롯
- 목표: 템플릿 `이미지 편집` 컷에서 레퍼런스 슬롯을 1개만 받던 문제를 수정하고, 실제 이미지 편집 기능처럼 1~3개의 이미지 슬롯을 참조할 수 있게 한다.
- 결정:
  - 기존 `reference_slot`은 첫 번째 메인 슬롯으로 유지하고, 새 `reference_slots` 배열에 최대 3개 슬롯을 저장한다.
  - 기존 템플릿/블록은 `reference_slot` 하나만 있어도 자동으로 첫 번째 슬롯으로 변환한다.
  - 템플릿 실행 시 `이미지 편집` 컷은 선택된 이미지 슬롯을 최대 3개까지 `/api/i2i`의 `library_image_paths`로 전달하고 `edit_input_mode=multi`를 사용한다.
  - 다중 슬롯은 지정된 슬롯만 정확히 사용하며, 아무 슬롯도 연결되지 않았을 때만 직전 이미지 결과를 fallback으로 사용한다.
- 변경:
  - `app.py`: 템플릿 컷/블록 정규화에 `reference_slots` 저장과 하위호환 변환 추가.
  - `static/app.js`: 이미지 편집 컷 박스에 `이미지 슬롯 1~3` UI 추가, 저장/블록 보관/실행 계획/실행 요청의 다중 슬롯 처리 추가.
  - `static/styles.css`: 다중 슬롯 입력 그리드 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-24` / `webgui-shell-v3-24`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `normalize_video_template`, `normalize_template_block`에서 `reference_slots` 3개 보존 확인.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-24`에서 새 HTML/JS/CSS 반영 확인.
- 백업: `backups/before-template-edit-reference-slots-20260603-163000`

### 템플릿 컷 요청 모델 선택
- 목표: 템플릿의 `이미지 생성`, `이미지 편집`, `이미지→영상`, `공식 연장`, `프레임 연장` 컷에서도 실제 기능 탭처럼 요청 모델을 선택하고 저장/실행할 수 있게 한다.
- 결정:
  - 이미지 생성/이미지 편집 컷은 기존 이미지 편집 폼과 같은 `Grok 이미지 퀄리티`, `Grok 이미지 기본`, `Codex/ChatGPT` 이미지 모델 선택지를 사용한다.
  - 이미지→영상/프레임 연장 컷은 `Grok 영상`, `Grok 영상 1.5 preview` 선택지를 사용한다.
  - 공식 연장은 preview 모델이 연장을 지원하지 않으므로 `Grok 영상`만 선택지로 둔다.
  - 선택한 모델은 템플릿 JSON과 블록 JSON에 저장하고, 템플릿 실행 시 각 API 요청의 `image_model` 또는 `video_model`로 전달한다.
- 변경:
  - `app.py`: 템플릿 컷/블록 정규화에 `image_model`, `video_model` 저장 추가.
  - `static/app.js`: 방식별 모델 필드 표시, 모델 선택 UI, 저장/블록 보관/실행 계획/실행 요청 전달 처리 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-25` / `webgui-shell-v3-25`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `normalize_video_template`, `normalize_template_block`에서 `image_model`, `video_model` 보존 확인.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-25`에서 새 HTML/JS 반영 확인.
- 백업: `backups/before-template-shot-model-select-20260603-164500`

### 템플릿 이미지 결과 슬롯 등록
- 목표: 템플릿의 `이미지 생성`, `이미지 편집` 컷 결과물을 배우/레퍼런스 이미지 슬롯에 다시 등록해서 뒤쪽 컷이 해당 결과물을 참조할 수 있게 한다.
- 결정:
  - 컷 카드에 `결과 저장 슬롯` 입력을 추가하고, 이미지 생성/이미지 편집 방식에서만 표시한다.
  - 결과 저장 슬롯은 템플릿 JSON과 블록 JSON에 `output_slot`으로 저장한다.
  - 자동 실행에서는 컷 성공 직후 슬롯에 등록하고, 수동 확인 모드에서는 사용자가 결과를 확정한 뒤에만 등록한다.
  - retry를 선택한 경우 잘못 생성된 결과는 슬롯에 등록하지 않는다.
- 변경:
  - `app.py`: 템플릿 컷/블록 정규화에 `output_slot` 저장 추가.
  - `static/app.js`: 결과 저장 슬롯 UI, 저장/블록 보관/실행 계획 표시, 실행 중 슬롯 등록 로직 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-26` / `webgui-shell-v3-26`으로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `normalize_video_template`, `normalize_template_block`에서 `output_slot` 보존 확인.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-26`에서 새 HTML/JS 반영 확인.
- 백업: `backups/before-template-result-slot-output-20260603-213000`

### 이미지 편집 입력 로컬 파일 강제
- 목표: 이미지 편집 탭에서 라이브러리 이미지의 `remote_url` 메타데이터를 우선 사용하다가 만료된 `imgen.x.ai` URL 404로 실패하는 문제를 막는다.
- 원인:
  - 라이브러리 결과 이미지에 `remote_url`이 남아 있으면 `image_input_object()`가 로컬 파일 대신 원격 URL을 API 입력으로 전달했다.
  - 해당 원격 URL이 만료되거나 삭제되면 xAI 이미지 편집 API가 `Fetching image failed with HTTP status 404 Not Found`를 반환했다.
- 결정:
  - `remote_url` 메타데이터 저장 자체는 유지한다.
  - 이미지 편집 계열 요청에서는 원격 URL을 사용하지 않고 실제 로컬 파일을 base64 data URI로 전송한다.
  - 영상 생성/참조 이미지 기반 영상 쪽의 원격 URL 재사용은 기존처럼 유지한다.
- 변경:
  - `app.py`: `image_input_url`, `image_input_object`에 `allow_remote` 옵션 추가.
  - `app.py`: xAI 이미지 편집 경로인 `live_image`, `edit_image_with_config`, `edit_image_sources_with_config`에서 `allow_remote=False` 적용.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `remote_url_for_media_path`를 mock 처리한 상태에서 `allow_remote=False`가 원격 URL 대신 `data:image/...`를 반환하는지 확인.
  - v3 서버 재시작 후 `/health` 응답 `200 ok` 확인.
- 백업: `backups/before-i2i-force-local-inputs-20260603-222500`

### 템플릿 수동 확인/오류 진행 표시 보강
- 목표: 템플릿 실행 중 수동 확인 대기 상태가 중앙 진행 패널에서 계속 처리 중처럼 보여 멈춘 것처럼 보이는 문제를 줄인다.
- 원인:
  - 수동 확인 모드에서는 1컷 완료 후 큐 카드의 `다음 컷`/`재시도`/`중단` 선택을 기다리지만, 중앙 진행 패널은 `1/5 처리 완료`만 표시했다.
  - 템플릿 큐 등록 시 내부 상태값을 기준으로 모드를 저장해, 드롭다운 표시와 내부 상태가 엇갈릴 여지가 있었다.
- 결정:
  - 템플릿 큐 등록 버튼을 누르는 순간 `실행 모드` 드롭다운의 실제 값을 다시 읽어 저장한다.
  - 수동 확인 대기 시 중앙 진행 패널에 `확인 대기` 안내를 표시한다.
  - 오류 발생 시 중앙 진행 패널에 오류 메시지를 짧게 표시한 뒤 닫는다.
- 변경:
  - `static/app.js`: `selectedTemplateRunMode`, 진행 패널 `message()` 상태 메서드, 수동 확인/오류 메시지 연결 추가.
  - `static/styles.css`: 진행 패널 확인 대기/오류 색상 상태 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-27` / `webgui-shell-v3-27`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `git diff --check` 통과.
  - v3 서버 재시작 후 `http://127.0.0.1:7863/?v=20260603-v3-27`에서 새 HTML/JS/CSS 반영 확인.
- 백업: `backups/before-template-run-mode-status-20260603-225500`

### 템플릿 실행 슬롯/모드 저장과 확인 조작 UI
- 목표: 템플릿 저장 후 실행 준비에 연결한 레퍼런스 이미지가 사라지고, 수동/자동 실행 모드가 저장되지 않으며, 수동 확인 버튼이 보이지 않는 문제를 고친다.
- 원인:
  - `saveTemplateEditor()`가 저장 후 `setTemplateEditorItem()`을 다시 호출하면서 `resetTemplateRunState()`가 `templateRunState.slots`와 모드를 초기화했다.
  - 템플릿 JSON의 슬롯 정의에는 선택한 라이브러리 파일 경로와 실행 모드가 저장되지 않았다.
  - 큐 카드의 액션 버튼을 숨기는 CSS 규칙 때문에 확인 대기 상태에서도 `다음 컷`/`재시도`/`중단` 버튼이 보이지 않을 수 있었다.
- 결정:
  - 템플릿 슬롯에 `selected_path`, `selected_kind`, `selected_label`을 저장한다.
  - 템플릿 설정에 `run_mode`를 저장한다.
  - 템플릿 로드/저장 직후 실행 준비 상태를 저장된 슬롯과 모드로 복원한다.
  - 수동 확인 조작은 큐 카드뿐 아니라 중앙 진행 패널에서도 바로 누를 수 있게 한다.
- 변경:
  - `app.py`: 템플릿 슬롯 선택값과 `settings.run_mode` 정규화/저장 추가.
  - `static/app.js`: 저장 payload에 현재 슬롯 선택과 실행 모드 포함, 로드 시 복원, 중앙 진행 패널 액션 버튼 추가.
  - `static/styles.css`: 중앙 진행 패널 액션 버튼 및 확인 대기 큐 액션 버튼 표시 override 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260603-v3-28` / `webgui-shell-v3-28`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `normalize_video_template`에서 `run_mode`, `selected_path`, `selected_kind`, `selected_label` 보존 확인.
- 백업: `backups/before-template-slot-selection-persist-20260603-232500`

### 템플릿 슬롯 저장/수동 확인 UI 추가 검증
- 확인 시각: 2026-06-03 23:40 KST 전후.
- 추가 확인:
  - 기존 `v3-27` 서버가 살아 있어 HTML만 이전 버전을 내보내던 상태를 확인하고, 해당 서버 프로세스를 종료한 뒤 v3 서버를 재시작했다.
  - `http://127.0.0.1:7863/?v=20260603-v3-28` HTML이 `20260603-v3-28` 정적 파일을 참조하는 것을 확인했다.
  - `/static/app.js?v=20260603-v3-28`에 슬롯 선택 저장(`selected_path`)과 중앙 진행 패널 조작 UI(`progress-actions`)가 포함된 것을 확인했다.
  - `/static/styles.css?v=20260603-v3-28`에 수동 확인 대기 상태 버튼 표시 override가 포함된 것을 확인했다.

### 템플릿 수동 확인 중 결과 미리보기 안전 처리
- 목표: 템플릿 수동 확인 대기 중 큐 썸네일로 결과물을 확인한 뒤 모달을 닫을 때 템플릿이 중단되는 문제를 막는다.
- 원인:
  - 큐 카드 내부에서 결과 보기 버튼과 수동 확인 결정 버튼이 같은 위임 클릭 핸들러를 공유했다.
  - 수동 확인의 `중단` 버튼이 일반 큐 취소 버튼과 같은 `data-cancel-job` 속성을 사용해, 모달 닫힘 직후 클릭이 뒤쪽 버튼으로 새면 바로 템플릿 `cancel`로 이어질 수 있었다.
- 결정:
  - 수동 확인의 중단 버튼을 `data-template-review-cancel`로 분리한다.
  - 큐 결과 미리보기 모달은 `queue-preview` 컨텍스트로 열고, 닫힌 직후 짧은 시간 동안 큐 취소/중단 입력을 무시한다.
  - 큐 결과 보기 클릭은 `preventDefault()`와 `stopPropagation()`으로 다른 큐 액션과 완전히 분리한다.
- 변경:
  - `static/app.js`: 미디어 뷰어 컨텍스트 추적, 큐 결과 보기 우선 처리, review cancel 분리, 모달 닫힘 직후 중단 입력 guard 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-29` / `webgui-shell-v3-29`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `20260603-v3-28` 잔여 참조 없음 확인.
- 백업: `backups/before-template-review-modal-safe-20260604-000500`

### 템플릿 수동 확인 팝업 내 결과 미리보기
- 목표: 템플릿 수동 확인 중 왼쪽 큐를 누르지 않아도 중앙 확인 팝업에서 현재 컷 결과물을 바로 확인할 수 있게 한다.
- 원인:
  - 수동 확인 단계에서 결과 확인을 왼쪽 큐 썸네일에 의존하면 큐 카드의 상태/결정 이벤트와 섞일 여지가 있었다.
  - 사용자는 수동 확인 팝업에서 이미 `다음 컷`/`재시도`/`중단`을 결정하므로 결과 확인도 같은 팝업 안에서 처리하는 편이 더 직관적이다.
- 결정:
  - 중앙 진행 팝업에 `현재 컷 결과` 미리보기 영역을 추가한다.
  - 현재 컷에서 생성된 결과만 팝업에 표시하고, 썸네일을 누르면 큰 미디어 뷰어로 확인할 수 있게 한다.
  - 수동 확인 상태의 왼쪽 큐 카드는 결정 버튼을 표시하지 않고 `팝업에서 선택` 안내만 보여준다.
- 변경:
  - `static/app.js`: `createProgress()`에 미디어 미리보기 렌더링 추가, 템플릿 review에 `previewItems` 전달, review 상태 큐 카드 read-only화.
  - `static/styles.css`: 팝업 미디어 그리드와 큐 안내 문구 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-30` / `webgui-shell-v3-30`으로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `git diff --check` 통과.
  - `20260604-v3-29` 잔여 참조 없음 확인.
- 백업: `backups/before-template-review-inline-preview-20260604-002000`

### 템플릿 요청 연결 실패 복구
- 목표: 템플릿 컷 요청 중 브라우저 `fetch()` 연결이 끊겼을 때 `Failed to fetch`만 표시하고 템플릿 전체가 실패 종료되는 문제를 줄인다.
- 원인:
  - `fetchTemplateShot()`이 브라우저 네트워크 예외를 그대로 바깥으로 던져, 요청 실패가 즉시 템플릿 실패 상태로 처리됐다.
  - `Failed to fetch`는 서버가 오류 본문을 돌려준 것이 아니라 브라우저가 응답 자체를 받지 못한 상황이라 원인 파악이 어려웠다.
- 결정:
  - `Failed to fetch` 계열 오류를 “로컬 WebGUI 서버 응답을 받지 못함”이라는 설명 메시지로 변환한다.
  - 템플릿 컷 요청 실패 시 중앙 팝업에서 `재시도` 또는 `중단`을 선택하게 하며, 자동 모드에서도 바로 실패 종료하지 않는다.
  - 일반 큐 작업도 fetch 단절 시 같은 설명 메시지를 표시한다.
- 변경:
  - `static/app.js`: `friendlyFetchError()` 추가, `fetchTemplateShot()` 네트워크/JSON 응답 오류 처리 보강, `waitForTemplateRetry()` 추가, 템플릿 실행 루프에 재시도 대기 분기 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-31` / `webgui-shell-v3-31`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `20260604-v3-30` 잔여 참조 없음 확인.
- 백업: `backups/before-template-fetch-retry-review-20260604-004500`

### 템플릿 참조 슬롯 해석 보정
- 목표: 템플릿 이미지/영상 단계에서 프롬프트가 슬롯 문구로 꼬이거나, 명시한 참조 슬롯 대신 다른 슬롯/이전 결과가 사용되는 문제를 줄인다.
- 원인:
  - 이미지 생성 블록은 참조 슬롯을 프롬프트 텍스트에는 넣을 수 있었지만 실제 이미지 파일을 API에 첨부하지 않았다.
  - 명시 참조 슬롯이 비어 있어도 `templateSlotEntry()`가 첫 번째 같은 종류 슬롯으로 fallback할 수 있어, 의도와 다른 이미지/영상이 참조될 수 있었다.
  - 실제 API 전송 프롬프트에 `참조 슬롯: [슬롯명]` 같은 내부 UI 문구가 함께 들어가 프롬프트가 불필요하게 섞였다.
- 결정:
  - `이미지 생성` 블록도 1~3개 이미지 참조 슬롯을 선택할 수 있게 한다.
  - 이미지 생성 블록에 참조 슬롯이 있으면 `/api/t2i`가 아니라 `/api/i2i`로 보내 실제 참조 이미지를 첨부한다.
  - 명시 참조 슬롯은 정확히 해당 슬롯만 사용하고, 비어 있으면 다른 슬롯으로 대체하지 않는다.
  - 실제 API 프롬프트에서는 내부 `참조 슬롯` 문구를 제거하되, 미리보기/계획 표시에는 유지한다.
- 변경:
  - `static/app.js`: 이미지 생성 블록 참조 UI 활성화, `image` 블록 참조 기반 `/api/i2i` 라우팅, 명시 참조 슬롯 strict lookup, 누락 슬롯 오류 메시지, 실행 프롬프트의 참조 슬롯 문구 제거.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-32` / `webgui-shell-v3-32`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `20260604-v3-31` 잔여 참조 없음 확인.
- 백업: `backups/before-template-reference-resolution-20260604-010500`

### 템플릿 이미지 생성 순수화와 최종 영상 병합
- 목표: 이미지 생성 블록에 레퍼런스 이미지가 자동으로 섞이는 문제를 막고, 템플릿 실행 완료 후 생성된 영상 클립을 조건에 맞춰 최종 결과물로 병합한다.
- 원인:
  - `image` 블록이 참조 슬롯을 받을 수 있도록 바뀌면서, 숨겨진 슬롯 값이나 이전 상태가 있으면 `/api/t2i` 대신 `/api/i2i`로 우회할 수 있었다.
  - 템플릿 실행 루프는 각 블록 결과만 누적하고, 전체 완료 후 영상 클립을 하나의 결과물로 묶는 단계가 없었다.
- 변경:
  - `static/app.js`: `image` 템플릿 블록은 참조 슬롯 UI를 숨기고, 수집 단계에서도 `reference_slot/reference_slots`를 빈 값으로 강제한다.
  - `static/app.js`: 이미지 생성 요청은 항상 `/api/t2i`만 사용하도록 되돌렸다. 참조 기반 이미지는 `이미지 편집` 블록에서만 처리한다.
  - `static/app.js`: 템플릿 완료 후 생성된 영상이 2개 이상이면 `/api/video-edit`로 최종 병합한다. 전환 설정은 `crossfade/fade/fade_in/fade_out` 값을 반영하고 오디오는 보존한다.
  - `app.py`: 템플릿 최종 병합을 위해 영상 편집 입력 한도를 12개에서 80개로 늘렸다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-33` / `webgui-shell-v3-33`으로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - 로컬 서버 캐시 버전 확인 예정.
- 백업: `backups/before-template-image-pure-final-merge-20260604-012001`

### 이미지→영상 기본 모델 추가 참조 UI 정리
- 목표: Grok 기본 영상 모델에서 첫 이미지를 시작 레퍼런스로 쓰고, 추가 이미지를 참조 이미지로 함께 보내는 동작을 UI에서 명확히 보이게 한다.
- 확인:
  - `/api/i2v` 백엔드는 이미 기본 모델에서 최대 3장까지 받아 `reference_images` 방식으로 전송한다.
  - `grok-imagine-video-1.5-preview`는 기존처럼 1장만 남기도록 제한한다.
- 변경:
  - `templates/index.html`: 이미지→영상 입력 라벨과 안내 문구를 `시작 레퍼런스 이미지 / 추가 참조` 기준으로 변경.
  - `static/app.js`: 이미지→영상 썸네일에서 첫 장은 `시작`, 추가 이미지는 `참조 1`, `참조 2`로 표시한다.
  - `static/app.js`: 모델 선택에 따라 안내 문구를 갱신하고, 1.5 preview 선택 시 추가 참조를 자동 제거한다.
  - `static/styles.css`: 참조 역할 배지가 깨지지 않도록 `source-role` 스타일 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-34` / `webgui-shell-v3-34`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-34` 및 `/static/app.js?v=20260604-v3-34` 서빙 확인.
- 백업: `backups/before-i2v-extra-reference-ui-20260604-012846`

### 템플릿 이미지→영상 기본 모델 추가 참조 슬롯
- 목표: 템플릿의 `이미지→영상` 블록에서 Grok 기본 영상 모델을 선택하면 시작 이미지 슬롯 외에 추가 참조 이미지 슬롯 2개를 더 지정할 수 있게 한다.
- 원인:
  - 일반 이미지→영상 탭은 여러 이미지를 전송할 수 있었지만, 템플릿 블록 UI와 실행 요청은 단일 `reference_slot`만 수집하고 `/api/i2v`에도 한 장만 전달했다.
- 변경:
  - `static/app.js`: 템플릿 `이미지→영상` 블록이 Grok 기본 모델일 때 `시작 슬롯 + 추가 참조 2개` UI를 표시한다.
  - `static/app.js`: Grok 기본 모델의 템플릿 i2v 실행 요청은 최대 3개의 이미지 슬롯을 `/api/i2v`에 전달한다.
  - `static/app.js`: `grok-imagine-video-1.5-preview` 선택 시에는 기존처럼 첫 번째 슬롯 1개만 사용하고 추가 슬롯은 비운다.
  - `static/app.js`: 영상 모델 셀렉트 변경 시 템플릿 블록 UI가 즉시 단일/다중 참조 모드로 전환되게 했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-35` / `webgui-shell-v3-35`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-35` 및 `/static/app.js?v=20260604-v3-35` 서빙 확인.
- 백업: `backups/before-template-i2v-extra-slots-20260604-015222`

### 템플릿 공식 연장 최종 조립 중복 방지와 실행 콘솔
- 목표: 템플릿에서 `공식 연장` 결과가 이미 원본 영상을 포함하는데도 최종 병합에서 원본 영상을 다시 붙여 중복 재생되는 문제를 막고, 템플릿 실행 중 서버 통신/진행 상태를 볼 수 있는 콘솔을 제공한다.
- 원인:
  - 최종 병합 단계가 전체 결과 `items`에서 영상만 단순 추출해 병합했다.
  - `공식 연장`과 `프레임 연장` 결과는 원본+연장 결과인데, 이전 원본 영상과 함께 다시 병합되어 `원본 → 원본+연장` 형태가 되었다.
- 변경:
  - `static/app.js`: 템플릿 실행 중 별도의 최종 조립 영상 목록을 유지한다.
  - `static/app.js`: `공식 연장`/`프레임 연장` 결과가 나오면 직전 조립 클립을 새 결과로 교체해 원본 중복 병합을 방지한다.
  - `static/app.js`: 요청 시작, 응답 수신, 실패, 재시도, 조립 목록 추가/교체, 최종 병합 로그를 템플릿 실행 콘솔에 기록한다.
  - `templates/index.html`: 템플릿 실행 패널에 `실행 콘솔` 로그 영역을 추가했다.
  - `static/styles.css`: 실행 콘솔을 작은 터미널 스타일로 표시하도록 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-36` / `webgui-shell-v3-36`으로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-36` 및 `/static/app.js?v=20260604-v3-36` 서빙 확인.
- 백업: `backups/before-template-assembly-console-20260604-111457`

### 템플릿 이미지 생성/편집 전역 프롬프트 제외
- 목표: 템플릿의 `이미지 생성`과 `이미지 편집` 블록에는 전역 프롬프트를 적용하지 않는다.
- 변경:
  - `static/app.js`: `templateShotPromptText()`에서 `image`, `edit` 블록은 `payload.global_prompt`를 제외하고 컷 프롬프트를 조립하도록 변경했다.
  - `static/app.js`: API 요청과 적용 미리보기가 같은 조립 규칙을 사용하므로 실제 요청 프롬프트와 미리보기 모두 전역 프롬프트 제외가 반영된다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 셸 캐시를 `20260604-v3-37` / `webgui-shell-v3-37`로 갱신.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - 이미지 생성/편집 프롬프트 조립에서 전역 프롬프트 제외 로직 확인.
  - `http://127.0.0.1:7863/?v=20260604-v3-37` 및 `/static/app.js?v=20260604-v3-37` 서빙 확인.
- 백업: `backups/before-template-image-edit-no-global-20260604-114954`

### 일반 기능 탭에서 템플릿 블록 저장
- 목표: 템플릿 편집 화면 안에서만 블록을 만들 수 있던 흐름을 확장해, 일반 이미지 생성/편집/이미지→영상/공식 연장/프레임 연장 탭의 현재 설정을 바로 재사용 가능한 템플릿 블록으로 저장할 수 있게 한다.
- 변경:
  - `static/app.js`: 대상 endpoint를 템플릿 블록 방식(`image`, `edit`, `i2v`, `official`, `frame`)으로 매핑하는 설정을 추가했다.
  - `static/app.js`: 일반 폼의 프롬프트, 모델, 길이, 해상도/비율, 업스케일/음소거 등 보조 설정을 템플릿 블록 payload로 변환하는 저장 헬퍼를 추가했다.
  - `static/app.js`: 대상 일반 기능 탭에 `블록 저장` 보조 버튼을 자동 삽입하고 `/api/video-template-blocks`에 저장하도록 연결했다.
  - `static/styles.css`: 블록 저장 버튼을 기존 보조 버튼 톤으로 맞추고 제출 버튼과 간격을 정리했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-38` / `webgui-shell-v3-38`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-38` 및 `/static/app.js?v=20260604-v3-38` 서빙 확인.
  - localhost `/api/video-template-blocks` 저장 후 `/api/video-template-blocks/delete`로 테스트 블록 삭제 확인.
- 백업: `backups/before-form-to-template-block-20260604-125921`

### 템플릿 산출물 라이브러리 분리
- 목표: 템플릿 실행으로 생성된 이미지/영상/최종 병합 결과를 라이브러리의 별도 `템플릿` 분류에서 확인할 수 있게 한다.
- 변경:
  - `static/app.js`: 템플릿 컷 실행 요청과 최종 병합 요청에 `template_result`, 템플릿 ID/제목, 컷 ID/제목/방식, 단계 정보를 함께 전송하도록 추가했다.
  - `app.py`: 생성/편집/이미지→영상/공식 연장/프레임 연장/영상 편집 저장 시 템플릿 요청 메타데이터를 결과물 `extra`에 보존하도록 추가했다.
  - `templates/index.html`: 라이브러리 상단 필터에 `템플릿` 항목을 추가했다.
  - `static/app.js`: 라이브러리 필터에서 템플릿 결과물을 기본 전체 목록에서 분리하고, `템플릿` 필터 선택 시에만 모아 보여주도록 변경했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-39` / `webgui-shell-v3-39`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-39` 및 `/static/app.js?v=20260604-v3-39` 서빙 확인.
  - `template_request_metadata()`가 템플릿 결과 플래그와 컷 방식을 정상 추출하는지 확인.
- 백업: `backups/before-template-library-filter-20260604-131006`

### 템플릿 실행 체크포인트와 중간 블록 재실행
- 목표: 템플릿 실행 중 각 컷의 진행 상태와 결과물을 저장하고, 저장된 실행 기록에서 원하는 컷부터 다시 큐에 넣어 실행할 수 있게 한다.
- 변경:
  - `static/app.js`: 템플릿 실행 세션을 `localStorage`의 `webgork.templateRunSessions.v1`에 저장하도록 추가했다. 세션에는 템플릿 payload, 초기 슬롯 상태, 현재 슬롯 상태, 컷별 상태, 결과물 경로, 최종 조립용 영상 목록이 포함된다.
  - `static/app.js`: 템플릿 컷 요청 시작/실패/확인대기/완료/취소/최종 완료 시점마다 체크포인트가 갱신되도록 `runTemplateJob()`에 저장 지점을 추가했다.
  - `static/app.js`: 저장된 세션의 특정 컷을 선택하면 이전 컷의 결과와 슬롯 상태를 재구성한 뒤 해당 컷부터 다시 큐에 등록하는 재실행 흐름을 추가했다.
  - `templates/index.html`: 템플릿 실행 패널에 `실행 체크포인트` 영역을 추가했다.
  - `static/styles.css`: 체크포인트 카드, 진행 바, 컷별 재실행 버튼 스타일을 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-40` / `webgui-shell-v3-40`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-40` 및 `/static/app.js?v=20260604-v3-40` 서빙 확인.
  - 체크포인트 UI DOM과 `webgork.templateRunSessions.v1` 저장 로직, 특정 컷 재실행 함수가 새 정적 파일에 포함되는지 확인.
- 백업: `backups/before-template-run-checkpoints-20260604-131851`

### 템플릿 작업 상황 패널 노출
- 목표: 템플릿 실행 상태가 접힌 체크포인트 영역에만 숨어 보이지 않던 문제를 해결하고, 실행 중 상황을 우측 패널에서 바로 확인할 수 있게 한다.
- 변경:
  - `templates/index.html`: 템플릿 적용 미리보기 패널 상단에 `templateRunMonitor` 영역을 배치했다.
  - `static/app.js`: 저장된 템플릿 실행 세션을 현재 템플릿 기준으로 필터링하고, 최신 실행 상태/진행률/현재 단계/업데이트 시간을 `작업 상황` 패널에 렌더링하도록 추가했다.
  - `static/app.js`: 작업 상황 패널에서 현재 단계부터 재실행하거나 상세 체크포인트 영역으로 이동할 수 있게 이벤트를 연결했다.
  - `static/styles.css`: 작업 상황 카드, 상태 배지, 진행 바, 현재 단계 요약 스타일을 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-41` / `webgui-shell-v3-41`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-41`에서 작업 상황 패널 DOM과 새 정적 파일 서빙 확인.
  - `/static/app.js?v=20260604-v3-41`에서 `renderTemplateRunMonitor`와 현재 단계 재실행 이벤트가 포함되는지 확인.
- 백업: `backups/before-template-run-visible-monitor-20260604-133911`

### 템플릿 작업 중단 기능
- 목표: 템플릿 실행 중 상황을 확인하는 패널에서 바로 실행을 중단하고, 큐/체크포인트 상태도 함께 중단으로 정리되게 한다.
- 변경:
  - `static/app.js`: 작업 상황 패널에 `작업 중단` 버튼을 추가하고, 현재 템플릿 실행 세션과 연결된 큐 작업을 찾아 `cancelled` 상태로 전환하도록 추가했다.
  - `static/app.js`: 일반 큐 작업과 템플릿 컷 요청에 `AbortController`를 연결해 가능한 경우 진행 중인 브라우저 요청을 중단하도록 했다.
  - `static/app.js`: 템플릿 실행 루프가 중단 상태를 감지하면 다음 컷이나 최종 병합으로 넘어가지 않도록 방어 지점을 추가했다.
  - `static/styles.css`: 작업 상황 패널의 중단 버튼을 작은 위험 톤 버튼으로 표시하도록 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-42` / `webgui-shell-v3-42`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-42`에서 새 HTML과 작업 상황 패널 DOM 서빙 확인.
  - `/static/app.js?v=20260604-v3-42`에서 `cancelTemplateRunSession`, `data-template-monitor-cancel`, `AbortController` 포함 확인.
- 백업: `backups/before-template-run-cancel-20260604-141000`

### 템플릿 실행 플로팅 작업 패널
- 목표: 템플릿 실행 중 진행/수동 확인 UI가 템플릿 실행 준비 패널을 덮어 탭 조작을 막던 문제를 해결하고, 실행 중에도 다른 설정 수정이나 추가 큐 등록을 할 수 있게 한다.
- 변경:
  - `static/app.js`: 템플릿 실행 진행 UI를 `#templateRunner` 내부가 아니라 `body` 하단의 `floatingProgressHost`에 붙이도록 변경했다.
  - `static/app.js`: 기존 `createProgress()` 흐름은 유지해 수동 확인, 재시도, 중단 버튼은 그대로 동작하되 페이지 본문을 막지 않게 했다.
  - `static/styles.css`: 플로팅 작업 패널을 오른쪽 아래에 고정하고, 패널 자체만 클릭을 받도록 스타일을 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-43` / `webgui-shell-v3-43`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-43`에서 새 HTML 서빙 확인.
  - `/static/app.js?v=20260604-v3-43`에서 `templateProgressHost`, `floatingProgressHost`, 새 정적 버전 포함 확인.
  - `/static/styles.css?v=20260604-v3-43`에서 `floating-progress-host` 스타일 포함 확인.
- 백업: `backups/before-template-floating-progress-20260604-143000`

### 템플릿 슬롯 빠른 삽입과 콘솔 확대
- 목표: 템플릿 컷 편집 중 우측 실행 준비 슬롯을 빠르게 참조하고, 작은 실행 콘솔을 큰 팝업으로 확인할 수 있게 한다.
- 변경:
  - `static/app.js`: 템플릿 컷의 참조/프롬프트 입력칸 포커스를 기억하고, 우측 실행 준비 슬롯을 Ctrl/Command+클릭하면 해당 입력칸에 슬롯 참조를 삽입하도록 추가했다.
  - `static/app.js`: 참조 슬롯 입력칸에는 `slot_name` 그대로, 프롬프트/카메라/메모 입력칸에는 `{{slot_name}}` 형태로 삽입하도록 분기했다.
  - `templates/index.html`, `static/app.js`, `static/styles.css`: 실행 콘솔 확대 팝업을 추가하고, 작은 콘솔 로그를 클릭하면 큰 로그 뷰어가 열리도록 연결했다.
  - `static/styles.css`: 우측 실행 준비 슬롯 hover와 콘솔 확대 팝업 스타일을 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-44` / `webgui-shell-v3-44`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-44`에서 새 HTML과 콘솔 뷰어 DOM 서빙 확인.
  - `/static/app.js?v=20260604-v3-44`에서 `insertTemplateSlotReference`, `openTemplateConsoleViewer`, 새 정적 버전 포함 확인.
  - `/static/styles.css?v=20260604-v3-44`에서 `template-console-viewer`, `template-run-slot:hover` 스타일 포함 확인.
- 백업: `backups/before-template-slot-console-final-20260604-145500`

### 템플릿 기존 결과 슬롯 단계 스킵
- 목표: 템플릿 실행 시 컷의 `결과 저장 슬롯`에 이미 파일이 들어 있으면 해당 컷을 다시 생성하지 않고 다음 단계로 넘어가게 한다.
- 변경:
  - `static/app.js`: 컷 실행 전에 `output_slot`이 가리키는 실행 준비 슬롯에 기존 파일 경로가 있는지 확인하는 `templateExistingOutputSlotItem()`을 추가했다.
  - `static/app.js`: 기존 결과 슬롯이 있으면 API 요청을 보내지 않고 해당 파일을 컷 결과로 간주해 체크포인트를 `done`으로 저장하고, 이전 결과/최종 조립 목록/작업 큐 진행률을 갱신하도록 했다.
  - `static/app.js`: 실행 콘솔에 `단계 스킵` 로그를 남겨 어떤 컷이 기존 결과 슬롯 때문에 건너뛰어졌는지 확인할 수 있게 했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-45` / `webgui-shell-v3-45`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-45`에서 새 HTML 정적 버전 서빙 확인.
  - `/static/app.js?v=20260604-v3-45`에서 `templateExistingOutputSlotItem`, `단계 스킵`, 새 정적 버전 포함 확인.
- 백업: `backups/before-template-skip-existing-output-20260604-151500`

### 이미지 생성/편집 해상도 선택 노출
- 목표: 이미지 생성과 이미지 편집 탭에서 `auto / 1k / 2k` 해상도 선택 항목이 화면에 명확히 보이도록 한다.
- 변경:
  - `static/app.js`: `data-grok-resolution-field` 컨트롤을 숨기지 않고 항상 표시하되, Grok 이미지 모델이 아닐 때만 비활성화하고 `auto`로 되돌리도록 변경했다.
  - `templates/index.html`: 이미지 생성/편집의 해상도 레이블을 `이미지 해상도`로 통일했다.
  - `static/styles.css`: 비활성 해상도 컨트롤용 `muted-control` 스타일을 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-46` / `webgui-shell-v3-46`으로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-46`에서 새 HTML 정적 버전과 `이미지 해상도` 레이블 서빙 확인.
  - `/static/app.js?v=20260604-v3-46`에서 해상도 컨트롤 표시 로직과 새 정적 버전 포함 확인.
  - `/static/styles.css?v=20260604-v3-46`에서 `muted-control` 스타일 포함 확인.
- 백업: `backups/before-image-resolution-ui-20260604-185131`

### 템플릿 블록 이미지 해상도 선택
- 목표: 템플릿 화면의 이미지 생성/이미지 편집 블록에서도 `auto / 1k / 2k` 해상도를 선택하고 실행 요청에 반영되게 한다.
- 변경:
  - `static/app.js`: 템플릿 이미지 생성/편집 방식의 표시 필드에 `image_resolution`을 추가했다.
  - `static/app.js`: 템플릿 블록 카드에 `이미지 해상도` select를 추가하고 `auto / 1k / 2k` 옵션을 렌더링하도록 했다.
  - `static/app.js`: 블록 저장, 블록 불러오기, 템플릿 저장 payload에 `image_resolution`이 유지되도록 했다.
  - `static/app.js`: 템플릿 실행 시 `/api/t2i`, `/api/i2i` 요청에 블록별 `image_resolution` 값을 전달하도록 했다.
  - `static/app.js`: 이미지 모델이 Grok이 아닐 때는 템플릿 블록 해상도를 `auto`로 고정하고 비활성화한다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260604-v3-47` / `webgui-shell-v3-47`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - `http://127.0.0.1:7863/?v=20260604-v3-47`에서 새 HTML 정적 버전 서빙 확인.
  - `/static/app.js?v=20260604-v3-47`에서 `data-shot-image-resolution`, `templateImageResolutionLabels`, `/api/t2i` JSON 요청의 `image_resolution`, `/api/i2i` FormData 요청의 `image_resolution` 포함 확인.
- 백업: `backups/before-template-image-resolution-20260604-193456`

### 템플릿 실행 슬롯 파일 입력
- 목표: 템플릿 실행 준비의 배우/레퍼런스 슬롯에 라이브러리 선택뿐 아니라 파일 선택, 드래그앤드랍, 클립보드 붙여넣기로 이미지를 바로 넣을 수 있게 한다.
- 변경:
  - `app.py`: `/api/template-slot-upload`를 추가해 이미지/영상 슬롯 파일을 저장하고 라이브러리 메타데이터로 등록하도록 했다.
  - `static/app.js`: 템플릿 실행 슬롯 카드에 `파일` 버튼과 숨김 파일 입력을 추가했다.
  - `static/app.js`: 슬롯 카드에 드래그앤드랍, 붙여넣기, 파일 선택 업로드 이벤트를 연결하고 업로드 결과를 `templateRunState.slots`에 즉시 반영하도록 했다.
  - `static/styles.css`: 슬롯 드롭/업로드 진행 상태와 3개 액션 버튼 레이아웃을 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-48` / `webgui-shell-v3-48`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - Flask test client로 `/api/template-slot-upload` 이미지 슬롯 업로드, 메타데이터 등록, 테스트 파일 정리 확인.
  - `http://127.0.0.1:7863/?v=20260605-v3-48`에서 새 HTML 정적 버전 서빙 확인.
  - `/static/app.js?v=20260605-v3-48`에서 슬롯 업로드 버튼, 붙여넣기 이벤트, `/api/template-slot-upload` 호출 포함 확인.
  - `/static/styles.css?v=20260605-v3-48`에서 슬롯 드롭 상태 스타일 포함 확인.
- 백업: `backups/before-template-slot-upload-20260605-132202`

### 템플릿 이미지 편집 입력 모드 선택
- 목표: 템플릿의 이미지 편집 블록에서 여러 참조 이미지를 API에 그대로 전달할지, 먼저 붙여 1장으로 만든 뒤 편집할지 블록별로 선택하게 한다.
- 변경:
  - `static/app.js`: 이미지 편집 블록에 `다중 이미지 처리` 선택 UI를 추가하고 기본값을 기존 템플릿 동작과 같은 `여러 장 그대로 API 전달`로 유지했다.
  - `static/app.js`: 템플릿 저장, 블록 저장, 블록 불러오기, 검색, 실행 요청에 `edit_input_mode` 값을 포함하도록 연결했다.
  - `static/app.js`: 템플릿 실행 시 `/api/i2i` 요청에 저장된 `edit_input_mode`를 전달하도록 하여 `multi`/`stitch`가 실제 요청에 반영되게 했다.
  - `app.py`: 템플릿/블록 정규화에서 `image_resolution`과 `edit_input_mode`를 보존하도록 보강했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-49` / `webgui-shell-v3-49`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과.
  - Flask test client로 템플릿/블록 저장 시 `edit_input_mode=stitch`와 `image_resolution=2k` 보존 확인.
  - `http://127.0.0.1:7863/?v=20260605-v3-49` 및 `/static/app.js?v=20260605-v3-49`에서 v49 HTML/JS와 새 선택 UI 코드 확인.
- 백업: `backups/before-template-edit-input-mode-20260605-133907`
