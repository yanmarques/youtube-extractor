# Terminal colors
NULL   = '\033[0m' # -> Reset
BLUE   = '\033[34m' 
YELLOW = '\033[33m' 
GREEN  = '\033[32m' 
RED    = '\033[031m'

class Logger(object):
    """Print verbosity layer"""
    def __init__(self):
        self.__verbose = False

    def log(self, message, color=NULL):
        if self.__verbose:
            print(color + message + NULL)
    
    def set_verbose(self):
        self.__verbose = True
