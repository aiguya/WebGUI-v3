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
