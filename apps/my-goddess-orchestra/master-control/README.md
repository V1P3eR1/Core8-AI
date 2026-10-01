# My Goddess — voice + GUI commander for The Agency

A local web app: talk (Hebrew/English) to a Goddess AI (CEO) that commands the 269 agency agents
via the Claude API, watch delegations live on a mission-control dashboard, and launch
fully autonomous missions with a step budget and a kill switch.

## Folder layout expected

```
<your folder>\
├─ agency-agents-main\      <- the agent repo (the 269 .md personas)
└─ master-control\          <- this app
   ├─ server.py
   ├─ static\index.html
   ├─ requirements.txt
   ├─ PLAN.md
   └─ README.md
```

If the repo lives elsewhere, set `AGENCY_DIR` to its path before starting.

## Setup (Windows, one time)

```powershell
cd master-control
pip install -r requirements.txt
```

Get an API key at https://console.anthropic.com → API Keys, then:

```powershell
setx ANTHROPIC_API_KEY "sk-ant-your-key-here"   # then open a NEW terminal
```

## Run

```powershell
python server.py
```

Open **http://localhost:8420** in Chrome or Edge (voice needs Chrome/Edge).

## Using it

- **Chat**: type or hit 🎤 and speak — Hebrew or English; it answers and speaks back in your language.
- **Roster** (left): all divisions and agents; agents light up while working.
- **Live Activity** (right): every delegation and result as it happens.
- **Autonomy Mode** (bottom right): write a goal, set a step budget, ▶ Launch.
  She works alone until `MISSION COMPLETE`, the step cap, or your ■ Stop.

## Notes

- Model defaults to `claude-sonnet-4-5`; override with the `MASTER_MODEL` env var.
- Each chat costs a few cents of API usage; autonomy missions cost roughly (steps × 1–3 calls).
- v0.1 agents can only think and write (no file/shell/internet access) — see PLAN.md for the roadmap.
