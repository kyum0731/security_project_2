# KnitCode Analyzer v2

**로컬 Python 프로젝트 경로를 입력하면, 코드를 실행하지 않고 구조·호출 관계·읽기 시작점을 한국어 보고서로 정리합니다.** AI, API 키, Git, VS Code, 분석 대상 패키지 설치가 필요하지 않습니다.

구현 범위는 [계획서](pre_prototype_2.md)의 **A~F와 I**입니다. 기본 보고서에 오프라인 관계 그래프를 포함하며, 별도 명령으로 로컬 검색·문맥 구성·선택 AI 설명을 제공합니다. G(VS Code)·H(Git)는 구현하지 않았습니다. 배포용 샘플 프로젝트는 포함하지 않습니다.

## 실행 환경과 설치

이 문서는 **가상환경을 만들지 않고 일반 `python` 명령으로 실행하는 방법**을 기준으로 합니다. `.venv` 폴더는 필요하지 않습니다.

- Python **3.13 이상**이 필요합니다. Windows / Python 3.13.3에서 검증했습니다.
- 기본 분석은 Python 표준 라이브러리만 사용합니다.
- 아래 명령은 Windows PowerShell 기준입니다.
- `python3`가 Python 3.13 이상을 가리키는 환경에서는 아래의 `python`을 모두 `python3`로 바꿔도 됩니다. 설치와 실행에 같은 명령을 사용하세요.

먼저 `prototype_2` 폴더로 이동합니다. 이미 해당 폴더 안이라면 `cd`는 생략합니다. **이후 예시는 모두 `prototype_2` 안에서 실행합니다.**

```powershell
cd ./prototype_2
python --version
python -m pip install -e .
```

`pip install -e .`는 현재 `python`이 KnitCode를 찾을 수 있도록 최초 한 번 등록하는 명령입니다. `-e`는 현재 소스 위치를 참조하는 개발용 설치 방식이므로 소스 수정이 실행에 반영됩니다. 프로젝트 폴더를 옮기거나 Python을 바꿨다면 새 위치에서 다시 설치하세요.

런타임 외부 라이브러리는 없지만 설치 과정에서 빌드 도구를 내려받을 수 있습니다. 패키지 설치도 생략하려면 아래의 ‘설치 없이 실행하기’를 사용하세요. 가상환경은 여러 프로젝트의 패키지를 분리할 때 선택적으로 사용하는 도구이며, 이 프로젝트의 실행 조건은 아닙니다.

## 프로젝트 분석과 결과 열기

### 기본 사용법

`C:/work/my-python-project`를 **실제로 분석할 Python 프로젝트 폴더**로 바꾸세요. 대상 프로젝트를 KnitCode 디렉터리로 복사할 필요는 없습니다.

```powershell
python -m knitcode_analyzer_v2 "C:/work/my-python-project" --report-dir "./reports/my-project"
Start-Process "./reports/my-project/report.html"
```

첫 번째 명령은 분석과 결과 저장을 수행하고, 두 번째 명령은 생성된 HTML을 기본 브라우저로 엽니다. 서버 실행 없이 파일을 직접 열 수 있습니다. 공백·한글이 있는 경로도 따옴표로 감싸서 지정하면 됩니다.

위 예시의 출력 폴더는 `prototype_2/reports/my-project/`입니다. 상대 입력 경로와 상대 출력 경로는 모두 **명령을 실행한 현재 디렉터리**를 기준으로 합니다. 분석할 폴더 경로는 필수입니다.

### `src` 구조인 프로젝트

예를 들어 대상 파일이 `my-python-project/src/mypkg/__init__.py`, `src/mypkg/service.py`에 있다면 다음처럼 실행합니다.

```powershell
python -m knitcode_analyzer_v2 "C:/work/my-python-project" --source-root src --report-dir "./reports/my-project-src"
```

`--source-root src`는 `src`를 파일 탐색과 import 해석의 기준으로 사용합니다. **이 경우 src 밖의 tests는 분석하지 않습니다.** 최상위 패키지 폴더 자체보다 그 부모를 소스 루트로 선택하세요. 소스 루트는 입력 프로젝트 내부의 상대 경로이며 자동 변경하지 않습니다.

### 제외 설정과 JSON 출력

```powershell
python -m knitcode_analyzer_v2 "C:/work/my-python-project" --exclude "tests/" --exclude "**/generated/**" --report-dir "./reports/my-project"
python -m knitcode_analyzer_v2 "C:/work/my-python-project" --json-stdout --strict
python -m knitcode_analyzer_v2 --help
python -m knitcode_analyzer_v2 --version
```

`--exclude`는 반복 지정할 수 있습니다. 패턴은 **입력 프로젝트의 루트 기준**입니다. `--source-root src`를 사용해도 기준은 같으므로 `src/tests`를 제외하려면 `--exclude "src/tests/"`로 지정합니다.

`--json-stdout`은 파일 없이 JSON만 출력하는 옵션이고, `--strict`는 부분 분석이나 Python 파일 없음 상태에서 종료 코드 1을 반환하는 옵션입니다. JSON 출력과 함께 나타나는 상태 메시지는 stderr이므로 별도로 구분할 수 있습니다.

설치 후 Python의 Scripts 디렉터리가 PATH에 등록되어 있으면 `knitcode-analyzer-v2 PROJECT`도 사용할 수 있습니다. 여기서는 실행할 Python을 명확히 선택하는 `python -m knitcode_analyzer_v2` 형식을 사용합니다.

### 설치 없이 실행하기

`pip install`도 하지 않으려면 `prototype_2` 안에서 소스 경로를 지정합니다.

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m knitcode_analyzer_v2 "C:/work/my-python-project" --report-dir "./reports/my-project"
Start-Process "./reports/my-project/report.html"
```

이 설정은 현재 PowerShell 창과 그 창에서 실행한 프로세스에 적용됩니다. 새 터미널을 열면 다시 설정해야 합니다. 이미 `PYTHONPATH`를 사용 중이면 기존 경로를 보존하도록 조정하세요. 패키지를 설치했다면 이 설정은 필요하지 않습니다.

`python src/knitcode_analyzer_v2/__main__.py`처럼 파일을 직접 실행하면 패키지 내부 상대 import가 동작하지 않을 수 있습니다. 설치하거나 소스 경로를 지정한 뒤 `python -m knitcode_analyzer_v2`로 실행하세요.

## 어떤 내용을 통해 분석하는가

입력 폴더 안의 **저장된 `.py` 파일**을 읽고 Python의 `ast`로 문법 구조를 추출합니다. AST는 소스를 함수 정의·import·호출 표현식 같은 요소로 나타낸 것입니다. 분석기는 이 구조와 이름의 유효 범위를 모은 뒤, 같은 파일의 정의와 명시적인 import·별칭을 따라 관계를 찾습니다.

```text
로컬 폴더 경로
  → .py 파일 탐색과 제외 처리
  → 파일 읽기·인코딩 처리·AST 파싱
  → 정의·소속·이름 바인딩·import·호출 위치 수집
  → 지원 규칙에 따른 대상 해석
  → 구조 요약·진입점 후보·읽기 안내
  → JSON / HTML / Markdown 저장
```

| 분석 정보 | 제공하는 내용 |
| --- | --- |
| 파일 구조 | 디렉터리 트리, 분석한 Python 파일, 파싱 상태와 제외 항목 |
| 정의와 소속 | 함수·클래스·메서드·비동기 함수·중첩 정의, 부모 요소와 위치 |
| 선언 정보 | 매개변수 이름·종류, 기본값·타입 힌트 원문, 반환 힌트 |
| 작성자 설명 | 파일·클래스·함수에 작성된 docstring |
| import 관계 | 가져오는 모듈·정의, 별칭, 지원 범위 내 상대 import |
| 호출 관계 | 같은 파일의 직접 호출, 모듈 수준 재귀, 명시적 import·별칭을 통한 호출 |
| 호출자·호출 대상 | 분석된 내부 호출자, 호출 대상, 원문 표현식과 소스 위치 |
| 읽기 시작점 | `if __name__ == "__main__":`와 `__main__.py`에 근거한 진입점 후보 |
| 읽기 안내 | 내부 연결을 따라가는 읽기 순서, 제한된 탐색에서 발견한 순환·생략 정보 |
| 분석 진단 | 읽기·인코딩·문법·탐색 오류, 분석 중 파일 변경, 미해결 이유 |

예를 들어 `from payment import calculate_price as calc`로 가져온 뒤 함수 안에서 `calc(items)`를 호출하면, 지원 조건을 충족하는 경우 호출자와 내부 정의 `calculate_price`를 연결합니다. 단순히 이름이 같다는 이유만으로 다른 파일의 함수를 연결하지 않습니다.

`.pyi`, Jupyter Notebook, 다른 언어 파일, Git 기록은 현재 분석하지 않습니다. Git 저장소가 아닌 일반 폴더도 사용할 수 있습니다. 실제 실행 순서·횟수·입력 값·반환 값은 계산하지 않으며, 타입 힌트는 선언된 정보로 표시합니다. 파싱 가능한 문법은 실행 중인 Python 파서가 지원하는 범위입니다.

## F: 오프라인 관계 그래프

기존 분석 명령을 실행하고 `report.html`의 **관계 그래프**를 여세요. 별도 설치·서버·네트워크 연결이 필요하지 않습니다. 이전에 생성한 보고서에는 없으므로 업데이트 후 다시 분석해야 합니다.

1. 파일 이름으로 검색하고 중심 파일을 선택합니다. 처음에는 선택 요소의 1단계 주변을 표시합니다.
2. 노드를 선택해 **파일 안의 정의 펼치기**를 누르거나 표시 단위를 **파일·정의**로 바꿉니다. 함수·메서드·클래스도 선택할 수 있습니다.
3. 방향과 `calls`·`imports`·`contains` 필터를 조합합니다. 들어오는 관계를 볼 때도 화살표는 원래 호출·import·소속 방향을 유지합니다.
4. **이 노드 주변 확장** 또는 **표시된 노드 주변 확장**으로 탐색 범위를 늘립니다. 확대·축소와 스크롤을 사용할 수 있습니다.
5. 관계 선이나 관계 이름을 선택하면 묶인 모든 근거 위치가 나타납니다. 근거 링크는 보고서의 상세 항목을 펼쳐 이동합니다.

화면에는 최대 노드 40개·관계 묶음 100개를 표시하고 생략 수를 알립니다. 원자료를 잘라내지는 않습니다. 파일 그래프는 호출·import를 파일 단위로 집계하며, 같은 파일 내부 관계는 자기 자신을 향하는 선으로 표시합니다. `contains`는 파일·정의 모드에서 확인합니다. 대상이 없는 외부·내장·미해결 관계는 선택 노드의 별도 목록에 표시하며 가상 함수를 만들지 않습니다.

JavaScript를 꺼도 기존 표·트리·코드 상세는 읽을 수 있습니다. 그래프의 코드는 HTML에 포함되고, 분석 대상의 문자열은 실행되지 않도록 이스케이프합니다.

## I: 검색·문맥 구성·선택 AI 설명

이 기능은 기본 분석과 분리한 `assist` 명령으로 실행합니다. **`search`와 `context`는 오프라인이고, `explain`만 설정한 AI 서버로 질문·선택 원문·관계·위치 정보를 전송합니다.** 가상환경이나 추가 런타임 라이브러리는 필요하지 않습니다. 설치를 생략했다면 앞에서 설명한 `PYTHONPATH`를 같은 터미널에 설정하세요.

### 로컬 검색과 전송할 문맥 확인

`calculate_price`는 분석할 프로젝트에 실제로 있는 이름이나 docstring의 단어로 바꿉니다.

```powershell
python -m knitcode_analyzer_v2.assist search "C:/work/my-python-project" --query "calculate_price"
python -m knitcode_analyzer_v2.assist context "C:/work/my-python-project" --query "calculate_price" --output "./reports/context.json"
```

검색은 이름·경로·docstring의 단어 일치를 점수화합니다. 의미 검색이나 임베딩 검색은 아닙니다. 문맥은 최상위 검색 결과를 선택한 뒤 호출·import의 양방향 주변에서 모읍니다. 다른 대상을 지정하려면 검색 결과의 `node_id`를 `--node "노드 ID"`로 전달하세요. `--query`에는 질문을 넣을 수 있습니다.

```powershell
python -m knitcode_analyzer_v2.assist context "C:/work/my-python-project" --query "이 함수의 역할과 호출자를 설명해줘" --node "검색 결과의 node_id" --depth 1 --max-nodes 8 --max-chars 16000
```

`--source-root src`, 반복 `--exclude`도 기본 분석과 같이 사용할 수 있습니다. 기본 문맥은 거리 1, 원문 최대 8개, 원문 문자 수 16,000자이며 거리 0~2·노드 1~20·원문 1,000~100,000자로 조정할 수 있습니다. 문자 수 예산은 토큰 수나 전체 HTTP 요청 크기와 다릅니다. 큰 함수를 중간에서 자르지 않고 생략 이유를 기록합니다. 관계는 최대 80개를 제공하고 초과 수를 기록합니다.

### I의 실행 흐름

```text
프로젝트 재분석 (AI 없음)
  → 이름·경로·docstring 검색 또는 --node로 대상 선택
  → 선택한 정의와 호출·import 주변 원문 수집
  → 원문 해시·문맥 예산 확인
  → explain일 때만 외부 API 또는 로컬 Ollama에 요청
  → 응답 JSON과 근거 ID 검사
  → JSON 출력 + 선택적 Markdown 설명 문서 저장
```

`search`, `context`, `explain`은 각자 한 번에 실행하는 명령입니다. 앞의 두 명령을 먼저 실행하지 않아도 `explain`이 내부에서 검색과 문맥 구성을 수행합니다. 검색은 자연어 의미 검색이 아니므로 질문에 실제 함수 이름을 포함하거나 `--node`로 대상을 지정하세요.

### 방법 A: 외부 API로 설명하기

`--provider api`는 Chat Completions 호환 API를 사용합니다(생략 시 기본값). 서버의 기본 주소(`/v1`까지)·해당 서비스에서 사용 가능한 모델·발급받은 API 키를 설정합니다. 아래는 OpenAI 주소 예시이며 모델명과 키는 실제 값으로 바꿉니다. 선택된 원문과 질문이 해당 서비스로 전송되며 서비스 사용 요금이 발생할 수 있습니다.

```powershell
$env:KNITCODE_AI_BASE_URL = "https://api.openai.com/v1"
$env:KNITCODE_AI_MODEL = "사용할-모델명"
$env:KNITCODE_AI_API_KEY = "발급받은-API-키"
python -m knitcode_analyzer_v2.assist explain "C:/work/my-python-project" --provider api --query "calculate_price 함수의 역할을 설명해줘" --output "./reports/api-explanation.json" --markdown-output "./reports/api-explanation.md"
```

키는 `KNITCODE_AI_API_KEY` 환경 변수로만 읽고 결과에 저장하지 않습니다. 실제 키를 README나 소스에 적지 마세요. 위 환경 변수 설정은 현재 PowerShell 세션에 적용됩니다. 주소·모델은 `--base-url`·`--model`로도 지정할 수 있습니다. 다른 호환 서비스는 주소·모델·키를 해당 서비스 값으로 바꾸면 됩니다. Chat Completions 형식과 다른 API를 직접 호출하는 어댑터는 포함하지 않습니다.

로컬 Chat Completions 호환 서버도 `--provider api --base-url http://127.0.0.1:1234/v1 --model "로컬-모델명"`으로 연결할 수 있습니다. 루프백 HTTP에서는 키를 생략할 수 있고 프록시 환경 변수를 사용하지 않습니다. 이 방식에서 키 환경 변수가 남아 있으면 설정한 로컬 서버에도 전달되므로 불필요한 키는 현재 세션에서 비우세요. 아래 Ollama 전용 모드는 외부 API 키를 읽거나 전송하지 않습니다.

호환 계약은 `POST /chat/completions`, `messages`, `response_format: {"type":"json_object"}`, `max_completion_tokens`, 비스트리밍 응답입니다. 서버·모델이 이 계약을 지원해야 하며 모든 ‘호환’ 서버를 검증한 것은 아닙니다. API 형식은 [OpenAI 공식 Chat Completions 문서](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)를 참고했습니다. 실제 외부 API 호출·모델 품질 평가는 아직 하지 않았습니다.

### 방법 B: Ollama로 로컬 AI 사용하기

1. [Ollama Windows 설치 안내](https://docs.ollama.com/windows)에 따라 설치합니다. KnitCode가 Ollama나 모델을 자동 설치하지는 않습니다.
2. PowerShell에서 모델을 내려받고 설치 목록을 확인합니다. 아래 `qwen2.5-coder:7b`는 [실행 예시 모델](https://ollama.com/library/qwen2.5-coder:7b)이며 이 프로젝트에서 품질을 보증한 추천 모델은 아닙니다. PC의 RAM·GPU 메모리에 맞는 로컬 모델을 선택하세요.

```powershell
ollama pull qwen2.5-coder:7b
ollama ls
```

모델 다운로드에는 인터넷이 필요합니다. 로컬 추론은 내려받은 모델을 사용합니다. 클라우드 기능까지 끄려면 실행 중인 Ollama를 트레이에서 종료한 뒤 아래 명령으로 서버를 시작합니다. 이 창은 서버 실행 상태로 두고, KnitCode 명령은 다른 PowerShell에서 실행하세요. 설정 근거는 [Ollama 로컬 전용 모드 안내](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features)입니다.

```powershell
$env:OLLAMA_NO_CLOUD = "1"
ollama serve
```

`prototype_2` 폴더의 다른 PowerShell에서 실행합니다. 이미 KnitCode를 설치했다면 `PYTHONPATH` 설정은 생략합니다.

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m knitcode_analyzer_v2.assist explain "C:/work/my-python-project" --provider ollama --model "qwen2.5-coder:7b" --query "calculate_price 함수의 역할을 설명해줘" --max-chars 8000 --timeout 300 --output "./reports/local-explanation.json" --markdown-output "./reports/local-explanation.md"
```

이 모드는 Ollama의 [네이티브 Chat API](https://docs.ollama.com/api/chat)를 사용합니다. 기본 주소는 `http://127.0.0.1:11434`이며 `/v1`을 붙이지 않습니다. 다른 로컬 포트는 `--base-url` 또는 `KNITCODE_OLLAMA_BASE_URL`로 지정합니다. 모델은 `--model` 또는 `KNITCODE_OLLAMA_MODEL`로 지정합니다. 외부 API용 `KNITCODE_AI_*` 설정은 사용하지 않습니다.

원격 주소와 알려진 `:cloud`·`-cloud` 모델 태그는 거부합니다. 이 검사만으로 임의의 로컬 프록시나 사용자 정의 모델의 실행 위치를 증명하지는 않습니다. 내려받은 모델과 클라우드를 끈 Ollama 서버를 사용하세요. 기본 문맥 창은 `--num-ctx 16384` 토큰이며 모델·메모리에 맞게 조정할 수 있습니다. 원문 `--max-chars`와 토큰 수는 다르므로 너무 큰 문맥은 줄이세요. 기본 timeout은 60초, 최대 600초이며 느린 초기 모델 로딩에는 위 예시처럼 늘릴 수 있습니다.

`explain`은 현재 소스를 새로 분석해 문맥을 구성합니다. 앞서 저장한 `context.json`을 그대로 전송하는 명령은 아니므로, 두 명령 사이 소스를 변경하면 입력도 달라집니다. 구성 시 원문 해시를 확인해 분석 결과와 다른 파일을 섞지 않습니다. 선택 대상이 예산 때문에 빠지면 전송하지 않습니다.

### 결과와 실패 처리

| 실행 옵션 | 출력 위치와 형식 |
| --- | --- |
| 출력 옵션 없음 | 터미널 stdout에 JSON. 파일은 생성하지 않음 |
| `--output ./reports/local-explanation.json` | 현재 디렉터리의 지정 경로에 전체 JSON 저장. stdout에는 JSON을 중복 출력하지 않음 |
| `--markdown-output ./reports/local-explanation.md` | 설명·관찰/추정·근거 원문과 위치·한계를 Markdown으로 추가 저장. explain 전용 |
| 두 옵션 함께 사용 | 같은 AI 응답으로 JSON과 Markdown 생성. AI를 두 번 호출하지 않음 |

위 명령을 `prototype_2`에서 실행하면 `prototype_2/reports/` 아래에 저장됩니다. Markdown만 지정하면 JSON은 터미널에 출력됩니다. 기존 파일은 덮어쓰지 않으므로 다시 실행할 때 새 파일명을 사용하세요. 기존 `report.html`에는 AI 결과를 자동 삽입하지 않습니다. 정적 그래프·보고서와 AI 설명 문서는 별개입니다.

Markdown을 텍스트로 확인하거나 JSON의 설명 부분만 확인하려면 다음처럼 실행합니다.

```powershell
Get-Content ./reports/local-explanation.md -Encoding UTF8
(Get-Content ./reports/local-explanation.json -Raw -Encoding UTF8 | ConvertFrom-Json).answer.claims | Format-List
```

- 기본 출력은 UTF-8 JSON입니다. `--output`을 지정하면 새 JSON 파일에 저장하며 기존 파일은 덮어쓰지 않습니다.
- 설명에는 모델·주소·snapshot·프롬프트 버전·입력/요청 해시·제공 원문·생략 이유를 기록합니다.
- `answer.claims`는 관찰과 추정을 구분합니다. 각 항목의 근거 ID를 제공된 파일·범위·해시로 연결합니다. 근거가 존재한다는 검사는 설명의 진실성을 보장하지 않습니다.
- AI 관계 제안은 `answer.suggested_relations`의 미검증 가설로만 저장합니다. `analysis.json`의 정적 관계나 그래프를 수정하지 않습니다.
- AI 실패는 `status: failed`와 문맥을 남기고 종료 코드 3을 반환합니다. Markdown을 지정했으면 실패 이유와 제공 문맥을 문서로도 남깁니다. 잘못된 입력·출력은 2, 취소는 130입니다. 기존 정적 보고서는 그대로 사용할 수 있습니다.
- 원문과 docstring 안의 지시는 데이터로 취급하도록 요청하며, AI가 반환한 코드·명령을 실행하지 않습니다. 공유할 문맥·설명 JSON에도 원문이 담기므로 공유 대상을 확인하세요.

## 결과를 읽는 순서

1. **프로젝트 한눈에 보기:** 분석 범위·파일 수·정의 수·호출 상태·파싱 실패를 확인합니다.
2. **먼저 살펴볼 곳:** `__main__` 가드·`__main__.py` 후보와 호출 관계에 근거한 읽기 안내를 확인합니다. 후보가 없으면 구조에 따른 대안을 제공합니다.
3. **파일 구조·파일 사이 관계:** 트리와 import·호출 집계에서 관심 파일을 찾습니다.
4. **파일·코드 상세:** 파일을 펼쳐 docstring, 선언 정보, 호출자·호출 대상·원문 표현식·소스 위치를 확인합니다.
5. **분석 한계와 진단:** 미해결 이유·파일 오류·제외 항목을 확인합니다.

보고서의 읽기 안내는 기본 깊이 2, 최대 20개 항목이며 실행 순서도가 아닙니다. 이름만으로 업무 목적을 단정하지 않고 구조 사실, 작성자 docstring, 규칙 기반 후보를 구분합니다. 클래스 생성은 클래스 노드에 연결하고 `__init__` 호출이라고 단정하지 않습니다. 소스 위치는 행 1부터, 열 0부터 시작하는 UTF-8 바이트 기준이며 끝 위치는 제외합니다. VS Code로 직접 이동하는 기능은 후속 범위입니다.

| 파일 | 용도 |
| --- | --- |
| `analysis.json` | 모든 수집 요소·관계·근거·진단을 담은 스키마 2.0 원자료 |
| `report.html` | 서버나 CDN 없이 여는 단일 HTML 보고서 |
| `report.md` | 문서로 읽거나 공유할 한국어 보고서 |
| `manifest.json` | 같은 분석 결과의 산출물인지 확인하는 snapshot과 파일 해시 |

출력 위치를 생략하면 실행 디렉터리의 `knitcode-reports/<이름>-<경로해시>/`에 저장하고 실제 경로를 터미널에 안내합니다. 코드를 수정한 후 같은 명령을 다시 실행하면 전체를 재분석하여 이전 정상 산출물을 교체합니다. 다른 프로젝트 결과, 사용자가 편집한 보고서, 같은 이름의 사용자 파일은 덮어쓰지 않습니다. 이 경우 새 출력 디렉터리를 지정하세요.

저장 중 실패하면 기존 파일 복원을 시도하며, 소비자는 manifest의 해시가 일치하는 결과만 사용해야 합니다. 프로세스 강제 종료 뒤 잠금 파일 `.knitcode.lock`이 남았다면 같은 위치에 실행 중인 분석기가 없는지 확인한 뒤 정리하세요. 새 출력 폴더로 실행하는 방법도 있습니다.

`--json-stdout`은 파일을 만들지 않고 UTF-8 JSON 하나만 stdout으로 출력합니다. 로그는 stderr로 분리합니다. `--report-dir`과 동시에 지정할 수 없습니다.

## 상태와 범위

| 호출 상태 | 의미 |
| --- | --- |
| `resolved` | 지원하는 정적 규칙에서 프로젝트 내부 대상 하나를 선택 |
| `builtin` | 이름 가림이 없는 내장 이름 호출 |
| `external` | 분석 인덱스 밖의 명시적 import 이름. 설치·실제 출처는 확인하지 않음 |
| `unresolved` | 정적 규칙만으로 대상을 결정하지 못함. 이유와 호출 위치 보존 |

`self.method()`, 상속, closure, 함수 값 전달·대입 전파, 데코레이터, 재수출, 동적 import의 완전한 해석은 지원하지 않습니다. 해석된 일부 관계를 바탕으로 한 호출자 수는 업무 중요도·위험도·사용 여부 판정이 아닙니다. [정확한 제한](docs/limitations.md)을 참고하세요.

기본 제외: `.git`, `.venv`, `venv`, `env`, `__pycache__`, `site-packages`, `node_modules`, `build`, `dist`, `.tox`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache` 및 현재 출력 디렉터리. 테스트는 기본 포함합니다. 파일·디렉터리 링크와 Windows junction은 따라가지 않습니다.

제외 패턴은 프로젝트 상대 경로와 `/`를 사용합니다. `*`는 한 경로 구간, `**`는 여러 구간, `?`는 한 글자, 끝 `/`는 디렉터리와 하위를 뜻합니다. **분석기는 `.gitignore`를 자동으로 읽지 않으며** `!` 재포함은 지원하지 않습니다. Git 업로드 제외와 분석 대상 제외는 서로 다른 설정입니다.

| 분석 상태 / 종료 코드 | 의미 |
| --- | --- |
| `complete` | 범위 내 발견 파일의 분석 완료. 미해결 호출이 있을 수 있음 |
| `partial` | 읽기·파싱·탐색 실패 또는 분석 중 파일 변경 |
| `empty` | 분석할 `.py` 파일 없음 |
| 종료 `0` | 결과 생성 성공. 기본 실행은 partial·empty도 결과 생성 |
| 종료 `1` | `--strict`일 때 partial 또는 empty |
| 종료 `2` | 인자·루트·출력 오류 |
| 종료 `130` | 사용자 취소 |

## 폴더 구조와 파일 역할

아래는 유지해야 하는 소스·설정·문서·테스트 구조입니다. 분석할 프로젝트는 이 폴더 밖에 있어도 됩니다.

```text
prototype_2/
├── .gitignore                     # Git에서 제외할 생성물·캐시 규칙
├── README.md                      # 설치·사용법과 프로젝트 구조
├── pre_prototype_2.md              # 프로젝트 계획과 단계별 구현 방향
├── pyproject.toml                 # Python 버전·패키지 설치·CLI·테스트 의존성 설정
├── docs/
│   ├── analysis_contract.md       # 분석 결과 데이터와 소비자 간 계약
│   ├── limitations.md             # 지원 범위·미해결 처리·분석 한계
│   ├── extensions.md              # F·I 구현 계약과 검증 범위
│   └── validation.md              # 검증 방법·측정 결과·환경 제한
├── schemas/
│   └── analysis.schema.json       # analysis.json의 구조 검증용 JSON Schema
├── src/
│   └── knitcode_analyzer_v2/
│       ├── __init__.py            # 공개 API와 패키지 버전
│       ├── __main__.py            # python -m 실행 진입점
│       ├── cli.py                 # 명령행 인자·출력 모드·종료 코드 처리
│       ├── analyzer.py            # 탐색부터 결과 검증까지 분석 과정 연결
│       ├── scanner.py             # Python 파일 탐색·경로 검증·제외 처리
│       ├── parser.py              # 파일 읽기·인코딩·AST 파싱·오류 처리
│       ├── symbols.py             # 정의·이름 바인딩·import·호출 정보 수집
│       ├── resolver.py            # 수집된 이름과 호출 대상의 정적 해석
│       ├── models.py              # 데이터 모델·ID·소스 위치·결과 검증
│       ├── insights.py            # 구조 요약·진입점 후보·읽기 안내 생성
│       ├── exporter.py            # 산출물 저장·manifest 해시 검증·복원 처리
│       ├── graph.py               # 정적 결과를 파일·정의 그래프로 변환
│       ├── context.py             # 로컬 검색·주변 관계·해시 확인·문맥 예산
│       ├── ai.py                  # 선택 API 호출·응답과 근거 ID 검증
│       ├── assist.py              # search/context/explain 전용 명령
│       └── reports/               # 보고서를 만드는 소스 코드: 반드시 유지
│           ├── __init__.py        # 보고서 렌더링 함수 공개
│           ├── common.py          # HTML·Markdown 보고서의 공통 처리
│           ├── html.py            # 단일 HTML 보고서 생성
│           ├── graph.py           # HTML 안의 SVG 그래프·검색·필터·확장 UI
│           ├── ai_markdown.py     # AI 설명·근거·실패 결과의 Markdown 문서 생성
│           └── markdown.py        # Markdown 보고서 생성
└── tests/
    ├── __init__.py                # 테스트 패키지 표시
    ├── helpers.py                 # 임시 프로젝트 등 테스트 공통 도구
    ├── input_cases.py             # 테스트용 Python 코드 문자열과 정답 사례
    ├── test_scanner.py            # 탐색·제외·파일 읽기·파싱 검증
    ├── test_resolution.py         # 이름·import·호출 해석 검증
    ├── test_insights.py           # 진입점 후보·읽기 안내 검증
    ├── test_contract.py           # 스키마·ID·결과 일관성 검증
    ├── test_reports.py            # 보고서·출력 보호·manifest 검증
    ├── test_cli.py                # 명령행 옵션·출력·종료 코드 검증
    ├── test_graph.py              # 그래프 근거 보존·스크립트 이스케이프 검증
    ├── test_context.py            # 검색·문맥 예산·원문 해시·문맥 CLI 검증
    ├── test_ai.py                 # 모의 API 응답·근거·실패·전송 경계 검증
    ├── graph_ui_smoke.mjs         # 선택적 Node 실행으로 모의 DOM 그래프 동작 검증
    ├── evaluate.py                # 정답 사례 기준 분석 정확도 평가
    └── benchmark.py               # 지정 프로젝트의 반복 분석 시간 측정
```

실행·설치 과정에서 아래 폴더가 추가로 생길 수 있습니다. Git 업로드에는 필요하지 않으며, 현재 `.gitignore`에서 제외합니다.

| 생성 폴더 | 내용과 처리 |
| --- | --- |
| `.venv/` | 가상환경. 이 README 방식에서는 생성하거나 사용할 필요 없음 |
| `build/` | 빌드 중간 결과·테스트 임시 파일. 필요할 때 다시 생성 |
| `dist/` | 배포용 wheel·압축 패키지. 소스에서 실행할 때 불필요 |
| `*.egg-info/` | 패키지 설치·빌드 메타데이터. 재설치하면 생성되며, 설치 상태를 유지하는 동안 임의 삭제하지 않기를 권장 |
| `__pycache__/` | Python 바이트코드 캐시. 삭제해도 실행할 때 다시 생성 |
| 루트 `reports/` | 이 문서의 예시 명령으로 만든 분석 결과. 삭제하면 해당 결과가 없어지므로 필요하면 별도 보관 |
| `knitcode-reports/` | 출력 위치를 생략했을 때 만드는 기본 분석 결과 |
| `.pytest_cache/` | pytest를 별도로 사용했을 때 생기는 테스트 캐시 |

**루트 `reports/`는 결과물이고 `src/knitcode_analyzer_v2/reports/`는 실행에 필요한 코드입니다.** `.gitignore`의 `/reports/`는 루트 결과 폴더만 제외합니다. `.gitignore`는 이미 Git이 추적 중인 파일을 자동으로 추적 해제하지 않습니다. `.git/`이 있다면 저장소 이력이므로 생성물 정리 대상으로 취급하지 마세요.

## Python API

설치하거나 `PYTHONPATH`를 설정한 같은 Python에서 사용할 수 있습니다.

```python
from knitcode_analyzer_v2 import analyze_project
from knitcode_analyzer_v2.exporter import write_report, verify_manifest

result = analyze_project("C:/work/my-python-project", source_root="src", excludes=("src/generated/",))
print(result["stats"])
data = result.to_dict()  # 독립 복사본
write_report(result, "./reports/my-project")
assert verify_manifest("./reports/my-project")
```

`analyze_project`는 대상 파일을 읽기만 합니다. 출력·네트워크·대상 코드 import를 수행하지 않습니다. 대상 안에 출력 폴더를 만들 경우 CLI는 자동으로 제외하며, API 사용 시에는 `excluded_paths=(출력경로,)`를 전달할 수 있습니다. [데이터 계약](docs/analysis_contract.md)과 [JSON Schema](schemas/analysis.schema.json)를 후속 그래프·익스텐션 개발 기준으로 사용하세요.

## 개발 검증

일반 사용에는 필요하지 않습니다. 코드를 수정한 뒤 검증하려면 `prototype_2` 디렉터리에서 실행합니다.

```powershell
python -m pip install -e ".[test]"
python -m unittest discover -s tests -t . -v
python -m tests.evaluate
```

런타임 외부 의존성은 없으며 `jsonschema`는 테스트용입니다. 위 설치 명령은 현재 `python` 환경에 테스트 의존성도 설치합니다. 테스트 입력은 코드 문자열로 정의하고 `build/tests/` 아래 임시 폴더에 생성했다가 정리합니다. 배포 패키지에는 테스트와 생성된 보고서가 포함되지 않습니다.

실제 프로젝트의 분석 시간을 측정하려면 다음 명령을 사용합니다. 기본 3회 분석하며 보고서 렌더링·저장 시간은 측정에서 제외합니다.

```powershell
python -m tests.benchmark "C:/work/my-python-project" --report-dir "./reports/benchmark"
```

검증 범위·측정 결과·환경 제한은 [검증 기록](docs/validation.md)에 기록합니다. 작은 정답 입력의 정확도와 실제 프로젝트의 해석률을 구분합니다.

## 실행 중 문제가 생기면

| 증상 | 확인할 내용 |
| --- | --- |
| `No module named knitcode_analyzer_v2` | `prototype_2`에서 실행할 Python으로 `python -m pip install -e .`를 했는지 확인. 설치 없이 실행한다면 현재 터미널의 `PYTHONPATH` 설정 확인 |
| Python 버전 오류 | `python --version`으로 3.13 이상인지 확인 |
| Python 파일이 없거나 예상 파일이 빠짐 | 입력 경로·`--source-root`·`--exclude` 확인 |
| 내부 import가 external 또는 unresolved로 표시됨 | 패키지 부모가 소스 루트인지와 분석 한계 확인. 대상 라이브러리를 설치하는 것만으로 해석 범위가 확장되지는 않음 |
| 기존 출력 폴더에 저장할 수 없음 | 안내된 오류 확인. 수정된 결과나 다른 프로젝트 결과가 있다면 새로운 `--report-dir` 지정 |
