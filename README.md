# BBB Streamer NG?

Makes a conference like this...

![](pics/before.jpg)

...streamable like this!

![](pics/after.jpg)

I also recorded a small video showing the basic features: https://www.youtube.com/watch?v=u9pTmzowIPc

Big Blue Button streaming without pressing a virtual camera against a remote controlled webbrowser..

Heavily work-in-progress, but kinda functional.

The whiteboard is definitively the hardest part to get right. Everything else just kinda depends on
gstreamer not breaking every 5 minutes :D

Example usage: `python main.py --greenlight-url https://example.org/b/my-cool-room --rtmp-url rtmp://server/app/path?auth=foobar`

Or alternatively with docker replace `python main.py` with `docker run -t -i --rm=true lukas2511/bbb-streaming` in the line above

Inside the `stuff` directory you'll find a tampermonkey script (probably also working with greasemonkey or by injecting directly into your
bbb backend) that adds four buttons to easily control scenes from within BBB :) Set `STREAM_USER` inside the script if you don't name your
streamer `stream`.

Working:

- Capturing audio
- Capturing all cameras
- Capturing screen captures
- Generating presentation canvas (including annotations) and converting it into an internal video stream
- Automatic switching between presentation and screenshare
- Simple side-by-side scene with exactly 1 active webcam and the presentation/screenshare
- Tracking camera of active speaker
- Background image for streams
- Selection of multiple scenes (side-by-side, fullscreen cam/presentation) using chat commands (`!view <sbs|pip|cam|pres>`)
- Support for 4:3 (and other weird) ratio inputs (resized to fit + transparent border)

Output is streamed using rtmp for now. How this is implemented will probably change.

Todo:

- Fixing the gstreamer webrtc video glitches (recovery on packetloss is b0rked, currently enabling slight fec and requesting a keyframe every second)
- Support different camera selections (follow-speaking/follow-presenter/manual selection)
- Lots of error handling + recovery foo
- Clean shutdown (some threads seem to be doing weird stuff :D)
- Finishing the todo list
