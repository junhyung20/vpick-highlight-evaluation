# 데이터 저장 규칙 (SCHEMA)

팀원 모두가 같은 형식으로 저장하기 위한 규칙입니다. 새 파일을 만들기 전에 꼭 확인해 주세요.

## 1. 공통 규칙

- **연결 키**: 모든 파일은 유튜브 영상 ID(**롱폼 ID**)로 연결합니다.
  - 예: 롱폼 `https://www.youtube.com/watch?v=abc123XYZ00` → `long_id = "abc123XYZ00"`
  - 롱폼 단위 파일명은 `{long_id}.json` 형식으로 저장합니다.
- **시간 단위**: 시간은 전부 **밀리초(ms) 정수**로 저장합니다. 초, 소수, `"00:01:23"` 같은 문자열은 쓰지 않습니다.
  - 예: 1분 23.5초 → `83500`
- **장르**: 아래 9개 중 하나만 사용합니다. (표기 그대로, 띄어쓰기·슬래시 포함)

  | 장르 |
  |---|
  | 예능/토크 |
  | 스포츠/현장 |
  | 브이로그/일상 |
  | 뉴스/시사 |
  | 인터뷰/대담 |
  | 드라마/영화 |
  | 게임 |
  | 교육/튜토리얼 |
  | 그 외 |

- **개수 세는 기준**: 데이터 개수는 **롱폼 기준**으로 셉니다. 한 롱폼에서 숏폼이 여러 개 나왔다면, 그 롱폼의 정답 구간이 여러 개가 됩니다.

## 2. 저장 위치

| 종류 | 저장 위치 |
|---|---|
| 사람이 적는 기록 (채널 목록, 롱폼-숏폼 페어, 검수 기록) | **팀 구글 시트** |
| 코드가 만드는 결과 (자막, 정답 구간, Vpick 응답, 평가 결과) | **`data/`** (평가 결과는 `results/`) |

## 3. `data/ground_truth.jsonl`

롱폼-숏폼 페어 1개당 **한 줄**(JSON 한 개)입니다.

```json
{"long_id": "...", "short_id": "...", "segments": [[시작ms, 끝ms]], "method": "subtitle", "text_score": 78.3, "length_ratio": 1.0, "accepted": null}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `long_id` | 문자열 | 롱폼 유튜브 영상 ID |
| `short_id` | 문자열 | 숏폼 유튜브 영상 ID |
| `segments` | `[[int, int], ...]` | 롱폼 안에서 숏폼에 해당하는 구간 `[시작ms, 끝ms]` 목록 |
| `method` | 문자열 | 매칭 방법 (예: `"subtitle"`, `"subtitle+whisper"`) |
| `text_score` | 실수 | 자막 텍스트 유사도 점수 (0~100) |
| `length_ratio` | 실수 | 매칭 구간 길이 / 숏폼 길이 |
| `accepted` | `null` / `true` / `false` | 검수 전에는 `null`, 검수 후 통과면 `true`, 탈락이면 `false` |

## 4. `data/vpick/scenes/{long_id}.json`

Vpick 장면 분석 API 응답을 저장합니다. 평가에 쓰는 필드는 다음과 같습니다.

| 필드 | 설명 |
|---|---|
| `data[].start_ms` | 장면 시작 (ms) |
| `data[].end_ms` | 장면 끝 (ms) |
| `data[].scene_name` | 장면 이름 |
| `data[].description` | 장면 설명 |
| `data[].speeches[].text` | 장면 내 발화 텍스트 |
| `data[].persons[]` | 등장 인물 |
| `summary.description` | 영상 전체 요약 |

## 5. `data/vpick/baseline/{long_id}.json`

Vpick 베이스라인 숏폼 생성 결과를 저장합니다. 평가에 쓰는 필드는 다음과 같습니다.

| 필드 | 설명 |
|---|---|
| `generation_metadata.scenes[].source_start_ms` | 원본(롱폼) 기준 시작 (ms) |
| `generation_metadata.scenes[].source_end_ms` | 원본(롱폼) 기준 끝 (ms) |
| `generation_metadata.scenes[].asset_id` | 장면 에셋 ID |
| `generation_metadata.scenes[].overall_score` | 장면 종합 점수 |
| `generation_metadata.scenes[].duration_ms` | 장면 길이 (ms) |
