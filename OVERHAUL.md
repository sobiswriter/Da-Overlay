# Cutex — desktop companion overhaul

## Companion presence extension

The workspace is one surface, not the default way to talk while doing something
else. Alt X collapses it to a draggable, round orb. A single click opens a
four-action radial menu; Alt A opens a native chat bar; a double click restores
the window. Chat, capture-to-chat and workspace/overlay are available from the
radial menu. The orb can stay anywhere, with magnetic snapping near screen edges.
Native resize/fade transitions connect the surfaces and honor reduced motion.
Passive
message cards rise above the orb, stay long enough to read, pause on hover and
expire. They never activate a window or steal keyboard focus. All surfaces share
one conversation. Native transparent windows avoid a second Chromium renderer.
Thoughts follow the orb during dragging. The small chat bar shows replies in
floating bubbles; History expands its transcript. There is no desktop backdrop
or slogan in the shipped UI. Companions are saved individually with local icons
or circular images, and switching preserves chats and memories.

Autopilot can use periodic screen snapshots after its separate screen-observation
switch is enabled. It works with the workspace tucked away, honors pause, skips
unchanged captures and active requests, hides Cutex surfaces during capture, and
never writes the image to disk. It sees snapshots, not continuous video or audio.
An API failure pauses check-ins instead of repeatedly interrupting the user.

Every original shortcut is retained: Alt X/A/0/5/7/D/W/S, Alt Arrows and Alt 8/4/2/6.
Automatic capture modes, memory TXT export, collapse-to-memory, refresh, and clear
are restored. Autosave and the original full conversation survive collapsing.
Native focus behavior, actual transparency, quick-reply streaming, screen
opt-in/cancellation, notification lifetime and shortcut registration are checked.

Direction: a companion and a useful screen-aware copilot. Keep Python, Gemini,
Windows capture, existing keys/personas, and importable chat files. Replace the
Tkinter presentation with a local HTML/CSS/JS interface in Edge WebView2 through
pywebview. No Node build, account, hosted backend, or remote UI assets.

## Product and design contract

- A calm charcoal workspace, warm ivory text, pale citron actions, restrained
  borders, clear type hierarchy, and an original orbital companion mark.
- Conversation is primary. Searchable local sessions at left; explicit context
  and companion controls at right. A compact always-on-top overlay shares the
  same conversation. Adapt down to a 420px-wide panel.
- Modes: Companion, Focus, Study, Play. They change useful instructions, not
  claims about the underlying model's abilities. Custom personas stay editable.
- Real streaming; stop generation; copy the current completed answer; retry;
  readable Markdown and source links. Never simulate successful AI responses.
- Manual captures are previewed, cancellable, and held in memory. Automatic
  attachment modes require an explicit selection; periodic Autopilot screenshots
  require separate permission. Region selection supports Escape. Window titles
  and screenshots have separate controls, respected in proactive requests.
- Persist conversations automatically, atomically, and locally. A memory library
  supports manually pinned notes and model-generated diaries. Only enabled
  memories enter prompts. Import old JSON chats and TXT memories without changing
  the originals. API keys use Windows DPAPI, never enter frontend state or exports.
- Autopilot is off until enabled. It respects context controls, skips unchanged
  context and active requests, and stops when paused. No desktop actions or
  background audio capture are added; voice messages require explicit recording.
- Show real empty, disconnected, generating, stopped, error, saved, and capture
  states. All controls have names, keyboard focus, and reduced-motion support.

## Implementation order

1. Storage and Gemini boundary: validate imports, atomic saves, secret protection,
   stream all text parts, cancellation, explicit errors and grounding metadata.
2. Desktop controller: one active request, autosave, capture preview, memory,
   model discovery, native dialogs, overlay, hotkeys, context-aware proactivity.
3. UI: workspace, conversation, composer, context rail, memory library, settings,
   compact mode, searchable sessions and command palette.
4. Verify with offline unittest regressions, mocked streamed requests, real
   WebView2 startup and native UI interactions, plus screenshots at both sizes.
5. Update launch/build scripts and README. Build into a fresh release directory;
   never delete the user's existing dist folder or settings.

## Files and verification

- `main.py`: entry point; `desktop.py`: pywebview bridge and Windows integration.
- `utils/storage.py`: persistence; `utils/gemini_client.py`: Gemini REST boundary.
- `ui/web/`: local frontend and vendored, pinned Markdown/sanitizer/icon assets.
- `tests/`: stdlib unittest, no API keys or billable calls required.
- Run: `.venv\Scripts\python.exe main.py`
- Test: `.venv\Scripts\python.exe -B -m unittest discover -s tests -v`
- Syntax: `node --check ui/web/app.js`
- Build: `build.bat` (new release output only).

Existing uncommitted Tkinter changes remain available in their original files.
No unrelated data, old builds, screenshots, chats, or legacy settings are removed.
Cluely is a reference for compact, immediate access; its branding, claims about
invisibility, interview features, and exact screens are not part of this design.

## Verified on 3 November 2026

- 72 offline regression tests pass, covering protected keys, migration, imports,
  atomic saves, failed saves/close/delete, request isolation/cancellation, context
  permissions, region cancellation, real message text and stream parsing, native
  bubble lifetime/placement, capture downsampling, Autopilot pause/skip rules,
  companion migration/persistence/rollback, radial layout at monitor corners,
  voice capture/cleanup/retry, ADC identity, provider routing and cancellation
  during authentication. See `REFINEMENTS.md` for this pass's fixes.
- The explicit WebView2 integration check passes: native startup, all icons,
  modes, streamed Markdown, sanitization, sources, copy, memory save, navigation,
  preferences submission, command palette, overlay/restore, both themes, and
  graceful shutdown. It also checks real native orb/quick-reply startup beside
  WebView2, browser freeze/wake, resynchronization and closing while docked.
  Avatar icon rendering, file-image conversion, saved-companion creation and
  switching are exercised through the real frontend. Synthetic record/review/send
  flows, transcript rendering and Vertex settings submission are also checked.
  Real UI screenshots are in `output/playwright/`.
- The native companion check passes on a synthetic backdrop: actual transparent
  surfaces, passive messages preserving foreground focus, streaming quick reply,
  persisted docking, visible top-edge bubbles and clean Tk shutdown. It also
  checks all four radial actions, labels on bright backgrounds, capture
  cancellation, native avatar updates, voice record/review/send, capture previews
  and bubbles following a freely dragged orb.
- Wake checks assert the actual browser viewport and page visibility across
  repeated orb/full/compact transitions. Native geometry changes keep hidden
  windows hidden; waking explicitly restores WebView2 host visibility.
- JavaScript syntax and whitespace checks pass for this overhaul. Whitespace
  issues in the pre-existing, uncommitted Tkinter changes were left untouched.
- The earlier AI Studio key returned HTTP 402. The new Vertex integration verifies
  the requested account and existing On Sundays project. All three requested
  models pass token-count checks; Gemini 3.8 Flash also passes real synthetic voice
  transcription and streaming generation. No personal voice/screen data is used.
- The new executable builds separately as `release/Cutex.exe`. No old builds,
  chat files, memory files, or legacy settings were deleted.
- The packaged executable passes startup, bundled assets, native bridge,
  initialized workspace, collapse to the native orb, restore and graceful close
  using an isolated profile without live model calls. The radial build also
  passes companion/avatar saving and full → compact → orb → compact → orb → full,
  checking actual viewport dimensions and page visibility after waking.
- Physical multi-monitor/DPI capture, a long gaming session, and screen reader
  behavior still need real-use validation. Capture cancellation is covered at the
  native boundary; screenshots in the UI verification use no personal screen data.
