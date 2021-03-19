#!/usr/bin/env python3

import requests
import secrets
import websockets
import asyncio
import json
import threading
import time
import cmd
import sys
from .helpers import unasyncio

class SessionManager(threading.Thread):
    def __init__(self, join_url):
        self.listeners = []
        self.join_url = join_url
        self.running = True
        self.ready = False
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

    def join(self, join_url):
        tmpsession = requests.session()
        req = tmpsession.get(join_url, allow_redirects=False)

        self.bbb_server = '/'.join(req.headers['Location'].split('/')[:3])
        self.bbb_token = req.headers['Location'].split('?sessionToken=')[1]
        self.bbb_info = json.loads(tmpsession.get(self.bbb_server + "/bigbluebutton/api/enter?sessionToken=" + self.bbb_token).text)["response"]
        self.bbb_stuns = json.loads(tmpsession.get(self.bbb_server + "/bigbluebutton/api/stuns?sessionToken=" + self.bbb_token).text)

        self.stun_server = self.bbb_stuns['stunServers'][0]['url']
        if self.stun_server.startswith('stun:') or self.stun_server.startswith('stuns:'):
            self.stun_server = self.stun_server.split(':')[1]
        else:
            self.stun_server = self.stun_server.split(':')[0]

    def connect(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.websocket = unasyncio(websockets.connect(self.bbb_server.replace("https", "wss") + "/html5client/sockjs/494/" + secrets.token_urlsafe(8) + "/websocket"))

        _ = self.recv()
        _ = self.recv()
        self.send({'msg': 'connect', 'version': '1', 'support': ['1', 'pre1', 'pre2']})
        self.send({'msg': 'method', 'method': 'userChangedLocalSettings', 'params': [{'application': {'animations': True, 'chatAudioAlerts': False, 'chatPushAlerts': False, 'fallbackLocale': 'en', 'overrideLocale': None, 'userJoinAudioAlerts': False, 'userJoinPushAlerts': False, 'locale': 'en-US'}, 'audio': {'inputDeviceId': 'undefined', 'outputDeviceId': 'undefined'}, 'dataSaving': {'viewParticipantsWebcams': True, 'viewScreenshare': True}}], 'id': '1'})
        self.send({'msg': 'method', 'method': 'validateAuthToken', 'params': [self.bbb_info['meetingID'], self.bbb_info['internalUserID'], self.bbb_info['authToken'], self.bbb_info['externUserID']], 'id': '2'})

        #for sub in ['annotations', 'breakouts', 'captions', 'current-user', 'group-chat', 'group-chat-msg', 'guestUser', 'local-settings', 'meetings', 'meetings', 'meeting-time-remaining', 'meteor_autoupdate_clientVersions', 'network-information', 'note', 'ping-pong', 'polls', 'presentation-pods', 'presentations', 'record-meetings', 'screenshare', 'slide-positions', 'slides', 'users', 'users', 'users-infos', 'users-settings', 'video-streams', 'voice-call-states', 'voiceUsers', 'whiteboard-multi-user']:
        for sub in ['annotations', 'current-user', 'group-chat', 'group-chat-msg', 'guestUser', 'local-settings', 'meetings', 'network-information', 'note', 'ping-pong', 'presentations', 'screenshare', 'slide-positions', 'slides', 'users', 'users-infos', 'video-streams', 'voice-call-states', 'voiceUsers']:
            self.send({'msg': 'sub', 'id': 'fnord-' + sub, 'name': sub, 'params': []})

    def attach(self, listener):
        if listener not in self.listeners:
            self.listeners.append(listener)

    def detach(self, listener):
        if listener in self.listeners:
            self.listeners.remove(listener)

    def run(self):
        self.join(self.join_url)
        self.connect()
        while self.running:
            msg = self.recv()

            if not self.ready and msg['msg'] == 'ready':
                self.ready = True

            for listener in self.listeners:
                listener(msg)

            if msg['msg'] == 'ping':
                self.send({'msg': 'pong'})

    def recv(self):
        raw = unasyncio(self.websocket.recv())
        if raw.startswith('a['):
            return json.loads(json.loads(raw[1:])[0])
        else:
            return raw

    def send(self, msg):
        raw = unasyncio(self.websocket.send(json.dumps([json.dumps(msg)])))
