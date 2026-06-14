#!/usr/bin/env python3
"""
ClipMatch — find audio clips inside a video and cut the matching video segments.

The problem this solves (Harry Stebbings / 20VC $500 bounty):
  You mark clip "compositions" in Descript on the AUDIO file. Those selections only
  exist in the audio project, so your team has to manually recreate the same clips in
  the separate VIDEO file. ClipMatch automates that: it finds where each exported
  audio clip occurs inside the video and cuts the matching video segment for you.

Workflow:
  1. Make your clip compositions in Descript on the audio file (as you do today).
  2. Export each clip as an mp3/wav into one folder.
  3. Run:  python3 clipmatch.py episode_video.mp4 clips_folder/ -o video_clips
  4. Get back: matching video clips (.mp4) + a timestamps.json report.

How it works:
  The audio and video come from the same recording session, so every clip is a span
  of audio that also exists in the video's audio track. ClipMatch decodes the video's
  audio, then slides each clip's waveform across it using FFT-based *normalized*
  cross-correlation. The normalization makes the match robust to volume, EQ and
  mp3-compression differences, and the sliding search handles the two files starting
  at different times. The peak gives the exact offset; its score (~cosine similarity,
  0-1) is the confidence. ffmpeg then cuts the video at those timestamps.

Requires: ffmpeg + ffprobe on PATH, numpy, scipy.
  pip install numpy scipy
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

SR = 8000  # downsample rate for matching — plenty for alignment, and fast
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".mp4", ".mov"}


def check_ffmpeg():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        sys.exit("Error: ffmpeg/ffprobe not found on PATH. Install ffmpeg first "
                 "(macOS: `brew install ffmpeg`).")


def load_audio(path, sr=SR):
    """Decode any media file to a mono float32 numpy array at `sr` Hz via ffmpeg."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to decode {path}:\n"
                           f"{proc.stderr.decode()[:500]}")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def normalized_xcorr(haystack, needle):
    """
    Find `needle` inside `haystack`.
    Returns (best_offset_samples, confidence) where confidence is the normalized
    correlation coefficient at the best lag (~cosine similarity, in [-1, 1]).
    """
    n = len(needle)
    H = len(haystack)
    if n == 0 or H < n:
        return 0, 0.0
    needle = needle - needle.mean()          # zero-mean for DC robustness
    needle_norm = float(np.linalg.norm(needle))
    if needle_norm == 0:
        return 0, 0.0
    # cross-correlation via FFT (correlation = convolution with reversed kernel)
    corr = fftconvolve(haystack, needle[::-1], mode="valid")        # len H-n+1
    # sliding-window L2 norm of the haystack at every candidate lag
    cumsum = np.cumsum(np.concatenate(([0.0], haystack.astype(np.float64) ** 2)))
    win_energy = cumsum[n:] - cumsum[:-n]                            # len H-n+1
    win_norm = np.sqrt(np.maximum(win_energy, 1e-12))
    score = corr / (win_norm * needle_norm)
    best = int(np.argmax(score))
    return best, float(score[best])


def cut_video(video, start, dur, out_path, reencode=True):
    if reencode:
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(video),
               "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast",
               "-c:a", "aac", "-movflags", "+faststart", str(out_path)]
    else:
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(video),
               "-t", f"{dur:.3f}", "-c", "copy", str(out_path)]
    subprocess.run(cmd, check=True)


def fmt_ts(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(int(m), 60)
    return f"{h:02d}:{int(m):02d}:{s:06.3f}"


def main():
    ap = argparse.ArgumentParser(
        description="Find audio clips inside a video and cut the matching segments.")
    ap.add_argument("video", help="Full episode video file")
    ap.add_argument("clips", help="Folder of exported audio clips (mp3/wav/...)")
    ap.add_argument("-o", "--out", default="video_clips", help="Output folder")
    ap.add_argument("--min-confidence", type=float, default=0.5,
                    help="Flag matches below this confidence (0-1). Default 0.5")
    ap.add_argument("--no-reencode", action="store_true",
                    help="Stream-copy cuts (faster, less frame-accurate)")
    args = ap.parse_args()

    check_ffmpeg()
    video = Path(args.video)
    clips_dir = Path(args.clips)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not video.exists():
        sys.exit(f"Video not found: {video}")
    if not clips_dir.is_dir():
        sys.exit(f"Clips folder not found: {clips_dir}")

    clip_files = sorted(p for p in clips_dir.iterdir()
                        if p.suffix.lower() in AUDIO_EXTS and p.is_file())
    if not clip_files:
        sys.exit(f"No audio clips found in {clips_dir}")

    print(f"Decoding video audio: {video.name} ...")
    hay = load_audio(video)
    print(f"  {len(hay) / SR:.1f}s of audio at {SR} Hz")

    results = []
    for i, clip in enumerate(clip_files, 1):
        needle = load_audio(clip)
        dur = len(needle) / SR
        off, conf = normalized_xcorr(hay, needle)
        start = off / SR
        end = start + dur
        flag = conf < args.min_confidence
        tag = "  ⚠ LOW" if flag else ""
        print(f"[{i}/{len(clip_files)}] {clip.name}: "
              f"{fmt_ts(start)} → {fmt_ts(end)} (conf {conf:.3f}){tag}")

        out_name = f"{i:02d}_{clip.stem}.mp4"
        out_path = out_dir / out_name
        try:
            cut_video(video, start, dur, out_path, reencode=not args.no_reencode)
        except subprocess.CalledProcessError as e:
            print(f"    ffmpeg cut failed: {e}")
            out_name = None

        results.append({
            "clip": clip.name,
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "start_timecode": fmt_ts(start),
            "end_timecode": fmt_ts(end),
            "duration_seconds": round(dur, 3),
            "confidence": round(conf, 3),
            "low_confidence": flag,
            "output": out_name,
        })

    report = out_dir / "timestamps.json"
    report.write_text(json.dumps(results, indent=2))
    low = [r for r in results if r["low_confidence"]]
    print(f"\nDone. {len(results)} clip(s) → {out_dir}/")
    print(f"Report: {report}")
    if low:
        print(f"⚠ {len(low)} low-confidence match(es) to review: "
              + ", ".join(r["clip"] for r in low))


if __name__ == "__main__":
    main()
