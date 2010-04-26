import sys
args,sys.argv = sys.argv,[]

import pygst
pygst.require('0.10')
import gst
import gobject

sys.argv = args

import time
import traceback

from common import *
from thread import BgThread

Element = gst.element_factory_make
def Bin(*elements):
	bin = gst.Bin()
	if len(elements):
		bin.add(*elements)
		if len(elements)-1:
			gst.element_link_many(*elements)
		for t,d,i in (('sinks',gst.PAD_SINK,0),('srcs',gst.PAD_SRC,-1)):
			j = 0
			for pad in elements[i].pads():
				if pad.props.direction == d:
					bin.add_pad(gst.GhostPad(t[:-1] + str(j), pad))
					j+=1
	return bin
	
def GstError(error, debug):
	if error.domain == 'gst-resource-error-quark':
		if error.code == 3:
			return IOError(debug.split('\n',1)[1])
	return Exception(error.code, error.domain, error.message, debug)
	
class PlayThread(BgThread):
	def main(self, update, frequency=0.1):
		while True:
			update()
			time.sleep(frequency)

STATE_PLAYING = 'playing'
STATE_PAUSED = 'paused'
STATE_STOPPED = 'stopped'

class Player(object):
	def __init__(self, config, lib, pl):
		self.lib = lib
		
		self.taginject = Element('taginject')
		audio_sink = Element(config.get('Gstreamer', 'audio-plugin'))
		self.audio_bin = Bin(self.taginject, Element('rgvolume'), audio_sink)
		
		self.video_sink = Element(config.get('Gstreamer', 'video-plugin'))
		self.video_sink.set_property('force-aspect-ratio', True)
		
		self.player = Element('playbin')
		self.player.set_property('audio-sink', self.audio_bin)
		self.player.set_property('video-sink', self.video_sink)
		self.player.set_property('vis-plugin', Element(config.get('Gstreamer','vis-plugin')))
		
		self.playlist = pl
		
		self._window = None
		self.bus.add_signal_watch()
		self.bus.enable_sync_message_emission()
		
		self.last_update = ()
		self.updatethread = PlayThread(self.emit_update, 0.1)
		
	def start(self):
		self.updatethread.start()
		self.next()
		
	def quit(self):
		self.stop()
		
	def emit_update(self):
		try:
			pos, dur = self.get_position(), self.get_duration()
			if (pos,dur) != self.last_update:
				self.last_update = pos,dur
				struct = gst.structure_from_string('update,position=(gint64)%d,duration=(gint64)%d' % (pos,dur))
				m = gst.message_new_custom(gst.MESSAGE_APPLICATION, self.player, struct)
				self.bus.post(m)
		except:
			traceback.print_exc()
		
	@property
	def bus(self):
		return self.player.get_bus()
		
	@property
	def window(self):
		return self._window
	@window.setter
	def window(self, w):
		if self._window is not None:
			self._window.disconnect(self._window_handler)
		self._window = w
		self._window_handler = self._window.connect('expose-event', self.refresh_xid)
		
	def refresh_xid(self, widget=None, event=None):
		if self._window is not None:
			self.video_sink.set_xwindow_id(self._window.window.xid)
			
	def on_state_changed(self, bus, message, callback, *args):
		_, new, _ = message.parse_state_changed()
		if new == gst.STATE_PLAYING:
			callback(STATE_PLAYING, *args)
		elif new == gst.STATE_NULL:
			callback(STATE_STOPPED, *args)
		elif new == gst.STATE_PAUSED:
			callback(STATE_PAUSED, *args)
			
	def on_update(self, bus, message, cb):
		func, args, kwargs = cb
		pos = message.structure['position']
		dur = message.structure['duration']
		return func(pos, dur, *args, **kwargs)
		
	def connect(self, which, func, *args, **kwargs):
		if which == 'state-changed':
			self.bus.connect('message::state-changed', self.on_state_changed, func, *args)
		elif which == 'update':
			self.bus.connect('message::application', self.on_update, (func, args, kwargs))
		else:
			self.bus.connect('message::%s' % which, func, *args)
	
	def seek(self, new, absolute=True):
		if not absolute:
			new = max(0, new + self.get_position(percent=percent))
		debug('seek', new)
		self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, new)
	
	def isplaying(self):
		return self.player.get_state()[1] == gst.STATE_PLAYING
			 
	def play_pause(self):
		if self.isplaying():
			self.pause()
		else:
			self.play()
		
	def play(self):
		debug('play')
		self.player.set_state('playing')
		self.refresh_xid()
		
	def pause(self):
		debug('pause')
		self.player.set_state('paused')
		
	def stop(self):
		debug('stop')
		self.player.set_state('null')
		
	def get_volume(self):
		return self.player.get_property('volume')
		
	def set_volume(self, level, absolute=True):
		if not absolute:
			level = max(0, min(1, self.get_volume() + level))
		self.player.set_property('volume', level)
		
	def get_position(self, percent=False):
		try:
			return max(0, self.player.query_position(gst.FORMAT_PERCENT if percent else gst.FORMAT_TIME, None)[0])
		except gst.QueryError:
			return 0
		
	def get_duration(self):
		try:
			return max(0, self.player.query_duration(gst.FORMAT_TIME, None)[0])
		except gst.QueryError:
			return 0
		
	def previous(self):
		debug('previous')
		pos = self.get_position()
		self.stop()
		if pos < 3 * gst.SECOND:
			try:
				self.load(self.playlist.previous())
			except StopIteration:
				return
		self.play()
		
	def next(self):
		debug('next')
		self.stop()
		try:
			self.load(self.playlist.next())
		except StopIteration:
			return
		self.play()
			
	def load(self, uri):
		debug('load', uri)
		tags = self.lib[uri]._asdict()
		self.player.set_property('uri', uri)
		rgtags = 'replaygain-reference-level','replaygain-track-gain','replaygain-track-peak'
		self.taginject.props.tags = ','.join(['%s=%s' % (k,tags[k.replace('-','_')]) for k in rgtags])
		
