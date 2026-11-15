#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import os
import re
import subprocess
import threading

import indigo

APP_NAME = "Airfoil Satellite"
PLUGIN_VERSION = "0.1.7"


def _now_string():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _duration_text(seconds):
    try:
        seconds = int(seconds)
    except Exception:
        seconds = 0
    if seconds <= 0:
        return ""
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def _safe_filename(text):
    text = text or "artwork"
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text).strip(" ._")
    return text[:80] or "artwork"


def _truthy(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Plugin(indigo.PluginBase):
    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)
        self._stop_event = threading.Event()
        self._last_snapshots = {}
        self._pending_metadata = {}

    def startup(self):
        self._configure_logging()
        self.logger.info("Airfoil Satellite plugin startup v%s", PLUGIN_VERSION)

    def shutdown(self):
        self.logger.info("Airfoil Satellite plugin shutdown")
        self._stop_event.set()

    def closedPrefsConfigUi(self, values_dict, user_cancelled):
        if not user_cancelled:
            self.pluginPrefs.update(values_dict)
            self._configure_logging()
        return True

    def _configure_logging(self):
        log_level = self.pluginPrefs.get("logLevel", "info")
        self.logger.setLevel(logging.DEBUG if log_level == "debug" else logging.INFO)

    def deviceStartComm(self, dev):
        self.logger.info("Starting Airfoil Satellite monitor: %s", dev.name)
        self._last_snapshots.pop(dev.id, None)
        self._pending_metadata.pop(dev.id, None)
        self._update_device(dev, force=True)

    def deviceStopComm(self, dev):
        self.logger.info("Stopping Airfoil Satellite monitor: %s", dev.name)
        self._last_snapshots.pop(dev.id, None)
        self._pending_metadata.pop(dev.id, None)

    def runConcurrentThread(self):
        try:
            while not self._stop_event.is_set():
                poll_seconds = self._get_min_poll_seconds()
                for dev in indigo.devices.iter("self.airfoilSatelliteMonitor"):
                    if dev.enabled:
                        self._update_device(dev)
                self.sleep(max(1, poll_seconds))
        except self.StopThread:
            pass

    def _get_min_poll_seconds(self):
        seconds = 5
        for dev in indigo.devices.iter("self.airfoilSatelliteMonitor"):
            try:
                val = int(dev.pluginProps.get("updateFrequency", 5))
                if val > 0:
                    seconds = min(seconds, val)
            except Exception:
                pass
        return seconds

    def _run_osascript(self, script, timeout=8):
        cmd = ["/usr/bin/osascript", "-e", script]
        self.logger.debug("Running AppleScript: %s", script)
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "AppleScript returned an error").strip()
            raise RuntimeError(err)
        return (proc.stdout or "").rstrip("\n")

    def _get_raw_airfoil_snapshot(self):
        script = f'''
            tell application "{APP_NAME}"
                set c to (is connected as text)
                set a to artist
                set al to album
                set t to track title
                return c & linefeed & a & linefeed & al & linefeed & t
            end tell
        '''
        output = self._run_osascript(script)
        lines = output.splitlines()
        while len(lines) < 4:
            lines.append("")

        connected = lines[0].strip().lower() == "true"
        artist = lines[1].strip()
        album = lines[2].strip()
        track_title = lines[3].strip()
        # Do not check the artwork property during normal polling.
        # Some Airfoil streams can block AppleScript while artwork data is being marshalled.
        artwork_available = False
        now_playing = self._format_now_playing(artist, track_title)
        streaming = bool(connected and (artist or album or track_title))
        display_state = now_playing if streaming else ("Connected" if connected else "Stopped")

        return {
            "connected": connected,
            "streaming": streaming,
            "artist": artist,
            "album": album,
            "trackTitle": track_title,
            "nowPlaying": now_playing,
            "displayState": display_state,
            "artworkAvailable": artwork_available,
            "lastError": "",
        }

    def _format_now_playing(self, artist, track_title):
        if artist and track_title:
            return f"{artist} - {track_title}"
        if track_title:
            return track_title
        if artist:
            return artist
        return ""

    def _debounce_metadata(self, dev, raw_snapshot, force=False):
        """Delay metadata changes until stable for the configured debounce period."""
        try:
            debounce_seconds = int(dev.pluginProps.get("metadataDebounceSeconds", 0) or 0)
        except Exception:
            debounce_seconds = 0
        if force or debounce_seconds <= 0:
            self._pending_metadata.pop(dev.id, None)
            return raw_snapshot

        previous = self._last_snapshots.get(dev.id, {})
        metadata_keys = ("artist", "album", "trackTitle", "nowPlaying", "artworkAvailable")
        old_tuple = tuple(previous.get(k, "") for k in metadata_keys)
        new_tuple = tuple(raw_snapshot.get(k, "") for k in metadata_keys)

        if not previous or old_tuple == new_tuple:
            self._pending_metadata.pop(dev.id, None)
            return raw_snapshot

        pending = self._pending_metadata.get(dev.id)
        now_dt = datetime.datetime.now()
        if not pending or pending.get("tuple") != new_tuple:
            self._pending_metadata[dev.id] = {"tuple": new_tuple, "snapshot": raw_snapshot.copy(), "firstSeen": now_dt}
            debounced = raw_snapshot.copy()
            for k in metadata_keys:
                debounced[k] = previous.get(k, "")
            debounced["displayState"] = previous.get("displayState", raw_snapshot.get("displayState", ""))
            return debounced

        elapsed = (now_dt - pending["firstSeen"]).total_seconds()
        if elapsed >= debounce_seconds:
            self._pending_metadata.pop(dev.id, None)
            return raw_snapshot

        debounced = raw_snapshot.copy()
        for k in metadata_keys:
            debounced[k] = previous.get(k, "")
        debounced["displayState"] = previous.get("displayState", raw_snapshot.get("displayState", ""))
        return debounced

    def _update_device(self, dev, force=False):
        try:
            raw_snapshot = self._get_raw_airfoil_snapshot()
            snapshot = self._debounce_metadata(dev, raw_snapshot, force=force)
            previous = self._last_snapshots.get(dev.id, {})
            now = _now_string()
            now_dt = datetime.datetime.now()

            connected_changed = force or previous.get("connected") != snapshot["connected"]
            streaming_changed = force or previous.get("streaming") != snapshot["streaming"]

            if connected_changed:
                snapshot["lastConnectedChange"] = now
                snapshot["connectedSince"] = now if snapshot["connected"] else ""
                if snapshot["connected"]:
                    snapshot["lastConnectedStarted"] = now
                    snapshot["lastConnectedStopped"] = dev.states.get("lastConnectedStopped", "")
                else:
                    snapshot["lastConnectedStarted"] = dev.states.get("lastConnectedStarted", "")
                    snapshot["lastConnectedStopped"] = now
                if not force:
                    self.logger.info("%s Airfoil Satellite %s", dev.name, "connected" if snapshot["connected"] else "disconnected")
            else:
                snapshot["lastConnectedChange"] = dev.states.get("lastConnectedChange", "")
                snapshot["connectedSince"] = dev.states.get("connectedSince", "") if snapshot["connected"] else ""
                snapshot["lastConnectedStarted"] = dev.states.get("lastConnectedStarted", "")
                snapshot["lastConnectedStopped"] = dev.states.get("lastConnectedStopped", "")

            if streaming_changed:
                snapshot["lastStreamingChange"] = now
                snapshot["streamingSince"] = now if snapshot["streaming"] else ""
                if snapshot["streaming"]:
                    snapshot["lastStreamingStarted"] = now
                    snapshot["lastStreamingStopped"] = dev.states.get("lastStreamingStopped", "")
                    if not force:
                        snapshot["streamingStartCounter"] = int(dev.states.get("streamingStartCounter", 0) or 0) + 1
                        snapshot["streamingStopCounter"] = int(dev.states.get("streamingStopCounter", 0) or 0)
                        self.logger.info("%s Airfoil streaming started", dev.name)
                    else:
                        snapshot["streamingStartCounter"] = int(dev.states.get("streamingStartCounter", 0) or 0)
                        snapshot["streamingStopCounter"] = int(dev.states.get("streamingStopCounter", 0) or 0)
                else:
                    snapshot["lastStreamingStarted"] = dev.states.get("lastStreamingStarted", "")
                    snapshot["lastStreamingStopped"] = now
                    if not force:
                        snapshot["streamingStartCounter"] = int(dev.states.get("streamingStartCounter", 0) or 0)
                        snapshot["streamingStopCounter"] = int(dev.states.get("streamingStopCounter", 0) or 0) + 1
                        self.logger.info("%s Airfoil streaming stopped", dev.name)
                    else:
                        snapshot["streamingStartCounter"] = int(dev.states.get("streamingStartCounter", 0) or 0)
                        snapshot["streamingStopCounter"] = int(dev.states.get("streamingStopCounter", 0) or 0)
            else:
                snapshot["lastStreamingChange"] = dev.states.get("lastStreamingChange", "")
                snapshot["streamingSince"] = dev.states.get("streamingSince", "") if snapshot["streaming"] else ""
                snapshot["lastStreamingStarted"] = dev.states.get("lastStreamingStarted", "")
                snapshot["lastStreamingStopped"] = dev.states.get("lastStreamingStopped", "")
                snapshot["streamingStartCounter"] = int(dev.states.get("streamingStartCounter", 0) or 0)
                snapshot["streamingStopCounter"] = int(dev.states.get("streamingStopCounter", 0) or 0)

            metadata_keys = ("artist", "album", "trackTitle", "nowPlaying")
            metadata_changed = any(previous.get(k) != snapshot.get(k) for k in metadata_keys)
            if force or metadata_changed:
                snapshot["lastMetadataChange"] = now
                snapshot["lastMetadataUpdate"] = now
                old_counter = int(dev.states.get("metadataChangeCounter", 0) or 0)
                snapshot["metadataChangeCounter"] = old_counter if force else old_counter + 1
                if snapshot["nowPlaying"]:
                    self.logger.info("%s now playing: %s", dev.name, snapshot["nowPlaying"])
            else:
                snapshot["lastMetadataChange"] = dev.states.get("lastMetadataChange", "")
                snapshot["lastMetadataUpdate"] = dev.states.get("lastMetadataUpdate", "")
                snapshot["metadataChangeCounter"] = int(dev.states.get("metadataChangeCounter", 0) or 0)

            connected_since = _parse_time(snapshot.get("connectedSince"))
            streaming_since = _parse_time(snapshot.get("streamingSince"))
            connected_seconds = int((now_dt - connected_since).total_seconds()) if connected_since else 0
            streaming_seconds = int((now_dt - streaming_since).total_seconds()) if streaming_since else 0
            snapshot["connectionDurationSeconds"] = connected_seconds
            snapshot["connectionDuration"] = _duration_text(connected_seconds)
            snapshot["streamingDurationSeconds"] = streaming_seconds
            snapshot["streamingDuration"] = _duration_text(streaming_seconds)

            snapshot.update(self._match_states(dev, snapshot))

            # Artwork is intentionally not probed during normal polling because Airfoil can block
            # while returning large TIFF artwork data. Use the Refresh / Save Artwork action manually.
            snapshot["artworkAvailable"] = bool(dev.states.get("artworkAvailable", False))
            snapshot["artworkPath"] = dev.states.get("artworkPath", "")

            # Keep Indigo quiet if requested. Duration counters are the only values that normally churn every poll.
            update_durations = _truthy(dev.pluginProps.get("updateDurationEveryPoll", False), default=False)
            only_on_change = _truthy(dev.pluginProps.get("onlyUpdateOnChange", True), default=True)
            if only_on_change and not force and not update_durations:
                if not (connected_changed or streaming_changed or metadata_changed):
                    for key in ("connectionDuration", "connectionDurationSeconds", "streamingDuration", "streamingDurationSeconds"):
                        snapshot[key] = dev.states.get(key, snapshot.get(key))

            self._apply_states(dev, snapshot)
            self._update_state_image(dev, snapshot)
            self._last_snapshots[dev.id] = snapshot.copy()
            self._update_variables(dev, snapshot)
        except Exception as exc:
            msg = str(exc)
            self.logger.error("Error polling Airfoil Satellite for %s: %s", dev.name, msg)
            self._apply_states(dev, {
                "lastError": msg,
                "displayState": "Error",
            })

    def _match_states(self, dev, snapshot):
        props = dev.pluginProps

        def contains(field_id, value):
            needle = (props.get(field_id, "") or "").strip().lower()
            if not needle:
                return False
            return needle in (value or "").lower()

        return {
            "artistMatch": contains("artistContains", snapshot.get("artist", "")),
            "albumMatch": contains("albumContains", snapshot.get("album", "")),
            "trackMatch": contains("trackContains", snapshot.get("trackTitle", "")),
            "nowPlayingMatch": contains("nowPlayingContains", snapshot.get("nowPlaying", "")),
        }

    def _artwork_dir(self):
        path = os.path.join(indigo.server.getInstallFolderPath(), "Preferences", "Plugins", "AirfoilSatellite", "Artwork")
        os.makedirs(path, exist_ok=True)
        return path

    def _save_artwork(self, dev, snapshot):
        filename = _safe_filename(snapshot.get("nowPlaying") or dev.name) + ".tiff"
        path = os.path.join(self._artwork_dir(), filename)
        escaped = path.replace('\\', '\\\\').replace('"', '\\"')
        script = f'''
            tell application "{APP_NAME}"
                if artwork is missing value then return ""
                set artData to artwork
            end tell
            set outFile to POSIX file "{escaped}"
            try
                set fileRef to open for access outFile with write permission
                set eof fileRef to 0
                write artData to fileRef
                close access fileRef
                return POSIX path of outFile
            on error errMsg
                try
                    close access outFile
                end try
                error errMsg
            end try
        '''
        try:
            return self._run_osascript(script, timeout=10).strip()
        except Exception as exc:
            self.logger.debug("Could not save Airfoil artwork: %s", exc)
            return dev.states.get("artworkPath", "")

    def _apply_states(self, dev, snapshot):
        states = []
        for key, value in snapshot.items():
            if key in dev.states and dev.states.get(key) != value:
                states.append({"key": key, "value": value})
        if states:
            dev.updateStatesOnServer(states)

    def _update_state_image(self, dev, snapshot):
        if not dev.pluginProps.get("useStateImages", True):
            return
        try:
            if snapshot.get("streaming"):
                dev.updateStateImageOnServer(indigo.kStateImageSel.AvPlaying)
            elif snapshot.get("connected"):
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
            else:
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
        except Exception:
            try:
                dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn if snapshot.get("connected") else indigo.kStateImageSel.PowerOff)
            except Exception as exc:
                self.logger.debug("State image update skipped: %s", exc)

    def _update_variables(self, dev, snapshot):
        if not dev.pluginProps.get("updateVariables", False):
            return
        prefix = dev.pluginProps.get("variablePrefix", "AirfoilSatellite") or "AirfoilSatellite"
        mapping = {
            f"{prefix}Connected": str(snapshot.get("connected", False)),
            f"{prefix}Streaming": str(snapshot.get("streaming", False)),
            f"{prefix}Artist": snapshot.get("artist", ""),
            f"{prefix}Album": snapshot.get("album", ""),
            f"{prefix}TrackTitle": snapshot.get("trackTitle", ""),
            f"{prefix}NowPlaying": snapshot.get("nowPlaying", ""),
            f"{prefix}ConnectionDuration": snapshot.get("connectionDuration", ""),
            f"{prefix}StreamingDuration": snapshot.get("streamingDuration", ""),
            f"{prefix}ArtworkPath": snapshot.get("artworkPath", ""),
        }
        for name, value in mapping.items():
            try:
                if name in indigo.variables:
                    indigo.variable.updateValue(name, str(value))
                else:
                    indigo.variable.create(name, value=str(value))
            except Exception as exc:
                self.logger.debug("Could not update variable %s: %s", name, exc)

    def actionRefreshStatus(self, plugin_action, dev):
        self._update_device(dev, force=True)

    def actionRefreshArtwork(self, plugin_action, dev):
        snapshot = self._get_raw_airfoil_snapshot()
        path = self._save_artwork(dev, snapshot)
        states = {"artworkAvailable": bool(path), "artworkPath": path}
        dev.updateStatesOnServer([{"key": k, "value": v} for k, v in states.items()])
        self.logger.info("%s artwork %s", dev.name, "saved" if path else "not available")

    def actionPlayPause(self, plugin_action, dev):
        self._run_transport_command("playpause", dev)

    def actionNextTrack(self, plugin_action, dev):
        self._run_transport_command("next", dev)

    def actionPreviousTrack(self, plugin_action, dev):
        self._run_transport_command("previous", dev)

    def actionLaunchSatellite(self, plugin_action, dev):
        self._run_osascript(f'tell application "{APP_NAME}" to activate')
        self._update_device(dev, force=True)

    def actionQuitSatellite(self, plugin_action, dev):
        self._run_osascript(f'tell application "{APP_NAME}" to quit')
        self._update_device(dev, force=True)

    def _run_transport_command(self, command, dev):
        try:
            self._run_osascript(f'tell application "{APP_NAME}" to {command}')
            self.logger.info("Sent Airfoil Satellite command: %s", command)
            self._update_device(dev, force=True)
        except Exception as exc:
            self.logger.error("Airfoil Satellite command failed: %s", exc)
            raise
