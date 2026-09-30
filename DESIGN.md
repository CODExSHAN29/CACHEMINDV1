---
name: Precision Engineering Console
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#747686'
  outline-variant: '#c4c5d7'
  surface-tint: '#2151da'
  primary: '#0037b0'
  on-primary: '#ffffff'
  primary-container: '#1d4ed8'
  on-primary-container: '#cad3ff'
  inverse-primary: '#b7c4ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#003ca3'
  on-tertiary: '#ffffff'
  tertiary-container: '#0051d6'
  on-tertiary-container: '#c9d4ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dce1ff'
  primary-fixed-dim: '#b7c4ff'
  on-primary-fixed: '#001551'
  on-primary-fixed-variant: '#0039b5'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#dbe1ff'
  tertiary-fixed-dim: '#b4c5ff'
  on-tertiary-fixed: '#00174b'
  on-tertiary-fixed-variant: '#003ea8'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.03em
  display-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Space Grotesk
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Space Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Space Grotesk
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  code-lg:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.08em
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system delivers a high-density, mission-critical engineering console aesthetic. It is tailored for systems architects, distributed data engineers, and infrastructure operators who demand immediate telemetry clarity, exactness, and zero visual friction.

The style rejects atmospheric gradients, soft focus, and organic warmth in favor of structural clarity, high contrast, and mechanical discipline:
- **Style Archetype**: Technical Engineering Minimalism combined with architectural grid discipline.
- **Structural Integrity**: Hard outlines, flat solid fills, strict grid alignment, and monospaced telemetry readouts.
- **Emotional Stance**: Authoritative, predictable, deterministic, and razor-sharp. Visuals communicate speed, operational stability, and raw computational efficiency.

## Colors

All color deployments strictly mandate solid, flat pigment values. Gradients, diffuse chromatic glows, and multitone blending are expressly prohibited across all UI surfaces.

### Surface Palette
- Canvas Base: `#f8fafc` (slate-50)
- Structural Panel / Card Fill: `#ffffff` (white)
- Inset / Well / Metric Tray Fill: `#f1f5f9` (slate-100)
- Highlight / Sub-panel Active: `#e2e8f0` (slate-200)

### Border & Division Matrix
- Structural Grid & Outer Borders: `#cbd5e1` (slate-300)
- Subtle Internal Dividers & Column Rules: `#e2e8f0` (slate-200)
- Focused / Selected Structural Borders: `#1d4ed8` (blue-700)

### Primary Functional Blues
- Deep Precision Primary: `#1d4ed8` (interactive anchors, active tab state, primary commands)
- Bright Telemetry Blue: `#2563eb` (metric readouts, code highlights, positive operational state)
- Deep Anchor Navy: `#1e40af` (pressed states, secondary interactive focal points)

### Typography & Readout Contrast
- Core Dominant Text: `#0f172a` (slate-900)
- Secondary Body & Labels: `#1e293b` (slate-800)
- Metric Captions & Inactive Headers: `#64748b` (slate-500)
- Monospace Data / Key-Value Identifiers: `#0f172a` (slate-900)

### Telemetry Signals
- Status Active / Stable: `#15803d` (green-700) with `#f0fdf4` (green-50) container
- Status Warning / Invalidation: `#b45309` (amber-700) with `#fefce8` (amber-50) container
- Status Critical / Eviction Alert: `#b91c1c` (red-700) with `#fef2f2` (red-50) container

## Typography

The typographic hierarchy couples the geometric structure of Space Grotesk with the computational precision of JetBrains Mono.

- **Primary Proportional System (Space Grotesk)**: Controls structural layout headlines, major module titles, high-level labels, and informative body copy. Tight letter spacing (`-0.03em` to `-0.01em`) maintains dense headline weight.
- **Precision Data System (JetBrains Mono)**: Handles all latency figures, cache keys, hit/miss ratios, telemetry markers, timestamp logs, and table columnar indices.
- **Metric Micro-labels (`label-caps`)**: All section tags, architectural status tiers, and column grouping identifiers must use uppercase JetBrains Mono with expanded letter tracking (`0.08em`) for swift legibility at small scale.

## Layout & Spacing

The layout is grounded in a rigorous 12-column modular grid built for high information density and structural predictability.

### Grid & Breakpoints
- **Mobile (< 768px)**: 4-column layout, `1rem` margin, `1rem` gutter. Data tables switch to stacked key-value blocks.
- **Tablet (768px - 1199px)**: 8-column layout, `1.5rem` margin, `1rem` gutter. Left navigation docks to an icon rail.
- **Desktop (≥ 1200px)**: 12-column layout, `2rem` margin, `1.5rem` gutter. Fixed master control sidebar (260px) paired with fluid multi-pane telemetry workspaces. Max viewport canvas stretches up to 1600px before centering.

### Spacing Model
Vertical and horizontal rhythm adheres strictly to 4px/8px increments. Padding inside components prioritizes compactness:
- Data arrays, key-value tables, and inspector sheets use `space-xs` (4px) and `space-sm` (8px).
- Module container padding adheres to `space-md` (12px) or `space-lg` (16px).
- Inter-panel structural separation uses `space-xl` (24px).

## Elevation & Depth

This design system rejects drop shadows, ambient blur radiuses, floating elevated cards, and frosted translucent overlays. All depth, layering, and stacking logic are conveyed strictly via:

1. **Surface Tonality**:
   - Level 0 (App Shell/Backdrop): Solid `#f8fafc`.
   - Level 1 (Panels & Control Cards): Solid `#ffffff`.
   - Level 2 (Inspector Trays, Code Insets, Console Cells): Solid `#f1f5f9`.
   - Level 3 (Selected/Active Row): Solid `#e2e8f0`.

2. **Crisp Precision Outlines**:
   - Standard boundary lines use a solid 1px stroke of `#cbd5e1`.
   - Inset separators and table grid lines use a solid 1px stroke of `#e2e8f0`.
   - Hover and interactive focus states replace borders with a 1px or 2px solid stroke of `#1d4ed8`.

3. **Modals & Overlays**:
   - Dialog windows are rendered as crisp solid white (`#ffffff`) panels bounded by a 2px `#0f172a` perimeter line.
   - Backdrop mask uses an unblurred, solid `#0f172a` at 40% opacity.

## Shapes

The geometric framework is strictly sharp (0px border radius across all controls, containers, badges, and modals). 

- **Containers & Panels**: Hard 90-degree corners convey mechanical precision and match terminal-style data grids.
- **Interactive Controls**: Buttons, inputs, dropdown menus, and tabs feature right angles with flat solid fills and 1px outer bounds.
- **Badges & Tags**: Status telemetry pills are strictly rectangular micro-boxes (0px radius) to avoid consumer-app softness.

## Components

### Buttons
- **Primary**: Background `#1d4ed8`, text `#ffffff`, border 1px solid `#1e40af`, 0px border radius. Padding: 6px 14px. Font: Space Grotesk Medium 13px. Hover: Background `#2563eb`. Active: Background `#1e40af`.
- **Secondary / Technical Outlined**: Background `#ffffff`, text `#0f172a`, border 1px solid `#cbd5e1`. Hover: Background `#f1f5f9`, border 1px solid `#0f172a`.
- **Destructive**: Background `#ffffff`, text `#b91c1c`, border 1px solid `#b91c1c`. Hover: Background `#b91c1c`, text `#ffffff`.

### Telemetry Badges & Chips
- Structure: Rectangular, 0px border radius, padding 2px 6px. Font: JetBrains Mono 11px uppercase (`label-caps`).
- **Telemetry OK**: Solid `#f0fdf4` fill, `#15803d` text, 1px solid `#86efac` border.
- **Telemetry Active**: Solid `#eff6ff` fill, `#1d4ed8` text, 1px solid `#bfdbfe` border.
- **Telemetry Warning**: Solid `#fefce8` fill, `#b45309` text, 1px solid `#fde047` border.
- **Telemetry Error**: Solid `#fef2f2` fill, `#b91c1c` text, 1px solid `#fca5a5` border.

### Input Fields & Selectors
- Background: `#ffffff`, border: 1px solid `#cbd5e1`, 0px radius.
- Height: 32px for data density.
- Text: `#0f172a` in Space Grotesk 13px; Placeholder: `#64748b`.
- Focus State: 1px solid `#1d4ed8` with immediate 1px solid outer box ring of `#1d4ed8` (no fuzzy glow).
- Code/Key Inputs: Use JetBrains Mono 12px with a `#f1f5f9` inset background.

### Cards & Engineering Panels
- Shell: Solid `#ffffff` background with 1px solid `#cbd5e1` exterior frame. 0px corner radius.
- Panel Header: Flat `#f1f5f9` fill, height 36px, 1px solid `#cbd5e1` bottom border. Contains uppercase label in Space Grotesk Bold 12px and JetBrains Mono metric metadata.
- Body: 12px or 16px internal padding. Zero internal drop shadows.

### Telemetry Tables & Lists
- Table Header: Background `#f8fafc`, 1px solid `#cbd5e1` top and bottom lines. Typography: JetBrains Mono 11px bold, uppercase `#475569`.
- Row Elements: Height 36px, alternating row striping forbidden; visual separation achieved purely with 1px solid `#e2e8f0` bottom dividers.
- Hover Row: Solid `#f1f5f9` fill with a 2px left border accent in `#1d4ed8`.
- Metric Cells: Numeric columns right-aligned in JetBrains Mono 12px `#0f172a`.

### Checkboxes & Radios
- Box Dimensions: 14px x 14px, 0px border radius.
- Unchecked: Background `#ffffff`, border 1px solid `#94a3b8`.
- Checked: Background `#1d4ed8`, border 1px solid `#1d4ed8`, displaying a sharp white interior mark.
- Radio Variant: Square 14px box with an inner 6px solid square fill when selected.

### Engineering Metric Inset (Domain Specific)
- Purpose: High-density latency, cache hit ratios, and memory allocation counters.
- Visuals: Solid `#f1f5f9` surface with 1px solid `#cbd5e1` perimeter. Label displayed in JetBrains Mono 10px uppercase `#64748b`, metric value rendered in Space Grotesk 24px bold `#0f172a`, and delta tag displayed in JetBrains Mono 11px.