#!/usr/bin/python

import traceback

raw_input('Press enter key to continue')

try:
	from mcp import *
	import mcp

	g = mcp.gui()
	g.run()
except KeyboardInterrupt:
	pass
except:
	traceback.print_exc()
finally:
	print

