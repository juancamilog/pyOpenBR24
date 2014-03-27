#!/usr/bin/env python
import socket
from multiprocessing import Process, Queue, Event
import signal
import sys
import yaml
from struct import pack as s_pack
import time
import binascii
import cProfile

# A utility class for multicast sockets
class multicast_socket(Process):
    def __init__(self, group_addr, group_port, data_q = None, buffer_size = 65536, name="", iface_ip=None):
        # set thread properties
        Process.__init__(self)
        self.alive = Event()
        self.alive.clear()
        self.daemon = True
        
        # set class attributes
        self.address = group_addr
        self.port = group_port
        self.buffer_size = buffer_size
        self.name = name
        self.data_q = data_q
        self.max_qsize = 512

        # init socket as inet udp multicast
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        group = socket.inet_aton(self.address)
        if iface_ip is None:
            mreq = s_pack('=4sl', group, socket.INADDR_ANY)
        else:
            # 
            print iface_ip
            mreq = group + socket.inet_aton(iface_ip)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface_ip))

        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self.sock.bind((self.address,self.port))

    def close(self):
        self.sock.close()

    def write(self,data):
        self.sock.sendto(data, (self.address, self.port))

    def read(self, block = True):
        return self.data_q.get(block)

    def data_ready(self):
        return not self.data_q.empty()

    def clear(self):
        self.data_q = Queue() # TODO empty the queue

    def run(self):
        alive = self.alive
        sock = self.sock
        buffer_size = self.buffer_size
        data_q = self.data_q
        max_qsize = self.max_qsize

        alive.set()

        while alive.is_set():
            data, addr = sock.recvfrom(buffer_size)
            #print "multicast_socket:: Got %s"%(binascii.hexlify(data[:64]))
            if data_q.qsize() > max_qsize:
                data_q.get()
            data_q.put(data)
            time.sleep(0.0001)

    def stop(self):
        print "Stopping multicast socket %s..."%(self.name)
        self.alive.clear()
        self.sock.close()

# A class for interpreting incoming bytes as a scan data frame produced by the br24 radar. It just
# tries to create scanlines out of the incoming bytes
class br24_frame_decoder:
    FRAME_START_SEQUENCE = '\x01\x00\x00\x00\x00'
    FR_WAIT = 0
    FR_START_DONE = 4
    FR_N_SCANLINE = 5
    FR_L_SCANLINE = 6
    FR_HEADER_DONE = 7
    SC_START_HEADER = 8
    SC_HEADER = 9
    SC_DATA = 10

    STATE = {0:'FR_WAIT',
             1: 'FR_START_SEQ',
             2: 'FR_START_SEQ',
             3: 'FR_START_SEQ',
             4: 'FR_START_DONE',
             5: 'FR_N_SCANLINE',
             6:'FR_L_SCANLINE',
             7: 'FR_HEADER_DONE',
             8: 'SC_START_HEADER', 
             9: 'SC_HEADER',
             10: 'SC_DATA'}


    def __init__(self,max_queue_size = 512):
        self.max_scanlines = max_queue_size
        self.init()

    def init(self):
        self.state = 0
        self.curr_scanline_index = 0

        self.num_scanlines = -1
        self.scanline_size = 0
        self.scanline_header_size = 0

        self.scanlines = Queue()
        self.curr_scanline = {}
        self.scanline_header = []
        self.scanline_data = []

    def restore_from_local_copy(self,state,scanline_idx,num_scanlines,scanline_size,scanline_header_size,curr_sc,scanline_header,scanline_data):
        self.state = state
        self.curr_scanline_index = scanline_idx
        self.num_scanlines = num_scanlines
        self.scanline_size = scanline_size
        self.scanline_header_size = scanline_header_size
        self.curr_scanline = curr_sc
        self.scanline_header= scanline_header
        self.scanline_data= scanline_data

    def make_local_copy(self):
        state= self.state
        scanline_idx = self.curr_scanline_index
        num_scanlines = self.num_scanlines
        scanline_size = self.scanline_size 
        scanline_header_size = self.scanline_header_size
        curr_sc = self.curr_scanline
        scanline_header = self.scanline_header
        scanline_data = self.scanline_data
        return (state,scanline_idx,num_scanlines,scanline_size,scanline_header_size,curr_sc,scanline_header,scanline_data)
    
    def fill(self,data):
        #TODO add a timeout
        state,scanline_idx,num_scanlines,scanline_size,scanline_header_size,curr_sc,scanline_header,scanline_data = self.make_local_copy()
        i = 0
        nbytes = len(data)
        while i < nbytes:
            byte = data[i]
            # check if we have a valid header (i.e. starting with 01 00 00 00 00)
            if state <= self.FR_START_DONE: 
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
                    scanline_data = ''
                    scanline_header_size = ord(byte)
                    scanline_header.append(byte)
                    state = self.SC_HEADER
                    if scanline_header_size == 0:
                        state = self.FR_WAIT
                        scanline_idx = 0
                        num_scanlines=-1
                        break
            # process scanline header bytes
            elif state == self.SC_HEADER:
                #scanline_header.append(byte);
                end_index = i + min(scanline_header_size-len(scanline_header),nbytes-i) 
                scanline_header.extend(data[i:end_index]);
                #advance counter for bytes read
                i=end_index-1
                #print "header: %s size %s"%(scanline_header,scanline_header_size)
                # if we got the full header, extract the data
                if len(scanline_header) == scanline_header_size:
                    curr_sc['status'] = ord(scanline_header[1])
                    curr_sc['index'] = ord(scanline_header[2]) | ord(scanline_header[3])<<8
                    curr_sc['angle'] = ord(scanline_header[8]) | ord(scanline_header[9])<<8
                    curr_sc['scale'] = ord(scanline_header[12]) | ord(scanline_header[13])<<8
                    curr_sc['time'] = time.time()
                    state = self.SC_DATA
            # process scanline bytes
            elif state == self.SC_DATA:
                #scanline_data.append(byte);
                end_index = i + min(scanline_size-len(scanline_data),nbytes-i) 
                #scanline_data.extend(data[i:end_index]);
                scanline_data += data[i:end_index];
                #advance counter for bytes read
                i=end_index-1
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

            #increase counter
            i+=1
        
        self.restore_from_local_copy(state,scanline_idx,num_scanlines,scanline_size,scanline_header_size,curr_sc,scanline_header,scanline_data)

# A driver for the BR24 radar! This
class br24(Process): 
    # COMMANDS
    CMD_POWER_1 = '\x00\xc1'
    CMD_POWER_2 = '\x01\xc1'
    CMD_RANGE = '\x03\xc1'
    CMD_FILTER_AND_PREPROCESS = '\x06\xc1'
    CMD_INTERFERENCE_REJECTION = '\x08\xc1'
    CMD_TARGET_BOOST = '\x0A\xc1'
    CMD_LOCAL_INTERFERENCE_FILTER = '\x0E\xc1'
    CMD_SCAN_SPEED = '\x0F\xc1'
    CMD_KEEP_ALIVE = '\xA0\xc1'
    RADAR_RANGE_OPTIONS = ['\xf4\x01\x00\x00',
                           '\xee\x02\x00\x00',
                           '\xee\x03\x00\x00',
                           '\xc4\x09\x00\x00',
                           '\x88\x13\x00\x00',
                           '\x4c\x1d\x00\x00',
                           '\x10\x27\x00\x00',
                           '\x98\x3a\x00\x00',
                           '\x20\x4e\x00\x00',
                           '\x30\x75\x00\x00',
                           '\x40\x9c\x00\x00',
                           '\x60\xea\x00\x00',
                           '\x80\x38\x01\x00',
                           '\xc0\xd4\x01\x00',
                           '\x00\x71\x02\x00',
                           '\x80\xa9\x03\x00']

    def __init__(self, interface_ip = None):
        Process.__init__(self)
        self.data_q = Queue()

        self.scan_data_socket = multicast_socket('236.6.7.8', 6678, data_q = self.data_q, name="scan_data", iface_ip = interface_ip)
        self.command_response_socket = multicast_socket('236.6.7.9', 6679, name="command_response", iface_ip = interface_ip)
        self.command_request_socket = multicast_socket('236.6.7.10', 6680, name="command_request", iface_ip = interface_ip)
        self.radar_on = False

        self.alive = Event()
        self.alive.set()
        self.daemon = True

        self.scan_data_socket.start()
        self.scan_data_decoder = br24_frame_decoder()

    ### COMMAND SOCKET METHODS ###
    def send_command(self,cmd,value=''):
        self.command_request_socket.write(cmd+value)
        time.sleep(0.001)

    def start_radar(self):
        print "Starting radar..."
        self.send_command(self.CMD_POWER_1,'\x01')
        self.send_command(self.CMD_POWER_2,'\x01')
        self.radar_on = True
        return True

    def stop_radar(self):
        print "Stopping radar..."
        self.send_command(self.CMD_POWER_1,'\x00')
        self.send_command(self.CMD_POWER_2,'\x00')
        self.radar_on = False
        return True

    def increase_scan_speed(self,multiplier):
        for i in xrange(multiplier):
            self.send_command(self.CMD_SCAN_SPEED,'\x01')
        return True

    def reset_scan_speed(self):
        self.send_command(self.CMD_SCAN_SPEED,'\x00')
        return True

    def set_local_interference_filter(self,option):
        if option >=0 and option <=3:
            self.send_command(self.CMD_LOCAL_INTERFERENCE_FILTER,chr(option))
            return True
        return False

    def set_target_boost(self,option):
        if option >=0 and option <=2:
            self.send_command(self.CMD_TARGET_BOOST,chr(option))
            return True
        return False

    def set_interference_rejection(self,option):
        if option >=0 and option <=3:
            self.send_command(self.CMD_INTERFERENCE_REJECTION,chr(option))
            return True
        return False

    # TODO figure out if the filtering and preprocessing bits are correct
    def set_filters_and_preprocessing(self,option,arg = None):
        options = {'auto_gain': '\x00\x00\x00\x00\x01\x00\x00\x00\xA1',
                   'manual_gain': '\x00\x00\x00\x00\x00\x00\x00\x00',
                   'rain_clutter_manual': '\x04\x00\x00\x00\x00\x00\x00\x00',
                   'sea_clutter_auto': '\x02\x00\x00\x00\x01\x00\x00\x00\xD3',
                   'sea_clutter_manual': '\x02\x00\x00\x00\x00\x00\x00\x00'}
        param = options[option]
        if option == 'manual_gain' or option == 'rain_clutter_manual' or option == 'sea_clutter_manual':
            param += chr(arg)

        self.send_command(self.CMD_FILTER_AND_PREPROCESS,param)
        pass

    def set_radar_range(self,option):
        if option >=0 and option <=len(self.RADAR_RANGE_OPTIONS):
            self.send_command(self.CMD_RANGE,self.RADAR_RANGE_OPTIONS[option])
            return True
        return False

    def set_radar_range_mts(self,new_range):
        if new_range >= 50 and new_range <= 24000:
            range_hex = s_pack('<I',new_range*10)
            self.send_command(self.CMD_RANGE,range_hex)
            return True
        return False

    ### DATA SOCKET METHODS ###
    def scanline_ready(self):
        return not self.scan_data_decoder.scanlines.empty()

    def get_scanline(self,block=True):
        return self.scan_data_decoder.scanlines.get(block)

    def clear_scanlines(self):
        self.scan_data_decoder.init()

    ### PROCESS METHODS ###
    def run(self):
        self.start_radar()
        self.alive.set()
        keep_alive_time = time.time()

        while self.alive.is_set():
            if (self.radar_on):
                # send keep alive signal to radar every two seconds
                curr_time = time.time()
                if curr_time - keep_alive_time > 2:
                    keep_alive_time = curr_time
                    self.send_command(self.CMD_KEEP_ALIVE)
                # this will  process data once it is available
                if self.data_q.qsize()>2:
                    self.scan_data_decoder.fill(self.data_q.get())
                    #cProfile.runctx('self.scan_data_decoder.fill(self.data_q.get())',globals(),locals())
                time.sleep(0.0001)
                
    def stop(self):
        print "Stopping radar driver..."
        self.scan_data_socket.stop()
        self.stop_radar()
        self.alive.clear()
