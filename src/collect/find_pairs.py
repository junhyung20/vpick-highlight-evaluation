"""
채널 목록 → 롱폼-숏폼 페어 후보 자동 찾기 (쇼츠 "관련 동영상" 링크 이용)

쇼츠 화면 아래 ▶ 관련 동영상 버튼에 걸린 롱폼을 원본으로 보고 짝을 짓는다.
버튼 정보는 쇼츠 웹페이지 안 "reelCarouselButtonViewModel" 다음의 /watch?v= 링크에 있다.
(2026-11 파일럿 12개 페어로 확인: 12개 모두 이 위치에서 정답 롱폼을 찾음)

1. data/channels.csv 를 준비한다.
   - 구글 시트 [채널] 탭을 CSV로 다운로드해서 data/channels.csv 로 저장
     (제목 줄 "채널명, 채널 URL, 장르"를 그대로 읽음, "(예시)" 줄은 건너뜀)

2. 저장소 최상위 폴더에서 실행
   python src/collect/find_pairs.py
   (옵션) --shorts 30          채널마다 최근 쇼츠 몇 개를 볼지 (기본 30)
          --max-long 5         채널당 롱폼 최대 개수 (기본 5)
          --per-long 3         롱폼 하나당 쇼츠 최대 개수 (기본 3)
          --min-long-sec 300   롱폼 최소 길이(초) (기본 300 = 5분)
          --allow-other-channel  관련 동영상이 다른 채널 영상이어도 포함

3. 결과는 data/pairs_auto.csv 에 저장된다 (실행할 때마다 새로 만듦).
   열 순서가 구글 시트 [페어 입력] 탭과 같아서, 내용을 복사해 시트에 붙여넣으면 된다.
   그다음 [페어 입력] 탭을 CSV로 받아 data/pairs.csv 로 저장하고 match_batch.py 를 실행.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import time
import urllib.request

YTDLP = [sys.executable, "-m", "yt_dlp"]
CHANNELS = "data/channels.csv"
OUT = "data/pairs_auto.csv"
OUT_HEADER = ["롱폼 URL", "숏폼 URL", "채널명", "장르", "링크 출처", "담당자", "메모"]
WATCH_RE = re.compile(r"/watch\?v=([A-Za-z0-9_-]{11})")
RELATED_KEY = "reelCarouselButtonViewModel"


def normalize_channel(row):
    """시트에서 받은 한글 제목 줄과 영어 제목 줄 둘 다 지원"""
    return {
        "channel_url": (row.get("channel_url") or row.get("채널 URL") or "").strip(),
        "channel": (row.get("channel") or row.get("채널명") or "").strip(),
        "genre": (row.get("genre") or row.get("장르") or "").strip(),
        "owner": (row.get("owner") or row.get("담당자") or "").strip(),
    }


CHANNEL_TABS = ("featured", "videos", "shorts", "streams", "playlists", "community", "about")


def shorts_url(channel_url):
    """채널 주소 뒤에 붙은 ?si=... 나 /featured 같은 탭 이름을 떼고 /shorts 를 붙인다"""
    url = channel_url.strip().split("?")[0].rstrip("/")
    last = url.rsplit("/", 1)[-1]
    if last in CHANNEL_TABS:
        url = url.rsplit("/", 1)[0]
    return url + "/shorts"


def list_shorts(channel_url, n):
    """채널의 최근 쇼츠 ID 목록과 채널 ID (영상 정보는 안 받아서 빠름)"""
    out = subprocess.run(
        YTDLP + ["-J", "--flat-playlist", "--playlist-end", str(n), "--no-warnings",
                 shorts_url(channel_url)],
        capture_output=True, text=True, encoding="utf-8",
    )
    data = json.loads(out.stdout or "{}")
    ids = [e["id"] for e in data.get("entries") or [] if e.get("id")]
    return data.get("channel_id"), ids[:n]


def page_html(short_id):
    req = urllib.request.Request(
        f"https://www.youtube.com/shorts/{short_id}",
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def related_long_id(short_id, tries=3, wait=3):
    """쇼츠 페이지에서 관련 동영상 롱폼 ID 찾기.
    유튜브가 가끔 버튼 정보가 빠진 페이지를 주기 때문에, 못 찾으면 잠깐 쉬고 다시 받아본다.
    돌려주는 값: (롱폼 ID 또는 None, "찾음" / "없음")"""
    for t in range(tries):
        try:
            html = page_html(short_id)
        except Exception:
            time.sleep(wait)
            continue
        # 1순위: 관련 동영상 버튼 뒤에 나오는 링크 중 자기 자신이 아닌 첫 번째
        i = html.find(RELATED_KEY)
        if i >= 0:
            for m in WATCH_RE.finditer(html, i):
                if m.group(1) != short_id:
                    return m.group(1), "찾음"
        # 2순위: 페이지에 자기 자신 말고 다른 /watch 링크가 있으면 그것
        #   (파일럿 12개 모두 페이지에 링크가 자기 자신 + 관련 동영상 2개뿐이었음)
        others = [v for v in WATCH_RE.findall(html) if v != short_id]
        if others:
            return others[0], "찾음"
        if t < tries - 1:
            time.sleep(wait)
    return None, "없음"


def video_infos(ids):
    """롱폼 후보들의 길이·채널 정보 (하나 받을 때마다 진행 상황 출력)"""
    if not ids:
        return {}
    proc = subprocess.Popen(
        YTDLP + ["-j", "--skip-download", "--ignore-errors", "--no-warnings",
                 *[f"https://www.youtube.com/watch?v={i}" for i in ids]],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
    )
    infos = {}
    for line in proc.stdout:
        if line.startswith("{"):
            try:
                info = json.loads(line)
            except json.JSONDecodeError:
                continue
            infos[info["id"]] = info
            print(f"    롱폼 정보 {len(infos)}/{len(ids)}  {(info.get('title') or '')[:30]}",
                  flush=True)
    proc.wait()
    return infos


def find_channel_pairs(ch, args):
    print("  쇼츠 목록 받는 중...", flush=True)
    channel_id, short_ids = list_shorts(ch["channel_url"], args.shorts)
    print(f"  쇼츠 {len(short_ids)}개", flush=True)

    links = []  # (short_id, long_id)
    for k, sid in enumerate(short_ids, 1):
        lid, status = related_long_id(sid)
        print(f"    쇼츠 {k}/{len(short_ids)} {sid}: "
              f"{'관련 동영상 ' + lid if lid else '관련 동영상 없음 (3번 시도)'}", flush=True)
        if lid:
            links.append((sid, lid))
        time.sleep(1)  # 유튜브에 너무 빠르게 요청하지 않기
    print(f"  관련 동영상이 있는 쇼츠 {len(links)}개", flush=True)

    infos = video_infos(sorted({lid for _, lid in links}))

    pairs, per_long = [], {}
    skipped = {"짧은 롱폼": 0, "다른 채널": 0, "정보 없음": 0, "개수 제한": 0}
    for sid, lid in links:  # 최근 쇼츠부터
        info = infos.get(lid)
        if not info:
            skipped["정보 없음"] += 1
            continue
        if (info.get("duration") or 0) < args.min_long_sec:
            skipped["짧은 롱폼"] += 1
            continue
        if (not args.allow_other_channel and channel_id
                and info.get("channel_id") != channel_id):
            skipped["다른 채널"] += 1
            continue
        if lid not in per_long and len(per_long) >= args.max_long:
            skipped["개수 제한"] += 1
            continue
        if per_long.get(lid, 0) >= args.per_long:
            skipped["개수 제한"] += 1
            continue
        per_long[lid] = per_long.get(lid, 0) + 1
        pairs.append([f"https://www.youtube.com/watch?v={lid}",
                      f"https://www.youtube.com/shorts/{sid}",
                      ch["channel"], ch["genre"], "관련 동영상", ch["owner"], ""])
    print(f"  페어 {len(pairs)}개 (롱폼 {len(per_long)}개), 제외: "
          + ", ".join(f"{k} {v}" for k, v in skipped.items() if v), flush=True)
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shorts", type=int, default=30)
    ap.add_argument("--max-long", type=int, default=5)
    ap.add_argument("--per-long", type=int, default=3)
    ap.add_argument("--min-long-sec", type=int, default=300)
    ap.add_argument("--allow-other-channel", action="store_true")
    args = ap.parse_args()

    with open(CHANNELS, encoding="utf-8-sig", newline="") as f:
        channels = [c for c in map(normalize_channel, csv.DictReader(f))
                    if c["channel_url"].startswith("http") and not c["channel"].startswith("(예시)")]

    rows = []
    for n, ch in enumerate(channels, 1):
        print(f"\n[{n}/{len(channels)}] {ch['channel'] or ch['channel_url']}", flush=True)
        try:
            rows += find_channel_pairs(ch, args)
        except Exception as e:
            print(f"  에러: {e}", flush=True)

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(OUT_HEADER)
        w.writerows(rows)
    print(f"\n완료: 페어 {len(rows)}개를 {OUT}에 저장")


if __name__ == "__main__":
    main()
