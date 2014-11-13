#!/usr/bin/python2
# coding: utf-8

import os
import shelve

DEBUG = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILENAME = os.path.join(BASE_DIR, 'NCV.shelve')
DB = shelve.open(DB_FILENAME, writeback=True)

HOME_DIR = os.environ['HOME']
ICON_DIR = os.path.join(BASE_DIR, 'icons')

BROWSER_CHROME_SETTINGFILE_PATH = os.path.join(HOME_DIR, '.config/google-chrome/Default/Cookies')
BROWSER_CHROMIUM_SETTINGFILE_PATH = os.path.join(HOME_DIR, '.config/chromium/Default/Cookies')
BROWSER_FIREFOX_SETTINGFILE_PATH = os.path.join(HOME_DIR, '.mozilla/firefox/profiles.ini')

NICO_LOGIN_URL = 'https://secure.nicovideo.jp/secure/login?site=niconico'