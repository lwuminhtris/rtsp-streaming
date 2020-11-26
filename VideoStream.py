class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
			self.maxFrameNum = 0
			self.dataArr = []
			data = self.file.read(5) # Get the framelength from the first 5 bits
			while data: 
				framelength = int(data)
		
				# Read the current frame
				self.dataArr += [self.file.read(framelength)]
				self.maxFrameNum += 1
				data = self.file.read(5)
		except:
			raise IOError
		
		self.frameNum = 0
		
	def nextFrame(self, backward):
		"""Get next frame."""
		if backward:
			self.frameNum -= 1
		else:
			self.frameNum += 1
		if self.frameNum <= self.maxFrameNum and self.frameNum > 0:
			return self.dataArr[self.frameNum - 1]
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	