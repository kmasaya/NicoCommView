#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
クッキーファイルより値を取得する
現在は、Google Chrome(Chromium)のみ対応
"""

import os
import sys
import sqlite3
import shutil
import ConfigParser
        
class NicoSessionId:
    """
    ニコニコ動画セッションクラス
    """

    def __init__( self, btype, profile = "default"):
        """
        コンストラクタ
        
        引数:
        btype   - ブラウザタイプ
        profile - プロファイル
        返し値:
        
        """
    
        self.sessionId = self.Get( btype, profile)
    
    def __del__( self):
        """
        デストラクタ
        
        引数:
        
        返し値:
        
        """
        pass

    def Get( self, btype, profile = "default"):        
        """
        クッキーよりセッションIDを抽出する

        引数:
        btype - 
        # ブラウザタイプを選択
        # Type Values
        # gc - Google Chrome
        # ch - Chromium
        # fx - Firefox
        # nr - netrc
        profile -
        # ブラウザプロファイル名
        # default - デフォルトプロファイル
        
        返し値:
         - セッションID
        """
    
        # ブラウザ別クッキー取得処理
        # GoogleChrome
        if btype == "gc":
            # profileよりクッキーファイルの位置を設定
            homeDir  = os.environ["HOME"] 
            if profile == "default":
                cookieFile = homeDir + r"/.config/google-chrome/Default/Cookies"
            else:
                cookieFile = homeDir + profile

            # クッキーファイルの存在確認
            if not os.access( cookieFile, os.F_OK):
                print "クッキーファイルが見つかりません"
                print "PATH : " + cookieFile
                sys.exit( 1)

            # クッキーファイルに接続
            cnc = sqlite3.connect( cookieFile)
            cur = cnc.cursor()
            
            # セッションID取得SQL
            sql = r'select value from cookies where name="user_session" and host_key=".nicovideo.jp"'
            
            # SQL発行
            try:
                rows = cur.execute( sql)
            except:
                print "セッションIDが見つかりません"
                sys.exit( 1)
    
            # セッションIDを設定
            sessionId = None
            # セッションIDを返す
            for row in rows:
                sessionId = row[0]
    
            # クッキーファイルから切断
            cnc.close()
            
            return sessionId
        
        # Chromium
        elif btype == "ch":
            # profileよりクッキーファイルの位置を設定
            homeDir  = os.environ["HOME"]
            if profile == "default":
                cookieFile = homeDir + r"/.config/chromium/Default/Cookies"
            else:
                cookieFile = homeDir + profile
            
            # クッキーファイルの存在確認
            if not os.access( cookieFile, os.F_OK):
                print "クッキーファイルが見つかりません"
                print "PATH : " + cookieFile
                sys.exit( 1)
            
            # クッキーファイルに接続
            cnc = sqlite3.connect( cookieFile)
            cur = cnc.cursor()
            
            # セッションID取得SQL
            sql = r'select value from cookies where name="user_session" and host_key=".nicovideo.jp"'
            
            # SQL発行
            try:
                rows = cur.execute( sql)
            except:
                print "セッションIDが見つかりません"
                sys.exit( 1)
    
            # セッションIDを設定
            sessionId = None
            # セッションIDを返す
            for row in rows:
                sessionId = row[0]
    
            # クッキーファイルから切断
            cnc.close()
            
            return sessionId
    
            
        # Firefox
        elif btype == "fx":
            # profileよりクッキーファイルの位置を設定
            homeDir = os.environ["HOME"]
            iniFile  = homeDir + "/.mozilla/firefox/profiles.ini" 
    
            # iniファイルの存在確認
            if not os.access( iniFile, os.F_OK):
                print "プロファイルファイルが見つかりません"
                print "PATH : " + iniFile
                sys.exit( 1)
    
            # iniファイルパーサ
            iniParse = ConfigParser.ConfigParser()
            iniParse.read( iniFile)
            
            # プロファイルファイルのプロファイルよりフォルダPATHを取得
            cookieDir = None
            profiles  = iniParse.sections()
            for profile in profiles:
                items = iniParse.items( profile)
                for ( item, value) in items:
                    if item == profile:
                        for ( item, value) in items:
                            if item == "path":
                                cookieDir = value
            
            # クッキーファイルパス
            cookieFile = homeDir + "/.mozilla/firefox/" + cookieDir + "/cookies.sqlite"
            
            # クッキーファイルの存在確認
            if not os.access( cookieFile, os.F_OK):
                print "クッキーファイルが見つかりません"
                print "PATH : " + cookieFile
                sys.exit( 1)
    
            # ロック回避のためにクッキーファイルのコピー
            cookieFileCp = "/tmp/ncvFxCookies.sqlite.tmp"
            shutil.copyfile( cookieFile, cookieFileCp)
            cookieFile = cookieFileCp
    
            # クッキーファイルに接続
            cnc = sqlite3.connect( cookieFile)
            cur = cnc.cursor()

            # セッションID取得SQL
            sql = r'select value from moz_cookies where name = "user_session" and host=".nicovideo.jp"'
    
            # SQL発行
            try:
                rows = cur.execute( sql)
            except:
                print "セッションIDが見つかりません"
                sys.exit( 1)
    
            # セッションIDを設定
            sessionId = None
            # セッションIDを返す
            for row in rows:
                sessionId = row[0]
    
            # クッキーファイルから切断
            cnc.close()
            
            return sessionId
    
        # NoResource
        elif btype == "nr":
            # TODO: netrcを使うときの処理をこのモジュールに入れるか考える
            return ""

        # ブラウザが許容値以外
        else:
            print "ブラウザタイプが不正です"
            sys.exit( 1)
        
