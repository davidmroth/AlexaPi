#! /usr/bin/env python

import re
import os
import cgi
import sys
import time
import json
import wave
import email
import getch
import tunein
import random
import datetime
import requests
import alsaaudio
import fileinput
import webrtcvad
import traceback

from pocketsphinx import get_model_path
from pocketsphinx.pocketsphinx import *
from sphinxbase.sphinxbase import *

from alexapi.avs.interface_manager import InterfaceManager
import alexapi.shared as shared
import alexapi.player.player as player
import alexapi.player.player_state as pstate
import alexapi.exit_handler as exit_handler

#Setup
recorded = False
path = os.path.realpath(__file__).rstrip(os.path.basename(__file__))
resources_path = os.path.join(path, 'resources', '')

# PocketSphinx configuration
ps_config = Decoder.default_config()

# Set recognition model to US
ps_config.set_string('-hmm', os.path.join(get_model_path(), 'en-us'))
ps_config.set_string('-dict', os.path.join(get_model_path(), 'cmudict-en-us.dict'))

#Specify recognition key phrase
ps_config.set_string('-keyphrase', shared.config['sphinx']['trigger_phrase'])
ps_config.set_float('-kws_threshold',1e-5)

# Hide the VERY verbose logging information
ps_config.set_string('-logfn', '/dev/null')

# Process audio chunk by chunk. On keyword detected perform action and restart search
decoder = Decoder(ps_config)

#Variables
button_pressed = False
start = time.time()
tunein_parser = tunein.TuneIn(5000)
vad = webrtcvad.Vad(2)
http = False
exit = False

# constants
VAD_SAMPLERATE = 16000
VAD_FRAME_MS = 30
VAD_PERIOD = (VAD_SAMPLERATE / 1000) * VAD_FRAME_MS
VAD_SILENCE_TIMEOUT = 1000
VAD_THROWAWAY_FRAMES = 10
MAX_RECORDING_LENGTH = 8
MAX_VOLUME = 100
MIN_VOLUME = 30


def alexa_speech_recognizer():
	# https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/rest/speechrecognizer-requests
	if shared.debug: print("{}Sending Speech Request...{}".format(shared.bcolors.OKBLUE, shared.bcolors.ENDC))
	avs_interface.send_event('SpeechRecognizer', 'Recognize')

def detect_button(channel):
        global button_pressed
        buttonPress = time.time()
        button_pressed = True
        if shared.debug: print("{}Button Pressed! Recording...{}".format(shared.bcolors.OKBLUE, shared.bcolors.ENDC))
        time.sleep(.5) # time for the button input to settle down
        while (shared.get_button_status() == 0):
                button_pressed = True
                time.sleep(.1)
                if time.time() - buttonPress > 10: # pressing button for 10 seconds triggers a system halt
			player.play_avr(resources_path+'alexahalt.mp3')
			if shared.debug: print("{} -- 10 second putton press.  Shutting down. -- {}".format(shared.bcolors.WARNING, shared.bcolors.ENDC))
			os.system("halt")
        if shared.debug: print("{}Recording Finished.{}".format(shared.bcolors.OKBLUE, shared.bcolors.ENDC))
        button_pressed = False
        time.sleep(.5) # more time for the button to settle down

def silence_listener(throwaway_frames):
		global button_pressed
		# Reenable reading microphone raw data
		inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, shared.config['sound']['device'])
		inp.setchannels(1)
		inp.setrate(VAD_SAMPLERATE)
		inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
		inp.setperiodsize(VAD_PERIOD)
		audio = ""


		# Buffer as long as we haven't heard enough silence or the total size is within max size
		thresholdSilenceMet = False
		frames = 0
		numSilenceRuns = 0
		silenceRun = 0
		start = time.time()

		# do not count first 10 frames when doing VAD
		while (frames < throwaway_frames): # VAD_THROWAWAY_FRAMES):
			l, data = inp.read()
			frames = frames + 1
			if l:
				audio += data
				isSpeech = vad.is_speech(data, VAD_SAMPLERATE)

		# now do VAD
		while button_pressed == True or ((thresholdSilenceMet == False) and ((time.time() - start) < MAX_RECORDING_LENGTH)):
			l, data = inp.read()
			if l:
				audio += data

				if (l == VAD_PERIOD):
					isSpeech = vad.is_speech(data, VAD_SAMPLERATE)

					if (isSpeech == False):
						silenceRun = silenceRun + 1
						#print "0"
					else:
						silenceRun = 0
						numSilenceRuns = numSilenceRuns + 1
						#print "1"

			# only count silence runs after the first one
			# (allow user to speak for total of max recording length if they haven't said anything yet)
			if (numSilenceRuns != 0) and ((silenceRun * VAD_FRAME_MS) > VAD_SILENCE_TIMEOUT):
				thresholdSilenceMet = True
			shared.led.rec_on()

		if shared.debug: print ("Debug: End recording")

		# if shared.debug: player.play_avr(resources_path+'beep.wav', 0, 100)

		shared.led.rec_off()
		rf = open(shared.tmp_path + 'recording.wav', 'w')
		rf.write(audio)
		rf.close()
		inp.close()

def start():
	global vad, button_pressed
	shared.Button(detect_button)

	while True:
		record_audio = False

		# Enable reading microphone raw data
		inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, shared.config['sound']['device'])
		inp.setchannels(1)
		inp.setrate(16000)
		inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
		inp.setperiodsize(1024)
		start = time.time()

		decoder.start_utt()

                while record_audio == False:

			time.sleep(.1)

			# Process microphone audio via PocketSphinx, listening for trigger word
			while decoder.hyp() == None and button_pressed == False:
				# Read from microphone
				l,buf = inp.read()
				# Detect if keyword/trigger word was said
				decoder.process_raw(buf, False, False)

			# if trigger word was said
			if decoder.hyp() != None:
				if player.is_avr_playing():
					player.stop_avr()
					time.sleep(.5) #add delay before audio prompt

				if player.is_media_playing():
					player.stop_media_player()
					time.sleep(.5) #add delay before audio prompt

				start = time.time()
				record_audio = True
				player.play_avr(resources_path+'alexayes.mp3', 0)
			elif button_pressed:
				if player.is_avr_playing or player.is_media_playing(): player.stop_media_player()
				record_audio = True

		# do the following things if either the button has been pressed or the trigger word has been said
		if shared.debug: print ("detected the edge, setting up audio")

		# To avoid overflows close the microphone connection
		inp.close()

		# clean up the temp directory
		if shared.debug == False:
			for file in os.listdir(shared.tmp_path):
				file_path = os.path.join(shared.tmp_path, file)
				try:
					if os.path.isfile(file_path):
						os.remove(file_path)
				except Exception as e:
					print(e)

		if shared.debug: print "Starting to listen..."
		silence_listener(VAD_THROWAWAY_FRAMES)

		if shared.debug: print "Debug: Sending audio to be processed"
		alexa_speech_recognizer()

		# Now that request is handled restart audio decoding
		decoder.end_utt()

def setup():
	global avs_interface, exit
	exit = exit_handler.CleanUp()

	#hardware = hadware.Somthing() #Initialize hardware
	avs_interface = InterfaceManager()
	#player.setup(alexa_playback_progress_report_request, alexa_getnextitem, tuneinplaylist)
	if (shared.silent == False): player.play_avr(resources_path+"hello.mp3")

if __name__ == "__main__":
	try:
		setup()
		start()

	except:
		exc_type, exc_value, exc_traceback = sys.exc_info()
		lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
		print ''.join('!! ' + line for line in lines)  # Log it or whatever here

	finally:
		exit.cleanup()
