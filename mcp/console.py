import thread
import rawtty

class ConsoleThread(thread.BgThread):
	name = 'ConsoleThread'
	dependencies = ('mcp.keymap.KeyMap',)
	def connect(self, key, func, *args, **kwargs):
		self.keymap[key] = func,args,kwargs
		
	def on_dep_available(self, name, dep):
		if name == 'mcp.keymap.KeyMap':
			self.handler = dep.interpret
		
	def init(self):
		self.rawtty = rawtty.rawtty(timeout=0.3, quit='eof')
		
	def start(self):
		self.rawtty.start()
		thread.BgThread.start(self)
	
	def main(self, confitems):
		try:
			for key in self.rawtty:
				self.handler(key)
		except KeyboardInterrupt:
			self.handler('quit')
		finally:
			print 'done'
		
	def quit(self):
		self.rawtty.restore()
