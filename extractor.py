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
logger.set_verbose()

def signalhandler(singnum, frame):
    """Handle a keyboard interrupt"""
    logger.log('\n[*] Received user keyboard interrupt.')
    print('[*] Exiting.')
    sys.exit()

class ProcessNotKilledException(BaseException):
    def __init__(self, message):
        self.message = message
    
    def __repr__(self):
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

    def execute_process(self, command, shell=True, root=False, loader=None, timeout=5):
        """Handle a process execution returning a tuple with stdout and stderr"""
        if root:
            command[0] = 'sudo ' + command[0]

        logger.log('[*] Running: '+(' '.join(command) if type(command) is list else command), YELLOW)
        process = subprocess.Popen(command, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

        try:
            if root and self._require_root:
                stdout, stderr = process.communicate()
            else:    
                stdout, stderr = process.communicate(timeout=timeout)
            if loader:
                    loader.start()
        except subprocess.TimeoutExpired:
            stdout, stderr = (b'', b'Process timed out.')

        if root and 'incorrect' in stderr.decode().lower():
            return '', 'Incorrect password.'
        
        return self._parse_output(stdout, stderr)

    def check_availability(self, command, errors=False):
        """Check if service is available on user system"""
        stderr = self.execute_process(command if type(command) is list else [command])[1]
        
        if stderr and ( 'usage' in stderr.lower() or 'Process timed out' in stderr ):
            return True
        if errors:
            return (None, stderr)
        return False

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
            attempts = 0
            while attempts < 2:
                attempts += 1
                available = self.check_availability(command, errors=True)
                if available:
                    self.installed = True
                else:
                    logger.log('[*] Error: Service is not available on system.')
                    self._install()
                    self.tried_to_install = True
                
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
        command = ['-H python' + pyversion + ' -m pip install youtube-dl']
        error = self.execute_process(command, root=True, loader=loader)[1]
        if error:
            logger.log('\n[-] Error: '+ error, RED)
            logger.log('[*] Last command failed.')
            if platform == 'darwin':
                command = ['brew install youtube-dl']
                stderr = self.execute_process(command, timeout=None)[1]
            elif platform == 'linux':
                command = ['apt-get install -y youtube-dl']
                error = self.execute_process(command, timeout=None, root=True)[1]
        loader.stop()
        if error:
            logger.log('\n[*] Error installing: '+ error, RED)
            print('[*] Could not install youtube-dl.')
            print('[+] See: https://rg3.github.io/youtube-dl')
            sys.exit()
        logger.log('\n[*] youtube-dl has been installed.', color=GREEN)

class Tor(Service):
    """Start a tor proxy on user machine"""
    def __init__(self):
        self.started = False
        self.tried_to_install = False
        self.installed = False
        self.ip = None
        self.socket_patched = False
        self.pid = None

    def start(self):
        """Start tor"""
        if self.started:
            logger.log('[*] Service already started.')
            return True
       
        if not self._kill_process():
            raise ProcessNotKilledException('Could not kill a already running tor process.')

        logger.log('[*] Starting tor service.')
        command = ['tor']
        if not self.installed and not self.tried_to_install:
            tries = 0
            while tries < 2:
                available = self.check_availability(command)
                tries += 1
                if not available:
                    if platform == 'linux':
                        logger.log('[*] Trying to start with systemctl interface.', YELLOW)
                        stderr = self.execute_process(['systemctl start tor.service'], root=True)[1]
                        if not stderr:
                            self.installed = True
                            break
                    logger.log('[*] Error: '+ stderr, RED)
                    self._install()
                else:
                    self.installed = True
                    break
                
        if self.tried_to_install and not self.installed:
            return False

        self._kill_process()
        self._start_in_background()
        return True

    def restart(self, *args):
        """Restart tor service"""
        if not self.started:
            return self.start()

        if not self.installed and self.tried_to_install:
           raise Exception('Trying to restart a not installed service.')
    
        self.stop()
        if platform == 'linux':
            if not self.execute_process(['systemctl restart tor'], root=True)[1]:
                logger.log('[*] Restarted tor on systemctl interface.', YELLOW)
                self.started = True
                return True

        self._start_in_background()
        return True

    def stop(self):
        """Stop running process"""
        logger.log('[*] Stopping tor service.')
        self.event.clear()
        time.sleep(1)

        # kill any remaining process
        self._kill_process()

    def _start_in_background(self):
        """Start service in background with a Thread"""
        if self.started:
            logger.log('[*] Tor service already running.')
        elif not self.installed and self.tried_to_install:
            logger.log('[*] Cannot start in background. First must be installed.')

        def run():
            logger.log('[*] Started tor process in background.')
            process = subprocess.Popen(['tor'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while self.event.is_set():
                process.communicate()
                time.sleep(1)
            self.started = False

            # receive the process return code
            if process.poll() and process.poll() < 0:
                if platform == 'windows':
                    process.terminate()
                else:
                    process.kill()
        self.started = True
        self.event.set()
        threading.Thread(target=run).start()
    
    def _install(self):
        """Try to install tor with system installers"""
        loader = Loader(message='[*] Installing tor', color=YELLOW)
        loader.start()
        if platform == 'darwin':
            command = ['brew install tor']
            stderr = self.execute_process(command, timeout=None)[1]
        elif platform == 'linux':
            command = ['apt-get install -y tor']
            stdout, stderr = self.execute_process(command, timeout=None, root=True)   
        else:
            loader.stop()
            print('\n[-] You are using Windows. No available installers.')
            print('[+] See: https://rg3.github.io/youtube-dl')
            sys.exit()
        loader.stop()
        if stderr:
            logger.log('\n[*] Error installing: '+ stderr, RED)
            print('[*] Could not install tor.')
            print('[+] See: https://rg3.github.io/youtube-dl')
            sys.exit()
        self.tried_to_install = True
        logger.log('\n[*] tor has been installed.', color=GREEN)

    def _kill_process(self):
        """Handle the process being executed on tor default port and kill it"""
        if platform == 'windows':
            command = ['netstat -ano | findstr :9050']
            stdout, sterr = self.execute_process(command)
            if not stdout:
                return True
            else:
                stdout = ' '.join([e for e in stdout.split(' ') if e])
                pid = re.findall(r'LISTENING (\d)+', stdout)
                if len(pid) > 0:
                    stderr = self.execute_process(['taskkill /PID {} /F'.format(pid[0])])[1]
                    if not stderr:
                        return True
                return False

        elif platform == 'darwin':
            command = ['lsof -i tcp:9050']
            stdout, stderr = self.execute_process(command)
            if not stdout:
                return True
            else:
                stdout = ' '.join([e for e in stdout.split(' ') if e])
                pid = re.findall(r"[a-zA-Z]\s(\d+)", stdout)
                if len(pid) > 0:
                    stderr = self.execute_process(['kill '+ pid[0]], root=True)[1]
                    if not stderr:
                        return True
                return False
        else:
            command = ['sudo systemctl stop tor']
            self.execute_process(command)[1]
            command = ['netstat -nlp | grep 9050']
            stdout, stderr = self.execute_process(command, root=True)
            if not stdout:
                return True
            else:
                pid = re.findall(r"(\d+)\/[a-zA-Z]+", stdout)
                if len(pid) > 0:
                    stderr = self.execute_process(['kill '+ pid[0]], root=True)[1]
                    if not stderr:
                        return True
                return False
