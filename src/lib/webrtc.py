#!/usr/bin/env python3

import re
import asyncio
from .helpers import unasyncio
import threading
import json

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

Gst.init(None)

class WebRTC(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.running = True
        self.ready = False
        threading.Thread.__init__(self, *args, **kwargs)
        self.daemon = True
        self.force_keyframes()

    def stop(self):
        self.running = False

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

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def force_keyframes(self):
        if self.running:
            threading.Timer(1, self.force_keyframes).start()

        if self.ready:
            struct = Gst.Structure("GstForceKeyUnit")
            event = Gst.Event.new_custom(Gst.EventType.CUSTOM_UPSTREAM, struct)
            self.webrtc.send_event(event)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        if not self.check_ice_candidate(candidate):
            return

        msg = {}
        msg['id'] = 'iceCandidate'
        msg['role'] = 'viewer' if self.stype == 'video' else 'recv'
        msg['type'] = self.stype
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

    def check_ice_candidate(self, candidate):
        _, _, candidate_proto, _, candidate_ip, _ = candidate.split(None, 5)

        # bbb webrtc sfu doesn't seem to support tcp, don't even need to send our ice candidates then..
        if candidate_proto == 'TCP':
            return False

        # just why is this even here?!
        if candidate_ip.startswith("fe80::"):
            return False

        # ignore RFC1918 addresses
        if re.match("^(192\.168|10|172\.(1[6-9]|2[0-9]|3[0-1]))\.", candidate_ip):
            return False

        # everything else is good enough
        return True

    def handle_sdp(self, msg):
        if 'sdpAnswer' in msg:
            sdp = msg['sdpAnswer']
            res, sdpmsg = GstSdp.SDPMessage.new()
            GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
            answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
            promise = Gst.Promise.new()
            self.webrtc.emit('set-remote-description', answer, promise)
            promise.interrupt()
        elif 'candidate' in msg:
            ice = msg['candidate']
            candidate = ice['candidate']

            if not self.check_ice_candidate(candidate):
                return

            sdpmlineindex = ice['sdpMLineIndex']
            self.webrtc.emit('add-ice-candidate', sdpmlineindex, candidate)

    def on_incoming_stream(self, _, pad):
        self.ready = True
        print("WebRTC %r ready" % self)
