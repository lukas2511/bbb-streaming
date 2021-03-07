#!/usr/bin/env python3

import time
import threading

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

        pipeline = "compositor background=black name=comp sink_1::alpha=1 sink_1::xpos=20 sink_1::ypos=700 sink_0::alpha=1 sink_0::xpos=220 sink_0::ypos=20 sync=true"
        pipeline += " ! video/x-raw,width=1920,height=1080"
        pipeline += " ! timeoverlay valignment=bottom halignment=right"
        pipeline += " ! videoconvert"
        pipeline += " ! x264enc pass=4 quantizer=22 speed-preset=4"
        pipeline += " ! video/x-h264, profile=baseline"
        pipeline += " ! queue"
        pipeline += " ! mux."

        pipeline += " appsrc name=presentation-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=RGB,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        pipeline += " ! videorate"
        pipeline += " ! videoscale"
        pipeline += " ! video/x-raw,width=1680,height=945"
        pipeline += " ! queue"
        pipeline += " ! comp.sink_0"

        pipeline += " appsrc name=camera-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=RGB,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        pipeline += " ! videorate"
        pipeline += " ! queue"
        pipeline += " ! videoscale"
        pipeline += " ! video/x-raw,width=480,height=360"
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
        pipeline += " ! rtmpsink location=%s" % rtmpurl

        self.pipe = Gst.parse_launch(pipeline)

        self.audio_input = self.pipe.get_by_name("audio-input")
        self.audio_input.set_property("format", Gst.Format.TIME)

        self.camera_input = self.pipe.get_by_name("camera-input")
        self.camera_input.set_property("format", Gst.Format.TIME)

        self.presentation_input = self.pipe.get_by_name("presentation-input")
        self.presentation_input.set_property("format", Gst.Format.TIME)

        self.pipe.set_state(Gst.State.PLAYING)

        self.lasttime = time.time()
        self.frames = 0

        self.cambuffer = Gst.Buffer.new_wrapped(b'\x00' * (4*1920*1080))
        self.presbuffer = Gst.Buffer.new_wrapped(b'\x00' * (4*1920*1080))

        self.push_frames()

    def stop(self):
        self.running = False

    def push_frames(self):
        if self.running:
            threading.Timer(1/25, self.push_frames).start()

        self.presentation_input.emit("push-buffer", self.presbuffer)
        self.camera_input.emit("push-buffer", self.cambuffer)

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


