# kIRH — Krita Inner Rim Highlight

A small FOSS Krita Python plugin that automatically creates a soft white **inner rim highlight** along the transparent edges of a painted shape. It is meant for the stylized edge-lighting effect where white fades inward from the silhouette.

The source layer is never modified. kIRH creates a separate paint layer above it, so you can erase, mask, recolor, or adjust the result afterward.

## Features

- Soft white highlight generated just inside transparent edges
- Adjustable highlight width, opacity, and softness
- Alpha threshold to ignore faint stray pixels
- Optional restriction to the current Krita selection
- Creates a normal editable paint layer
- No AI or cloud service; the effect is generated locally with a distance transform

## Install

### Recommended: import the packaged plugin

1. Download **`kIRH-krita-plugin.zip`** from this repository.
2. Open Krita.
3. Go to **Tools → Scripts → Import Python Plugin…**.
4. Select `kIRH-krita-plugin.zip`.
5. Restart Krita.
6. Open **Settings → Configure Krita → Python Plugin Manager**.
7. Enable **Inner Rim Highlight**.
8. Restart Krita again.

Krita is very committed to the restart ritual.

### Manual install

If the plugin importer is unavailable, copy both of these from the repository into Krita's `pykrita` resource directory:

- `edge_highlight.desktop`
- the entire `edge_highlight/` folder

Typical Linux path:

```text
~/.local/share/krita/pykrita/
```

You should end up with:

```text
~/.local/share/krita/pykrita/
├── edge_highlight.desktop
└── edge_highlight/
    ├── __init__.py
    ├── edge_highlight.py
    ├── rim.py
    └── Manual.html
```

Then restart Krita, enable **Inner Rim Highlight** in **Settings → Configure Krita → Python Plugin Manager**, and restart once more.

## Use

1. Select a filled **8-bit RGBA** paint layer.
2. Go to **Tools → Scripts → Inner Rim Highlight…**.
3. Adjust the settings.
4. Click **Generate**.

A new `Inner Rim Highlight` paint layer is inserted above the source layer.

Good starting values for a soft airbrushed look:

- **Width:** 34 px
- **Opacity:** 82%
- **Softness:** 72%
- **Alpha threshold:** 8

## Controls

- **Width** — how far the highlight extends inward from the silhouette.
- **Opacity** — maximum strength of the white highlight.
- **Softness** — how gradual the fade is.
- **Alpha threshold** — pixels below this alpha are treated as transparent; useful for ignoring nearly invisible stray pixels.
- **Limit to current selection** — only generates the highlight inside the current selection.

## How it works

kIRH reads the active layer's alpha channel and computes an approximate distance from each opaque pixel to the nearest transparent pixel using a two-pass 3–4 chamfer distance transform. Pixels near the boundary receive a stronger white alpha value, which fades with distance toward the interior.

## Current limitations

- Supports 8-bit RGBA source layers.
- Detects the silhouette from transparency. Internal black line art on an otherwise opaque area is not treated as a boundary.
- This initial version has been syntax-checked and its raster algorithm tested outside Krita, but has not yet been runtime-tested inside Krita itself.

## License

GPL-3.0-or-later.
