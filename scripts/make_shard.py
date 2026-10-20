#!/usr/bin/env python3
"""Generate a shard composition for parallel (segmented) rendering.

The hyperframes CLI counts capture frames from the STATIC data-duration of the
composition file, so each shard is its own entry HTML with:
  - root data-duration rewritten to (E - S)      [frame count becomes f1-f0]
  - every data-start window retime into shard-local time
  - the voiceover removed (muxed once in the assemble step)
  - window.__HF_SHARD baked so the seek handler maps u -> S + u

Usage: make_shard.py <src index.html> <out html> <start_frame> <end_frame>
       (frame indices at the composition fps; shard = [f0/fps, f1/fps))
"""
import re
import sys

FPS = 24.0


def fmt(v: float) -> str:
    return f"{v:.9f}".rstrip("0").rstrip(".") or "0"


def main() -> None:
    src, dst, f0s, f1s = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    html = open(src, encoding="utf-8").read()

    S = f0s / FPS
    E = f1s / FPS
    dur = (f1s - f0s) / FPS  # never exceeds the exact frame count

    # 1) root data-duration -> shard length (root data-start stays 0)
    m = re.search(r'(id="root"[\s\S]{0,500}?data-duration=")([^"]+)(")', html)
    assert m, "root data-duration not found"
    html = html[: m.start(2)] + fmt(dur) + html[m.end(2) :]

    # 2) drop the voiceover (muxed once over the assembled video)
    n = len(html)
    html = re.sub(r"\s*<audio[\s\S]*?id=\"vo\"[\s\S]*?</audio>", "", html, count=1)
    assert len(html) < n, "voiceover <audio> not removed"

    # 3) retime the card clip into shard-local time
    cm = re.search(
        r'(<section id="card-scene" class="clip" data-start=")([\d.]+)'
        r'(" data-duration=")([\d.]+)(")',
        html,
    )
    assert cm, "card-scene not found"
    ds, dd = float(cm.group(2)), float(cm.group(4))
    ns, ne = max(ds, S), min(ds + dd, E)
    if ne <= ns:
        end = html.index("</section>", cm.start()) + len("</section>")
        html = html[: cm.start()] + html[end:]
    else:
        html = html[: cm.start()] + (
            f'<section id="card-scene" class="clip" data-start="{fmt(ns - S)}"'
            f' data-duration="{fmt(ne - ns)}"'
            + html[cm.end() :]
        )

    # 4) bake shard state ahead of the setup script
    needle = "window.__hfShardSetup = function"
    assert needle in html, "shard setup script not found"
    html = html.replace(
        needle,
        f"window.__HF_SHARD_APPLIED=true;\n"
        f"      window.__HF_SHARD={{s:{fmt(S)},e:{fmt(E)}}};\n"
        f"      " + needle,
        1,
    )

    open(dst, "w", encoding="utf-8").write(html)
    print(f"shard frames [{f0s},{f1s}) dur={fmt(dur)} -> {dst}")


if __name__ == "__main__":
    main()
