"""
채널 목록 → 롱폼-숏폼 페어 후보 자동 찾기

1. data/channels.csv 를 준비한다. 두 방법 중 편한 것:
   - 구글 시트 [채널] 탭을 CSV로 다운로드해서 data/channels.csv 로 저장
     (파일 > 다운로드 > CSV, 제목 줄 "채널명, 채널 URL, 장르"를 그대로 읽음)
   - 직접 적기 (첫 줄은 제목 줄)
     channel_url,channel,genre
     https://www.youtube.com/@채널핸들,채널명,예능/토크

2. 저장소 최상위 폴더에서 실행
   python src/collect/find_pairs.py
   (옵션) --shorts 50       채널마다 최근 쇼츠 몇 개를 볼지 (기본 50)
          --max-long 5      채널당 롱폼 최대 개수 (기본 5)
          --min-long-sec 300  롱폼 최소 길이(초) (기본 300 = 5분)
          --allow-other-channel  풀영상 링크가 다른 채널 영상이어도 포함

3. 쇼츠 설명란에 있는 유튜브 링크를 원본 롱폼으로 보고 짝을 지은 뒤,
   data/pairs.csv 에 추가한다 (이미 있는 숏폼은 건너뜀).
   그다음 python src/match/match_batch.py 로 매칭하면 된다.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys

YTDLP = [sys.executable, "-m", "yt_dlp"]
CHANNELS = "data/channels.csv"
PAIRS = "data/pairs.csv"
PAIR_HEADER = ["long_url", "short_url", "channel", "genre", "link_source"]
LINK_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def dump_json(urls, extra=()):
    """yt-dlp로 영상 정보(JSON)를 한 번에 가져오기. 실패한 영상은 건너뜀."""
    if not urls:
        return []
    out = subprocess.run(
        YTDLP + ["-j", "--skip-download", "--ignore-errors", "--no-warnings", *extra, *urls],
        capture_output=True, text=True, encoding="utf-8",
    )
    infos = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                infos.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return infos


def shorts_url(channel_url):
    url = channel_url.strip().rstrip("/")
    return url if url.endswith("/shorts") else url + "/shorts"


def linked_ids(description, own_id):
    """설명란에서 유튜브 영상 ID 뽑기 (자기 자신 제외, 순서 유지)"""
    ids = []
    for vid in LINK_RE.findall(description or ""):
        if vid != own_id and vid not in ids:
            ids.append(vid)
    return ids


def normalize_channel(row):
    """시트에서 받은 한글 제목 줄과 영어 제목 줄 둘 다 지원"""
    return {
        "channel_url": (row.get("channel_url") or row.get("채널 URL") or "").strip(),
        "channel": (row.get("channel") or row.get("채널명") or "").strip(),
        "genre": (row.get("genre") or row.get("장르") or "").strip(),
    }


def find_channel_pairs(ch, n_shorts, max_long, min_long_sec, allow_other):
    shorts = dump_json([shorts_url(ch["channel_url"])], ["--playlist-end", str(n_shorts)])
    print(f"  쇼츠 {len(shorts)}개 확인")

    # 쇼츠마다 설명란 링크 후보
    cand = {}  # short_id -> (short_info, [long_id 후보])
    for s in shorts:
        ids = linked_ids(s.get("description"), s.get("id"))
        if ids:
            cand[s["id"]] = (s, ids)
    print(f"  설명란에 유튜브 링크가 있는 쇼츠 {len(cand)}개")

    # 후보 롱폼 정보 한꺼번에 가져오기
    all_ids = sorted({i for _, ids in cand.values() for i in ids})
    longs = {info["id"]: info for info in
             dump_json([f"https://www.youtube.com/watch?v={i}" for i in all_ids])}

    pairs, used_longs = [], []
    for short_id, (s, ids) in cand.items():  # 최근 쇼츠부터
        for lid in ids:
            info = longs.get(lid)
            if not info or (info.get("duration") or 0) < min_long_sec:
                continue
            if not allow_other and info.get("channel_id") != s.get("channel_id"):
                continue
            if lid not in used_longs:
                if len(used_longs) >= max_long:
                    continue
                used_longs.append(lid)
            pairs.append([f"https://www.youtube.com/watch?v={lid}",
                          f"https://www.youtube.com/shorts/{short_id}",
                          ch.get("channel", ""), ch.get("genre", ""), "설명란 링크"])
            break  # 쇼츠 하나당 롱폼 하나
    print(f"  페어 {len(pairs)}개 (롱폼 {len(used_longs)}개)")
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shorts", type=int, default=50)
    ap.add_argument("--max-long", type=int, default=5)
    ap.add_argument("--min-long-sec", type=int, default=300)
    ap.add_argument("--allow-other-channel", action="store_true")
    args = ap.parse_args()

    with open(CHANNELS, encoding="utf-8-sig", newline="") as f:
        channels = [c for c in map(normalize_channel, csv.DictReader(f))
                    if c["channel_url"].startswith("http") and not c["channel"].startswith("(예시)")]

    existing = set()
    if os.path.exists(PAIRS):
        with open(PAIRS, encoding="utf-8-sig", newline="") as f:
            existing = {p.get("short_url", "").strip() for p in csv.DictReader(f)}

    new_rows = []
    for n, ch in enumerate(channels, 1):
        print(f"[{n}/{len(channels)}] {ch.get('channel') or ch['channel_url']}")
        try:
            for row in find_channel_pairs(ch, args.shorts, args.max_long,
                                          args.min_long_sec, args.allow_other_channel):
                if row[1] not in existing:
                    existing.add(row[1])
                    new_rows.append(row)
        except Exception as e:
            print(f"  에러: {e}")

    write_header = not os.path.exists(PAIRS) or os.path.getsize(PAIRS) == 0
    with open(PAIRS, "a", encoding="utf-8-sig" if write_header else "utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(PAIR_HEADER)
        w.writerows(new_rows)
    print(f"\n완료: 새 페어 {len(new_rows)}개를 {PAIRS}에 추가")


if __name__ == "__main__":
    main()
