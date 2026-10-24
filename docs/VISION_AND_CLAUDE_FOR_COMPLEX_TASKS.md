# Use Apple Local Vision + Claude Vision & Thinking for Difficult Software

When managing **difficult software** or **complex tasks**, prefer **Apple local vision** and **Claude vision + thinking** instead of relying only on the step-by-step agent. This is faster and more reliable for hard cases.

---

## Why

- **Agent (Agent-S)** does screenshot → predict action → execute in a loop. For messy UIs, multi-step flows, or ambiguous screens, it can take many steps and sometimes fail.
- **Apple local vision** (Vision service, MediaPipe, or on-device Vision framework) gives fast, local understanding of the screen or camera feed.
- **Claude with vision + thinking** can reason over a screenshot (or vision output) in one shot with extended thinking, then output a clear plan or answer—often faster and more accurate than the agent loop for complex stuff.

---

## When to Use This

Use **local vision + Claude vision + thinking** when:

- The task involves **difficult or unfamiliar software** (complex UIs, enterprise apps, custom tools).
- The task is **multi-step or ambiguous** and would require many agent steps.
- You want a **single strong reasoning pass** (Claude thinking) over the current state instead of repeated agent cycles.
- You need **speed**: one vision capture + one Claude (vision + thinking) call can replace several agent steps.

Use the **agent** when:

- The task is straightforward (known apps, clear clicks/typing).
- You need actual **GUI execution** (clicks, typing) and the agent’s grounding is sufficient.

---

## How

### 1. Apple local vision

- **Vision service** (`backend/vision_service.py`, port 5003): sends a frame (e.g. webcam, FaceTime, or screen crop), get back hand/finger or structured output. Uses MediaPipe (and can be extended with Apple Vision if on Mac).
- **Screen capture**: use the same screenshot path the agent uses (e.g. `screencapture` on Mac, or pyautogui/mss elsewhere) and optionally crop to the region of interest.
- Use this to get a **current state** (image or features) to send to Claude.

### 2. Claude vision + thinking

- **Vision**: send the screenshot (or a representative frame) to Claude as an image in the message content.
- **Thinking**: use a model that supports extended thinking (e.g. Claude 3.5 Sonnet thinking, or Claude 3.7 Sonnet with `thinking={"type": "enabled", "budget_tokens": 4096}`).
- In this codebase, **Agent-S** already has `generate_with_thinking` in `Agent-S/src/s3/core/engine.py` (LMMEngineAnthropic). You can add a **separate path** that:
  1. Captures the screen (or uses vision service output).
  2. Calls Claude with that image + the user request, with thinking enabled.
  3. Parses the answer (plan, next action, or final response) and either returns it to the user or feeds one-shot instructions to the agent/browser.

### 3. Making it faster than the agent

- **Single call**: one screenshot + one Claude (vision + thinking) call instead of 5–15 agent steps.
- **Routing**: in the backend or task router, treat “complex” or “difficult” tasks (e.g. by keyword, or after one failed agent attempt) by switching to this vision + Claude path.
- **Caching**: if the same screen appears again (e.g. same dialog), reuse the last Claude answer when safe.

---

## Implementation Hooks

| Component | Purpose |
|-----------|--------|
| `backend/vision_service.py` | Local vision (frames → finger/landmarks or future Apple Vision). |
| `backend/main.py` | Route “complex” or “difficult” requests to a vision + Claude path instead of only Agent-S. |
| `Agent-S/src/s3/core/engine.py` | `generate_with_thinking` for Claude thinking; extend or call with image content for vision + thinking. |
| Screenshot capture | Same as Agent-S (e.g. `capture_screenshot()` in main.py, or vision service input). |

---

## Summary

- **Difficult software / complex tasks** → Prefer **Apple local vision** (vision service + screen capture) + **Claude vision and thinking**.
- Use this path to get **faster, more reliable** results than the agent loop when the situation is hard.
- Keep the **agent** for simple, well-defined GUI tasks and for actually executing clicks/typing when the plan is clear.
