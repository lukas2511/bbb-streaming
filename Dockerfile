FROM archlinux
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm python python-pillow python-requests python-cairo librsvg python-websockets gst-plugins-bad gst-plugins-base gst-plugins-good gst-plugins-ugly gst-python gstreamer && \
    rm -rf /var/cache/pacman/pkg
RUN useradd stream
USER stream
WORKDIR /opt/stream/
ADD src/ /opt/stream/
ENTRYPOINT ["/opt/stream/main.py"]
