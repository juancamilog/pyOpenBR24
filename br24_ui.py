#!/usr/bin/python
import Tkinter as tk
import ttk
import br24_driver
from PIL import Image, ImageTk
import time
import math
import multiprocessing as mp
import threading
import datetime
import yaml

#class br24_ctrl_window(mp.Process):
class br24_ctrl_window(threading.Thread):
    def __init__(self, master, br, refresh_period=500):
        #mp.Process.__init__(self)
        self.refresh_period = refresh_period
        threading.Thread.__init__(self)
        self.master = master
        master.wm_title("BR24 radar options")

        self.br = br

        self.frame = tk.Frame(self.master)
        self.local_interference_opts = ['off', 'low','medium', 'high']
        self.interference_reject_opts = ['off', 'low','medium', 'high']
        self.target_boost_opts = ['off', 'low', 'high']
        self.radar_range_opts = ['50 m','75 m','100 m','250 m','500 m','750 m','1 km','1.5 km','2 km','3 km','4 km','6 km','8 km','12 km','16 km','24 km']
        self.fp_opts = ['Gain', 'Rain Clutter Filter', 'Sea Clutter Filter']
        self.fp_vals = ['auto_gain', 'manual_gain', 'rain_clutter_manual', 'sea_clutter_auto', 'sea_clutter_manual']
        self.fp_opts = ['Auto']
        print self.fp_opts.extend(range(1,0x50))

        self.button1 = tk.Button(self.frame, text = 'Start Radar', width = 25, command = self.start_driver)
        self.button1.pack()
        self.button2 = tk.Button(self.frame, text = 'Increase Scanning Speed', width = 25, command = self.increase_scan_speed)
        self.button2.pack()
        self.button3 = tk.Button(self.frame, text = 'Reset Scanning Speed', width = 25, command = self.reset_scan_speed)
        self.button3.pack()

        self.radar_range_label = tk.Label(self.frame, text = "Radar Range:")
        self.radar_range_label.pack()
        self.radar_range_cbox = ttk.Combobox(self.frame, values=self.radar_range_opts)
        self.radar_range_cbox.pack()

        self.interference_reject_label = tk.Label(self.frame, text = "Interference Rejection:")
        self.interference_reject_label.pack()
        self.interference_reject_cbox = ttk.Combobox(self.frame, values=self.interference_reject_opts)
        self.interference_reject_cbox.pack()

        self.target_boost_label = tk.Label(self.frame, text = "Target Boost:")
        self.target_boost_label.pack()
        self.target_boost_cbox = ttk.Combobox(self.frame, values=self.target_boost_opts)
        self.target_boost_cbox.pack()

        self.local_interference_label = tk.Label(self.frame, text = "Local Interference Filter:")
        self.local_interference_label.pack()
        self.local_interference_cbox = ttk.Combobox(self.frame, values=self.local_interference_opts)
        self.local_interference_cbox.pack()
        
        self.fp_frame = tk.Frame(self.frame)
        self.gain_label = tk.Label(self.fp_frame, text = "Gain:")
        self.gain_label.pack()
        self.gain_cbox = ttk.Combobox(self.fp_frame, values=self.fp_opts)
        self.gain_cbox.pack()
        self.rainc_label = tk.Label(self.fp_frame, text = "Rain Clutter")
        self.rainc_label.pack()
        self.rainc_cbox = ttk.Combobox(self.fp_frame, values=self.fp_opts[1:])
        self.rainc_cbox.pack()
        self.seac_label = tk.Label(self.fp_frame, text = "Sea Clutter:")
        self.seac_label.pack()
        self.seac_cbox = ttk.Combobox(self.fp_frame, values=self.fp_opts)
        self.seac_cbox.pack()
        self.fp_frame.pack(pady=5)


        self.frame.pack()

        self.newWindow = tk.Toplevel(self.master)
        self.image_window = br24_image_window(self.newWindow,self.refresh_period)
                
        self.radar_range_cbox.bind('<<ComboboxSelected>>', self.radar_range_cmd)
        self.interference_reject_cbox.bind('<<ComboboxSelected>>', self.interference_reject_cmd)
        self.target_boost_cbox.bind('<<ComboboxSelected>>', self.target_boost_cmd)
        self.local_interference_cbox.bind('<<ComboboxSelected>>', self.local_interference_cmd)

        self.master.protocol("WM_TAKE_FOCUS", self.on_focus)

        self.daemon = True
        #self.alive = mp.Event()
        self.alive = threading.Event()
        self.start()


    def on_focus(self):
        self.image_window.master.lift()
        self.master.lift()

    def set_driver(self,br):
        self.br = br

    def start_driver(self):
        if not self.br.is_alive():
            self.br.start()
        self.br.start_radar()
        self.button1.config(text = 'Stop Radar', width = 25, command = self.stop_driver)

    def stop_driver(self):
        self.br.stop_radar()
        self.button1.config(text = 'Start Radar', width = 25, command = self.start_driver)

    def increase_scan_speed(self):
        print "increasing scanning speed by %s"%(1)
        self.br.increase_scan_speed(1)

    def reset_scan_speed(self):
        print "resetting scanning speed to normal"
        self.br.reset_scan_speed()

    def set_filter_preprocessing(self, event):
        print "setting "
        self.br.increase_scan_speed(val)


    def radar_range_cmd(self, event):
        val = self.radar_range_cbox.get() 
        if val is not '':
            print "setting radar range to %s"%(val)
            self.br.set_radar_range(self.radar_range_opts.index(val))

    def interference_reject_cmd(self, event):
        val = self.interference_reject_cbox.get()
        if val is not '':
            print "setting interference rejection %s"%(val)
            self.br.set_interference_rejection(self.interference_reject_opts.index(val))

    def local_interference_cmd(self, event):
        val = self.local_interference_cbox.get()
        if val is not '':
            print "setting local interference filter %s"%(val)
            self.br.set_local_interference_filter(self.local_interference_opts.index(val))
            
    def target_boost_cmd(self, event):
        val =self.target_boost_cbox.get()
        if val is not '':
            print "setting target boost %s"%(val)
            self.br.set_target_boost(self.target_boost_opts.index(val))

    def run(self):
        self.alive.set()
        last_angle = -1
        start_time = time.time()
        count = 0
        while self.alive.is_set():
            while self.br.scanline_ready():
                sc = self.br.get_scanline()
                self.image_window.draw_scanline(sc)

                if last_angle > sc['angle']:
                    #self.image_window.update_radar_image()
                    curr_time = time.time()-start_time
                    print "finished full scan: %s %s"%(curr_time,last_angle)
                    print "processed %d scan lines"%(count)
                    print "socket queue size: %d"%(self.br.data_q.qsize())
                    print "scanline queue size: %d"%(self.br.scan_data_decoder.scanlines.qsize())
                    count = 0 
                    start_time = time.time()

                last_angle = sc['angle']
                count+=1
            time.sleep(0.0001)
    
class br24_image_window:
    def __init__(self, master, refresh_period = 500):
        self.refresh_period = refresh_period
        self.master = master
        master.wm_title("BR24 radar image")
        self.frame = tk.Frame(self.master)
        self.master.geometry('512x512')
        self.master.aspect(1,1,1,1)

        self.angle_increment = 2*math.pi/4096

        self.radar_image_label = tk.Label(self.frame)
        self.radar_image_label.pack()

        self.radar_image = Image.new("RGB", (1024,1024), "black")
        radar_imagetk = ImageTk.PhotoImage(self.radar_image)
        self.radar_image_label.configure(image = radar_imagetk)
        self.radar_image_label._image_cache = radar_imagetk

        self.pixels = self.radar_image.load()

        self.frame.pack()
        self.master.after(self.refresh_period, self.update_radar_image)

    def draw_scanline(self,sc):
        ang = sc['angle']*self.angle_increment
        cos_ang = math.cos(ang)
        sin_ang = math.sin(ang)
        scale = self.radar_image_label.winfo_width()/1024.0
        center = self.radar_image_label.winfo_width()/2.0
        height = self.radar_image_label.winfo_height()
        r_max = len(sc['data'])

        for r in xrange(r_max):
            intensity = ord(sc['data'][r])
            x = int(center + r*scale*sin_ang)
            y = height - int(center + r*scale*cos_ang)
            #y = int(center + r*scale*cos_ang)
            self.pixels[x,y] = (0,intensity,40)

    def draw_scanline_ros(self, msg):
        sc['data'] = msg.scanline_data
        sc['angle'] = msg.angle
        self.draw_scanline(sc)

    def update_radar_image(self):
        radar_imagetk = ImageTk.PhotoImage(self.radar_image)
        self.radar_image_label.configure(image = radar_imagetk)
        self.radar_image_label._image_cache = radar_imagetk
        self.master.after(self.refresh_period, self.update_radar_image)

if __name__ == '__main__':
    br = br24_driver.br24()

    root = tk.Tk()
    ctrl_window = br24_ctrl_window(root,br, refresh_period=200)
    root.mainloop()

