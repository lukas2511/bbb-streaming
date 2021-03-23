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
import logging
log = logging.getLogger('bbb-streamer')

class SessionManager(threading.Thread):
    def __init__(self, join_url):
        self.listeners = []
        self.join_url = join_url
        self.running = True
        self.ready = False
        threading.Thread.__init__(self)
        self.daemon = True

        self.users = {}

        self.start()

    def get_user_by_internal_id(self, userid):
        for user in self.users.values():
            if user['userId'] == userid:
                return user
        return None

    def join(self, join_url):
        tmpsession = requests.session()
        req = tmpsession.get(join_url, allow_redirects=False)

        log.debug("Got join url: %s?..." % join_url.split("?")[0])

        self.bbb_server = '/'.join(req.headers['Location'].split('/')[:3])
        self.bbb_token = req.headers['Location'].split('?sessionToken=')[1]
        self.bbb_info = json.loads(tmpsession.get(self.bbb_server + "/bigbluebutton/api/enter?sessionToken=" + self.bbb_token).text)["response"]
        self.bbb_stuns = json.loads(tmpsession.get(self.bbb_server + "/bigbluebutton/api/stuns?sessionToken=" + self.bbb_token).text)

        self.stun_server = self.bbb_stuns['stunServers'][0]['url']
        if self.stun_server.startswith('stun:') or self.stun_server.startswith('stuns:'):
            self.stun_server = self.stun_server.split(':')[1]
        else:
            self.stun_server = self.stun_server.split(':')[0]

        log.info("Found STUN server: %s" % self.stun_server)

    def connect(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        log.debug("Connecting to websocket")
        self.websocket = unasyncio(websockets.connect(self.bbb_server.replace("https", "wss") + "/html5client/sockjs/494/" + secrets.token_urlsafe(8) + "/websocket"))

        _ = self.recv()
        _ = self.recv()
        log.debug("Sending initial control messages")
        self.send({'msg': 'connect', 'version': '1', 'support': ['1', 'pre1', 'pre2']})
        self.send({'msg': 'method', 'method': 'userChangedLocalSettings', 'params': [{'application': {'animations': True, 'chatAudioAlerts': False, 'chatPushAlerts': False, 'fallbackLocale': 'en', 'overrideLocale': None, 'userJoinAudioAlerts': False, 'userJoinPushAlerts': False, 'locale': 'en-US'}, 'audio': {'inputDeviceId': 'undefined', 'outputDeviceId': 'undefined'}, 'dataSaving': {'viewParticipantsWebcams': True, 'viewScreenshare': True}}], 'id': '1'})
        self.send({'msg': 'method', 'method': 'validateAuthToken', 'params': [self.bbb_info['meetingID'], self.bbb_info['internalUserID'], self.bbb_info['authToken'], self.bbb_info['externUserID']], 'id': '2'})

        #for sub in ['annotations', 'breakouts', 'captions', 'current-user', 'group-chat', 'group-chat-msg', 'guestUser', 'local-settings', 'meetings', 'meetings', 'meeting-time-remaining', 'meteor_autoupdate_clientVersions', 'network-information', 'note', 'ping-pong', 'polls', 'presentation-pods', 'presentations', 'record-meetings', 'screenshare', 'slide-positions', 'slides', 'users', 'users', 'users-infos', 'users-settings', 'video-streams', 'voice-call-states', 'voiceUsers', 'whiteboard-multi-user']:
        for sub in ['annotations', 'current-user', 'group-chat', 'group-chat-msg', 'guestUser', 'local-settings', 'meetings', 'network-information', 'note', 'ping-pong', 'presentations', 'screenshare', 'slide-positions', 'slides', 'users', 'users-infos', 'video-streams', 'voice-call-states', 'voiceUsers']:
            log.debug("Subscribing to %s messages" % sub)
            self.send({'msg': 'sub', 'id': 'fnord-' + sub, 'name': sub, 'params': []})

    def attach(self, listener):
        log.debug("Attaching listener to session manager: %r" % listener)
        if listener not in self.listeners:
            self.listeners.append(listener)

    def detach(self, listener):
        log.debug("Detaching listener from session manager: %r" % listener)
        if listener in self.listeners:
            self.listeners.remove(listener)

    def run(self):
        self.join(self.join_url)
        self.connect()
        while self.running:
            msg = self.recv()

            if not self.ready and msg['msg'] == 'ready':
                self.ready = True
                log.debug("Session manager is ready")

            for listener in self.listeners:
                listener(msg)

            if msg['msg'] == 'ping':
                log.debug("Responding to ping")
                self.send({'msg': 'pong'})

            if 'collection' not in msg:
                continue

            if msg['collection'] == 'users':
                if msg['msg'] == 'added':
                    self.users[msg['id']] = msg['fields']
                    self.users[msg['id']]['_id'] = msg['id']
                elif msg['msg'] == 'changed':
                    self.users[msg['id']].update(msg['fields'])

    def recv(self):
        raw = unasyncio(self.websocket.recv())
        if raw.startswith('a['):
            return json.loads(json.loads(raw[1:])[0])
        else:
            return raw

    def send(self, msg):
        raw = unasyncio(self.websocket.send(json.dumps([json.dumps(msg)])))
