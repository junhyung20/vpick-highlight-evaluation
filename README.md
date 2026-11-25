# Vpick 숏폼 하이라이트 품질 평가 체계

LLM이 고른 숏폼 하이라이트 장면이 얼마나 좋은지 객관적으로 재는 평가 체계를 만들고,
이를 이용해 Gemini(생성형)와 Jev(판별형)의 장면 채점 성능을 비교합니다.

- 2026 AI P-실무프로젝트 · AI-1분반-4조 (오승근, 이민지, 이준형)
- 기업 연계: CLOUDIKE × Vpick

## 폴더 구조

| 폴더 | 내용 |
|---|---|
| `src/collect` | 채널에서 롱폼-숏폼 페어 후보 찾기 |
| `src/match` | 숏폼이 롱폼의 어느 구간인지 찾기 (정답 구간) |
| `src/vpick` | Vpick 장면 데이터·베이스라인 수집 |
| `src/eval` | IoU, 적중률, 순위 등 평가 지표 |
| `src/experiment` | Gemini·Jev 장면 채점 실험 |
| `data/` | 페어 목록, 매칭 결과, 정답 구간, Vpick 데이터 (저장 형식은 `SCHEMA.md`) |
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

1. 팀 구글 시트 [페어 입력] 탭에 롱폼 URL, 숏폼 URL, 채널명, 장르를 적는다
   - 쇼츠 제목 아래 ▶ "관련 동영상" 링크나 설명란 풀영상 링크로 원본 롱폼을 찾는다
   - 롱폼 5분 이상, 채널당 롱폼 5개까지, 한 롱폼에서 쇼츠 2~3개까지
2. [페어 입력] 탭을 CSV로 다운로드해서 `data/pairs.csv`로 저장한다
3. 일괄 매칭

```
python src/match/match_batch.py
```

4. `data/pilot_results.csv`를 시트 [페어] 탭에 붙여넣고, 메모 칸 링크로 위치가 맞는지 확인해 O/X를 적는다

페어 하나만 확인할 때:

```
python src/match/match_one.py "롱폼URL" "숏폼URL"
```

참고: `src/collect/find_pairs.py`는 쇼츠 설명란에 풀영상 링크가 있는 채널에서 페어를 자동으로 찾습니다.
"관련 동영상" 링크는 아직 읽지 못합니다.
