# Cutex

A little company. A clearer mind.

Cutex is a Windows desktop companion and screen-aware copilot. A full workspace
keeps conversations, memories, and personality in one place. A compact overlay
and a native round companion orb stay beside whatever you are doing. The interface is local; Gemini handles the
AI requests you choose to send.

## Run it

- Open `release/Cutex.exe` for the new standalone build, if present.
- For source development, run `run.bat` once. It creates/uses `.venv` and installs
  missing dependencies. Later, `run.vbs` opens Cutex without a terminal.
- Or: `.venv\Scripts\python.exe main.py` from this directory.

Requires Windows 10/11, Microsoft Edge WebView2 Runtime, and either a Gemini API key
or a Google Cloud project with Vertex AI access and local Google Cloud credentials.
Source development also requires Python 3.10+ with Tkinter. Get a key at
https://aistudio.google.com/apikey. Google bills model and search usage directly.

Open Settings to choose Gemini API or Vertex AI, then save and test the connection.
Vertex AI uses Application Default Credentials from this device; it does not need
an AI Studio key. If sign-in is needed, run `gcloud auth application-default login`
yourself, then enter the project ID, account email and location (`global`). The
account is checked before using the project. OAuth tokens never enter UI state,
exports or the executable. The Cloud SDK is needed for sign-in, not app runtime.

The default model is `gemini-3.8-flash`. Presets also include
`gemini-3.5-flash-lite` and `gemini-4-argon`. Existing preferences are retained unless
explicitly updated. Refresh checks key-based model discovery; Vertex presets use
Save & test to verify access in the selected project. A key being
present does not guarantee billing, quota, or model access. Errors are displayed
in the conversation with a retry control. No successful AI response is simulated.

## The new experience

- A charcoal/ivory workspace with pale citron accents, original orbital artwork,
  a daylight theme, keyboard focus states, and reduced-motion support.
- Conversation, memory library, and companion editor. Search local conversations
  from the sidebar or Ctrl K. Long histories render in batches of 80 messages.
- Companion, Focus, Study, and Play modes change the instructions supplied to your
  chosen model. Anna, TARS, Holmes, Neko, and custom personalities are available.
- Real streamed Markdown, code blocks, tables, copy, stop, retry, and web source
  links. Only one response is active; cancelled workers cannot overwrite it.
- Voice messages from the workspace, compact overlay, native chat bar, or the
  radial menu's separate Voice action. Alt Shift V starts/stops recording. Review,
  play or discard the clip before sending. Clear recording indicators, a level
  meter and a 2-minute limit keep the microphone's state explicit.
- Voice messages get a saved transcript, and Gemini receives the audio for its
  reply. Optional Windows read-aloud speaks replies to voice messages. Listen can
  read any completed reply; Mute stops it. Code blocks are omitted and read-aloud
  is capped at 6,000 characters. The microphone stops before playback or read-aloud
  can feed back into the next recording.
- A compact 440px overlay, pinning, window opacity, and all original global shortcuts.
- A draggable round edge orb, transparent floating thoughts, and a native quick-reply
  bar. Alt X folds to the orb; click for a radial menu with Chat, Capture, Voice and
  Workspace/Overlay. Double-click restores the window. Drag it anywhere; it only
  snaps when close to a screen edge. Thoughts follow during dragging.
  Passive thoughts do not steal focus and stay 10–45 seconds, with hover to pause.
  The orb is 48px; its four action circles are 36px. Closing the radial menu pulls
  its controls back into the orb and fades them out.
  The browser workspace is frozen while tucked away and wakes when restored.
- All 13 original persona presets remain available in the Companion editor.
- Save multiple companions, each with its own name, instructions and avatar.
  Use an icon or upload a PNG, JPEG or WebP under 5 MB; Cutex crops it to a small
  circular image locally. Switch in Companion or the orb's right-click menu.
  One companion is active at a time; switching preserves chats and memories.
- Short native resize/fade transitions connect workspace, overlay and orb, with
  Windows reduced-motion support. The radial menu and thoughts also animate from
  the orb. No permanent backdrop or desktop slogan is part of the app.
- Chat opens a small input bar. Replies float above it; History expands the
  transcript. Capture opens the bar with a preview and remove control, without
  opening the workspace. Right-click the orb to choose full workspace or overlay.
- The conversation menu restores refresh, clear/start fresh, TXT diary export,
  and collapse-to-memory. Collapsing retains the original full conversation.
- Manual notes, remembered answers, and model-generated conversation diaries.
  Generating a diary never replaces or deletes the original conversation.
- Import original JSON conversation files and TXT memories; export portable JSON.

## Context and privacy

For a manual capture, choose the primary screen or drag a region, inspect the
preview, and remove it if you change your mind. Nothing is sent until you send a
message. Capture bytes stay in memory, not screenshot files or chat exports.
Escape cancels region selection. A recent capture remains in process memory for
retry until another message replaces it or Cutex closes.

Window context is a separate switch. When enabled, the foreground application's
name and window title can be included in requests. Turning it off also pauses
proactive observations unless screen-snapshot permission is separately enabled. Date/time and Google Search have separate controls.

A gentle nudge is off by default. In Settings, explicitly enable periodic screen
snapshots if you want visual check-ins. With that permission off, Autopilot can
use separately permitted window titles. It runs even with the workspace tucked
away. Choose a fixed interval, an optional interval sequence, and quiet time after
speaking. Unchanged snapshots and active responses are skipped. The companion's
own surfaces are temporarily hidden during capture, with no focus change.

Background snapshots are reduced to at most 1280px wide to limit CPU, upload size
and model input. Manual captures stay full resolution. Images stay in process
memory. An API failure pauses Autopilot instead of repeatedly interrupting you.
Alt Shift P or the orb's menu pauses/resumes it. It sees periodic snapshots, not
continuous video or audio. Watching a movie or game does not give it the audio.

Alt 0 cycles no automatic capture, region selection on each send, and primary
screen on each send. The active mode is visible at the composer. This explicit
mode choice allows automatic attachment; normal manual captures still preview
before sending. Escape cancels a region selection without discarding the draft.

Microphone recording starts only from a record control or Alt Shift V. There is
no background listening. Cutex keeps clips in RAM, sends them to the selected
Google provider only when you send, and saves the transcript instead of an audio
file. Transcription and answering use separate model calls; Google's service
terms apply to processing. A failed transcription can retain the clip in memory
for Retry until another message or app close. Recording and voice drafts pause
Autopilot check-ins. A disconnected microphone preserves captured audio where
possible and warns when audio was skipped. Actual microphone permission is checked
when recording starts; Cutex does not change Windows privacy settings.

Enabled memories are reference context, capped at 12,000 characters, newest first.
Disable a memory to keep it in the library without including it in new requests.
This is an editable notes/diary system, not an autonomous or unlimited memory.

## Your data

Conversations, preferences, and memories save automatically under
`%LOCALAPPDATA%\OverlayCutex\state.json`. Writes use a temporary file and atomic
replacement. If a save fails, Cutex keeps the window open when closing so you can
export the conversation. Partial responses are recovered after an interruption.

The API key is protected with Windows DPAPI in `key.bin`, separate from chat
state. The key never enters frontend state, exports, screenshots, or the build.
A legacy `settings.json` is read on first source launch (or beside a packaged
executable), but is never changed or deleted. Original plaintext keys in old
settings files remain there; exclude those old settings when sharing old folders.

Each workspace allows one running instance to avoid conflicting autosaves.
`CUTEX_DATA_DIR` selects an isolated workspace for development and tests. Microsoft
Store Python can redirect source-mode AppData writes into its package cache;
the standalone executable uses the normal AppData folder. Export/import chats
when moving between those profiles. No Cutex account or hosted storage is required.

## Shortcuts

| Action | Shortcut |
| --- | --- |
| Workspace / round orb | Alt X |
| Quick reply at the orb | Alt Shift Q |
| Pause / resume Autopilot | Alt Shift P |
| Hide / show all Cutex surfaces | Alt Shift H |
| Start / stop voice recording | Alt Shift V |
| Cycle automatic capture | Alt 0 |
| Context / time sharing | Alt 5 / Alt 7 |
| Theme | Alt D |
| Opacity up / down | Alt W / Alt S |
| Move window or orb | Alt Arrows / Alt 8, 4, 2, 6 |
| Focus chat | Alt A |
| Overlay / workspace | Alt Shift O |
| Capture a region | Alt Shift S |
| Quick actions and conversation search | Ctrl K |
| New conversation | Ctrl N |
| Send / new line | Enter / Shift Enter |
| Stop response, when no dialog is open | Escape |

Matched global shortcuts suppress the original key combination, so moving the
overlay with Alt Left does not also navigate the browser back. These combinations
are reserved while Cutex runs; the same actions are also available inside Cutex. Exclusive fullscreen games can cover a desktop overlay; use a
borderless/windowed mode where needed.

Right-click the orb and choose Hide Cutex to remove the orb, input and thoughts.
Alt Shift H or Alt X brings the orb back; Alt A opens quick reply. Fully hiding
Cutex pauses Autopilot and mutes speech. An active recording stops into a draft.
Quit uses the same saved-exit path from the workspace or orb. A failed save keeps
Cutex running and opens the workspace for recovery.

## Development and verification

The new entry point is `main.py`; `desktop.py` owns the native bridge and request
lifecycle. `utils/storage.py` owns persistence, `utils/gemini_client.py` owns the
Gemini REST boundary, and `ui/web/` contains the frontend. The old Tkinter UI
source is retained unchanged so existing local work is not discarded; the new
entry point does not load it.

```
.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check ui/web/app.js
.venv\Scripts\python.exe -B tests\smoke_webview.py
.venv\Scripts\python.exe -B tests\smoke_companion.py
```

The unittest suite uses temporary workspaces and mocked network boundaries.
The explicit WebView2 check opens a short-lived test window, streams a clearly
synthetic offline fixture, verifies real frontend interactions and screenshots,
and closes without reading your saved workspace or calling an external model.
Artifacts are written to `output/playwright/`. These screenshots demonstrate the
UI; the example conversation is not a live model benchmark.

Frontend libraries are bundled with pinned versions and licenses in
`ui/web/vendor/`. There is no Node build step or runtime CDN dependency.

Run `build.bat` to test and build `release/Cutex.exe` using PyInstaller. The build
includes UI assets, Python, and the native bridge. It does not bundle API keys,
settings, chat files, or Edge WebView2 itself. The build never deletes the old
`dist/` directory. Keep WebView2 installed on the destination PC.

`OVERHAUL.md` records the design and implementation contract.

`PARITY.md` maps every original ability to its current control and describes the native companion surfaces.

`REFINEMENTS.md` records the bug fixes, voice boundaries and live Vertex validation.
