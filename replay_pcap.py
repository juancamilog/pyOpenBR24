#!/usr/bin/env python
import argparse
import subprocess
from os import path
from scapy.all import *
from scapy.utils import rdpcap
from br24_driver import multicast_socket
import time
import StringIO
import binascii
import struct

def reassemble_packet(fragment_list):
    buffer=StringIO.StringIO()
    for pkt in sorted(fragment_list, key = lambda pkt:pkt['IP'].frag):
         buffer.seek(pkt['IP'].frag*8)
         buffer.write(pkt['IP'].payload)
    b = buffer.getvalue()
    # the first 64 bits are the udp header
    # TODO compute checksum
    packet_length = struct.unpack('>H',b[4:6])[0]
    return b[8:packet_length]

if __name__=="__main__":
    interface_ip  = '192.168.8.2'
    #interface_ip  = None

    scale = 1.0
    mcastsocket = {}
    mcastsocket['236.6.7.8'] = multicast_socket('236.6.7.8', 6678, name="scan_data", iface_ip = interface_ip)
    mcastsocket['236.6.7.9'] = multicast_socket('236.6.7.9', 6679, name="command_response" , iface_ip = interface_ip)
    mcastsocket['236.6.7.10'] = multicast_socket('236.6.7.10', 6680, name="command_request", iface_ip = interface_ip)

    try:
        parser = argparse.ArgumentParser("Replay packets from a pcap_file")
        parser.add_argument("pcap_file_path", type=str, help ="The path of the pcap file to replay")
        args = parser.parse_args()
        pcap_path, pcap_file_name = path.split(args.pcap_file_path)
        pcap_file_name, ext = path.splitext(pcap_file_name)

        print (pcap_path, pcap_file_name)
        subprocess.call(['editcap','-c','1024','-F','libpcap',args.pcap_file_path,'_'+pcap_file_name+'_out.pcap'])
        out,err = subprocess.Popen(['ls | grep '+pcap_file_name+'_out'], stdout=subprocess.PIPE, shell=True).communicate()

        fragments = {}

        for pcap_file in out.splitlines():
            print 'Processing %s'%(pcap_file)
            pkts = rdpcap(pcap_file)
            timestamp = pkts[0].time
            for pkt in pkts:
                if pkt.haslayer('IP'):
                    dst = pkt['IP'].dst
                    if dst in mcastsocket.keys():
                        print "id: %d offset: %d"%(pkt['IP'].id,pkt['IP'].frag*8)
                        time.sleep((pkt.time - timestamp)*scale)
                        timestamp = pkt.time
                        if pkt['IP'].flags == 1:
                            #print [(pkt.time, fragment_id, fragments[fragment_id].len) for fragment_id in fragments.keys()]
                            if pkt['IP'].frag == 0:
                                #fragments[pkt['IP'].id] = [pkt]
                                #print pkt['IP'].payload
                                buffer=StringIO.StringIO()
                                buffer.seek(pkt['IP'].frag*8)
                                buffer.write(pkt['IP'].payload)
                                fragments[pkt['IP'].id] = buffer
                            else:
                                if pkt['IP'].id not in fragments.keys():
                                    continue
                                #fragments[pkt['IP'].id].append(pkt)
                                buffer=fragments[pkt['IP'].id]
                                buffer.seek(pkt['IP'].frag*8)
                                buffer.write(pkt['IP'].payload)
                                fragments[pkt['IP'].id] = buffer
                        else:
                            frags = fragments.pop(pkt['IP'].id,None)
                            if frags is None:
                                mcastsocket[dst].write(pkt.load)
                            else:
                                #frags.append(pkt)
                                frags.seek(pkt['IP'].frag*8)
                                frags.write(pkt['IP'].payload)
                                #mcastsocket[dst].write(reassemble_packet(frags))
                                payload = frags.getvalue()
                                packet_length = struct.unpack('>H',payload[4:6])[0]
                                #print (packet_length,len(payload))
                                mcastsocket[dst].write(payload[8:packet_length])


        subprocess.call(['rm _'+pcap_file_name+'*'], shell =True)
    except KeyboardInterrupt:
        subprocess.call(['rm _'+pcap_file_name+'*'], shell =True)
    
