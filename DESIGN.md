---
name: YTPI
description: A friendly, clear home-network library for managing downloads.
colors:
  primary: "#0b57d0"
  primary-dark: "#8ab4f8"
  primary-container: "#d3e3fd"
  on-primary-container: "#041e49"
  secondary: "#5f6368"
  secondary-container: "#dae2f9"
  tertiary: "#754b91"
  error: "#c5221f"
  error-container: "#f9dedc"
  success: "#188038"
  success-container: "#ceead6"
  warning: "#b06000"
  warning-container: "#feefc3"
  background: "#f8f9fa"
  surface: "#ffffff"
  surface-low: "#f4f7fb"
  surface-container: "#eef2f8"
  surface-high: "#e6ecf4"
  surface-highest: "#dfe6ef"
  on-surface: "#1f1f1f"
  on-surface-variant: "#5f6368"
  outline: "#b8bcc1"
  outline-variant: "#dadce0"
typography:
  display:
    fontFamily: "Roboto, Arial, sans-serif"
    fontSize: "clamp(28px, 3.2vw, 40px)"
    fontWeight: 600
    lineHeight: 1.17
    letterSpacing: "-0.045em"
  headline:
    fontFamily: "Roboto, Arial, sans-serif"
    fontSize: "25px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Roboto, Arial, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Roboto, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: "Roboto, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    height: "44px"
    padding: "0 20px"
    typography: "14px Roboto, Arial, sans-serif; weight 600"
  button-tonal:
    backgroundColor: "{colors.primary-container}"
    textColor: "{colors.on-primary-container}"
    rounded: "{rounded.pill}"
    height: "44px"
    padding: "0 20px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.xl}"
    padding: "26px 28px 23px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    height: "48px"
    padding: "12px 14px"
---

# Design System: YTPI

## Overview

**Creative North Star: "The Friendly Home Console"**

YTPI's interface makes a household download queue feel familiar and manageable rather than technical. It uses plain labels, a clear action-to-library workflow, visible progress, and compact status summaries. The mood is approachable, clear, and practical: information earns its place by helping someone queue media, understand current work, or manage their local library.

The responsive application shell gives desktop users a persistent navigation rail and gives mobile users a compact header and bottom navigation. Light and dark themes retain the same role-based color relationships. The interface's primary visual signal is its friendly, familiar blue, used for the main action, selection, and progress; success, warning, and error colors communicate download state.

**Key Characteristics:**
- Familiar Roboto typography and straightforward interface language.
- Blue-led, role-based palette with light and dark theme values.
- Rounded surfaces, pill-shaped actions, and subtle rather than dramatic elevation.
- Progress and status remain visible in the download workflow.
- Responsive navigation and layouts for desktop and touch-sized mobile screens.

## Colors

The palette is a cool, light neutral foundation with a familiar blue action color; semantic green, amber, red, and purple distinguish state and secondary content. Dark theme values are specified where the application defines them.

### Primary
- **Friendly Interface Blue** (`#0b57d0`): Light-theme primary action, links, active progress, focus indicators, and emphasized headings.
- **Soft Sky Blue** (`#8ab4f8`): Dark-theme primary accent, maintaining contrast against dark surfaces.
- **Pale Blue Selection** (`#d3e3fd`): Light-theme selected navigation and tonal actions.
- **Deep Blue Ink** (`#041e49`): Text on pale-blue containers.

### Secondary
- **Quiet Slate** (`#5f6368`): Secondary text and subdued interface symbols in the light theme.
- **Mist Blue** (`#dae2f9`): Secondary tonal backgrounds, including selected filters and contextual audio guidance.

### Tertiary
- **Playlist Violet** (`#754b91`): Playlist identity and related accents; dark theme uses `#d0a9ff`.

### Neutral
- **Cloud Background** (`#f8f9fa`): Light-theme page canvas.
- **White Surface** (`#ffffff`): Light-theme cards, fields, and dialogs.
- **Cool Low Surface** (`#f4f7fb`): Light-theme navigation rail and quiet containers.
- **Blue-Gray Container** (`#eef2f8`): Light-theme statistics, metadata, and tonal surface hierarchy.
- **Ink** (`#1f1f1f`): Light-theme main text.
- **Dark Canvas** (`#101214`): Dark-theme page canvas.
- **Dark Surface** (`#16191c`): Dark-theme cards and dialogs.
- **Light Ink** (`#e3e6e8`): Dark-theme primary text.
- **Outline** (`#b8bcc1`): Light-theme field outlines and subtle separators; low-emphasis outlines use `#dadce0`.

### Named Rules
**The Status-Has-a-Color Rule.** Keep semantic success, warning, error, and in-progress colors attached to the corresponding job state; do not use them as unrelated decoration.

## Typography

**Display Font:** Roboto (with Arial, sans-serif fallback)
**Body Font:** Roboto (with Arial, sans-serif fallback)
**Label/Mono Font:** Roboto for interface labels; ui-monospace, monospace for technical output.

**Character:** A single familiar sans-serif family keeps the interface consistent and legible. Weight, size, and color establish hierarchy; technical output is intentionally separated in a monospace face.

### Hierarchy
- **Display** (600, responsive 28–40px, line-height 1.17): Main page heading; tightened tracking creates a compact headline without changing the friendly tone.
- **Headline** (600, 25px desktop section heading; 23px mobile, line-height about 1.25): Major library sections.
- **Title** (600, 20px, line-height about 1.3): Card and form-section headings.
- **Body** (400, 15px, line-height 1.55): Default interface text; supporting text is commonly 12–16px and uses the secondary text role.
- **Label** (600, 13px, line-height about 1.4): Form labels; small uppercase eyebrow text uses 11px, weight 700, and expanded tracking.

### Named Rules
**The Plain-Language Rule.** Prefer short, task-oriented labels and explanatory copy; reserve technical monospace text for the detailed output view.

## Layout

Desktop uses a fixed 252px left navigation rail and a centered main column capped at 1060px. At 1100px and below, the rail narrows to 220px and the main column reflows within the remaining width. At 760px and below, the rail is replaced by a sticky 62px header and a fixed bottom navigation; the main content becomes full width with 16px side padding, reduced to 12px on very narrow screens (380px and below).

The download summary uses four equal columns on desktop and two on mobile. Form options flow horizontally where space permits, become a two-column grid on mobile, then stack on screens below 380px. Job rows place actions beside the content on desktop and below it on mobile. Maintain visible grouping between the submit form, download summary, filters, jobs, and saved playlists. The observed spacing is compact and consistent, commonly using 8–24px gaps and padding, with larger vertical breaks between primary sections.

## Elevation & Depth

Depth is hybrid but restrained: tonal surface shifts and thin outlines carry most grouping, while low-contrast shadows subtly lift primary cards and actions. A stronger shadow is reserved for overlays such as the details dialog and transient toast. Dark theme uses darker, slightly broader shadows so floating content remains distinct without introducing bright borders.

### Shadow Vocabulary
- **Resting surface** (`0 1px 2px rgba(60,64,67,.12), 0 1px 3px rgba(60,64,67,.08)`): Compose and playlist cards in light theme.
- **Floating overlay** (`0 4px 14px rgba(60,64,67,.12)`): Details dialog and toast in light theme use this stronger elevation role.
- **Dark resting / floating**: Dark theme uses `0 1px 4px rgba(0,0,0,.3)` and `0 6px 20px rgba(0,0,0,.32)` respectively.

## Shapes

The form language is generously rounded but not geometric or ornamental. Main compose cards use 24px corners; playlist and compose cards reduce to 20px on mobile. Inputs use 12px corners, statistics and job cards sit around 16–18px, and icons use compact 10–14px rounding. Primary and tonal buttons, chips, navigation selections, and progress tracks use pill or capsule silhouettes. Thin neutral outlines define fields and cards; focus is indicated by a blue outline and soft ring.

## Components

Components are friendly and direct: recognizable controls, clear states, and accessible interaction feedback take priority over visual novelty.

### Buttons
- **Shape:** Pill corners (`999px`); primary actions are at least 44px tall.
- **Primary:** Friendly Interface Blue background, white text, 14px semibold Roboto, and 20px horizontal padding.
- **Hover / Focus:** Hover slightly reduces brightness; keyboard focus uses a 2px primary outline offset by 3px. Active press scales subtly to 0.985.
- **Tonal / Outlined:** Tonal buttons use a pale-blue fill and deep-blue text. Outlined buttons are transparent with a 1px outline and primary text.
- **Text actions:** Compact primary-colored text buttons use a softly tinted hover surface.

### Chips
- **Style:** Status chips are compact pills with a neutral container by default.
- **State:** Downloading uses the primary container; finished uses semantic green; errors use semantic red; cancelled uses semantic amber. Keep status words visible, not color-only.

### Cards / Containers
- **Corner Style:** Compose cards use 24px; playlists and job cards use approximately 16–18px; mobile primary cards use 20px.
- **Background:** Main cards use the theme surface; statistics and detail cells use tonal surface containers; empty states use a low surface and dashed outline.
- **Shadow Strategy:** Subtle resting shadow for major cards; most inner containers rely on tonal contrast and outlines.
- **Border:** Cards use a 1px outline-variant border where present; job cards strengthen the outline on hover.
- **Internal Padding:** Compose card uses 26px 28px 23px desktop and 20px 17px mobile; job cards use 17–18px desktop and 12–14px mobile.

### Inputs / Fields
- **Style:** Surface-colored controls with a 1px outline, 12px corners, 48px minimum height, and 12px 14px padding. Compact selects and inputs use 44px height.
- **Focus:** Primary border plus a translucent 3px blue ring.
- **Error / Disabled:** Errors use semantic red; disabled submit actions lower opacity and indicate waiting.

### Navigation
- **Desktop:** Fixed left rail with a 48px minimum-height navigation item; selected destination uses a blue tonal capsule, while hover uses a neutral tonal surface.
- **Mobile:** Sticky compact header plus fixed three-destination bottom navigation. The selected destination uses a rounded tonal background; account for device safe-area inset at the bottom.

### Download Progress
- **Presentation:** Each job displays a labeled status, destination and quality/audio metadata, and a thin rounded progress bar with a numeric percentage.
- **Behavior:** Progress fill transitions as work updates. Pair color with the percentage and accessible progressbar name/value; do not communicate progress by color alone.

### Details Dialog
- **Presentation:** Full-height side panel on wider viewports, expanding to full width on mobile; separated from the page by an outline and scrim.
- **Content:** Use tonal detail cells and a distinct monospace block for technical output.

## Do's and Don'ts

### Do:
- **Do** preserve the light and dark theme role relationships when extending the UI.
- **Do** keep download status, progress, and percentage together in the job row.
- **Do** use the established blue for primary actions, selection, focus, and progress.
- **Do** keep touch controls at least 44px high where established and preserve visible keyboard focus.
- **Do** let desktop and mobile navigation follow their distinct existing patterns.

### Don't:
- **Don't** use status color as the only indication of a job's state.
- **Don't** make technical output the default content shown to a non-technical user; keep it in details.
- **Don't** remove the configured mobile bottom navigation or ignore its safe-area spacing.
- **Don't** add new palette roles or typefaces without a product or interface need.
