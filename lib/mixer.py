#!/usr/bin/env python3

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

Gst.init(None)

class Mixer(object):
    def __init__(self):
        pipeline = "appsrc name=camera-input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=RGB,framerate=25/1,pixel-aspect-ratio=1/1"
        pipeline += " ! queue"
        pipeline += " ! videoscale"
        pipeline += " ! videoconvert"
        pipeline += " ! queue"
        pipeline += " ! xvimagesink sync=false"

        self.pipe = Gst.parse_launch(pipeline)
        self.camera_input = self.pipe.get_by_name("camera-input")
        self.pipe.set_state(Gst.State.PLAYING)

        self.source = "camera"

    def new_sample(self, stype, source, sample):
        if stype == self.source:
            self.camera_input.emit("push-sample", sample)
