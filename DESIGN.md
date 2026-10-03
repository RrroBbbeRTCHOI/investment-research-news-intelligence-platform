---
name: Institutional Intelligence
colors:
  surface: '#10131a'
  surface-dim: '#10131a'
  surface-bright: '#363940'
  surface-container-lowest: '#0b0e14'
  surface-container-low: '#191c22'
  surface-container: '#1d2026'
  surface-container-high: '#272a31'
  surface-container-highest: '#32353c'
  on-surface: '#e1e2eb'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#e1e2eb'
  inverse-on-surface: '#2e3037'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#c3c6d1'
  on-secondary: '#2c3039'
  secondary-container: '#454952'
  on-secondary-container: '#b5b8c3'
  tertiary: '#c2c6d4'
  on-tertiary: '#2b303b'
  tertiary-container: '#8c909e'
  on-tertiary-container: '#252a35'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#dfe2ee'
  secondary-fixed-dim: '#c3c6d1'
  on-secondary-fixed: '#181c24'
  on-secondary-fixed-variant: '#434750'
  tertiary-fixed: '#dee2f1'
  tertiary-fixed-dim: '#c2c6d4'
  on-tertiary-fixed: '#171c26'
  on-tertiary-fixed-variant: '#424752'
  background: '#10131a'
  on-background: '#e1e2eb'
  surface-variant: '#32353c'
typography:
  h1:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  h2:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  container-padding: 12px
  gutter: 8px
  component-gap: 4px
  section-margin: 16px
---

## Brand & Style

The design system is engineered for high-performance financial analysis and professional decision-making. It prioritizes information density, data integrity, and visual endurance for analysts spending extended hours within the interface.

The aesthetic follows a **Modern Institutional** approach—a refined evolution of classic Bloomberg/FactSet utility. It rejects decorative trends like glassmorphism or neomorphism in favor of a rigid, grid-based structure that maximizes screen real estate. The visual language conveys authority and precision through mathematical spacing, sharp edges, and a restrained color palette that draws attention only where data requires action.

**Core Principles:**
- **Density over Whitespace:** Information is packed efficiently to reduce scrolling and provide a holistic view of market data.
- **Visual Hierarchy through Tones:** Depth is communicated via subtle shifts in surface luminosity rather than shadows.
- **Functional Semantics:** Color is reserved strictly for status, trends, and primary calls to action.

## Colors

The palette is anchored in a multi-layered dark mode designed to minimize eye strain and maximize the pop of semantic data points. 

- **Foundation:** The deepest layer (`#0B0E14`) acts as the canvas. 
- **Surfaces:** Tiers of blue-grey (`#151921`) and charcoal define functional regions and widgets.
- **Borders:** Low-contrast strokes (`#2A2F3A`) create boundaries without introducing visual noise.
- **Typography:** A three-tier grayscale ensures that headings, body text, and metadata have distinct visual weights.
- **Semantics:** High-clarity Green, Amber, and Red are used for directional data (Up/Down/Hold). These should never be used for non-data decorative elements.

## Typography

This design system utilizes **Inter** for its exceptional legibility at small sizes and **JetBrains Mono** for tabular data and financial metrics where character alignment is critical.

**Typographic Rules:**
- **Tight Leading:** Line heights are kept narrow to support high-density layouts.
- **Weighting:** Use Semibold (600) for headers to create contrast against the dark background.
- **Data Display:** All price tickers, percentages, and numerical values must use the `data-mono` style to ensure numbers align vertically in tables.
- **Labels:** Use `label-caps` for table headers and section titles to differentiate structural labels from interactive content.

## Layout & Spacing

The layout is based on a **strict 4px grid system**. Every margin, padding, and height value must be a multiple of 4.

- **Grid Model:** A 12-column fluid grid is used for the primary dashboard, but individual workstation panes (widgets) use a "Flex-Container" model where content determines height.
- **Density:** We utilize "Compact" spacing as the default. Standard padding within cards and table cells is 8px.
- **Breakpoints:** 
    - **Desktop (1440px+):** Full multi-pane dashboard layout.
    - **Tablet (1024px):** Sidebars collapse into icons; main content area retains density.
    - **Mobile:** Not supported for primary analysis; simplified "Watchlist" view only.

## Elevation & Depth

Elevation is achieved through **Tonal Layering** rather than shadows. In a professional dark UI, shadows often create "muddiness."

1. **Level 0 (Background):** `#0B0E14` - The main application shell.
2. **Level 1 (Card/Surface):** `#151921` - The base for all widgets, charts, and tables.
3. **Level 2 (Overlay/Popout):** `#1C212B` - Used for dropdown menus, tooltips, and modals.
4. **Interactive State:** Hovered items should use a subtle highlight of `#2A2F3A`.

**Outlines:** Use 1px solid borders (`#2A2F3A`) to define all container boundaries. For focus states, use a 1px solid Primary Blue (`#3B82F6`) stroke.

## Shapes

The design system uses a **Soft (0.25rem)** roundedness level to maintain a professional, architectural feel while slightly softening the edges for modern readability.

- **Small Elements:** Checkboxes, tags, and small buttons use a 2px radius.
- **Containers:** Cards and dashboard panes use a 4px (Soft) radius.
- **Inputs:** Text fields and segmented controls use a 4px radius.
- **Charts:** Bar charts and data visualizations should use square caps (0px) to ensure mathematical precision in visual representation.

## Components

### Buttons & Inputs
- **Primary Button:** Solid `#3B82F6` with white text. Height: 28px (Compact) or 32px (Standard).
- **Ghost Button:** No fill, 1px border of `#2A2F3A`. Used for secondary actions in toolbars.
- **Input Fields:** Background `#0B0E14`, border `#2A2F3A`. Placeholder text in `text_low`.

### Data Tables
- **Header:** Background `#1C212B`, text `label-caps` in `text_med`.
- **Row:** Height 32px. Border-bottom 1px `#2A2F3A`.
- **Cell Alignment:** Text is left-aligned; numerical data is right-aligned using `data-mono`.

### Specialized Components
- **Segmented Controls:** Used for time-range selectors (1D, 5D, 1M, 1Y, YTD). Background `#0B0E14`, active segment `#2A2F3A` with `text_high`.
- **Metric Cards:** Small, border-only containers showing a Label, a Large Value, and a Trend Indicator (Arrow + Semantic Color).
- **Status Pills:** Small, low-saturation backgrounds with high-saturation text (e.g., "BUY" tag: Dark green background at 15% opacity with `#22C55E` text).
- **Financial Charts:** Use a thin 1px crosshair on hover. Tooltips must be pinned to the cursor and use the `Level 2` elevation color.