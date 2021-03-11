#!/usr/bin/env python3

import time
import threading

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
    def __init__(self, rtmpurl):
        self.running = True

        pipeline = "compositor background=black sync=true name=comp"
        pipeline += " ! video/x-raw,width=1920,height=1080"
        #pipeline += " ! timeoverlay valignment=bottom halignment=left"
        pipeline += " ! videoconvert"
        pipeline += " ! x264enc pass=4 quantizer=22 speed-preset=4 key-int-max=50"
        pipeline += " ! video/x-h264, profile=baseline"
        pipeline += " ! h264parse config-interval=1"
        pipeline += " ! queue"
        pipeline += " ! mux."

        pipeline += " appsrc name=background-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=RGB,framerate=1/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        pipeline += " ! videorate"
        pipeline += " ! queue"
        pipeline += " ! comp.sink_2"

        pipeline += " appsrc name=presentation-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=RGB,framerate=10/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        pipeline += " ! videorate"
        pipeline += " ! queue"
        pipeline += " ! videoscale"
        pipeline += " ! comp.sink_0"

        pipeline += " appsrc name=camera-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1280,height=720,format=RGB,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        pipeline += " ! videorate"
        pipeline += " ! queue"
        pipeline += " ! videoscale"
        pipeline += " ! comp.sink_1"

        pipeline += " appsrc name=audio-input emit-signals=false do-timestamp=true is-live=true block=true caps=audio/x-raw,rate=48000,channels=2,format=U16LE,layout=interleaved"
        pipeline += " ! queue"
        pipeline += " ! audioconvert"
        pipeline += " ! audioresample"
        pipeline += " ! fdkaacenc bitrate=128000"
        pipeline += " ! audio/mpeg,rate=48000,channels=2"
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
        self.set_view("sbs")

        self.lasttime = time.time()
        self.frames = 0

        self.cambuffer = Gst.Buffer.new_wrapped(b'\x00' * (4*1280*720))
        self.presbuffer = Gst.Buffer.new_wrapped(b'\x00' * (4*1920*1080))

        self.bgbuffer = Gst.Buffer.new_wrapped(Image.open("images/bg.png").resize((1920, 1080)).convert("RGB").tobytes())

        self.push_camera_frames()
        self.push_presentation_frames()
        self.push_background_frames()

    def set_view(self, view):
        if view == "sbs":
            camera = {'xpos': 1420, 'ypos': 790, 'width': 480, 'height': 270, 'alpha': 1.0}
            presentation = {'xpos': 20, 'ypos': 96, 'width': 1440, 'height': 810, 'alpha': 1.0}
        elif view == "pip":
            camera = {'xpos': 1420, 'ypos': 790, 'width': 480, 'height': 270, 'alpha': 1.0}
            presentation = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 1.0}
        elif view == "cam":
            camera = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 1.0}
            presentation = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 0.0}
        elif view == "pres":
            camera = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 0.0}
            presentation = {'xpos': 0, 'ypos': 0, 'width': 1920, 'height': 1080, 'alpha': 1.0}
        else:
            print("unknown view: %s" % view)

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

    def push_camera_frames(self):
        if self.running:
            threading.Timer(1/25, self.push_camera_frames).start()
        self.camera_input.emit("push-buffer", self.cambuffer)

    def push_presentation_frames(self):
        if self.running:
            threading.Timer(1/10, self.push_presentation_frames).start()
        self.presentation_input.emit("push-buffer", self.presbuffer)

    def fpscount(self):
        self.frames += 1
        if self.lasttime < (time.time()-1):
            print(self.frames)
            self.frames = 0
            self.lasttime = time.time()

    def new_audio_sample(self, source, sample):
        buf = sample.get_buffer()
        buf.pts = 18446744073709551615
        buf.dts = 18446744073709551615
        self.audio_input.emit("push-buffer", buf)

    def new_sample(self, stype, source, sample):
        if stype == "video":
            buf = sample.get_buffer()
            buf.pts = 18446744073709551615
            buf.dts = 18446744073709551615
            buf.duration = 40000000
            self.cambuffer = buf
        elif stype == "presentation":
            buf = sample.get_buffer()
            buf.pts = 18446744073709551615
            buf.dts = 18446744073709551615
            buf.duration = 40000000
            self.presbuffer = buf
            #self.presentation_input.emit("push-sample", sample)


