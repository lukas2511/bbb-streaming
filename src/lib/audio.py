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

class Audio(WebRTC):
    def __init__(self, sessionmanager, streammixer):
        log.debug("Initializing audio connection")
        self.stype = 'audio'
        self.sessionmanager = sessionmanager
        self.streammixer = streammixer
        WebRTC.__init__(self)

    def run(self):
        while not self.sessionmanager.ready:
            time.sleep(0.1)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        log.debug("Connecting to bbb-webrtc-sfu")
        server = self.sessionmanager.bbb_server.replace('https', 'wss') + '/bbb-webrtc-sfu?sessionToken=' + self.sessionmanager.bbb_token
        self.conn = unasyncio(websockets.connect(server))

        pipeline = "webrtcbin name=recvonly bundle-policy=max-bundle stun-server=stun://%s" % self.sessionmanager.stun_server
        pipeline += " ! rtpopusdepay"
        pipeline += " ! queue"
        pipeline += " ! opusdec"
        pipeline += " ! audioconvert"
        pipeline += " ! audioresample"
        pipeline += " ! queue"
        pipeline += " ! appsink name=output emit-signals=true drop=false sync=true caps=audio/x-raw,rate=44100,channels=2,format=S16LE,layout=interleaved,channel-mask=(bitmask)0x0000000000000003"

        log.debug("Starting audio webrtc pipeline")
        self.pipe = Gst.parse_launch(pipeline)
        self.webrtc = self.pipe.get_by_name('recvonly')

        self.appsink = self.pipe.get_by_name("output")
        self.appsink.connect("new-sample", self.new_sample, self.appsink)

        direction = GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY
        caps = Gst.caps_from_string("application/x-rtp,media=audio,encoding-name=opus,payload=111,fec-type=ulp-red,do-nack=true,clock-rate=48000")
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

    def new_sample(self, sink, data):
        sample = self.appsink.emit("pull-sample")
        self.streammixer.new_audio_sample(self, sample)
        return Gst.FlowReturn.OK

    def send_sdp_offer(self, offer):
        log.info('Sending offer for audio')
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
                if '48000/2' not in line:
                    log.debug("Fixing sdp offer, broken opus codec line: %s" % line)
                    line = "a=rtpmap:111 opus/48000/2"
            sdpoffer += line
            sdpoffer += "\r\n"

        if 'a=mid:audio0' not in sdpoffer:
            log.debug("Fixing sdp offer, appending a=mid:audio0")
            sdpoffer += "a=mid:audio0\r\n"

        msg['sdpOffer'] = sdpoffer.strip()

        log.debug("Sending audio SDP offer: %r" % msg['sdpOffer'])

        self.send(msg)

