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

### 프로젝트 작업공간 1차
- 목표: 특정 테마/작업 묶음을 프로젝트로 선택하고, 이후 생성되는 결과물을 프로젝트별로 추적할 수 있게 한다.
- 결정:
  - 프로젝트는 저장 경로의 `projects.json`에 별도로 저장한다.
  - 현재 프로젝트 선택은 브라우저 `localStorage`에 유지한다.
  - 결과물 파일 자체는 기존 저장 구조를 유지하고, 라이브러리 메타데이터 `extra.project_*` 값으로 프로젝트 연결을 기록한다.
- 변경:
  - `app.py`: 프로젝트 저장소 초기화, 프로젝트 CRUD API, 즐겨찾기 토글, 생성/편집/영상화/연장/영상편집/망가 배치 결과의 프로젝트 메타데이터 저장 추가.
  - `templates/index.html`: 상단 프로젝트 선택기, 라이브러리 프로젝트 필터, 설정 탭 프로젝트 관리 카드 추가.
  - `static/app.js`: 프로젝트 로드/선택/저장/삭제/즐겨찾기, 요청 payload 자동 태깅, 라이브러리 프로젝트 필터와 프로젝트 배지 표시 추가.
  - `static/styles.css`: 프로젝트 선택기, 설정 카드, 목록, 배지 스타일 추가.
  - `README.md`: 프로젝트 작업공간과 라이브러리 프로젝트 필터 설명 추가.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-50` / `webgui-shell-v3-50`으로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - 임시 app 복사본의 Flask test client로 `/api/projects` 생성/목록/즐겨찾기/삭제와 mock `/api/t2i` 결과 `extra.project_id`, `extra.project_title`, `extra.project_result` 저장 확인.
  - 실제 v3 서버를 `http://127.0.0.1:7863`에 재시작하고 `/health`, `/api/projects`, `/static/app.js?v=20260605-v3-50`, `/?v=20260605-v3-50` 응답 확인.
- 백업: `backups/before-projects-phase1-20260605-142200`

### 템플릿 저장 포맷 v1 고정과 마이그레이션 진입점
- 목표: 현재 템플릿/블록 저장 형태를 1차 포맷으로 명시하고, 이후 포맷이 업그레이드되더라도 기존 무버전/v1 파일을 읽을 수 있는 구조를 만든다.
- 결정:
  - 영상 템플릿과 재사용 블록 JSON에 `format_version: 1`을 저장한다.
  - 무버전 템플릿/블록은 v1로 간주한다.
  - 읽기/저장/응답 시 서버 정규화 전에 마이그레이션 함수를 반드시 통과시킨다.
  - future v2 이후 변환은 `migrate_video_template_format()`와 `migrate_template_block_format()`에 순차 변환으로 추가한다.
- 변경:
  - `app.py`: 템플릿/블록 포맷 버전 상수, 포맷 버전 파서, 템플릿/블록 마이그레이션 진입점 추가.
  - `app.py`: `normalize_video_template()`, `normalize_template_block()` 결과에 `format_version` 저장 추가.
  - `static/app.js`: 템플릿/블록 포맷 버전 상수와 저장 payload의 `format_version` 명시 추가.
  - `README.md`: 템플릿 포맷 호환 정책 문서화.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-51` / `webgui-shell-v3-51`로 갱신했다.
- 검증:
  - 무버전 템플릿/블록을 임시 앱 복사본의 Flask test client로 저장/조회했을 때 `format_version: 1`로 응답되고 실제 JSON 파일에도 v1이 저장되는지 확인.
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - 실제 v3 서버를 `http://127.0.0.1:7863`에 재시작하고 `/health`, `/static/app.js?v=20260605-v3-51`, `/api/video-templates`, `/api/video-template-blocks` 응답 확인.
- 백업: `backups/before-template-format-v1-20260605-154500`

### Grok 이미지 신규 모델 선택지 추가
- 목표: 이미지 생성/편집과 템플릿 이미지 블록에서 신규 Grok 이미지 모델을 선택할 수 있게 한다.
- 변경:
  - `templates/index.html`: 이미지 생성, 이미지 편집의 `image_model` 선택지에 `grok-imagine-image-pro`, `grok-imagine-image-quality-latest` 추가.
  - `static/app.js`: 템플릿 이미지 생성/편집 블록 모델 목록에 동일한 두 모델 추가.
  - `README.md`: 이미지 생성 모델 선택 설명 갱신.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-52` / `webgui-shell-v3-52`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - 실제 v3 서버를 `http://127.0.0.1:7863`에 재시작하고 `/health`, `/?v=20260605-v3-52`, `/static/app.js?v=20260605-v3-52` 응답과 새 모델 옵션 포함 확인.
- 백업: `backups/before-image-model-options-20260605-184546`

### Grok 공식홈 Quota 연동 보강과 실행 런처 안정화
- 목표: xAI API 과금 경로를 제외하고, 사용자가 로그인한 Grok 공식홈 세션 쿠키 기반 Quota 경로를 Hermes Proxy 경로와 병행해 쓸 수 있게 한다.
- 결정:
  - 이미지 생성은 `wss://grok.com/ws/imagine/listen` 공식홈 WebSocket 경로를 사용한다.
  - 이미지 편집과 이미지→영상은 `https://grok.com/rest/media/pipeline/run` 공식홈 streaming 경로를 사용한다.
  - 공식홈 경로는 UI에서 Hermes Proxy와 분리하고, 템플릿 블록에서도 `official:` 이미지 모델을 고르면 공식홈 경로로 자동 라우팅한다.
  - `official:imagine_h_1`의 고해상도 요청은 공식 payload 기준 `resolution_name: "2mp"`로 보낸다. UI의 `2k` 표시는 유지하되 실제 WebSocket payload에서는 `2mp`로 매핑한다.
- 변경:
  - `app.py`: `grok_official` provider 모드, 공식홈 Chrome/CDP 세션 상태, 진행 상태 API, 공식홈 이미지 WebSocket 생성, pipeline 기반 이미지 편집/이미지→영상 생성, 업로드 blob 참조 처리, 결과 blob/URL 다운로드 로직을 추가했다.
  - `app.py`: 공식홈 이미지 모델 후보 `official:imagine-x-1`, `official:imagine_h_1`을 추가하고 `/health`, `/api/auth/status` 모델 응답에 포함했다.
  - `app.py`: `official:imagine_h_1`에서 `2k` 선택 시 `resolution_name: "2mp"`로 전송하고, `1k`는 공식 payload 값이 확인되지 않아 명시하지 않도록 했다.
  - `templates/index.html`: 이미지 생성, 이미지 편집, 이미지→영상, Provider 설정에 `Grok 공식홈 Quota` 요청 경로 선택지를 추가했다.
  - `static/app.js`: 요청 경로 선택, 공식홈 모델 선택지 표시, 공식홈 경로의 파일/참조 이미지 처리 제한, Hermes 모델 탐색 버튼, 템플릿 블록의 공식홈 자동 라우팅을 연결했다.
  - `run_webgork_app.bat`: `PIL` 의존성 확인을 추가하고, `work\run_server.py`가 있으면 서버 로그를 남기는 runner로 실행하도록 하여 더블클릭 실행 실패 원인을 확인할 수 있게 했다.
  - `work/run_server.py`: 배치 실행 시 Flask 서버 stdout/stderr를 `work/server-runner.log`에 남기는 runner를 추가했다.
  - `.gitignore`: Grok 공식홈 Chrome 프로필과 임시 캡처 작업물을 저장소에 올리지 않도록 제외하고, `work/run_server.py`만 추적 대상으로 남겼다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-59` / `webgui-shell-v3-59`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py work\run_server.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - Flask test client로 `/health` 응답과 `models.grok_official_image_candidates`에 `official:imagine_h_1` 포함 확인.
  - `grok_official_image_resolution_name("2k") == "2mp"` 및 `grok_official_image_resolution_name("1k") == ""` 확인.
  - 새 `run_webgork_app.bat` 서버 시작 경로로 `/health` 200 응답 확인.
- 백업: `backups/after-grok-official-routes-launcher-20260606-230007`

### 앱 실행 상태 점검과 런처 중복 실행 방지
- 목표: `run_webgork_app.bat` 실행 후 앱이 열리지 않는 것처럼 보이는 상태를 확인하고, 런처가 최신 앱 URL을 열도록 정리한다.
- 확인:
  - 현재 Flask 서버는 `http://127.0.0.1:7863/health`에서 200으로 응답했다.
  - 루트 HTML, `/static/app.js?v=20260605-v3-59`, `/static/styles.css?v=20260605-v3-59`도 200으로 정상 서빙됐다.
  - `netstat`에서 7863 리스너가 2개 잡혀 중복 실행 흔적이 확인됐다.
  - `run_webgork_app.bat`의 Chrome 앱 실행 URL만 아직 `20260605-v3-52`로 남아 있었다.
- 변경:
  - `run_webgork_app.bat`: Chrome 앱 실행 URL과 기본 브라우저 fallback URL을 `20260605-v3-59`로 맞췄다.
  - `work/run_server.py`: 이미 `127.0.0.1:7863` 서버가 떠 있으면 새 Flask 서버를 띄우지 않고 로그에 상태만 남긴 뒤 정상 종료하도록 포트 체크를 추가했다.
- 검증:
  - `python -m py_compile work\run_server.py app.py` 통과.
  - 서버가 실행 중인 상태에서 `work\run_server.py`를 직접 호출했을 때 `webgork server already running on 127.0.0.1:7863` 로그를 남기고 종료 확인.
  - `/health` 200 응답 확인.
  - `run_webgork_app.bat`의 실행 URL이 `20260605-v3-59`로 변경됐는지 확인.
- 백업: `backups/after-launch-state-check-20260606-230420`

### 런처 health-check 타임아웃 수정
- 목표: 서버가 실제로 200 응답을 반환하는데도 `run_webgork_app.bat`가 `Server did not start.`로 종료되는 문제를 해결한다.
- 확인:
  - `/health`는 Grok 공식홈 상태 확인까지 포함해 약 2.5초가 걸렸다.
  - 기존 배치 파일은 시작 대기 중 `/health`를 `TimeoutSec 1`로 호출해서, Flask 로그에는 200이 찍혀도 PowerShell 쪽은 타임아웃으로 실패 처리했다.
  - 실패 시 앱 창 로딩 요청인 `GET /?v=...`가 찍히지 않았다.
- 변경:
  - `run_webgork_app.bat`: 서버 준비 확인 URL을 무거운 `/health`에서 가벼운 `/`로 바꿨다.
  - `run_webgork_app.bat`: 준비 확인 timeout을 5초로 늘리고, 성공 시 `exit 0`을 명시하도록 유지했다.
- 검증:
  - `cmd /c run_webgork_app.bat` 실제 실행 시 `Server did not start.` 메시지가 사라짐을 확인.
  - 로그에서 `GET /?v=20260605-v3-59`, `/static/app.js?v=20260605-v3-59`, `/api/projects`, `/api/grok-official/status` 요청 확인.
  - 현재 `127.0.0.1:7863` 리스너는 1개이며 `/health` 200 응답 확인.
- 백업: `backups/after-launch-health-timeout-fix-20260606-231339`

### Codex OAuth Proxy 연결 복구
- 목표: Codex/ChatGPT OAuth Local Proxy가 연결되지 않고 `127.0.0.1:3333` 연결 거부로 표시되는 문제를 확인하고 복구한다.
- 확인:
  - 앱 상태에서 `codex_proxy_configured=true`, `codex_proxy_running=false`, `codex_proxy_base_url=http://127.0.0.1:3333`으로 확인됐다.
  - `127.0.0.1:3333/api/health`는 연결 거부 상태였다.
  - 앱이 선택한 `C:\Users\aiguy\AppData\Roaming\npm\ima2.cmd serve` shim은 존재했지만, 실제 대상인 `node_modules\ima2-gen\bin\ima2.js`가 없어 `MODULE_NOT_FOUND`로 즉시 종료됐다.
  - `npx -y ima2-gen serve` fallback은 서버를 띄우지 못한 채 조용히 종료되어 로그가 필요했다.
- 변경:
  - `app.py`: 깨진 `ima2`/`ima2-gen` npm shim을 실행 후보에서 제외하고, 정상 패키지 파일이 있을 때만 직접 shim을 사용하도록 보강했다.
  - `app.py`: Codex proxy 시작 stdout/stderr를 `.webgork-private\codex-proxy.log`에 남기도록 변경했다.
  - `app.py`: Codex proxy 시작 프로세스가 바로 종료되면 502와 로그 tail을 반환하도록 빠른 실패 감지를 추가했다.
  - `app.py`: Codex proxy 상태 API에 `log_path`, `log_tail`을 포함했다.
  - 시스템 전역 npm 패키지 `ima2-gen@2.0.1`을 재설치해 깨진 shim을 복구했다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `resolve_codex_proxy_command()`가 깨진 상태에서는 `npx.cmd -y ima2-gen serve`로 fallback하는지 확인.
  - 전역 `ima2-gen@2.0.1` 재설치 후 `ima2.cmd --version`이 `2.0.1`을 반환하고, 앱이 `ima2.cmd serve`를 선택하는지 확인.
  - `/api/codex-proxy/start` 호출 후 `127.0.0.1:3333/api/health` 200 확인.
  - `/api/codex-proxy/status`에서 `running=true`, `oauth_status=ready`, `oauth_url=http://127.0.0.1:10532`, `version=2.0.1` 확인.
  - `/health`에서 `codex_proxy_running=true` 확인.
- 백업: `backups/after-codex-oauth-proxy-fix-20260606-232502`

### official:imagine_h_1 2k 해상도 선택 활성화
- 목표: Grok 공식홈 `official:imagine_h_1` 모델 선택 시 이미지 해상도 `2k` 옵션을 UI에서 선택할 수 있게 한다.
- 확인:
  - 공식 payload 기준 `official:imagine_h_1`의 고해상도 요청은 UI의 `2k`를 내부에서 `resolution_name: "2mp"`로 매핑한다.
  - 기존 UI 활성화 판정은 `grok-imagine-image...` 모델만 true로 보고 있어 `official:imagine_h_1`에서 해상도 select가 비활성화됐다.
- 변경:
  - `static/app.js`: `isGrokImageModel()`이 `official:imagine_h_1`도 해상도 선택 가능 모델로 판단하도록 보강했다.
  - `templates/index.html`, `static/service-worker.js`, `static/app.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-60` / `webgui-shell-v3-60`으로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `/?v=20260605-v3-60`에서 v60 HTML 서빙 확인.
  - `/static/app.js?v=20260605-v3-60`에서 `official:imagine_h_1` 해상도 활성화 판정 포함 확인.
  - WebGUI 서버를 재시작해 현재 실행 중인 앱도 v60 HTML/JS를 서빙하도록 반영했다.
- 백업: `backups/after-official-imagine-h1-resolution-ui-20260606-233110`

### 영상 latest 모델 404 fallback 처리
- 목표: `grok-imagine-video-latest` 선택 시 xAI/Hermes에서 모델 미존재 404가 발생하는 문제를 줄인다.
- 확인:
  - 오류 응답은 `The model grok-imagine-video-latest does not exist or your team ... does not have access to it` 형태였다.
  - 기본 영상 후보 목록에 `grok-imagine-video-latest`, `grok-imagine-video-1.5-latest`가 포함되어 있어 UI에 접근 불가 모델이 노출될 수 있었다.
- 변경:
  - `app.py`: 기본 Hermes 영상 후보 목록에서 `grok-imagine-video-latest`, `grok-imagine-video-1.5-latest`를 제거했다.
  - `app.py`: 영상 생성, 참조 이미지 기반 영상 생성, 영상 연장 요청에서 모델 미존재 404가 오면 fallback 모델로 재시도하도록 추가했다.
  - `app.py`: `grok-imagine-video-latest`는 `grok-imagine-video`로, `grok-imagine-video-1.5-latest`는 `grok-imagine-video-1.5-preview`, `grok-imagine-video-1.5`, `grok-imagine-video` 순서로 재시도한다.
  - `app.py`: fallback이 사용되면 결과 메타데이터에 `requested_video_model`, `video_model_fallback_attempts`를 남긴다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `video_model_retry_candidates("grok-imagine-video-latest")`가 `["grok-imagine-video-latest", "grok-imagine-video"]` 순서로 반환되는지 확인.
  - Flask test client `/health`에서 `grok-imagine-video-latest`가 `models.hermes_video_candidates`에 포함되지 않는지 확인.
  - WebGUI 서버를 재시작하고 실제 `/health` 응답에서도 latest 후보 제거와 7863/3333 리스너 정상 상태를 확인했다.
- 백업: `backups/after-video-model-latest-fallback-20260606-233652`

### Grok 공식홈 이미지 생성 moderation 완료 응답 진단 보강
- 목표: `official:imagine_h_1` 이미지 생성이 `completed=true`, `moderated=true`, `blobs=0`으로 끝나는 경우를 단순 WebSocket 종료 오류로 오진하지 않도록 한다.
- 확인:
  - `/api/grok-official/progress`에서 실패 요청은 `event_count=8`, `blob_count=0`, `completed=true`, `blocked_reason=moderated=true`, `last_event_status=completed` 상태였다.
  - 이 케이스는 연결 실패가 아니라 공식홈이 검열/모더레이션으로 결과 blob/URL을 보내지 않은 완료 응답이다.
- 변경:
  - `app.py`: `grok_official_image_blocked_message()`와 `grok_official_ws_closed_message()`를 추가해 차단, 완료 후 결과 없음, 일반 WebSocket 종료를 분리했다.
  - `app.py`: WebSocket 수신 중 `RuntimeError`가 발생해도 이미 받은 이벤트에 `blocked_reason`이 있으면 “검열/차단되어 이미지를 저장하지 않았습니다” 안내를 반환하도록 변경했다.
  - `app.py`: 완료 상태에서 URL 목록만 있는 경우도 성공 후보로 판단하도록 close 처리 조건을 보강했다.
  - `app.py`: post-loop 차단 처리의 progress `error`에도 사용자 안내 문구를 남기도록 정리했다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `grok_official_ws_closed_message()` 단위 확인으로 `moderated=true` 메시지가 차단 안내문에 포함되는지 확인.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - WebGUI 서버를 재시작하고 `/health` 200, Grok 공식홈 세션 쿠키 연결, Codex proxy 실행 상태를 확인했다.
- 백업: `backups/after-grok-official-moderation-ws-message-20260606-234830`

### 요청 경로별 모델 선택지 분리
- 목표: 이미지 생성, 이미지 편집, 이미지→영상, 영상 연장, 프레임 연장, 템플릿 블록에서 요청 경로를 선택하면 해당 경로에서 사용할 수 있는 모델만 보이도록 한다.
- 확인:
  - 기존 UI는 `applyHermesModelCandidates()`가 모든 `video_model` select에 Hermes 후보를 주입하고, 공식홈 경로 선택 시 이를 다시 숨기지 않아 공식홈 영상 생성 모델에 Hermes 후보가 함께 보였다.
  - 이미지 모델은 공식 모델 숨김 처리만 일부 있었고, Hermes 경로에서는 Codex/공식 모델까지 남을 수 있었다.
  - 영상 연장/프레임 연장 폼에는 `request_provider` select가 없어 경로별 모델 필터를 적용할 기준이 부족했다.
- 변경:
  - `app.py`: `/health`, `/api/auth/status` 모델 응답에 `grok_official_video_candidates`를 추가했다. 현재 공식홈 영상 pipeline 후보는 `grok-imagine-video`만 노출한다.
  - `templates/index.html`: 영상 연장과 프레임 연장 폼에 요청 경로 select를 추가했다.
  - `static/app.js`: 모델 후보 상태를 Hermes 이미지/영상, Grok 공식홈 이미지/영상으로 분리하고, 각 폼의 `request_provider` 값에 따라 모델 option을 숨김/비활성화하도록 변경했다.
  - `static/app.js`: 템플릿 shot 카드에 요청 경로 select를 노출하고, 이미지/편집/i2v/공식 연장/프레임 연장 블록의 모델 목록도 경로별로 다시 그리도록 보강했다.
  - `templates/index.html`, `static/app.js`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 버전과 앱 캐시를 `20260605-v3-61` / `webgui-shell-v3-61`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - Flask test client `/health`에서 `grok_official_video_candidates == ["grok-imagine-video"]` 확인.
  - Flask test client `/`와 `/static/app.js?v=20260605-v3-61`에서 v61 HTML/JS 서빙 확인.
  - 실제 실행 서버를 재시작하고 `http://127.0.0.1:7863/health` 200, Grok 공식홈 세션 쿠키 연결, Codex proxy 실행 상태, v61 HTML/JS 서빙을 확인했다.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
- 백업: `backups/after-route-scoped-model-selects-20260606-235828`

### Grok 공식홈 검열 placeholder 라이브러리 등록 제외
- 목표: Grok 공식홈 이미지 생성에서 검열/모더레이션 placeholder처럼 보이는 노이즈 이미지가 라이브러리에 쌓이지 않도록 한다.
- 확인:
  - 사용자가 보여준 라이브러리 항목은 같은 공식 request에서 나온 5장 중 4장이 흐릿한 다색 노이즈 placeholder였다.
  - 샘플 5장을 분석해 정상 이미지 1장은 유지하고 노이즈 placeholder 4장만 감지되는 픽셀 기준을 확인했다.
- 변경:
  - `app.py`: `likely_grok_official_censor_placeholder()`를 추가해 공식홈 placeholder 특유의 edge/entropy/gray_std 패턴을 감지한다.
  - `app.py`: `/api/grok-official-t2i`가 여러 결과를 받으면 placeholder로 감지된 파일은 메타데이터 등록에서 제외하고, 정상 결과만 라이브러리에 추가한다.
  - `app.py`: 템플릿 실행처럼 `/api/t2i`에 `request_provider=grok_official`로 들어오는 경로와 공식홈 이미지 편집 경로도 메타데이터 등록 전에 같은 필터를 통과하도록 보강했다.
  - `app.py`: placeholder가 제외된 경우 정상 결과 metadata extra에 `official_skipped_censor_placeholder_count`와 판정값을 남긴다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - 기존 공식홈 샘플 5장에서 placeholder 4장만 `is_placeholder=True`, 정상 이미지 1장은 `False`로 판정되는지 확인.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - WebGUI 서버를 재시작하고 `/health` 200, Grok 공식홈 세션 쿠키 연결, Codex proxy 실행 상태를 확인했다.
- 백업: `backups/after-skip-grok-censor-placeholders-20260607-000520`

### Grok 공식홈 pipeline 조기 종료 상태 진단 보강
- 목표: 이미지 편집 pipeline 스트림이 `PIPELINE_STEP_STATUS_RUNNING` 상태에서 닫힌 경우를 “결과 URL/blob 없음”으로 오진하지 않도록 한다.
- 확인:
  - 오류 payload의 마지막 이벤트는 `MEDIA_POST_MEDIA_STATUS_DRAFT_STARTED`, `PIPELINE_STEP_STATUS_RUNNING`, `progressPct=5~10` 상태였다.
  - 기존 코드는 스트림이 닫히면 완료 여부와 무관하게 post detail 후보 URL들을 조회했고, draft 상태라 404가 반복된 뒤 “결과 미디어 URL/blob을 찾지 못했습니다”로 실패했다.
- 변경:
  - `app.py`: `grok_official_pipeline_state()`를 추가해 pipeline status, step status, progress, failed/completed/running 상태를 파싱한다.
  - `app.py`: pipeline 이벤트 수신 중 progress를 `/api/grok-official/progress`에 남기도록 했다.
  - `app.py`: 완료 이벤트 없이 스트림이 닫히고 결과 미디어도 없으면 post detail 404 조회를 건너뛰고 `pipeline-incomplete` 오류로 반환한다.
  - `app.py`: 실패/차단 상태가 감지되면 `pipeline-failed`로 명확히 분리한다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - 사용자가 붙여준 형태의 synthetic 이벤트에서 `running=True`, `completed=False`, `progress=10`으로 파싱되는지 확인.
  - incomplete 메시지가 `kind=image`, `events`, `post_id`, `progress`, `pipeline`, `step_status`를 포함하는지 확인.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - WebGUI 서버를 재시작하고 `/health` 200, Grok 공식홈 세션 쿠키 연결, Codex proxy 실행 상태를 확인했다.
- 백업: `backups/after-grok-pipeline-incomplete-status-20260607-001030`
### Grok 공식홈 업로드 Cloudflare 403 fallback 보강
- 목표: 이미지→영상 공식홈 경로에서 `/rest/app-chat/upload-file` 직접 호출이 Cloudflare `Just a moment...` HTML 403을 반환할 때 브라우저 세션 fetch fallback을 타도록 한다.
- 확인:
  - 오류 detail은 JSON/anti-bot 응답이 아니라 Cloudflare challenge HTML이었다.
  - 기존 `grok_official_upload_file()`은 403 본문에 `anti-bot` 문자열이 있을 때만 `grok_official_browser_fetch()`로 우회했다.
- 변경:
  - `app.py`: 업로드 403 detail에 `Just a moment`, `challenges.cloudflare.com`, `<!doctype html`, `<html`이 포함된 경우도 브라우저 세션 업로드 fallback 대상으로 분류한다.
  - 기존 pipeline/video/image 알고리즘과 payload는 변경하지 않았다.
- 검증:
  - `python -m py_compile app.py` 통과.
- 백업: `backups/after-grok-upload-cloudflare-fallback-20260607-021123`

### Grok Agent provider 탭 추가 및 공식홈 업로드 Cloudflare 차단 메시지 정리
- 목표: 기존 Hermes Proxy/Grok 공식홈 pipeline 알고리즘을 건드리지 않고, Grok Imagine Agent 호출을 별도 provider 탭으로 추가한다.
- 확인:
  - Agent 명령은 `https://grok.com/rest/app-chat/conversations/new` 또는 기존 conversation의 `/responses`를 Chrome 세션 fetch로 호출한다.
  - 응답은 단일 JSON이 아니라 newline-delimited JSON 스트림이며, `cardAttachment.jsonData`, `cardAttachmentsJson`, `video_chunk.videoUrl`, `render_imagine_media.url` 등에서 결과 미디어 URL을 찾는다.
  - 이미지→영상 공식홈 업로드 오류는 브라우저 fetch fallback까지 진입한 뒤에도 Cloudflare `Just a moment...` HTML 403을 받을 수 있다.
- 변경:
  - `app.py`: `grok_agent_*` helper와 `/api/grok-agent` route를 추가해 Agent 자동/이미지 생성/이미지 편집/이미지→영상/영상 생성 명령을 별도 경로로 실행하도록 했다.
  - `app.py`: Agent 스트림 파서가 큰 JSON 문자열 자체를 미디어 URL로 오인하지 않도록 URL 후보 조건을 좁혔다.
  - `app.py`: Grok 공식홈 업로드가 Cloudflare 검증 페이지로 차단될 때 긴 HTML 대신 원인과 조치 안내를 반환하도록 정리했다.
  - `templates/index.html`: Grok Agent 탭과 독립 패널을 추가했다.
  - `static/app.js`: `/api/grok-agent` 큐 라벨과 결과 탭 매핑을 추가했다.
  - `templates/index.html`, `static/app.js`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 버전/캐시를 `20260605-v3-62` / `webgui-shell-v3-62`로 갱신했다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `node --check static/app.js` 통과.
  - Flask test client `/health` 200 확인.
  - Flask test client `/`에서 `grokAgent`, `/api/grok-agent`, `20260605-v3-62` 포함 확인.
  - Cloudflare challenge 문자열 판별 함수가 `True`를 반환하는지 확인.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
- 백업: `backups/after-grok-agent-provider-cloudflare-upload-message-20260607-000000`

### 2026-06-07 22:53 KST - Grok 공식홈 내부 이미지 편집 app-chat 우선 분기
- 목표: 공식홈에서 내부 생성 이미지를 편집할 때 실제 웹이 사용하는 `https://grok.com/rest/app-chat/conversations/new` 요청 형태와 앱의 공식 이미지 편집 경로를 맞춘다.
- 확인:
  - Chrome 9227 탭 훅으로 공식홈 편집 요청을 추적했다.
  - 공식 웹은 `modelName: imagine-image-edit`, `imageReferences: [assets.grok.com/.../generated/<parentPostId>/image.jpg]`, `parentPostId`를 `conversations/new`로 전송했다.
  - 응답에서 서버가 `rootPostId`, `resolvedImageReferences`, `isRootUserUploaded: false`, 최종 `assetId`를 보강했다.
- 변경:
  - `app.py`: 라이브러리 이미지가 공식 생성 post reference를 가진 경우 감지하는 `grok_official_path_has_post_reference()`를 추가했다.
  - `app.py`: 공식 생성 이미지 편집은 `app-chat/conversations/new` 경로를 먼저 사용하도록 분기했다.
  - `app.py`: 공식 내부 이미지 app-chat 요청에서는 공식 웹과 맞추기 위해 클라이언트가 `isRootUserUploaded: false`와 `rootPostId`를 직접 보내지 않도록 했다. 업로드 파일인 경우에만 `isRootUserUploaded: true`를 유지한다.
  - 기존 외부/업로드 이미지의 기본 `pipeline/run` 경로는 유지했다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - 기존 라이브러리의 공식 생성 이미지 metadata 샘플 5개에서 `grok_official_path_has_post_reference()`가 `True`를 반환하는지 확인.
  - WebGUI 서버를 재시작하고 `http://127.0.0.1:7863/health` 200 및 Grok 공식홈 세션 쿠키 연결 상태를 확인.
  - 실제 Grok 재요청은 크레딧 소모를 피하기 위해 자동 실행하지 않았다.
- 백업: `backups/grok-official-appchat-edit-20260607-225231`

### 2026-06-07 23:33 KST - Grok 공식홈 app-chat 요청 context 정렬
- 목표: 공식홈 직접 요청과 앱의 app-chat 이미지 편집 요청 차이를 줄이되, 실제 Grok 생성/편집 요청은 보내지 않아 크레딧을 쓰지 않는다.
- 확인:
  - 공식홈 캡처 요청에는 `x-statsig-id`, `x-xai-request-id`, `parentPostId`, `assets.grok.com/.../generated/<postId>/image.jpg` 형식의 `imageReferences`가 포함되어 있었다.
  - 기존 앱 요청은 `target_post_id`와 무관하게 첫 Grok 탭에서 fetch가 실행될 수 있었고, metadata 상태에 따라 `imagine-public.x.ai` URL을 참조할 수 있었다.
- 변경:
  - `app.py`: `grok_imagine_tab()`에 `post_id` 우선 선택을 추가하고, 일치 탭이 없으면 해당 공식 post 탭을 연 뒤 그 context에서 fetch하도록 했다.
  - `app.py`: `grok_official_browser_fetch()`가 페이지 storage에서 `x-statsig-id`를 찾을 수 있을 때만 공식 요청과 같은 헤더로 포함하도록 했다.
  - `app.py`: 공식 post reference 이미지 URL을 `assets.grok.com/.../generated/<postId>/image.jpg` 형식으로 정규화하는 helper를 추가했다.
  - `app.py`: app-chat 이미지 편집 요청에 `target_post_id=parentPostId`를 넘기도록 했다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `grok_official_generated_asset_image_url()`가 성공 기록의 `generated/<postId>/content`를 `generated/<postId>/image.jpg`로 변환하는지 확인.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - 실제 Grok 생성/편집 요청은 크레딧 절약을 위해 실행하지 않았다.
- 백업: `backups/grok-official-appchat-context-20260607-233041`

### 2026-06-07 23:40 KST - Codex/ChatGPT 모델 표시 보강
- 목표: 이미지 생성/편집 UI에서 Codex/ChatGPT OAuth 경로와 `gpt-5.x` 모델이 요청 경로별 모델 필터에 맞게 보이도록 최소 수정했다.
- 변경:
  - `templates/index.html`: 이미지 생성, 이미지 편집의 요청 경로에 `Codex/ChatGPT OAuth` 옵션을 추가했다.
  - `static/app.js`: `codex_proxy` 요청 경로를 인식하고, 해당 경로 선택 시 `gpt-5.4-mini`, `gpt-5.4`, `gpt-5.5` 모델만 보이도록 이미지 모델 필터를 분리했다.
  - `static/app.js`: 템플릿 블록에서도 Codex/ChatGPT 경로와 GPT 모델 표시/실행값이 어긋나지 않도록 허용 목록을 맞췄다.
  - `app.py`, `static/app.js`: Codex Proxy 상태 패널에 현재 Codex 이미지 모델을 표시하도록 `image_model` 상태값과 UI 행을 추가했다.
  - `templates/index.html`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 캐시 버전을 `20260605-v3-63` / `webgui-shell-v3-63`으로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - Flask test client `/`에서 `Codex/ChatGPT OAuth`, `20260605-v3-63` 포함 확인.
  - Flask test client `/api/codex-proxy/status` 200 및 `image_model: gpt-5.4-mini` 확인.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
- 백업: `backups/gpt-codex-model-display-20260607-234011`

### 2026-06-08 10:41 KST - Agent 탭 숨김 및 Hermes 이미지 모델 4개 제한
- 목표: Grok Agent 탭은 화면에서만 숨기고, Hermes Proxy 이미지 생성/편집 모델 목록은 실제 사용할 4개 모델만 표시되도록 정리했다.
- 변경:
  - `templates/index.html`: `grokAgent` 탭 버튼에 `hidden`을 추가했다. Agent 패널과 API 코드는 유지했다.
  - `app.py`: `HERMES_IMAGE_MODEL_CANDIDATES`를 `grok-imagine-image-quality`, `grok-imagine-image-pro`, `grok-imagine-image-quality-latest`, `grok-imagine-image` 4개로 제한했다.
  - `app.py`: `/api/auth/status`, `/health`의 Hermes 이미지 후보가 기존 발견 모델을 섞지 않고 4개만 내려가도록 수정했다.
  - `app.py`, `static/app.js`: Hermes 모델 탐색/프론트 후보 적용에서도 숨긴 이미지 모델이 다시 목록에 섞이지 않도록 필터링했다.
  - `templates/index.html`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 캐시 버전을 `20260605-v3-64` / `webgui-shell-v3-64`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - Flask test client `/`에서 `grokAgent` 탭 버튼 `hidden` 및 `20260605-v3-64` 확인.
  - Flask test client `/api/auth/status`에서 Hermes 이미지 후보가 4개만 내려오는지 확인.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
- 백업: `backups/hide-agent-limit-hermes-models-20260608-104109`

### 2026-06-08 20:00 KST - Hermes Proxy 영상 공식 연장 provider 전달 수정
- 목표: 템플릿 공식 연장 단계에서 요청 경로가 `Hermes Proxy`인 경우에도 기존 direct xAI OAuth/API 경로로 떨어지던 문제를 수정했다.
- 확인:
  - 2026-06-08 19:56~19:57 KST 템플릿 08단계는 `/api/v2v-extend` 502로 실패했다.
  - 에러는 `Grok OAuth 로그인 또는 XAI_API_KEY 설정이 필요합니다.`였고, 이는 Hermes Proxy 인증 실패가 아니라 direct xAI 인증 경로로 들어갔다는 신호였다.
  - `handle_v2v_extend("official")`가 `request_provider`를 읽고도 `live_video_extension()`에 provider를 전달하지 않아 `/files`, `/videos/extensions`, polling이 기본 direct provider를 사용하고 있었다.
- 변경:
  - `app.py`: `xai_upload_file(path, provider=None)`로 확장하고 provider가 `hermes_proxy`이면 Hermes base URL과 Hermes headers를 사용하도록 했다.
  - `app.py`: `live_video_extension(..., provider=None)`로 확장하고 `/videos/extensions`와 polling에도 provider를 전달하도록 했다.
  - `app.py`: `/api/v2v-extend` 공식 연장 분기에서 `effective_video_provider`를 `live_video_extension()`으로 넘기도록 했다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - monkeypatch 테스트로 `provider='hermes_proxy'`일 때 호출 URL이 `http://127.0.0.1:8645/v1/files`, `http://127.0.0.1:8645/v1/videos/extensions`가 되는지 확인했다.
  - 실제 영상 연장 요청은 크레딧 절약을 위해 실행하지 않았다.
- 백업: `backups/hermes-v2v-extension-provider-20260608-200053`

### 2026-06-08 20:21 KST - 검열 안내 토스트 전용 처리
- 목표: 검열/모더레이션 관련 안내는 큰 오류 로그 팝업을 띄우지 않고 간단한 토스트로만 보여주도록 조정했다.
- 변경:
  - `static/app.js`: `moderationNoticeText()`를 추가해 `검열`, `moderated`, `moderation`, `content policy`, `policy violation` 등 모더레이션 계열 메시지를 감지하도록 했다.
  - `static/app.js`: `showToast(message, true)` 호출 시 모더레이션 안내이면 `errorModal`을 열지 않고 토스트만 표시하도록 분기했다.
  - `static/app.js`: 긴 모더레이션 문구는 짧은 안내 문구로 줄여 표시하도록 했다.
  - `static/app.js`, `templates/index.html`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 캐시 버전을 `20260605-v3-65` / `webgui-shell-v3-65`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - DOM 시뮬레이션으로 모더레이션 메시지는 `openErrorLog()`를 호출하지 않고, 일반 오류는 기존처럼 `openErrorLog()`를 호출하는지 확인했다.
- 백업: `backups/moderation-toast-only-20260608-202149`

### 2026-06-09 16:44 KST - 프롬프트 추출 Hermes Proxy 라우팅 수정
- 목표: 그림 → 프롬프트 추출 기능이 Hermes Proxy 연결 상태에서도 direct xAI `/responses` 인증 경로로 빠지던 문제를 수정했다.
- 확인:
  - `/api/reverse-prompt`가 기존에는 `cfg["api_base"] + "/responses"`와 기본 `xai_headers()`를 사용해 provider가 `grok_official`일 때 `Grok OAuth 로그인 또는 XAI_API_KEY 설정이 필요합니다.` 오류가 날 수 있었다.
  - 현재 설정은 `provider: grok_official`, `hermes_base_url: http://127.0.0.1:8645/v1` 조합이라 프롬프트 추출도 Hermes base URL을 우선 사용해야 한다.
- 변경:
  - `app.py`: `xai_responses_base_headers_provider()`를 추가해 Hermes base URL이 있으면 `/responses` 요청도 Hermes Proxy 헤더와 base URL을 사용하도록 했다.
  - `app.py`: `/api/reverse-prompt`에서 provider override를 읽고, 응답에 `request_provider`를 함께 반환하도록 했다.
- 검증:
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - monkeypatch 테스트로 실제 외부 요청 없이 `/api/reverse-prompt` 호출 URL이 `http://127.0.0.1:8645/v1/responses`, provider가 `hermes_proxy`로 잡히는 것을 확인했다.
  - 실제 프롬프트 추출 요청은 크레딧/쿼터 사용 방지를 위해 실행하지 않았다.
- 백업: `backups/before-reverse-prompt-hermes-20260609-163800`

### 2026-06-11 14:36 KST - 템플릿 블록 불러오기와 이미지별 i2v 병렬 큐
- 목표: 각 생성/편집/영상/연장 탭에서 템플릿 블록 저장뿐 아니라 불러오기도 가능하게 하고, 이미지→영상 탭에서 여러 이미지를 같은 프롬프트로 이미지별 병렬 큐 등록할 수 있게 했다.
- 확인:
  - 기존 큐는 `maxActiveJobs = 30`이라 동시 생성 수를 크게 잡아도 앱 레벨에서 30개씩만 병렬 실행했다.
  - 기존 `queue_count` 최대값은 20이었다.
  - 기존 이미지→영상 다중 이미지는 한 요청 안의 시작 이미지/추가 참조 묶음으로 처리되었다.
- 변경:
  - `static/app.js`: 큐 반복 수 최대를 100으로 올렸다.
  - `static/app.js`: 앱 큐의 고정 병렬 cap을 제거해 대기 중인 작업을 가능한 즉시 모두 `fetch`로 시작하도록 했다.
  - `templates/index.html`, `static/app.js`: 이미지→영상 폼에 `여러 이미지를 각각 별도 영상 요청으로 큐에 등록` 옵션을 추가했다.
  - `static/app.js`: 해당 옵션이 켜지면 이미지 N개와 동시 생성 수 M개를 `N x M`개의 개별 i2v 작업으로 큐에 등록하도록 했다. 프롬프트 플래너는 한 번만 실행해 같은 프롬프트를 공유한다.
  - `static/app.js`, `static/styles.css`: 각 기능 탭에 템플릿 블록 선택/불러오기/저장 컨트롤을 추가하고, 같은 method의 블록만 표시하도록 했다.
  - `templates/index.html`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 캐시 버전을 `20260605-v3-66` / `webgui-shell-v3-66`으로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - 실제 생성 요청은 크레딧/쿼터 사용 방지를 위해 실행하지 않았다.
- 백업: `backups/before-template-load-i2v-batch-queue-20260611-142737`

### 2026-06-11 14:55 KST - Hermes 영상 모델 라우팅 엄격화
- 목표: Hermes Proxy 영상 생성에서 존재하지 않는 모델을 선택해도 기본 모델로 조용히 폴백되어 영상이 생성되는 문제와, Hermes 목록에 공식홈 쿼타 라벨이 섞여 보이는 문제를 정리했다.
- 변경:
  - `app.py`: Hermes 영상 후보를 실제 이미지->영상 probe에서 확인된 `grok-imagine-video`, `grok-imagine-video-1.5-preview` 두 개로 제한했다.
  - `app.py`: `video_model_retry_candidates()`의 무조건 기본 모델 재시도 경로를 제거했다. 이제 임의/미지원 모델은 선택값 그대로 실패하며, `latest` 계열 alias만 명시된 호환 후보로 재시도한다.
  - `static/app.js`: 같은 모델 ID가 Hermes/공식홈에 동시에 있을 때 현재 요청 경로 기준으로 옵션 라벨을 다시 적용하도록 `modelOptionLabelForRoute()`를 추가했다.
  - `static/app.js`, `templates/index.html`, `static/service-worker.js`, `run_webgork_app.bat`: 정적 캐시 버전을 `20260605-v3-67` / `webgui-shell-v3-67`로 갱신했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `video_model_retry_candidates()`에서 `grok-imagine-video-v2`, `grok-imagine-video-fast`가 더 이상 `grok-imagine-video`로 폴백하지 않는 것을 확인했다.
  - Flask test client `/api/auth/status`에서 `models.hermes_video_candidates`가 `grok-imagine-video`, `grok-imagine-video-1.5-preview` 두 개로 내려오는 것을 확인했다.
  - 실제 서버를 `http://127.0.0.1:7863`에 재시작하고 `/health`, `/?v=20260605-v3-67`, `/static/app.js?v=20260605-v3-67` 응답을 확인했다.
  - 실제 영상 생성 요청은 쿼터/크레딧 보호를 위해 실행하지 않았다.
- 백업: `backups/before-video-model-route-strict-20260611-145244`

### 2026-06-11 15:11 KST - 설정 탭 Hermes 신규 모델 검색/추가
- 목표: 설정 탭에서 Hermes Proxy 기반 이미지 생성, 이미지 편집, 이미지→영상 모델 후보를 실제 요청으로 검사하고, 정상 응답한 모델을 사용자가 선택해 목록에 추가할 수 있게 했다.
- 변경:
  - `templates/index.html`: 설정 탭에 `Hermes 모델 검색` 카드를 추가했다. 검색 범위, 후보 모델 입력, 최대 검사 수, 검색/선택 추가 버튼, 결과 영역을 포함한다.
  - `app.py`: `/api/hermes/model-probe`가 사용자 입력 후보와 Hermes `/models` 응답까지 검사하도록 확장했다. 검색 결과는 기본적으로 저장하지 않고, `save=true`일 때만 저장하도록 분리했다.
  - `app.py`: `/api/hermes/models/add`를 추가해 체크된 정상 응답 모델만 `hermes_discovered_image_models`, `hermes_discovered_video_models`에 저장하도록 했다.
  - `app.py`: 이미지/편집/영상 후보 응답을 `hermes_model_candidates_payload()`로 통합하고, 저장된 신규 이미지/편집 모델도 드롭다운 후보에 포함되도록 했다.
  - `app.py`: 영상 모델 probe는 앱의 이미지→영상 흐름에 맞춰 1px 테스트 이미지를 `reference_images`로 포함해 검사하도록 했다.
  - `static/app.js`: 검색 결과 표, 성공 모델 체크박스, 선택 모델 추가 동작을 구현했다. 검색만으로는 기존 목록을 바꾸지 않고, 추가 버튼을 눌렀을 때만 모델 목록을 갱신한다.
  - `static/app.js`: Hermes 이미지 후보의 고정 4개 필터를 풀어 사용자가 추가한 신규 모델이 이미지 생성/편집 드롭다운에 표시되도록 했다.
  - `static/styles.css`, `templates/index.html`, `static/service-worker.js`, `run_webgork_app.bat`: 모델 검색 결과 UI와 정적 캐시 버전 `20260605-v3-68` / `webgui-shell-v3-68`을 반영했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py` 통과.
  - `git diff --check` 통과. Windows CRLF 안내 경고만 출력됨.
  - Flask test client로 `/?v=20260605-v3-68`, `/static/app.js?v=20260605-v3-68`에 모델 검색 UI/JS가 포함되는 것을 확인했다.
  - 임시 설정 파일을 사용해 `/api/hermes/models/add`가 이미지/편집/영상 모델을 저장 후보로 반환하는 것을 확인했다.
  - monkeypatch 테스트로 `/api/hermes/model-probe`가 정상 응답 모델을 반환하되 기본적으로 실제 설정 파일에 저장하지 않는 것을 확인했다.
  - 실제 서버를 `http://127.0.0.1:7863`에 재시작하고 `/health`, `/?v=20260605-v3-68`, `/api/hermes/models/add` 응답을 확인했다.
  - 인앱 브라우저 검증은 브라우저 연결 프로세스가 샌드박스에서 시작 중 종료되어 진행하지 못했고, HTTP/DOM 문자열 검증으로 대체했다.
  - 실제 생성/편집/영상 probe 요청은 쿼터/크레딧 보호를 위해 실행하지 않았다.
- 백업: `backups/before-20260611-1500-model-discovery-ui`

### 2026-06-11 20:13 KST - Hermes-only 개인정보 클린 릴리즈 폴더 생성
- 목표: 공홈 quota를 사용하는 UI/라우트/웹 세션 루틴이 포함되지 않고, 개인 설정/쿠키/로그/라이브러리 파일이 빠진 원클릭 실행 릴리즈 폴더를 만든다.
- 변경:
  - `tools/build_release_no_official.py`: `release/WebGrok-v3-Hermes` 산출물을 재생성하는 빌드 스크립트를 추가했다.
  - 릴리즈 산출물에는 `app.py`, `templates`, `static`, `requirements.txt`, `work/run_server.py`, `webgork-settings.json`, `RUN_WEBGROK_HERMES_ONLY.bat`, `README_RELEASE.md`만 포함한다.
  - 빌드 과정에서 공홈 quota provider 옵션, 공홈 사용량 카드, 직접 OAuth 로그인 카드, 공홈 quota endpoint/모델/Chrome 세션 문자열을 제거하거나 비활성화한다.
  - 릴리즈 기본 설정은 `provider: hermes_proxy`, `hermes_base_url: http://127.0.0.1:8645/v1`로 생성한다.
  - `.webgork-private`, `.chrome-*`, `media-library`, `backups`, 로그, git 메타데이터, 기존 `webgork-settings.json`은 복사하지 않는다.
  - 공유용 압축본 `release/WebGrok-v3-Hermes-20260611.zip`을 생성했다.
- 검증:
  - 릴리즈 폴더 기준 `python -m py_compile app.py` 통과.
  - 릴리즈 폴더 기준 `node --check static/app.js` 통과.
  - Flask test client에서 `/health`와 `/` 200, 공홈 quota 관련 route 없음 확인.
  - `rg`로 `grok-official`, `grok_official`, `GROK_OFFICIAL`, `official:imagine`, `grok.com/rest/app-chat`, `Cookie`, `csrf`, 개인 이메일/계정 문자열, OAuth token 파일명 패턴이 릴리즈 폴더에 남지 않았는지 확인했다.
  - 테스트 중 생성된 빈 `.webgork-private`, `media-library`, `__pycache__`는 릴리즈 폴더 내부 경로를 확인한 뒤 삭제하고 zip을 다시 만들었다.
- 산출물:
  - `release/WebGrok-v3-Hermes/RUN_WEBGROK_HERMES_ONLY.bat`
  - `release/WebGrok-v3-Hermes-20260611.zip`

### 2026-06-11 21:43 KST - Hermes-only 릴리즈 샘플 템플릿 포함
- 목표: 릴리즈를 받은 사용자가 템플릿 탭에서 빈 목록만 보지 않도록, 현재 즐겨찾기된 `테스트용 템플릿`을 개인정보 없는 샘플로 포함한다.
- 변경:
  - `release_seed/library/video-templates.json`: 즐겨찾기 템플릿 1개를 샘플 seed로 추가했다.
  - `release_seed/library/video-template-blocks.json`: 샘플 블록 목록은 빈 배열로 추가했다.
  - 샘플 템플릿의 슬롯 `selected_path`, `selected_kind`, `selected_label`은 모두 비워 실제 작업 이미지/로컬 경로가 릴리즈에 포함되지 않도록 했다.
  - `tools/build_release_no_official.py`: 릴리즈 빌드 시 `release_seed/library`의 JSON을 `release/WebGrok-v3-Hermes/media-library`에 심도록 추가했다.
  - 릴리즈 안내문에서 개인 media-library 전체 제외 대신, 생성 이미지/영상은 제외하고 정리된 샘플 JSON만 포함한다고 정리했다.
  - 릴리즈 HTML의 예시 경로에 남아 있던 `C:\Users\aiguy\...` placeholder를 `C:\WebGrok\media`로 치환하도록 했다.
- 검증:
  - 릴리즈 `/api/video-templates`가 `테스트용 템플릿` 1개를 반환하는 것을 Flask test client로 확인했다.
  - 샘플 템플릿의 슬롯 선택 참조가 0개인 것을 확인했다.
  - 릴리즈 폴더에서 공홈/쿠키/CSRF/OAuth token/개인 계정명/`C:\Users\` 패턴이 검색되지 않음을 확인했다.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `release/WebGrok-v3-Hermes-20260611.zip`를 샘플 템플릿 포함 상태로 재생성했다.

### 2026-06-11 21:57 KST - 릴리즈 공홈 쿼타 잔여 UI/루틴 제거 보강
- 목표: Hermes-only 릴리즈 전달본에서 상단 `G` 상태 표시, credit 배터리, 무료 크레딧/Usage 카드, 공홈 quota 대체 provider 잔여 문자열이 보이지 않도록 정리한다.
- 변경:
  - `tools/build_release_no_official.py`: 릴리즈 HTML에서 `quotaPill`과 `무료 크레딧·토큰` 카드를 제거하도록 보강했다.
  - 직접 OAuth 카드 제거 regex가 nested `div` 때문에 닫힘 태그를 남기던 문제를 수정했다.
  - 릴리즈 JS에서 `refreshQuota`, `/api/oauth/quota`, `installQuotaPanel`, Usage 링크 제거 루틴, 상단 `G` mini-service를 제거했다.
  - 공홈 quota 대체명으로 남던 `home_quota_disabled`, `disabled_web_provider`, `release_removed_provider` 관련 문자열이 릴리즈 산출물에 남지 않도록 후처리를 추가했다.
  - 모델 검색 안내 문구를 `Hermes 요청량` 기준으로 조정했다.
- 검증:
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 릴리즈 폴더에서 `Grok 공식홈`, `grok_official`, `grok-official`, `home_quota`, `disabled_web_provider`, `release_removed_provider`, `quotaPill`, `refreshQuota`, `/api/oauth/quota`, `grok.com/?_s=usage`, `C:\Users\` 패턴이 검색되지 않음을 확인했다.
  - Flask test client에서 `/health` 200, provider `hermes_proxy`, UI에 `quotaPill`/`무료 크레딧`/`Grok 공식홈`/`C:\Users\` 미포함, 샘플 템플릿 1개 유지 확인.
  - `release/WebGrok-v3-Hermes-20260611.zip`를 갱신했다.

### 2026-06-11 22:02 KST - 릴리즈 Chrome 앱 모드 exe 추가
- 목표: 릴리즈 사용자가 배치 파일 대신 Chrome 앱 창 형태로 WebGrok을 실행할 수 있는 exe를 제공한다.
- 변경:
  - `tools/build_release_no_official.py`: `WEBGROK_CHROME_APP.exe`를 생성하는 C# WinExe 런처 빌드 단계를 추가했다.
  - 런처는 `/health`를 확인하고 서버가 없으면 `work/run_server.py`를 `WEBGORK_PORT=7863`, `WEBGORK_OPEN_BROWSER=0` 환경으로 시작한 뒤 Chrome을 `--app=http://127.0.0.1:7863/?v=...` 모드로 연다.
  - Chrome을 찾지 못하면 기본 브라우저로 fallback한다.
  - `README_RELEASE.md`에 exe 사용법과 unsigned 실행 파일이라 SmartScreen/보안 경고가 뜰 수 있음을 추가했다.
- 검증:
  - `release/WebGrok-v3-Hermes/WEBGROK_CHROME_APP.exe` 생성 확인.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 공홈 quota/Usage/개인 경로 잔여 패턴 검색 통과.
  - `release/WebGrok-v3-Hermes-20260611.zip`를 exe 포함 상태로 재생성했다.

### 2026-06-12 00:05 KST - 릴리즈 설정 연결 상태 패널 복원
- 목표: Hermes-only 릴리즈 설정 화면에서 원본 앱의 `연결 상태` 패널을 유지하되, `Grok 공식홈` quota 연결 행만 제외한다.
- 변경:
  - `tools/build_release_no_official.py`: 릴리즈 JS에서 `compactSettingsLayout()` 호출을 제거해 `Provider` 설정 카드를 유지하도록 했다.
  - `installConnectionStatusPanel()`은 유지하고, 패널 내부에는 `Hermes xAI`와 `Codex / ChatGPT` 행만 남도록 정리했다.
  - 남아 있던 `bindGrokOfficialPanel()` 호출을 제거해 설정 스크립트가 끊기지 않도록 했다.
  - `installQuotaPanel()` 호출은 제거해 공홈 quota/Usage UI는 계속 제외했다.
- 검증:
  - 릴리즈 HTML에 `providerForm` 포함, `quotaPill`/`무료 크레딧`/`Grok 공식홈` 미포함 확인.
  - 릴리즈 JS에 `connectionStatusPanel`, `Hermes xAI`, `Codex / ChatGPT` 포함, `Grok 공식홈` 미포함 확인.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 공홈 quota/Usage/개인 경로 잔여 패턴 검색 통과.
  - `WEBGROK_CHROME_APP.exe`와 샘플 템플릿 1개 유지 확인.
  - `release/WebGrok-v3-Hermes-20260611.zip`를 갱신했다.

### 2026-06-12 00:31 KST - 릴리즈 연결 상태 카드 HTML 기본 삽입
- 목표: 릴리즈 설정 화면에서 JS 삽입 실패나 브라우저 캐시가 있어도 사용자가 원본 스타일의 `연결 상태` 카드를 바로 볼 수 있게 한다.
- 변경:
  - `tools/build_release_no_official.py`: `settings-grid` 시작 직후에 `connectionStatusPanel` HTML을 직접 삽입하도록 변경했다.
  - 삽입 카드에는 `Hermes xAI`와 `Codex / ChatGPT` 연결 행만 포함하고, `Grok 공식홈` 행은 포함하지 않는다.
  - 기존 `installConnectionStatusPanel()`은 이미 존재하는 패널에 Hermes/Codex 버튼 동작만 바인딩하도록 유지했다.
- 검증:
  - 릴리즈 HTML에 `connectionStatusPanel`, `Hermes xAI`, `Codex / ChatGPT` 포함 확인.
  - 릴리즈 HTML/JS에 `Grok 공식홈`, quota/Usage/credit 관련 문자열 미포함 확인.
  - 릴리즈 JS에 `bindGrokOfficialPanel`, `installQuotaPanel();`, `compactSettingsLayout();` 호출이 남지 않음을 확인했다.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - `release/WebGrok-v3-Hermes-20260611.zip`를 갱신했다.

### 2026-06-12 01:43 KST - 릴리즈 상단 연결 배지 기준 일치
- 목표: 연결 상태 카드에서는 끊김으로 보이는데 화면 상단 H/C 배지는 초록으로 표시되는 불일치를 제거한다.
- 변경:
  - `tools/build_release_no_official.py`: 릴리즈 `renderStatus()`에서 Codex 상단 배지가 `/health`의 `codex_proxy_running`만 보고 초록이 되지 않도록 초기값을 끊김으로 변경했다.
  - 상단 H/C 미니 배지에 `data-top-service` 식별자를 추가하고, `setTopServiceBadge()` 헬퍼로 연결 카드 갱신 결과와 같은 기준을 반영하도록 했다.
  - Hermes는 `logged_in && proxy_running`, Codex는 `/api/codex-proxy/status`의 `running && oauth_status === "ready"`일 때만 상단 배지가 초록으로 바뀌도록 맞췄다.
- 검증:
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 공홈 quota/Usage/official 관련 잔여 문자열 검색 통과.
  - 7863 릴리즈 서버로 `/health` 응답을 확인했고, 확인 후 서버를 다시 종료했다.
  - `release/WebGrok-v3-Hermes-20260611.zip`를 갱신했다.

### 2026-06-12 02:20 KST - 원본 WebGUI.v3 EXE 서버 직접 기동화
- 목표: 원본 앱에서 서버가 내려가 있을 때 `WebGUI.v3.exe`만 실행해도 서버가 뜨지 않는 문제를 해결한다.
- 확인:
  - 기존 `WebGUI.v3.exe`는 같은 폴더의 `run_webgork_app.bat`만 실행하는 래퍼였고, 실제 재현 시 새 서버 기동 로그가 남지 않았다.
  - 서버 직접 기동 로직은 릴리즈 `WEBGROK_CHROME_APP.exe`에만 들어 있었다.
- 변경:
  - `tools/WebGuiLauncher.cs`: `/health` 확인 후 서버가 없으면 `work/run_server.py`를 `WEBGORK_PORT=7863`, `WEBGORK_OPEN_BROWSER=0` 환경으로 직접 시작하도록 교체했다.
  - 서버 준비가 끝나면 Chrome `--app=http://127.0.0.1:7863/?v=20260605-v3-68` 모드로 앱을 연다.
  - Python/Chrome 탐색 fallback과 서버 시작 실패 시 `work/server-runner.log` 안내 메시지를 추가했다.
  - `WebGUI.v3.exe`를 새 런처 소스로 재빌드했다.
- 검증:
  - `python -m py_compile app.py work/run_server.py` 통과.
  - `tools/build_webgui_launcher.ps1`로 `WebGUI.v3.exe` 재생성 확인.
  - 서버가 내려간 상태에서 `WebGUI.v3.exe`만 실행해 7863 LISTENING 생성 및 `/health` 200 응답 확인.

### 2026-06-12 02:57 KST - 미리보기 이미지 바로 편집/영상 전송
- 목표: 결과 미리보기나 큐 결과를 전체화면으로 볼 때 라이브러리를 거치지 않고 바로 이미지 편집 또는 이미지→영상 탭으로 보낼 수 있게 한다.
- 변경:
  - `templates/index.html`: `mediaViewer`에 `편집`, `영상`, `닫기` 버튼을 추가하고, 라이브러리 선택 모달에 `선택 완료` 버튼을 추가했다.
  - `static/app.js`: 전체화면 이미지의 `/media-library/...` 경로를 기준으로 이미지 편집/영상 탭의 레퍼런스를 교체하는 흐름을 추가했다. 기존 프롬프트 입력값은 유지한다.
  - 큐 완료 항목의 `보기`는 첫 결과를 전체화면으로 열도록 정리해 같은 버튼 흐름을 사용할 수 있게 했다.
  - 이미지→영상의 `여러 이미지를 각각 별도 영상 요청으로 큐에 등록`이 켜진 경우 라이브러리 선택 모달에서 여러 이미지를 선택/해제할 수 있게 하고, 최대 10개까지 허용했다.
  - 일반 이미지 편집/일반 이미지→영상 참조 제한은 기존처럼 3개 또는 단일 참조 모델 기준을 유지했다.
  - 정적 캐시 버전을 `20260612-v3-69` / `webgui-shell-v3-69`로 갱신하고 `WebGUI.v3.exe`를 재빌드했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py work/run_server.py` 통과.
  - 원본 서버를 재시작해 `/`, `/static/app.js`, `/static/styles.css` 응답에 새 버튼/선택 로직/캐시 버전이 포함됨을 확인했다.
  - `/health` 200 응답 확인.
  - 브라우저 자동 확인 도구는 `spawn setup refresh` 오류로 사용하지 못했다.

### 2026-06-12 03:25 KST - 라이브러리 불러오기 응답 지연 개선
- 목표: 이미지/영상 탭의 `라이브러리에서 불러오기` 선택창이 전체 라이브러리 스캔과 20MB대 JSON 응답 때문에 10초 이상 멈추는 문제를 줄인다.
- 확인:
  - 기존 `/api/library`는 3,200개 이상 항목과 약 21MB 응답을 매번 만들고, `metadata.json` 전체 읽기/파일 존재 확인/이미지·영상 폴더 재귀 스캔/정렬을 수행했다.
  - 선택창은 실제로 이미지 또는 영상 한쪽만 필요하지만 기존에는 전체 목록을 받은 뒤 프론트에서 필터링했다.
- 변경:
  - `app.py`: 라이브러리 조회 캐시를 추가하고, `media_type`, `scan`, `compact`, `limit`, `offset`, `refresh` 파라미터를 지원하도록 `/api/library`를 확장했다.
  - `app.py`: 선택창/라이브러리 화면에 필요한 필드만 반환하는 compact item 응답을 추가해 큰 `extra` payload 전송을 줄였다.
  - `app.py`: 새 결과 저장, 즐겨찾기, 삭제처럼 `write_metadata()`를 거치는 변경 후 라이브러리 캐시를 무효화하도록 했다.
  - `static/app.js`: 라이브러리 선택창을 누르면 모달을 즉시 열고, `/api/library?media_type=...&scan=0&compact=1&limit=...` 경량 조회로 필요한 타입만 불러오도록 변경했다.
  - `static/app.js`: 앱 시작 시 전체 라이브러리 자동 로드를 제거하고, 라이브러리 탭이 활성화된 경우에만 전체 라이브러리 갱신을 수행하도록 했다.
  - 정적 캐시 버전을 `20260612-v3-70` / `webgui-shell-v3-70`으로 갱신하고 `WebGUI.v3.exe`를 재빌드했다.
- 검증:
  - `node --check static/app.js` 통과.
  - `python -m py_compile app.py work/run_server.py` 통과.
  - Flask test client 기준 선택창용 image compact 요청: 첫 호출 약 1.26초, 캐시 재호출 약 0.003초, 응답 약 392KB.
  - 실행 서버 기준 `curl`: 선택창용 image compact 첫 호출 1.52초, 캐시 재호출 0.006초, 응답 392,022 bytes.
  - 실행 서버 기준 전체 라이브러리 compact 첫 호출 5.97초, 캐시 재호출 0.052초, 응답 2,547,789 bytes.
  - 서버를 새 코드로 재시작했고 `/health` 200 및 7863 LISTENING PID 32736 확인.
  - Browser 플러그인 검증은 기존과 같은 `spawn setup refresh` 오류로 진행하지 못했다.

### 2026-06-12 04:29 KST - 릴리즈 라이브러리 불러오기 성능 개선 반영
- 목표: 원본 앱에 적용한 라이브러리 선택창 경량 조회/캐시 개선을 Hermes-only 릴리즈 전달본에도 반영한다.
- 변경:
  - `tools/build_release_no_official.py`: 릴리즈 정적 스탬프를 `20260612-release-hermes-04`로 올리고, 원본 `20260612-v3-70` / `webgui-shell-v3-70`도 릴리즈 스탬프로 치환하도록 보정했다.
  - `release/WebGrok-v3-Hermes`: 빌드 스크립트로 릴리즈 폴더를 재생성해 `LIBRARY_CACHE`, compact `/api/library`, 선택창용 `fetchPickerItems()` 개선이 포함되도록 했다.
  - `release/WebGrok-v3-Hermes-20260611.zip`: 최신 릴리즈 폴더 기준으로 다시 압축했다.
- 검증:
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 릴리즈 Flask test client로 `/`, `/health`, `/api/library?media_type=image&scan=0&compact=1&limit=20` 응답을 확인했다.
  - 릴리즈 폴더에서 `20260612-release-hermes-04`, `LIBRARY_CACHE`, `fetchPickerItems`, `compact=1` 포함을 확인했다.
  - zip 내부에 `__pycache__`, `.webgork-private`, `.chrome`, OAuth token류가 포함되지 않았음을 확인했다.

### 2026-06-12 09:04 KST - 릴리즈 사용자 매뉴얼 추가
- 목표: Hermes-only 릴리즈 전달본을 받은 사용자가 기능별 사용법을 확인할 수 있는 한국어 사용자 매뉴얼을 제공한다.
- 변경:
  - `docs/USER_MANUAL_HERMES_RELEASE.md`: 실행 방법, 설정, 이미지 생성, 이미지 편집, 이미지→영상, 영상 연장/프레임 연장, 영상 편집, 망가 배치, 프롬프트, 템플릿, 라이브러리, 작업 큐, 오류 확인, 데이터 백업, 릴리즈 제외 기능을 설명하는 사용자 매뉴얼을 추가했다.
  - `tools/build_release_no_official.py`: 릴리즈 빌드 시 매뉴얼을 `release/WebGrok-v3-Hermes/USER_MANUAL.md`로 복사하고 `README_RELEASE.md`의 Included 목록에 표시하도록 했다.
  - `release/WebGrok-v3-Hermes-20260611.zip`: `USER_MANUAL.md` 포함 상태로 다시 압축했다.
- 검증:
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 릴리즈 Flask test client로 `/`, `/health`, `/api/library?media_type=image&scan=0&compact=1&limit=20` 응답을 확인했다.
  - zip 내부에 `README_RELEASE.md`와 `USER_MANUAL.md`가 포함되고, `__pycache__`, `.webgork-private`, `.chrome`, OAuth token류가 포함되지 않았음을 확인했다.

### 2026-06-12 22:35 KST - 릴리즈 사용자 매뉴얼 공홈 관련 문구 제거
- 목표: Hermes-only 릴리즈 사용자 매뉴얼에서 릴리즈 사용자에게 필요 없는 공홈/quota/쿠키/CDP/웹 세션 관련 설명을 완전히 제거한다.
- 변경:
  - `docs/USER_MANUAL_HERMES_RELEASE.md`: 도입부의 공홈 quota/쿠키/Chrome 세션 문구, 영상 연장 설명의 공홈 quota 문구, 릴리즈 제외 기능 섹션을 제거했다.
  - `release/WebGrok-v3-Hermes`: 빌드 스크립트로 릴리즈 폴더를 재생성해 `USER_MANUAL.md`에 수정 내용을 반영했다.
  - `release/WebGrok-v3-Hermes-20260611.zip`: 최신 릴리즈 폴더 기준으로 다시 압축했다.
- 검증:
  - 원본/릴리즈/zip 내부 `USER_MANUAL.md`에서 `공식홈`, `공홈`, `quota`, `쿠키`, `CDP`, `웹 세션`, `브라우저 자동화`, `Chrome 세션`, `Chrome 프로필` 검색 결과가 없음을 확인했다.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 릴리즈 Flask test client로 `/`, `/health`, `/api/library?media_type=image&scan=0&compact=1&limit=20` 응답을 확인했다.

### 2026-06-12 22:49 KST - 크롬 앱 종료 시 자체 서버 종료
- 목표: 크롬 앱 EXE로 실행한 경우 사용자가 앱 창을 닫으면 런처가 직접 띄운 서버도 함께 종료되도록 한다.
- 변경:
  - `tools/WebGuiLauncher.cs`: 서버가 꺼져 있을 때만 `StartServer()`의 `Process`를 보관하고, 크롬 앱 프로세스 종료를 기다린 뒤 해당 서버 프로세스를 종료하도록 변경했다.
  - `tools/WebGuiLauncher.cs`: 크롬 앱 실행 시 전용 `--user-data-dir=.webgui-chrome-app-profile`을 사용해 앱 창 프로세스를 추적할 수 있게 했다.
  - `tools/build_release_no_official.py`: 릴리즈 `WEBGROK_CHROME_APP.exe` 생성 코드에도 같은 서버 추적/종료 흐름을 적용하고, 릴리즈 전용 `.webgrok-chrome-app-profile`을 사용하도록 했다.
  - 이미 실행 중인 서버에 붙은 경우에는 런처가 서버를 새로 띄운 것이 아니므로 크롬 앱을 닫아도 기존 서버를 종료하지 않도록 분리했다.
  - `WebGUI.v3.exe`, `release/WebGrok-v3-Hermes/WEBGROK_CHROME_APP.exe`, `release/WebGrok-v3-Hermes-20260611.zip`을 재생성했다.
- 검증:
  - `tools/build_webgui_launcher.ps1`로 원본 `WebGUI.v3.exe` 재빌드 통과.
  - `python -m py_compile tools/build_release_no_official.py` 통과.
  - `python tools/build_release_no_official.py`로 Hermes-only 릴리즈 폴더 재생성 통과.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - `git diff --check` 통과.
  - 릴리즈 zip 안에 `__pycache__`, `.webgork-private`, 크롬 앱 프로필 폴더, OAuth 토큰/쿠키/공식홈 세션 파일이 포함되지 않았음을 확인했다.

### 2026-06-12 22:58 KST - 릴리즈 연결 상태 버튼 캐시 문제 수정
- 목표: Hermes-only 릴리즈에서 설정의 연결 상태 패널에 있는 `인증` 버튼이 보이지만 동작하지 않는 문제를 수정한다.
- 확인:
  - 릴리즈 HTML에는 `startHermesAuth` 버튼이 있고, 릴리즈 JS에도 `/api/hermes/auth/start` 바인딩이 남아 있었다.
  - 릴리즈 `app.py`에도 `/api/hermes/auth/status`, `/api/hermes/auth/start`, `/api/hermes/auth/submit`, `/api/hermes/auth/logout`, `/api/hermes/auth/reset` 라우트가 유지되어 있었다.
  - 문제 원인은 릴리즈 정적 버전이 `20260612-release-hermes-04`로 유지되어 Chrome 앱이 이전 `app.js` 캐시를 사용할 수 있는 상태였던 것으로 판단했다.
- 변경:
  - `tools/build_release_no_official.py`: 릴리즈 정적 버전을 `20260612-release-hermes-05`로 올려 HTML, JS, 앱 URL 캐시를 무효화했다.
  - `tools/build_release_no_official.py`: 릴리즈 Chrome 앱 프로필을 릴리즈 폴더 내부가 아니라 `%LOCALAPPDATA%\WebGrok\v3-Hermes\chrome-app-profile`에 만들도록 변경해 재빌드 시 릴리즈 폴더가 잠기는 문제를 막았다.
  - `release/WebGrok-v3-Hermes`, `release/WebGrok-v3-Hermes-20260611.zip`을 다시 생성했다.
- 검증:
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 릴리즈 Flask test client로 `/api/hermes/auth/status` 200 응답과 `ok=True`를 확인했다.
  - 릴리즈 zip 안에 `__pycache__`, `.webgork-private`, 크롬 앱 프로필 폴더, OAuth 토큰/쿠키/공식홈 세션 파일이 포함되지 않았음을 확인했다.
  - `git diff --check` 통과.

### 2026-06-12 23:12 KST - Hermes-only 릴리즈 첫 실행 부트스트랩 추가
- 목표: 릴리즈 전달본을 받은 사용자의 PC에 Python, Hermes Agent, Node.js가 없어도 `WEBGROK_CHROME_APP.exe` 또는 배치 실행만으로 필요한 의존성을 준비하고 앱을 열 수 있게 한다.
- 변경:
  - `tools/build_release_no_official.py`: `WEBGROK_BOOTSTRAP.bat` 생성 로직을 추가했다. 첫 실행 시 Python 탐색, `winget` 기반 Python 설치 시도, 앱 `requirements.txt` 설치, `.hermes-venv` 생성, `hermes-agent[cli]==0.15.1` 설치를 수행한다.
  - `tools/build_release_no_official.py`: Node.js/npx가 없으면 `winget install OpenJS.NodeJS.LTS`를 시도하도록 추가했다. Node 설치가 실패해도 Hermes 기본 기능은 실행 가능하도록 경고만 남긴다.
  - `tools/build_release_no_official.py`: 릴리즈 Chrome 앱 런처가 서버 시작 전에 부트스트랩 필요 여부를 확인하고, 필요하면 설치 창을 띄워 `WEBGROK_BOOTSTRAP.bat` 완료를 기다리도록 했다.
  - `tools/build_release_no_official.py`: `RUN_WEBGROK_HERMES_ONLY.bat`도 같은 부트스트랩을 먼저 호출하도록 변경했다.
  - `tools/build_release_no_official.py`: 릴리즈 정적 버전을 `20260612-release-hermes-06`으로 올렸다.
  - `docs/USER_MANUAL_HERMES_RELEASE.md`: 첫 실행 자동 설치 흐름, `WEBGROK_BOOTSTRAP.bat`, Hermes 인증 절차 안내를 반영했다.
  - `release/WebGrok-v3-Hermes`, `release/WebGrok-v3-Hermes-20260611.zip`을 다시 생성했다.
- 검증:
  - `python -m py_compile tools/build_release_no_official.py` 통과.
  - `python tools/build_release_no_official.py`로 Hermes-only 릴리즈 폴더 재생성 통과.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 릴리즈 Flask test client로 `/health`, `/api/hermes/auth/status` 200 응답을 확인했다.
  - 릴리즈 zip 안에 `WEBGROK_BOOTSTRAP.bat`, `WEBGROK_CHROME_APP.exe`, `RUN_WEBGROK_HERMES_ONLY.bat`, `README_RELEASE.md`, `USER_MANUAL.md`가 포함됨을 확인했다.
  - 릴리즈 zip 안에 `__pycache__`, `.webgork-private`, `.hermes-venv`, 크롬 앱 프로필 폴더, OAuth 토큰/쿠키/공식홈 세션 파일이 포함되지 않았음을 확인했다.
  - `git diff --check` 통과.

### 2026-06-12 23:37 KST - 릴리즈 Python 탐지 보강
- 목표: Python이 설치된 PC에서도 릴리즈 첫 실행 부트스트랩이 `winget` Python 설치로 넘어가는 문제를 막고, 사용자 안내 문구를 명확히 한다.
- 확인:
  - 테스트 PC의 PATH에는 `Microsoft\WindowsApps\python.exe`/`py.exe` 별칭이 먼저 잡히고, 실제 Python은 `%LOCALAPPDATA%\Python\bin\python.exe` 및 `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`에 있었다.
  - 기존 릴리즈 로그에는 `winget install --id Python.Python.3.12`가 실행된 흔적이 있어, Python 탐지가 기존 설치를 놓친 상태였음을 확인했다.
- 변경:
  - `tools/build_release_no_official.py`: `WEBGROK_BOOTSTRAP.bat`, `RUN_WEBGROK_HERMES_ONLY.bat`, 릴리즈 `WEBGROK_CHROME_APP.exe` 생성 코드의 Python 탐지를 같은 기준으로 보강했다.
  - `tools/build_release_no_official.py`: `%LOCALAPPDATA%\Python\bin\python.exe`와 Program Files x86 Python 경로를 후보에 추가하고, 후보 실행 시 실제 Python 3.11 이상인지 검증하도록 했다.
  - `tools/build_release_no_official.py`: `Microsoft\WindowsApps`의 `python.exe`/`py.exe` 별칭은 실제 Python으로 인정하지 않도록 제외했다.
  - `tools/build_release_no_official.py`: 선택된 Python 명령을 `work\python-cmd.txt`에 남기도록 했다.
  - `tools/WebGuiLauncher.cs`: 원본 Chrome 앱 런처도 같은 Python 탐지 기준으로 보강했다.
  - `docs/USER_MANUAL_HERMES_RELEASE.md`: 기존 Python은 재사용하고, 사용 가능한 Python 3.11 이상이 없을 때만 Python 설치를 시도한다고 명확히 적었다.
  - `WebGUI.v3.exe`, `release/WebGrok-v3-Hermes`, `release/WebGrok-v3-Hermes-20260611.zip`을 다시 생성했다.
- 검증:
  - `python -m py_compile tools/build_release_no_official.py` 통과.
  - `python tools/build_release_no_official.py`로 릴리즈 Chrome 앱 EXE 컴파일 및 릴리즈 폴더 재생성 통과.
  - `powershell -ExecutionPolicy Bypass -File tools\build_webgui_launcher.ps1`로 원본 `WebGUI.v3.exe` 재생성 통과.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과 후 생성된 릴리즈 `__pycache__`를 제거했다.
  - 릴리즈 zip 안에 `WEBGROK_BOOTSTRAP.bat`, `WEBGROK_CHROME_APP.exe`, `README_RELEASE.md`, `USER_MANUAL.md`가 포함됨을 확인했다.
  - 릴리즈 zip 안에 `__pycache__`, `.webgork-private`, `.hermes-venv`, 크롬 앱 프로필 폴더, 쿠키/공식홈 세션 파일이 포함되지 않았음을 확인했다.
  - `git diff --check` 통과.

### 2026-06-12 23:47 KST - 릴리즈 Hermes Agent 재사용 처리
- 목표: Hermes Agent가 이미 설치된 PC에서도 릴리즈 첫 실행 부트스트랩이 불필요하게 `.hermes-venv` 설치를 다시 시도하는 문제를 막는다.
- 확인:
  - 기존 `WEBGROK_BOOTSTRAP.bat`은 릴리즈 폴더의 `.hermes-venv\Scripts\hermes.exe`만 기준으로 Hermes 설치 여부를 판단하고 있었다.
  - 앱 런타임은 `shutil.which("hermes")` 후보를 일부 보지만, 부트스트랩과 EXE 런처의 필요 여부 판단이 기존 Hermes 설치를 충분히 인정하지 않았다.
- 변경:
  - `tools/build_release_no_official.py`: 부트스트랩에 `:find_hermes`/`:accept_hermes`를 추가해 기존 `hermes.exe`를 먼저 탐색하도록 했다.
  - `tools/build_release_no_official.py`: `%LOCALAPPDATA%\Python\bin`, Python `Scripts`, pipx venv, `%USERPROFILE%\.local\bin`, PATH의 `hermes.exe`를 후보로 추가했다.
  - `tools/build_release_no_official.py`: 기존 Hermes를 찾으면 `work\hermes-exe.txt`에 경로를 저장하고, Hermes가 없을 때만 `.hermes-venv`를 생성하도록 했다.
  - `tools/build_release_no_official.py`: 릴리즈 Chrome 앱 런처의 `NeedsBootstrap()`도 `work\hermes-exe.txt`, 기존 Hermes 후보, PATH 후보를 인정하도록 했다.
  - `app.py`: `work\hermes-exe.txt`와 표준 사용자 설치 경로의 Hermes 후보를 추가해 부트스트랩이 찾은 기존 Hermes를 앱이 그대로 사용하도록 했다.
  - `docs/USER_MANUAL_HERMES_RELEASE.md`: 기존 Hermes Agent가 있으면 재사용하고, 없을 때만 릴리즈 `.hermes-venv`에 설치한다고 명확히 적었다.
  - `release/WebGrok-v3-Hermes`, `release/WebGrok-v3-Hermes-20260611.zip`을 다시 생성했다.
- 검증:
  - `python -m py_compile app.py tools/build_release_no_official.py release/WebGrok-v3-Hermes/app.py` 통과.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - 릴리즈 생성 결과에 `Using existing Hermes Agent`, `work\hermes-exe.txt`, `release-hermes-08` 반영을 확인했다.
  - 릴리즈 zip 안에 `WEBGROK_BOOTSTRAP.bat`, `WEBGROK_CHROME_APP.exe`, `README_RELEASE.md`, `USER_MANUAL.md`가 포함됨을 확인했다.
  - 릴리즈 zip 안에 `__pycache__`, `.webgork-private`, `.hermes-venv`, 크롬 앱 프로필 폴더, 쿠키/공식홈 세션 파일이 포함되지 않았음을 확인했다.
  - `git diff --check` 통과.

### 2026-06-12 23:21 KST - 릴리즈 설치/실행 실패 이유 즉시 표시
- 목표: 릴리즈 사용자가 설치 또는 실행 실패 시 로그 파일을 직접 찾아 열지 않아도 실패 원인을 바로 확인할 수 있게 한다.
- 변경:
  - `tools/build_release_no_official.py`: `WEBGROK_BOOTSTRAP.bat` 실패 지점마다 `work/bootstrap.log` 최근 40줄을 콘솔에 출력하도록 `:show_log` 헬퍼를 추가했다.
  - `tools/build_release_no_official.py`: `RUN_WEBGROK_HERMES_ONLY.bat`에서 부트스트랩 실패 또는 서버 시작 실패 시 각각 `work/bootstrap.log`, `work/server-runner.log` 최근 50줄을 콘솔에 표시하도록 했다.
  - `tools/build_release_no_official.py`: 릴리즈 `WEBGROK_CHROME_APP.exe` 런처가 부트스트랩/서버 시작 실패 팝업에 `bootstrap.log`, `server-runner.log` 최근 내용을 함께 표시하도록 C# 생성 코드를 보강했다.
  - `docs/USER_MANUAL_HERMES_RELEASE.md`: 필요한 구성요소(Python, 인터넷 연결, Hermes Agent, Node.js/npx, Chrome)와 실패 시 확인 위치(`work/bootstrap.log`, `work/server-runner.log`)를 추가했다.
  - `release/WebGrok-v3-Hermes`, `release/WebGrok-v3-Hermes-20260611.zip`을 다시 생성했다.
- 검증:
  - `python -m py_compile tools/build_release_no_official.py` 통과.
  - `python tools/build_release_no_official.py`로 릴리즈 Chrome 앱 EXE 컴파일 및 릴리즈 폴더 재생성 통과.
  - `node --check release/WebGrok-v3-Hermes/static/app.js` 통과.
  - `python -m py_compile release/WebGrok-v3-Hermes/app.py tools/build_release_no_official.py` 통과.
  - 릴리즈 zip 안에 `WEBGROK_BOOTSTRAP.bat`, `WEBGROK_CHROME_APP.exe`, `RUN_WEBGROK_HERMES_ONLY.bat`, `README_RELEASE.md`, `USER_MANUAL.md`가 포함됨을 확인했다.
  - 릴리즈 zip 안에 `__pycache__`, `.webgork-private`, `.hermes-venv`, 크롬 앱 프로필 폴더, OAuth 토큰/쿠키/공식홈 세션 파일이 포함되지 않았음을 확인했다.
  - `git diff --check` 통과.
