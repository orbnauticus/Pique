VERSION = '0.01'

import ConfigParser
import os
import signal
import sys

from common import *
from library import library as Library
from library import uri
from network import NetThread
from console import ConsoleThread
from player import Player
from playlist import Playlist
from gui import GUI
from keymap import KeyMap
from client import Client

class Main(object):
	def __init__(self):
		conf = ConfigParser.SafeConfigParser()
		conf.read(['./mcp.conf',os.path.expanduser('~/.mcp.conf')])
		
		self.lib = Library(os.path.expanduser(conf.get('Library', 'path')))
		self.playlist = Playlist()
		self.player = Player(conf, self.lib, self.playlist)
		self.gui = GUI()
		
		self.commandmap = {
			'quit': self.quit,
			'fullscreen': self.gui.toggle_fullscreen,
			'next': self.player.next,
			'play-pause': self.player.play_pause,
			'play': self.player.play,
			'pause': self.player.pause,
			'stop': self.player.stop,
			'previous': self.player.previous,
			'controls': self.gui.toggle_controls,
			'seek': lambda pos:self.player.seek(pos*SECOND, False),
			'forward-near': lambda:self.player.seek(15*SECOND, False),
			'forward-far': lambda:self.player.seek(60*SECOND, False),
			'beginning': lambda:self.player.seek(0, True),
			'end': lambda:self.player.seek(self.player.get_duration(), True),
			'back-near': lambda:self.player.seek(-15*SECOND, False),
			'back-far': lambda:self.player.seek(-60*SECOND, False),
			'volume-up': lambda:self.player.set_volume(.05, False),
			'volume-down': lambda:self.player.set_volume(-.05, False),
			'mute': lambda:self.player.set_volume(0, True),
			'menu': self.gui.toggle_menu,
			'show-menu': self.gui.show_menu,
			'hide-menu': self.gui.hide_menu,
			'playlist-add': self.playlist.add,
			'playlist-load': self.playlist.load,
			'playlist-clear': self.playlist.clear,
			'playlist-repeat': self.playlist.set_repeat,
			'playlist-random': self.playlist.set_random,
			'playlist-list': lambda:'\n'.join(self.playlist.entries),
		}
		
		self.keymap = KeyMap(conf, self.commandmap)
		self.server = NetThread(conf, self.commandmap)
		
		self.gui.connect('play-pause', self.player.play_pause)
		self.gui.connect('next', self.player.next)
		self.gui.connect('previous', self.player.previous)
		self.gui.connect('position', self.player.seek)
		#self.gui.connect('volume', self.player.set_volume)
		self.gui.connect('destroy', self.quit)
		self.gui.set_keymap(self.keymap)
		
		self.player.window = self.gui.videobox.movie_window
		self.player.connect('eos', self.on_eos)
		self.player.connect('error', self.on_error)
		self.player.connect('state-changed', self.gui.update_state)
		self.player.connect('update', self.gui.update_time)
		
		self.console = ConsoleThread()
		self.console.set_keymap(self.keymap)
		
	def start(self):
		self.server.start()
		self.console.start()
		self.player.start()
		self.gui.start()
		
	def quit(self):
		self.player.quit()
		self.gui.quit()
		self.console.quit()
		self.server.quit()
		
	def on_eos(self):
		debug('eos')
		self.player.next()
		
	def on_error(self, error):
		debug('Error:', *error)
		self.player.stop()
		
	def on_destroy(self, *args):
		self.quit()
		

