import random
import websockets
import asyncio
import os
import sys
import json
import argparse

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

session_txt = open("session.txt").read().splitlines()
SESSION_TOKEN = session_txt[0].split()[0]
STUN_SERVER = json.loads(session_txt[1])['stunServers'][0]['url'].split(':')[0]
SESSION_BASE = session_txt[4]
SESSION_INFO = json.loads(session_txt[2])

PIPELINE_DESC = '''
webrtcbin name=recvonly bundle-policy=max-bundle stun-server=stun://%s ! rtpopusdepay ! opusdec ! audioconvert ! audioresample ! autoaudiosink
''' % STUN_SERVER
#recvonly.src_0 ! rtpopusdepay ! opusdec ! audioconvert ! audioresample ! autoaudiosink

 #videotestsrc is-live=true pattern=ball ! videoconvert ! queue ! vp8enc deadline=1 ! rtpvp8pay !
 #queue ! application/x-rtp,media=video,encoding-name=VP8,payload=97 ! recvonly.
 #audiotestsrc is-live=true wave=red-noise ! audioconvert ! audioresample ! queue ! opusenc ! rtpopuspay !
 #queue ! application/x-rtp,media=audio,encoding-name=OPUS,payload=96 ! recvonly.

#"sdpOffer":"v=0
# o=- 4121812343390791657 2 IN IP4 127.0.0.1
# s=-
# t=0 0
# a=group:BUNDLE 0
# a=extmap-allow-mixed
# a=msid-semantic: WMS
# 
#m=audio 9 UDP/TLS/RTP/SAVPF 111 103 104 9 0 8 106 105 13 110 112 113 126
# c=IN IP4 0.0.0.0
# a=rtcp:9 IN IP4 0.0.0.0
# a=ice-ufrag:YgMq
# 
#a=ice-pwd:o0kpNh64Gr1oDJbgDxSH9sZA
# a=ice-options:trickle
# 
#a=fingerprint:sha-256 1C:DE:6F:9F:00:3B:F4:7B:19:DD:70:DE:27:E5:1B:76:A1:0E:C3:96:C9:0A:C0:35:6E:B1:2E:73:9D:BE:E5:22
# a=setup:actpass
# 
#a=mid:0
# a=extmap:1 urn:ietf:params:rtp-hdrext:ssrc-audio-level
# a=extmap:2 http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time
# 
#a=extmap:3 http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01
# a=extmap:4 urn:ietf:params:rtp-hdrext:sdes:mid
# 
#a=extmap:5 urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id
# a=extmap:6 urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id
# a=recvonly
# 
#a=rtcp-mux
# a=rtpmap:111 opus/48000/2
# a=rtcp-fb:111 transport-cc
# a=fmtp:111 minptime=10;useinbandfec=1
# a=rtpmap:103 ISAC/16000
# 
#a=rtpmap:104 ISAC/32000
# a=rtpmap:9 G722/8000
# a=rtpmap:0 PCMU/8000
# a=rtpmap:8 PCMA/8000
# a=rtpmap:106 CN/32000
# a=rtpmap:105 CN/16000
# 
#a=rtpmap:13 CN/8000
# a=rtpmap:110 telephone-event/48000
# a=rtpmap:112 telephone-event/32000
# a=rtpmap:113 telephone-event/16000
# 
#a=rtpmap:126 telephone-event/8000
# "}

class WebRTCClient:
    def __init__(self):
        self.conn = None
        self.webrtc = None
        self.server = SESSION_BASE.replace('https', 'wss') + '/bbb-webrtc-sfu?sessionToken=' + SESSION_TOKEN

    def send_sdp_offer(self, offer):
        text = offer.sdp.as_text()
        print('Sending offer')
        msg = {}
        msg['id'] = 'start'
        msg['type'] = 'audio'
        msg['role'] = 'recv'
        msg['internalMeetingId'] = SESSION_INFO['meetingID']
        msg['voiceBridge'] = SESSION_INFO['voicebridge']
        msg['caleeName'] = 'GLOBAL_AUDIO_' + SESSION_INFO['voicebridge']
        msg['userId'] = SESSION_INFO['internalUserID']
        msg['userName'] = SESSION_INFO['fullname']

        text = text.split("a=rtpmap:111 opus/")[0] + "a=rtpmap:111 opus/48000/2\r\n" + text.split("a=rtpmap:111 opus/")[1].split("\r\n")[1]
        text += "\r\na=mid:audio0"

        #newtext = newtext.replace("nack pli", "transport-cc")
        #newtext = newtext.replace("m=opus", "m=audio")

        msg['sdpOffer'] = text

        print(msg['sdpOffer'])
        print("")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(json.dumps(msg)))
        loop.close()

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        #print("sending ice candidates: " + candidate)

        msg = {}
        msg['id'] = 'iceCandidate'
        msg['role'] = 'recv'
        msg['type'] = 'audio'
        msg['voiceBridge'] = SESSION_INFO['voicebridge']
        msg['candidate'] = {'candidate': candidate, 'sdpMLineIndex': mlineindex, 'sdpMid': '0'}

        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(json.dumps(msg)))
        loop.close()

    def on_offer_created(self, promise, _, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply['offer']
        promise = Gst.Promise.new()
        self.webrtc.emit('set-local-description', offer, promise)
        promise.interrupt()
        self.send_sdp_offer(offer)

    async def connect(self):
        self.conn = await websockets.connect(self.server)
        self.pipe = Gst.parse_launch(PIPELINE_DESC)
        self.webrtc = self.pipe.get_by_name('recvonly')

        direction = GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY
        caps = Gst.caps_from_string("application/x-rtp,media=audio,encoding-name=opus,channel-rate=48000,channels=2,payload=111")
        self.webrtc.emit('add-transceiver', direction, caps)

        self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)
        self.webrtc.connect('pad-added', self.on_incoming_stream)
        self.pipe.set_state(Gst.State.PLAYING)

    def handle_sdp(self, message):
        msg = json.loads(message)
        if 'sdpAnswer' in msg:
            sdp = msg['sdpAnswer']
            print('received sdp answer')
            print(sdp)
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
        else:
            print(msg)


    def on_incoming_stream(self, _, pad):
        print("!!!DANG DANG DANG DANG!!!")

#    def on_incoming_decodebin_stream(self, _, pad):
#        if not pad.has_current_caps():
#            print (pad, 'has no caps, ignoring')
#            return
#
#        caps = pad.get_current_caps()
#        assert (len(caps))
#        s = caps[0]
#        name = s.get_name()
#        if name.startswith('video'):
#            q = Gst.ElementFactory.make('queue')
#            conv = Gst.ElementFactory.make('videoconvert')
#            sink = Gst.ElementFactory.make('autovideosink')
#            self.pipe.add(q, conv, sink)
#            self.pipe.sync_children_states()
#            pad.link(q.get_static_pad('sink'))
#            q.link(conv)
#            conv.link(sink)
#        elif name.startswith('audio'):
#            q = Gst.ElementFactory.make('queue')
#            conv = Gst.ElementFactory.make('audioconvert')
#            resample = Gst.ElementFactory.make('audioresample')
#            sink = Gst.ElementFactory.make('autoaudiosink')
#            self.pipe.add(q, conv, resample, sink)
#            self.pipe.sync_children_states()
#            pad.link(q.get_static_pad('sink'))
#            q.link(conv)
#            conv.link(resample)
#            resample.link(sink)

#    def on_incoming_stream(self, _, pad):
#        if pad.direction != Gst.PadDirection.SRC:
#            return
#
#        decodebin = Gst.ElementFactory.make('decodebin')
#        decodebin.connect('pad-added', self.on_incoming_decodebin_stream)
#        self.pipe.add(decodebin)
#        decodebin.sync_state_with_parent()
#        self.webrtc.link(decodebin)
#
#    def close_pipeline(self):
#        self.pipe.set_state(Gst.State.NULL)
#        self.pipe = None
#        self.webrtc = None

    async def loop(self):
        assert self.conn
        async for message in self.conn:
            if message == 'HELLO':
                await self.setup_call()
            elif message == 'SESSION_OK':
                self.start_pipeline()
            elif message.startswith('ERROR'):
                print (message)
                self.close_pipeline()
                return 1
            else:
                self.handle_sdp(message)
        self.close_pipeline()
        return 0

    async def stop(self):
        if self.conn:
            await self.conn.close()
        self.conn = None


def check_plugins():
    needed = ["opus", "vpx", "nice", "webrtc", "dtls", "srtp", "rtp",
              "rtpmanager", "videotestsrc", "audiotestsrc"]
    missing = list(filter(lambda p: Gst.Registry.get().find_plugin(p) is None, needed))
    if len(missing):
        print('Missing gstreamer plugins:', missing)
        return False
    return True


if __name__=='__main__':
    Gst.init(None)
    if not check_plugins():
        sys.exit(1)
    c = WebRTCClient()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(c.connect())
    res = loop.run_until_complete(c.loop())
    sys.exit(res)
