#!/usr/bin/env python3

import asyncio
from .helpers import unasyncio
import websockets
import json
import threading
import time

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
    def __init__(self, sessionmanager, streammixer):
        self.screenshares = {}

        self.sessionmanager = sessionmanager
        self.sessionmanager.attach(self.listener)

        self.streammixer = streammixer

    def remove(self, msgid):
        if msgid in self.screenshares:
            self.screenshares[msgid].stop()
            self.screenshares[msgid].join()
            del self.screenshares[msgid]

    def add(self, msgid, fields):
        for msgid in self.screenshares:
            self.remove(msgid)

        self.screenshares[msgid] = Screenshare(self.sessionmanager, fields, self.streammixer)
        self.screenshares[msgid].start()

    def listener(self, msg):
        if 'collection' not in msg or msg['collection'] != 'screenshare':
            return

        if msg['msg'] == 'removed':
            self.remove(msg['id'])
        elif msg['msg'] == 'added':
            self.add(msg['id'], msg['fields'])

class Screenshare(threading.Thread):
    def __init__(self, sessionmanager, fields, streammixer):
        self.sessionmanager = sessionmanager
        self.streammixer = streammixer
        self.fields = fields
        self.running = True
        self.ready = False
        threading.Thread.__init__(self)
        self.daemon = True

    def new_sample(self, sink, data):
        sample = self.appsink.emit("pull-sample")
        self.streammixer.new_sample("screenshare", self, sample)
        return Gst.FlowReturn.OK

    def stop(self):
        self.running = False

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        server = self.sessionmanager.bbb_server.replace('https', 'wss') + '/bbb-webrtc-sfu?sessionToken=' + self.sessionmanager.bbb_token
        self.conn = unasyncio(websockets.connect(server))

        pipeline = "webrtcbin name=recvonly bundle-policy=max-bundle stun-server=stun://%s" % self.sessionmanager.stun_server
        pipeline += " ! rtpvp8depay"
        pipeline += " ! vp8dec"
        pipeline += " ! queue"
        pipeline += " ! videoscale"
        pipeline += " ! videoconvert"
        pipeline += " ! videorate"
        pipeline += " ! queue"
        pipeline += " ! video/x-raw,width=1920,height=1080,format=RGB,framerate=25/1,pixel-aspect-ratio=1/1"
        pipeline += " ! appsink name=output emit-signals=true drop=true"

        self.pipe = Gst.parse_launch(pipeline)
        self.webrtc = self.pipe.get_by_name('recvonly')
        self.appsink = self.pipe.get_by_name('output')
        self.appsink.connect("new-sample", self.new_sample, self.appsink)

        direction = GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY
        caps = Gst.caps_from_string("application/x-rtp,media=video,encoding-name=vp8,clock-rate=90000,payload=98")
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

    def recv(self):
        try:
            raw = unasyncio(asyncio.wait_for(self.conn.recv(), timeout=0.1))
        except asyncio.exceptions.TimeoutError:
            return None
        return json.loads(raw)

    def send(self, msg):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(json.dumps(msg)))
        loop.close()

    def send_sdp_offer(self, offer):
        print('Sending offer for screenshare')
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

        self.send(msg)

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        msg = {}
        msg['id'] = 'iceCandidate'
        msg['role'] = 'recv'
        msg['type'] = 'screenshare'
        msg['voiceBridge'] = self.sessionmanager.bbb_info['voicebridge']
        msg['candidate'] = {'candidate': candidate, 'sdpMLineIndex': mlineindex}
        self.send(msg)

    def on_offer_created(self, promise, _, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply['offer']
        promise = Gst.Promise.new()
        self.webrtc.emit('set-local-description', offer, promise)
        promise.interrupt()
        self.send_sdp_offer(offer)

    def handle_sdp(self, msg):
        if 'sdpAnswer' in msg:
            sdp = msg['sdpAnswer']
            print('Received sdp answer for screenshare')
            res, sdpmsg = GstSdp.SDPMessage.new()
            GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
            answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
            promise = Gst.Promise.new()
            self.webrtc.emit('set-remote-description', answer, promise)
            promise.interrupt()
        elif 'candidate' in msg:
            ice = msg['candidate']
            candidate = ice['candidate']
            #print("got ice candidate: %s" % candidate)
            sdpmlineindex = ice['sdpMLineIndex']
            self.webrtc.emit('add-ice-candidate', sdpmlineindex, candidate)
        #else:
        #    print(msg)

    def on_incoming_stream(self, _, pad):
        self.ready = True
        print("Screenshare ready")
