__author__  = 'Yan Marques de Cerqueira'
__email__   = 'marques_yan@outlook.com'
__git__     = 'https://github.com/yanmarques/youtube-extractor'
__version__ = '1.0'
__banner__  = 'youtube-extractor v.%s' % __version__ 

import sys

# Detects user platform
if sys.platform.startswith('win32'):
    platform = 'windows'
elif sys.platform.startswith('darwin'):
    platform = 'darwin'
else:
    platform = 'linux' 

pyversion = '.'.join(str(minor) for minor in sys.version_info[:2])