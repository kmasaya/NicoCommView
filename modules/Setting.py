#!/usr/bin/python
# encoding: utf-8

import os
import pickle

class Setting:
    """
    設定クラス
    """
    p            = None # 設定保存ディクショナリ
    nicknameFile = None # ニックネーム辞書のファイル名
    settingFile  = None # 設定保存ファイル名

    def __init__( self):
        """
        コンストラクタ
        
        引数:
        
        返し値:
        
        """
        # 設定ファイル名
        self.settingFile  = "./setting.pickle"
        self.commentFile  = "./comment.pickle"
        self.nicknameFile = "./nick.pickle"

        # 設定ファイルが無ければ初期化
        if not os.access( self.settingFile, os.F_OK):
            self.SettingInitialize()
        # 設定ファイルがあれば読み込み
        else:
            self.Load()

    def SettingInitialize( self):
        """
        設定の初期化
        
        引数:
        
        返し値:
        
        """
        # 設定の初期化
        self.p = {}
        self.p[ "ctype"]              = 0            # クッキーを取得するブラウザ
        self.p[ "pmod"]               = 0            # コメントを投稿するモディファイアキー
        self.p[ "184"]                = True         # 184でコメントするか
        self.p[ "browser"]            = "gnome-open" # リンクを開くブラウザ名
        self.p[ "nickOw"]             = True         # ニックネームの上書きを許可
        self.p[ "nickOwIsNum"]        = True         # ニックネームが数値の場合上書きを許可
        self.p[ "BgOwnerColorChange"] = True         # 放送主のコメントカラーを変更を許可
        self.p[ "BgOwnerColor"]       = "#DDEEFF"    # 放送主のコメントカラー
        self.p[ "BgNgColor"]          = "#FFD7F6"    # NGのコメントカラー
        
    def Load( self):
        """
        設定の読み込み
        
        引数:
        
        返し値:

        """
        # 設定の読み込み
        f = open( self.settingFile, "r")
        self.p = pickle.load( f)
        f.close()
    
    def Save( self):
        """
        設定の保存
        
        引数:
        
        返し値:
        
        """

        # 設定の保存
        f = open( self.settingFile, "w")
        pickle.dump( self.p, f)
        f.close()
        