# WebGUI V3 재현용 Codex 레시피

이 문서는 다른 Codex 사용자에게 전달해서, 새 작업공간에서 현재 WebGUI V3와 거의 유사한 웹앱을 만들도록 지시하기 위한 레시피입니다.

개인 OAuth 토큰, API 키, 세션 쿠키, 공유 client_id, 생성 결과물, 로컬 저장 경로는 포함하지 않습니다. 인증은 반드시 사용자가 직접 소유하거나 합법적으로 사용할 수 있는 계정/프록시/키를 통해 구성합니다.

## 붙여넣기용 원샷 프롬프트

아래 블록을 새 Codex 작업공간에서 그대로 붙여넣으면 됩니다.

```text
Python Flask 백엔드와 정적 HTML/CSS/Vanilla JS 프론트엔드로, 로컬에서 실행되는 다크 테마 AI 생성 WebGUI를 만들어줘. 빌드 도구 없이 실행 가능해야 하며, Windows 사용자가 `run_webgork.bat` 또는 `run_webgork_app.bat`를 눌러 실행할 수 있게 구성해줘.

앱 이름은 `WebGUI.v3`로 하고, 전체 UI는 Grok 공식 웹앱의 다크한 느낌을 참고하되 그대로 복제하지 말고 독립적인 세련된 작업 도구처럼 만들어줘. UI는 두 줄 헤더 구조로 만든다. 첫 번째 줄에는 왼쪽 `WebGUI.v3` 타이틀, 오른쪽에는 Hermes 연결 상태, Codex/OpenAI 이미지 프록시 연결 상태, credit 잔량 배터리 바를 작게 표시한다. 두 번째 줄에는 아이콘 탭만 둔다. 탭은 텍스트 대신 아이콘으로 표시하고, 마우스 오버 1초 뒤 툴팁이 뜨게 한다.

주요 화면 레이아웃은 다음과 같다.
1. 좌측에는 세로형 작업 큐 레일을 둔다. 썸네일 카드가 위아래로 스크롤되고, 각 작업의 상태/진행률/정리 버튼을 보여준다.
2. 중앙에는 결과 미리보기 패널을 둔다. 이미지/영상은 패널보다 넘치지 않게 contain 방식으로 맞춘다. 세로 영상은 높이에 맞추고, 가로 영상은 너비에 맞추며, 브라우저 하단에 영상 컨트롤이 잘리지 않게 한다.
3. 우측에는 현재 탭의 컨트롤 패널을 둔다. 우측 패널만 세로 스크롤 가능하게 하고, 결과 미리보기는 스크롤 없이 화면 높이에 맞춘다.
4. 화면이 좁으면 프롬프트/컨트롤이 위, 결과가 아래로 자연스럽게 쌓이게 한다.
5. 흰색 버튼은 너무 튀지 않도록 회색 톤의 다크 UI 버튼으로 만든다.

기능 탭은 다음을 구현한다.
1. 이미지 생성
   - 프롬프트 입력
   - 결과 비율 선택: auto/original, 2:3, 3:2, 1:1, 9:16, 16:9
   - provider/model 선택: Grok/xAI 계열, Codex 또는 ChatGPT OAuth 로컬 이미지 프록시 계열
   - Grok 이미지 생성은 가능하다면 1k/2k 옵션을 둔다. 지원하지 않는 조합이면 임의로 다른 모델로 fallback하지 말고 오류 팝업을 띄운다.

2. 이미지 편집
   - 파일 업로드, 드래그앤드랍, 클립보드 붙여넣기, 라이브러리에서 불러오기 지원
   - 여러 장 첨부 가능
   - 첫 번째 이미지를 메인 이미지로 보여주고, 나머지는 우측 세로 썸네일로 표시
   - 썸네일에는 X 삭제 버튼, 클릭 시 테두리 없는 확대 모달
   - 초기화 버튼은 입력 이미지와 결과 미리보기 모두 초기화
   - 다중 이미지 처리 방식 선택:
     - 여러 이미지를 API에 각각 첨부
     - 여러 이미지를 한 장으로 이어붙인 뒤 편집 요청
   - 실험 해상도 옵션: auto, 1k, 2k

3. 이미지 -> 영상
   - 원본 이미지 업로드, 드래그앤드랍, 붙여넣기, 라이브러리 선택 지원
   - 영상 모델 선택
   - 해상도 선택: 지원 모델에 따라 480p/720p/기타 가능 옵션
   - 업스케일 체크박스: 체크 시 이미지 편집 2k 업스케일을 먼저 수행한 뒤 영상 생성
   - 선택한 이미지만 요청에 사용하고, 이전 편집 원본이나 숨은 reference가 딸려가지 않도록 상태를 명확히 분리

4. 공식 영상 연장
   - xAI/Grok 공식 video extension 엔드포인트 또는 사용자가 연결한 proxy를 통해 영상 연장
   - 모델 선택
   - extension length 선택
   - 공식 연장에서는 해상도 선택을 표시하지 않는다.
   - 입력 영상이 15초 이하이면 후처리 concat 없이 서버 결과물을 그대로 저장한다.
   - 입력 영상이 15초 초과이면 앞부분과 마지막 15초를 나눈다. 마지막 15초만 연장 요청에 보내고, 결과로 받은 전체 연장 영상 앞에 잘라둔 앞부분을 붙여 최종 영상으로 저장한다.
   - 오디오는 가능한 보존한다. 서버 결과물이 무음이면 원본 오디오 보존 가능 여부를 로그에 명확히 남긴다.

5. 프레임 연장
   - 원본 영상의 마지막 프레임을 캡처
   - 캡처 이미지를 이미지 편집 2k 업스케일로 개선
   - 개선된 마지막 프레임으로 새 영상 생성
   - 원본 영상 뒤에 새 영상을 이어붙여 저장
   - 음소거 체크박스는 일반 체크박스와 `음소거` 텍스트가 한 줄에 있는 직관적인 UI로 만든다.
   - 음소거 해제 시 원본/연장 구간 오디오를 최대한 보존한다.
   - 영상 생성 시 사용한 원본 reference 이미지 경로가 존재하면 중복 파일을 새로 만들지 말고 원본 경로를 메타데이터에 참조한다.

6. 그림 프롬프트
   - 이미지에서 프롬프트를 추출하는 화면
   - 결과 미리보기 패널은 과하게 크게 잡지 말고 적당한 크기의 텍스트 패널로 둔다.
   - 버튼은 `복사` 하나만 둔다.
   - 참고 비율 선택 항목은 넣지 않는다.

7. 망가 실사화 + 역식
   - 수십~수백 장의 이미지 업로드
   - 최대 500장까지 등록 가능
   - 작업 큐 병렬 처리 수는 50개까지 지원하되 설정 가능하게 만든다.
   - 항목마다 X 삭제 버튼
   - 전체 취소 버튼
   - 진행률은 실제 완료 개수 기반으로 `17 / 200 진행중`처럼 표시
   - 자동 프롬프트를 제공한다:
     - 만화/망가 이미지를 실사 영화풍 이미지로 변환
     - 원본 패널 구성, 캐릭터 정체성, 포즈, 의상, 구도, 감정 유지
     - 말풍선/캡션/효과음을 한국어로 번역하고 자연스럽게 식자
   - 저장 파일명은 반드시 원본 파일명을 보존한다. 예: `grok_trans_original-file-name.png`
   - 숫자 prefix 때문에 순서가 뒤섞이지 않게 한다.
   - 저장 위치는 일반 image 폴더와 분리된 `translated` 또는 `manga-translated` 폴더를 사용하고, 라이브러리에는 함께 표시한다.

8. 로컬 영상 편집기
   - 라이브러리 영상 또는 업로드 영상을 여러 개 추가
   - 클립 카드를 세로 또는 리스트 형태로 보여준다.
   - 드래그로 순서 변경
   - 위/아래 이동 버튼
   - 각 클립별 start/end 초 단위 입력
   - 현재 재생 위치를 시작/끝으로 찍는 버튼
   - 붙이기, 자르기, fade in/out, crossfade 전환, 음소거, 오디오 보존 옵션
   - FFmpeg를 사용해서 처리
   - 결과는 라이브러리 video 폴더에 저장

9. 라이브러리
   - 저장 경로 아래 `image`, `video`, `uploads`, `thumbnails`, `manga-translated` 등을 스캔
   - 메타데이터 JSON을 영구 저장
   - 파일만 남고 메타데이터가 없는 항목도 라이브러리에 표시하되, 프롬프트는 `메타데이터 없음`처럼 처리
   - 즐겨찾기 상태를 영구 저장하고 작은 별 아이콘으로 표시
   - 즐겨찾기 on/off 상태가 시각적으로 명확히 달라야 한다.
   - 이미지/영상/전체 필터 드롭다운
   - 저장 위치 파일 브라우저 열기 버튼
   - 각 아이템의 점 3개 메뉴:
     - 파일 복사
     - 파일 경로 복사
   - 프롬프트는 카드에서 3줄까지만 표시하고 말줄임
   - 프롬프트 영역 클릭 시 테두리 없는 모달로 전체 프롬프트 표시
   - 모달 안 프롬프트는 텍스트 선택 가능
   - 모달 아래 `프롬프트 복사` 버튼
   - 이미지 클릭 또는 확대 아이콘 클릭 시 테두리 없는 이미지 확대 모달
   - 영상 클릭 또는 재생 아이콘 클릭 시 영상 재생 모달
   - 영상은 자동 repeat
   - 영상 썸네일은 1초쯤 프레임 이미지로 생성하고, 정사각형 썸네일로 표시
   - 라이브러리 선택 모달은 외부 클릭, 확대 모달, 재생 모달 이벤트가 서로 꼬이지 않도록 z-index와 event propagation을 분리
   - 선택 체크박스 직접 클릭 시 안정적으로 on/off
   - 체크박스를 드래그하면 사각 선택 영역 안의 아이템들이 선택/해제되도록 구현

10. 설정
   - Provider 패널:
     - Hermes xAI OAuth proxy 연결 상태
     - Hermes 인증 시작/로그아웃
     - Codex/ChatGPT OAuth 이미지 프록시 연결 상태
     - Codex 프록시 시작 또는 상태 확인
   - API 키 항목은 필요할 때만 접을 수 있는 고급 옵션으로 두거나 제외
   - 무료 credit 확인 패널:
     - 가능하면 OAuth 세션으로 `https://cli-chat-proxy.grok.com/v1/billing`을 호출해 `config.monthlyLimit`, `config.used` 기반으로 잔량 퍼센트 표시
     - 실패하면 Grok usage 페이지로 여는 버튼 제공
   - 저장 경로 패널:
     - 저장 폴더 직접 입력
     - Windows 파일 브라우저로 선택
     - 적용 시 `image`, `video`, `uploads`, `thumbnails` 폴더 자동 생성
     - 저장 경로 변경 시 기존 라이브러리 파일과 메타데이터를 함께 이동

백엔드 요구사항:
- Flask 앱으로 만든다.
- `app.py` 하나에 과도하게 몰아넣어도 되지만, 너무 커지면 `services/`, `providers/`, `media/` 같은 모듈로 분리한다.
- 주요 엔드포인트:
  - `GET /`, `GET /health`
  - `POST /api/t2i`
  - `POST /api/i2i`
  - `POST /api/i2v`
  - `POST /api/v2v-extend`
  - `POST /api/v2v-frame-extend`
  - `POST /api/video-edit`
  - `POST /api/reverse-prompt`
  - `POST /api/manga-batch`
  - `GET /api/library`
  - `POST /api/library/delete`
  - `POST /api/library/favorite`
  - `GET/POST /api/settings`
  - `GET /api/provider/status`
  - `POST /api/hermes/auth/start`
  - `POST /api/hermes/auth/code`
  - `POST /api/hermes/logout`
  - `GET /api/credit/status`
- 모든 오류는 JSON으로 `{time,message,detail}` 형태를 반환한다.
- provider 요청 실패 시 서버 응답 본문을 버리지 말고 detail에 포함한다.
- content moderation, unsupported model, invalid argument, proxy not connected, content too large는 서로 구분되는 메시지로 보여준다.
- 생성/편집 완료 시 credit 상태를 refresh한다.

저장 구조:
- 기본 저장 루트는 사용자가 설정 가능하게 한다.
- 루트 아래:
  - `image/`
  - `video/`
  - `uploads/`
  - `thumbnails/`
  - `manga-translated/`
  - `metadata.json`
  - `favorites.json`
- private 상태는 앱 폴더의 `.webgork-private/`에 저장하되 release에는 포함하지 않는다.
- release 배포본에는 `.env.example`, `requirements.txt`, `README.md`, 실행 bat, 앱 코드만 포함한다.
- OAuth token, API key, session cookie, 개인 media, metadata, 로그는 release에 포함하지 않는다.

인증/프록시 원칙:
- 공유 client_id를 하드코딩하지 않는다.
- 사용자가 직접 승인하는 OAuth 흐름만 사용한다.
- Hermes xAI OAuth proxy는 선택 기능으로 둔다. 설치되어 있지 않으면 설치 안내와 시작 버튼을 보여준다.
- Codex/ChatGPT OAuth 이미지 프록시는 로컬 프록시가 있을 때만 사용한다. 연결되지 않았으면 Grok으로 자동 fallback하지 말고 명확한 오류를 띄운다.
- API 키 방식은 선택적 고급 옵션으로만 둔다.

큐/진행률:
- 일반 생성 큐는 최대 30개 병렬 처리.
- 망가 실사화/역식 큐는 최대 50개 병렬 처리, 최대 500장 등록.
- 서버가 실제 progress를 주면 그대로 표시.
- 실제 progress를 알 수 없으면 indeterminate 로딩 UI 표시.
- 배치 작업은 완료 개수 기반으로 진행률 표시.

프론트엔드 구현 주의:
- CSS 캐시 문제를 피하려면 정적 파일 query version을 올린다.
- 서비스워커를 넣었다면 버전을 함께 올리고, 업데이트/새로고침 동작을 제공한다.
- select/dropdown은 다크 테마에서도 글자가 잘 보여야 한다.
- 모달은 z-index 계층을 명확히 나눈다:
  - 라이브러리 선택 모달
  - 이미지 확대 모달
  - 영상 재생 모달
  - 오류 로그 모달
- 모달 내부 클릭은 외부 클릭 닫기 이벤트로 전파되지 않게 한다.
- 긴 텍스트는 버튼이나 카드 밖으로 넘치지 않게 한다.

실행 파일:
- `requirements.txt`
- `run_webgork.bat`: 의존성 설치 후 Flask 실행
- `run_webgork_app.bat`: Flask 실행 후 Chrome `--app=http://127.0.0.1:7863` 모드로 독립 창 실행
- 가능하면 `run_webgork_all.bat`:
  - Python 의존성 확인
  - Hermes proxy 상태 확인/시작
  - Codex 이미지 프록시 상태 확인/시작
  - Flask 실행
  - Chrome app 창 열기
  - 단, OAuth 승인 자체는 사용자가 브라우저에서 직접 수행해야 한다.

검증 체크리스트:
1. `python -m py_compile app.py`
2. Flask test client로 `/`와 `/health` 확인
3. 저장 루트가 없을 때 자동 생성 확인
4. 이미지 생성/편집 요청 실패 시 오류 팝업에 detail 표시 확인
5. 라이브러리 스캔/필터/즐겨찾기/프롬프트 모달 확인
6. 영상 썸네일 생성과 영상 재생 모달 확인
7. 영상 편집 trim/concat/fade/crossfade smoke test
8. 공식 연장 15초 이하 영상은 concat 없이 저장되는지 확인
9. 공식 연장 15초 초과 영상은 앞부분 + 서버 결과 concat 구조인지 확인
10. release 폴더에 private token/media/log가 포함되지 않았는지 확인

마지막으로 README.md에 실행 방법, 인증 방법, 저장 경로 변경, release 배포 시 제외해야 할 항목을 한국어로 정리해줘.
```

## 세부 설계 메모

### 권장 기술 스택

- Backend: Python 3.11 이상, Flask, requests, Pillow
- Video: FFmpeg/ffprobe
- Frontend: HTML, CSS, Vanilla JavaScript
- Packaging: Windows `.bat` launcher
- Optional proxy:
  - Hermes xAI OAuth proxy
  - Codex/ChatGPT OAuth image proxy

Flask + 정적 파일 구조를 추천하는 이유는 배포가 단순하고, 다른 사용자가 Node 빌드 체인 없이 바로 고치기 쉽기 때문입니다.

### 파일 구조 예시

```text
project/
  app.py
  requirements.txt
  README.md
  CODEX_REBUILD_RECIPE.md
  .env.example
  run_webgork.bat
  run_webgork_app.bat
  static/
    app.js
    styles.css
    service-worker.js
  templates/
    index.html
  media-library/
    image/
    video/
    uploads/
    thumbnails/
    manga-translated/
    metadata.json
    favorites.json
  .webgork-private/
    settings-local.json
    tokens/
  release/
```

`media-library/`, `.webgork-private/`, 로그 파일은 일반 배포본에서 제외합니다.

### Provider 설계

provider는 앱 로직과 분리하는 편이 좋습니다. 최소한 다음처럼 내부 함수를 나눕니다.

```text
generate_image(provider, model, prompt, options)
edit_image(provider, model, prompt, images, options)
generate_video(provider, model, prompt, image, options)
extend_video(provider, model, video, options)
reverse_prompt(provider, image)
```

지원하지 않는 provider/model/옵션 조합은 자동으로 다른 provider로 바꾸지 않습니다. 사용자가 Grok 모델을 선택했는데 Codex 프록시가 실패했다거나, GPT 모델을 선택했는데 Grok으로 바뀌는 동작은 만들지 않습니다.

### 메타데이터 보존

생성 결과를 저장할 때마다 metadata에 다음 값을 남깁니다.

```json
{
  "id": "stable-id",
  "type": "image",
  "file_path": "absolute-or-root-relative-path",
  "created_at": "ISO-8601",
  "provider": "grok|hermes|codex|openai",
  "model": "model-name",
  "operation": "t2i|i2i|i2v|official_extend|frame_extend|reverse_prompt|manga_trans|video_edit",
  "prompt": "user prompt",
  "source_paths": [],
  "reference_paths": [],
  "aspect_ratio": "auto",
  "resolution": "720p",
  "favorite": false
}
```

파일 스캔 중 metadata가 없는 파일은 삭제하지 말고 fallback item으로 표시합니다.

### 릴리즈 검수 기준

release 폴더에 들어가면 안 되는 것:

- `.webgork-private/`
- OAuth token
- API key
- 쿠키
- 사용자 media 결과물
- `metadata.json`
- 로그 파일
- 개인 저장 경로가 박힌 설정 파일

release 폴더에 들어가야 하는 것:

- 앱 코드
- 정적 파일
- 템플릿
- README
- requirements
- 실행 bat
- `.env.example`
- 이 레시피 문서

### Codex에게 추가로 줄 수 있는 후속 지시

UI가 깨질 때:

```text
현재 UI가 일부 화면에서 겹치거나 스크롤이 중복됩니다. 앱 로직은 건드리지 말고 CSS와 DOM 이벤트 계층만 수정해줘. 결과 미리보기는 viewport 안에 contain되고, 우측 컨트롤만 스크롤되며, 라이브러리 모달/확대 모달/영상 모달의 z-index와 외부 클릭 이벤트가 서로 간섭하지 않게 해줘.
```

프록시 연결이 안 될 때:

```text
provider fallback을 하지 말고, 선택한 provider가 연결되지 않았을 때 오류 팝업에 어떤 프록시가 꺼져 있는지 명확히 표시해줘. Hermes와 Codex 이미지 프록시 상태를 각각 독립적으로 health check하고 헤더에 작은 상태 아이콘으로 보여줘.
```

영상 연장 문제를 고칠 때:

```text
공식 연장과 프레임 연장 로직을 분리해서 검토해줘. 공식 연장은 15초 이하 입력이면 서버 결과물을 그대로 저장하고, 15초 초과일 때만 앞부분을 잘라 보관한 뒤 마지막 15초를 연장 요청하고 결과 앞에 보관분을 concat해줘. 프레임 연장은 마지막 프레임 캡처, 2k 업스케일, 새 영상 생성, 원본 뒤에 concat 순서로 동작하게 해줘.
```

라이브러리 성능이 느릴 때:

```text
라이브러리 항목이 많아졌을 때 버벅이지 않도록 썸네일 지연 로딩, 영상 태그 직접 렌더링 최소화, IntersectionObserver, metadata 캐시, 페이지네이션 또는 가상 스크롤을 적용해줘. 기능 로직은 유지하고 렌더링 성능만 개선해줘.
```

## 주의

이 레시피는 유사한 로컬 WebGUI를 만들기 위한 설계 지시서입니다. 특정 서비스의 비공개 endpoint, 공유 client_id, 타인의 OAuth 권한, 약관을 우회하는 인증 흐름을 하드코딩하는 목적으로 사용하지 않습니다. 사용자는 각 provider의 공식 문서와 약관을 확인하고, 본인이 사용할 권한이 있는 인증 방식만 연결해야 합니다.
