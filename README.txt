# BBB Streamer NG?

Big Blue Button streaming without pressing a virtual camera against a remote controlled webbrowser..

Heavily work-in-progress, only partially functional.

The whiteboard is definitively the hardest part to get right. Everything else just kinda depends on
gstreamer not breaking every 5 minutes :D

Working:

- Capturing audio
- Capturing all cameras
- Capturing screen captures
- Generating presentation canvas (including annotations) and converting it into an internal video stream
- Automatic switching between presentation and screenshare
- Simple side-by-side scene with exactly 1 active webcam and the presentation/screenshare

Output is muxed as matroska and sent to tcp localhost port 10000.

Todo:

- Fixing the gstreamer webrtc video glitches (recovery on packetloss is b0rked, worst case should be able to just drop UDP ice candidates...)
- Support multiple (or no) cameras / Camera selection
- Selection of multiple scenes (side-by-side, fullscreen cam/presentation)
- Background for streams with whitespace
- Control via chat commands for easy integration?
- Lots of error handling + recovery foo
- Finishing the todo list
