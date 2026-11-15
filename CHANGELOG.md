# Airfoil Satellite Changelog

## 0.1.7
- Removed artwork availability checks from normal polling to prevent AppleScript timeouts.
- Kept artwork support as a manual Refresh / Save Artwork action.
- Preserved UTF-8 AppleScript output handling from 0.1.6.

## 0.1.5
- Fixed Indigo device list State column by restoring the Indigo-compatible `UiDisplayStateId` XML key for `displayState`.
- No functional changes to Airfoil polling or trigger behavior.

## 0.1.4

- Added low-chatter update mode: only updates Indigo states when something meaningful changes.
- Added optional live duration updates every poll.
- Added metadata debounce setting to avoid transient metadata flicker.
- Added streaming started/stopped timestamp states.
- Added streaming start/stop counters for easy Indigo triggers.
- Added last metadata update state.
- Kept device list State column tied to displayState / now playing.

## 0.1.3

- Updated Indigo device list State column using DisplayStateId/displayState.

## 0.1.2

- Added now playing state.
- Added connection/streaming duration states.
- Added artwork availability/path states and artwork save action.
- Added artist/album/track/now playing match states.
- Added optional Indigo variable updates.
- Added state image support.

## 0.1.1

- Rebuilt with Anthem-style Indigo 2025.x plugin structure.
- Added Python 3 compatible polling/actions.

## 0.1.0

- Initial Airfoil Satellite monitor plugin.
- Added connection, streaming, metadata, and app version states.
- Added actions for refresh, launch, quit, play/pause, next, and previous.

## 0.1.7 - 2026-06-12
- Fixed AppleScript metadata decoding for non-ASCII / accented characters.
- Forces osascript stdout/stderr decoding to UTF-8 with safe replacement to prevent polling errors.
