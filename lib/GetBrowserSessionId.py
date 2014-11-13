#!/usr/bin/python2
# coding: utf-8

import os
import sys
import sqlite3
import shutil
import ConfigParser

from Setting import HOME_DIR
from Setting import BROWSER_CHROME_SETTINGFILE_PATH, BROWSER_CHROMIUM_SETTINGFILE_PATH, BROWSER_FIREFOX_SETTINGFILE_PATH


class GetBrowserSessionId:
    def __init__(self, browser_name, profile='default'):
        # GoogleChrome
        if browser_name == 'gc':
            if profile == 'default':
                cookie_file_path = BROWSER_CHROME_SETTINGFILE_PATH
            else:
                cookie_file_path = os.path.join(HOME_DIR, profile)

            if not os.path.exists(cookie_file_path):
                print 'クッキーファイルが見つかりません'
                print 'PATH : ' + cookie_file_path
                sys.exit(1)

            cnc = sqlite3.connect(cookie_file_path)
            cur = cnc.cursor()

            # セッションID取得SQL
            sql = r'select value from cookies where name="user_session" and host_key=".nicovideo.jp"'

            # SQL発行
            try:
                rows = cur.execute(sql)
            except sqlite3.Error:
                print 'セッションIDが見つかりません'
                sys.exit(1)

            for row in rows:
                self.session_id = row[0]

            cnc.close()

        # Chromium
        elif browser_name == 'ch':
            if profile == 'default':
                cookie_file_path = BROWSER_CHROMIUM_SETTINGFILE_PATH
            else:
                cookie_file_path = os.path.join(HOME_DIR, profile)

            if not os.path.exists(cookie_file_path):
                print 'クッキーファイルが見つかりません'
                print 'PATH : ' + cookie_file_path
                sys.exit(1)

            cnc = sqlite3.connect(cookie_file_path)
            cur = cnc.cursor()

            sql = r'select value from cookies where name="user_session" and host_key=".nicovideo.jp"'

            try:
                rows = cur.execute(sql)
            except sqlite3.Error:
                print 'セッションIDが見つかりません'
                sys.exit(1)

            for row in rows:
                self.session_id = row[0]

            cnc.close()

        # Firefox
        elif browser_name == 'fx':
            setting_file_path = BROWSER_FIREFOX_SETTINGFILE_PATH

            if not os.path.exists(setting_file_path):
                print 'プロファイルファイルが見つかりません'
                print 'PATH : ' + setting_file_path
                sys.exit(1)

            ini_parser = ConfigParser.ConfigParser()
            ini_parser.read(setting_file_path)

            cookie_dir = None
            profiles = ini_parser.sections()
            for profile in profiles:
                items = ini_parser.items(profile)
                for (item, value) in items:
                    if item == profile:
                        for (profile_item, profile_value) in items:
                            if item == 'path':
                                cookie_dir = profile_value

            # XXX
            cookie_file_path = os.path.dir(HOME_DIR, '/.mozilla/firefox/', cookie_dir, 'cookies.sqlite')

            if not os.path.join(cookie_file_path):
                print 'クッキーファイルが見つかりません'
                print 'PATH : ' + cookie_file_path
                sys.exit(1)

            # ロック回避のためにクッキーファイルのコピー
            cookie_file_clone_path = '/tmp/ncvFxCookies.sqlite.tmp'
            shutil.copyfile(cookie_file_path, cookie_file_clone_path)
            cookie_file_path = cookie_file_clone_path

            cnc = sqlite3.connect(cookie_file_path)
            cur = cnc.cursor()

            sql = r'select value from moz_cookies where name = "user_session" and host=".nicovideo.jp"'

            try:
                rows = cur.execute(sql)
            except sqlite3.Error:
                print 'セッションIDが見つかりません'
                sys.exit(1)

            for row in rows:
                self.session_id = row[0]

            cnc.close()

        # netrc
        elif browser_name == 'nr':
            # TODO
            self.session_id = ''
