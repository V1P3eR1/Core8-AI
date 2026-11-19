# Capability catalog

The numbers match the supplied cards. Each department can handle the selected capability by number or name.

## Build & Test · `core8-build`

| # | Tool | Type | Prerequisites | Deliverable | Fallback | Upstream |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | Superpowers | Skill pack | Compatible Superpowers skill installed in the active client | Acceptance criteria, staged implementation plan, and verification evidence | Write and verify a scoped plan from the existing project conventions | [Source](https://github.com/obra/superpowers) |
| 02 | gstack | Skill pack and CLI | Compatible gstack installation and a supported local workflow | Engineering plan, implementation review, and functional QA notes | Use the repository's actual build and review workflow | [Source](https://github.com/garrytan/gstack) |
| 03 | graphify | Skill and CLI | Graphify installed and an authorized project folder to index | Codebase graph or an evidence-backed map of modules and links | Trace entry points and dependencies with local file search | [Source](https://github.com/Graphify-Labs/graphify) |
| 04 | GitHub CLI | CLI | Git repository, gh on PATH, and repository authorization for remote actions | Branch and check status, draft PR body, and post-action PR link if created | Use Git and prepare the PR body locally | [Source](https://cli.github.com/manual/gh_pr) |
| 05 | Vercel | Deployment CLI and API | Vercel project, Vercel CLI or connector, and scoped project access | Preview deployment and verified URL for a Vercel project | Use the project's configured host or verify a local preview | [Source](https://vercel.com/docs/cli) |
| 06 | Playwright | Browser test framework | Playwright and a browser installed, with a reachable test app | Results for a normal user flow with traces or screenshots when helpful | Use the project's test runner and record any browser checks still pending | [Source](https://playwright.dev/docs/intro) |
| 07 | Codex | Independent review agent | Independent Codex session with the exact diff or base and head | Read-only findings tied to the exact reviewed code and available test evidence | Use a separate read-only reviewer and label its runtime explicitly | [Source](https://developers.openai.com/codex/subagents) |
| 08 | Claude HUD | Claude Code status-line plugin | Claude Code with Claude HUD and its status line configured | Visible session status and progress | Report milestones and completed checks in the active session | [Source](https://github.com/jarrodwatts/claude-hud) |

## Design & Animate · `core8-design`

| # | Tool | Type | Prerequisites | Deliverable | Fallback | Upstream |
| --- | --- | --- | --- | --- | --- | --- |
| 09 | Figma | MCP and design service | Figma file access and a connected MCP. Canvas edits require a supported write tool | Design context or an authorized edit tied to a named file and node | Work from the supplied frame, export, or coded reference | [Source](https://developers.figma.com/docs/figma-mcp-server/) |
| 10 | ui-ux-pro-max | Skill pack | Compatible ui-ux-pro-max skill and the project brief or components | Responsive layout decisions, UI states, and accessibility checks | Use the existing design system and document its decisions | [Source](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) |
| 11 | impeccable | Design skill pack | Compatible impeccable skill and accessible project design references | Design consistency and a targeted visual critique | Compare screens against established Core8-AI tokens and reusable components | [Source](https://github.com/pbakaus/impeccable) |
| 12 | taste-skill | Design skill pack | Compatible taste-skill setup and relevant source assets | Art direction, reference choice, and visual finish review | Produce one art direction informed by the brief and actual assets | [Source](https://github.com/Leonxlnx/taste-skill) |
| 13 | emil-design-eng | Design skill | Compatible emil-design-eng skill and editable components or design source | Interaction and motion pass with focus and reduced-motion behavior | Use native component states and verify keyboard and reduced-motion behavior | [Source](https://github.com/emilkowalski/skills/blob/main/skills/emil-design-eng/SKILL.md) |
| 14 | HyperFrames | HTML video framework and skills | HyperFrames prerequisites, a supported renderer, and the project assets | Editable HTML composition and a rendered clip where supported | Deliver storyboard and timed HTML source | [Source](https://github.com/heygen-com/hyperframes) |
| 15 | Remotion | React video framework and skills | Remotion project, Node dependencies, and a working render command | Editable React composition and rendered video where supported | Supply a shot list and timing for the existing renderer | [Source](https://www.remotion.dev/docs/ai/skills) |
| 16 | FFmpeg | Media CLI | FFmpeg and ffprobe on PATH and eligible input media | Trimmed, captioned, or transcoded media with output metadata | Give reproducible edit timings and note the unrendered output | [Source](https://ffmpeg.org/documentation.html) |
| 17 | Higgsfield | Video service and API | Scoped provider access, accepted asset rights, and a generation budget when needed | Generated B-roll clip with asset and provider reference | Deliver shot prompts or use authorized stock footage | [Source](https://higgsfield.ai/creator-hub/help-center/integrations/what-is-the-higgsfield-api) |

## Research & Sell · `core8-grow`

| # | Tool | Type | Prerequisites | Deliverable | Fallback | Upstream |
| --- | --- | --- | --- | --- | --- | --- |
| 18 | Perplexity | Research service and API | Perplexity access and search or research scope for the task | Sourced answer with claim-level evidence and dates | Use available web research and verify original sources | [Source](https://docs.perplexity.ai/docs/getting-started/overview) |
| 19 | Claude in Chrome | Browser integration | A connected Claude in Chrome session with access to the intended site | Evidence from authorized browser navigation or interaction | Use the runtime's available browser capability or authorized page exports | [Source](https://code.claude.com/docs/en/chrome) |
| 20 | Firecrawl | Site extraction API and MCP | Firecrawl access and authorized URLs | Clean excerpts with source URLs and extraction dates | Read the authorized pages with browser or fetch tools | [Source](https://docs.firecrawl.dev/) |
| 21 | Apify | Data extraction platform and MCP | Apify access and an approved Actor, dataset, or collection scope | Bounded dataset from authorized sources with provenance | Use an official API, a supplied export, or a small manual sample | [Source](https://docs.apify.com/mcp) |
| 22 | last30days | Research skill | Compatible last30days setup and authorized access to the selected sources | 30-day signals with sample dates, links, and limitations | Apply the exact date filter in available search and collect corroboration | [Source](https://github.com/mvanhorn/last30days-skill) |
| 23 | Gemini | Video understanding API | Gemini access and an eligible media input for the selected model | Timestamped video observations and supported insights | Use supplied captions, stills, or a permitted transcript | [Source](https://ai.google.dev/gemini-api/docs/video-understanding) |
| 24 | humanizer | Editing skill | Supplied voice examples or brand guidance and the draft to edit | Natural Hebrew or English copy retaining the source facts and voice | Edit against the supplied voice examples, then check the factual claims | [Source](https://github.com/blader/humanizer) |
| 25 | Metricool | Social scheduling service and MCP | Connected Metricool brand, destination account, assets, and a time zone | Reviewable plan or verified scheduled item in the named brand and channel | Deliver a local schedule with assets, exact account, and time zone | [Source](https://help.metricool.com/schedule-and-edit-posts-through-an-llm-with-metricools-mcp-p8y4b) |

## Make the Posts · `core8-make`

| # | Tool | Type | Prerequisites | Deliverable | Fallback | Upstream |
| --- | --- | --- | --- | --- | --- | --- |
| 26 | GPT Image | Image generation API | Enabled image capability, approved input assets, and quota where applicable | Generated asset with editable text kept in layout source when needed | Deliver prompts and layout directions with a clearly labeled placeholder | [Source](https://developers.openai.com/api/docs/guides/image-generation) |
| 27 | Nano Banana | Image generation and editing API | Gemini image editing access and an approved reference asset | Edited supplied image with a list of changes and retained details | Write precise editing instructions for the approved reference | [Source](https://ai.google.dev/gemini-api/docs/image-generation) |
| 28 | ElevenLabs | Text-to-speech API | ElevenLabs access and an authorized voice | Voiceover using an authorized voice, with script and pronunciation notes | Deliver the production-ready script and timing | [Source](https://elevenlabs.io/docs/overview/capabilities/text-to-speech) |
| 29 | Puppeteer | Browser rendering library | Puppeteer and compatible browser installed with local HTML and fonts | Rendered HTML graphic with size and editable source | Use Playwright or provide the HTML for local preview | [Source](https://pptr.dev/) |
| 30 | Google Drive | Storage API and connector | Authorized Google Drive connection and exact folder | Organized files and verified link in the authorized folder | Write an asset manifest with local paths | [Source](https://developers.google.com/workspace/drive/api/guides/about-sdk) |
| 31 | Granola | Meeting-notes service and MCP | Authorized Granola connection and selected meeting notes | Meeting decisions, attributed action items, and the source note | Use the selected transcript or meeting notes supplied in the task | [Source](https://www.granola.ai/mcp) |
| 32 | Whisper | Transcription model and API | Eligible audio and an available local or hosted transcription model | Transcript with requested time markers and uncertain passages indicated | Use supplied captions or an available local transcription engine | [Source](https://developers.openai.com/api/docs/guides/speech-to-text) |
| 33 | Python | Runtime and libraries | Supported Python runtime, approved data, and the project's needed libraries | Reproducible analysis with validated inputs, CSV, chart, or PDF | Use the repository's installed runtime or return a checked data table | [Source](https://docs.python.org/3/) |

## Run the Office · `core8-run`

| # | Tool | Type | Prerequisites | Deliverable | Fallback | Upstream |
| --- | --- | --- | --- | --- | --- | --- |
| 34 | Notion | Workspace connector and MCP | Connected Notion workspace and the named page or database | Sourced brief or verified update in the chosen workspace | Prepare Markdown and the intended update target | [Source](https://developers.notion.com/guides/mcp/overview) |
| 35 | Gmail | Mail API and connector | Authorized Gmail thread and draft access for in-app drafts | Thread summary and reply draft for the named recipients | Return a local draft using the supplied thread text | [Source](https://developers.google.com/workspace/gmail/api/guides/drafts) |
| 36 | Google Calendar | Calendar API and connector | Authorized calendar identifiers and the requested date range and zone | Time-zone-aware availability and a proposed slot or verified event | Use supplied constraints and label any unverified availability | [Source](https://developers.google.com/workspace/calendar/api/guides/overview) |
| 37 | Slack | Messaging API and connector | Authorized Slack workspace and exact channel for posting | Team update draft or verified message reference when posting is authorized | Return the update with the intended channel | [Source](https://docs.slack.dev/messaging/sending-and-scheduling-messages/) |
| 38 | Zapier | Automation platform and MCP | Configured Zapier actions with scoped access to each participating app | Integration plan or verified workflow result for an authorized action | Return the exact trigger, mapped fields, and staged test inputs | [Source](https://help.zapier.com/hc/en-us/articles/48308034391821-What-is-Zapier-MCP) |
| 39 | caveman | Output compression skill | Compatible caveman skill or the requested concise response format | Concise operational status that retains decisions and evidence | Use a short status, blocker, and next step format | [Source](https://github.com/JuliusBrussee/caveman) |
| 40 | find-skills | Skill discovery | Skill discovery access to the upstream repo and license | Candidates with upstream repository, license, and compatibility notes | Search the official or maintainer-owned sources manually | [Source](https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md) |
| 41 | Node.js | Runtime | Node version and dependencies specified by the repository | Local script outputs from the project's documented commands | Use another available project-supported runtime or document the missing runtime | [Source](https://nodejs.org/en/learn/getting-started/introduction-to-nodejs) |
| 42 | Ollama | Local model host | Reachable local Ollama server and a model already installed | Local inference output and selected local model name | Use an approved configured model or provide a repeatable local test plan | [Source](https://docs.ollama.com/) |
