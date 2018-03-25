__author__  = 'Yan Marques de Cerqueira'
__email__   = 'marques_yan@outlook.com'
__git__     = 'https://github.com/yanmarques/youtube-extractor'
__version__ = '1.0'
__banner__  = 'youtube-extractor v.%s' % __version__ 

import sys
import os
import subprocess 
import itertools
import time
import threading
from logger import *
from abc import abstractmethod

# Detects user platform
if sys.platform.startswith('win32'):
    platform = 'windows'
elif sys.platform.startswith('darwin'):
    platform = 'darwin'
else:
    platform = 'linux' 

pyversion = '.'.join(str(minor) for minor in sys.version_info[:2])
logger = Logger()
logger.set_verbose()

def signalhandler(singnum, frame):
    """Handle a keyboard interrupt"""
    log('\n[*] Received user keyboard interrupt.')
    print('[*] Exiting.')
    sys.exit()

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
    @abstractmethod
    def start(self):
        """Start running service"""
        pass
    
    @abstractmethod
    def restart(self):
        """Put service down and start again"""
        pass

    @abstractmethod
    def _install(self):
        """Try to install service based on user platform"""
        pass

    def execute_process(self, command):
        """Handle a process execution returning a tuple with stdout and stderr"""
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutException:
            stdout, stderr = (b'', b'Process timed out.')

        return stdout, stderr

    def parse_stderr(self, stderr):
        """Parse a stderr output buffer decode and strip new-lines on end of string"""
        if type(stderr) is bytes:
            stderr = stderr.decode()
        return stderr.rstrip().lstrip()

    def _require_root(self):
        """Require that user be root"""
        if os.getuid() != 0:
            print(RED + '[-] You need be root!' + NULL)
            sys.exit()

class YoutubeDl(Service):
    """Use youtube-dl wonderfull script to execute content download"""
    def __init__(self):
        self.tried_to_install = False
        self.installed = False

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
                if stderr and 'usage' not in stderr.decode().lower():
                    stderr = self.parse_stderr(stderr)
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
        if stderr and not 'help' in stderr.decode():
            stderr = self.parse_stderr(stderr)
            logger.log('[*] Error output: '+ stderr, RED)
            return False
        return True

    def restart(self, *args):
        """Just pass arguments to start method"""
        return self.start(*args)

    def _install(self):
        """Try to install youtube-dl with python"""
        self._require_root()
        loader = Loader(message='[*] Installing youtube-dl', color=YELLOW)
        loader.start()
        command = ['sudo', '-H',  'python' + pyversion, '-m', 'pip', 'install', 'youtube-dl']
        logger.log('[*] Running: '+' '.join(command))
        stderr = self.execute_process(command)[1]
        if stderr:
            logger.log('[*] Last command failed.')
            if platform == 'darwin':
                command = ['sudo', 'brew', 'install', 'youtube-dl']
                logger.log('[*] Running:' + ' '.join(command))
                stderr = self.execute_process(command)[1]
            elif platform == 'linux':
                command = ['sudo apt-get install youtube-dl --assume-yes']
                logger.log('[*] Running:' + ' '.join(command))
                stdout, stderr = self.execute_process(command)
        loader.stop()
        if stderr:
            logger.log('\n[*] Error installing: '+ self.parse_stderr(stderr), RED)
            print('[*] Could not install youtube-dl.')
            print('[+] See: https://rg3.github.io/youtube-dl')
            sys.exit()
        logger.log('\n[*] youtube-dl has been installed.', color=GREEN)