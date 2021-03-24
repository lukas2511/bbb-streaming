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

PIPELINE_DESC = '''
'''

class ScreenshareManager(object):
    def __init__(self, sessionmanager, switcher):
        self.screenshares = {}

        self.sessionmanager = sessionmanager
        self.sessionmanager.attach(self.listener)
        self.switcher = switcher

    def remove(self, msgid):
        if msgid in self.screenshares:
            self.screenshares[msgid].stop()
            self.screenshares[msgid].join()
            del self.screenshares[msgid]
        self.switcher.screenshare_active = False

    def add(self, msgid, fields):
        for msgid in self.screenshares:
            self.remove(msgid)

        self.screenshares[msgid] = Screenshare(self.sessionmanager, fields, self.switcher)
        self.switcher.screenshare_active = True

    def listener(self, msg):
        if 'collection' not in msg or msg['collection'] != 'screenshare':
            return

        if msg['msg'] == 'removed':
            self.remove(msg['id'])
        elif msg['msg'] == 'added':
            self.add(msg['id'], msg['fields'])

class Screenshare(WebRTC):
    def __init__(self, sessionmanager, fields, streammixer):
        self.stype = "screenshare"
        self.sessionmanager = sessionmanager
        self.streammixer = streammixer
        self.fields = fields
        WebRTC.__init__(self)

    def new_sample(self, sink, data):
        sample = self.appsink.emit("pull-sample")
        self.streammixer.new_sample(self.stype, self, sample)
        return Gst.FlowReturn.OK

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        server = self.sessionmanager.bbb_server.replace('https', 'wss') + '/bbb-webrtc-sfu?sessionToken=' + self.sessionmanager.bbb_token
        self.conn = unasyncio(websockets.connect(server))

        pipeline = "webrtcbin name=recvonly bundle-policy=max-bundle stun-server=stun://%s" % self.sessionmanager.stun_server
        pipeline += " ! rtpvp8depay"
        pipeline += " ! queue"
        pipeline += " ! vp8dec"
        pipeline += " ! videoscale"
        pipeline += " ! videoconvert"
        pipeline += " ! videorate"
        pipeline += " ! video/x-raw,width=1920,height=1080,format=RGBA,framerate=10/1,pixel-aspect-ratio=1/1"
        pipeline += " ! queue"
        pipeline += " ! appsink name=output emit-signals=true drop=false sync=true"

        self.pipe = Gst.parse_launch(pipeline)
        self.webrtc = self.pipe.get_by_name('recvonly')
        self.appsink = self.pipe.get_by_name('output')
        self.appsink.connect("new-sample", self.new_sample, self.appsink)

        direction = GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY
        caps = Gst.caps_from_string("application/x-rtp,media=video,encoding-name=vp8,clock-rate=90000,payload=98,fec-type=ulp-red,do-nack=true")
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
        log.info('Sending offer for screenshare')
        msg = {}
        msg['id'] = 'start'
        msg['type'] = 'screenshare'
        msg['role'] = 'recv'
        msg['internalMeetingId'] = self.sessionmanager.bbb_info['meetingID']
        msg['meetingId'] = msg['internalMeetingId']
        msg['voiceBridge'] = self.sessionmanager.bbb_info['voicebridge']

        # no idea why/if this has to be here
        msg['record'] = True
        msg['userId'] = self.sessionmanager.bbb_info['internalUserID']
        msg['callerName'] = self.sessionmanager.bbb_info['internalUserID']
        msg['userName'] = self.sessionmanager.bbb_info['fullname']
        msg['hasAudio'] = False

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

        self.send(msg)

class Switcher(object):
    def __init__(self, streammixer):
        self.screenshare_active = False
        self.streammixer = streammixer

    def new_sample(self, stype, source, sample):
        if self.screenshare_active and stype == 'screenshare':
            self.streammixer.new_sample('presentation', source, sample)
        elif not self.screenshare_active and stype == 'presentation':
            self.streammixer.new_sample('presentation', source, sample)
