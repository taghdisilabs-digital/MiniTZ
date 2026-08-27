# Biella Engine — UI Asset List

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Scope: project-level Biella Engine visual/UI assets; not universal Engine-kernel mechanisms

## 1. Purpose

Define the visual asset families required for Biella Engine software/product surfaces.

These are brand/project UI resources. They do not define a scheduler, memory system, routing system, runtime state model or other universal Engine mechanism.

## 2. Visual direction

UI assets must preserve:

- deep graphite/navy surfaces;
- dominant Biella violet;
- thin precision borders;
- restrained emissive edges;
- compact professional density;
- machined/engineered visual character;
- high contrast;
- clear state semantics;
- restrained futuristic presentation.

Avoid:

- arcade HUD styling;
- giant mechanical frames;
- generic AI/neural motifs;
- orange/blue game-UI branding;
- excessive glass blur;
- decorative complexity that harms dense professional use.

## 3. Required asset families

The final UI production inventory must cover:

```text
panels
frames
buttons
dividers
status indicators
loaders
icons
HUD / technical elements
cards
patterns / backgrounds
badges / chips
tabs
inputs
progress elements
tooltips / popovers
app icons
splash assets
empty-state / placeholder-safe decorative assets
```

## 4. Panels

Required panel types:

```text
PANEL_BASE
PANEL_ELEVATED
PANEL_INSET
PANEL_MODAL
PANEL_SIDEBAR
PANEL_TOOL
PANEL_STATUS
```

Requirements:

- scalable;
- corners/borders remain clean at target DPI;
- support dark backgrounds;
- do not bake text into generic panel assets;
- support variable content height/width.

Prefer CSS/vector/procedural construction over raster panels where practical.

## 5. Frames

Required:

```text
FRAME_FOCUS
FRAME_SELECTED
FRAME_ACTIVE
FRAME_WARNING
FRAME_ERROR
FRAME_SUCCESS
FRAME_PREVIEW
```

Rules:

- violet for brand/active emphasis;
- semantic warning/error/success colors only when required by product meaning;
- orange is not the general active/focus color;
- border treatment must remain thin and precise.

## 6. Buttons

Required visual states:

```text
PRIMARY
SECONDARY
TERTIARY
GHOST
DESTRUCTIVE
DISABLED
HOVER
PRESSED
FOCUS
LOADING
```

Primary button:
- brand violet emphasis;
- legible text;
- no glow dependency.

Button artwork must not embed button labels in raster assets.

## 7. Dividers and separators

Required:

```text
DIVIDER_HORIZONTAL
DIVIDER_VERTICAL
DIVIDER_SECTION
DIVIDER_EMPHASIS
```

Use subtle neutral/graphite lines; violet only for active/emphasis contexts.

## 8. Status indicators

Required semantic states:

```text
UNKNOWN
IDLE
READY
RUNNING
PAUSED
COMPLETE
WARNING
FAILED
OFFLINE
```

These are visual vocabulary candidates for UI implementation. Actual software status mapping must use real product/runtime semantics and must not claim an Engine state that does not exist.

Visual forms may include:
- dot;
- ring;
- bar;
- badge;
- compact label.

## 9. Loaders

Required:

```text
LOADER_INDETERMINATE
LOADER_PROGRESS
LOADER_COMPACT
LOADER_FULLSCREEN
LOADER_INLINE
```

Rules:

- violet primary motion;
- restrained pulse/rotation;
- no generic spinning AI brain/network;
- loading animation remains readable at 1× and high-DPI.

Fullscreen loader consumes `LOADING_SCREEN_MATRIX.md`.

## 10. Icons

Required baseline categories:

### Navigation
```text
home
project
task
run
graph
artifact
resource
knowledge
settings
search
```

### Actions
```text
add
remove
edit
duplicate
download
upload
refresh
retry
play
pause
stop
open
close
expand
collapse
filter
sort
more
```

### Status
```text
info
success
warning
error
unknown
locked
unlocked
connected
disconnected
```

### Production
```text
code
browser
terminal
build
test
render
image
audio
video
3d
package
publish
```

Icons:
- use consistent stroke/fill system;
- remain clear at 16/20/24/32 px classes;
- use vector source;
- must not imitate proprietary third-party iconography without rights.

## 11. HUD / technical elements

Allowed supporting technical visuals:

```text
measurement ticks
coordinate markers
connection nodes
thin graph lines
resource bars
timeline markers
frame counters
crosshair / focus marker
grid fragments
technical labels
```

These are secondary.

Do not make the entire UI look like an arcade cockpit.

## 12. Card treatments

Required:

```text
CARD_DEFAULT
CARD_INTERACTIVE
CARD_SELECTED
CARD_PREVIEW
CARD_METRIC
CARD_ARTIFACT
CARD_RESOURCE
CARD_PROJECT
```

Cards must support:
- icon/thumbnail;
- title;
- metadata;
- status;
- primary action;
- compact dense layouts.

## 13. Patterns and backgrounds

Required/allowed:

```text
BG_DEEP_NAVY
BG_GRAPHITE
PATTERN_DOT_GRID
PATTERN_TECH_GRID
PATTERN_CONNECTOR_LINES
PATTERN_SUBTLE_NOISE
```

Rules:
- very low visual hierarchy;
- tileable when applicable;
- no embedded branding text;
- no generic code rain.

## 14. App / splash assets

Required future production:

```text
APP_ICON_MASTER
APP_ICON_1024
APP_ICON_512
APP_ICON_256
APP_ICON_128
APP_ICON_64
APP_ICON_32

SPLASH_16X9_4K
SPLASH_21X9
SPLASH_9X16
SPLASH_4X5
SPLASH_1X1
```

App icon must derive from approved symbol/master geometry.

Until `MASTER_LOGO_GEOMETRY.svg` exists, do not create an authoritative app icon geometry from an approximation.

## 15. UI color roles

Use `COLOR_TOKENS.json` as authority.

At minimum distinguish:

```text
brand accent
brand emission
background
surface
surface elevated
border
text primary
text secondary
text muted
success
warning
error
information
focus
disabled
```

Semantic colors must not overwrite brand identity roles.

## 16. Typography

Consume `TYPOGRAPHY_SPEC.md`.

Requirements:
- dense professional readability;
- clear hierarchy;
- no image-based UI text;
- fallbacks documented;
- licensed production typefaces only.

## 17. Vector/raster policy

Prefer:
- SVG/vector for icons, dividers, frames and scalable marks;
- CSS/procedural construction for panels/buttons where product implementation supports it;
- PNG only where raster content/effects genuinely require it.

Do not rasterize basic UI primitives solely for style.

## 18. State variants

For reusable UI assets, provide systematic state behavior rather than individual ad hoc images.

Examples:

```text
DEFAULT
HOVER
PRESSED
FOCUS
SELECTED
DISABLED
ACTIVE
```

## 19. Accessibility requirements

- focus state visible without relying only on glow;
- status not conveyed by color alone where product UI requires interpretation;
- icons have semantic labels in application implementation;
- contrast must be validated in final UI context;
- motion-reduced alternatives for repeating decorative animations.

## 20. Delivery structure

Recommended:

```text
08_UI/
|-- UI_ASSET_LIST.md
|-- SOURCE/
|   |-- ICONS/
|   |-- PATTERNS/
|   |-- APP_ICON/
|   `-- SPLASH/
`-- EXPORTS/
    |-- SVG/
    |-- PNG/
    `-- WEB/
```

## 21. QA

For each delivered UI asset verify:

- correct filename;
- vector validity where expected;
- dimensions where raster;
- true alpha where required;
- no embedded placeholder text;
- no duplicate authority;
- open/read validation;
- licensing/source status;
- manifest/export-matrix entry.

## 22. Completion rule

`UI_ASSET_LIST.md` defines the production inventory only.

The UI asset family is complete only when the actual required source/exports are created and validated under `ASSET_MANIFEST.json`, `EXPORT_MATRIX.csv` and `QA_CHECKLIST.md`.
