#!/usr/bin/env python3

import requests
from . import shapes
import io
import ctypes
import threading
import time

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
    def __init__(self, sessionmanager):
        self.sessionmanager = sessionmanager
        self.sessionmanager.attach(self.listener)

        self.presentations = {}
        self.active_presentation = None
        self.slides = {}
        self.active_slide = None
        self.annotations = {}

        self.framesvg = None
        self.frame = None
        self.framebuf = Gst.Buffer.new_wrapped(b'\x00' * (4*1920*1080))
        self.frame_updated = False
        self.mapped_framebuf = map_gst_buffer(self.framebuf, Gst.MapFlags.READ | Gst.MapFlags.WRITE)

        self.pipe = Gst.parse_launch("appsrc name=input emit-signals=false do-timestamp=true is-live=true block=false caps=video/x-raw,width=1920,height=1080,format=BGRA ! video/x-raw,width=1920,height=1080,format=BGRA,framerate=25/1 ! queue ! videoconvert ! xvimagesink")
        self.appsrc = self.pipe.get_by_name("input")
        self.pipe.set_state(Gst.State.PLAYING)

        self.running = True

        self.framepusherthread = threading.Thread(target=self.push_frame, daemon=True)
        self.framepusherthread.start()

        self.frameupdaterthread = threading.Thread(target=self.update_frame_loop, daemon=True)
        self.frameupdaterthread.start()

    def push_frame(self):
        while self.running:
            self.appsrc.emit("push-buffer", self.framebuf)
            time.sleep(1/25)

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

        for annotation_id, annotation in self.annotations.items():
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

            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 1920, 1080)
            context = cairo.Context(surface)
            handle = Rsvg.Handle()
            handle.new_from_data(self.framesvg.encode()).render_cairo(context)

            self.frame = bytes(surface.get_data())
            ctypes.memmove(self.mapped_framebuf, self.frame, len(self.frame))

        print("Update frame")

    def add_slide(self, msg):
        slide_id = msg['id']

        if slide_id not in self.slides:
            print("Adding slide %s" % slide_id)
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
                print("setting active slide to %s (new slide)" % slide_id)
                self.active_slide = slide_id
                self.frame_updated = True

    def remove_slide(self, msg):
        slide_id = msg['id']

        if slide_id in self.slides:
            del self.slides[slide_id]

    def listener(self, msg):
        if 'collection' not in msg:
            return

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
                            print("setting active slide to %s (presentation changed)" % slide_id)
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
                    print("setting active slide to %s (slide changed)" % msg['id'])
                    self.active_slide = msg['id']
                    self.presentations[self.active_presentation]['active_slide'] = self.slides[self.active_slide]['whiteboardId']
                    self.frame_updated = True
            else:
                print(msg)
        elif msg['collection'] == 'annotations':
            if msg['msg'] == 'removed':
                if msg['id'] in self.annotations:
                    del self.annotations[msg['id']]
                    self.frame_updated = True
            elif msg['msg'] in ['changed', 'added']:
                if 'status' in msg['fields']:
                    if msg['fields']['status'] == 'DRAW_START':
                        self.annotations[msg['id']] = msg['fields']['annotationInfo']
                    elif msg['fields']['status'] == 'DRAW_UPDATE':
                        if msg['id'] in self.annotations:
                            self.annotations[msg['id']].update(msg['fields']['annotationInfo'])
                        else:
                            return
                    elif msg['fields']['status'] == 'DRAW_END':
                        self.annotations[msg['id']] = msg['fields']['annotationInfo']
                    else:
                        print("wat")
                        print(msg['fields']['status'])
                        return
                elif 'status' in msg['fields']['annotationInfo'] and msg['fields']['annotationInfo']['status'] == 'DRAW_END':
                    self.annotations[msg['id']] = msg['fields']['annotationInfo']

                if msg['id'] in self.annotations:
                    print("Updating annotation %s" % msg['id'])
                    self.annotations[msg['id']]['svg'] = None
                    self.frame_updated = True
            else:
                print("wat")
                print(msg)

        elif msg['collection'] == 'slide-positions':
            pass # not supported yet

        elif 'slide' in msg['collection'] or 'annot' in msg['collection']:
            print(msg)
