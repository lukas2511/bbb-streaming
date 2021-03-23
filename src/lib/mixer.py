#!/usr/bin/env python3

import time
import requests
import threading
import logging
log = logging.getLogger('bbb-streamer')

from PIL import Image

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

Gst.init(None)

class Mixer(object):
    def __init__(self, rtmpurl, background):
        self.running = True

        pipeline = "compositor background=black sync=true name=comp"
        pipeline += " ! video/x-raw,width=1920,height=1080"
        pipeline += " ! videoconvert"
        pipeline += " ! videorate"
        pipeline += " ! queue"
        pipeline += " ! x264enc pass=4 quantizer=22 speed-preset=4 key-int-max=50"
        pipeline += " ! video/x-h264, profile=baseline"
        pipeline += " ! h264parse config-interval=1"
        pipeline += " ! queue"
        pipeline += " ! mux."

        pipeline += " appsrc name=background-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=RGB,framerate=1/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        #pipeline += " ! timeoverlay valignment=bottom halignment=left"
        pipeline += " ! comp.sink_2"

        pipeline += " appsrc name=presentation-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=RGBA,framerate=10/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        #pipeline += " ! timeoverlay valignment=bottom halignment=right"
        pipeline += " ! comp.sink_0"

        pipeline += " appsrc name=camera-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1280,height=720,format=RGBA,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        #pipeline += " ! timeoverlay valignment=top halignment=left"
        pipeline += " ! comp.sink_1"

        pipeline += " appsrc name=audio-input emit-signals=false do-timestamp=true is-live=true block=true caps=audio/x-raw,rate=44100,channels=2,format=S16LE,layout=interleaved,channel-mask=(bitmask)0x0000000000000003"
        pipeline += " ! queue"
        pipeline += " ! fdkaacenc bitrate=128000"
        pipeline += " ! queue"
        pipeline += " ! mux."

        pipeline += " flvmux name=mux"
        pipeline += " ! queue"
        pipeline += " ! rtmpsink sync=true location=%s" % rtmpurl

        self.pipe = Gst.parse_launch(pipeline)

        self.audio_input = self.pipe.get_by_name("audio-input")
        self.audio_input.set_property("format", Gst.Format.TIME)

        self.compositor = self.pipe.get_by_name("comp")

        self.camera_input = self.pipe.get_by_name("camera-input")
        self.camera_input.set_property("format", Gst.Format.TIME)

        self.presentation_input = self.pipe.get_by_name("presentation-input")
        self.presentation_input.set_property("format", Gst.Format.TIME)

        self.background_input = self.pipe.get_by_name("background-input")
        self.background_input.set_property("format", Gst.Format.TIME)

        self.pipe.set_state(Gst.State.PLAYING)

        self.camera_aspect = 16 / 9
        self.presentation_aspect = 16 / 9
        self.current_view = "sbs"
        self.set_view(self.current_view)

        self.lasttime = time.time()
        self.frames = 0

        self.cambuffer = (Gst.Buffer.new_wrapped(b'\x00' * (4*1280*720)), (1280, 720))
        self.presbuffer = (Gst.Buffer.new_wrapped(b'\x00' * (4*1920*1080)), (1920, 1080))

        if background:
            if background.startswith("http://") or background.startswith("https://"):
                bgimage = Image.open(requests.get(background, stream=True).raw).resize((1920, 1080))
            else:
                bgimage = Image.open(background).resize((1920, 1080))
        else:
            bgimage = Image.open("images/bg.png").resize((1920, 1080))

        self.bgbuffer = Gst.Buffer.new_wrapped(bgimage.convert("RGB").tobytes())

        self.push_camera_frames()
        self.push_presentation_frames()
        self.push_background_frames()

    def set_view(self, view):
        if view == "sbs":
            presentation_width = 1440
            presentation_height = presentation_width / self.presentation_aspect
            if presentation_height > (1080-96-60):
                presentation_height = 1080-96-60
                presentation_width = presentation_height * self.presentation_aspect

            camera_width = 480
            camera_height = camera_width / self.camera_aspect

            camera = {'xpos': (1920 - camera_width - 20), 'ypos': (1080 - camera_height - 20), 'width': camera_width, 'height': camera_height, 'alpha': 1.0}
            presentation = {'xpos': 20, 'ypos': 96, 'width': presentation_width, 'height': presentation_height, 'alpha': 1.0}
        elif view == "pip":
            presentation_width = 1920
            presentation_height = presentation_width / self.presentation_aspect
            if presentation_height > 1080:
                presentation_height = 1080
                presentation_width = presentation_height * self.presentation_aspect

            camera_width = 480
            camera_height = camera_width / self.camera_aspect

            camera = {'xpos': (1920 - camera_width), 'ypos': (1080 - camera_height), 'width': camera_width, 'height': camera_height, 'alpha': 1.0}
            presentation = {'xpos': 0, 'ypos': 0, 'width': presentation_width, 'height': presentation_height, 'alpha': 1.0}
        elif view == "cam":
            camera = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 1.0}
            presentation = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 0.0}
        elif view == "pres":
            camera = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 0.0}
            presentation = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 1.0}
        else:
            log.warning("Unknown view: %s" % view)
            return

        self.current_view = view

        for key, value in camera.items():
            sink = self.compositor.get_static_pad('sink_1')
            sink.set_property(key, value)
        for key, value in presentation.items():
            sink = self.compositor.get_static_pad('sink_0')
            sink.set_property(key, value)

    def stop(self):
        self.running = False

    def push_background_frames(self):
        if self.running:
            threading.Timer(1, self.push_background_frames).start()
        self.background_input.emit("push-buffer", self.bgbuffer)

    def setsinkres(self, sink, res):
        curcaps = sink.get_property("caps")
        curwidth, curheight = curcaps.get_structure(0).get_value("width"), curcaps.get_structure(0).get_value("height")
        if curwidth != res[0] or curheight != res[1]:
            caps = curcaps.copy()
            caps.set_value("width", res[0])
            caps.set_value("height", res[1])
            sink.set_property("caps", caps)
            return True
        return False

    def push_camera_frames(self):
        if self.running:
            threading.Timer(1/25, self.push_camera_frames).start()

        buf, (width, height) = self.cambuffer
        changed = False
        if self.setsinkres(self.camera_input, (width, height)):
            self.camera_aspect = width / height
            changed = True

        self.camera_input.emit("push-buffer", self.cambuffer[0])
        if changed:
            self.background_input.emit("push-buffer", self.bgbuffer)
            self.presentation_input.emit("push-buffer", self.presbuffer[0])
            self.set_view(self.current_view)

    def push_presentation_frames(self):
        if self.running:
            threading.Timer(1/10, self.push_presentation_frames).start()

        buf, (width, height) = self.presbuffer
        changed = False
        if self.setsinkres(self.presentation_input, (width, height)):
            self.presentation_aspect = width / height
            changed = True

        self.presentation_input.emit("push-buffer", self.presbuffer[0])
        if changed:
            self.background_input.emit("push-buffer", self.bgbuffer)
            self.camera_input.emit("push-buffer", self.cambuffer[0])
            self.set_view(self.current_view)

    def new_audio_sample(self, source, sample):
        buf = sample.get_buffer()
        buf.pts = 18446744073709551615
        buf.dts = 18446744073709551615
        self.audio_input.emit("push-buffer", buf)

    def new_sample(self, stype, source, sample):
        if stype == "video":
            caps = sample.get_caps().get_structure(0)
            width, height = caps.get_value("width"), caps.get_value("height")
            buf = sample.get_buffer()
            buf.pts = 18446744073709551615
            buf.dts = 18446744073709551615
            buf.duration = 40000000
            self.cambuffer = (buf, (width, height))
        elif stype == "presentation":
            caps = sample.get_caps().get_structure(0)
            width, height = caps.get_value("width"), caps.get_value("height")
            buf = sample.get_buffer()
            buf.pts = 18446744073709551615
            buf.dts = 18446744073709551615
            buf.duration = 100000000
            self.presbuffer = (buf, (width, height))


