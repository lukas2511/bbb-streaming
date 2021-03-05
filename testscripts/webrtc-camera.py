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

CAMERA_ID = '<censored>'

PIPELINE_DESC = '''
webrtcbin name=recvonly bundle-policy=max-bundle stun-server=stun://%s ! rtpvp8depay ! vp8dec ! videoconvert ! autovideosink
''' % STUN_SERVER

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
        msg['type'] = 'video'
        msg['role'] = 'viewer' # viewer for webcam, recv for audio+screenshare
        msg['internalMeetingId'] = SESSION_INFO['meetingID']
        msg['meetingId'] = SESSION_INFO['meetingID']
        msg['voiceBridge'] = SESSION_INFO['voicebridge']
        msg['bitrate'] = 200
        msg['record'] = True

        msg['userId'] = SESSION_INFO['internalUserID']
        msg['userName'] = SESSION_INFO['fullname']
        msg['cameraId'] = CAMERA_ID

        # fix gst codec parameters
        text = text.split("a=rtpmap:98 vp8/")[0] + "a=rtpmap:98 vp8/90000\r\n" + text.split("a=rtpmap:98 vp8/")[1].split("\r\n")[1]
        text += "\r\na=mid:video0"

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
        msg['candidate'] = {'candidate': candidate, 'sdpMLineIndex': mlineindex}

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
        caps = Gst.caps_from_string("application/x-rtp,media=video,encoding-name=vp8,payload=98")
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
