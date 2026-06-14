# ClipMatch

Automatically transfer podcast clip selections from an **audio** file onto the
**video** file. Built for the workflow Harry Stebbings (20VC) described: clips are
marked in Descript on the audio, and the team shouldn't have to recreate them by hand
on the video.

## How it works

The audio and video are the same recording, so each clip's waveform also exists in the
video's audio track. ClipMatch finds it with normalized cross-correlation — robust to
volume, EQ and mp3-compression differences, and to the two files starting at different
times — then cuts the video at those timestamps with ffmpeg.

## Two ways to use it

**Python (does the actual cutting):**

```bash
pip install numpy scipy        # plus ffmpeg on your PATH
python3 clipmatch.py episode_video.mp4 clips_folder/ -o video_clips
```

Outputs the cut `.mp4` clips and a `timestamps.json` report. Low-confidence matches
are flagged for a quick manual check.

**Browser (`index.html`):** open it, drop in the episode video and the exported mp3
clips, hit *Find clips in video*. Everything runs locally (nothing uploads). It
reports the timestamps + ready-to-paste ffmpeg commands and a downloadable
`timestamps.json`. Deployed as a static site on Vercel.

## Per-episode workflow

1. Mark clip compositions in Descript on the audio file (unchanged for the host).
2. Export each clip as an mp3 into one folder.
3. Drop the raw video + the mp3s into the tool, hit run.
4. Get the matched video clips (Python) or the timestamps + commands (browser).

See `RECOVERY_PROMPT.md` to rebuild the whole project in a fresh session.
