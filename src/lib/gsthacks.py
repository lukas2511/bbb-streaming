from ctypes import *
from contextlib import contextmanager

class GstMapInfo(Structure):
    _fields_ = [("memory", c_void_p),        # GstMemory *memory
                ("flags", c_int),            # GstMapFlags flags
                ("data", POINTER(c_byte)),   # guint8 *data
                ("size", c_size_t),          # gsize size
                ("maxsize", c_size_t),       # gsize maxsize
                ("user_data", c_void_p * 4), # gpointer user_data[4]
                ("_gst_reserved", c_void_p * 4)]

libgst = CDLL("libgstreamer-1.0.so.0")

GST_MAP_INFO_POINTER = POINTER(GstMapInfo)

# gst_buffer_map
libgst.gst_buffer_map.argtypes = [c_void_p, GST_MAP_INFO_POINTER, c_int]
libgst.gst_buffer_map.restype = c_int

# gst_buffer_unmap
libgst.gst_buffer_unmap.argtypes = [c_void_p, GST_MAP_INFO_POINTER]
libgst.gst_buffer_unmap.restype = None

# gst_mini_object_is_writable
libgst.gst_mini_object_is_writable.argtypes = [c_void_p]
libgst.gst_mini_object_is_writable.restype = c_int

def map_gst_buffer(pbuffer, flags):
    if pbuffer is None:
        raise TypeError("Cannot pass NULL to map_gst_buffer")

    ptr = hash(pbuffer)
    if flags & 2 and libgst.gst_mini_object_is_writable(ptr) == 0:
        raise ValueError("Writable array requested but buffer is not writeable")

    mapping = GstMapInfo()
    success = libgst.gst_buffer_map(ptr, mapping, flags)

    if not success:
        raise RuntimeError("Couldn't map buffer")

    try:
        # Cast POINTER(c_byte) to POINTER to array of c_byte with size mapping.size
        # Returns not pointer but the object to which pointer points
        return cast(mapping.data, POINTER(c_byte * mapping.size)).contents
    finally:
        libgst.gst_buffer_unmap(ptr, mapping)
