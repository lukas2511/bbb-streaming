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

class Audio(threading.Thread):
    def __init__(self, sessionmanager):
        self.sessionmanager = sessionmanager
        self.running = True
        self.ready = False
        threading.Thread.__init__(self)
        self.daemon = True

    def stop(self):
        self.running = False

    def run(self):
        while not self.sessionmanager.ready:
            time.sleep(0.1)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        server = self.sessionmanager.bbb_server.replace('https', 'wss') + '/bbb-webrtc-sfu?sessionToken=' + self.sessionmanager.bbb_token
        self.conn = unasyncio(websockets.connect(server))

        stun_server = self.sessionmanager.bbb_stuns['stunServers'][0]['url'].split(':')[0]
        pipeline = "webrtcbin name=recvonly bundle-policy=max-bundle stun-server=stun://%s" % stun_server
        pipeline += " ! rtpopusdepay"
        pipeline += " ! opusdec"
        pipeline += " ! audioconvert"
        pipeline += " ! audioresample"
        pipeline += " ! autoaudiosink"

        self.pipe = Gst.parse_launch(pipeline)
        self.webrtc = self.pipe.get_by_name('recvonly')

        direction = GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY
        caps = Gst.caps_from_string("application/x-rtp,media=audio,encoding-name=opus,payload=111")
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
        print('Sending offer for audio')
        msg = {}
        msg['id'] = 'start'
        msg['type'] = 'audio'
        msg['role'] = 'recv'
        msg['internalMeetingId'] = self.sessionmanager.bbb_info['meetingID']
        msg['voiceBridge'] = self.sessionmanager.bbb_info['voicebridge']
        msg['caleeName'] = 'GLOBAL_AUDIO_' + self.sessionmanager.bbb_info['voicebridge']
        msg['userId'] = self.sessionmanager.bbb_info['internalUserID']
        msg['userName'] = self.sessionmanager.bbb_info['fullname']

        # fix gst codec parameters
        sdpoffer = ""
        for line in offer.sdp.as_text().splitlines():
            if line.startswith("a=rtpmap:111 opus/"):
                line = "a=rtpmap:111 opus/48000/2"
            sdpoffer += line
            sdpoffer += "\r\n"

        if 'a=mid:audio0' not in sdpoffer:
            sdpoffer += "a=mid:audio0\r\n"

        msg['sdpOffer'] = sdpoffer.strip()

        self.send(msg)

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        msg = {}
        msg['id'] = 'iceCandidate'
        msg['role'] = 'recv'
        msg['type'] = 'audio'
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
            print('Received sdp answer for audio')
            #print(sdp)
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
        print("Audio ready")
