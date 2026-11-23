# vpick-highlight-evaluation

유튜브 롱폼-숏폼 페어에서 크리에이터가 잘라낸 구간을 정답으로 삼아, Vpick 베이스라인과 Gemini/Jev 모델이 고른 하이라이트 구간을 IoU 등으로 채점하는 **LLM 기반 숏폼 하이라이트 장면 선택 품질 평가 체계**입니다.

데이터 저장 규칙은 [SCHEMA.md](SCHEMA.md)를 먼저 읽어 주세요.

## 폴더 구조

```
.
├─ README.md
├─ SCHEMA.md              # 팀 데이터 저장 규칙
├─ requirements.txt
├─ .env.example           # API 키 템플릿 (.env로 복사해서 사용)
├─ data/
│  ├─ raw/subs/           # 내려받은 자막·오디오 원본 (git 제외)
│  ├─ ground_truth.jsonl  # 롱폼-숏폼 정답 구간
│  └─ vpick/
│     ├─ scenes/          # Vpick 장면 분석 결과 ({long_id}.json)
│     └─ baseline/        # Vpick 베이스라인 숏폼 결과 ({long_id}.json)
├─ src/
│  ├─ collect/            # 채널·롱폼-숏폼 페어 수집
│  ├─ match/              # 롱폼-숏폼 구간 매칭 → 정답 구간 생성 (match_one.py)
│  ├─ vpick/              # Vpick 데이터 수집·변환
│  ├─ eval/               # IoU 등 평가 지표 계산
│  └─ experiment/         # Gemini/Jev 모델 하이라이트 선택 실험
├─ notebooks/             # 분석·시각화용 노트북
└─ results/               # 평가·실험 결과
```

## 설치 (Windows, Python 3.10)

저장소 최상위 폴더에서 실행합니다.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

API 키가 필요한 경우 `.env.example`을 `.env`로 복사한 뒤 키를 채워 넣습니다. (`.env`는 git에 올라가지 않습니다.)

```bat
copy .env.example .env
```

숏폼에 자동 자막이 없어 STT가 필요할 때만 추가로 설치합니다. (ffmpeg 필요)

```bat
pip install faster-whisper
```

## 실행

반드시 **저장소 최상위 폴더**에서 실행합니다.

```bat
python src/match/match_one.py "롱폼URL" "숏폼URL"
```

숏폼에 자막이 없을 때:

```bat
python src/match/match_one.py "롱폼URL" "숏폼URL" --whisper
```

결과는 화면에 출력되고 `data/ground_truth.jsonl`에 한 줄 추가됩니다.
