#!/usr/bin/env python3

import argparse
from lib import run
import logging

logging.basicConfig()
log = logging.getLogger('bbb-streamer')

def main():
    argp = argparse.ArgumentParser(allow_abbrev=False)

    argp.add_argument("--debug", help="Print debug log", action='store_true')
    argp.add_argument("--background", help="Background image, either direct file path or via http/https URL")

    jnurlgroup = argp.add_argument_group('URL', 'Join using fully prepared API join URL')
    jnurlgroup.add_argument("--join-url", help="Fully prepared API join URL, e.g. https://bbb.example.org/bigbluebutton/api/join?...")

    glgroup = argp.add_argument_group('Greenlight', 'Join using Greenlight Frontend')
    glgroup.add_argument("--greenlight-url", help="Greenlight URL, e.g. https://bbb.example.org/gl/my-cool-room")
    glgroup.add_argument("--greenlight-name", help="Name for stream user", default="stream")
    glgroup.add_argument("--greenlight-password", help="Greenlight password for protected rooms")

    argp.add_argument("--rtmp-url", help="Output RTMP URL, e.g. rtmp://example.org/app/stream?auth=key", required=True)

    args = argp.parse_args()

    if sum([0 if x is None else 1 for x in [args.join_url, args.greenlight_url]]) != 1:
        argp.error("Exactly one of --join-url/--greenlight-url is required")

    if args.debug:
        log.setLevel(logging.DEBUG)

    if args.join_url:
        log.info("Joining using prepared API join URL")
        join_url = args.join_url
    elif args.greenlight_url:
        log.info("Joining using Greenlight frontend")
        join_url = run.greenlight_join(args.greenlight_url, args.greenlight_name, args.greenlight_password)

    run.start(join_url=join_url, rtmp_url=args.rtmp_url, background=args.background)

if __name__ == '__main__':
    main()
