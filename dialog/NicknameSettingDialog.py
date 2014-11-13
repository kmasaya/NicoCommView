#!/usr/bin/python2
# coding: utf-8

import gtk


class NicknameSettingDialog(gtk.Dialog):
    """
    ニックネーム設定ダイアログ
    """

    nickname_entry = None

    def __init__(self, user_id, nick, *args, **kwargs):
        gtk.Dialog.__init__(self, *args, **kwargs)

        self.window_initialize(user_id, nick)

    def window_initialize(self, user_id, nick):
        # デフォルトレスポンスを設定
        self.set_default_response(gtk.RESPONSE_OK)

        # 格納ボックス
        nick_box = gtk.VBox()

        # ID表示ラベル
        label_id = gtk.Label(user_id)

        # ニックネーム入力エントリ
        self.nickname_entry = gtk.Entry()
        self.nickname_entry.set_activates_default(True)
        self.nickname_entry.set_text(nick)
        self.nickname_entry.grab_focus()

        # ボックスに格納
        nick_box.add(label_id)
        nick_box.add(self.nickname_entry)

        # ダイアログにボックスを格納
        self.vbox.add(nick_box)

        # 全てを表示
        self.vbox.show_all()

    def get_nickname(self):
        return self.nickname_entry.get_text()

