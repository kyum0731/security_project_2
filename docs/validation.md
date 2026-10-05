# 구현 검증 기록

갱신일: 2026-10-05 · 분석기 0.4.0 · 정적 계약 2.1 / 동적 계약 1.0

## 0.4.0: 함수·클래스·변수 관계 확장

전체 Python 테스트 95개 중 94개 통과, Windows 심볼릭 링크 권한으로 1개 건너뜀. 기존 동적 실행 11개를 포함해 회귀 검증했다. 추가 테스트 6개에서 변수·매개변수의 스코프 분리, global/nonlocal, 클래스와 메서드의 이름 탐색 차이, 복합 대입의 읽기/쓰기, 삭제, 변수 간 대입식 참조, 직접 import한 변수, 명시적 상속과 미해결 기반식, 한글 위치, 모든 HTML 근거 앵커와 스키마를 확인했다.

모의 DOM에서는 변수/클래스 선택 목록 필터, 변수 읽기/쓰기 관계 필터, 상속 표시, 근거 클릭과 기존 정적/실행 관측 필터를 검증했다. 실제 브라우저 시각 검수와 Mermaid 렌더러 검수는 미실시이며 Markdown 그래프는 안전한 제한 문법과 표시 한도를 검사했다.

자체 프로젝트를 `--source-root src --report-dir ./reports/symbol-review`로 정적 분석했다. 파일 27개, 함수 70개, 클래스 12개, 메서드 56개, 변수 949개를 기록했다. 이 수치는 해당 검수 시점의 결과다. JSON Schema·manifest·중복 앵커 없음·모든 관계 ID에 대응하는 HTML 앵커 존재를 확인했다. 기존 수작업 호출 평가 7개는 TP 4 / FP 0 / FN 1을 유지했으며 변수 분석 전체의 정확도 측정치로 사용하지 않는다.

```powershell
python -B -m unittest discover -s tests -t . -q
python -B -m tests.evaluate
python -B -m knitcode_analyzer_v2 . --source-root src --report-dir ./reports/symbol-review
```

테스트의 JSON Schema 검증에는 pyproject의 test 선택 의존성(jsonschema)이 필요하다. 일반 실행은 외부 패키지나 venv 없이 가능하다.

## 0.3.0: J 동적 실행 검증

**전체 Python 테스트 89개: 88개 통과, 심볼릭 링크 권한으로 1개 건너뜀.** 기존 정적 평가 7개 호출의 TP 4 / FP 0 / FN 1은 유지했다. Windows CPython 3.13.3에서 동적 통합 테스트 11개를 실제 자식 프로세스로 실행했다. 테스트 소스는 임시 프로젝트에 쓰고 종료 후 정리하며 배포용 샘플로 두지 않는다.

검증한 범위:

- 일반 함수·메서드·재귀·중첩·데코레이터 코드의 진입·위치·횟수. 한 줄의 두 호출과 한글·이모지 앞부분이 있는 위치 구분.
- 정적 미해결 메서드 호출을 실행 관측으로 별도 연결하고 static edges를 그대로 유지. 생성된 코드가 같은 파일명을 써도 정적 정의로 억지 연결하지 않음.
- 정상/처리된 예외/미처리 예외, 스크립트·패키지 모듈·unittest 실행, 공백·한글 경로, 대상 인자 전달과 cwd.
- 이벤트 한도·시간 초과·취소와 부분 보고서 보존, 로그 바이트 상한, 잘린 마지막 이벤트 처리.
- 비동기·제너레이터·추가 스레드·자식 프로세스 범위 제한 표시, 실행 중 파일 변경 감지.
- 잘못된 입력·출력 경로 거부, 실행별 새 디렉터리, 없는 Python의 실행 실패, static manifest와 전체 run manifest 검증.
- C 함수 콜백의 상위 Python 프레임 관계 표시. 이를 항상 명시적 직접 호출로 단정하지 않음.

모의 DOM에서 기존 그래프 기능과 새 정적/실행 관측/함께 보기 필터, 관측 횟수 표시를 실행했다. 실제 브라우저가 연결되지 않은 환경이므로 화면·레이아웃·전체 접근성 시각 검수는 미실시다.

추가 검수 명령:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -S -B -m knitcode_analyzer_v2.runtime . --module tests.evaluate --source-root src --report-dir ./reports/runtime-review --max-events 10000 --timeout 30
```

평가 모듈은 대상 종료 코드 0으로 완료했다. 이벤트 414개, 집계 호출 관계 52개를 기록했다. 실행된 소스의 제너레이터 및 매칭 불가 합성 코드 때문에 trace_status는 partial이며 해당 제한을 표시했다. run manifest와 HTML 근거 앵커의 존재·중복 검증을 통과했다. 이 수치는 한 번의 자체 검수 결과이며 임의 프로젝트의 분석률·성능 보장이 아니다. 생성물은 Git에서 제외되는 `reports/runtime-review/`에 있다.

프로그램의 임의 자식 프로세스 종료 보장, 모든 비동기/스레드 동작 탐지, 함수별 성능 측정, 대상 코드의 보안 격리, 실모델 기반 동적 설명은 구현·검증 범위 밖이다. `-S`는 부모 분석 CLI 검증에 사용했으며 worker는 대상 의존성을 사용할 수 있도록 선택한 Python을 일반 실행한다.

## 0.2.1: 외부 API·로컬 Ollama·Markdown 출력

**Python 테스트 78개: 77개 통과, 심볼릭 링크 권한으로 1개 건너뜀.** 일반 Python 3.13.3에서 테스트했고 스키마 검증 의존성은 기존 로컬 경로를 재사용했다. `python -S`에서도 새 CLI 도움말과 버전 조회가 정상 동작했다.

- 실제 루프백 HTTP 모의 서버에 `/api/chat` 요청을 보내 Ollama의 요청 필드·응답 구조를 검증했다. 네이티브 요청에는 Chat Completions 전용 필드와 외부 API Authorization 키가 들어가지 않는지 확인했다.
- 로컬 모드가 기존 외부 API 주소·모델·키 환경 변수의 영향을 받지 않는지, 원격 Ollama 주소·cloud 모델 태그·잘린 응답을 거부하는지 검사했다.
- 하나의 응답을 JSON과 Markdown으로 저장하고, 설명·근거 ID·원문이 일치하는지 확인했다. 기존 Markdown 파일이 있으면 요청 전에 거부하며 파일을 보존했다.
- Markdown의 모델 문자열 이스케이프와 실패 이유 표시를 확인했다. 정적 보고서에 자동 병합하지 않는다.

현재 PATH에서 Ollama 실행 파일을 찾지 못했다. Ollama·모델을 자동 설치하거나 실제 모델을 호출하지 않았다. 루프백 모의 서버 검증은 실제 모델의 답변 품질·GPU 성능·모델별 호환성을 검증한 결과가 아니다. 외부 API에 사용자 코드를 전송하지 않았다.

## 2026-10-05 F·I 추가 검증

F(오프라인 그래프)·I(로컬 검색·문맥·선택 API 설명)를 추가하고 G(VS Code)·H(Git)는 제외했다. 런타임 외부 의존성은 없다.

**Python 테스트 74개: 73개 통과, 1개 건너뜀.** 실제 심볼릭 링크 생성 테스트만 Windows 권한 오류 1314로 건너뛰었다. 정답 호출 평가 7개는 기존과 동일하게 TP 4, FP 0, FN 1, precision 1.0, recall 0.8이다. 일반 프로젝트 정확도로 확대하지 않는다.

추가로 검증한 내용:

- 파일·정의 그래프의 원본 관계와 모든 근거 ID 보존, 미해결 대상의 가상 노드 생성 방지, 정적 결과 불변.
- 악성 `</script>` 문자열의 inert JSON 이스케이프, 실제 내장 스크립트와 CSP 해시 일치.
- 모의 DOM에서 초기 1단계, 방향·유형 필터, 검색, 주변 확장, 초기화, 근거 선택, 확대, 노드 40·관계 묶음 100개 상한과 생략 수.
- 이름·한국어 docstring 검색, 검색 실패, 명시적 대상 선택, 관계 문맥, 노드·원문 예산, 원문 변경 거부, CRLF·한글·이모지·문자열 안 Unicode 줄 구분자의 위치 보존.
- 모의 API 성공, 존재하지 않는 근거·제안 노드 거부, JSON 오류·응답 중단·HTTP 오류·timeout·리디렉션 거부, 키의 결과 미포함, 대상 문맥 없음 시 미전송.
- AI 실패 시 별도 실패 JSON과 문맥 보존, 종료 코드 3, 기존 출력 덮어쓰기 거부, 정적 결과 불변.

실행한 통합 확인:

```powershell
# prototype_2 안에서. 설치하지 않은 소스로 실행
$env:PYTHONPATH = "$PWD/src"
python -S -B -m knitcode_analyzer_v2 . --source-root src --report-dir ./reports/extensions-review
python -S -B -m knitcode_analyzer_v2.assist context . --source-root src --query build_context --output ./reports/extensions-context.json
```

Python 3.13.3에서 site-packages를 읽지 않는 `-S`로 성공했다. 소스 20개 파일·정의 94개·호출 1,006개, 상태 complete, 파싱 실패 0이며 생성 보고서 manifest 검증을 통과했다. 문맥은 선택한 원문과 미제공 범위를 포함했다. 이 생성물은 로컬 검수용으로 Git에서 제외한다.

전체 테스트의 JSON Schema 검사에는 기존에 로컬에 있던 jsonschema 4.26.0과 관련 의존성 경로를 일반 Python의 `PYTHONPATH`에 추가해 사용했다. 새 가상환경은 만들지 않았다. 테스트 의존성의 별도 다운로드는 현재 환경에서 사용 가능한 배포본을 찾지 못해 실패했으며, 일반 실행에는 이 라이브러리가 필요하지 않다. 다른 환경의 표준 검증 명령은 다음과 같다.

```powershell
python -m pip install -e ".[test]"
python -m unittest discover -s tests -t . -v
python -m tests.evaluate
```

선택적 모의 DOM 검사 재현 방법(Node 필요, 일반 사용자 실행에는 불필요):

```powershell
python -c "from pathlib import Path; from knitcode_analyzer_v2.reports.graph import SCRIPT; Path('build').mkdir(exist_ok=True); [Path('build/'+n).write_text(SCRIPT, encoding='utf-8') for n in ('graph-script.mjs', 'graph-script-dense.mjs')]"
node ./tests/graph_ui_smoke.mjs
```

이번 모의 DOM 검사는 도구가 제공하는 Node 런타임에서 실행했다. 연결된 브라우저가 없고 IAB도 사용 불가하여 **실제 브라우저 화면·레이아웃·전체 접근성 검수는 하지 못했다.** 모의 DOM 검사는 이를 대체하지 않는다. **실제 외부 API·로컬 모델 호출과 설명 품질·모델별 호환성도 검증하지 않았다.** 테스트는 모의 전송 계층이며 외부 코드 전송을 하지 않았다.

## 최초 A~E 검증 기록 (2026-10-04, 분석기 0.1.0)

아래는 확장 전 결과를 보존한 기록이다. 현재 범위와 테스트 수는 위 F·I 추가 검증을 따른다.

## 환경과 범위

- Windows 11, Python 3.13.3.
- CPU 식별자: Intel64 Family 6 Model 170 Stepping 4, GenuineIntel. 논리 CPU 22개.
- RAM 용량은 기록하지 못했다. WMI 조회가 환경 권한에 의해 차단되었다.
- 런타임 외부 의존성 없음. 개발 검증에는 jsonschema 4.26.0 사용.
- 계획 A~E 구현. 그래프·VS Code·Git·AI는 미구현인 후속 범위.

## 자동 테스트

```powershell
# prototype_2 안에서
& ./.venv/Scripts/python.exe -m unittest discover -s tests -t . -v
& ./.venv/Scripts/python.exe -m tests.evaluate
```

**총 62개: 61개 통과, 1개 건너뜀.** 실제 심볼릭 링크 생성 테스트는 Windows 권한 오류(1314) 때문에 건너뛰었다. junction 제외 분기는 모의 파일시스템 응답으로 검증했으며 실제 junction을 생성한 검증과 같지 않다.

기존 정적 분석의 회귀 사례 31개를 옮겼다. 레거시 테스트의 읽기 쉬운 노드 이름은 테스트 전용 변환으로 비교하며, 새 hash ID·위치 구조·스키마는 별도 테스트에서 원형 그대로 검사한다.

검증 내용:

- 직접·재귀·별칭·상대 import, 이름 가림, 중첩·비동기 정의, 클래스 생성, 동적 호출 보존.
- 내장 이름과 매개변수 구분, 타입 힌트 호출 context, 같은 행의 복수 호출·복수 import 구분.
- 잘못된 경로, 한글·공백 경로, 반복 제외 옵션, 소스 루트, 부분 실패, 빈 결과, strict 종료 코드.
- 읽기·인코딩·문법·탐색 오류와 분석 중 파일 변경. 실제 대상 코드를 실행하지 않는지 확인.
- 재분석 후 삭제·이동 반영, ID·근거 범위·합계·설명 참조 검증, 입력이 같은 경우 결정성.
- 실제 관계가 달라지면 같은 파일 목록이라도 snapshot이 달라지는지 확인.
- 보고서 내부 앵커의 존재와 중복, HTML·Markdown 이스케이프, 외부 웹 자원 미포함.
- 사용자 파일·다른 프로젝트 결과·편집된 보고서의 덮어쓰기 거부.
- 저장 실패 시 이전 결과 복원, manifest 해시 일치, 동시 저장 잠금.

## 정답 기반 소규모 평가

`tests/input_cases.py`의 문자열을 테스트 때만 임시 파일로 만든다. 정답은 파일·행·UTF-8 열·표현식·대상으로 수동 지정했다. 미지원 `self.run()`의 의도된 내부 대상도 정답에 포함했다.

| 항목 | 결과 |
| --- | ---: |
| 호출 위치 | 7 |
| 정답 내부 호출 | 5 |
| 올바른 연결 TP | 4 |
| 잘못 연결한 관계 FP | 0 |
| 놓친 내부 관계 FN | 1 |
| Precision | 100% |
| Recall | 80% |
| 미해결 비율 | 2 / 7 = 28.57% |
| 파싱 실패 | 0 |

위 결과는 이 작은 정답 입력에만 해당한다. 일반 Python 프로젝트 정확도, 실행 결과 또는 이해도 개선의 증거가 아니다.

## 실제 로컬 코드 분석

아래 모두 `complete`, 파싱 실패 0이며 JSON Schema와 manifest 검증을 통과했다. 입력 프로젝트는 실행하거나 수정하지 않았다.

| 대상 | 파일 | 물리 행 | 정의 | 호출 위치 | 분석 시간 중앙값 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 기존 prototype | 26 | 2,003 | 172 | 1,080 | 0.1929초 |
| prototype_2/src | 15 | 1,474 | 79 | 788 | 0.1176초 |
| Python 표준 라이브러리 unittest | 13 | 6,888 | 507 | 1,756 | 1.4380초 |

3회 연속 분석 API 호출의 중앙값이다. insights와 무결성 검사까지 포함하며 HTML 렌더링·출력 파일 저장 시간은 제외한다. OS 파일 캐시를 비우지 않았으므로 냉간 실행 성능 측정이 아니다. 하드웨어·캐시·파일 크기·규칙에 따라 달라지며 큰 저장소 전체의 처리 시간을 보장하지 않는다.

| 대상 | 내부 연결 | 내장 이름 | 범위 밖 import | 미해결 |
| --- | ---: | ---: | ---: | ---: |
| 기존 prototype | 160 | 173 | 105 | 642 |
| prototype_2/src | 142 | 183 | 78 | 385 |
| unittest | 275 | 537 | 17 | 927 |

실제 코드에는 정답 관계가 없으므로 precision·recall을 계산하지 않았다. 미해결에는 객체 메서드, 변수 값 전달, 보수적인 이름 가림 등이 포함된다. `complete`는 파일 분석 작업이 완료되었다는 의미이며 호출 대상이 모두 해결되었다는 뜻이 아니다.

`unittest`는 설치된 Python의 `Lib`를 import 기준으로 두고 `unittest`를 제외한 형제 항목을 제외했다. 따라서 다른 표준 라이브러리를 향하는 이름 일부가 `module_not_indexed`로 분류된다. 이는 해당 라이브러리가 설치되지 않았다는 판정이 아니다.

재측정 예시:

```powershell
# prototype_2 안에서, 출력 폴더는 측정하려는 프로젝트 전용으로 지정
& ./.venv/Scripts/python.exe -m tests.benchmark ../prototype --report-dir ./reports/existing-prototype
& ./.venv/Scripts/python.exe -m tests.benchmark . --source-root src --report-dir ./reports/self
```

로컬 생성물: `reports/verification.json`, `reports/self/report.html`, `reports/existing-prototype/report.html`, `reports/stdlib-unittest/report.html`. 이들은 고정 배포 샘플이 아니라 실제 코드를 분석한 검증 결과이며 버전 관리·패키지 배포에서 제외된다.

## 독립 설치 검증

배포 wheel을 만들고 `build/isolated-env`의 별도 가상환경에 `--no-index --no-deps`로 설치했다. import 위치가 해당 가상환경의 `site-packages`인지 확인했으며 설치된 배포 패키지는 KnitCode 하나였다.

이 환경에서 기존 prototype 경로를 분석하여 26개 파일과 보고서를 생성하고 manifest를 확인했다. 기존 prototype 분석기 자체를 import하지 않았으며 새 패키지의 런타임 의존성도 없었다. wheel에 테스트·sample_project·생성 보고서가 포함되지 않는지 확인했다.

## 미실시 검증

연결된 브라우저 목록이 비어 있어 HTML의 실제 브라우저 화면·반응형 배치·접힌 영역으로의 앵커 이동을 육안 검수하지 못했다. HTML 구조·링크·이스케이프·자체 포함 여부는 자동 검사했다. 실제 프로젝트 사용자의 탐색 시간·정답률 비교 실험도 아직 하지 않았다. 이 두 항목을 확인한 것처럼 주장하지 않는다.
