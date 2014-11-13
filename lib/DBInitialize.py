#!/usr/bin/python2
# coding: utf-8

from Setting import DB


class DBInitialize:
    def __init__(self):
        self.db = DB

        if 'setting' not in self.db:
            self.initialize()

    def initialize(self):
        self.db['setting'] = {}
        # XXX
        self.db['setting']['cookie_browser'] = 0  # クッキーを取得するブラウザ
        self.db['setting']['open_browser'] = 'gnome-open'  # リンクを開くブラウザ名

        self.db['setting']['comment_enter_modifier'] = 0  # コメントを投稿するモディファイアキー
        self.db['setting']['comment_is_184'] = True  # 184でコメントするか

        self.db['setting']['nickname_overwrite_is'] = True  # ニックネームの上書きを許可する
        self.db['setting']['nickname_overwrite_num_is'] = True  # ニックネームが数値の場合も上書きする

        self.db['setting']['bg_owner_color_change_is'] = True  # 放送主のコメントカラーを変更する
        self.db['setting']['bg_owner_color'] = '#DDEEFF'  # 放送主のコメントカラー
        self.db['setting']['bg_ng_color'] = '#FFD7F6'  # NGのコメントカラー

        self.db['nickname'] = {}

        self.db.sync()