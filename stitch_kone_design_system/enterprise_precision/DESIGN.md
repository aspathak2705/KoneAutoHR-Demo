---
name: Enterprise Precision
colors:
  surface: '#f8f9fb'
  surface-dim: '#d9dadc'
  surface-bright: '#f8f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f6'
  surface-container: '#edeef0'
  surface-container-high: '#e7e8ea'
  surface-container-highest: '#e1e2e4'
  on-surface: '#191c1e'
  on-surface-variant: '#404751'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f3'
  outline: '#707882'
  outline-variant: '#c0c7d2'
  surface-tint: '#00629f'
  primary: '#005991'
  on-primary: '#ffffff'
  primary-container: '#0072b8'
  on-primary-container: '#eaf2ff'
  inverse-primary: '#9bcbff'
  secondary: '#5e5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e1dfdf'
  on-secondary-container: '#626262'
  tertiary: '#854400'
  on-tertiary: '#ffffff'
  tertiary-container: '#a95802'
  on-tertiary-container: '#ffeee4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d0e4ff'
  primary-fixed-dim: '#9bcbff'
  on-primary-fixed: '#001d34'
  on-primary-fixed-variant: '#004a79'
  secondary-fixed: '#e4e2e2'
  secondary-fixed-dim: '#c7c6c6'
  on-secondary-fixed: '#1b1c1c'
  on-secondary-fixed-variant: '#464747'
  tertiary-fixed: '#ffdcc5'
  tertiary-fixed-dim: '#ffb781'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#703800'
  background: '#f8f9fb'
  on-background: '#191c1e'
  surface-variant: '#e1e2e4'
  status-success: '#107C10'
  status-warning: '#D83B01'
  status-error: '#A4262C'
  status-info: '#0078D4'
  status-ready: '#28A745'
  status-running: '#FD7E14'
  status-completed: '#6C757D'
  surface-border: '#E1E4E8'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  section-title:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  card-title:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  button:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  gutter: 24px
  margin-page: 32px
  container-max: 1440px
  sidebar-width: 260px
---

## Brand & Style

This design system is built for an internal enterprise environment where clarity, reliability, and speed of use are paramount. It adopts a **Corporate / Modern** aesthetic, heavily influenced by the structured efficiency of Microsoft 365 and the refined minimalism of Linear. 

The visual narrative is focused on "Institutional Trust"—using a restricted palette, high-quality typography, and a strict 8px grid to convey a sense of stability and professional excellence. By prioritizing functional whitespace over decorative elements, the design system ensures that HR professionals can manage complex induction workflows with minimal cognitive load.

## Colors

The palette is anchored by **KONE Blue**, used strategically for primary actions and brand identifiers. The system relies on a foundation of neutral grays to create a quiet background that allows status-critical information to stand out.

- **Primary:** Reserved for high-impact interactions like "Create Session" and active navigation states.
- **Surface & Background:** A tiered system of off-whites and very light grays distinguishes the sidebar from the main content area.
- **Semantic Palette:** Distinct, high-contrast colors are used for session statuses (Created, Ready, Running, Completed) to ensure immediate visual recognition in dense table views.

## Typography

This design system uses **Inter** for its exceptional legibility in data-heavy environments. The hierarchy is strictly enforced to guide the user's eye from the page title to specific session details without distraction.

Weights are used sparingly: **Semibold** (600) is reserved for titles, **Medium** (500) for interactive elements and card headers, and **Regular** (400) for all body copy and descriptions. This prevents the "bold everywhere" effect, maintaining a clean and professional appearance.

## Layout & Spacing

The system follows a **Fixed Grid** philosophy for the main content area, centered within a fluid container to maintain readability on ultra-wide displays.

- **The 8px Rhythm:** All spacing (padding, margins, gap) must be a multiple of 8px. 
- **Sidebar:** A fixed-width left navigation (260px) provides consistent access to Dashboard, Sessions, and Reports.
- **Main Stage:** Content is housed in a container with a max-width of 1440px, ensuring line lengths for tables and forms remain comfortable.
- **Responsive Behavior:** On tablet, the sidebar collapses into a hamburger menu or narrow rail. On mobile, the 4-column statistics grid reflows into a single vertical stack.

## Elevation & Depth

To maintain the "Enterprise First" feel, the system avoids dramatic shadows. Depth is communicated through **Tonal Layers** and **Low-Contrast Outlines**.

- **Level 0 (Background):** The base canvas uses a subtle neutral tint (#F4F5F7).
- **Level 1 (Cards/Sidebar):** White surfaces with a 1px border (#E1E4E8).
- **Level 2 (Interaction/Hover):** A very soft, diffused shadow (0px 4px 12px rgba(0, 0, 0, 0.05)) is applied only to indicate interactivity or to lift active modals.
- **Contrast:** High-contrast borders are avoided; instead, we rely on the subtle difference between the white cards and the light gray background to create structure.

## Shapes

The design system utilizes **Rounded** (8px) geometry. This corner radius provides a modern, approachable feel while remaining structured enough for a corporate environment.

- **Standard Elements:** Cards, input fields, and buttons all share the 8px (0.5rem) radius.
- **Status Badges:** Use a "Pill" shape (full rounding) to clearly distinguish them from interactive buttons.
- **Icons:** Use Lucide React with a 2px stroke weight and slightly rounded joins to match the UI's geometry.

## Components

### Buttons
- **Primary:** Solid KONE Blue. White text. Used for "Create Session."
- **Secondary:** Outlined with a 1px gray border. Used for "Edit" or "Cancel."
- **Danger:** Ghost or Outlined red, transitioning to solid red on hover. Used for "Delete."

### Cards
- Flat white backgrounds, 8px radius, 1px subtle border. 
- Padding should be generous (24px) to separate data points.

### Status Badges
- Small, uppercase text with a subtle background tint of the status color and a dark text version for accessibility.
- Example: `READY` (Green background 10% opacity, Solid green text).

### Tables
- No vertical borders. Light horizontal dividers only.
- Hover state: Change row background to a very light blue or gray.
- Icons (Lucide) used for "Upload Status" (e.g., CheckCircle for uploaded, Circle for pending).

### Input Fields
- 8px radius, 1px border. 
- Focus state: Border color changes to KONE Blue with a 2px soft outer glow (ring).
- Labels are always positioned above the field in `caption` style.