from tkinter import *
import tkinter.messagebox
from tkinter import messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os, time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	SPEEDUP = False
	BACKWARDING = False

	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	SPEEDING = 4
	NORMAL = 5
	BACKWARD = 6
	FORWARD = 7
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		#SETUP when create client
		self.setupMovie()
		self.frameLost = 0
		self.statExpRtpNb = 0
		self.statTotalFrames = 0
		self.statFrameRate = 0
		self.statTotalPlayTime = 0

	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create Info button
		self.info = Button(self.master, width=20, padx=3, pady=3)
		self.info["text"] = "Info"
		self.info["command"] =  self.showInfo
		self.info.grid(row=1, column=4, padx=2, pady=2)

		# Create speedUp button
		self.speedUp = Button(self.master, width=20, padx=3, pady=3)
		self.speedUp["text"] = "Speed up"
		self.speedUp["command"] =  self.makeSpeedUp
		self.speedUp.grid(row=2, column=4, padx=2, pady=2)

		# Create backward button
		self.backward = Button(self.master, width=20, padx=3, pady=3)
		self.backward["text"] = "Backward"
		self.backward["command"] =  self.makeBackward
		self.backward.grid(row=3, column=4, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height = 19)
		self.label.grid(row=0, column=0, columnspan=5, sticky=W+E+N+S, padx=5, pady=5) 
	
		#statlable
		self.statLabel1 = Label(self.master, height = 3, width = 20)
		self.statLabel1.grid(row = 2, column = 0,sticky=W+E+N+S, padx=5, pady=5)
		self.statLabel2 = Label(self.master, height = 3, width = 20)
		self.statLabel2.grid(row = 2, column = 1,sticky=W+E+N+S, padx=5, pady=5)
		self.statLabel3 = Label(self.master, height = 3, width = 20)
		self.statLabel3.grid(row = 2, column = 2, columnspan = 2, sticky=W+E+N+S, padx=5, pady=5)

	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)

	def showInfo(self):
		"""show info"""
		self.check = FALSE;
		if self.state == self.PAUSE:
			self.check = TRUE
		info = "Filemane: " + self.fileName + "\nRTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nTransport: RTP/UDP\nclient_port= " + str(self.rtpPort) + '\nSession: ' + str(self.sessionId)
		self.pauseMovie()
		messagebox.showinfo("Info",info)
		if self.check:
			self.playMovie()

	def makeSpeedUp(self):
		if self.state == self.PLAYING:
			if self.SPEEDUP:
				self.speedUp.configure(text = 'Speed up')
				self.sendRtspRequest(self.NORMAL)
				self.SPEEDUP = False
			else:
				self.speedUp.configure(text = 'Normal')
				self.sendRtspRequest(self.SPEEDING)
				self.SPEEDUP = True

	def makeBackward(self):
		if self.BACKWARDING:
			self.backward.configure(text = 'Backward')
			self.sendRtspRequest(self.FORWARD)
			self.BACKWARDING = False
		else:
			self.backward.configure(text = 'Forward')
			self.sendRtspRequest(self.BACKWARD)
			self.BACKWARDING = True

	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			self.statStartTime = time.perf_counter_ns()
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
				
					currFrameNbr = rtpPacket.seqNum()
					#print("Current Seq Num: " + str(currFrameNbr))

					self.curTime = time.perf_counter_ns() #get current time
					if abs(currFrameNbr - self.frameNbr) != 1:
						 self.frameLost += 1
					if currFrameNbr != self.frameNbr: # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
					self.statTotalPlayTime = self.statTotalPlayTime + (self.curTime - self.statStartTime) #cal total play time
					self.statStartTime =  self.curTime

					self.statExpRtpNb = self.statExpRtpNb + 1 #Num of Frame get
					#if currFrameNbr - self.statExpRtpNb != self.frameLost:
					#	self.frameLost = self.frameLost + 1 #increase number of lost frame if there are more frames lost
					
					
					#get frame rate

					if self.statTotalPlayTime == 0 :
						self.statFrameRate =  0
					else:
						self.statFrameRate = self.statTotalFrames / (self.statTotalPlayTime / 1000000000.0)
					self.statFractionLost = self.frameLost / (self.statExpRtpNb + self.frameLost);
					self.statTotalFrames = self.statTotalFrames + 1;
					self.updateStatsLabel();


			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
			

	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = f"SETUP {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nTransport RTP/UDP; client_port= {self.rtpPort}"

			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.SETUP
		
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1

			# Write the RTSP request to be sent.
			# request = ...
			request = f"PLAY {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PLAY
		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = f"PAUSE {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PAUSE
		elif requestCode == self.SPEEDING and not self.state == self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = f"SPEEDUP {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
		elif requestCode == self.NORMAL and not self.state == self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = f"NORMAL {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
		elif requestCode == self.BACKWARD and not self.state == self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = f"BACKWARD {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
		elif requestCode == self.FORWARD and not self.state == self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = f"FORWARD {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"

		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = f"TEARDOWN {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"			
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.TEARDOWN
		else:
			return
		
		# Send the RTSP request using rtspSocket.
		# ...
		self.rtspSocket.send(request.encode())
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break

	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						#-------------
						# TO COMPLETE
						#-------------
						# Update RTSP state.
						# self.state = ...
						self.state = self.READY
						# Open RTP port.
						self.openRtpPort() 
					elif self.requestSent == self.PLAY:
						# self.state = ...
						self.state=self.PLAYING
					elif self.requestSent == self.PAUSE:
						# self.state = ...
						self.state=self.READY

						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						# self.state = ...
						self.state=self.INIT
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		# self.rtpSocket = ...
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Set the timeout value of the socket to 0.5sec
		# ...
		self.rtpSocket.settimeout(0.5)

		try:
			# Bind the socket to the address using the RTP port given by the client user
			# ...
			self.state = self.READY
			self.rtpSocket.bind(('',self.rtpPort))
		except:
			messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
	def updateStatsLabel(self):
		self.statLabel1.configure(text = 'Total Frames Received: ' + str(self.statTotalFrames))
		self.statLabel2.configure(text = "Packet Lost Rate: " + str("{:0.3f}".format(self.statFractionLost)))
		self.statLabel3.configure(text = "Frame Rate: " + str("{:0.3f}".format(self.statFrameRate)) + " frames/s")