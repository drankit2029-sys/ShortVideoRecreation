# BRIEF — The 14-Day Trial (vertical short)

Source: `Storyboard.txt` (transcript timestamps + cinematic storyboard).

## Spec
- 1080x1920, 24 fps, 46.5 s, no audio track (voiceover supplied by the user)
- One hero prop: a floating dark-glass app card in clean 2D vector space, one 2.5D tilt
- Canvas `#0D0E15`; Electric Cyan `#00F5D4`; Amber `#FFB703`; Coral `#FF4D6D`; purple `#9D4EDD`
- Burned-in stylized captions from the transcript timestamps (uppercase, karaoke cyan highlight)

## Beat map
1. 0.0–4.3 card flips in, `14` locks in cyan
2. 4.3–8.3 card compresses to a progress track, dot stops at day 3 / 7, amber 7–14
3. 8.3–14.3 card re-expands, neon border draws, shockwave latch
4. 14.3–23.3 cursor clicks an empty product (nothing sticks)
5. 23.3–27.3 trial ends, card slides off
6. 27.3–34.3 card returns, blocks snap in (data / flows / automations)
7. 34.3–38.7 the one 2.5D tilt + glow pool
8. 38.7–46.5 red threat, KEEP MY WORKSPACE click, cyan bloom, fade

## Pipeline
- Push to `main` triggers `.github/workflows/3-render.yml`: 40 shards rendered in
  parallel via `scripts/make_shard.py`, assembled with ffmpeg, QA snapshots uploaded.
- Deliverable: `Output/trial-explainer.mp4` (gitignored; downloaded from the run artifact).
