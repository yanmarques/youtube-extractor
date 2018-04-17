# Table of Contents
 - [Description](#description)
 - [Installation](#installation)
 - [Usage](#usage)
 - [Options](#options)

# Description
Python script to extract audio or videos from youtube. We use the wonderfull [youtube-dl](https://github.com/rg3/youtube-dl)
module to extract the content, and [tor](https://www.torproject.org) as proxy server using with experimental purpose.

# Installation
Youtube-extractor is a python program and requires [PySocks](https://pypi.org/project/PySocks/) and [stem](https://pypi.org/project/stem/). Please install this modules with manually or use the requirements text file. To install with text file, type:
```
  pip install -r requirements.txt
```

- If you do not have python installed on your computer, please read [this](http://docs.python-guide.org/en/latest/starting/install3/linux/) article.

# Usage
The script uses youtube-dl to download the desired content. But we starts the tor proxy to be runned with youtube-dl downloads.
```
usage: usage: [options] [url...]
```

# Options
The options to download the desired content from script.
```
  -h, --help            show this help message and exit
  --verbose             Be moderately verbose to watch every script step.
  -a, --audio           Only extract audio.
  --audio-quality       Audio quality.
  --audio-format        Audio format.
  -v, --video           Only extract video.
  --video-quality       Video quality.
  --video-format        Video format.
  -t THREADS            Number of threads to use.
  --with-tor            Enable tor. [Experimental].
  -f FILE               Read urls from specified file.
```
