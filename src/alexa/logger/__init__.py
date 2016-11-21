#alexa/logger/log.py

import sys
import types
import logging
import traceback

from alexa.logger.terminal import *

class _AlexaCustomLogger:

	class ColorFormatter(logging.Formatter):
		FORMAT = ("%(asctime)s - [$BOLD%(name)-30s$RESET][%(levelname)-20s]" " %(message)s " "($BOLD%(filename)s$RESET:%(lineno)d)")

		def __init__(self, use_color=False):
			msg = self.format_formatter(self.FORMAT, use_color)
			logging.Formatter.__init__(self, msg)

			self._use_color = use_color
			self._fmt_modified = False

		def format_formatter(self, msg, use_color):
			if use_color:
				msg = msg.replace("$RESET", ESC_SEQ.RESET).replace("$BOLD", FORMAT.BOLD)
			else:
				msg = msg.replace("$RESET", "").replace("$BOLD", "")

			return msg

		def format(self, record):
			if self._fmt_modified:
				self._fmt = self.format_formatter(self.FORMAT, self._use_color)
				self._fmt_cleared = False

			levelname = record.levelname
			msg = record.msg

			# colorize and format logname
			if self._use_color and levelname in LOG_LEVEL_COLORS:
				record.levelname = str(LOG_LEVEL_COLORS[levelname]) + levelname + ESC_SEQ.RESET

			# colorize and format message...if msg is a str
			if isinstance(msg, basestring):
				if self._use_color:
					if msg.find('$$BLANK$$') > -1:
						self._fmt = ''
						self._fmt_modified = True

					elif msg.find('$$LOG_START$$') > -1:
						self._fmt = '%(message)s'
						msg =           '\n\n\n\n\n$GREEN$BOLD ########################################################## \n' + \
								'##                                                        ##\n' + \
								'##              $RESETALEXA LOGGING STARTING...$GREEN$BOLD                 ##\n' + \
								'##                                                        ##\n' + \
								' ##########################################################$RESET\n\n\n\n\n'
						self._fmt_modified = True

					# parse colors/formats TODO: fix BG
					for k,v in COLOR_FORMATS.iteritems():
						#print '-->' + k,v()
						msg = msg.replace("$" + k, str(v)) \
						.replace("$BG" + k,  str(v)) \
						.replace("$BG-" + k, str(v))

					# parse formats
					msg = msg.replace("$RESET", ESC_SEQ.RESET) \
					.replace("$BOLD", FORMAT.BOLD) \
					.replace("$ITALICS", FORMAT.ITALICS) \
					.replace("$UNDERLINE", FORMAT.UNDERLINE) \
					.replace("$STRIKETHROUGH", FORMAT.STRIKETHROUGH)

				else:
					for k,v in terminal.color.COLORS.iteritems():
						msg = msg.replace("$" + k, '') \
						.replace("$BG" + k,  '') \
						.replace("$BG-" + k, '')

					msg = msg.replace("$RESET", '') \
					.replace("$BOLD", '') \
					.replace("$ITALICS", '') \
					.replace("$UNDERLINE", '') \
					.replace("$STRIKETHROUGH", '') \
					.replace("$RESET", '') \
					.replace("$$BLANK$$", '$$BLANK$$') \
					.replace('$$LOG_START$$', '')

				record.msg = msg

			return logging.Formatter.format(self, record)

	def __init__(self):
		self._logger = logging.getLogger()
		self._logger.setLevel(logging.DEBUG)
		self._handler = logging.StreamHandler(sys.stdout)
		self._handler.setFormatter(self.ColorFormatter())
		self._logger.addHandler(self._handler)

	def _log_start(self, logger):
		logger.info('$$LOG_START$$')

	def _log_newline(self, logger):
		logger.info('$$BLANK$$')

	def setup(self, config, log_file):
		# clear current handlers
		for hdlr in self._logger.handlers[:]:  # remove all old handlers
			self._logger.removeHandler(hdlr)

		#if 'debug' in config:
		if log_file:
			if 'logFileLocation' in config['debug']:
				log_file_location =  config['debug']['logFileLocation']
			else:
				log_file_location = '/var/log/Alexa.log'

			# create a file handler
			handler = logging.FileHandler(log_file_location)
			print 'File logging {}enabled{}: Logging to {}{}{}'.format(FORMATS.BOLD, ESC_SEQ.RESET, FORMAT.ITALICS, log_file_location, ESC_SEQ.RESET)

		else:
			handler = logging.StreamHandler(sys.stdout)

		handler.setFormatter(self.ColorFormatter())
		self._set_logging(config, handler)

	def _set_logging(self, config, handler):
		if config and 'debug' in config:
			if 'alexa' in config['debug']:
				self._logger.setLevel(self._get_debug_level(config['debug']['alexa']))

			if 'hpack' in config['debug']:
				hpack_logger = logging.getLogger('hpack')
				hpack_logger.setLevel(self._get_debug_level(config['debug']['hpack']))

			else:
				hpack_logger = logging.getLogger('hpack')
				hpack_logger.setLevel(logging.CRITICAL)

			if 'hyper' in config['debug']:
				hyper_logger = logging.getLogger('hyper')
				hyper_logger.setLevel(self._get_debug_level(config['debug']['hyper']))
			else:
				hyper_logger = logging.getLogger('hyper')
				hyper_logger.setLevel(logging.CRITICAL)

			if 'requests' in config['debug']:
				hyper_logger = logging.getLogger('requests')
				hyper_logger.setLevel(self._get_debug_level(config['debug']['requests']))
			else:
				hyper_logger = logging.getLogger('requests')
				hyper_logger.setLevel(logging.CRITICAL)

			if 'colorize' in config['debug']:
				colorize = config['debug']['colorize']
				if colorize:
					handler.setFormatter(self.ColorFormatter(True))

		self._logger.addHandler(handler)

	def _get_debug_level(self, name):
		'''
		Level	Numeric value
		CRITICAL	50
		ERROR		40
		WARNING		30
		INFO		20
		DEBUG		10
		'''
		if name == 'critical':
			return logging.CRITICAL

		elif name == 'ERROR':
			return logging.ERROR

		elif name == 'warning':
			return logging.WARNING

		elif name == 'info':
			return logging.INFO

		elif name == 'debug':
			return logging.DEBUG

	def getLogger(self, name):
		log = logging.getLogger(name)
		setattr(log, 'newline', types.MethodType(self._log_newline, log))
		setattr(log, 'start', types.MethodType(self._log_start, log))

		def exception_hook(exc_type, exc_value, exc_traceback):
			log.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

		sys.excepthook = exception_hook

		return log

_logger = _AlexaCustomLogger() #Initialize logger

def setup(configuration, log_file):
	_logger.setup(configuration, log_file)

def getLogger(name):
	return _logger.getLogger(name)
