

void decode_frame(state ,scanline_idx,num_scanlines,scanline_size,scanline_header_size,curr_sc,scanline_header,scanline_data){
        for byte in data:
            # process scanline bytes
            if state == self.SC_DATA:
                scanline_data.append(byte);
                # if we finished current scanline bytes, update scanline index
                if len(scanline_data) == scanline_size:
                    scanline_idx +=1
                    curr_sc['data'] = scanline_data
                    self.scanlines.put(curr_sc)
                    # keep a fixed amount of scanlines in the queue
                    if self.scanlines.qsize()>= self.max_scanlines:
                        self.scanlines.get()
                    state = self.SC_START_HEADER
                    # we are DONE!
                    if scanline_idx == num_scanlines:
                        state = self.FR_WAIT
                        scanline_idx = 0
                        num_scanlines=-1
            # process scanline header bytes
            elif state == self.SC_HEADER:
                scanline_header.append(byte);
                #print "header: %s size %s"%(scanline_header,scanline_header_size)
                # if we got the full header, extract the data
                if len(scanline_header) == scanline_header_size:
                    curr_sc['status'] = ord(scanline_header[1])
                    curr_sc['index'] = ord(scanline_header[2]) | ord(scanline_header[4])<<8
                    curr_sc['angle'] = ord(scanline_header[8]) | ord(scanline_header[9])<<8
                    curr_sc['scale'] = ord(scanline_header[12]) | ord(scanline_header[13])<<8
                    curr_sc['time'] = time.time()
                    state = self.SC_DATA
            # check if we have a valid header (i.e. starting with 01 00 00 00 00)
            elif state <= self.FR_START_DONE: 
                if byte == self.FRAME_START_SEQUENCE[state]:
                   state += 1
                else:
                   state = self.FR_WAIT
            # we got a good header, get number of scan lines
            elif state == self.FR_N_SCANLINE:
                num_scanlines = ord(byte)
                if num_scanlines == 0:
                    state = self.FR_WAIT
                    scanline_idx = 0
                    num_scanlines=-1
                    break

                state = self.FR_L_SCANLINE
                # reset scanline indices
                scanline_size = []
            # and get the scan line size
            elif state == self.FR_L_SCANLINE:
                scanline_size.append(byte)
                if len(scanline_size) == 2:
                    scanline_size = ord(scanline_size[0]) | ord(scanline_size[1])<<8
                    # start processing scanlines
                    state = self.SC_START_HEADER
                    scanline_idx = 0
            #get scanline header size
            elif state == self.SC_START_HEADER:
                    curr_sc = {}
                    scanline_header = []
                    scanline_data = []
                    scanline_header_size = ord(byte)
                    scanline_header.append(byte)
                    state = self.SC_HEADER
                    if scanline_header_size == 0:
                        state = self.FR_WAIT
                        scanline_idx = 0
                        num_scanlines=-1
                        break
        
        self.restore_from_local_copy(state,scanline_idx,num_scanlines,scanline_size,scanline_header_size,curr_sc,scanline_header,scanline_data)
