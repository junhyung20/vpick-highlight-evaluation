# Vpick 숏폼 하이라이트 품질 평가 체계

LLM이 고른 숏폼 하이라이트 장면이 얼마나 좋은지 객관적으로 재는 평가 체계를 만들고,
이를 이용해 Gemini(생성형)와 Jev(판별형)의 장면 채점 성능을 비교합니다.

- 2026 AI P-실무프로젝트 · AI-1분반-4조 (오승근, 이민지, 이준형)
- 기업 연계: CLOUDIKE × Vpick

## 폴더 구조

| 폴더 | 내용 |
|---|---|
| `src/collect` | 채널에서 롱폼-숏폼 페어 자동 찾기 |
| `src/match` | 숏폼이 롱폼의 어느 구간인지 찾기 (정답 구간) |
| `src/vpick` | Vpick 장면 데이터·베이스라인 수집 |
| `src/eval` | IoU, 적중률, 순위 등 평가 지표 |
| `src/experiment` | Gemini·Jev 장면 채점 실험 |
| `data/` | 채널·페어 목록, 매칭 결과, 정답 구간, Vpick 데이터 (저장 형식은 `SCHEMA.md`) |
| `results/` | 평가 결과 |

## 설치 (Windows)

Git Bash 기준:

```
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

(명령 프롬프트에서는 `.venv\Scripts\activate`)

루트 폴더에 `.env` 파일을 만들고 `GEMINI_API_KEY=본인키`를 적어주세요. (깃에 올리지 않습니다)

## 정답 구간 만들기

모든 명령은 저장소 최상위 폴더에서 실행합니다.

### 1. 채널 고르기 (사람)

- 쇼츠 제목 아래 ▶ "관련 동영상" 버튼으로 원본 롱폼을 걸어두는 채널
- 롱폼이 5분 이상인 채널
- 팀 구글 시트 [채널] 탭에 채널명, 채널 URL, 장르를 적고, CSV로 다운로드해서 `data/channels.csv`로 저장

### 2. 페어 찾기 + 매칭 (자동)

```
python src/collect/find_pairs.py --shorts 20 && python src/match/match_batch.py --pairs data/pairs_auto.csv
```

- `find_pairs.py`: 채널의 최근 쇼츠에서 관련 동영상 롱폼을 찾아 `data/pairs_auto.csv` 생성
  (5분 미만·다른 채널 롱폼 제외, 채널당 롱폼 5개, 롱폼당 쇼츠 3개까지)
- `match_batch.py`: 자막으로 숏폼이 롱폼의 어느 구간인지 찾아 `data/pilot_results.csv` 생성
  - 숏폼 문장마다 롱폼 위치를 따로 찾아, 이어 붙인 숏폼도 구간 여러 개로 찾습니다
  - 결과의 `구간 수`, `문장 커버리지`, `구간 목록(ms)` 칸을 봅니다

### 3. 채택 판단

| 문장 커버리지 | 판단 |
|---|---|
| 0.8 이상 | 자동 채택, `구간 목록` 전체가 정답 구간 |
| 0.3 이하 | 자동 제외 (롱폼을 잘라낸 게 아니라 따로 제작한 숏폼) |
| 그 사이 | 사람이 확인 |

기준은 파일럿 12개 페어를 사람이 검수해서 정한 초안입니다.
결과는 팀 구글 시트 [페어] 탭에 붙여넣어 관리합니다.

### 기타

- 페어를 손으로 찾았을 때: 시트 [페어 입력] 탭에 적고 CSV로 받아 `data/pairs.csv`로 저장한 뒤 `python src/match/match_batch.py`
- 페어 하나만 확인: `python src/match/match_one.py "롱폼URL" "숏폼URL"`

### 알려진 한계

- 자막(유튜브 자동 자막)으로 찾기 때문에 말이 거의 없는 영상은 찾기 어렵습니다
- 자막 한 줄이 몇 초씩 걸쳐 있어서 구간 경계가 몇 초 넉넉하게 잡힐 수 있습니다
- 자막이 없는 영상은 에러로 표시되고 건너뜁니다 (`--whisper` 옵션은 STT용, 별도 설치 필요)
