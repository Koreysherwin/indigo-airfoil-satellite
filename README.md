# Airfoil Satellite Indigo Plugin

Monitors Rogue Amoeba Airfoil Satellite from Indigo using Airfoil Satellite's AppleScript dictionary.

## Requirements

- Indigo 2025.1 or newer
- Python 3 Indigo plugin runtime
- Airfoil Satellite 5.x installed in `/Applications`

## Device

Create one **Airfoil Satellite Monitor** device.

The device exposes:

- Connected
- Streaming
- Artist
- Album
- Track Title
- Now Playing
- Artwork Available
- Artwork Path
- Connection Duration
- Streaming Duration
- Last Connected Started/Stopped
- Last Streaming Started/Stopped
- Streaming Start/Stop Counters
- Metadata Change Counter
- Artist/Album/Track/Now Playing Match states

The Indigo device list State column follows the `displayState` state and will show now-playing text while streaming.

## Actions

- Refresh Status
- Refresh / Save Artwork
- Play/Pause
- Next Track
- Previous Track
- Launch Airfoil Satellite
- Quit Airfoil Satellite

## Recommended trigger states

For Indigo triggers, use normal device-state triggers on these states:

- `streaming` turns on/off
- `connected` turns on/off
- `streamingStartCounter` changes
- `streamingStopCounter` changes
- `metadataChangeCounter` changes
- `trackMatch`, `artistMatch`, `albumMatch`, or `nowPlayingMatch` turns on

## Low-chatter settings

Version 0.1.7 defaults to reduced Indigo state chatter:

- **Only Update Indigo on Change** is enabled by default.
- **Update Durations Every Poll** is disabled by default.
- **Metadata Debounce** defaults to 2 seconds.

Enable live duration updates only if you want the duration counters to tick in real time.


## v0.1.7 note

This release restores the Indigo-compatible `UiDisplayStateId` declaration so the device list State column follows the plugin `displayState` value.


## 0.1.7 Notes

Metadata returned by Airfoil Satellite is decoded as UTF-8 so accented artist, album, or track names do not stop polling.
