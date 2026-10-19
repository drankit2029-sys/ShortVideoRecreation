# BRIEF — Indian Ocean Size Recreation (1:1)

workflow: general-video
flow: automation
storyboard: no
mode: autonomous

## Message
Recreate the reference YouTube Short "Indian Ocean is larger than you think" 1:1: a broadcast-grade 3D satellite-globe motion piece where the Indian Ocean's basin is revealed, measured, and compared (area, world share, USA, Asia, two moons), with matching camera choreography, timing, typography, grade and audio.

## Deliverable
- 1080x1920, 60fps, ~27.633s MP4 (reference is 720x1280 24fps — upscale only, no creative reinterpretation).
- Rendered on GitHub Actions runners (all heavy work: transcription, asset build, render, frame-compare).
- Final file lands in `Output/` at repo root.

## Assets
- `reference/target.mp4` — the reference video (authoritative timing/visual truth).
- Audio: original audio track extracted from `reference/target.mp4` on a runner; re-muxed into the render (music bed + SFX parity).
- Satellite imagery: NASA Blue Marble equirect texture, ocean color-graded to the reference palette (deep ocean `#18594B`, warm land `#B79984`).
- Overlay textures (built on runner): Indian Ocean basin mask + glowing coastline outline, Asia region outline glow, US flag-map cutout, Moon texture, dark grid background tile.
- Font: Inter ExtraBold (local `@font-face`, weights 800/900).

## Design truth (sampled from reference)
- Ocean: `#18594B`; land warm tan `#B79984`; grid-scene background `#001D16`.
- Accent yellow: gradient `#FFE84A → #FFC12D → #F5A81F`; coastline stroke `#FFC93C` with outer glow.
- Text: Inter ExtraBold, vertical yellow gradient, strong outer glow, no stroke.
- Grade: dark teal vignette, subtle film grain, motion-blur whips, slight chromatic aberration on fast moves.

## Customizations
None beyond 1:1 fidelity. No progress bars, no scene labels, no chrome (per AGENTS.md bans).

## Structure (scene timing from reference analysis)
1. `0.0–2.0s` Whip: fast east pan/zoom from Africa close-up to Indian Ocean settle (India top wall).
2. `2.0–6.2s` Slow drift zoom-out on the basin.
3. `6.2–8.4s` Coastline outline draws on; "3rd" (largest ocean) text.
4. `8.4–12.7s` Basin grid overlay + area counter "70.56 Million Sq. Kms" (counts up 0→70.56).
5. `12.7–16.2s` Whip to tilted flat world-map card on 3D grid background; percent counter 0→"14%".
6. `16.2–19.6s` Whip back to globe; US flag-map drops into the ocean (size comparison).
7. `19.6–23.0s` Flag fades; clean slow-drift ocean wide.
8. `23.0–25.4s` Whip to flat card; Asia region glows with outline; "1.5x" (vs Asia area).
9. `25.4–27.633s` Whip back to globe; two Moons drop into the ocean; hold to end.

## Verification
- `npx hyperframes check` clean (lint/runtime/layout/motion/contrast).
- Frame-extracted SSIM/visual compare against reference at scene midpoints; iterate until similar.
