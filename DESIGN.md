---
name: Human Temporal Continuity
description: A quiet, user-controlled memory landscape that gives one life continuity across many conversations.
colors:
  memory-amber: "#f3cf8d"
  memory-amber-strong: "#d8a95f"
  path-black: "#090b0c"
  scene-charcoal: "#0d1011"
  panel-charcoal: "#141718"
  paper-white: "#edf0ed"
  fog-gray: "#b9c0bc"
  drawer-paper: "#e3e4df"
  drawer-ink: "#171a1a"
typography:
  display:
    fontFamily: '"Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "clamp(36px, 3.6vw, 54px)"
    fontWeight: 560
    lineHeight: 1.06
    letterSpacing: "-0.02em"
  headline:
    fontFamily: '"Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "clamp(30px, 4vw, 46px)"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  title:
    fontFamily: '"Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "clamp(24px, 2.5vw, 36px)"
    fontWeight: 560
    lineHeight: 1.16
    letterSpacing: "-0.02em"
  body:
    fontFamily: '"Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "14px"
    lineHeight: 1.65
  label:
    fontFamily: '"Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 700
rounded:
  compact: "5px"
  control: "6px"
  panel: "8px"
  pill: "999px"
spacing:
  xs: "5px"
  sm: "8px"
  md: "12px"
  lg: "24px"
  xl: "44px"
components:
  icon-button:
    backgroundColor: "rgba(13, 16, 17, 0.72)"
    textColor: "{colors.paper-white}"
    rounded: "{rounded.control}"
    size: "38px"
  icon-button-hover:
    backgroundColor: "#1b1f20"
    textColor: "{colors.memory-amber}"
    rounded: "{rounded.control}"
    size: "38px"
  search-panel:
    backgroundColor: "{colors.panel-charcoal}"
    textColor: "{colors.paper-white}"
    rounded: "{rounded.panel}"
    width: "min(460px, calc(100vw - 36px))"
  memory-tag:
    backgroundColor: "transparent"
    textColor: "#3b433f"
    rounded: "{rounded.pill}"
    padding: "6px 9px"
  quiet-action:
    backgroundColor: "transparent"
    textColor: "#252b28"
    rounded: "{rounded.control}"
    padding: "8px 12px"
---

# Design System: Human Temporal Continuity

## Overview

**Creative North Star: "时雾深径"**

HTC is a solitary walk through time: the retained past begins inside an original vertical path's distant fog, and one anonymous human silhouette walks chronologically toward the present in the foreground. The world borrows the emotional language of monochrome silhouette cinema and LIMBO-like atmosphere without copying characters, scenes, or assets. It should feel introspective and slightly lonely, never horrific or theatrical.

The interface stays quiet enough for memory to remain the subject. Near-black terrain, cold paper-white type, layered mist, and one scarce amber signal establish the scene; operational controls remain precise and restrained. When detail is required, a warm light drawer overlays the world rather than rearranging it, preserving the user's place on the path.

**Key Characteristics:**

- Vertical depth and a winding path express time as lived distance.
- Silhouette, fog, controlled light, and tonal layering create atmosphere without decorative imagery.
- Amber is scarce and semantic: it marks active time, state, and navigation.
- Memory chapters sit directly in the world, not inside floating cards.
- Controls remain compact, legible, and subordinate to the memory scene.

## Colors

The palette is a cold charcoal monochrome interrupted by a restrained, human amber and a warm paper drawer.

### Primary

- **Memory Amber:** the rare attention color for active dates, state labels, focus, and small brand details.
- **Memory Amber Strong:** the firmer line and rule color used to connect chapter text to the landscape.

### Neutral

- **Path Black:** the page ground and deepest foreground silhouette.
- **Scene Charcoal:** the atmospheric canvas behind terrain, road, and fog.
- **Panel Charcoal:** the compact search surface; it remains part of the dark world.
- **Paper White:** primary text and high-contrast controls in the landscape.
- **Fog Gray:** secondary copy, temporal labels, and receding information.
- **Drawer Paper:** the inspection surface that separates focused reading from the scene.
- **Drawer Ink:** primary text within the light detail surface.

**The Amber Scarcity Rule.** Amber identifies memory state or current position; it never becomes a broad fill or decorative wash.

**The Two Worlds Rule.** Exploration stays charcoal and fog-bound; close reading moves onto warm paper while the dimmed path remains visible behind it.

## Typography

**Display Font:** Microsoft YaHei UI with PingFang SC, Noto Sans CJK SC, and system sans-serif fallbacks
**Body Font:** Microsoft YaHei UI with the same native CJK fallbacks
**Label Font:** the same family, using weight and scale rather than a second typeface

**Character:** A single native CJK sans family keeps the product personal, direct, and highly legible. Large titles are dense and decisive; secondary text is compact, calm, and never styled as metadata theater.

### Hierarchy

- **Display:** the present-state statement; large, tightly led, and limited to the primary opening thought.
- **Headline:** the chapter drawer title on the light reading surface.
- **Title:** the active memory chapter within the landscape.
- **Body:** summaries and explanatory copy with generous line height for emotionally dense material.
- **Label:** dates, state, navigation, and compact actions; weight supplies hierarchy without uppercase styling.

**The One Voice Rule.** Use one CJK sans voice throughout; hierarchy comes from scale, weight, contrast, and placement, not novelty fonts.

## Layout

The primary spatial model is a full-viewport sticky scene inside a long vertical scroll. The road occupies the depth axis, the anonymous walker follows it, and chapters alternate across its two banks. A fixed toolbar sits above the scene while a narrow year rail provides direct temporal jumps at the right edge.

The present-day arrival summary is anchored in the upper-left with a maximum width of 400px and appears only near the journey's endpoint. Active chapters remain deliberately narrow (up to 370px or 31vw) so the path stays readable as the central structure. Spacing follows a compact 5/8/12 rhythm for controls and a 24/44 rhythm for reading surfaces.

At 900px and below, chapter text tightens and secondary summaries yield space. At 640px and below, the scene preserves the vertical path, hides neighboring chapter previews, compresses the year rail to dots, and turns the detail drawer into a bottom sheet. Typography changes at explicit breakpoints rather than continuously scaling with viewport width alone.

**The Preserved Path Rule.** Navigation, chapter text, and detail surfaces must never erase the visible route through time.

## Elevation & Depth

The landscape is flat in component terms but deep in spatial terms. Canvas terrain, overlapping forest silhouettes, fog blur, contrast falloff, text shadow, and road perspective create the world. Conventional box shadows are reserved for temporary overlays: the search panel, chapter drawer, and mobile bottom sheet.

### Shadow Vocabulary

- **Search Lift:** a diffuse downward shadow keeps search readable above the scene (`0 24px 70px rgba(0, 0, 0, 0.52)`).
- **Drawer Separation:** a broad lateral shadow separates focused reading from the dimmed path (`-30px 0 80px rgba(0, 0, 0, 0.52)`).
- **Mobile Sheet Separation:** a broad upward shadow supports the bottom-sheet transition (`0 -24px 70px rgba(0, 0, 0, 0.58)`).
- **World Legibility:** restrained text and walker shadows preserve silhouettes against changing fog without making them float.

**The Atmospheric Depth Rule.** Build depth with occlusion, fog, scale, and contrast first; use box shadow only when a temporary interface surface physically overlays the world.

## Shapes

Controls use compact, almost-square geometry with 5-8px corners. Pills are limited to small source and memory tags. The road, terrain, fog, and human figure use organic silhouettes; chapter content itself has no enclosing card shape. Circular dots are reserved for temporal position and the walker head.

**The No Memory Card Rule.** A memory chapter belongs on the landscape bank as typography and a fine rule, not inside a rounded rectangle.

## Components

### Icon Buttons

- **Shape:** fixed 38px square with a restrained 6px corner and a fine translucent border.
- **Default:** dark translucent charcoal with paper-white iconography.
- **Hover / Focus:** hover moves to solid charcoal and amber; keyboard focus uses a 2px amber outline with 3px offset.

### Search

- **Style:** a compact dark panel up to 460px wide, with a three-column search row and minimally rounded results.
- **State:** results use tonal background change on hover; input remains visually integrated rather than becoming a separate white field.
- **Motion:** the panel enters over 220ms with the same decelerating curve used by drawers.

### Memory Chapters

- **Style:** title, period, state, summary, and action are placed directly over the scene with a fine amber rule.
- **State:** the active chapter receives full contrast; neighboring chapters recede in opacity and scale of type.
- **Motion:** chapter transitions use opacity and small vertical movement; scrolling owns position, so motion must not compete with it.

### Year Rail

- **Style:** small dots and compact labels form a vertical temporal index at the right edge.
- **State:** the active point scales to 1.8 and turns amber. On mobile, inactive labels disappear while their dots remain.

### Tags

- **Style:** transparent warm-paper chips with a thin gray border, 999px radius, and compact 6px by 9px padding.

### Chapter Drawer

- **Style:** a warm paper reading surface overlays the right side at up to 540px; it uses ink text, horizontal rules, and generous 24-44px padding.
- **Responsive:** below 640px it becomes a bottom sheet with an 84vh maximum height.
- **Behavior:** the backdrop dims but does not replace the path, preserving spatial context and the user's timeline position.

## Do's and Don'ts

### Do:

- **Do** preserve a visible vertical route and a sense of near-to-far depth on every timeline surface.
- **Do** use amber only for active time, memory state, focus, and small moments of orientation.
- **Do** aggregate memories into readable life chapters and let recency determine detail.
- **Do** keep overlays operational, bounded, and visibly connected to the scene beneath them.
- **Do** provide keyboard focus, reduced-motion behavior, forced-color support, and text equivalents for animated state.

### Don't:

- **Don't** copy LIMBO characters, scenes, composition, or assets; use only the confirmed monochrome silhouette atmosphere.
- **Don't** turn the vertical journey into a horizontal platformer or game map with targets and level nodes.
- **Don't** use stock travel photography, glass panels, floating memory cards, gradients as decorative spectacle, or avatar customization.
- **Don't** let controls, marketing copy, or dashboard columns become more visually important than the memory path.
- **Don't** encode meaning only through motion, fog, light, or color.
