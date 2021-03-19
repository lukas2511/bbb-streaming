#!/usr/bin/env python3

import requests
import cmd
import json
import sys
import time
from . import session, camera, audio, screenshare, presentation, mixer

def greenlight_join(url, name, password):
    session = requests.session()

    html = session.get(url).text
    try:
        room = html.split('room="')[1].split('"')[0]
        authenticity_token = html.split('name="authenticity_token"')[1].split('"')[1]
        if not room or not authenticity_token:
            raise Exception()
    except:
        raise Exception("Unable to access greenlight frontend (incorrect url?)")

    if '"room[access_code]"' in html:
        if not password:
            raise Exception("Given greenlight room requires a password but none was provided")
        try:
            html = session.post(url + "/login", data={'authenticity_token': authenticity_token, 'room[access_code]': password}).text
            room = html.split('room="')[1].split('"')[0]
            authenticity_token = html.split('name="authenticity_token"')[1].split('"')[1]
            if not room or not authenticity_token:
                raise Exception()
        except:
            raise Exception("Access to greenlight room failed (invalid access code?)")

    try:
        req = session.post(url, allow_redirects=False, data={'authenticity_token': authenticity_token, '/b/' + room + '[join_name]': name})

        while 'Location' in req.headers and 'checksum' in req.headers['Location']:
            join_url = req.headers['Location']
            req = session.get(join_url, allow_redirects=False)

        return join_url
    except:
        raise Exception("Unable to acquire join URL (weird loadbalancing setup / non-standard paths?)")

def start(join_url, rtmp_url, background):
    sessionmanager = session.SessionManager(join_url)
    streammixer = mixer.Mixer(rtmp_url, background)
    audiostream = audio.Audio(sessionmanager, streammixer)
    cameramanager = camera.CameraManager(sessionmanager, streammixer)
    screenshareswitch = screenshare.Switcher(streammixer)
    presentationstream = presentation.Presentation(sessionmanager, screenshareswitch)
    screensharemanager = screenshare.ScreenshareManager(sessionmanager, screenshareswitch)

    def chatmsg(msg):
        if 'collection' not in msg or msg['collection'] != 'group-chat-msg':
            return
        print(msg['fields']['sender'] + ": " + msg['fields']['message'])

        txt = msg['fields']['message']
        if txt.startswith("!") and ' ' in txt:
            cmd, args = txt[1:].split(' ', 1)
            if cmd == 'view':
                streammixer.set_view(args)
    sessionmanager.attach(chatmsg)

    class MyShell(cmd.Cmd):
        prompt = '(bbb) '

        def do_keyframe(self, arg):
            for camera in cameramanager.cameras.values():
                camera.force_keyframe()

        def do_say(self, arg):
            timestamp = int(time.time())
            msg = {}
            msg['msg'] = 'method'
            msg['method'] = 'sendGroupChatMsg'
            msg['params'] = []
            msg['params'].append('MAIN-PUBLIC-GROUP-CHAT')
            msg['params'].append({'color': '0', 'correlationId': '%s-%d' % (sessionmanager.bbb_info['internalUserID'], timestamp), 'sender': {'id': sessionmanager.bbb_info['internalUserID'], 'name': sessionmanager.bbb_info['fullname']}, 'message': arg})
            msg['id'] = 'fnord-chat-%d' % timestamp
            sessionmanager.send(msg)

        def do_view(self, arg):
            streammixer.set_view(arg)

        def do_raw(self, arg):
            sessionmanager.send(json.loads(arg))

    try:
        MyShell().cmdloop()
    except:
        pass

    streammixer.stop()
