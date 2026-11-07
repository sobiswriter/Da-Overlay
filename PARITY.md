# Original abilities and companion presence

| Original ability | Current access |
| --- | --- |
| Show/hide, focus input | Alt X now folds to an edge orb; Alt A focuses the appropriate chat surface |
| Region, fullscreen, no capture | Share screen menu; Alt 0 cycles automatic capture modes |
| Global movement | Alt Arrows and Alt 8/4/2/6; moves the window or repositions the orb |
| Context and clock sharing | Rail switches; Alt 5 and Alt 7 |
| Theme and opacity | Settings; Alt D, Alt W, Alt S; 20–100% workspace opacity |
| All 13 original persona presets | Companion → Original personalities; original instructions retained verbatim |
| Custom companions | Save multiple named profiles with individual images/icons; switch in the editor or orb menu |
| Cloud connection | Gemini API keys or Vertex AI through local ADC, with account/project checks |
| Voice messages | Record, review, play, discard and send from full/compact/native chat; Alt Shift V |
| Spoken replies | Optional local Windows voice, Listen on written replies and Mute |
| Custom personality and model | Companion editor and Settings; live model discovery |
| Screen understanding | Full-resolution manual captures; separate opt-in periodic Autopilot snapshots |
| Google Search grounding | Search switch; response sources and search suggestions |
| Streamed text and Markdown | Full workspace; quick reply streams plain text into the same conversation |
| Copy an answer | Copy control in the workspace |
| Save/load chat | Autosave, JSON export/import and searchable history |
| Generate/save/load memory diary | Memories, TXT export/import and diary generation |
| Collapse conversation into memory | Conversation menu → Collapse to memory; original chat is retained in history |
| Configurable Autopilot intervals and cooldown | Settings; fixed interval or a comma-separated sequence, plus quiet time after speaking |
| Refresh interface and clear chat | Conversation menu; clearing starts fresh while retaining the archived conversation |
| Safe exit/save handling | Atomic autosave; failed saves block closing instead of losing the session |
| Tooltips, moving and resizing | Named controls, visible shortcut reference, draggable header and native resizing |

## New side-by-side interaction

- Native 48px round orb, draggable anywhere inside a monitor's work area, with
  magnetic snapping near its edges. Thoughts follow while it moves.
- Single click fans out four actions: Chat, Capture, Voice, and the last workspace or
  overlay. Right-click offers explicit full/compact window choices and companion
  switching. Double click restores the window. Alt Shift Q opens the small chat
  bar directly; Escape closes it. History expands its transcript.
- Radial action circles are 36px with compact labels. Closing retracts/fades them
  into the orb, with immediate cleanup when hiding or capturing.
- Right-click → Hide Cutex removes every surface and pauses check-ins. Alt Shift H
  or Alt X restores the orb. Quit saves and closes both UI threads even while docked.
- Capture selects a region, then opens chat with a preview and removal control.
  Cancelling capture leaves the small chat surface closed.
- Voice recording is explicit, capped at two minutes and reviewed before upload.
  Transcripts survive restart; raw recordings are not saved. Recording, voice
  drafts and speech playback pause Autopilot check-ins.
- Native resize/fade transitions connect workspace, overlay and orb; radial
  actions, chat and thoughts move out from the orb. Windows reduced motion is
  respected. Animation callbacks stop when a surface is dragged or dismissed.
- Native transparent message cards rise beside the orb, remain for 10–45 seconds
  according to reading length, and pause expiry while hovered. Up to three cards
  are visible; the full answer remains in chat. Near the top edge, cards expand
  downward so they remain visible. Click a thought to reply.
- Passive windows use Windows' no-activate/tool-window styles. Incoming messages
  do not take keyboard focus from a game or another app.
- The full workspace's browser lifecycle is frozen while tucked away. Hidden
  replies update the native surface; restoring wakes and resynchronizes the page.
- Screen check-ins require explicit permission and work while the workspace is
  tucked away. Unchanged images and active requests are skipped. Background
  snapshots are reduced to at most 1280px wide; manual captures stay full size.
- Companion names, instructions and avatars persist independently. Uploaded
  images are cropped to circular 96px PNGs locally, with no new imaging dependency.
  Switching companions preserves shared chats/memories; new answers keep their
  author's name even after switching again.
- No screenshot files, background microphone recording, continuous video, or
  automatic desktop actions are added. Autopilot pauses on API failure. Alt Shift P pauses
  or resumes it after permissions have been configured.

The app remains a normal Windows overlay. Exclusive fullscreen games may require
borderless/windowed mode. This is not a guarantee of compatibility with every
game, capture system, anti-cheat product, or monitor/DPI arrangement.
