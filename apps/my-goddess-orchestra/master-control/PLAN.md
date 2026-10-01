# My Goddess — Plan for the Voice + Visual Orchestrator AI

**Project:** The Agency — My Goddess ("master boot" — the CEO AI)
**Owner:** Lev
**Date:** 2026-07-28
**Status:** v0.1 shipped (this folder) · phases 2+ are the roadmap

---

## 1. Vision

One AI — **My Goddess** — that you talk to with your voice (Hebrew or English), see on a live mission-control dashboard, and that commands the entire Agency of 269 specialist agents. You give it a goal; it decides which specialists to activate, delegates work to them, combines their results, and reports back — either interactively, or fully autonomously while you're away.

```
                          ┌────────────────────────────┐
     🎤 voice in  ───────▶│                            │
     🔊 voice out ◀───────│       MY GODDESS  👑        │
     🖥  GUI      ◀──────▶│  (Claude API, orchestrator │
                          │   brain + memory + rules)  │
                          └──────────┬─────────────────┘
                                     │ delegate_to_agent(slug, task)
              ┌──────────┬───────────┼───────────┬──────────┐
              ▼          ▼           ▼           ▼          ▼
         Frontend    Backend      Security    Marketing   ...265 more
         Developer   Architect    Architect   Strategist
        (each runs as a Claude sub-call loaded with its agency persona)
```

## 2. Architecture (what v0.1 already implements)

| Layer | Choice | Why |
|---|---|---|
| Brain | Claude API (Anthropic SDK), tool-use loop | The Goddess reasons + calls `delegate_to_agent` as a tool |
| Specialists | The 269 `.md` personas loaded as system prompts for sub-calls | Zero conversion — the repo IS the agent registry |
| Backend | Python + FastAPI, single `server.py` | Simple, hackable, runs on Windows with one command |
| GUI | Single-page dark "mission control" dashboard (`static/index.html`) | Roster by division, live delegation feed, chat, autonomy panel |
| Voice | Browser Web Speech API — SpeechRecognition (STT) + speechSynthesis (TTS) | Free, no keys; auto-detects Hebrew (א-ת) vs English per message |
| Autonomy | Background job loop with step cap + kill switch | "Fully independent work" with safety rails |

## 3. How orchestration works

1. Your message (typed or spoken) goes to `/api/chat`.
2. My Goddess gets a system prompt containing the full roster index (slug + name + description of all 269 agents) and rules of engagement.
3. It answers directly, or emits `delegate_to_agent(agent_slug, task)` tool calls. The server loads that agent's persona file and runs the task as a sub-conversation.
4. Results return to the Goddess, which synthesizes the final answer.
5. Every delegation appears live in the GUI's **Activity Feed**, and the roster panel highlights which agents are working.

## 4. Autonomy mode ("fully independent work")

- You give a **goal** and a **step budget** (default 10, max 40).
- She loops: think → delegate → evaluate → next step, until it declares `MISSION COMPLETE` or hits the cap.
- Safety rails built in: hard step cap, **Stop button** (kill switch), full audit log of every step, and v0.1 agents can only *think and write* — they have no file/shell/internet access yet, so autonomy is safe by construction.
- Later phases add real tool access (below) gated by a permissions panel: you choose per-mission what the agents may touch.

## 5. Roadmap

**Phase 0 — Copy & baseline (done):** project copied to a separate working folder; validation checks green.

**Phase 1 — v0.1 My Goddess (done, this folder):**
GUI dashboard · bilingual voice chat · orchestrator with live delegation · autonomy loop with kill switch.

**Phase 2 — Better visualization:**
Animated agency graph (force-directed map of divisions/agents, pulses on active delegations) · per-agent result cards with markdown rendering · mission timeline view · conversation history persistence (SQLite).

**Phase 3 — Voice upgrade:**
Wake word ("Hey Goddess") · continuous listening mode · streaming TTS so it starts speaking mid-answer · optional premium voices (ElevenLabs) behind a config flag.

**Phase 4 — Real hands for the agents:**
Give delegated agents actual tools: file read/write in a sandboxed workspace folder, web search, code execution. Permission toggles per mission in the GUI. This is when autonomy becomes truly productive (it can *build* things, not just plan/write).

**Phase 5 — Long-running independence:**
Mission queue + scheduler (run missions at night) · self-review step (a testing-division agent reviews every deliverable before the Goddess accepts it) · memory of past missions · optional Telegram/email report when a mission finishes.

## 6. Costs & keys

- Needs `ANTHROPIC_API_KEY` (console.anthropic.com). Each chat ≈ a few cents; autonomous missions cost more (each step = 1–3 API calls). The step cap is also your budget cap.
- Voice is free (browser). GUI is free (local).

## 7. Run it

See `README.md` in this folder — 3 commands and it's live at `http://localhost:8420`.
