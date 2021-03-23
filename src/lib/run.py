#!/usr/bin/env python3

import requests
import cmd
import json
import sys
import time
from . import session, camera, audio, screenshare, presentation, mixer

import logging
log = logging.getLogger('bbb-streamer')

def greenlight_join(url, name, password):
    log.debug("Trying to acquire join url from greenlight: %s (%s access code)" % (url, 'with' if password else 'without'))

    session = requests.session()
    html = session.get(url).text

    if 'name="authenticity_token"' not in html:
        raise Exception("Greenlight authenticity token not found (layout changed?)")
    authenticity_token = html.split('name="authenticity_token"')[1].split('"')[1]

    if '"room[access_code]"' in html:
        if not password:
            raise Exception("Greenlight room requires an access code but none was provided")
        html = session.post(url + "/login", data={'authenticity_token': authenticity_token, 'room[access_code]': password}).text
        if '"room[access_code]"' in html:
            raise Exception("Greenlight access code seems to be invalid")

        if 'name="authenticity_token"' not in html:
            raise Exception("Greenlight authenticity token not found after providing access code (layout changed? invalid access code?)")

        authenticity_token = html.split('name="authenticity_token"')[1].split('"')[1]

    if 'room="' not in html:
        raise Exception("Greenlight room name not found (layout changed?)")
    room = html.split('room="')[1].split('"')[0]

    req = session.post(url, allow_redirects=False, data={'authenticity_token': authenticity_token, '/b/' + room + '[join_name]': name})

    if ('join-name="%s"' % name) in req.text:
        raise Exception("Greenlight room is closed and is not set up to auto-open")

    if 'Location' not in req.headers:
        raise Exception("Greenlight is not redirecting to BBB, something has gone wrong")

    while 'Location' in req.headers and 'checksum' in req.headers['Location']:
        join_url = req.headers['Location']
        req = session.get(join_url, allow_redirects=False)

    return join_url

def start(join_url, rtmp_url, background):
    sessionmanager = session.SessionManager(join_url)
    streammixer = mixer.Mixer(rtmp_url, background)
    audiostream = audio.Audio(sessionmanager, streammixer)
    cameramanager = camera.CameraManager(sessionmanager, streammixer)
    screenshareswitch = screenshare.Switcher(streammixer)
    presentationstream = presentation.Presentation(sessionmanager, screenshareswitch)
    screensharemanager = screenshare.ScreenshareManager(sessionmanager, screenshareswitch)

    def sendmsg(txt, chatid='MAIN-PUBLIC-GROUP-CHAT'):
        timestamp = int(time.time())
        msg = {}
        msg['msg'] = 'method'
        msg['method'] = 'sendGroupChatMsg'
        msg['params'] = []
        msg['params'].append(chatid)
        msg['params'].append({'color': '0', 'correlationId': '%s-%d' % (sessionmanager.bbb_info['internalUserID'], timestamp), 'sender': {'id': sessionmanager.bbb_info['internalUserID'], 'name': sessionmanager.bbb_info['fullname']}, 'message': txt})
        msg['id'] = 'fnord-chat-%d' % timestamp
        sessionmanager.send(msg)

    def chatmsg(msg):
        if 'collection' not in msg:
            return

        if msg['collection'] == 'group-chat':
            rply = {}
            rply['msg'] = 'sub'
            rply['name'] = 'group-chat-msg'
            rply['params'] = [[msg['fields']['chatId']]]
            rply['id'] = 'fnord-group-' + msg['fields']['chatId']
            sessionmanager.send(rply)

        elif msg['collection'] == 'group-chat-msg':
            if msg['fields']['sender'] == sessionmanager.bbb_info['internalUserID']:
                return

            txt = msg['fields']['message']
            sender = sessionmanager.get_user_by_internal_id(msg['fields']['sender'])
            if not sender:
                return

            print("%s (%s,%s): %s" % (sender['name'], sender['role'], 'PUBLIC' if msg['fields']['chatId'] == 'MAIN-PUBLIC-GROUP-CHAT' else 'PRIVATE', txt))
            if sender['role'] != 'MODERATOR':
                if msg['fields']['chatId'] != 'MAIN-PUBLIC-GROUP-CHAT':
                    sendmsg('You have no permissions to use this command', msg['fields']['chatId'])
                return

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
            sendmsg(arg)

        def do_view(self, arg):
            streammixer.set_view(arg)

        def do_raw(self, arg):
            sessionmanager.send(json.loads(arg))

    try:
        MyShell().cmdloop()
    except:
        pass

    streammixer.stop()
