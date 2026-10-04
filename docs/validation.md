# 구현 검증 기록

검증일: 2026-10-04 · 분석기 0.1.0 · 데이터 계약 2.0

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
