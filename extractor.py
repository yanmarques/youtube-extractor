#!/usr/bin/python
# -*- coding: UTF-8 -*-

__author__  = 'Yan Marques de Cerqueira'
__email__   = 'marques_yan@outlook.com'
__git__     = 'https://github.com/yanmarques/youtube-extractor'
__version__ = '1.0'
__banner__  = 'youtube-extractor v.%s' % __version__ 

from logger import *
from abc import abstractmethod
from argparse import ArgumentParser, ArgumentError
import sys
import os
import subprocess 
import itertools
import time
import threading
import re
import ssl
import socks
import stem.process
import urllib.request
import signal

# Detects user platform
if sys.platform.startswith('win32'):
    platform = 'windows'
elif sys.platform.startswith('darwin'):
    platform = 'darwin'
else:
    platform = 'linux' 

pyversion = '.'.join(str(minor) for minor in sys.version_info[:2])
logger = Logger()

def parse_opts():
    arguments = ArgumentParser(usage='usage: [options] [url...]')
    arguments.add_argument('--verbose', help='Be moderately verbose to watch every script step.', dest='verbose', action='store_true', default=False)
    arguments.add_argument('-a', '--audio', help='Only extract audio.', dest='audio', action='store_true', default=False)
    arguments.add_argument('--audio-quality', help='Audio quality.', dest='audio_quality', type=int, default=0)
    arguments.add_argument('--audio-format', help='Audio format.', dest='audio_format', type=str)
    arguments.add_argument('-v', '--video', help='Only extract video.', dest='video', action='store_true', default=False)
    arguments.add_argument('--video-quality', help='Video quality.', dest='video_quality', type=int, default=0)
    arguments.add_argument('--video-format', help='Video format.', dest='video_format', type=str)
    arguments.add_argument('-t', help='Number of threads to use.', dest='threads', type=int, default=1)
    arguments.add_argument('--without-tor', help='Disable tor.', dest='tor', action='store_false', default=True)
    arguments.add_argument('-f', help='Read urls from specified file.', dest='file', type=str)
    arguments.add_argument('url', help='Url to extract data', action='append', nargs='*')
    return arguments.parse_args()

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

    def execute_process(self, command, shell=True, root=False, loader=None, timeout=5, pid=False):
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
        
        output, errors = self._parse_output(stdout, stderr)
        if pid:
            return output, errors, process.pid
        return output, errors

    def check_availability(self, command):
        """Check if service is available on user system"""
        stderr = self.execute_process(command if type(command) is list else [command])[1]
        
        if stderr and ( 'usage' in stderr.lower() or 'Process timed out' in stderr ):
            return True
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
                available = self.check_availability(command)
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
        error = self.execute_process([' '.join(command)], timeout=None)[1]
        if error and not 'help' in error.lower():
            logger.log('[*] Error output: '+ error, RED)
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
                command = ['HOMEBREW_NO_AUTO_UPDATE=1 brew install youtube-dl']
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
        pid = self._is_process_running()
        print(pid)
        if self.started or pid:
            self.pid = pid
            logger.log('[*] Service already started.')
            return True
       
        logger.log('[*] Starting tor service.')
        if not self.started:
            if not self._start_in_background(): 
                logger.log('[*] Error: Service is not available on system.', RED)
                self._install()  
                # auto restart script
                os.execv(sys.executable, [sys.executable] + sys.argv)

        if not self.installed and self.tried_to_install:
            print(RED +'[-] Could not run or install tor.'+ NULL)
            return False
        return True

    def restart(self, *args):
        """Restart tor service"""
        if not self.started:
            return self.start()

        if not self.installed and self.tried_to_install:
           raise Exception('Trying to restart a not installed service.')

        self.stop()
        if platform == 'linux':
            # try to restart tor using systemctl interface
            if not self.execute_process(['systemctl restart tor'], root=True)[1]:
                logger.log('[*] Restarted tor on systemctl interface.', YELLOW)
                self.started = True
                return True

        self._start_in_background()
        return True

    def stop(self):
        """Stop running process"""
        logger.log('[*] Stopping tor service.')

        # kill any remaining process
        self._kill_process()
        self.socket_patched = False
        self.pid = None
        self.ip = None
        self.started = False

    def get_ip(self):
        """Return tor IP"""
        if not self.ip:
            self._set_identity()
        return self.ip

    def _start_in_background(self):
        """Start service in background with a Thread"""
        if self.started:
            logger.log('[*] Tor service already running.')
        
        if platform == 'linux':
            errors, pid = self.execute_process(['systemctl start tor'], root=True, pid=True)[0:]
            if not errors:
                logger.log('[*] Started tor on systemctl interface.', YELLOW)
                self.pid = pid
                self.started = True
                return True
        try:
            process = stem.process.launch_tor()
            self.pid = process.pid
            self.started = True
        except OSError:
            logger.log('[-] Failed to start tor.', RED)
            return False
        return True
    
    def _install(self):
        """Try to install tor with system installers"""
        loader = Loader(message='[*] Installing tor', color=YELLOW)
        loader.start()
        if platform == 'darwin':
            command = ['HOMEBREW_NO_AUTO_UPDATE=1 brew install tor']
            error = self.execute_process(command, timeout=None)[1]
        elif platform == 'linux':
            command = ['apt-get install -y tor']
            error = self.execute_process(command, timeout=None, root=True)[1]
        else:
            loader.stop()
            print('\n[-] You are using Windows. No available installers.')
            print('[+] See: https://rg3.github.io/youtube-dl')
            sys.exit()
        loader.stop()
        if error:
            logger.log('\n[*] Error installing: '+ error, RED)
            print('[*] Could not install tor.')
            print('[+] See: https://rg3.github.io/youtube-dl')
            sys.exit()
        self.tried_to_install = True
        logger.log('\n[*] tor has been installed.', color=GREEN)

    def _is_process_running(self):
        """Determine wheter there is a tor process running."""
        if platform == 'windows':
            command = ['netstat -ano | findstr :9050']
            output = self.execute_process(command)[0]
            if output:
                output = ' '.join([e for e in output.split(' ') if e])
                pid = re.findall(r'LISTENING (\d)+', output)
                if len(pid) > 0:
                    return pid[0]
        elif platform == 'darwin':
            command = ['lsof -i tcp:9050']
            output = self.execute_process(command)[0]
            if output:
                output = ' '.join([e for e in output.split(' ') if e])
                pid = re.findall(r'[a-zA-Z]\s(\d+)', output)
                if len(pid) > 0:
                    return pid[0]
        else:
            command = ['netstat -nlp | grep 9050']
            output = self.execute_process(command, root=True)[0]
            if output:
                pid = re.findall(r"(\d+)\/[a-zA-Z]+", output)
                if len(pid) > 0:
                    return pid[0]
        return False

    def _kill_process(self):
        """Handle the process being executed on tor default port and kill it"""
        if self.started and self.pid:
            if platform == 'windows':
                error = self.execute_process(['taskkill /PID {} /F'.format(self.pid)])[1]
            else:
                error = self.execute_process(['kill ' + str(self.pid)])[1]
            if not error:
                return True

        # Get pid if process is running.
        pid = self._is_process_running()

        if pid:
            if platform == 'windows':
                error = self.execute_process(['taskkill /PID {} /F'.format(pid)])[1]
                if not error:
                    return True
            elif platform == 'linux':
                error = self.execute_process(['kill {}'.format(pid)], root=True)[1]
                if not error:
                    return True
            return False
        return True

    def _set_identity(self):
        """Set tor service IP"""
        if self.started:
            logger.log('[*] Checking if tor is running and get relay ip. It can take a while...', YELLOW)
            if not self.socket_patched:
                # use monkey patching method to pass default proxy through socket
                socks.set_default_proxy(socks.SOCKS5, '127.0.0.1', 9050)
                socks.wrapmodule(urllib.request)
                self.socket_patched = True
            context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            response = urllib.request.urlopen('https://check.torproject.org', context=context).read()
            if 'Congratulations. This browser is configured to use Tor' in response.decode():
                ip = re.findall(r'Your IP address appears to be\:  \<strong\>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', response.decode())
                if len(ip) is 0:
                    print(RED + '[-] Something on check tor website changed and we was unable to determine our IP.')
                    print('[-] Please report a issue https://github.com/yanmarques/youtube-extractor/issues.')
                    print('[*] We will be now trying to get out IP on another aproach.' + NULL)
                    ip = urllib.request.urlopen('http://www.icanhazip.com').read()
                    self.ip = ip.decode().strip()
                else:
                    self.ip = ip[0]
            else:
                raise Exception('Could not bind tor proxy on socket.')
        else:
            raise Exception('Tor service not started. Unable to get indentity')

class Extractor(object):
    """Extract video/audio from youtube urls with threading."""
    def __init__(self, opts):
        self.opts = opts
        self.params = self._parse_opt(opts)
        self.urls = self._parse_urls(opts)
        self.tor = None
        self.threads = opts.threads

    def run(self, with_overlapping=True):
        manager = ThreadingManager(self.threads)
        ydl = YoutubeDl()
        ydl.start()
        print(self.tor.get_ip())
        for url in self.urls:
            manager.add(self._run_yotube_dl_service, ydl, url)
        manager.start()
        print(GREEN + '[+] Download finished.' + NULL)

    def _run_yotube_dl_service(self, ydl, url):
        ydl.start(' '.join(self.params) + ' {}'.format(url))

    def _parse_opt(self, opts):
        """Parse user options"""
        params = []

        # TODO - Add option to extract audio and video
        if opts.audio and opts.video:
            raise Exception('You choosed to extract both audio and video. This option is still not available.')
    
        if opts.verbose:
            logger.set_verbose()

        if opts.audio:
            params.append('-x')
            params.append('--audio-quality ' + str(opts.audio_quality))
            params.append('--audio-format ' + (opts.audio_format if opts.audio_format else 'mp3'))
        elif opts.video:
            params.append('-f')
            params.append('--video-quality ' + str(opts.video_quality))
            params.append('--video-format ' + (opts.video_format if opts.video_format else 'mp4'))
        params.append('--no-check-certificate')

        if opts.tor:
            # Start tor
            self.tor = Tor()
            self.tor.start()

        return params

    def _parse_urls(self, opts):
        """Retrive all urls from options"""
        if opts.file:
            path = os.path.normpath(opts.file)
            if os.path.isfile(path):
                with open(path, 'rb') as handler:
                    urls = handler.read().decode().split('\n');
                    for index, url in enumerate(urls):
                        if not re.match(r'^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/watch\?v\=.+$', url):
                            logger.log('[-] Skipping URL: ' + url)
                            del urls[index]
                    opts.url = urls
            else:
                raise ArgumentError('-f', 'File does not exist') 
        if len(opts.url) == 0:
            raise ArgumentError('No urls specified.', 'url')  
        return opts.url    

class ThreadingManager(object):
    """Manage concurrencie running threads"""
    def __init__(self, concurrencies, with_overlapping=True):
        self.concurrencies = concurrencies
        self.threads = []
        self.started = 0
        self.executed = 0
        self.overlap = with_overlapping
        self.event = threading.Event()

    def add(self, function, *args):
        """"Add a thread to manager"""
        self.threads.append(threading.Thread(target=self._wrap_function, args=(function, *args)))

    def start(self):
        """Started all threads in concurrency mode"""
        if self.concurrencies >= len(self.threads):
            for thread in self.threads:
                thread.start()
                thread.join()
        else:
            self.event.set()
            for thread in self.threads[:self.concurrencies]:
                thread.start()
                thread.join()    
                self.started += 1
            self._manage_threads()

    def stop(self):
        """Stop all registered threads"""
        self.event.clear()

    def _wrap_function(self, function, *args):
        """Wrap the callback on thread function"""
        function(*args)
        self.executed += 1

    def _manage_threads(self):
        """Manage all registered threads to overlap each one or run in sequence"""
        while self.event.is_set():
            if len(self.threads) == self.executed:
                self.stop()
                continue
            if self.overlap:
                if self.executed - self.started >= 0:
                    end = self.executed - self.started if self.concurrencies - (self.executed - self.started) <= 0 else self.concurrencies
                    for thread in self.threads[self.started:self.started + end]:
                        thread.start()
                        self.started += 1
            else:
                if self.started == self.executed:
                    for thread in self.threads[self.started:self.started + self.concurrencies]:
                        thread.start()
                        self.started += 1

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signalhandler)
    opts = parse_opts()
    extractor = Extractor(opts)
    extractor.run()