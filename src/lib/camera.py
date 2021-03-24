#!/usr/bin/env python3

import asyncio
from .helpers import unasyncio
from .webrtc import WebRTC
import websockets
import json
import threading
import time
import logging
log = logging.getLogger('bbb-streamer')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

Gst.init(None)

class CameraManager(object):
    def __init__(self, sessionmanager, streammixer):
        self.cameras = {}

        self.sessionmanager = sessionmanager
        self.sessionmanager.attach(self.listener)

        self.streammixer = streammixer
        self.active_camera = None
        self.active_speakers = {}
        self.voice_users = {}

    def remove(self, msgid):
        if msgid in self.cameras:
            self.cameras[msgid].stop()
            self.cameras[msgid].join()
            del self.cameras[msgid]

    def add(self, msgid, fields):
        self.cameras[msgid] = Camera(self.sessionmanager, fields, self)

    def new_sample(self, stype, camera, sample):
        if self.active_camera is None:
            log.debug("Switching active camera to %s" % camera.fields['userId'])
            self.active_camera = camera.fields['userId']

        if camera.fields['userId'] == self.active_camera:
            self.streammixer.new_sample(stype, camera, sample)

    def listener(self, msg):
        if 'collection' not in msg:
            return

        if msg['collection'] == 'video-streams':
            if msg['msg'] == 'removed':
                self.remove(msg['id'])
            elif msg['msg'] == 'added':
                self.add(msg['id'], msg['fields'])
        elif msg['collection'] == 'voiceUsers':
            if msg['msg'] == 'added':
                self.voice_users[msg['id']] = msg['fields']
            elif msg['msg'] == 'removed':
                del self.voice_users[msg['id']]
                return
            elif msg['msg'] == 'changed':
                self.voice_users[msg['id']].update(msg['fields'])

            talking = self.voice_users[msg['id']]['talking']
            userid = self.voice_users[msg['id']]['voiceUserId']

            if talking and userid not in self.active_speakers:
                self.active_speakers[userid] = time.time()
            elif not talking and userid in self.active_speakers:
                del self.active_speakers[userid]

            if self.active_speakers:
                for userid, _ in sorted(self.active_speakers.items(), key=lambda x: x[1]):
                    for camera in self.cameras.values():
                        if camera.fields['userId'] == userid:
                            log.debug("Switching active camera to %s" % userid)
                            self.active_camera = userid
                            return

class Camera(WebRTC):
    def __init__(self, sessionmanager, fields, cameramanager):
        log.debug("Initializing new camera connection")
        self.stype = 'video'
        self.cameramanager = cameramanager
        self.appsink = None
        self.sessionmanager = sessionmanager
        self.fields = fields
        WebRTC.__init__(self)

    def new_sample(self, sink, data):
        sample = self.appsink.emit("pull-sample")
        self.cameramanager.new_sample(self.stype, self, sample)
        return Gst.FlowReturn.OK

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        log.debug("Connecting to bbb-webrtc-sfu")
        server = self.sessionmanager.bbb_server.replace('https', 'wss') + '/bbb-webrtc-sfu?sessionToken=' + self.sessionmanager.bbb_token
        self.conn = unasyncio(websockets.connect(server))

        pipeline = "webrtcbin name=recvonly bundle-policy=max-bundle stun-server=stun://%s" % self.sessionmanager.stun_server
        pipeline += " ! rtpvp8depay"
        pipeline += " ! queue"
        pipeline += " ! vp8dec"
        pipeline += " ! videorate"
        pipeline += " ! videoconvert"
        pipeline += " ! video/x-raw,format=RGBA,framerate=25/1,pixel-aspect-ratio=1/1"
        pipeline += " ! queue"
        pipeline += " ! appsink name=output emit-signals=true drop=false sync=true"

        log.debug("Starting camera webrtc pipeline")
        self.pipe = Gst.parse_launch(pipeline)
        self.webrtc = self.pipe.get_by_name('recvonly')
        self.appsink = self.pipe.get_by_name('output')
        self.appsink.connect("new-sample", self.new_sample, self.appsink)

        direction = GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY
        caps = Gst.caps_from_string("application/x-rtp,media=video,encoding-name=vp8,clock-rate=90000,ssrc=1,payload=98,fec-type=ulp-red,do-nack=true")
        self.webrtc.emit('add-transceiver', direction, caps)

        self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)
        self.webrtc.connect('pad-added', self.on_incoming_stream)

        self.pipe.set_state(Gst.State.PLAYING)

        while self.running:
            msg = self.recv()
            if msg is None:
                continue
            self.handle_sdp(msg)

        self.pipe.set_state(Gst.State.NULL)
        self.loop.stop()
        self.loop.close()

    def send_sdp_offer(self, offer):
        log.info('Sending offer for camera %s' % self.fields['stream'])
        msg = {}
        msg['id'] = 'start'
        msg['type'] = 'video'
        msg['role'] = 'viewer'
        msg['internalMeetingId'] = self.sessionmanager.bbb_info['meetingID']
        msg['meetingId'] = msg['internalMeetingId']
        msg['voiceBridge'] = self.sessionmanager.bbb_info['voicebridge']
        msg['cameraId'] = self.fields['stream']

        # no idea why this has to be here
        msg['bitrate'] = 10000 # should be unlimited on server-side as viewer anyway
        msg['record'] = True
        msg['userId'] = self.sessionmanager.bbb_info['internalUserID']
        msg['userName'] = self.sessionmanager.bbb_info['fullname']

        # fix gst codec parameters
        sdpoffer = ""
        for line in offer.sdp.as_text().splitlines():
            if line.startswith("a=rtpmap:98 vp8/"):
                line = "a=rtpmap:98 vp8/90000"
            sdpoffer += line
            sdpoffer += "\r\n"

        if 'a=mid:video0' not in sdpoffer:
            sdpoffer += "a=mid:video0\r\n"

        msg['sdpOffer'] = sdpoffer.strip()

        log.debug("Sending camera SDP offer: %r" % msg['sdpOffer'])

        self.send(msg)

