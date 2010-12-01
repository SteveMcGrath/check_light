#!/usr/bin/env python

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import os
import sys
import commands as cmd
import md5
import datetime
import ConfigParser

class Resources(object):
  def __init__(self, salt):
    self.salt = salt

  def get_num_cores(self, auth):
    if self._valid_auth(auth):
      cores = 0
      for line in open('/proc/cpuinfo'):
        if line.find('vendor_id') > -1:
          cores += 1
      return cores
  
  def get_core_info(self, auth, cpu_id):
    if self._valid_auth(auth):    
      result  = cmd.getoutput('sar -P %s' % cpu_id)
      avg     = result.split('\n')[-1].split()
      return {
        'user': round(float(avg[2]),2),
        'nice': round(float(avg[3]),2),
         'sys': round(float(avg[4]),2),
          'io': round(float(avg[5]),2),
       'steal': round(float(avg[6]),2),
        'idle': round(float(avg[7]),2),
      }
  
  def get_mem_info(self, auth):
    if self._valid_auth(auth):    
      results = {}
      for line in open('/proc/meminfo'):
        dset = line.lower().strip(':').split()
        results[dset[0].strip(':')] = int(int(dset[1])/1024)
      return results
  
  def get_disk_info(self, auth):
    if self._valid_auth(auth):
      results = cmd.getoutput('df').split('\n')
      results.pop(0)
      values = []
      for line in results:
        dset = line.split()
        values.append({
          'filesystem': dset[0],
                'size': int(dset[1]),
                'used': int(dset[2]),
           'available': int(dset[3]),
        'percent_used': int(dset[4].strip('%')),
         'mount_point': dset[5],
        })
      return values
  
  def get_load(self, auth):
    if self._valid_auth(auth):
      results = cmd.getoutput('uptime')
      uptime  = results.split('load average:')[1].split(',')
      min_1   = uptime[0]
      min_5   = uptime[1]
      min_15  = uptime[2]
      return {'1min': min_1, '5min': min_5, '15min': min_15}
  
  def started_service(self, auth, name):
    if self._valid_auth(auth):
      result = cmd.getoutput('/etc/init.d/%s status' % name)
      if result.find('running') > -1:
        return True
      else:
        return False
  
  def running_process(self, auth, name):
    if self._valid_auth(auth):
      result = cmd.getoutput('ps aux')
      values = {'running': False}
      for line in result.split('\n'):
        if line.find(name) > -1:
          dset = line.split()
          values = {
            'running': True,
               'user': dset[0],
                'pid': int(dset[1]),
                'cpu': round(float(dset[2]),2),
                'mem': round(float(dset[3]),2),
          'vmem_size': int(dset[4]),
            'res_mem': int(dset[5]),
                'tty': dset[6],
             'status': dset[7],
              'start': dset[8],
                'age': dset[9],
            'process': ' '.join(dset[9:]),
          }
      return values
  
  def _valid_auth(self, auth):
    check = md5.md5()
    try:
      check.update(auth['user'])
      check.update(auth['date'])
      check.update(self.salt)
      if check.hexdigest() == auth['hash']:
        return True
      else:
        return False
    except:
      return False

class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

def daemonize():
  pidfile = '/var/run/service_light.pid'
  # do the UNIX double-fork magic, see Stevens' "Advanced 
  # Programming in the UNIX Environment" for details (ISBN 0201563177)
  try: 
    pid = os.fork() 
    if pid > 0:
      # exit first parent
      sys.exit(0) 
  except OSError, e: 
    print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror) 
    sys.exit(1)
  # decouple from parent environment
  os.chdir("/") 
  os.setsid() 
  os.umask(0) 
  # do second fork
  try: 
    pid = os.fork() 
    if pid > 0:
      # exit from second parent, print eventual PID before
      #print "Daemon PID %d" % pid
      open(pid_file, 'w').write('%d' % pid)
      sys.exit(0) 
  except OSError, e: 
    print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror) 
    sys.exit(1) 
  # Redirect all console data to logfiles
  out_log = file('/var/log/service_light.log', 'a+')
  err_log = file('/var/log/service_light.err', 'a+', 0)
  dev_null = file('/dev/null', 'r')
  os.dup2(out_log.fileno(),   sys.stdout.fileno())

def main():
  config  = ConfigParser.ConfigParser()
  config.read('/etc/service_light.conf')
  salt    = config.get('Settings', 'salt')
  port    = config.getint('Settings', 'port')
  address = config.get('Settings', 'address')
  server  = SimpleXMLRPCServer((address, port), requestHandler=RequestHandler)
  server.register_introspection_functions()
  server.register_instance(Resources(salt))
  daemonize()
  server.serve_forever()

if __name__ == '__main__':
  if not os.path.exists('/etc/init.d/service_light'):
    init = open('/etc/init.d/service_light', 'w')
    init.write(init_script)
    init.close()
    os.chmod(0755,'/etc/init.d/service_light')
  sys.exit(main())