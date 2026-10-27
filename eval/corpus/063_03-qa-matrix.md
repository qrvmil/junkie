# QA matrix

## Packaging

- [x] Final executable is Mach-O ARM64.
- [x] Every bundled Mach-O contains ARM64. The six unused x86-only VLC MMX/SSE2 converter variants were removed from staging; architecture-neutral universal equivalents remain.
- [x] Bundle passes ad-hoc `codesign --verify --deep --strict`.
- [ ] Launch works from Finder and from the executable. Direct executable launch succeeds; Finder launch remains to be checked on the packaged copy.

## UI and persistence

- [x] Existing-save cold cache and title screen. A 777-file cache pass completed and transitioned without the previous null-title crash; first-boot warning remains pending.
- [ ] Main menu, story menu, freeplay, gallery, costumes, credits, and every options category.
- [ ] Fonts render as original text, without percent-sign substitutions or missing glyphs.
- [ ] Backgrounds, logical 1280x720 layout, Retina scaling, windowed mode, and fullscreen. Static generation confirms `allowHighDPI: true`; the windowed cold-cache/title screens rendered correctly, while fullscreen and representative gameplay still need visual QA.
- [ ] Clean save, relaunch, and progress persistence without deleting user data.

## Content and native integration

- [ ] Every chart loads through the existing CLI/debug paths.
- [ ] Full botplay traversal and story transitions.
- [ ] MP4 playback, letterboxing, audio sync, completion callbacks, focus loss, and skip behavior. The doubled fullscreen video offset is fixed statically; user visual confirmation is pending. Authored black starts are documented in `07-video-audio-diagnosis.md`.
- [ ] Shaders and representative custom mechanics.
- [ ] OBS-sensitive dialogue, username substitution, DDLC save detection, and Discord Rich Presence.

## User checkpoints

- [x] First playable-build smoke test and latency feedback.
- [ ] Release-candidate representative songs and one continuous story route.
