#!/usr/bin/env python3

from lib import session
from lib import camera
from lib import audio
from lib import screenshare
from lib import presentation
from lib import mixer

import cmd
import json
import sys
import time

join_url = session.greenlight_join(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'stream')
sessionmanager = session.SessionManager(join_url)
sessionmanager.daemon = True
sessionmanager.start()

streammixer = mixer.Mixer()

cameramanager = camera.CameraManager(sessionmanager, streammixer)
#screensharemanager = screenshare.ScreenshareManager(sessionmanager, streammixer)
#audiostream = audio.Audio(sessionmanager)
#audiostream.start()

presentationstream = presentation.Presentation(sessionmanager, streammixer)

def chatmsg(msg):
    if 'collection' not in msg or msg['collection'] != 'group-chat-msg':
        return
    print(msg['fields']['sender'] + ": " + msg['fields']['message'])
sessionmanager.attach(chatmsg)

# just a test script to get control over the websocket
# doesn't do anything fancy yet

class MyShell(cmd.Cmd):
    prompt = '(bbb) '

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

    def do_source(self, arg):
        streammixer.source = arg

    def do_raw(self, arg):
        sessionmanager.send(json.loads(arg))

MyShell().cmdloop()
