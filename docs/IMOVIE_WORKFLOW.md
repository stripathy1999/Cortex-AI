# iMovie Workflow: New Project, First Video as Base, Claude Timeframe Suggestion, and Coordinates When Unsure

This workflow covers: **open iMovie → new project → use first new video as base → edit based on Claude timeframe suggestion → send/export → ask for coordinates when unsure** (e.g. about layout or “together” elements).

---

## 1. High-level flow

1. **Open iMovie, make a new project, use the first new video as the first base.**
2. **Edit the video based on Claude timeframe suggestion** (Claude sees the current state and suggests in/out points or edit steps).
3. **Send** (export or share the video).
4. **When unsure about “together things”** (how elements are laid out, where to click, alignment), **ask for coordinates** (vision + Claude returns click coordinates or element locations).

---

## 2. Step-by-step

### 2.1 Open iMovie, new project, first video as base

- **Who**: Agent-S (desktop automation) or a small script.
- **Actions**:
  - Open iMovie (e.g. `open -a "iMovie"` on Mac, or agent `open` action).
  - Create a new project (File → New Movie, or equivalent; use agent click/type if needed).
  - Add the **first new video** as the first clip (e.g. drag from Events/Media or Import → select first video → add to timeline as base).
- **If the UI is unclear**: capture screen → send to Claude with vision + thinking: “Describe how to create a new project and add the first video as the first clip in iMovie.” Use the answer to drive the next agent steps. **When unsure about where to click**, use the “ask for coordinates” step below.

### 2.2 Edit based on Claude timeframe suggestion

- **Input**: Current iMovie state (timeline, source media, or playback).
- **Process**:
  1. **Capture screen** (screenshot of iMovie window: timeline, inspector, or playback).
  2. **Send to Claude with vision + thinking** (e.g. `generate_with_thinking` with the screenshot as an image). Prompt example: “This is the current iMovie project. Suggest exact timeframe edits: which portions to keep, trim in/out points, or split points. Reply with a clear list of suggestions, e.g. ‘Use 0:00–0:30 from clip 1’, ‘Trim clip 2 from 1:00 to 2:15’.”
  3. **Parse** Claude’s reply into concrete edit steps (timecodes, trim in/out, etc.).
  4. **Agent (or automation)** performs those steps in iMovie (select clip, set in/out, trim, split, etc.).
- **If a step is ambiguous** (e.g. “click the trim handle” but multiple elements look similar): **ask for coordinates** (see 2.4) before clicking.

### 2.3 Send (export/share)

- **Who**: Agent-S or script.
- **Actions**: Use iMovie’s Share/Export (File → Share → File or equivalent). Follow the export dialog; if the dialog layout is unfamiliar, use **ask for coordinates** for each button or field you’re unsure about.

### 2.4 Ask for coordinates when unsure (e.g. “together things”)

When the agent is **unsure about layout** or **how things go together** (e.g. which control is which, where to click, alignment of elements):

1. **Capture screen** (full window or region of interest).
2. **Send to Claude with vision + thinking** (or a dedicated “coordinates” prompt), with a clear question, e.g.:
   - “In this screenshot, where should I click to [e.g. start the trim / open Share menu / confirm export]? Reply with approximate (x, y) in screen pixels and a short label.”
   - “Describe how these elements are laid out together and which one is the [e.g. primary timeline].”
3. **Parse** Claude’s reply for:
   - **Coordinates** `(x, y)` → agent uses them for the next click.
   - **Description** of “together” layout → use it to choose the right element or next action.
4. **Optional**: If you have a **vision service** that can return element positions (e.g. from accessibility or image analysis), you can combine it with Claude’s description to refine coordinates.

**Implementation hook**: a small backend endpoint or Agent-S helper, e.g. `ask_coordinates(screenshot_b64, question)` → calls Claude vision + thinking → returns `{ "x": int, "y": int, "label": str }` or a short layout description. The agent calls this whenever it’s unsure about where to click or how things are arranged.

---

## 3. Summary table

| Step | Do | When unsure |
|------|----|-------------|
| Open iMovie, new project, first video as base | Agent/script: open app, new project, add first video. | Use vision + Claude to describe steps; **ask for coordinates** for the next click. |
| Edit based on Claude suggestion | Capture screen → Claude vision + thinking → timeframe suggestions → agent applies edits. | **Ask for coordinates** before clicking (e.g. trim handle, playhead). |
| Send (export) | Agent: Share/Export flow in iMovie. | **Ask for coordinates** for each dialog button or field. |
| “Together things” / layout | Rely on Claude’s description of how elements are laid out together. | **Ask for coordinates** (and optionally a short layout description) from Claude with the current screenshot. |

---

## 4. Prompt ideas for Claude

- **Timeframe suggestion**: “Look at this iMovie screenshot. Suggest exact edit timeframes: which segments to keep, trim in/out points, or splits. Reply with a numbered list of concrete steps and timecodes.”
- **Coordinates when unsure**: “In this screenshot, I need to [action]. Where should I click? Reply with (x, y) in screen pixels and a one-word label. If the UI is complex, first describe how the main elements are arranged together.”

---

## 5. Integration with this repo

- **Vision + thinking**: Use the same pattern as in `docs/VISION_AND_CLAUDE_FOR_COMPLEX_TASKS.md` (screen capture → Claude with image + thinking).
- **Agent-S**: Handles open iMovie, new project, add video, and applying edit steps; when it doesn’t know where to click, it can call an “ask for coordinates” helper that uses a screenshot + Claude vision + thinking.
- **Backend**: Optional endpoint, e.g. `POST /api/vision/ask_coordinates` or `POST /api/claude/vision_thinking` with `{ "image_b64": "...", "prompt": "..." }` returning coordinates or layout description for the agent to use.

This gives you: **open iMovie → new project → first video as base → edit from Claude timeframe suggestion → send → and ask for coordinates whenever unsure about layout or “together” things.**
