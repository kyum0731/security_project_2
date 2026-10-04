# KnitCode Analyzer v2

**로컬 Python 프로젝트 경로를 입력하면, 코드를 실행하지 않고 구조·호출 관계·읽기 시작점을 한국어 보고서로 정리합니다.** AI, API 키, Git, VS Code, 분석 대상 패키지 설치가 필요하지 않습니다.

구현 범위는 [계획서](pre_prototype_2.md)의 A~E입니다. 대화형 그래프, VS Code 확장, Git 공동 변경, AI 설명은 후속 단계입니다. 배포용 샘플 프로젝트는 포함하지 않습니다.

## 바로 실행

Windows / Python 3.13.3에서 검증했습니다. Python 3.13 이상이 필요하며 분석 가능한 문법은 실행 중인 Python 파서가 지원하는 범위입니다. 아래 명령은 `prototype_2`의 **상위 디렉터리**에서 실행합니다.

```powershell
python -m venv ./prototype_2/.venv
& "./prototype_2/.venv/Scripts/python.exe" -m pip install -e ./prototype_2

& "./prototype_2/.venv/Scripts/python.exe" -m knitcode_analyzer_v2 "C:/work/my-python-project" --report-dir "./prototype_2/reports/my-project"
Start-Process "./prototype_2/reports/my-project/report.html"
```

`C:/work/my-python-project`를 **실제로 분석할 폴더**로 바꾸세요. 대상 프로젝트를 KnitCode 디렉터리로 복사하지 않아도 됩니다. 이 작업 공간에는 `.venv` 설치를 완료했으므로 바로 세 번째 명령부터 실행할 수 있습니다. 디렉터리를 다른 PC나 위치로 옮겼다면 가상환경은 다시 만드세요.

`src` 아래를 import 기준으로 사용하는 프로젝트:

```powershell
& "./prototype_2/.venv/Scripts/python.exe" -m knitcode_analyzer_v2 "C:/work/my-python-project" --source-root src --report-dir "./prototype_2/reports/my-project-src"
```

이 옵션은 **src 안의 파일만 분석**합니다. src 밖의 tests는 포함되지 않습니다. import의 최상위 패키지 폴더 자체보다는 그 부모를 소스 루트로 선택하세요. 예를 들어 `src/mypkg/__init__.py`이면 `--source-root src`를 사용합니다. 소스 루트를 자동 변경하지 않습니다.

제외할 파일·폴더와 자동화용 출력:

```powershell
& "./prototype_2/.venv/Scripts/python.exe" -m knitcode_analyzer_v2 "C:/work/my-python-project" --exclude "tests/" --exclude "**/generated/**"
& "./prototype_2/.venv/Scripts/python.exe" -m knitcode_analyzer_v2 "C:/work/my-python-project" --json-stdout --strict
& "./prototype_2/.venv/Scripts/python.exe" -m knitcode_analyzer_v2 --help
```

가상환경을 활성화했다면 `knitcode-analyzer-v2 PROJECT`도 사용할 수 있습니다. 설치 전 개발 확인은 `prototype_2`에서 `$env:PYTHONPATH = "$PWD/src"`를 설정한 뒤 `python -m knitcode_analyzer_v2 PROJECT`로 실행할 수 있습니다.

## 결과를 읽는 순서

1. **프로젝트 한눈에 보기:** 분석 범위·파일 수·정의 수·호출 상태·파싱 실패를 확인합니다.
2. **먼저 살펴볼 곳:** `__main__` 가드·`__main__.py` 후보와 호출 관계에 근거한 읽기 안내를 확인합니다. 후보가 없으면 구조에 따른 대안을 제공합니다.
3. **파일 구조·파일 사이 관계:** 트리와 import·호출 집계에서 관심 파일을 찾습니다.
4. **파일·코드 상세:** 파일을 펼쳐 docstring, 선언 정보, 호출자·호출 대상·원문 표현식·소스 위치를 확인합니다.
5. **분석 한계와 진단:** 미해결 이유·파일 오류·제외 항목을 확인합니다.

보고서의 읽기 안내는 실행 순서도가 아닙니다. 이름만으로 업무 목적을 단정하지 않으며 구조 사실, 작성자 docstring, 규칙 기반 후보를 구분합니다. 클래스 생성은 클래스 노드에 연결하고 `__init__` 호출이라고 단정하지 않습니다.

| 파일 | 용도 |
| --- | --- |
| `analysis.json` | 모든 수집 요소·관계·근거·진단을 담은 스키마 2.0 원자료 |
| `report.html` | 서버나 CDN 없이 여는 단일 HTML 보고서 |
| `report.md` | 문서로 읽거나 공유할 한국어 보고서 |
| `manifest.json` | 같은 분석 결과의 산출물인지 확인하는 snapshot과 파일 해시 |

출력 위치를 생략하면 실행 디렉터리의 `knitcode-reports/<이름>-<경로해시>/`에 저장합니다. 기존 정상 산출물은 재분석으로 교체합니다. 다른 프로젝트 결과, 사용자가 편집한 보고서, 같은 이름의 사용자 파일은 덮어쓰지 않습니다. 이 경우 새 출력 디렉터리를 지정하세요.

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

제외 패턴은 프로젝트 상대 경로와 `/`를 사용합니다. `*`는 한 경로 구간, `**`는 여러 구간, `?`는 한 글자, 끝 `/`는 디렉터리와 하위를 뜻합니다. `.gitignore`를 자동으로 읽지 않으며 `!` 재포함은 지원하지 않습니다.

| 분석 상태 / 종료 코드 | 의미 |
| --- | --- |
| `complete` | 범위 내 발견 파일의 분석 완료. 미해결 호출이 있을 수 있음 |
| `partial` | 읽기·파싱·탐색 실패 또는 분석 중 파일 변경 |
| `empty` | 분석할 `.py` 파일 없음 |
| 종료 `0` | 결과 생성 성공. 기본 실행은 partial·empty도 결과 생성 |
| 종료 `1` | `--strict`일 때 partial 또는 empty |
| 종료 `2` | 인자·루트·출력 오류 |
| 종료 `130` | 사용자 취소 |

## Python API

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

`prototype_2` 디렉터리에서 실행합니다.

```powershell
& ./.venv/Scripts/python.exe -m pip install -e ".[test]"
& ./.venv/Scripts/python.exe -m unittest discover -s tests -t . -v
& ./.venv/Scripts/python.exe -m tests.evaluate
```

런타임 외부 의존성은 없으며 `jsonschema`는 테스트용입니다. 테스트 입력은 코드 문자열로 정의하고 `build/tests/` 아래 임시 폴더에 생성했다가 정리합니다. 배포 패키지에는 테스트와 보고서가 포함되지 않습니다.

검증 범위·측정 결과·환경 제한은 [검증 기록](docs/validation.md)에 기록합니다. 작은 정답 입력의 정확도와 실제 프로젝트의 해석률을 구분합니다.
