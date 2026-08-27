# Biella Engine — Typography Specification

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Scope: wordmark handling, brand typography direction, presentation hierarchy, UI/documentation hierarchy and fallback behavior

## 1. Principle

Biella Engine typography must feel **engineered, premium, international and production-grade**.

The type system must support two very different contexts without becoming two brands:

1. **AAA / cinematic identity** — wide, deliberate, high-impact, mechanically precise.
2. **Software / technical communication** — compact, neutral, highly legible and efficient.

The logo symbol is not a font glyph. The final wordmark must become approved vector artwork.

## 2. Wordmark Direction

Primary wordmark content:

**BIELLA**  
**ENGINE**

Locked behavior:
- uppercase;
- generous tracking;
- horizontal, engineered stance;
- no italics;
- no script;
- no rounded playful forms;
- no distressed military stencil treatment;
- no generic esports / sharp-claw typography;
- no cyberpunk glitch lettering;
- no condensed horror / sci-fi novelty face.

Recommended visual direction:
- extended or semi-extended grotesk;
- geometric terminals;
- clean counters;
- strong horizontal proportion;
- moderate stroke contrast at most;
- premium industrial / automotive / AAA studio feel.

### Wordmark construction target

`BIELLA`
- visual weight: SemiBold to Bold;
- tracking target after custom optical adjustment: approximately `+160` to `+240` Adobe tracking equivalent;
- default material: polished silver / warm white.

`ENGINE`
- visual weight: Medium to SemiBold;
- tracking target after custom optical adjustment: approximately `+220` to `+320`;
- smaller than `BIELLA`;
- default color: Biella Violet.

These are starting construction values. The final vector wordmark must be optically adjusted by eye and then locked as geometry.

## 3. Typeface Selection Policy

No commercial font family is considered permanently locked until:
1. licensing is verified for the intended business uses;
2. the wordmark has been tested at cinematic, presentation, web, UI, print and small-size applications;
3. the founder approves the final vector wordmark.

Until then, typeface names are **implementation candidates**, not brand authority.

## 4. Primary Brand / Display Typeface Direction

Preferred characteristics:
- geometric;
- extended / semi-extended;
- technical but not futuristic novelty;
- stable uppercase;
- strong numerals;
- useful Medium, SemiBold and Bold weights.

Open-source / readily replaceable candidates may be evaluated for mockups, but no candidate may redefine the final wordmark.

Candidate directions include families with the character of:
- Rajdhani;
- Oxanium;
- Space Grotesk;
- other extended industrial grotesks with suitable licensing.

Avoid using a display candidate for dense body copy when legibility suffers.

## 5. UI / Documentation Typeface Direction

Default production stack:

`Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`

Use:
- Regular 400;
- Medium 500;
- SemiBold 600;
- Bold 700 only when hierarchy requires it.

Body text should normally use Inter or an equivalent neutral UI sans.

## 6. Presentation Hierarchy

### Hero title
- weight: 600–700;
- size: 54–84 pt equivalent depending on canvas;
- tracking: `-1%` to `0%`;
- line height: 0.95–1.05;
- sentence case or short uppercase label + sentence-case main title.

### Section title
- weight: 600;
- size: 32–48 pt;
- line height: 1.05–1.15.

### Supporting statement
- weight: 400–500;
- size: 18–28 pt;
- line height: 1.25–1.4;
- color: muted neutral unless emphasis is required.

### Eyebrow / section number
- uppercase;
- weight: 600;
- tracking: `+8%` to `+16%`;
- small scale;
- Biella Violet allowed.

## 7. UI Hierarchy

### App / panel title
- 18–24 px;
- 600 weight.

### Section label
- 13–16 px;
- 600 weight;
- tracking up to `+4%` when uppercase.

### Body
- 14–16 px;
- 400–500 weight;
- 1.4–1.55 line height.

### Caption / metadata
- 11–13 px;
- 400–500 weight;
- never below accessibility-safe scale for production UI.

### Numbers / telemetry
- tabular numerals preferred when supported;
- weight 500–600;
- use color for semantic status only.

## 8. Tracking Rules

Do:
- use wide tracking in the wordmark and small uppercase labels;
- use neutral or slightly tight tracking in large headlines;
- use normal tracking in body text.

Do not:
- apply wordmark tracking values to paragraphs;
- stretch text horizontally;
- fake an extended typeface by scaling glyphs;
- kern by arbitrary spaces.

## 9. Case Rules

Brand:
- `Biella Engine` in normal prose;
- `BIELLA ENGINE` in the formal wordmark.

Tagline:
- preferred formal lockup: `CONNECTING INTELLIGENCE TO EXECUTION`.

Documentation headings:
- title case or sentence case based on document context;
- do not force every interface label into all caps.

## 10. Wordmark Color Rules

Preferred dark-background lockup:
- `BIELLA`: Polished Silver / Warm White;
- `ENGINE`: Biella Violet.

Monochrome:
- all white;
- all black;
- single manufacturing color.

The wordmark must not require a gradient.

## 11. Small-Size Handling

At small sizes:
- remove tagline first;
- use symbol + `BIELLA ENGINE` only if legible;
- for very small app icons use the symbol alone;
- do not reduce tracking until letters visually touch;
- do not add outline strokes merely to rescue legibility.

Minimum sizes will be finalized in `LOGO_CONSTRUCTION_SHEET.pdf`.

## 12. Motion Typography

Motion must be:
- precise;
- restrained;
- mechanically synchronized with logo activation.

Allowed:
- opacity;
- controlled position reveal;
- masked linear reveal;
- subtle light sweep.

Avoid:
- glitch text;
- scrambling characters;
- random code rain;
- elastic bounce;
- typewriter gimmicks for the main logo;
- excessive chromatic aberration.

## 13. Print / Corporate

Corporate material should prioritize clarity over gaming drama.

Use:
- neutral UI/documentation family for body;
- display family sparingly for covers and high-level headings;
- vector wordmark artwork rather than live-font reconstruction.

## 14. Fallback Rules

If the preferred UI family is unavailable:
1. use the next font in the approved fallback stack;
2. preserve weights and hierarchy;
3. do not substitute a novelty display face;
4. keep the logo wordmark as vector artwork.

If the display face is unavailable in a working file, use a neutral placeholder and label it as non-authoritative until the approved wordmark vector is placed.

## 15. Accessibility

- maintain sufficient contrast;
- avoid ultra-light weights on dark backgrounds;
- avoid purple body text when contrast is insufficient;
- never use color alone to communicate state;
- body copy must remain readable at normal viewing distance.

## 16. Locked vs Flexible

Locked:
- wordmark text;
- uppercase formal lockup;
- engineered extended direction;
- wide tracked identity;
- silver/white `BIELLA` + violet `ENGINE` default dark treatment;
- vector wordmark requirement.

Flexible until later founder approval:
- exact licensed display family;
- exact optical kerning values;
- secondary editorial family if ever needed;
- localized typographic adaptations.

## 17. Finalization Requirement

Once the final wordmark is approved, it must be converted into clean vector geometry and included in the future `MASTER_LOGO_GEOMETRY.svg` / construction package.

No downstream asset may recreate the authoritative wordmark from a live font after the vector lock is established.
