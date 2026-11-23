"""
롱폼-숏폼 1쌍 자막 기반 구간 매칭 (파일럿용)

사용법:
    pip install yt-dlp rapidfuzz
    python src/match/match_one.py "<롱폼 URL>" "<숏폼 URL>"

    # 숏폼에 자동 자막이 없을 때 (STT 사용, ffmpeg 필요)
    pip install faster-whisper
    python src/match/match_one.py "<롱폼 URL>" "<숏폼 URL>" --whisper

결과: 화면 출력 + data/ground_truth.jsonl 에 한 줄 추가
저장소 최상위 폴더(pfrog-highlight-eval)에서 실행할 것
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

from rapidfuzz import fuzz

WORK = "data/raw/subs"
# Windows에서 yt-dlp 명령을 못 찾는 문제를 피하려고 파이썬 모듈로 실행
YTDLP = [sys.executable, "-m", "yt_dlp"]


# ---------- 다운로드 ----------
def video_id(url):
    out = subprocess.run(YTDLP + ["--get-id", url], capture_output=True, text=True)
    return out.stdout.strip()


def video_duration_ms(url):
    out = subprocess.run(YTDLP + ["--print", "duration", url], capture_output=True, text=True)
    return int(float(out.stdout.strip()) * 1000)


def download_subs(url, vid):
    """한국어 자막(수동 자막 우선, 없으면 자동 자막)을 json3로 받기"""
    subprocess.run(YTDLP + [
        "--skip-download",
        "--write-subs", "--write-auto-subs",
        "--sub-langs", "ko.*,ko",
        "--sub-format", "json3",
        "-o", f"{WORK}/{vid}.%(ext)s", url,
    ], capture_output=True, text=True)
    files = sorted(glob.glob(f"{WORK}/{vid}*.json3"))
    return files[0] if files else None


def parse_json3(path):
    """json3 -> [(start_ms, end_ms, text), ...]"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cues = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if not text or text == "\n":
            continue
        start = ev.get("tStartMs", 0)
        end = start + ev.get("dDurationMs", 0)
        cues.append((start, end, text))
    return cues


def whisper_cues(url, vid):
    """자막이 없는 숏폼: 오디오 받아서 faster-whisper로 STT"""
    from faster_whisper import WhisperModel
    subprocess.run(YTDLP + [
        "-x", "--audio-format", "wav",
        "-o", f"{WORK}/{vid}.%(ext)s", url,
    ], capture_output=True, text=True)
    device = "cuda" if _has_cuda() else "cpu"
    model = WhisperModel("small", device=device,
                         compute_type="float16" if device == "cuda" else "int8")
    segments, _ = model.transcribe(f"{WORK}/{vid}.wav", language="ko")
    return [(int(s.start * 1000), int(s.end * 1000), s.text.strip()) for s in segments]


def _has_cuda():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


# ---------- 매칭 ----------
def norm(text):
    """공백·문장부호 제거 (자동 자막 띄어쓰기 차이 무시)"""
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text)


def match(long_cues, short_text, short_dur_ms, min_ratio=0.5, max_ratio=1.5):
    """
    롱폼 자막 위에서 창(window)을 밀어가며 숏폼 대사와 가장 비슷한 구간 찾기.
    창 길이는 숏폼 길이의 0.5~1.5배 범위에서만 본다.
    """
    target = norm(short_text)
    best = {"score": -1}
    for i in range(len(long_cues)):
        start = long_cues[i][0]
        buf = ""
        for j in range(i, len(long_cues)):
            end = long_cues[j][1]
            dur = end - start
            if dur > short_dur_ms * max_ratio:
                break
            buf += norm(long_cues[j][2])
            if dur < short_dur_ms * min_ratio:
                continue
            score = fuzz.ratio(target, buf)
            if score > best["score"]:
                best = {"score": score, "start_ms": start, "end_ms": end}
    return best


# ---------- 메인 ----------
def main():
    os.makedirs("data", exist_ok=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("long_url")
    ap.add_argument("short_url")
    ap.add_argument("--whisper", action="store_true", help="숏폼 자막 대신 STT 사용")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)

    long_id, short_id = video_id(args.long_url), video_id(args.short_url)
    print(f"롱폼 {long_id} / 숏폼 {short_id}")

    long_sub = download_subs(args.long_url, long_id)
    if not long_sub:
        sys.exit("롱폼 자막이 없음 → 이 페어는 오디오 매칭이나 STT가 필요")
    long_cues = parse_json3(long_sub)

    if args.whisper:
        short_cues = whisper_cues(args.short_url, short_id)
        method = "subtitle+whisper"
    else:
        short_sub = download_subs(args.short_url, short_id)
        if not short_sub:
            sys.exit("숏폼 자막이 없음 → --whisper 옵션으로 다시 실행")
        short_cues = parse_json3(short_sub)
        method = "subtitle"

    short_text = " ".join(c[2] for c in short_cues)
    short_dur = video_duration_ms(args.short_url)

    best = match(long_cues, short_text, short_dur)
    found_dur = best["end_ms"] - best["start_ms"]
    length_ratio = found_dur / short_dur

    def mmss(ms):
        return f"{ms // 60000:02d}:{ms // 1000 % 60:02d}"

    print(f"\n찾은 구간: {mmss(best['start_ms'])} ~ {mmss(best['end_ms'])}")
    print(f"텍스트 유사도: {best['score']:.1f}  (출발 기준 85 이상)")
    print(f"길이 정합: {length_ratio:.2f}배  (0.9~1.1이면 통과)")
    print(f"확인 링크: https://youtu.be/{long_id}?t={best['start_ms'] // 1000}")

    result = {
        "long_id": long_id,
        "short_id": short_id,
        "segments": [[best["start_ms"], best["end_ms"]]],
        "method": method,
        "text_score": round(best["score"], 1),
        "length_ratio": round(length_ratio, 3),
        "accepted": None,  # 검수 후 true/false로 채움
    }
    with open("data/ground_truth.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
    print("\ndata/ground_truth.jsonl 에 한 줄 추가 완료")


if __name__ == "__main__":
    main()
