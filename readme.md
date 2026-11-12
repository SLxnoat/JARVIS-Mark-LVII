# ⚙️ J.A.R.V.I.S. (Mark LVII)
### The Ultimate Cross-Platform Personal AI Assistant & Autonomous Workstation
**Architected, Extended & Maintained by [SLxnoat (Xnoat)](https://github.com/SLxnoat)**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue?logo=python&logoColor=white)](https://python.org)
[![PyQt6 HUD](https://img.shields.io/badge/GUI-PyQt6%20HUD-success?logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Gemini Live API](https://img.shields.io/badge/AI-Google%20Gemini%20Live-orange?logo=google&logoColor=white)](https://ai.google.dev/)
[![ChromaDB Vector Store](https://img.shields.io/badge/Memory-ChromaDB%20Local-purple?logo=databricks&logoColor=white)](https://www.trychroma.com/)
[![Plugins](https://img.shields.io/badge/Autonomous%20Plugins-68%20Active-brightgreen)](https://github.com/SLxnoat/JARVIS-Mark-LVII)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

---

## ✨ Overview

**J.A.R.V.I.S. Mark LVII** is a production-grade, multimodal, native desktop AI assistant engineered for deep operating system orchestration, autonomous software development, cybersecurity monitoring, and real-time environmental awareness. 

Unlike traditional browser wrappers or conversational chatbots, JARVIS executes with **direct OS-level authority** across your local machine. It combines low-latency bidirectional voice streaming via **Gemini Live**, an **8,000-particle software-rendered cybernetic hologram face**, a **human-brain-inspired self-learning engine**, a **hybrid ChromaDB vector memory**, and a fleet of **68 auto-discovered autonomous plugins**.

JARVIS runs wherever you work: directly through the interactive Qt6 voice HUD, headlessly in the background via the **Autonomous Task Engine**, remotely through an authenticated **Telegram Command Center**, or via a secure local **Web Dashboard**.

---

## 🌟 What Sets Mark LVII Apart

| Capability | Engineering Architecture | Real-World Impact |
|---|---|---|
| 🧑‍💻 **8K Cybernetic Point-Cloud Hologram** | CPU-rendered `QPainter` + `NumPy` software projection (zero GPU dependency). Real-time viseme mouth synchronization and live HUD palette retinting. | Stunning sci-fi HUD aesthetic that runs smoothly on low-power laptops, Wayland, X11, macOS, and Windows alike. |
| 🧠 **Human-Brain Cognitive Self-Learning** | Dopaminergic error plasticity, hippocampal dialogue consolidation, basal ganglia habit mining, and associative concept meshes. | Automatically learns from operator corrections (*"Always use dry run first"*), mining procedural macros and injecting them into the prompt. |
| 🧵 **Autonomous Background Tasks** | Dedicated worker thread loop with agent personas (`coder.md`, `researcher.md`, `general.md`). Checkpoints progress, cites sources, and writes Markdown reports. | Say *"Research the latest eBPF security tools for 15 minutes"* — talk continues uninterrupted while the agent conducts deep inquiry. |
| 🧬 **Two-Tier Hybrid Memory** | In-memory rolling short-term turns (<0.01ms) coupled with a persistent local **ChromaDB vector embedding store**. | Remembers user identity, projects, preferences, and historical sessions forever without cloud tracking or token bloat. |
| 📱 **Telegram Remote Command Center** | End-to-end encrypted Telegram bot bridge with interactive button grids, photo analysis, and voice note transcribing. | Control your desktop workstation, run terminal commands, and receive security alerts from your phone anywhere in the world. |
| 🛡️ **Defensive Sandboxing & Undo** | Automatic multi-stage undo stack for file edits and settings; confirmation gates for destructive actions (`toggle_wifi`, `shutdown`). | Execute confidently knowing any accidental change or file modification can be reversed in a single turn. |
| 🌐 **Offline / Local Engine Freedom** | Full support for local models (Ollama, llama.cpp, vLLM), local transcription (**faster-whisper**), and local neural TTS (**piper-tts**). | Zero telemetry, zero external network dependency, and complete privacy whenever you choose to run offline. |

---

## 🧩 Complete 68-Plugin Catalog

All plugins reside in `plugins/` and are auto-discovered on startup without manual configuration or registry edits.

### 1. 🛡️ Cybersecurity, Forensics & System Defense (10 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`firewall_warden.py`** | Audits workstation packet filtering rules (UFW/iptables/nftables), default chain policies, and exposed listening ports. | *"Jarvis, audit my firewall rules and open ports"* |
| **`process_forensics.py`** | Scans process tree for in-memory anomalies, unlinked running binaries, and execution from temporary directories. | *"Run process forensics and check for hidden binaries"* |
| **`threat_intel_radar.py`** | Real-time threat intelligence radar checking IP addresses, domain names, and file hashes against malware feeds. | *"Check threat reputation for IP 185.220.101.5"* |
| **`audio_deepfake_detector.py`** | Neural vocoder spectral forensics inspecting audio clips for synthetic AI voice cloning artifacts. | *"Inspect this audio memo for AI voice deepfakes"* |
| **`digital_footprint_scanner.py`** | Zero-knowledge k-Anonymity dark web breach scanner auditing credential exposures and email leaks. | *"Check if my primary email has appeared in data breaches"* |
| **`file_xray_decompiler.py`** | Non-execution forensic inspection of ELF/PE binaries and documents, extracting strings, symbols, and headers. | *"Analyze this suspicious executable with file X-ray"* |
| **`usb_sentinel.py`** | Audits physical USB ports, classifies connected peripherals, and detects BadUSB / Rubber Ducky HID injection devices. | *"Jarvis, scan connected USB devices for rogue keystroke injectors"* |
| **`crypto_vault_sentinel.py`** | Audits `~/.ssh/` key hygiene and file permissions, computes SHA-256/BLAKE2b hashes, and calculates Shannon entropy. | *"Audit my SSH directory security and key entropy"* |
| **`dns_propagator.py`** | Global Anycast DNS cartographer verifying DNS record propagation (A, AAAA, MX, TXT) across worldwide resolvers. | *"Check DNS propagation for my new domain"* |
| **`docker_sentinel.py`** | Container fleet radar inspecting Docker & Podman container health, port mappings, resource consumption, and crash loops. | *"Show running Docker containers and crash loop alerts"* |

---

### 2. 💻 Autonomous Engineering, Code & Terminal (9 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`ai_terminal_copilot.py`** | Translates natural language goals into safe, production-grade Linux shell one-liners with syntax breakdown. | *"How do I find all files over 500MB modified in the last 7 days?"* |
| **`code_debugger_sandbox.py`** | Executes Python snippets in an in-memory isolated sandbox with an autonomous self-healing traceback fix loop. | *"Test this sorting algorithm in the sandbox and auto-fix errors"* |
| **`code_architecture_mapper.py`** | Parses Python repositories into AST trees to generate visual Mermaid architecture and class dependency flowcharts. | *"Map the architecture and dependencies of this project"* |
| **`git_time_machine.py`** | Visualizes Git repository evolution, analyzing author velocity, code churn, and refactoring hotspots. | *"Show the Git churn hotspots for the last month"* |
| **`git_workspace.py`** | Inspects branches, staged/unstaged changes, and diffs across multiple local Git workspaces. | *"Check my project folder for uncommitted changes"* |
| **`prompt_engineering_forge.py`** | Transforms rough prompt ideas into production-grade LLM prompts applying Chain-of-Thought (CoT) and XML guards. | *"Optimize this prompt for technical code generation"* |
| **`smart_clipboard_ai.py`** | Contextual clipboard transformer: auto-detects formats (curl, JWT, JSON, SQL) and decodes or converts them. | *"Transform clipboard curl command into Python requests"* |
| **`cognitive_neuro_cortex.py`** | Human-brain self-learning engine: learns behavioral rules from corrections, mines habits, and maps concept graphs. | *"Remember: always format shell scripts for Linux Bash"* |
| **`task_planner.py`** | Autonomous goal planner and dynamic multi-tool combiner executing complex multi-step objectives. | *"Plan and execute an audit of my network, disk, and Git repos"* |

---

### 3. ⚡ Hardware, Acoustic, RF & Network Telemetry (7 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`pci_hardware_radar.py`** | Deep inspection of PCIe bus link speeds (Gen3/Gen4/Gen5), NVMe SMART drive health, and CPU clock governors. | *"Check NVMe drive health and PCIe link bandwidth"* |
| **`audio_spectrum_analyzer.py`** | Real-time acoustic FFT spectrum sensor measuring room noise floor, dominant frequency peaks, and coil whine. | *"Analyze ambient room acoustics and noise floor"* |
| **`wifi_radar.py`** | Tactical Wi-Fi radar inspecting link health (dBm signal, bitrate), nearby AP spectrum, and channel congestion. | *"Survey ambient Wi-Fi channels and optimize my router channel"* |
| **`network_speed.py`** | Non-blocking bandwidth test, ICMP ping latency, and packet loss diagnostics via Cloudflare CDN edge nodes. | *"Test my network latency and download speed"* |
| **`network_topology.py`** | Local LAN radar performing ARP sweeps, mapping active host IPs/MACs, and verifying open ports. | *"Map all devices connected to my local Wi-Fi subnet"* |
| **`bluetooth_governor.py`** | Manages Bluetooth peripherals via `bluetoothctl`, querying battery levels and toggling connections. | *"What is my wireless headphone battery level?"* |
| **`systemd_sentinel.py`** | Inspects Linux systemd services, lists failed units, retrieves `journalctl` error logs, and restarts daemons. | *"Show any system services that failed to start"* |

---

### 4. 🛰️ Tactical Space, Environmental & Celestial Telemetry (4 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`orbital_tracker.py`** | Real-time satellite & ISS orbital telemetry: latitude/longitude coordinates, orbital velocity, and overhead passes. | *"Where is the International Space Station right now?"* |
| **`solar_space_weather.py`** | Real-time NOAA solar flare activity (X-ray flux A/B/C/M/X), planetary K-index (Kp 0-9), and geomagnetic storm alerts. | *"What is the current solar storm and geomagnetic activity?"* |
| **`celestial_ephemeris.py`** | Mathematical lunar phase calculator, visible planetary coordinates, and solar dawn/dusk twilight timings. | *"What phase is the moon in tonight and when is twilight?"* |
| **`air_quality_sentinel.py`** | Atmospheric air quality radar measuring PM2.5, PM10, ozone, and gas pollutants with European AQI ratings. | *"What is the current air quality and PM2.5 level in London?"* |

---

### 5. 👁️ Perception, Biometrics & Multimodal Intelligence (6 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`hologram_visualizer_3d.py`** | 3D wireframe models (Mark Helmet, Arc Reactor, Tesseract) projected with dynamic perspective rotation on the HUD. | *"Project 3D hologram of the Mark helmet on the HUD"* |
| **`voice_biometrics_sentinel.py`** | Acoustic voiceprint speaker verification analyzing pitch contour (F0) and vocal tract formant resonances. | *"Verify operator voiceprint telemetry"* |
| **`speech_emotion_tone_detector.py`** | Vocal affect analyzer measuring operator pitch variance, speech rate cadence, and acoustic stress levels. | *"Analyze vocal stress and emotional tone"* |
| **`webcam_posture_fatigue_sentinel.py`** | Workstation vision sentinel auditing operator head tilt angle, spinal alignment, and eye blink fatigue rates. | *"Audit my workstation posture and check for eye strain"* |
| **`multilingual_live_translator.py`** | Live multilingual interpreter with phonetic pronunciation guides and HUD subtitles across 50+ languages. | *"Translate 'Server deployment complete' into Japanese"* |
| **`stealth_browser_recon.py`** | Ad-free web article extractor stripping popups, paywalls, and cookie banners into clean readable Markdown. | *"Fetch and summarize this technical article without ads"* |

---

### 6. 💼 Daily Workstation Productivity & Automation (9 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`smart_desktop_cleaner.py`** | Categorizes and sorts `~/Downloads` and `~/Desktop` files into subfolders; identifies duplicate download versions. | *"Scan my Downloads folder and find duplicate files"* |
| **`workspace_health_summary.py`** | Unified morning executive workstation readiness briefing: CPU/RAM/disk vitals, uncommitted Git repos, and agenda. | *"Good morning Jarvis, give me the workstation briefing"* |
| **`smart_reminder_snoozer.py`** | In-session voice-activated countdown timers with HUD countdown board, completion audio alert, and voice snooze. | *"Set a timer for 15 minutes to check the server"* |
| **`weather_astronomy_briefing.py`** | Real-time weather, 12-hour hourly rain radar probability bar charts, and solar schedule via Open-Meteo (100% free). | *"What's the weather forecast and will it rain today?"* |
| **`smart_unit_converter.py`** | High-precision converter for data rates (Mbps to GB/h), compute storage (TiB to TB / GiB), and download durations. | *"How long will it take to download a 60GB game at 150 Mbps?"* |
| **`focus_flowstate_guardian.py`** | Engages distraction shields by tracking deep work duration and blocking non-essential application focus. | *"Engage deep work flow-state protocol for 45 minutes"* |
| **`smart_home_scene_automator.py`** | Executes multi-device Iron Man protocol scenes (*"Protocol Nightfall"*, *"Protocol Workstation"*, *"Protocol Security"*). | *"Initiate Protocol Workstation scene"* |
| **`home_assistant.py`** | Direct Home Assistant smart home integration to query entities, toggle lights, and adjust climate controls. | *"Turn off the office desk lamp"* |
| **`printer_control.py`** | Monitors and controls 3D printers running OctoPrint, Moonraker, or Klipper (temperatures, job progress, pause). | *"Check 3D printer nozzle temperature and job progress"* |

---

### 7. 📚 Knowledge, Documents & Personal Management (12 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`ai_meeting_summarizer.py`** | Processes raw meeting transcripts or audio memos, extracting key decisions, action items, owners, and deadlines. | *"Summarize this meeting audio and extract action items"* |
| **`obsidian_vault.py`** | Reads, searches, creates, and appends notes in a local Obsidian Markdown vault with tag indexing. | *"Create a daily note in Obsidian with today's tasks"* |
| **`open_rss_briefing.py`** | Privacy-respecting RSS/Atom aggregator fetching top tech, AI, Hacker News, and Linux developer headlines. | *"Read me the top tech headlines from Hacker News"* |
| **`document_review.py`** | Analyzes documents, PDF files, and text drafts, rendering structured reviews and critiques on the HUD. | *"Review this project proposal and highlight flaws"* |
| **`excel_writer.py`** | Creates, reads, queries, and appends rows to Excel (`.xlsx`) spreadsheets or CSV files. | *"Create an Excel sheet tracking monthly cloud expenses"* |
| **`gmail_control.py`** | Reads unread emails, searches messages, drafts contextual replies, and sends emails through Gmail. | *"Check my unread emails from the engineering team"* |
| **`calendar_control.py`** | Reads calendar schedules, displays appointments for today or tomorrow, and creates new meetings. | *"What is on my calendar schedule for this afternoon?"* |
| **`chat_takeover.py`** | Reads incoming chat messages from clipboard or screen and drafts professional contextual replies. | *"Draft a polite reply to this client message on my clipboard"* |
| **`telegram_bridge.py`** | Sends proactive push notifications, alerts, files, and system reports to the operator's paired Telegram phone. | *"Send this system report to my Telegram phone"* |
| **`telegram_remote.py`** | Checks pairing status and manages remote control security credentials over Telegram. | *"Check Telegram remote pairing status"* |
| **`whatsapp_call.py`** | Initiates or terminates WhatsApp voice and video calls to contacts or phone numbers. | *"Start a WhatsApp voice call with Alex"* |
| **`whatsapp_guard.py`** | Screens incoming WhatsApp calls, logs callers, and applies automatic voice message reply rules. | *"Activate WhatsApp call screening and auto-reply"* |

---

### 8. 🏃 Health, Lifestyle, Media & Learning (11 Plugins)
| Plugin | Capabilities | Example Voice Prompt |
|---|---|---|
| **`pomodoro.py`** | Controls Pomodoro focus sessions (25-min focus, 5-min break) with interval tracking and verbal notifications. | *"Start a 25-minute Pomodoro focus session"* |
| **`water_reminder.py`** | Logs daily water intake and checks hydration progress towards a configured target (e.g. 2500 ml). | *"Log 350ml of water and check my hydration progress"* |
| **`shopping_list.py`** | Manages a persistent grocery checklist (add, remove, check off, and review items). | *"Add AAA batteries and espresso beans to my shopping list"* |
| **`quiz.py`** | Generates an interactive multiple-choice quiz on any topic rendered directly on the HUD. | *"Quiz me on Linux kernel internals with 5 questions"* |
| **`spaced_repetition.py`** | Flashcard review system using Leitner/SM-2 interval scheduling for long-term knowledge retention. | *"Review my active flashcards for spaced repetition"* |
| **`calorie_counter.py`** | Estimates calories and macronutrients (protein, carbs, fat) from food photos or meal descriptions. | *"Estimate calories in a grilled salmon salad with avocado"* |
| **`pushup_counter.py`** | Tracks pushup workouts and counts repetitions using camera vision or manual workout logging. | *"Start tracking my pushup workout"* |
| **`screen_agent.py`** | Inspects displayed screen elements, identifies buttons/dialogs, and provides step-by-step UI guidance. | *"What button on screen should I click to export the database?"* |
| **`image_generator.py`** | Generates high-fidelity AI imagery from descriptive prompts and saves them locally. | *"Generate an image of a cybernetic research laboratory"* |
| **`upload_video.py`** | Prepares and uploads video files from local workstation to YouTube with title and description tags. | *"Upload the demo video on my Desktop to YouTube"* |
| **`system_matrix_hud.py`** | Engages a full-screen Iron Man diagnostic command matrix compiling cores, RAM, and network shields. | *"Engage system matrix diagnostic HUD"* |

---

## 🛠️ Actions: Native Computer Control (23 Tools)

In addition to plugins, JARVIS carries 23 core action modules in `actions/` driving operating system primitives:

| Action Tool | Description |
|---|---|
| **`computer_settings`** | Master OS control: volume, mute, brightness, Wi-Fi hardware toggle, dark mode, power, restart, lock screen. |
| **`computer_control`** | Keyboard shortcuts, typing text into active windows, mouse clicks, and window management. |
| **`open_app`** | Native application launcher mapping common names to OS executables (VS Code, Chrome, Terminal, Slack). |
| **`file_controller`** | Direct file system operations: list, create, delete, move, copy, rename, find, and disk usage. |
| **`file_processor`** | Reads, parses, and summarizes text, PDF, Word documents (`.docx`), and code source trees. |
| **`code_helper`** | Fast single-script code authoring, syntax debugging, file editing, and execution. |
| **`dev_agent`** | Autonomous background software engineer for deep multi-file project implementation and refactoring. |
| **`system_monitor`** | Hardware telemetry engine monitoring CPU, RAM, GPU, and thermal thresholds with voice warnings. |
| **`screen_processor`** | Visual perception engine capturing screenshots and webcam snapshots for vision analysis. |
| **`web_search`** | High-speed factual search engine querying DuckDuckGo and Google with parallel scraping. |
| **`browser_control`** | Headless and automated browser navigation, link clicking, and page interaction. |
| **`background_tasks`** | Starts, monitors, steers, or cancels long-running background research and drafting tasks. |
| **`background_monitor`** | Daily automated topic monitoring searching for fresh news and alerts on configured subjects. |
| **`proactive`** | Time-aware, rotation-aware proactive check-in engine initiating timely, context-sensitive observations. |
| **`reminder`** | OS-level scheduled alarms using Windows Task Scheduler or Linux systemd/cron timers. |
| **`routines`** | Manages recurring scheduled routines, morning briefings, quiet hours, and daily check-ins. |
| **`send_message`** | Telegram messaging dispatcher delivering proactive text, photos, and voice notes. |
| **`weather_report`** | Native browser search trigger for weather forecasts. |
| **`video_player`** | Embedded video player rendering video files directly inside the HUD where the hologram normally sits. |
| **`desktop`** | Desktop wallpaper manager and legacy file tidying controller. |
| **`flight_finder`** | Automated flight schedule and price scanner. |
| **`game_updater`** | Checks game patches and launcher updates. |
| **`youtube_video`** | Searches YouTube and launches video streams. |

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
- **Operating System:** Linux (Ubuntu 22.04+, Fedora, Arch, Debian), macOS (Sonoma+), or Windows 10/11.
- **Python:** Version 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Hardware:** Microphone and speakers/headphones for voice input and audio response. **Zero GPU required** — all graphics, video rendering, and voice fallbacks run in software on CPU.

### 2. Clone & Setup
```bash
# Clone the repository
git clone https://github.com/SLxnoat/JARVIS-Mark-LVII.git
cd JARVIS-Mark-LVII

# Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies for your specific OS
python setup.py
```

`setup.py` automatically detects your operating system and installs only the relevant packages, skipping platform-specific binaries.

### 3. Configure API Credentials
On first launch, enter your free [Google Gemini API Key](https://aistudio.google.com/app/apikey) in the settings drawer, or populate `config/api_keys.json`:
```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "assistant_name": "JARVIS",
  "user_name": "Sir"
}
```
*(Running in 100% offline local mode with Ollama or llama.cpp requires zero API keys and zero internet connection).*

### 4. Launch JARVIS
```bash
python main.py
```

---

## 🗂️ Project Directory Architecture

```
JARVIS-Mark-LVII/
├── main.py                   # Core event loop — Gemini Live session, audio I/O, viseme extraction, tool dispatch
├── ui.py                     # JarvisUI singleton — thread-safe proxy between worker threads and Qt main thread
├── setup.py                  # OS-aware intelligent dependency installer
├── requirements.txt          # Universal Python dependency manifest
├── AGENTS.md                 # Strict architectural rules for contributors and AI coding agents
├── readme.md                 # Complete system documentation and capability catalog
├── gui/                      # PyQt6 Cybernetic HUD & Widgets
│   ├── theme.py              # Hex color palette, live theme retinting engine, and typography
│   ├── window.py             # MainWindow layout, sliding drawers, and activity stream
│   ├── hud.py                # 8,000-particle software-rendered cybernetic hologram face
│   ├── widgets.py            # High-density activity logs, telemetry gauges, and buttons
│   ├── overlays.py           # Confirmation modal gates (restart, shutdown, wifi toggle)
│   └── providers_panel.py    # Engine switcher: Gemini Live vs Local Ollama vs Piper TTS
├── core/                     # Foundational Runtime Systems
│   ├── prompt.txt            # Master system prompt with 68-plugin disambiguation catalog
│   ├── plugin_loader.py      # Dynamic auto-discovery and validation engine for plugins/
│   ├── action_loader.py      # Dynamic auto-discovery engine for actions/
│   ├── gemini.py             # Multi-tier LLM engine (FAST, SMART) with auto-fallback ladder
│   ├── cloud.py              # Remote cloud server body for Telegram operations
│   ├── llm_client.py         # Multi-provider unified LLM client interface
│   ├── undo.py               # Multi-action reversible undo stack
│   └── tasks/                # Autonomous Background Task Engine
│       ├── engine.py         # Long-running task loop and worker rules
│       ├── research.py       # Autonomous deep investigative researcher runner
│       └── store.py          # Persistent task checkpoint and state storage
├── agents/                   # Autonomous Task Persona Directives
│   ├── general.md            # Multi-step operational and analytical workflows
│   ├── researcher.md         # Primary-source investigative intelligence researcher
│   └── coder.md              # Principal software architect and production code author
├── plugins/                  # 68 Auto-Discovered Autonomous Plugins
│   ├── cognitive_neuro_cortex.py     # Human-brain self-learning engine (rules, habits, mesh)
│   ├── smart_desktop_cleaner.py      # Downloads & Desktop auto-organizer and duplicate scanner
│   ├── workspace_health_summary.py   # Unified executive morning workstation briefing
│   ├── smart_reminder_snoozer.py     # Quick countdown timers and snooze alerts
│   ├── weather_astronomy_briefing.py # Real-time weather, hourly rain radar & solar twilight
│   ├── smart_unit_converter.py       # Technical data rate, download time & compute storage engine
│   ├── pci_hardware_radar.py         # PCIe bus link speeds, NVMe SMART health, CPU governors
│   ├── firewall_warden.py            # UFW/iptables packet filter and listening socket audit
│   ├── docker_sentinel.py            # Docker/Podman container fleet monitor
│   ├── task_planner.py               # Autonomous goal planner & multi-tool combiner
│   └── ... (58 additional plugins)
├── actions/                  # 23 Native Computer & OS Primitive Skills
│   ├── computer_settings.py  # Master volume, brightness, power, and Wi-Fi toggles
│   ├── computer_control.py   # Window focus, typing, clicking, and keyboard shortcuts
│   ├── open_app.py           # Native application launcher
│   ├── file_controller.py    # Local file system CRUD and search operations
│   ├── file_processor.py     # Document reading and summarization
│   ├── code_helper.py        # Single-file code authoring, syntax fix, and debugging
│   ├── dev_agent.py          # Deep multi-file codebase refactoring and development
│   ├── system_monitor.py     # Hardware telemetry background alerts
│   └── ... (15 additional actions)
├── memory/                   # Multi-Tier Knowledge & Memory Storage
│   ├── short_term.py         # Thread-safe in-memory rolling dialogue buffer (<0.01ms)
│   ├── memory_manager.py     # Long-term factual memory and prompt injection formatting
│   ├── vector_store.py       # Local ChromaDB semantic vector embeddings
│   ├── long_term.json        # Permanent user identity, relationships, and preferences
│   ├── learned_rules.json    # Self-learned behavioral rules from operator corrections
│   ├── habits.json           # Discovered procedural workflow macros
│   └── concept_graph.json    # Associative semantic knowledge network
├── config/                   # Local User Settings & API Credentials (Git-Ignored)
│   ├── api_keys.json         # API keys, assistant name, voice choice, and toggles
│   └── certs/                # Local self-signed TLS certificates for secure web dashboard
└── tests/                    # Comprehensive Automated Unit Test Suites (51+ Tests)
    ├── test_daily_productivity_plugins.py
    ├── test_cognitive_neuro_cortex.py
    ├── test_new_high_tech_plugins.py
    ├── test_20_cool_plugins.py
    └── test_task_planner.py
```

---

## 🔒 Security & Data Privacy

JARVIS is built from the ground up on a **Local-First, Zero-Telemetry** philosophy:
- **No Third-Party Cloud Servers:** There is no centralized JARVIS server. All tools, memory databases, and background tasks run exclusively on your physical hardware.
- **Local Credentials:** API keys and credentials reside in `config/api_keys.json` on your local file system, protected from repository commits via `.gitignore`.
- **Destructive Action Confirmation Gate:** Critical system operations (restarting, shutting down, toggling Wi-Fi hardware) render a physical visual modal gate requiring explicit operator confirmation before execution.
- **Untrusted Content Demarcation:** External web pages, PDFs, and scraped data are quarantined inside `<<<UNTRUSTED>>>` safety boundaries, shielding the prompt engine from prompt injection attacks.
- **Complete Offline Mode:** Switch to local models (Ollama, llama.cpp, Faster-Whisper, Piper-TTS) at any time to guarantee that zero bytes of audio, text, or metadata ever leave your machine.

---

## ⚠️ License

Personal, educational, and non-commercial use only.  
Licensed under the **[Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)**.

---

## 👤 Maintainer & Acknowledgments

- **Lead Developer & Maintainer:** **SLxnoat (Xnoat)**  
- **GitHub:** [@SLxnoat](https://github.com/SLxnoat)  
- **Repository:** [JARVIS-Mark-LVII](https://github.com/SLxnoat/JARVIS-Mark-LVII)  
- **Academic Contact:** [itbin-2211-0148@horizoncampus.edu.lk](mailto:itbin-2211-0148@horizoncampus.edu.lk)  
- **Upstream Inspiration:** Based on the foundational concept by [FatihMakes](https://www.youtube.com/@FatihMakes).

⭐ **Star the repository if JARVIS empowers your daily workstation!**
