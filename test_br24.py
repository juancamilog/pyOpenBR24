#!/usr/bin/env python
import br24_driver
import time

if __name__ == '__main__':
    br = br24_driver.br24()
    br.start()
    br.set_radar_range(5)
    br.reset_scan_speed()
    angle_increment = 360.0/4096.0
    try:
        last_angle = -1
        start_time = time.time()
        count = 0
        while True:
            #if br.scanline_ready():
                sc = br.get_scanline()
                #print sc
                curr_angle = sc['angle']*angle_increment
                curr_idx = sc['index']
                #print (sc.index,curr_angle)
                if last_angle > curr_angle:
                    # e.g.  360 > 1
                    curr_time = time.time()-start_time
                    print "finished full scan: %s %s"%(curr_time,last_angle)
                    print "processed %d scan lines"%(count)
                    print "socket queue size: %d"%(br.data_q.qsize())
                    print "scanline queue size: %d"%(br.scan_data_decoder.scanlines.qsize())
                    count = 0 
                    start_time = time.time()
                last_angle = curr_angle
                count+=1
            #else:
            #    time.sleep(0.001)
    except KeyboardInterrupt:
        print "Stopping radar.."
        br.stop()

