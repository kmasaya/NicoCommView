#!/usr/bin/python2
# coding: utf-8

import os
import time
import socket
import re
import urllib
import urllib2
import netrc
from xml.dom import minidom
import gobject
import cookielib
import gtk

from lib.DBInitialize import DBInitialize
from lib.GetBrowserSessionId import GetBrowserSessionId
from lib.NgCommentDict import ng_comments
from dialog.NicknameSettingDialog import NicknameSettingDialog
from Setting import ICON_DIR, NICO_LOGIN_URL, DB, DEBUG


def debug(debug_print):
    if DEBUG:
        print debug_print


def str2html_escape(raw_str):
    return raw_str.replace(r'&', '&amp;').replace(r'<', '&lt;').replace(r'>', '&gt;').replace(r'\"', '&quote;')


def str2html_unescape(comment):
    return comment.replace("&lt;", r"<").replace("&gt;", r">").replace("&quote;", r"\"").replace("&amp;", r"&")


class Live:
    # 接続用
    opener = None  # Opener
    socket = None  # ソケット

    # ニコ生用
    comment_server_address = None  # コメントサーバのURI
    comment_server_port = None  # コメントサーバポート番号
    comment_thread_id = None  # コメントのスレッドID
    comment_basetime = None  # コメント基礎時間
    comment_count = None  # 現在のコメント数

    user_id = None  # ユーザID
    user_premium = None  # ユーザがプレミアか (0:一般 1:プレミア 3:放送主
    ticket = None  # チケット番号
    vpos = None  # Vpos

    # ユーザ設定
    anonymity = None  # 匿名 # 184(匿名(コメント時184でコメント))
    comments = []  # コメントリスト
    connecting = False  # 放送接続フラグ

    live_page_title = None

    def __init__(self, live_uri, session_id):
        self.set_opener(session_id)

        # セッションIDが空ならnetrcから接続情報を読み込みログインを行う
        if not session_id:
            # TODO netrc読み込み時の例外
            # TODO ログイン時の例外
            info = netrc.netrc().authenticators('nicovideo')
            mail = info[0]
            password = info[2]
            self.make_session(mail, password)

        self.live_connect(live_uri)

    def live_connect(self, live_uri):
        """
        放送が存在していれば接続
        """
        def parse_live_title(dom):
            """
            放送タイトル
            """
            title = dom.getElementsByTagName('title')[0].firstChild.data.strip()

            return title

        def parse_live_status(dom):
            """
            放送状態
            """
            status = dom.getElementsByTagName('getplayerstatus')[0].getAttribute("status")

            if status == "ok":
                return True
            else:
                return False

        def parse_player_status(dom):
            """
            放送ステータス
            """
            # XXX
            child = dom.getElementsByTagName('getplayerstatus')[0]
            if child.getElementsByTagName('ms'):
                ms_dom = child.getElementsByTagName('ms')[0]
                # コメントサーバURI
                self.comment_server_address = ms_dom.getElementsByTagName('addr')[0].firstChild.data.strip()
                # コメントサーバポート番号
                self.comment_server_port = int(ms_dom.getElementsByTagName('port')[0].firstChild.data.strip())
                # コメントのスレッドID
                self.comment_thread_id = ms_dom.getElementsByTagName('thread')[0].firstChild.data.strip()
            if child.getElementsByTagName('user'):
                user_dom = child.getElementsByTagName('user')[0]
                # ユーザID
                self.user_id = user_dom.getElementsByTagName('user_id')[0].firstChild.data.strip()
                # ユーザがプレミアかどうか(0:一般 1:プレミアム
                self.user_premium = user_dom.getElementsByTagName('is_premium')[0].firstChild.data.strip()
            if child.getElementsByTagName('stream'):
                stream_dom = child.getElementsByTagName('stream')[0]
                # コメントの基礎時間
                self.comment_basetime = stream_dom.getElementsByTagName('base_time')[0].firstChild.data.strip()
                # 現在のコメント数
                self.comment_count = int(stream_dom.getElementsByTagName('comment_count')[0].firstChild.data.strip())

        live_page_dom = minidom.parseString(self.opener.open(live_uri).read())
        self.live_page_title = parse_live_title(live_page_dom)

        if parse_live_status(live_page_dom):
            parse_player_status(live_page_dom)
            self.socket_connect()
            self.vpos = int((time.time() - float(self.comment_basetime)) * 100)
            self.connecting = True

    def set_opener(self, session_id, ua='NicoCommView'):
        cookie_jar = cookielib.CookieJar()

        if session_id:
            ck = cookielib.Cookie(version=0, name='user_session', value=session_id, port=None, port_specified=False,
                                  domain='.nicovideo.jp', domain_specified=False, domain_initial_dot=False, path='/',
                                  path_specified=True, secure=False, expires=None, discard=True, comment=None,
                                  comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
            cookie_jar.set_cookie(ck)

        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
        self.opener.addheaders = [("User-agent", ua)]

    def make_session(self, mail, password):
        request = urllib2.Request(NICO_LOGIN_URL)
        account = {"mail": mail, "password": password}
        request.add_data(urllib.urlencode(account.items()))
        self.opener.open(request)

    def socket_connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.comment_server_address, self.comment_server_port))

    def socket_disconnect(self):
        self.socket.close()

    def set_ticket(self):
        send_xml_tag = '<thread thread="%s" version="20061206" res_from="-1000" />\0' % (self.comment_thread_id,)
        self.socket.send(send_xml_tag)

    def get_comment(self):
        # ソケットデータを受信する(終端がコメントの終(</chat>)になるまで
        socket_data = ''
        pattern = re.compile(r'<thread[^>]+>$')
        while True:
            socket_data += self.socket.recv(4096).replace('\0', '')
            if socket_data.endswith('</chat>') or len(pattern.findall(socket_data)) != 0:
                break

        debug(socket_data)

        # コメントを送信した時の結果を破棄
        socket_data = re.sub(r'<chat_result[^>]+>', '', socket_data)

        # 改行を破棄
        socket_data = socket_data.replace('\r', '').replace('\n', '')

        # チケットを設定
        ticket = re.sub(r'<thread[^>]*ticket="([0-9A-Za-z-_]+)".*', r'\1', socket_data)
        # チケットを受信すれば(15文字以上なら未受信
        if len(ticket) < 15:
            self.ticket = ticket
            # チケット文字列を破棄
            socket_data = re.sub(r'<thread[^>]+>', '', socket_data)

        # コメントから情報を抜き出す
        for line in socket_data.split(r"</chat>"):
            # 行が5文字以下なら次へ(<chat>で５文字を超える
            if len(line) < 5:
                continue
            # スプリットした文字列を復帰
            line += '</chat>'

            # コメント
            comment = re.sub(r'</?chat[^>]*>', '', line)
            # コメントナンバー
            comment_number = re.sub(r'<chat[^>]*no="([0-9]+)".*', r'\1', line)
            # コメントナンバーがなければ0に
            if comment_number == line:
                comment_number = "0"
            # コメントユーザ
            comment_user = re.sub(r'<chat[^>]*user_id="([0-9a-zA-Z-_]+)".*', r'\1', line)
            # コメントユーザがいなければ運営に
            if comment_user == line:
                comment_user = "394"
            # コメント時間
            comment_time = re.sub(r'<chat[^>]*date="([0-9]+)".*', r'\1', line)
            # コメントユーザがプレミアか
            comment_premium = re.sub(r'<chat[^>]*premium="([0-9])".*', r'\1', line)
            # プレミアムじゃなければ一般に
            if comment_premium == line:
                comment_premium = "0"

            self.comments.append([comment_number, comment_user, comment, comment_premium, comment_time])
            self.comment_count = int(comment_number)

    def post_comment(self):
        uri = 'http://live.nicovideo.jp/api/getpostkey?thread=%s&block_no=%d' % (self.comment_thread_id, self.comment_count/100)
        key = self.opener.open(uri).read()
        postkey = key.split('=')[-1]

        comment_xml_tag = u'<chat thread="%s" ticket="%s" vpos="%s" postkey="%s" %s user_id="%s" premium="%s">%s</chat>\0' % (self.comment_thread_id, self.ticket, self.vpos, postkey, self.anonymity, self.user_id, self.user_premium, str2html_escape(self.comment))
        self.socket.send(comment_xml_tag)


class WinCom:
    # メインウインドウ
    main_window = None
    main_notebook = None
    tab_live_label = None
    comment_tree = None
    comment_tree_column_comment_width = None
    comment_tree_column_comment_render_text = None
    comment_tree_column_comment = None
    comment_tree_scroll = None
    live_connect_url_entry = None
    live_connect_enter_button = None
    live_connect_disconnect_enter_button = None
    live_connect_reconnect_enter_button = None
    comment_enter_184_checkbutton = None
    comment_logging_checkbox = None
    comment_enter_entry = None
    comment_enter_button = None
    comment_tree_context_menu = None
    ng_user_tree = None
    ng_user_tree_scroll = None
    ng_user_control_nickname = None
    ng_user_control_remove_all = None
    ng_user_control_remove_select = None
    setting_nickname_overwrite_checkbox = None
    setting_nickname_num_overwrite_checkbox = None
    setting_ownerbgcolor_change_checkbox = None
    setting_ownerbgcolor_change_color_entry = None
    setting_openlinkbrowser_entry = None
    setting_comment_enter_default_184_checkbox = None
    setting_hide_control_comment_checkbox = None
    setting_comment_logging_checkbox = None
    setting_comment_enter_modifier_conbobox = None
    setting_cookiebrouser_conbobox = None
    clipboard = None
    # 放送インスタンス
    live = None
    # コメントリストの最終ポインタ
    current_list_number = None
    # コメントの前番号
    before_number = None
    # Treeview行番号
    tree_iterator = None
    db = None

    def __init__(self):
        self.db = DB
        # リストポインタを初期化
        self.current_list_number = 0
        # 行番号の初期化
        self.tree_iterator = 1
        # ウインドウの初期化
        self.main_window_initialize()
        # 設定ウインドウに設定を適用
        self.setting_load()

    def main_window_initialize(self):
        # メインウインドウ
        self.main_window = gtk.Window()
        self.main_window.set_title('NicoCommView')
        self.main_window.connect('destroy_event', self.close_window)
        self.main_window.connect('delete_event', self.close_window)

        # タブ
        self.main_notebook = gtk.Notebook()
        # タブ1
        tab_live1_vbox = gtk.VBox(homogeneous=False)
        self.tab_live_label = gtk.Label("Live1")
        self.main_notebook.append_page(tab_live1_vbox, self.tab_live_label)

        # コメント表示ツリー
        self.comment_tree = gtk.TreeView(model=gtk.ListStore(str, str, str, gtk.gdk.Pixbuf, str, str))
        self.comment_tree.props.rules_hint = True
        self.comment_tree.connect('size-allocate', self.comment_tree_column_resize)
        self.comment_tree.connect("button-press-event", self.comment_tree_left_click)
        # コメント表示ツリーカラムナンバー
        comment_tree_column_number = gtk.TreeViewColumn("No", gtk.CellRendererText(), text=0)
        comment_tree_column_number.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        comment_tree_column_number.set_fixed_width(50)
        # コメント表示ツリーカラムユーザ
        comment_tree_column_user_render_text = gtk.CellRendererText()
        comment_tree_column_user = gtk.TreeViewColumn("User", comment_tree_column_user_render_text, text=1, background=5)
        comment_tree_column_user.set_resizable(True)
        comment_tree_column_user.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        comment_tree_column_user.set_fixed_width(80)
        # コメント表示ツリーカラムコメント
        self.comment_tree_column_comment_width = 380
        self.comment_tree_column_comment_render_text = gtk.CellRendererText()
        self.comment_tree_column_comment_render_text.set_property("wrap-mode", True)
        self.comment_tree_column_comment_render_text.set_property("wrap-width", self.comment_tree_column_comment_width-10)
        self.comment_tree_column_comment = gtk.TreeViewColumn("Comment", self.comment_tree_column_comment_render_text, text=2)
        self.comment_tree_column_comment.set_resizable(True)
        self.comment_tree_column_comment.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.comment_tree_column_comment.set_fixed_width(self.comment_tree_column_comment_width)
        # コメント表示ツリーステータス
        comment_tree_column_status = gtk.TreeViewColumn("S", gtk.CellRendererPixbuf(), pixbuf=3)
        comment_tree_column_status.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        comment_tree_column_status.set_fixed_width(24)
        # コメント表示ツリータイム
        comment_tree_column_time = gtk.TreeViewColumn("Time", gtk.CellRendererText(), text=4)
        comment_tree_column_time.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        comment_tree_column_time.set_fixed_width(50)
        # ツリーにカラムを追加
        self.comment_tree.append_column(comment_tree_column_number)
        self.comment_tree.append_column(comment_tree_column_user)
        self.comment_tree.append_column(self.comment_tree_column_comment)
        self.comment_tree.append_column(comment_tree_column_status)
        self.comment_tree.append_column(comment_tree_column_time)
        # コメント表示ツリースクロール
        self.comment_tree_scroll = gtk.ScrolledWindow()
        self.comment_tree_scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.comment_tree_scroll.add(self.comment_tree)

        # 放送接続
        live_connect_url_hbox = gtk.HBox()
        # 放送ID入力ボックス
        self.live_connect_url_entry = gtk.Entry()
        self.live_connect_url_entry.connect("activate", self.live_enter)
        self.live_connect_url_entry.connect("drag_data_received", self.drags_live_id)
        # エントリへのドラッグ処理
        self.live_connect_url_entry.drag_dest_set(gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP, [('text/uri-list', 0, 0), ], gtk.gdk.ACTION_COPY)
        # 放送接続ボタン
        self.live_connect_enter_button = gtk.Button("接続")
        self.live_connect_enter_button.connect("clicked", self.connect_live)
        # 放送切断ボタン
        self.live_connect_disconnect_enter_button = gtk.Button("切断")
        self.live_connect_disconnect_enter_button.connect("clicked", self.disconnect_live)
        self.live_connect_disconnect_enter_button.set_sensitive(False)
        # 放送再接続ボタン
        self.live_connect_reconnect_enter_button = gtk.Button("再接続")
        self.live_connect_reconnect_enter_button.connect("clicked", self.reconnect_live)
        self.live_connect_reconnect_enter_button.set_sensitive(False)
        # ボックス、ボタンの追加
        live_connect_url_hbox.pack_start(self.live_connect_url_entry, True, True)
        live_connect_url_hbox.pack_start(self.live_connect_enter_button, False, False)
        live_connect_url_hbox.pack_start(self.live_connect_disconnect_enter_button, False, False)
        live_connect_url_hbox.pack_start(self.live_connect_reconnect_enter_button, False, False)

        # コメント
        comment_enter_hbox = gtk.HBox()
        # コメント184チェック
        self.comment_enter_184_checkbutton = gtk.CheckButton("184")
        self.comment_enter_184_checkbutton.set_active(self.db['setting']["comment_is_184"])
        # コメント入力ボックス
        self.comment_enter_entry = gtk.Entry()
        self.comment_enter_entry.connect("key-press-event", self.comment_entry_key_press_enter)
        # コメント投稿ボタン
        self.comment_enter_button = gtk.Button("投稿")
        self.comment_enter_button.connect("clicked", self.comment_post)
        self.comment_enter_button.set_sensitive(False)
        # コメント追加
        comment_enter_hbox.add(self.comment_enter_184_checkbutton)
        comment_enter_hbox.add(self.comment_enter_entry)
        comment_enter_hbox.add(self.comment_enter_button)

        # 接続、スクロール、コメント追加
        tab_live1_vbox.pack_start(live_connect_url_hbox, False, False)
        tab_live1_vbox.pack_start(self.comment_tree_scroll)
        tab_live1_vbox.pack_start(comment_enter_hbox, False, False)

        # ウインドウにタブを追加
        self.main_window.add(self.main_notebook)
        self.main_window.set_default_size(600, 420)

        # ツリー内でのコンテキストメニュー
        self.comment_tree_context_menu = gtk.Menu()
        comment_tree_context_menu_item_nickname = gtk.MenuItem("ニックネーム設定")
        comment_tree_context_menu_item_nickname.connect("activate", self.dialog_open_nickname_setting)
        comment_tree_context_menu_item_linkopen = gtk.MenuItem("リンクを開く")
        comment_tree_context_menu_item_linkopen.connect("activate", self.browser_open_comment_uri)
        comment_tree_context_menu_item_useropen = gtk.MenuItem("ユーザーページを開く")
        comment_tree_context_menu_item_useropen.connect("activate", self.browser_open_user_page)
        comment_tree_context_menu_item_commentcopy = gtk.MenuItem("コメントをコピー")
        comment_tree_context_menu_item_commentcopy.connect("activate", self.CommentCopy)
        comment_tree_context_menu_item_userng = gtk.MenuItem("NGに設定")
        comment_tree_context_menu_item_userng.connect("activate", self.append_ng_user)
        self.comment_tree_context_menu.append(comment_tree_context_menu_item_nickname)
        self.comment_tree_context_menu.append(comment_tree_context_menu_item_linkopen)
        self.comment_tree_context_menu.append(comment_tree_context_menu_item_useropen)
        self.comment_tree_context_menu.append(comment_tree_context_menu_item_commentcopy)
        self.comment_tree_context_menu.append(comment_tree_context_menu_item_userng)
        self.comment_tree_context_menu.show_all()

        # 設定タブ
        tab_setting_vbox = gtk.VBox()
        tab_setting_label = gtk.Label("設定")
        self.main_notebook.append_page(tab_setting_vbox, tab_setting_label)

        # 設定タブ
        setting_vbox = gtk.VBox()
        tab_setting_vbox.pack_start(setting_vbox, False, False)
        # ニックネームの自動上書きを許可する
        self.setting_nickname_overwrite_checkbox = gtk.CheckButton("ニックネームの自動上書きを許可する")
        setting_vbox.pack_start(self.setting_nickname_overwrite_checkbox, False, False)
        # ニックネームが数値の場合上書きしない
        self.setting_nickname_num_overwrite_checkbox = gtk.CheckButton("ニックネームが数値の場合上書きしない")
        setting_vbox.pack_start(self.setting_nickname_num_overwrite_checkbox, False, False)
        # 放送主の背景色を変更する
        setting_ownerbgcolor_hbox = gtk.HBox()
        self.setting_ownerbgcolor_change_checkbox = gtk.CheckButton("放送主のコメントカラーを変更する")
        self.setting_ownerbgcolor_change_color_entry = gtk.Entry()
        setting_ownerbgcolor_hbox.pack_start(self.setting_ownerbgcolor_change_checkbox, False, False)
        setting_ownerbgcolor_hbox.pack_start(self.setting_ownerbgcolor_change_color_entry, False, False)
        setting_vbox.pack_start(setting_ownerbgcolor_hbox, False, False)
        # リンクを開くブラウザ名
        setting_openlinkbrowser_hbox = gtk.HBox()
        setting_openlinkbrowser_label = gtk.Label("リンクを開くブラウザ")
        setting_openlinkbrowser_hbox.pack_start(setting_openlinkbrowser_label, False, False)
        self.setting_openlinkbrowser_entry = gtk.Entry()
        setting_openlinkbrowser_hbox.pack_start(self.setting_openlinkbrowser_entry, False, False)
        setting_vbox.pack_start(setting_openlinkbrowser_hbox, False, False)
        # 184デフォルト値
        self.setting_comment_enter_default_184_checkbox = gtk.CheckButton("標準で184コメントにする")
        setting_vbox.pack_start(self.setting_comment_enter_default_184_checkbox, False, False)
        # 管理費表示デフォルト値
        self.setting_hide_control_comment_checkbox = gtk.CheckButton("管理コメントを非表示にする")
        setting_vbox.pack_start(self.setting_hide_control_comment_checkbox, False, False)
        # 管理費表示デフォルト値
        self.setting_comment_logging_checkbox = gtk.CheckButton("コメントをログに残す")
        setting_vbox.pack_start(self.setting_comment_logging_checkbox, False, False)
        # コメント投稿のモディファイア
        setting_comment_enter_modifier_label = gtk.Label("コメント投稿モディファイア")
        setting_vbox.pack_start(setting_comment_enter_modifier_label, False, False)
        self.setting_comment_enter_modifier_conbobox = gtk.combo_box_new_text()
        self.setting_comment_enter_modifier_conbobox.append_text("Enterのみ")
        self.setting_comment_enter_modifier_conbobox.append_text("Alt")
        self.setting_comment_enter_modifier_conbobox.append_text("Ctrl")
        setting_vbox.pack_start(self.setting_comment_enter_modifier_conbobox, False, False)
        # クッキーを取得するブラウザ
        setting_cokkiebrowser_label = gtk.Label("クッキーを取得するブラウザ")
        setting_vbox.pack_start(setting_cokkiebrowser_label, False, False)
        self.setting_cookiebrouser_conbobox = gtk.combo_box_new_text()
        self.setting_cookiebrouser_conbobox.append_text("Chromium")
        self.setting_cookiebrouser_conbobox.append_text("GoogleChrome")
        self.setting_cookiebrouser_conbobox.append_text("Firefox")
        self.setting_cookiebrouser_conbobox.append_text("独自ログイン")
        setting_vbox.pack_start(self.setting_cookiebrouser_conbobox, False, False)
        # 設定保存ボタン
        setting_save_button = gtk.Button("設定保存")
        setting_save_button.connect("clicked", self.setting_save)
        setting_vbox.pack_start(setting_save_button, False, False)

        # NGユーザタブ
        tab_ng_user_vbox = gtk.VBox()
        tab_ng_user_label = gtk.Label("NG")
        self.main_notebook.append_page(tab_ng_user_vbox, tab_ng_user_label)
        # NGユーザツリー
        self.ng_user_tree = gtk.TreeView(model=gtk.ListStore(str, str))
        self.ng_user_tree.props.rules_hint = True
        # コメント表示ツリーカラムナンバー
        ng_user_tree_column_number = gtk.TreeViewColumn("", gtk.CellRendererText(), text=0)
        ng_user_tree_column_number.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        ng_user_tree_column_number.set_fixed_width(50)
        # コメント表示ツリーカラムナンバー
        ng_user_tree_column_username = gtk.TreeViewColumn("NG User", gtk.CellRendererText(), text=1)
        ng_user_tree_column_username.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        # ツリーにカラムを追加
        self.ng_user_tree.append_column(ng_user_tree_column_number)
        self.ng_user_tree.append_column(ng_user_tree_column_username)
        # コメント表示ツリースクロール
        self.ng_user_tree_scroll = gtk.ScrolledWindow()
        self.ng_user_tree_scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.ng_user_tree_scroll.add(self.ng_user_tree)
        # コントロールボックス
        ng_user_control_hbox = gtk.HBox()
        self.ng_user_control_nickname = gtk.Button('ニックネーム')
        self.ng_user_control_nickname.connect('clicked', self.ng_user_set_nickname)
        self.ng_user_control_remove_all = gtk.Button('全解除')
        self.ng_user_control_remove_all.connect("clicked", self.ng_user_remove_all)
        self.ng_user_control_remove_select = gtk.Button('解除')
        self.ng_user_control_remove_select.connect("clicked", self.ng_user_remove_select)
        ng_user_control_hbox.pack_start(self.ng_user_control_nickname)
        ng_user_control_hbox.pack_start(self.ng_user_control_remove_all)
        ng_user_control_hbox.pack_start(self.ng_user_control_remove_select)
        # tab
        tab_ng_user_vbox.pack_start(self.ng_user_tree_scroll, True, True)
        tab_ng_user_vbox.pack_start(ng_user_control_hbox, False, False)
        self.ng_user_tree_refresh()

        # クリップボード
        self.clipboard = gtk.Clipboard()

        # ウインドウを表示
        self.main_window.show_all()

    def ng_user_set_nickname(self, widget=None):
        selection = self.ng_user_tree.get_selection()
        (model, iter) = selection.get_selected()
        line_num = int(model.get_value(iter, 0))

        user_id = self.db['ng_users'][line_num-1]
        nickname = self.db['nickname'][user_id] if user_id in self.db['nickname'] else ''

        dlg = NicknameSettingDialog(title="ニックネーム設定", user_id=user_id, nick=nickname, flags=gtk.DIALOG_DESTROY_WITH_PARENT, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        resid = dlg.run()
        if resid == gtk.RESPONSE_OK:
            nickname = dlg.get_nickname()
            self.save_nickname(user_id, nickname)
        dlg.destroy()

        self.ng_user_tree_refresh()

    def ng_user_tree_refresh(self):
        self.ng_user_tree.get_model().clear()
        for line_num, user_id in enumerate(self.db['ng_users']):
            line_num += 1
            nickname = self.db['nickname'][user_id] if user_id in self.db['nickname'] else user_id
            self.ng_user_tree.get_model().append((str(line_num), nickname),)

    def ng_user_remove_all(self, widget=None):
        self.db['ng_users'] = []
        self.db.sync()

        self.ng_user_tree_refresh()

    def ng_user_remove_select(self, widget=None):
        selection = self.ng_user_tree.get_selection()
        (model, iter) = selection.get_selected()
        line_num = int(model.get_value(iter, 0))

        self.db['ng_users'].pop(line_num-1)
        self.db.sync()

        self.ng_user_tree_refresh()

    def live_enter(self, widget=None):
        # 接続中なら放送を切断
        if not self.live_connect_enter_button.get_sensitive():
            self.disconnect_live()

        self.connect_live()

    def drags_live_id(self, widget, context, x, y, selection, info, time):
        # ドラッグされたデータを入力する
        uri = selection.data
        self.live_connect_url_entry.set_text(uri.rstrip())

    def comment_entry_key_press_enter(self, widget=None, event=None):
        keyname = gtk.gdk.keyval_name(event.keyval)

        modifier_keys = [0, 0x18, 0x14]

        # エンターが入力されたら
        if "Return" == keyname:
            # モディファイアキー設定がなしならば
            if self.db['setting']["comment_enter_modifier"] == 0:
                self.comment_post(widget)
            # モディファイアキーの入力なら
            elif event.state == modifier_keys[self.db['setting']["comment_enter_modifier"]]:
                self.comment_post(widget)

    def comment_tree_left_click(self, widget=None, event=None):
        # 右クリックの判定
        if event.button == 3:
            # コンテキストメニューの表示
            self.comment_tree_context_menu.popup(None, None, None, event.button, event.time)

    def comment_tree_column_resize(self, source, condition):
        # 保存カラム幅と実カラム幅が違えば
        if self.comment_tree_column_comment_width != self.comment_tree_column_comment.get_width():
            # 実カラム幅を保存カラム幅に
            self.comment_tree_column_comment_width = self.comment_tree_column_comment.get_width()
            # テキストの折り返しを調整
            self.comment_tree_column_comment_render_text.set_property("wrap-width", self.comment_tree_column_comment_width - 10)

    def CheckScroll(self):
        # 現在のスクロール位置
        adjustment = self.comment_tree_scroll.get_vadjustment()

        # スクロール位置を
        adjustment.value = adjustment.upper - adjustment.page_size

    def Time2LiveFTime(self, base, now):
        # 経過秒を計算
        tm = now - base

        # フォーマットして返す(時間、分ともに0埋め2桁
        return time.strftime("%H:%M:%S", time.gmtime(tm))[1:]

    def CommentCopy(self, widget=None):
        # コメントを取得
        comment = self.get_tree_column(2)

        # コメントをクリップボードにコピー
        self.clipboard.set_text(comment)

    def append_ng_user(self, widget=None):
        selection = self.comment_tree.get_selection()
        (model, iter) = selection.get_selected()
        line_num = model.get_value(iter, 0)

        for line in self.live.comments:
            if line[0] == line_num:
                user_id = line[1]
                break

        self.db['ng_users'].append(user_id)

        self.ng_user_tree_refresh()

    def setting_load(self):
        # 設定の適応
        self.setting_cookiebrouser_conbobox.set_active(self.db['setting']["cookie_browser"])
        self.setting_comment_enter_modifier_conbobox.set_active(self.db['setting']["comment_enter_modifier"])
        self.setting_comment_enter_default_184_checkbox.set_active(self.db['setting']["comment_is_184"])
        self.setting_hide_control_comment_checkbox.set_active(self.db['setting']['hide_control_comment'])
        self.setting_comment_logging_checkbox.set_active(self.db['setting']['comment_logging_is'])
        self.setting_nickname_overwrite_checkbox.set_active(self.db['setting']["nickname_overwrite_is"])
        self.setting_nickname_num_overwrite_checkbox.set_active(self.db['setting']["nickname_overwrite_num_is"])
        self.setting_ownerbgcolor_change_checkbox.set_active(self.db['setting']["bg_owner_color_change_is"])
        self.setting_ownerbgcolor_change_color_entry.set_text(self.db['setting']["bg_owner_color"])
        self.setting_openlinkbrowser_entry.set_text(self.db['setting']["open_browser"])

    def setting_save(self, widget=None):
        # クッキーブラウザ
        active = self.setting_cookiebrouser_conbobox.get_active()
        self.db['setting']["cookie_browser"] = active

        # 投稿モディファイア
        active = self.setting_comment_enter_modifier_conbobox.get_active()
        self.db['setting']["comment_enter_modifier"] = active

        # 184
        if self.setting_comment_enter_default_184_checkbox.get_active():
            self.db['setting']["comment_is_184"] = True
        else:
            self.db['setting']["comment_is_184"] = False

        # hide
        if self.setting_hide_control_comment_checkbox.get_active():
            self.db['setting']["hide_control_comment"] = True
        else:
            self.db['setting']["hide_control_comment"] = False

        # logging
        if self.setting_comment_logging_checkbox.get_active():
            self.db['setting']["comment_logging_is"] = True
        else:
            self.db['setting']["comment_logging_is"] = False

        # ニックネーム上書き
        if self.setting_nickname_overwrite_checkbox.get_active():
            self.db['setting']["nickname_overwrite_is"] = True
        else:
            self.db['setting']["nickname_overwrite_is"] = False

        # 数値ニックネーム上書き
        if self.setting_nickname_num_overwrite_checkbox.get_active():
            self.db['setting']["nickname_overwrite_num_is"] = True
        else:
            self.db['setting']["nickname_overwrite_num_is"] = False

        # 放送主コメントの背景色変更
        if self.setting_ownerbgcolor_change_checkbox.get_active():
            self.db['setting']["bg_owner_color_change_is"] = True
        else:
            self.db['setting']["bg_owner_color_change_is"] = False

        # 放送主コメント背景色
        self.db['setting']["bg_owner_color"] = self.setting_ownerbgcolor_change_color_entry.get_text()

        # URIオープンブラウザ
        self.db['setting']["open_browser"] = self.setting_openlinkbrowser_entry.get_text()

        self.db.sync()

    def browser_open_user_page(self, widget=None):
        # noを取得
        no = self.get_tree_column(0)

        # 投稿者IDの抜き出し
        for line in self.live.comments:
            if line[0] == no:
                id = line[1]
                break

        # 生IDかチェック
        if id.isdigit():
            # ページを開く
            os.popen("%s '%s%s' &" % (self.db['setting']["open_browser"], "http://www.nicovideo.jp/user/", id))

    def get_tree_column(self, retno):
        # セレクトされている行を取得
        selection = self.comment_tree.get_selection()
        # 行からモデルとイテレータを取得
        (model, iter) = selection.get_selected()
        # モデルとイテレータから行のIDを取得 ( 0: No行
        return model.get_value(iter, retno)

    def browser_open_comment_uri(self, widget=None):
        # コメントを取得
        comment = self.get_tree_column(2)

        # URIを抽出
        uriPattern = re.compile(r'(http://[\w\d/\-_.%?=&]+)')
        match = uriPattern.findall(comment)

        # URIがあれば開く
        if len(match) != 0:
            os.popen("%s '%s' &" % (self.db['setting']["open_browser"], match[0]))

    def dialog_open_nickname_setting(self, widget=None):
        # セレクトされている行を取得
        selection = self.comment_tree.get_selection()
        # 行からモデルとイテレータを取得
        (model, iter) = selection.get_selected()
        # モデルとイテレータから行のIDを取得 ( 0: No行
        no = model.get_value(iter, 0)

        # 投稿者IDの抜き出し
        for line in self.live.comments:
            if line[0] == no:
                id = line[1]
                break

        # ニックネームを取得
        nick = self.pick_nickname(id)
        if nick == id:
            nick = ""

        # ニックネームダイアログ
        dlg = NicknameSettingDialog(title="ニックネーム設定", user_id=id, nick=nick, flags=gtk.DIALOG_DESTROY_WITH_PARENT, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        # ダイアログの表示 終了コードを保存
        resid = dlg.run()
        # 終了コードがOKコードなら
        if resid == gtk.RESPONSE_OK:
            # 入力ニックネームを取得し、設定する
            nick = dlg.get_nickname()
            self.save_nickname(id, nick)
        # ダイアログを終了する
        dlg.destroy()

        # ポインタを初期化
        self.current_list_number = 0

        # 行番号を初期化
        self.tree_iterator = 1

        # 前コメント番号を初期化
        self.before_number = None

        # TreeViewを消去
        self.comment_tree.get_model().clear()

        # オリジナル設定を保存
        nickOwOrg = self.db['setting']["nickname_overwrite_is"]
        self.db['setting']["nickname_overwrite_is"] = False

        # TreeViewの更新
        self.comment_tree_append_comment()

        # オリジナル設定に戻す
        self.db['setting']["nickname_overwrite_is"] = nickOwOrg

    def save_nickname(self, user_id, nickname):
        # ニックネームを辞書に設定
        self.db['nickname'][user_id] = nickname
        self.db.sync()

    def parse_live_id(self, raw_string):
        # DEBUG 正しい放送IDを抜き出す
        re_live_id = re.compile(r"(co\d{4,}|lv\d{4,})")
        match = re_live_id.findall(raw_string)

        # matchが空ならマッチしなかった
        if len(match) == 0:
            return None
        else:
            return match[0]

    def connect_live(self, widget=None):
        # ポインタを初期化
        self.current_list_number = 0
        # 行番号を初期化
        self.tree_iterator = 1
        # 前コメント番号を初期化
        self.before_number = None
        # TreeViewを消去
        self.comment_tree.get_model().clear()

        # クッキーよりセッションIDの取得
        browser_names = ["ch", "gc", "fx", "nr"]
        nico_session = GetBrowserSessionId(browser_names[self.db['setting']["cookie_browser"]])
        session_id = nico_session.session_id

        # 入力より放送IDを抜き出す
        self.live_id = self.parse_live_id(self.live_connect_url_entry.get_text())
        if self.live_id == None:
            print "放送IDが不正です。"
            return

        # 放送へ接続
        self.live = Live("http://watch.live.nicovideo.jp/api/getplayerstatus?v=%s" % (self.live_id), session_id)
        self.tab_live_label.set_markup(self.live.live_page_title)

        # 放送に接続できない
        if not self.live.connecting:
            print "放送に接続できません"
            return

        # ソケットウォッチの追加
        self.watch = gobject.io_add_watch(self.live.socket, gobject.IO_IN, self.get_comment)

        # チケット/過去のコメントの取得
        self.live.set_ticket()

        # ボタンの制御
        self.live_connect_enter_button.set_sensitive(False)
        self.live_connect_disconnect_enter_button.set_sensitive(True)
        self.live_connect_reconnect_enter_button.set_sensitive(True)
        self.comment_enter_button.set_sensitive(True)

    def disconnect_live(self, widget=None):
        # ソケットウォッチの削除
        gobject.source_remove(self.watch)

        # ソケットの切断
        self.live.socket_disconnect()

        if self.db['setting']['comment_logging_is']:
            if self.live_id not in self.db['log']:
                self.db['log'][self.live_id] = []
            self.db['log'][self.live_id] += self.live.comments
            self.db.sync()

        # 放送の削除
        del self.live

        # ボタンの制御
        self.live_connect_enter_button.set_sensitive(True)
        self.live_connect_disconnect_enter_button.set_sensitive(False)
        self.live_connect_reconnect_enter_button.set_sensitive(False)
        self.comment_enter_button.set_sensitive(False)

    def reconnect_live(self, widget=None):
        # 切断
        self.disconnect_live(widget)

        # 接続
        self.connect_live(widget)

    def comment_post(self, widget=None):
        # コメント入力ボックスよりコメントを取得
        self.live.comment = self.comment_enter_entry.get_text()

        # 入力が空ならコメントを送信しない
        if self.live.comment == "":
            return

        # コメント入力ボックスを空に
        self.comment_enter_entry.set_text("")

        # 匿名コメントチェック確認
        if self.comment_enter_184_checkbutton.get_active():
            self.live.anonymity = "mail='184'"
        else:
            self.live.anonymity = ""

        # NGワードチェック
        for word in ng_comments.keys():
            if self.live.comment.find(word) != -1:
                self.live.comment = self.live.comment.replace(word, ng_comments[word])

        # コメントを投稿
        self.live.post_comment()

    def get_comment(self, source, condition):
        # コメントをソケットから読み込み
        self.live.get_comment()

        # ツリーに追加
        self.comment_tree_append_comment()

        # io_add_watchに渡す
        return True

    def comment_tree_append_comment(self):
        # ツリーに追加
        while self.current_list_number < len(self.live.comments):
            # 名前を設定
            user_id = self.live.comments[self.current_list_number][1]
            name = self.pick_nickname(user_id)

            # 時間を設定
            if self.live.comments[self.current_list_number][4].isdigit():
                time = self.Time2LiveFTime(int(self.live.comment_basetime), int(self.live.comments[self.current_list_number][4]))
            else:
                time = ""

            # コメントからニックネームを設定
            self.comment2nick(self.live.comments[self.current_list_number][1], self.live.comments[self.current_list_number][2])

            # Statusを取得
            status = self.live.comments[self.current_list_number][3]

            # コメント番号
            no = self.live.comments[self.current_list_number][0]

            # アイコンの設定
            if status == "0":
                status_icon = gtk.gdk.pixbuf_new_from_file(ICON_DIR + "/Normal.png")
            elif status == "1":
                status_icon = gtk.gdk.pixbuf_new_from_file(ICON_DIR + "/Premium.png")
            elif status == "3":
                status_icon = gtk.gdk.pixbuf_new_from_file(ICON_DIR + "/Owner.png")
            else:
                status_icon = gtk.gdk.pixbuf_new_from_file(ICON_DIR + "/Ng.png")

            # NGコメント
            if self.before_number != None and no != "0":
                sa = int(no) - int(self.before_number)
                if sa != 1:
                    for i in range(1, sa):
                        # NGコメント背景
                        color = self.db['setting']['bg_ng_color']
                        # NGコメントアイコン
                        ng_icon = gtk.gdk.pixbuf_new_from_file(ICON_DIR + "/Ng.png")
                        # NGコメントをTreeViewに追加
                        self.comment_tree.get_model().append((str(int(no) - sa + i), "", "NGコメント", ng_icon, "", color), )
                        self.tree_iterator += 1

            # コメントNoを保存
            self.before_number = no

            # コメント
            comment = self.live.comments[self.current_list_number][2]
            comment = str2html_unescape(comment)

            # 背景色の取得
            color = self.iter2bgcolor(self.tree_iterator, status)

            # ツリーに行を追加
            if self.db['setting']['hide_control_comment'] is True and comment.startswith('/hb'):
                pass
            elif user_id in self.db['ng_users']:
                pass
            else:
                self.comment_tree.get_model().append((no, name, comment, status_icon, time, color), )

            # 行番号を次へ
            self.tree_iterator += 1

            # リストポインタを移動
            self.current_list_number += 1

        # スクロールの調整
        adjustment = self.comment_tree_scroll.get_vadjustment()

        # スクロールさせるかいなか
        if adjustment.value == adjustment.upper - adjustment.page_size:
            gobject.idle_add(self.CheckScroll)

    def comment2nick(self, id, comment):
        # ニックネームの上書きを許可するか
        nickOw = self.db['setting']["nickname_overwrite_is"]
        # ニックネームが数値のみでも登録するか
        nickNumOw = self.db['setting']["nickname_overwrite_is"]

        # コメントに@が含まれていれば
        if comment.find("@") != -1 or comment.find("＠") != -1:
            # @で分割
            nick = re.split(r"@|＠", comment)
            # 分割した文字列の最後をさらにスペースで分割して最初をニックネームに設定
            nick = nick[-1].split(" ")[0]
            # ニックネームが数値だけで、数値の登録を拒否していれば
            if nick.isdigit() and nickNumOw:
                return False
            else:
                # IDが存在し、ニックネームの上書きが許可されていればニックネームの設定
                if self.db['nickname'].has_key(id) and nickOw:
                    self.save_nickname(id, nick)
                # IDが存在しなければニックネームの設定
                elif not self.db['nickname'].has_key(id):
                    self.save_nickname(id, nick)
                return True

    def pick_nickname(self, user_id):
        # ニックネーム辞書よりIDを検索する
        if user_id in self.db['nickname']:
            return self.db['nickname'][user_id]
        else:
            return user_id

    def iter2bgcolor(self, iter, status=0):
        # 放送主コメントなら設定カラーを返す
        if status == "3" and self.db['setting']["bg_owner_color"]:
            return self.db['setting']["bg_owner_color"]

        # 行番号に応じたカラーを返す
        if self.tree_iterator % 2:
            return "#FFFFFF"
        else:
            return "#EEEEEE"

    def close_window(self, widget=None, event=None):
        self.db.sync()

        # GUI終了
        gtk.main_quit()


if __name__ == '__main__':
    DBInitialize()
    WinCom()
    gtk.main()
