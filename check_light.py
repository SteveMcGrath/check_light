#!/usr/bin/env python

import ConfigParser
import datetime
import md5
import os
import sys
import time
from termcolor import colored
import xmlrpclib
import threading
import curses

version = '0.2.1'
motd    = '''
Check Light Version %s
-----------------------
Written By: Steven McGrath
     Build: 045
      Date: 2010-11-22

check_light> Threaded for your enjoyment. (thread responsibly)
''' % version

def auth(con):
  config    = get_config()
  user      = config.get(con, 'user')
  salt      = config.get(con, 'salt')
  date      = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  md5_hash  = md5.md5()
  md5_hash.update(user)
  md5_hash.update(date)
  md5_hash.update(salt)
  return {
    'user': user,
    'date': date,
    'hash': md5_hash.hexdigest(),
  }

def get_config():
  config  = ConfigParser.ConfigParser()
  config.read('%s/.check_light.conf' % os.environ['HOME'])
  return config

class Connection(threading.Thread):
  def __init__(self, name):
    config                    = get_config()
    self.connection_name      = name
    self.shutdown_connection  = False
    self.statuses             = []
    self.delay                = 0
    self.con_status           = 'down'
    self.comids               = {'acpu': True, 'icpu': True, 'mem': True, 
                                 'iowait': True, 'disk': True, 'swap': True}
    self.display_name         = config.get(name, 'display')
    self.queue_point          = config.getint(name, 'position')
    
    
    
    threading.Thread.__init__(self)
  
  def run(self):
    while not self.shutdown_connection:
      # Setting up any variables that we will be using.
      info              = {}
      config            = get_config()
      section           = self.connection_name
      start             = datetime.datetime.now()
      delay             = config.getint(section, 'delay')
      
      # Initiating the connection and pulling all of the data.
      try:
        proxy           = xmlrpclib.ServerProxy('http://%s:%s' %\
                                        (config.get(section, 'address'),
                                         config.get(section, 'port')))

        info['mem']       = proxy.get_mem_info(auth(self.connection_name))
        info['disk']      = proxy.get_disk_info(auth(self.connection_name))
        info['load']      = proxy.get_load(auth(self.connection_name))
        info['cpus']      = {}
        num_cpus          = proxy.get_num_cores(auth(self.connection_name))
        for cpu in range(0,num_cpus):
          info['cpus'][cpu] = proxy.get_core_info(auth(self.connection_name),cpu)

        info['svcs']  = {}
        for svc in config.get(section, 'services').split(','):
          if svc is not '':
            name  = svc.strip()
            info['svcs'][svc] = proxy.started_service(auth(self.connection_name),name)

        info['procs'] = {}
        for proc in config.get(section, 'processes').split(','):
          if proc is not '':
            name  = proc.strip()
            info['procs'][proc] = proxy.running_process(auth(self.connection_name),name)
        self.con_status = 'up'
      except:
        self.con_status = 'down'
        self.statuses   = []
        self.comids     = {'acpu': True, 'icpu': True, 'mem': True, 
                           'iowait': True, 'disk': True, 'swap': True}
      
      if self.con_status == 'up': 
        acpu      = []
        icpu      = 0
        iowait    = []
        for cpu in info['cpus']:
          usage   = (100 - info['cpus'][cpu]['idle'])
          acpu.append(usage)
          iowait.append(info['cpus'][cpu]['io'])
          if usage > icpu:
            icpu  = usage
        
        vals      = {
          'icpu': icpu,
          'acpu': round(sum(acpu) / len(acpu),1),
        'iowait': round(sum(iowait) / len(iowait),1),
           'mem': round(100 - float(info['mem']['memfree']) / float(info['mem']['memtotal']) * 100,1),
          'swap': round(100 - float(info['mem']['swapfree']) / float(info['mem']['swaptotal']) * 100,1),
          'load': info['load']['1min']
        }
        
        hdisk     = 0
        for disk in info['disk']:
          if disk['percent_used'] > hdisk:
            hdisk = disk['percent_used']
        vals['disk']  = hdisk
        
        for item in vals:
          if vals[item] > config.getint(section, item):
            self.comids[item]  = True
          else:
            self.comids[item]  = False
        
        self.statuses  = []
        for proc in info['procs']:
          status    = False
          if info['procs'][proc]['running']:
            status  = True
          self.statuses.append((proc, status))
        
        for svc in info['svcs']:
          status    = False
          if info['svcs'][svc]:
            status  = True
          self.statuses.append((svc, status))
        
        self.delay  = (datetime.datetime.now() - start).seconds
        time.sleep(delay)


def main(win):
  #curses.curs_set(0)
  config  = get_config()
  threads = []
  win.clear()
  win.box()
  win.nodelay(True)
  for con in config.sections():   
    if config.get(con, 'enabled'):
      threads.append(Connection(con))

  
  for thread in threads:
    thread.start()

  win.clear()
  win.box()
  curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
  curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_GREEN)
  curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_RED)
  curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)
  
  color_status  = {'up': 1, 'down': 3}
  color_comids  = {True: 3, False: 2}
  color_svcs    = {True: 2, False: 3}
  
  try:
    while True:
      win.clear()
      win.redrawwin()
      win.box()
      win.addstr(0,10, '  Check Light Version %s ' % version, curses.color_pair(4))
      for thread in threads:
        y = thread.queue_point
        win.addstr(y,1,'%20s' % thread.display_name, curses.color_pair(color_status[thread.con_status]))
        win.addstr(y,22,'[%3s]' % thread.delay)
        win.addstr(y,28,'C', curses.color_pair(color_comids[thread.comids['acpu']]))
        win.addstr(y,29,'O', curses.color_pair(color_comids[thread.comids['iowait']]))
        win.addstr(y,30,'M', curses.color_pair(color_comids[thread.comids['mem']]))
        win.addstr(y,31,'I', curses.color_pair(color_comids[thread.comids['icpu']]))
        win.addstr(y,32,'D', curses.color_pair(color_comids[thread.comids['disk']]))
        win.addstr(y,33,'S', curses.color_pair(color_comids[thread.comids['swap']]))
    
        x = 35
        for entry in thread.statuses:
          item  = ' %s ' % entry[0]
          win.addstr(y,x,item, curses.color_pair(color_svcs[entry[1]]))
          x += len(item) 
  
      win.addstr(curses.LINES - 1,10,'  %s  (Q)uit' % datetime.datetime.now().ctime(), curses.color_pair(4))
      try:
        key = win.getkey()
      except:
        key = None
      if key == 'Q':
        curses.endwin()
        break
      time.sleep(1)
  except:
    curses.endwin()

if __name__ == '__main__':
  print motd
  time.sleep(5)
  sys.exit(curses.wrapper(main))