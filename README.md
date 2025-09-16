Call of Dragons Automation Bot
==============================

Highlights
- Windows-only automation for Call of Dragons built on OpenCV, pywin32, and mss.
- Flask-powered web control panel with live status, counters, logs, and latest match screenshots (served in your browser).
- Modular state machine with cooldown gates, stuck detection, and round-robin multi-mode orchestration.
- Template-driven flows covering scouts, alliance help, resource farming, gem scanning, troop training, and more.
- Configurable via .env (editable from the UI) with persistent counters and log rotation.

Project Layout
- `main.py` - entry point that enables DPI awareness and launches the embedded web UI.
- `bot/config.py` - default configuration, .env loader, and runtime overrides.
- `bot/core/` - window capture/click helpers, state machine runtime, logging, counters, and perf probes.
- `bot/actions/` - reusable actions such as screenshot capture, template matching, cooldown gates, retries, and spiral camera moves.
- `bot/states/` - high-level behaviors for each automation mode plus orchestrators for alternating / round-robin execution.
- `bot/web/` - Flask app, REST API, templates, and static assets for the control panel.
- `assets/templates/` - PNG templates that drive matching (you supply these per mode).
- `debug_captures/` and `start_captures/` - optional screenshot dumps for debugging.
- `bot.counters.json` and `bot.log*` - persisted counters and rotating log files.
- `codbot.spec` and `start_bot.bat` - PyInstaller specification and convenience launcher.

Prerequisites & Setup
1. Windows 10/11 (64-bit) with the Call of Dragons client (Google Play Games) installed.
2. Python 3.10+ (64-bit). Install from python.org and check "Add Python to PATH".
3. Install the Microsoft Visual C++ Redistributable for Visual Studio 2015-2022 (needed by OpenCV).
4. From the project folder:
   ```
   py -3.10 -m venv .venv
   .\.venv\Scripts\activate
   python -m pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```
5. If pywin32 prompts for post-install hooks:
   ```
   python -m pywin32_postinstall -install
   ```

Running the Bot
- Ensure `assets/templates/` contains the PNG templates that match your game resolution and UI scale.
- Launch the game (or configure `GAME_SHORTCUT_PATH` so the bot can start it for you).
- Start the bot:
  ```
  python main.py
  ```
- The control panel opens at `http://127.0.0.1:5000` in your default browser.
- Use the mode cards to choose one or more flows (search or bulk-select as needed), press **Start** to run, **Stop** to halt, and **Pause/Resume** to temporarily suspend actions.
- One selection runs that state with an automatic check-stuck pass each cycle. Multiple selections are executed round-robin with per-mode cooldowns and a randomised order after the first round.
- The **Close** button in the UI shuts down the bot process.

Web Control Panel
- Live status shows running/paused state, selected modes, and remaining cooldowns reported from the state contexts.
- Counters persist between runs (`bot.counters.json`) and session deltas reset each time you press **Start**.
- The settings drawer edits `.env` in place and hot-reloads the machine when possible. You can tune match/verify thresholds, toggle snapping, change cooldown ranges with dual sliders, adjust logging/capture options, and point at custom shot directories.
- The log view streams the last ~400 entries with severity coloring; `/shots/latest` preview shows the newest annotated match (enable `SAVE_SHOTS`).
- Metrics include the active state/step, last action duration, cycle count, memory/handle usage, capture health, and the current game window rectangle.

Available Modes & Templates
All templates live under `assets/templates/`. Names are case-sensitive; capture them from the same resolution the bot will use.

- **Farm Alliance Resource Center** (`farm_alliance_resource_center`): `AllianceIcon.png`, `TerritoryIcon.png`, `AllianceTerritoryHideButton.png`, `AllianceResourceCentersButton.png`, `AllianceResouceCenterPlusButton.png`, `AllianceResourceCenterCreateLegionIcon.png`, `CreateLegionsButton.png`, `GatherButton.png`, `March.png`.
- **Scouts** (`scouts`): `ScoutIdle.png`, `ScoutSelectExplore.png`, optional `ScoutSelectExplore2.png`, `ScoutExplore.png`.
- **Farm Wood / Ore / Gold** (`farm_wood`, `farm_ore`, `farm_gold`): shared templates `Magnifier.png`, `MapIcon.png`, `SearchFarmButton.png`, `MinusFarmLevelButton.png`, `GatherButton.png`, `CreateLegionsButton.png`, `March.png`, plus resource-specific icons such as `LoggingCamp.png` and `LoggingCampEnabled.png`, `OreMine.png` or `Quarry.png`, or `GoldMine.png` or `GoldDeposit.png`. Ensure `MiningIcon.png`, `GoingIcon.png`, `ReturningIcon.png`, `BuildingIcon.png`, and `StillIcon.png` exist for the unit-overview checks.
- **Farm Mana** (`farm_mana`): use the common farming templates above and `ManaPool.png`, `ManaPoolEnabled.png`.
- **Farm Gems** (`farm_gem`): `GemMine.png`, `GatherButton.png`, `CreateLegionsButton.png`, `March.png` plus the unit overview icons listed above. Spiral camera moves continue until a gem mine is detected.
- **Train** (`train`): `ActionsMenuButton.png`, `ActionMenuClose.png`, `ActionSectionsMinimizedIndicator.png`, `ActionMinimizeArrow.png`, `ActionDoneNotification.png` or `ActionProgressComplete.png`, `TrainButton.png`, and one or more of `TrainCavalaryButton.png`, `TrainMageButton.png`, `TrainBalistaButton.png`, `TrainInfantaryButton.png`, `TrainInfantryButton.png`.
- **Alliance Help** (`alliance_help`): `AllianceHelp.png`, `AllianceHelpBig.png`.
- **Stuck Recovery**: `BackArrow.png`, `CloseButton.png`, `ReconnectConfirmButton.png`, `ChatCloseButton.png`. This state is injected automatically after each cycle to clear popups.

Configuration
- Settings live in `.env` and are parsed on startup (and whenever you save from the UI). `bot/config.py` accepts raw numbers such as `0.85` or percent strings such as `85%`. Duration fields accept suffixes such as `30s`, `5m`, or `2h`.
- **Window and launching**
  - `WINDOW_TITLE_SUBSTR`: substring used to locate the game window (default `Call of Dragons`).
  - `FORCE_WINDOW_RESIZE`, `FORCE_WINDOW_WIDTH`, `FORCE_WINDOW_HEIGHT`: resize the client area to a known size before running.
  - `GAME_SHORTCUT_PATH`: `.lnk` or `.exe` to launch when the window is missing.
  - `GAME_LAUNCH_WAIT`: seconds to wait after launching the shortcut before scanning for the window.
- **Matching and input**
  - `MATCH_THRESHOLD`, `VERIFY_THRESHOLD`: template matching ratios.
  - `CLICK_SNAP_BACK`: return the cursor to its original position after clicks.
  - `MAX_ARMIES`: how many gathering icons count as "full" before a farm mode enters cooldown.
- **UI embedding**
  - **Cooldowns**
  - `FARM_COOLDOWN_MIN`, `FARM_COOLDOWN_MAX`, `TRAIN_COOLDOWN_MIN`, `TRAIN_COOLDOWN_MAX`, `ALLIANCE_HELP_COOLDOWN_MIN`, `ALLIANCE_HELP_COOLDOWN_MAX`: min/max ranges picked uniformly at random.
- **Debugging and captures**
  - `SAVE_SHOTS`, `SHOTS_DIR`, `SHOTS_MAX_BYTES`: enable annotated screenshot dumps and cap total size.
  - `START_SHOTS_DIR`: folder for the initial full-screen capture each time you press **Start**.
- **Logging**
  - `LOG_TO_FILE`, `LOG_FILE`, `LOG_MAX_BYTES`, `LOG_BACKUPS`: control log rotation.
- All defaults are documented in `bot/config.py`; unknown keys are ignored.

Debugging & Telemetry
- Annotated matches and templates are written to `debug_captures/` when `SAVE_SHOTS=true`; the folder is pruned automatically to stay under the configured byte limit.
- The very first capture of each session is stored in `start_captures/` for troubleshooting initial window alignment.
- `bot.log` (plus `bot.log.1` through `bot.log.5`) contains the structured log stream surfaced in the UI. Delete them if you want a fresh log; rotation happens automatically at about 1 MB each.
- `bot.counters.json` persists total troops trained, nodes farmed, and alliance helps so the UI can display lifetime counts even after restarting the app.
- The `/api/metrics` endpoint (and the UI panel) expose process memory, handle counts, capture health, and window bounds for quick health checks.

HTTP API
The UI consumes the same REST API that you can script against:

- `GET /api/modes` - available mode keys and labels.
- `GET /api/status` - running/paused state and active cooldowns.
- `POST /api/start` - start with `{"selection": ["farm_wood", "train"]}`.
- `POST /api/stop`, `/api/pause`, `/api/resume` - control the state machine.
- `GET /api/env` / `POST /api/env` - read or update `.env` entries.
- `POST /api/reload` - rebuild the running machine without changing the selection.
- `GET /api/logs?since=N` - stream incremental log entries.
- `GET /api/metrics` - runtime metrics and counters.
- `GET /shots/latest` - latest debug match image.
- `POST /api/quit` - stop the machine and exit the process.

**OCR Utilities**
- `ReadText` uses EasyOCR under the hood. Set `region_pct` to crop the screenshot, optionally specify `expected` for fuzzy matching, and dial `min_ratio` to control tolerance.

Packaging
- `codbot.spec` targets PyInstaller if you want to distribute a bundled executable. Build with:
  ```
  pyinstaller codbot.spec
  ```
  Bundled runs still expect the `assets/` and template files next to the executable.

Disclaimer
- Automating online games may violate their terms of service. Use this project responsibly and at your own risk.
