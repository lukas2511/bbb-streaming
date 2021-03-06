# BBB Streamer NG?

Big Blue Button streaming without pressing a virtual camera against a remote controlled webbrowser..

Heavily work-in-progress, not yet functional.

Currently there is code to receive all webcams, screenshare, the conference audio,
and even some initial support for generating a video stream of the whiteboard including annotations.

The whiteboard is definitively the hardest part to get right. Everything else just kinda depends on
gstreamer not breaking every 5 minutes :D

At the moment all sources are simply displayed in their own windows or played back through system audio,
internal mixing and stream outputs are not yet implemented.
