__author__  = 'Yan Marques de Cerqueira'
__email__   = 'marques_yan@outlook.com'
__git__     = 'https://github.com/yanmarques/youtube-extractor'
__version__ = '1.0'
__banner__  = 'youtube-extractor v.%s' % __version__ 

from logger import *
from abc import abstractmethod
import sys
import os
import subprocess 
import itertools
import time
import threading
import re
import shlex
import urllib

# Detects user platform
if sys.platform.startswith('win32'):
    platform = 'windows'
elif sys.platform.startswith('darwin'):
    platform = 'darwin'
else:
    platform = 'linux' 

pyversion = '.'.join(str(minor) for minor in sys.version_info[:2])
logger = Logger()

def signalhandler(singnum, frame):
    """Handle a keyboard interrupt"""
    log('\n[*] Received user keyboard interrupt.')
    print('[*] Exiting.')
    sys.exit()

class ProcessNotKilledException(BaseException):
    def __init__(self, message):
        self.message = message
    
    def __repr__():
        return str(self.message)

class Loader(object):
    """Start an animation"""
    def __init__(self, output=None, message='', sleep=0.1, color=NULL):
        self.output = output if output else ['|', '/', '-', '\\']
        self.message = message
        self.sleep = sleep
        self.color = color
        self.event = threading.Event()
    
    def start(self):
        """Start the animation output"""
        self.event.set()
        def run():
            time.sleep(0.2)
            for i in itertools.cycle(self.output):
                if not self.event.is_set():
                    break
                sys.stdout.write('\r' + self.color + self.message + ' ' + i + NULL)
                sys.stdout.flush()
                time.sleep(self.sleep)

        threading.Thread(target=run).start()
    
    def stop(self):
        """Stop animation output"""
        self.event.clear()

class Service(object):
    """Service manager"""
    def __init__(self):
        self.started = False
        self.tried_to_install = False
        self.installed = False
        self.event = threading.Event()

    @abstractmethod
    def start(self):
        """Start running service"""
        pass
    
    @abstractmethod
    def restart(self):
        """Put service down and start again"""
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def _install(self):
        """Try to install service based on user platform"""
        pass

    def execute_process(self, command, shell=True, root=False):
        """Handle a process execution returning a tuple with stdout and stderr"""
        if root:
            command[0] = 'sudo ' + command[0]
        
        logger.log('[*] Running: '+(' '.join(command) if type(command) is list else command), YELLOW)
        process = subprocess.Popen(command, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            if root and self._require_root:
                stdout, stderr = process.communicate()
            else:    
                stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = (b'', b'Process timed out.')

        if root and 'incorrect' in stderr.decode().lower():
            return '', 'Incorrect password.'
        
        return self._parse_output(stdout, stderr)

    def _parse_output(self, stdout, stderr):
        """Parse a stderr output buffer decode and strip new-lines on end of string"""
        if type(stderr) is not bytes or type(stdout) is not bytes:
            raise TypeError('Invalid type for argument. Stdout and stderr must be a bytes-like object.')
        return stdout.decode().rstrip().lstrip(), stderr.decode().rstrip().lstrip()

    def _require_root(self):
        """Indicate wheter user is root"""
        if os.getuid() != 0:
            return True
        return False

class YoutubeDl(Service):
    """Use youtube-dl wonderfull script to execute content download"""
    def start(self, *args):
        """Run youtube-dl script on process"""
        logger.log('[*] Running youtube-dl service.')
        command = ['youtube-dl']
        if not self.installed and not self.tried_to_install:
            tries = 0
            while tries < 2:
                stderr = self.execute_process(command)[1]
                tries += 1
                self.tried_to_install = True
                if stderr and 'usage' not in stderr.lower():
                    logger.log('[*] Error: '+ stderr, RED)
                    self._install()
                else:
                    self.installed = True
                
        if self.tried_to_install and not self.installed:
            print('[*] Tried to install youtube-dl with no success.')
            print('[-] Exiting.')
            sys.exit()
        
        if args:
            command.append(*args)
        stderr = self.execute_process(command)[1]
        if stderr and not 'help' in stderr.lower():
            logger.log('[*] Error output: '+ stderr, RED)
            return False
        return True

    def restart(self, *args):
        """Just pass arguments to start method"""
        return self.start(*args)

    def _install(self):
        """Try to install youtube-dl with python"""
        loader = Loader(message='[*] Installing youtube-dl', color=YELLOW)
        loader.start()
        command = ['-H python' + pyversion + ' -m pip install youtube-dl']
        stderr = self.execute_process(command, root=True)[1]
        if stderr:
            logger.log('[-] Error: '+ stderr, RED)
            logger.log('[*] Last command failed.')
            if platform == 'darwin':
                command = ['brew', 'install', 'youtube-dl']
                stderr = self.execute_process(command, root=True)[1]
            elif platform == 'linux':
                command = ['apt-get', 'install', '-y', 'youtube-dl']
                stderr = self.execute_process(command, root=True)[1]
        loader.stop()
        if stderr:
            logger.log('\n[*] Error installing: '+ stderr, RED)
            print('[*] Could not install youtube-dl.')
            print('[+] See: https://rg3.github.io/youtube-dl')
            sys.exit()
        logger.log('\n[*] youtube-dl has been installed.', color=GREEN)