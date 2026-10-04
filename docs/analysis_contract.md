# 분석 결과 계약 2.0

최상위 필드: `schema_version`, `metadata`, `files`, `nodes`, `edges`, `insights`, `diagnostics`, `stats`. 구조 제약은 [JSON Schema](../schemas/analysis.schema.json), 의미상 참조·통계 검사는 `analyzer.validate_result()`에 정의합니다. 1.0과 자동 호환되지 않습니다.

## 위치와 식별자

경로는 프로젝트 상대 POSIX 경로입니다. 절대 입력 경로는 `metadata.project_root`에 있습니다. source_root는 프로젝트 상대 경로입니다. 진단의 OS 오류 메시지에는 원래 절대 경로가 포함될 수 있습니다.

위치는 `range: {start_line, start_col, end_line, end_col}`이며 행은 1부터, 열은 0부터인 UTF-8 바이트 수입니다. 끝 위치는 제외합니다. 파일 읽기·디코딩 실패 시 파일 노드 범위는 null입니다. 정의 위치와 호출 위치를 혼동하지 마세요. VS Code 연동 시 동일 해시의 원문으로 UTF-16 좌표 변환이 필요합니다.

`node:<sha256>` ID는 종류·경로·중첩 이름·시작 위치의 정규화된 값에서 생성합니다. `edge:<sha256>`는 종류·source·target·근거·import 항목 순번·상태 등을 포함합니다. 같은 줄의 여러 호출도 열 위치로 구분됩니다. ID는 영구적인 심볼 추적용이 아닙니다.

`snapshot_id`는 분석기·스키마·Python 버전, 해석 옵션, 정렬된 파일 목록·원본 바이트 해시·파싱 상태, 분석 상태와 실제 노드·관계에서 계산합니다. 같은 Python 파일 목록이어도 제외 범위에 따라 관계가 달라지면 다른 snapshot이 됩니다. 시각·소요 시간·출력 위치 자체는 제외합니다. 프로젝트 전체의 원자적 파일시스템 스냅샷을 보장하지 않습니다.

## 노드와 관계

노드는 `file`, `class`, `function`, `method`이며 비동기는 `is_async`로 나타냅니다. 파일 이외의 정의는 parent와 contains 관계를 갖습니다. 매개변수 종류·기본값·타입 힌트는 선언된 텍스트이고 실제 런타임 값이 아닙니다.

| 관계 | 방향 / 특징 |
| --- | --- |
| `contains` | 부모→자식. 항상 실제 target. resolution_status 없음 |
| `imports` | 가져오는 범위→내부 파일 또는 정의. import 항목별 기록 |
| `calls` | 호출이 속한 범위→내부 정의. 호출 위치별 기록 |

resolved target은 반드시 nodes에 존재합니다. builtin·external·unresolved는 target null입니다. builtin_name, external_name 또는 reason이 대상을 설명합니다. external의 origin_verified는 false이며 `외부 패키지 설치 확인`을 뜻하지 않습니다.

각 관계의 evidence는 실제 표현식 범위이며 provenance에는 `provider: python_ast`와 적용 규칙이 있습니다. context는 module_body, class_body, function_body, definition_expression, annotation입니다. 타입 힌트의 호출은 실제 실행 여부가 확정되지 않았다는 표시입니다.

## 설명과 집계

insights에는 overview, entry_points, reading_order, reading_limit, components, metrics, file_relations가 있습니다. `observed`는 구조 집계, `documented`는 작성자 docstring, `heuristic`은 규칙에 따른 후보입니다. 각 설명의 node ID·edge ID·evidence로 원자료를 확인합니다.

읽기 안내는 기본 깊이 2, 최대 20개입니다. 생략 수는 탐색 경계에서 확인된 추가 노드 수로, 저장소 전체의 미표시 노드 수가 아닙니다. 순환 ID도 이 제한된 탐색에서 발견한 관계입니다. import 자체나 일반 식별자 참조를 호출 간선으로 변환하지 않습니다.

통계의 호출 상태 합은 파싱 성공 파일의 전체 ast.Call 수와 일치합니다. 해석률은 정확도가 아닙니다. 호출이 없으면 해석률·미해결률은 null입니다. 파싱 실패 파일에는 내부 구조를 추정해 채우지 않습니다.

## 저장 결과 소비

JSON stdout은 단일 분석 객체입니다. 파일 결과는 analysis.json, report.md, report.html와 마지막에 기록하는 manifest.json으로 구성합니다. manifest는 producer, schema_version, project_root, snapshot_id, artifacts의 SHA-256을 저장합니다.

파일 결과를 읽을 때 `verify_manifest(directory)`가 true인지 확인하세요. 다중 파일 교체 전체가 원자적이지 않으므로 완료 표식과 해시가 맞지 않으면 재분석 결과를 기다리거나 오류로 처리해야 합니다. 편집기에서 실제 코드로 이동하거나 후속 AI 입력을 구성할 때 해당 소스 파일의 해시도 따로 확인해야 합니다.

스키마 2.x에서 기존 의미를 보존하는 필드 추가는 가능하지만 소비자는 미지원 주 버전을 거부해야 합니다. 이번 패키지 버전은 0.1.0이고 데이터 버전 2.0과 독립적입니다.
