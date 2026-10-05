# KnitCode Analyzer v2

**로컬 Python 프로젝트 경로를 입력하면, 코드를 실행하지 않고 구조·호출 관계·읽기 시작점을 한국어 보고서로 정리합니다.** AI, API 키, Git, VS Code, 분석 대상 패키지 설치가 필요하지 않습니다.

구현 범위는 [계획서](pre_prototype_2.md)의 A~E입니다. 대화형 그래프, VS Code 확장, Git 공동 변경, AI 설명은 후속 단계입니다. 배포용 샘플 프로젝트는 포함하지 않습니다.

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
│       └── reports/               # 보고서를 만드는 소스 코드: 반드시 유지
│           ├── __init__.py        # 보고서 렌더링 함수 공개
│           ├── common.py          # HTML·Markdown 보고서의 공통 처리
│           ├── html.py            # 단일 HTML 보고서 생성
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
