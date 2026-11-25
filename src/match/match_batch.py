"""
페어 여러 개를 한꺼번에 매칭 (파일럿용 일괄 실행)

1. data/pairs.csv 를 준비한다.
   - 구글 시트 [페어 입력] 탭을 CSV로 다운로드해서 data/pairs.csv 로 저장
     (파일 > 다운로드 > CSV, 제목 줄 "롱폼 URL, 숏폼 URL, 채널명, 장르, 링크 출처, 담당자"를 그대로 읽음)
   - find_pairs.py 가 만든 파일(영어 제목 줄)도 그대로 읽음

2. 저장소 최상위 폴더에서 실행
   python src/match/match_batch.py

3. data/pilot_results.csv 가 만들어진다.
   열 순서가 구글 시트 [페어] 탭과 같아서, 열어서 복사한 뒤 시트에 붙여넣으면 된다.
   메모 칸에 확인 링크(또는 에러 내용)가 들어 있다.
"""
import csv
import os

from match_one import WORK, download_subs, match, parse_json3, video_duration_ms, video_id

PAIRS = "data/pairs.csv"
OUT = "data/pilot_results.csv"
HEADER = ["롱폼 ID", "숏폼 ID", "채널명", "장르", "링크 출처", "정답 시작(ms)", "정답 끝(ms)",
          "텍스트 유사도", "길이 비율", "사람 판정", "채택", "담당자", "메모"]


def normalize_pair(row):
    """시트에서 받은 한글 제목 줄과 영어 제목 줄 둘 다 지원"""
    def get(*keys):
        for k in keys:
            if row.get(k):
                return row[k].strip()
        return ""
    return {
        "long_url": get("long_url", "롱폼 URL"),
        "short_url": get("short_url", "숏폼 URL"),
        "channel": get("channel", "채널명"),
        "genre": get("genre", "장르"),
        "link_source": get("link_source", "링크 출처"),
        "owner": get("owner", "담당자"),
    }


def run_pair(long_url, short_url):
    long_id, short_id = video_id(long_url), video_id(short_url)
    if not long_id or not short_id:
        raise RuntimeError("영상 ID를 못 가져옴 (URL 확인)")

    long_sub = download_subs(long_url, long_id)
    if not long_sub:
        raise RuntimeError("롱폼 자막 없음")
    short_sub = download_subs(short_url, short_id)
    if not short_sub:
        raise RuntimeError("숏폼 자막 없음")

    short_cues = parse_json3(short_sub)
    short_text = " ".join(c[2] for c in short_cues)
    short_dur = video_duration_ms(short_url)
    best = match(parse_json3(long_sub), short_text, short_dur)
    if best["score"] < 0:
        raise RuntimeError("매칭 실패 (롱폼 자막이 너무 짧음)")

    return {
        "long_id": long_id,
        "short_id": short_id,
        "start": best["start_ms"],
        "end": best["end_ms"],
        "score": round(best["score"], 1),
        "ratio": round((best["end_ms"] - best["start_ms"]) / short_dur, 3),
        "link": f"https://youtu.be/{long_id}?t={best['start_ms'] // 1000}",
    }


def main():
    os.makedirs(WORK, exist_ok=True)
    with open(PAIRS, encoding="utf-8-sig", newline="") as f:
        pairs = [p for p in map(normalize_pair, csv.DictReader(f))
                 if p["long_url"].startswith("http") and p["short_url"].startswith("http")]

    rows = []
    for n, p in enumerate(pairs, 1):
        print(f"[{n}/{len(pairs)}] {p['short_url']}")
        base = [p["channel"], p["genre"], p["link_source"]]
        try:
            r = run_pair(p["long_url"], p["short_url"])
            rows.append([r["long_id"], r["short_id"], *base, r["start"], r["end"],
                         r["score"], r["ratio"], "미검수", "", p["owner"], r["link"]])
            print(f"    유사도 {r['score']}, 길이 {r['ratio']}배")
        except Exception as e:
            rows.append([p["long_url"], p["short_url"], *base, "", "", "", "", "미검수", "X", p["owner"],
                         f"에러: {e}"])
            print(f"    에러: {e}")

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)

    ok = sum(1 for r in rows if r[5] != "")
    print(f"\n완료: {len(rows)}개 중 {ok}개 매칭, 결과는 {OUT}")


if __name__ == "__main__":
    main()
