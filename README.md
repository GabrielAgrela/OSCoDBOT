Call of the Dragons Bot (UI + State Machine)

Overview
- Tkinter UI with a single Start/Stop button to run a scouting loop.
- Windows-only capture and click using `pywin32` and `mss`.
- State machine + modular actions (periodic screenshot, find+click, wait).
- Template matching via OpenCV with percentage-based search regions.

Project Structure
- `main.py`: Entry point for the UI.
- `bot/ui/app.py`: Tkinter UI and background runner thread.
- `bot/core/state_machine.py`: Context, SequenceState, GraphState and StateMachine.
- `bot/core/window.py`: Window discovery, capture, bring-to-front, and click.
- `bot/core/image.py`: Matching utilities and template loading.
- `bot/actions/`: One file per action
  - `screenshot.py` (`Screenshot`)
  - `find_click.py` (`FindAndClick` with one-or-many templates)
  - `click.py` (`ClickPercent`)
  - `wait.py` (`Wait`)
- `bot/states/`: One file per machine state
  - `scouts.py` (`build_scouts_state`)
  - `farm_wood.py` (`build_farm_wood_state`)
- `assets/templates/`: Place your PNG templates here.

Prerequisites
- Windows 10/11.
- Python 3.10+ recommended.
- Google Play Games window running the game. Default title substring: `Call of Dragons`.

Windows Install (Step-by-step)
1) Install Python 3.10+ from python.org (check "Add Python to PATH").
2) Open Command Prompt (CMD) in this project folder.
3) Create a virtual environment:
   py -m venv .venv
4) Activate it:
   .\\.venv\\Scripts\\activate.bat
5) Upgrade tooling (recommended):
   python -m pip install --upgrade pip setuptools wheel
6) Install dependencies:
   pip install -r requirements.txt
7) Run the app:
   python main.py

Optional
- If you see a pywin32 post-install message or click issues, run:
  python -m pywin32_postinstall -install
- If OpenCV fails to import due to missing VCRUNTIME DLLs, install the
  "Microsoft Visual C++ Redistributable for Visual Studio 2015-2022 (x64)" from Microsoft.

Usage
1) Place template images in `assets/templates/`.
   - Scouts: `ScoutIdle.png`, `ScoutSelectExplore.png`, `ScoutExplore.png`.
   - Farm Wood: `Magnifier.png`, `MapIcon.png`, `LoggingCamp.png`, `LoggingCampEnabled.png`,
     `SearchFarmButton.png`, `GatherButton.png`, `CreateLegionsButton.png`, `March.png`.
2) Run the UI:
   python main.py
3) Buttons:
   - "Start Scouts" runs the scouts loop.
   - "Start Farm Wood" runs the wood-farm flow. Starting one stops the other.

Behavior
- Scouts: Screenshot then find/click templates in sequence with waits.
- Farm Wood: Branching flow (GraphState) with retries and a center-tap fallback before re-trying Gather.


Configuration
- Defaults are set in `bot/config.py`:
  - `WINDOW_TITLE_SUBSTR = "Call of Dragons"`
  - `MATCH_THRESHOLD = 0.85`
  - `SIDE_REGION_PCT = (0.6, 0.0, 0.4, 1.0)`  # right 40%
  - Templates: place PNGs under `assets/templates/` per the state definitions.

Notes
- Template matching is sensitive to resolution/scale. Ensure templates are captured from the same window scale.
- If matching is noisy, adjust `MATCH_THRESHOLD` in `bot/config.py`.
- If the window title differs, update `WINDOW_TITLE_SUBSTR`.

Disclaimer
- Use responsibly and in accordance with the game’s terms of service.



