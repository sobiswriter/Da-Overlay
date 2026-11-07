# Voice, Vertex AI and refinement pass — 3 November 2026

## Fixed

- Radial labels now have opaque high-contrast capsules, larger type and more
  room. All four actions fit without overlapping at monitor corners and on small
  work areas. The menu no longer immediately dismisses if Windows refuses focus.
- Long companion names no longer push native chat controls out of the header.
  Resizing native cards replaces their background polygon instead of accumulating
  old borders. Bubbles preserve C#, multiplication and inline code when removing
  Markdown formatting.
- Failed conversation switches restore the selected chat and unsent media.
  Retrying an older answer cannot overwrite a new voice/image draft. Deleting an
  active conversation clears its pending media after the save succeeds.
- Cancelled requests recheck cancellation after credential refresh, preventing
  an upload after the user stopped while authentication was pending.
- Recording can always be stopped, including during another action. Send checks
  recording state again after screen capture, closing the record/send race.
  Unplug/stop failures preserve captured audio where possible and release devices.
- Launching a second instance signals a real workspace restore through the
  existing controller, instead of exposing a still-frozen browser window.
- Custom Autopilot intervals survive opening/saving Settings. Motion honors
  reduced-motion preferences; recording timers do not flood live announcements.

## Added

- Four radial actions: Chat, Capture, Workspace/Overlay and Voice. Record controls
  also live in the full/compact composer and native chat input; Alt Shift V works
  globally. Voice recording has explicit start/stop, a level meter, review,
  playback, discard, a 120-second cap and no automatic upload.
- A transcript is saved in the conversation. The selected Gemini model also
  hears the audio while answering. Combined audio/image uploads are bounded to
  18 MiB. Raw clips stay in RAM, not exported chat or audio files.
- Optional local Windows speech replies to voice messages, Listen on written
  replies, and Mute. Starting another recording stops speech to avoid feedback.
- Dialog/view entrance motion, hover lift, press feedback, toast arrivals and an
  active-recording pulse. No extra always-running visual effects were added.
- Vertex AI authentication through local ADC, expected-account checks, project /
  location settings and a connection test. API-key Gemini remains available.
- Default Gemini 3.8 Flash; presets for Gemini 3.5 Flash-Lite and Gemini 4 Argon.

## Verification

- 72 offline unit tests; real WebView2 and native Tk/Windows integration checks.
  Recording UI checks use synthetic clips and never open the microphone.
- Live Google Cloud checks verified sobiisupforai@gmail.com and the existing
  project **On Sundays**, ID `gen-lang-client-0100408368`. Billing and the Vertex AI
  API were already enabled. All three model IDs passed `countTokens` checks.
- The standalone 25.9 MB build passed real ADC authentication, connection testing,
  a live Gemini 3.8 Flash reply, native quick reply, full/compact/orb transitions,
  and restoring a docked instance by launching it again. Bundled PortAudio and
  credential metadata were checked. The normal workspace is configured for that
  account/project with Gemini 3.8 Flash; its prior chats and companions remain.
- The final connection was saved and tested through the running executable's own
  bridge, then verified in its actual AppData file. Microsoft Store Python's
  source profile is redirected into its package cache; that Windows behavior is
  documented instead of assuming both profiles share a physical settings file.
- A real Gemini 3.8 Flash integration check transcribed Windows-generated speech
  and streamed its reply. No personal voice or screen data was used. The command
  is explicit and billable, excluded from the offline suite:
  `.venv\Scripts\python.exe -B tests\smoke_vertex_live.py --project PROJECT_ID --account EMAIL`
- Physical microphone acoustics, output-device quality, exclusive-fullscreen
  games and multi-DPI monitor arrangements still need real-use validation.

## Compact menu and exit follow-up

- Context/mode menus retain their Tk commands after posting and defer actions
  until menu selection completes. Context menus explicitly focus their owner.
- Quit requests the saved-exit controller directly, including when the browser is
  hidden/frozen. Save failure restores the workspace instead of silently exiting.
- The orb is 48px; radial canvases are 64×60 with 36px circles and tighter spacing.
  Close uses a 128ms retract/fade. Quick reopen cancels leftover closing surfaces;
  capture/hide/quit removes them immediately so they cannot leak into screenshots.
- Hide Cutex removes all surfaces, pauses check-ins and mutes speech. Alt Shift H
  toggles visibility; Alt X also restores a fully hidden orb. Voice drafts survive.
- Native integration exercises retained menu commands, mode selection, Hide,
  shortcut restore, close animation/reopen and Quit. The mixed WebView2/Tk check
  invokes the actual menu command while the workspace is docked, and verifies
  that both native UI and browser close cleanly.
- The rebuilt executable passes full Hide, Alt X restore-to-orb, hide/show toggle,
  quick reply from hidden mode and saved Quit while docked in an isolated profile.
  These checks make no model or microphone calls. Existing Vertex settings remain.
