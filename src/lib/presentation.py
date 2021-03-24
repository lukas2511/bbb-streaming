#!/usr/bin/env python3

import requests
from . import shapes
import io
import ctypes
import threading
import time
import queue
import logging
log = logging.getLogger('bbb-streamer')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import cairo

Gst.init(None)

from .gsthacks import map_gst_buffer

class Presentation(object):
    def __init__(self, sessionmanager, streammixer):
        self.sessionmanager = sessionmanager

        self.streammixer = streammixer

        self.presentations = {}
        self.active_presentation = None
        self.slides = {}
        self.active_slide = None
        self.annotations = {}

        self.counter = 0
        self.lasttime = time.time()
        self.frames = 0

        self.frameres = (1920, 1080)
        self.framesvg = None
        self.frame = None
        self.framebuf = Gst.Buffer.new_wrapped(b'\x00' * (4*1920*1080))

        self.frame_updated = False
        self.mapped_framebuf = map_gst_buffer(self.framebuf, Gst.MapFlags.READ | Gst.MapFlags.WRITE)

        pipeline = "appsrc name=input emit-signals=false format=time do-timestamp=true is-live=true block=true caps=video/x-raw,width=1920,height=1080,format=BGRA,framerate=10/1,pixel-aspect-ratio=1/1,interlace-mode=progressive"
        pipeline += " ! videoconvert"
        pipeline += " ! queue"
        pipeline += " ! appsink name=output emit-signals=true drop=false sync=true caps=video/x-raw,format=RGBA,framerate=10/1,pixel-aspect-ratio=1/1"

        self.pipe = Gst.parse_launch(pipeline)
        self.appsink = self.pipe.get_by_name('output')
        self.appsink.connect("new-sample", self.new_sample, self.appsink)
        self.appsrc = self.pipe.get_by_name("input")
        self.pipe.set_state(Gst.State.PLAYING)

        self.running = True

        self.frameupdaterthread = threading.Thread(target=self.update_frame_loop, daemon=True)
        self.frameupdaterthread.start()

        self.push_frame()

        self.messagequeue = queue.Queue()
        self.messageparserthread = threading.Thread(target=self.parse_message_loop, daemon=True)
        self.messageparserthread.start()
        self.sessionmanager.attach(self.listener)

    def new_sample(self, sink, data):
        sample = self.appsink.emit("pull-sample")
        self.streammixer.new_sample("presentation", self, sample)
        return Gst.FlowReturn.OK

    def push_frame(self):
        if self.running:
            threading.Timer(1/10, self.push_frame).start()
        self.appsrc.emit("push-buffer", self.framebuf)

    def update_frame_loop(self):
        while self.running:
            self.update_frame()
            time.sleep(1/10)

    def update_frame(self):
        if not self.frame_updated:
            return
        self.frame_updated = False

        if not self.active_slide:
            return

        slide = self.slides[self.active_slide]
        svg = slide['raw'].replace('</svg>', '')

        for annotation_id, annotation in sorted(self.annotations.items(), key=lambda v: v[1]['counter']):
            if annotation['whiteboardId'] != slide['whiteboardId']:
                continue

            # only draw finished shapes
            if 'status' not in annotation or annotation['status'] != 'DRAW_END':
                continue

            if annotation['svg'] is None:
                annotation['svg'] = shapes.generate_svg(annotation, slide)
            svg += annotation['svg']

        svg += '</svg>'

        if svg != self.framesvg:
            self.framesvg = svg

            handle = Rsvg.Handle()
            svghandle = handle.new_from_data(self.framesvg.encode())

            scale_w = 1920 / svghandle.get_dimensions().width
            scale_h = 1080 / svghandle.get_dimensions().height

            if scale_w > scale_h:
                scale = scale_h
                width = int(svghandle.get_dimensions().width * scale_h)
                height = int(svghandle.get_dimensions().height * scale_h)
            else:
                scale = scale_w
                width = int(svghandle.get_dimensions().width * scale_w)
                height = int(svghandle.get_dimensions().height * scale_w)

            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
            context = cairo.Context(surface)
            context.scale(scale, scale)

            if self.frameres != (width, height):
                self.frameres = (width, height)

                curcaps = self.appsrc.get_property("caps")
                curwidth, curheight = curcaps.get_structure(0).get_value("width"), curcaps.get_structure(0).get_value("height")
                if curwidth != width or curheight != height:
                    caps = curcaps.copy()
                    caps.set_value("width", width)
                    caps.set_value("height", height)
                    self.appsrc.set_property("caps", caps)
                    log.info("Resized presentation canvas")

            svghandle.render_cairo(context)

            self.frame = bytes(surface.get_data())
            ctypes.memmove(self.mapped_framebuf, self.frame, len(self.frame))

        log.debug("Presentation frame updated")

    def add_slide(self, msg):
        slide_id = msg['id']

        if slide_id not in self.slides:
            log.debug("Adding slide %s" % slide_id)
            slide = {}
            slide['raw'] = requests.get(msg['fields']['svgUri']).text
            slide['whiteboardId'] = msg['fields']['id']
            slide['current'] = msg['fields']['current']
            slide['width'] = float(slide['raw'].split('width="')[1].split('"')[0].replace('pt', ''))
            slide['height'] = float(slide['raw'].split('height="')[1].split('"')[0].replace('pt', ''))

            self.slides[slide_id] = slide

            if slide['current']:
                if not self.active_presentation:
                    return
                if self.presentations[self.active_presentation]['id'] != slide['whiteboardId'].split('/')[0]:
                    return
                log.debug("Setting active slide to %s (new slide)" % slide_id)
                self.active_slide = slide_id
                self.frame_updated = True

    def remove_slide(self, msg):
        slide_id = msg['id']

        if slide_id in self.slides:
            del self.slides[slide_id]

    def listener(self, msg):
        if 'collection' not in msg:
            return
        self.messagequeue.put(msg)

    def parse_message_loop(self):
        while True:
            msg = self.messagequeue.get()
            if msg == 'stop':
                break
            self.parse_message(msg)

    def stop(self):
        self.running = False
        self.messagequeue.put("stop")
        self.frameupdaterthread.join()
        self.messageparserthread.join()

    def parse_message(self, msg):
        if msg['collection'] == 'presentations':
            if msg['msg'] == 'added':
                self.presentations[msg['id']] = msg['fields']
                if 'pages' in msg['fields']:
                    for slide in msg['fields']['pages']:
                        if slide['current']:
                            self.presentations[msg['id']]['active_slide'] = slide['id']
                if 'current' in msg['fields'] and msg['fields']['current']:
                    self.active_presentation = msg['id']
            elif msg['msg'] == 'removed':
                if msg['id'] in self.presentations:
                    del self.presentations[msg['id']]
            elif msg['msg'] == 'changed':
                self.presentations[msg['id']].update(msg['fields'])
                if 'pages' in msg['fields']:
                    for slide in msg['fields']['pages']:
                        if slide['current']:
                            self.presentations[msg['id']]['active_slide'] = slide['id']
                if 'current' in self.presentations[msg['id']] and self.presentations[msg['id']]['current']:
                    self.active_presentation = msg['id']
                    for slide_id, slide in self.slides.items():
                        if slide['whiteboardId'] == self.presentations[self.active_presentation]['active_slide']:
                            log.debug("Setting active slide to %s (presentation changed)" % slide_id)
                            self.active_slide = slide_id
                            self.frame_updated = True
                            break

        elif msg['collection'] == 'slides':
            if msg['msg'] == 'added':
                self.add_slide(msg)
            elif msg['msg'] == 'removed':
                self.remove_slide(msg)
            elif msg['msg'] == 'changed':
                self.slides[msg['id']]['current'] = msg['fields']['current']
                if self.slides[msg['id']]['current']:
                    log.debug("Setting active slide to %s (slide changed)" % msg['id'])
                    self.active_slide = msg['id']
                    self.presentations[self.active_presentation]['active_slide'] = self.slides[self.active_slide]['whiteboardId']
                    self.frame_updated = True
            else:
                log.warning("Unknown message: %r" % msg)
        elif msg['collection'] == 'annotations':
            if msg['msg'] == 'removed':
                if msg['id'] in self.annotations:
                    del self.annotations[msg['id']]
                    self.frame_updated = True
            elif msg['msg'] in ['changed', 'added']:
                if 'status' in msg['fields']:
                    if msg['fields']['status'] == 'DRAW_START':
                        self.annotations[msg['id']] = msg['fields']['annotationInfo']
                        self.annotations[msg['id']]['counter'] = self.counter
                        self.counter += 1
                    elif msg['fields']['status'] == 'DRAW_UPDATE':
                        if msg['id'] in self.annotations:
                            self.annotations[msg['id']].update(msg['fields']['annotationInfo'])
                            self.annotations[msg['id']]['counter'] = self.counter
                            self.counter += 1
                        else:
                            return
                    elif msg['fields']['status'] == 'DRAW_END':
                        self.annotations[msg['id']] = msg['fields']['annotationInfo']
                        self.annotations[msg['id']]['counter'] = self.counter
                        self.counter += 1
                        log.debug("Updating annotation %s" % msg['id'])
                        self.annotations[msg['id']]['svg'] = None
                        self.frame_updated = True
                    else:
                        log.warning("Unknown message: %r" % msg)
                        return
                elif 'status' in msg['fields']['annotationInfo'] and msg['fields']['annotationInfo']['status'] == 'DRAW_END':
                    self.annotations[msg['id']] = msg['fields']['annotationInfo']
                    log.debug("Updating annotation %s" % msg['id'])
                    self.annotations[msg['id']]['svg'] = None
                    self.frame_updated = True
            else:
                log.warning("Unknown message: %r" % msg)

        elif msg['collection'] == 'slide-positions':
            pass # not supported yet

        elif 'slide' in msg['collection'] or 'annot' in msg['collection']:
            log.warning("Unknown message: %r" % msg)
