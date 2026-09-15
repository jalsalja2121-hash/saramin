# 채용 업무 자동화 POC — Python

## Streamlit 화면으로 실행

프로젝트는 `C:\project\saramin`에 저장되어 있습니다. 해당 폴더에서 실행하세요.

```powershell
cd C:\project\saramin
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

브라우저에서 **http://127.0.0.1:8501**을 엽니다. 종료는 터미널에서 Ctrl+C입니다.

1. **공고 분석**: 샘플 또는 직접 붙여넣은 공고를 오프라인/LLM 방식으로 분석합니다.
2. **문서 작성**: 지원자 소개·기술·경험을 입력해 문서를 저장하고 HTML/Markdown/TXT로 다운로드합니다.
3. **자동 입력**: 생성 문구를 검토·수정하고 `입력 문구 확정·저장`을 누른 뒤 로컬 자동화 또는 사람인 입력을 실행합니다.

결과는 `outputs/streamlit/<실행 ID>/`에 저장됩니다. 새 공고를 분석하면 새 폴더를 만들고 이전 문서 상태를 초기화합니다.
문구 수정은 사이트 입력 JSON에만 반영되며 보고서·TXT 원본은 유지됩니다.
화면을 새로고침하면 세션 상태는 초기화되지만 이미 저장한 파일은 유지됩니다.

사람인 실행은 **Chrome 열기 → 직접 로그인·직접 입력 폼 열기 → 화면에서 입력 확인 → 자동 입력 → 사람인에서 최종 저장 → Chrome 닫기** 순서입니다.
작업 도중 Streamlit 탭을 새로고침하거나 서버를 종료하면 열린 Chrome을 직접 닫아야 할 수 있습니다.
API 키는 기존 설명처럼 환경변수로 설정한 후 Streamlit을 실행합니다. 실제 API 호출과 실제 사람인 전송은 별도 설정·사용자 입력이 필요합니다.

Streamlit 진입점은 `streamlit_app.py`, 테마·로컬 접속 설정은 `.streamlit/config.toml`입니다.
기존 `main.py` 명령줄 실행도 그대로 사용할 수 있습니다.

**채용 공고 분석 → 지원 문서 작성 → Selenium 사이트 입력**을 각각 실행하거나 하나의 흐름으로 시연합니다.
애플리케이션 로직은 Python으로 작성했습니다. 웹 화면과 문서용 HTML/CSS는 Python에서 생성하며 JavaScript나 Node.js는 사용하지 않습니다.

## 구현 범위

| 기능 | 입력 | 동작 | 결과 |
|---|---|---|---|
| POC 1 · LLM 분석 | 채용 공고 TXT | OpenAI Responses API의 구조화 출력 / 오프라인 규칙 분석 | `analysis.json` |
| Tool 1 · 문서 작성 | 분석 JSON + 지원자 JSON | 입력한 경험을 조합한 지원 검토 보고서와 자기소개서 초안 | HTML, Markdown, TXT, 사이트 입력 JSON |
| Tool 2 · 업무 자동화 | 사이트 입력 JSON | Selenium 입력값 검증, 로컬 저장, SQLite 대조 | 입력·저장 스크린샷, 실행 결과 JSON, DB |
| 사람인 어댑터 | 검토한 사이트 입력 JSON | 로그인 후 이력서 제목·자기소개서 제목·본문 입력 | 화면에서 직접 최종 저장 |

오프라인 모드는 **LLM이 아닌 라벨 기반 파서**입니다. LLM 모드가 실패하면 오프라인으로 자동 전환하지 않습니다.
문서 작성은 사실 기반 템플릿 방식이며, 경력·성과 수치·자격증을 만들어내지 않습니다.

## 빠른 실행 (Windows PowerShell)

Python 3.10 이상과 Chrome이 필요합니다. 처음 실행할 때 Selenium Manager가 Chrome에 맞는 드라이버를 다운로드할 수 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py demo
```

이 작업 폴더에는 이미 `.venv`와 Selenium을 설치했습니다. 현재 컴퓨터에서는 마지막 명령으로 시연할 수 있습니다.

`demo`는 가상 기업·가상 지원자 데이터로 분석과 문서를 생성한 다음 임시 로컬 서버를 열고 Chrome을 화면 없이 실행합니다.
Selenium이 3개 필드에 입력하고 저장 버튼을 누릅니다. 저장 완료 화면과 SQLite 내용까지 확인한 후 브라우저와 서버를 종료합니다.
각 실행은 로컬 DB에 새 행을 추가합니다.

### 생성 파일 (`outputs/`)

- `analysis.json`: 추출 결과, 분석 모드, 공고 원문
- `report.html`: 브라우저에서 보는 지원 검토 보고서 (인쇄 가능)
- `report.md`: 편집 가능한 Markdown 문서
- `cover_letter.txt`: 자기소개서 초안
- `resume_payload.json`: 사람인 입력용 3개 필드
- `01_filled.png`, `02_saved.png`: 로컬 자동화 화면
- `automation_result.json`: 저장 번호 및 DB 검증 결과
- `submissions.sqlite3`: 로컬 등록 데이터

`pipeline`은 브라우저 없이 분석과 문서 생성만 실행합니다.

```powershell
.\.venv\Scripts\python.exe main.py pipeline
```

## 기능별 실행

### 1. 채용 공고 분석

`samples/job.txt`를 실제 공고 본문으로 바꾸거나 별도 UTF-8 TXT를 지정합니다.
공고 URL 수집은 현재 범위에 포함하지 않으며, 공고 본문을 입력받습니다.

```powershell
.\.venv\Scripts\python.exe main.py analyze --job samples/job.txt
```

실제 LLM 분석은 환경변수로 키와 구조화 출력을 지원하는 모델 ID를 설정합니다.
키는 코드나 JSON에 저장하지 않습니다. `llm` 모드에서는 지정한 공고 본문이 OpenAI API에 전송됩니다.
지원자 프로필은 LLM에 보내지 않습니다.

```powershell
$env:OPENAI_API_KEY = "발급받은 API 키"
$env:OPENAI_MODEL = "계정에서 사용할 수 있는 모델 ID"
.\.venv\Scripts\python.exe main.py analyze --mode llm --job samples/job.txt
# 또는 문서까지 한 번에
.\.venv\Scripts\python.exe main.py pipeline --mode llm
```

추출 항목: 기업명, 직무, 지역, 고용형태, 경력, 마감일, 요약, 담당업무, 필수요건, 우대사항, 기술, 확인 질문.
누락된 조건은 명시되지 않았다고 표시합니다. API 키·모델은 사용자가 제공해야 합니다.

### 2. 문서 작성

`samples/profile.json`의 `name`, `summary`, `skills`, `experiences`를 본인의 실제 정보로 바꿉니다.
문서 내 대괄호 문장은 지원 동기를 직접 보완할 부분입니다.

```powershell
.\.venv\Scripts\python.exe main.py document --analysis outputs/analysis.json --profile samples/profile.json
```

생성 후 `outputs/report.html`이나 `outputs/cover_letter.txt`를 검토합니다.
사이트에 들어갈 최종 문구는 `outputs/resume_payload.json`에서 수정할 수 있습니다.

### 3. 사람인 이력서 입력

대상: https://www.saramin.co.kr/zf_user/member/resume-manage/write?template_cd=1

```powershell
.\.venv\Scripts\python.exe main.py saramin --payload outputs/resume_payload.json
```

1. 터미널에 표시된 입력 내용을 검토하고 `INSERT`를 입력합니다.
2. 새 Chrome 창에서 직접 로그인합니다. 일반 Chrome의 로그인 세션을 복사하지 않습니다.
3. 지정한 이력서 작성 페이지에서 **자기소개서 → 추가 → 직접 입력하기**를 선택합니다.
4. 터미널에서 Enter를 누르면 **이력서 제목, 자기소개서 제목, 자기소개서 본문**을 자동 입력하고 값이 일치하는지 확인합니다.
5. 브라우저에서 문서를 검토한 뒤 **자기소개서 저장 → 작성완료**를 직접 선택합니다.
6. 작업을 마친 뒤 터미널에서 Enter를 누르면 Chrome을 종료합니다.

`saramin_result.json`의 `filled_not_submitted`는 입력 검증만 완료했다는 뜻입니다. 사람인 저장 성공을 의미하지 않습니다.
입력 중 사이트 자체의 임시 저장이 발생할 수 있어, 입력 전 실제 전송 내용을 보여줍니다.
샘플 가상 지원자 정보는 실제 계정에 입력하지 말고 본인의 정보로 교체하세요.

기존 내용이 있는 필드는 기본적으로 교체하지 않습니다. 의도적으로 교체할 때만 `--overwrite`를 추가합니다.
복수의 자기소개서 문항이 동시에 편집 중이면 중단합니다. 입력할 문항 하나만 열어주세요.
로그인·CAPTCHA·본인인증은 사용자가 직접 처리합니다.

2026-09-15 실제 로그인된 페이지에서 확인한 선택자:

| 항목 | CSS 선택자 |
|---|---|
| 이력서 제목 | `input#title` |
| 자기소개서 제목 | `#introduce input[name="intro_title[]"]` |
| 자기소개서 본문 | `#introduce textarea[name="intro_contents[]"]` |

계정마다 학력·경력 등 기존 데이터와 편집 상태가 다르므로 이 POC는 위 3개 텍스트 필드에 한정합니다.
페이지 구조가 바뀌면 `poc/automation.py`의 선택자를 수정해야 합니다.
실제 사람인에는 생성 샘플을 입력하거나 저장하지 않았습니다. 구조를 확인했고, Selenium 입력·저장 검증은 로컬 사이트에서 수행했습니다.

### 로컬 사이트만 열기

```powershell
.\.venv\Scripts\python.exe main.py serve
```

브라우저에서 http://127.0.0.1:8765 에 접속합니다. 종료는 Ctrl+C입니다.
이 서버는 로컬 시연 전용입니다.

## 검증 및 오류 처리

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py demo
```

- 단위/통합 테스트: 필수·우대 분리, 누락 정보, 빈 입력, API 키 누락, API 응답 파싱, 미완료 응답, HTML 이스케이프, 기존 내용 보호, 폼 저장 줄바꿈.
- 브라우저 테스트: 자동 입력값 확인 → 저장 완료 화면 → 실제 DB 내용 대조.
- 실제 LLM 호출은 API 키가 없어 미검증이며, 응답 처리 코드는 모의 응답으로 검증합니다.
- `Unable to obtain driver`: 네트워크 및 Chrome 설치를 확인하거나 `--driver-path C:\경로\chromedriver.exe`를 지정하세요.
- 사람인 입력칸 대기 오류: 로그인 및 직접 입력 폼을 확인하세요. 이미 채워진 필드가 있으면 화면에서 내용을 확인하세요.
- 출력물에는 입력한 공고·지원자 정보가 포함됩니다. `outputs/`는 버전 관리에서 제외합니다.

## 구조

```text
main.py                기능별 실행과 전체 흐름
poc/analysis.py        오프라인 / LLM 분석
poc/documents.py       지원 문서 생성
poc/automation.py      Selenium 로컬 / 사람인 입력
poc/demo_site.py       Python HTTP 서버 + SQLite
samples/               가상 공고와 지원자
tests/                 검증 코드
```

## 참고한 공식 문서

- [OpenAI 구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Selenium 대기 전략](https://www.selenium.dev/documentation/webdriver/waits/)
- [Selenium Manager](https://www.selenium.dev/documentation/selenium_manager/)
