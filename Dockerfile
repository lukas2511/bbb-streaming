FROM archlinux
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm python python-requests python-cairo librsvg python-websockets gst-plugins-bad gst-plugins-base gst-plugins-good gst-plugins-ugly gst-python gstreamer && \
    rm -rf /var/cache/pacman/pkg
ADD src/ /opt/stream/
ENTRYPOINT ["/opt/stream/test.py"]
