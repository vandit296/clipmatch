# ClipMatch — Session Recovery Prompt

If this session ever becomes inaccessible, paste everything below the line into a
fresh Claude session and it will rebuild the whole project.

---

I'm rebuilding a tool called **ClipMatch**. Please recreate the files described below.

**The problem (a $500 bounty tweeted by Harry Stebbings, host of the 20VC podcast):**
He records each episode as both an audio file and a separate video file, edited in
Descript. He listens to the audio and marks "compositions" — clips of the best
moments — but those selections only exist in the audio project. His team then has to
manually recreate the exact same clips in the video file, duplicating the work.
Descript's ChatGPT integration can't transfer the audio compositions to the video.

**The solution — ClipMatch:**
The audio and video come from the same recording session, so every clip is a span of
audio that also exists somewhere in the video's audio track. ClipMatch finds where
each exported audio clip occurs inside the video using *normalized* cross-correlation
of the waveforms (robust to volume / EQ / mp3-compression differences and to the two
files starting at different times), then cuts the video at those timestamps.

**Recreate two files:**

1. `clipmatch.py` — a Python CLI tool.
   - Usage: `python3 clipmatch.py episode_video.mp4 clips_folder/ -o video_clips`
   - Decode the video's audio to mono 8000 Hz via ffmpeg. For each audio clip in the
     folder, run FFT-based normalized cross-correlation (`scipy.signal.fftconvolve`
     with a reversed needle for the correlation, divided by the sliding-window L2 norm
     of the haystack times the needle norm) to find the best offset and a confidence
     score (~cosine similarity, 0–1). Cut the matching video segment with ffmpeg.
     Write the .mp4 clips plus a `timestamps.json` report. Flag any match below a
     `--min-confidence` threshold for manual review.
   - Requires ffmpeg + ffprobe on PATH, numpy, scipy. ~180 lines.

2. `clipmatch.html` / `index.html` — a single-file, in-browser version (nothing
   uploads anywhere).
   - Two drop zones: the episode video on the left, the exported audio clips (mp3s) on
     the right, and a "Find clips in video" button.
   - Decode media with the Web Audio API, run the same normalized waveform-matching
     math in JavaScript, and show a results table: start/end timestamp of each clip in
     the video plus a confidence score, flagging weak matches with a ⚠.
   - Let the user copy ready-made ffmpeg cut commands and download `timestamps.json`.
     (Browsers can't render video cuts, so the HTML version outputs timestamps +
     commands; the Python script does the actual cutting.)

**Deployment:** the HTML was deployed to Vercel as a static site (`index.html` at the
repo root). It was live at a Vercel URL.

**Verify before handing over:** smoke-test the matching engine on synthetic data —
embed a known clip at a known offset inside longer noise, add volume scaling + extra
noise + a DC offset to simulate a mismatched master, and confirm ClipMatch recovers
the exact offset with high confidence.

---
