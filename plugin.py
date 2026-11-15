#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apple Music Control Plugin for Indigo
Provides comprehensive control and monitoring of Apple Music playback
Version 1.0.4 - Fixed streaming radio station support
"""

import indigo
import time
import subprocess
import json
import re

# Constants
kUpdateFrequencyKey = "updateFrequency"


class Plugin(indigo.PluginBase):
    """Main plugin class for Apple Music control"""
    
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.deviceDict = {}
        
    def startup(self):
        """Called when plugin starts"""
        self.debugLog(u"Apple Music Plugin startup called")
        
    def shutdown(self):
        """Called when plugin shuts down"""
        self.debugLog(u"Apple Music Plugin shutdown called")
        
    def deviceStartComm(self, dev):
        """Called when device communication starts"""
        self.debugLog(u"Starting device: " + dev.name)
        
        # Initialize the device's update frequency
        updateFreq = float(dev.pluginProps.get(kUpdateFrequencyKey, 1))
        
        # Store device info
        self.deviceDict[dev.id] = {
            'device': dev,
            'updateFrequency': updateFreq,
            'lastUpdate': 0,
            'previousVolume': None  # For mute/unmute
        }
        
        # Do initial update
        self.updateAppleMusicStatus(dev)
        
    def deviceStopComm(self, dev):
        """Called when device communication stops"""
        self.debugLog(u"Stopping device: " + dev.name)
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]
            
    def runConcurrentThread(self):
        """Main plugin loop - updates device states"""
        try:
            while True:
                currentTime = time.time()
                
                for devId, devInfo in list(self.deviceDict.items()):
                    dev = devInfo['device']
                    updateFreq = devInfo['updateFrequency']
                    lastUpdate = devInfo['lastUpdate']
                    
                    # Check if it's time to update this device
                    if currentTime - lastUpdate >= updateFreq:
                        self.updateAppleMusicStatus(dev)
                        devInfo['lastUpdate'] = currentTime
                
                self.sleep(0.1)  # Short sleep to prevent CPU spinning
                
        except self.StopThread:
            pass
            
    def updateAppleMusicStatus(self, dev):
        """Update all Apple Music status information"""
        try:
            # Build comprehensive AppleScript to get all Apple Music data
            script = '''
            tell application "System Events"
                set musicRunning to (name of processes) contains "Music"
            end tell
            
            if musicRunning then
                tell application "Music"
                    try
                        set playerState to player state as string
                        set soundVol to sound volume
                        set isShuffleEnabled to shuffle enabled
                        set repeatMode to song repeat as string
                        
                        if playerState is not equal to "stopped" then
                            set trackName to name of current track
                            set trackArtist to artist of current track
                            set trackAlbum to album of current track
                            set trackDuration to duration of current track
                            set playerPos to player position
                            set trackNumber to track number of current track
                            set discNumber to disc number of current track
                            set trackGenre to genre of current track
                            set trackComposer to composer of current track
                            set trackRating to rating of current track
                            set trackYear to year of current track
                            set albumArtist to album artist of current track
                            
                            return {playerState:playerState, trackName:trackName, trackArtist:trackArtist, trackAlbum:trackAlbum, trackDuration:trackDuration, playerPosition:playerPos, trackNumber:trackNumber, discNumber:discNumber, genre:trackGenre, composer:trackComposer, rating:trackRating, year:trackYear, albumArtist:albumArtist, soundVolume:soundVol, shuffleEnabled:isShuffleEnabled, songRepeat:repeatMode}
                        else
                            return {playerState:"stopped", trackName:"", trackArtist:"", trackAlbum:"", trackDuration:0, playerPosition:0, trackNumber:0, discNumber:0, genre:"", composer:"", rating:0, year:0, albumArtist:"", soundVolume:soundVol, shuffleEnabled:isShuffleEnabled, songRepeat:repeatMode}
                        end if
                    on error errMsg
                        return {errorMsg:errMsg}
                    end try
                end tell
            else
                return {playerState:"stopped", trackName:"", trackArtist:"", trackAlbum:"", trackDuration:0, playerPosition:0, trackNumber:0, discNumber:0, genre:"", composer:"", rating:0, year:0, albumArtist:"", soundVolume:50, shuffleEnabled:false, songRepeat:"off"}
            end if
            '''
            
            # Execute AppleScript
            result = self.executeAppleScript(script)
            
            if result and 'errorMsg' not in result:
                stateList = []
                
                # Player state
                playerState = result.get('playerState', 'stopped')
                stateList.append({'key': 'playerState', 'value': playerState})
                stateList.append({'key': 'isPlaying', 'value': playerState == 'playing'})
                stateList.append({'key': 'isPaused', 'value': playerState == 'paused'})
                stateList.append({'key': 'isStopped', 'value': playerState == 'stopped'})
                
                # Track information
                trackName = result.get('trackName', '')
                artist = result.get('trackArtist', '')
                album = result.get('trackAlbum', '')
                albumArtist = result.get('albumArtist', '')
                
                stateList.append({'key': 'trackName', 'value': trackName})
                stateList.append({'key': 'artist', 'value': artist})
                stateList.append({'key': 'album', 'value': album})
                stateList.append({'key': 'albumArtist', 'value': albumArtist})
                
                # Track metadata (handle missing values for streaming stations)
                def safe_int(value, default=0):
                    """Safely convert to int, handling 'missing value' from AppleScript"""
                    if value == 'missing value' or value is None or value == '':
                        return default
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return default
                
                stateList.append({'key': 'trackNumber', 'value': safe_int(result.get('trackNumber', 0))})
                stateList.append({'key': 'discNumber', 'value': safe_int(result.get('discNumber', 0))})
                stateList.append({'key': 'genre', 'value': result.get('genre', '')})
                stateList.append({'key': 'composer', 'value': result.get('composer', '')})
                stateList.append({'key': 'rating', 'value': safe_int(result.get('rating', 0))})
                stateList.append({'key': 'year', 'value': safe_int(result.get('year', 0))})
                
                # Duration and position (handle streaming stations that have no duration)
                try:
                    duration_raw = result.get('trackDuration', 0)
                    if duration_raw == 'missing value' or duration_raw is None:
                        duration = 0
                    else:
                        duration = float(duration_raw)
                except (ValueError, TypeError):
                    duration = 0
                
                try:
                    position_raw = result.get('playerPosition', 0)
                    if position_raw == 'missing value' or position_raw is None:
                        position = 0
                    else:
                        position = float(position_raw)
                except (ValueError, TypeError):
                    position = 0
                
                stateList.append({'key': 'duration', 'value': int(duration)})
                stateList.append({'key': 'durationFormatted', 'value': self.formatTime(duration)})
                stateList.append({'key': 'playerPosition', 'value': int(position)})
                stateList.append({'key': 'playerPositionFormatted', 'value': self.formatTime(position)})
                
                # Progress percentage
                progressPercent = 0
                if duration > 0:
                    progressPercent = int((position / duration) * 100)
                stateList.append({'key': 'progressPercent', 'value': progressPercent})
                
                # Volume (protect against missing value)
                volume = safe_int(result.get('soundVolume', 50), 50)
                stateList.append({'key': 'soundVolume', 'value': volume})
                stateList.append({'key': 'muted', 'value': volume == 0})
                
                # Shuffle and repeat
                stateList.append({'key': 'shuffleEnabled', 'value': result.get('shuffleEnabled', False)})
                stateList.append({'key': 'songRepeat', 'value': result.get('songRepeat', 'off')})
                
                # Detect streaming stations (no duration)
                isStreamingStation = (duration == 0)
                
                # Status display
                if playerState == 'playing':
                    statusIcon = u"▶"
                elif playerState == 'paused':
                    statusIcon = u"⏸"
                else:
                    statusIcon = u"⏹"
                
                # Better status for streaming stations
                if trackName and artist:
                    if isStreamingStation:
                        status = u"{} {} - {} [Streaming]".format(statusIcon, artist, trackName)
                    else:
                        status = u"{} {} - {}".format(statusIcon, artist, trackName)
                elif trackName:
                    if isStreamingStation:
                        status = u"{} {} [Streaming]".format(statusIcon, trackName)
                    else:
                        status = u"{} {}".format(statusIcon, trackName)
                else:
                    status = u"{} Not Playing".format(statusIcon)
                
                stateList.append({'key': 'status', 'value': status})
                
                # Update all states at once
                dev.updateStatesOnServer(stateList)
                
                # Update variables if enabled
                if dev.pluginProps.get('updateVariables', False):
                    self.updateVariables(dev, stateList)
                
            else:
                # Error or Music not available
                if result and 'errorMsg' in result:
                    self.errorLog(u"Error getting Apple Music status: {}".format(result['errorMsg']))
                
        except Exception as e:
            self.errorLog(u"Exception in updateAppleMusicStatus: {}".format(str(e)))
            
    def updateVariables(self, dev, stateList):
        """Update Indigo variables with current states"""
        try:
            prefix = dev.pluginProps.get('variablePrefix', 'AppleMusic')
            
            for state in stateList:
                varName = prefix + state['key'][0].upper() + state['key'][1:]
                
                # Create variable if it doesn't exist
                if varName not in indigo.variables:
                    indigo.variable.create(varName, value=str(state['value']), folder=0)
                else:
                    indigo.variable.updateValue(varName, value=str(state['value']))
                    
        except Exception as e:
            self.errorLog(u"Exception in updateVariables: {}".format(str(e)))
            
    def formatTime(self, seconds):
        """Format seconds as MM:SS"""
        try:
            seconds = int(seconds)
            minutes = seconds // 60
            secs = seconds % 60
            return u"{}:{:02d}".format(minutes, secs)
        except:
            return "0:00"
            
    def executeAppleScript(self, script):
        """Execute AppleScript and return result"""
        try:
            process = subprocess.Popen(['osascript', '-e', script],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            output, error = process.communicate()
            
            if error:
                self.errorLog(u"AppleScript error: {}".format(error.decode('utf-8')))
                return None
            
            # Parse the output
            result_str = output.decode('utf-8').strip()
            
            if not result_str:
                return {}
            
            # Parse AppleScript record format
            result = {}
            
            # Remove outer braces
            if result_str.startswith('{') and result_str.endswith('}'):
                result_str = result_str[1:-1]
            
            # Split by comma, but be careful with nested content
            parts = []
            current = ""
            depth = 0
            for char in result_str:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                elif char == ',' and depth == 0:
                    parts.append(current.strip())
                    current = ""
                    continue
                current += char
            if current:
                parts.append(current.strip())
            
            # Parse each key:value pair
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes from strings
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    
                    # Convert to appropriate type
                    if value == 'true':
                        value = True
                    elif value == 'false':
                        value = False
                    elif value.replace('.', '', 1).isdigit():
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    
                    result[key] = value
            
            return result
            
        except Exception as e:
            self.errorLog(u"Exception in executeAppleScript: {}".format(str(e)))
            return None
            
    ########################################
    # Action Handlers
    ########################################
    
    def actionPlay(self, pluginAction, dev):
        """Play action"""
        self.debugLog(u"actionPlay called for device: " + dev.name)
        script = 'tell application "Music" to play'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionPause(self, pluginAction, dev):
        """Pause action"""
        self.debugLog(u"actionPause called for device: " + dev.name)
        script = 'tell application "Music" to pause'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionPlayPause(self, pluginAction, dev):
        """Play/Pause toggle action"""
        self.debugLog(u"actionPlayPause called for device: " + dev.name)
        script = 'tell application "Music" to playpause'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionStop(self, pluginAction, dev):
        """Stop action"""
        self.debugLog(u"actionStop called for device: " + dev.name)
        script = 'tell application "Music" to stop'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionNextTrack(self, pluginAction, dev):
        """Next track action"""
        self.debugLog(u"actionNextTrack called for device: " + dev.name)
        script = 'tell application "Music" to next track'
        self.executeAppleScript(script)
        time.sleep(0.5)  # Give Music time to switch tracks
        self.updateAppleMusicStatus(dev)
        
    def actionPreviousTrack(self, pluginAction, dev):
        """Previous track action"""
        self.debugLog(u"actionPreviousTrack called for device: " + dev.name)
        script = 'tell application "Music" to previous track'
        self.executeAppleScript(script)
        time.sleep(0.5)  # Give Music time to switch tracks
        self.updateAppleMusicStatus(dev)
        
    def actionSetVolume(self, pluginAction, dev):
        """Set volume action"""
        self.debugLog(u"actionSetVolume called for device: " + dev.name)
        volume = int(pluginAction.props.get('volume', 50))
        volume = max(0, min(100, volume))  # Clamp between 0-100
        script = f'tell application "Music" to set sound volume to {volume}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionVolumeUp(self, pluginAction, dev):
        """Volume up action"""
        self.debugLog(u"actionVolumeUp called for device: " + dev.name)
        amount = int(pluginAction.props.get('amount', 10))
        currentVolume = int(dev.states.get('soundVolume', 50))
        newVolume = min(100, currentVolume + amount)
        script = f'tell application "Music" to set sound volume to {newVolume}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionVolumeDown(self, pluginAction, dev):
        """Volume down action"""
        self.debugLog(u"actionVolumeDown called for device: " + dev.name)
        amount = int(pluginAction.props.get('amount', 10))
        currentVolume = int(dev.states.get('soundVolume', 50))
        newVolume = max(0, currentVolume - amount)
        script = f'tell application "Music" to set sound volume to {newVolume}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionMute(self, pluginAction, dev):
        """Mute action"""
        self.debugLog(u"actionMute called for device: " + dev.name)
        devInfo = self.deviceDict.get(dev.id)
        if devInfo:
            # Store current volume
            currentVolume = int(dev.states.get('soundVolume', 50))
            devInfo['previousVolume'] = currentVolume
        script = 'tell application "Music" to set sound volume to 0'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionUnmute(self, pluginAction, dev):
        """Unmute action"""
        self.debugLog(u"actionUnmute called for device: " + dev.name)
        devInfo = self.deviceDict.get(dev.id)
        previousVolume = 50  # Default
        if devInfo and devInfo.get('previousVolume'):
            previousVolume = devInfo['previousVolume']
        script = f'tell application "Music" to set sound volume to {previousVolume}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionSetPosition(self, pluginAction, dev):
        """Set playback position action"""
        self.debugLog(u"actionSetPosition called for device: " + dev.name)
        position = int(pluginAction.props.get('position', 0))
        script = f'tell application "Music" to set player position to {position}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionSkipForward(self, pluginAction, dev):
        """Skip forward action"""
        self.debugLog(u"actionSkipForward called for device: " + dev.name)
        seconds = int(pluginAction.props.get('seconds', 10))
        currentPos = int(dev.states.get('playerPosition', 0))
        newPos = currentPos + seconds
        script = f'tell application "Music" to set player position to {newPos}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionSkipBackward(self, pluginAction, dev):
        """Skip backward action"""
        self.debugLog(u"actionSkipBackward called for device: " + dev.name)
        seconds = int(pluginAction.props.get('seconds', 10))
        currentPos = int(dev.states.get('playerPosition', 0))
        newPos = max(0, currentPos - seconds)
        script = f'tell application "Music" to set player position to {newPos}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionSetShuffle(self, pluginAction, dev):
        """Set shuffle action"""
        self.debugLog(u"actionSetShuffle called for device: " + dev.name)
        shuffleState = pluginAction.props.get('shuffleState', 'toggle')
        
        if shuffleState == 'toggle':
            currentShuffle = dev.states.get('shuffleEnabled', False)
            shuffleState = 'off' if currentShuffle else 'on'
        
        shuffleBool = 'true' if shuffleState == 'on' else 'false'
        script = f'tell application "Music" to set shuffle enabled to {shuffleBool}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionSetRepeat(self, pluginAction, dev):
        """Set repeat action"""
        self.debugLog(u"actionSetRepeat called for device: " + dev.name)
        repeatState = pluginAction.props.get('repeatState', 'toggle')
        
        if repeatState == 'toggle':
            currentRepeat = dev.states.get('songRepeat', 'off')
            if currentRepeat == 'off':
                repeatState = 'all'
            elif currentRepeat == 'all':
                repeatState = 'one'
            else:
                repeatState = 'off'
        
        script = f'tell application "Music" to set song repeat to {repeatState}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionPlayPlaylist(self, pluginAction, dev):
        """Play playlist action"""
        self.debugLog(u"actionPlayPlaylist called for device: " + dev.name)
        playlistName = pluginAction.props.get('playlistName', '')
        if playlistName:
            script = f'''
            tell application "Music"
                try
                    play playlist "{playlistName}"
                on error
                    display dialog "Playlist not found: {playlistName}"
                end try
            end tell
            '''
            self.executeAppleScript(script)
            time.sleep(0.5)
            self.updateAppleMusicStatus(dev)
        
    def actionPlayAlbum(self, pluginAction, dev):
        """Play album action"""
        self.debugLog(u"actionPlayAlbum called for device: " + dev.name)
        albumName = pluginAction.props.get('albumName', '')
        artistName = pluginAction.props.get('artistName', '')
        
        if albumName:
            if artistName:
                script = f'''
                tell application "Music"
                    try
                        set theAlbum to first track of library whose album is "{albumName}" and artist is "{artistName}"
                        play theAlbum
                    on error
                        display dialog "Album not found: {albumName} by {artistName}"
                    end try
                end tell
                '''
            else:
                script = f'''
                tell application "Music"
                    try
                        set theAlbum to first track of library whose album is "{albumName}"
                        play theAlbum
                    on error
                        display dialog "Album not found: {albumName}"
                    end try
                end tell
                '''
            self.executeAppleScript(script)
            time.sleep(0.5)
            self.updateAppleMusicStatus(dev)
        
    def actionSearchAndPlay(self, pluginAction, dev):
        """Search and play action"""
        self.debugLog(u"actionSearchAndPlay called for device: " + dev.name)
        searchQuery = pluginAction.props.get('searchQuery', '')
        if searchQuery:
            script = f'''
            tell application "Music"
                try
                    set searchResults to (search library for "{searchQuery}")
                    if (count of searchResults) > 0 then
                        play item 1 of searchResults
                    else
                        display dialog "No results found for: {searchQuery}"
                    end if
                on error
                    display dialog "Search failed for: {searchQuery}"
                end try
            end tell
            '''
            self.executeAppleScript(script)
            time.sleep(0.5)
            self.updateAppleMusicStatus(dev)
    
    def actionSetRating(self, pluginAction, dev):
        """Set rating action"""
        self.debugLog(u"actionSetRating called for device: " + dev.name)
        rating = int(pluginAction.props.get('rating', 0))
        script = f'tell application "Music" to set rating of current track to {rating}'
        self.executeAppleScript(script)
        self.updateAppleMusicStatus(dev)
        
    def actionUpdateNow(self, pluginAction, dev):
        """Force immediate update"""
        self.debugLog(u"actionUpdateNow called for device: " + dev.name)
        self.updateAppleMusicStatus(dev)
