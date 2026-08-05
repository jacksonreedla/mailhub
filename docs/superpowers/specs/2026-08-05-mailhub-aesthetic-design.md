# Part II — Design & Aesthetic Plan

*Separate design track (will become its own spec in the repo at
`docs/superpowers/specs/`). Direction chosen by the user: the dark
"signal desk" concept, pushed into a niche aesthetic — **black/white/gray/
beige, 1930s classical revival × Italian Futurism × esoteric retro-futurist
("vril") energy**. NOT the OmniChrome design system. The user will later
supply a folder of reference images (e.g. `~/mailhub-inspo/`); when that
lands, re-derive the exact token values from the images and update this
section — structure below stays, values are provisional.*

## Concept: the Telegraph Exchange

A 1930s machine-age signal hall: monumental stone-and-ivory classicism
housing humming futurist machinery. The mail list is the dark hall —
dense, engraved, mechanical. Opening a message presents it as an **ivory
paper sheet** against the dark stone (letter-on-paper reading mode). The
AI is the hall's **annunciator/oracle** — its summaries appear on telegram
strips, its priority judgments as radiant-energy glyphs.

## Tokens (provisional until reference images arrive)

**Palette — strictly achromatic + beige; no color accent anywhere.**
Hierarchy is carried by contrast, engraving-weight rules, and radiance:
- `--ink` `#161512` — warm near-black (hall surface; also text on paper)
- `--bone` `#EDE7D8` — ivory (primary text on dark; the message "paper")
- `--stone` `#C7BCA5` — beige kraft/stone (structure, active states)
- `--graphite` `#77715F` — warm mid-gray (secondary text, muted rows)
- `--silver` `#A39C8C` — warm light gray (rules, borders, engraving lines)
- `--radiance` `#F7F2E3` — near-white glow (energy/priority highlights;
  "glow" is rendered as radiant ivory light, never neon color)

**Type roles** (Google Fonts, self-hosted locally so the app works offline):
- *Inscription* — *Cinzel* (Trajan-like engraved caps), wide letterspacing:
  wordmark, lane headings ("PEOPLE", "BULLETINS"), section facades.
- *Machine UI* — *Jost* (a Futura revival — literally 1920s–30s geometric
  DNA): buttons, labels, body UI text.
- *Signal data* — *Space Mono*: sender/subject/time rows, counts, the
  telegram-strip AI summaries (rendered uppercase, letterspaced).
- One display risk reserved for the wordmark treatment (stacked/stepped
  futurist composition), to be tuned against the reference images.

**Structure & texture:** stepped Deco frames and hairline double-rules
instead of rounded cards (border-radius 0); columned "bays" for lanes;
subtle paper/stone grain on surfaces; letterpress-depth text shadows used
sparingly. Dark theme is the only theme (the ivory paper reading sheet is
the deliberate counterpoint, not a light mode).

## Signature element: the Vril Dial

One memorable device, everything else disciplined: an engraved **sunburst
energy dial** in the masthead whose radiance (ray count/length/brightness)
encodes current mail pressure — unread volume and AI-judged importance
across all accounts. Its ray-glyph language repeats at micro scale as each
row's priority indicator (`✦ rays, not colored dots or bars`). New
high-priority arrivals pulse the dial's radiance once, slowly.

## Layout concept

```
┌──────────────────────────────────────────────────────────────┐
│  M A I L H U B          ☀ vril dial          accounts ▾  ⌕  │  masthead (inscription + dial)
╞══════════════════════════════════════════════════════════════╡
│ ══ P E O P L E ═══════════════════════════════ 4 unread ═══  │  lane facade (engraved caps, double-rule)
│  ✦✦✦  SARAH K.     re: lease renewal              14:02      │  dense mono signal rows
│  ─ TELEGRAM: wants your answer by Friday ─────────────       │  AI strip (on-hover/expand)
│  ✦··   STRIPE      receipt #4821                  13:40      │
│ ══ B U L L E T I N S ═════════════════════════ 12 new ════  │
│  ···   THE BATCH   weekly digest                  09:12      │
└──────────────────────────────────────────────────────────────┘
   message open → ivory paper sheet slides over the right 2/3,
   ink-on-bone, serif-set correspondence; AI draft-reply appears
   as a second, clipped-on telegram sheet with a COPY stamp.
```

**Motion:** almost none — one orchestrated dial pulse on priority arrivals,
a quiet paper-sheet slide on open. `prefers-reduced-motion` respected.
**Copy voice:** period-instrument but functional — lanes and actions use
plain words set like signage ("FILE", "MUTE", "DRAFT REPLY"); errors read
as machine-status lines, never cute.
**Quality floor:** responsive to narrow windows, visible keyboard focus
(engraved outline, not blue ring), WCAG-checked contrast for every
text/background pair in the palette.

## Design-track phases

1. **Reference analysis** (when the inspo folder lands): extract palette
   hexes, line weights, and type character from the images; update tokens.
2. **Static style tile**: one HTML page with tokens, type specimens, the
   Vril dial, sample lane + rows + paper sheet — approve look before app UI.
3. **Apply to app UI** as Part I phases 3–5 build out screens.

---

