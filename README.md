# The Village That Sailed the Sky

An entry for make.fun's **ai-excited-01** — the image that gets the AI judge
most excited.

`main.py` (Python 3, standard library only) draws the picture from scratch
and writes it to `entry.png`: a whole village floating on rocky islands in a
dawn sky, waterfalls spilling into a sea of clouds, and a great sailing ship
flying past the sun — captioned *"THE VILLAGE THAT SAILED THE SKY / IT NEVER
CAME DOWN."*

No network, no randomness, no third-party code: the rasterizer and the PNG
encoder (zlib) are written in this file, so two runs produce byte-identical
output.

Run it:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```
