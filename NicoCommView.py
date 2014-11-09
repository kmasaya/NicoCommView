#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import time
import pickle
import socket
import re
import urllib
import urllib2
import netrc
from xml.dom import minidom
import gobject
import cookielib
from modules.Setting import Setting
from modules.NicoSessionId import NicoSessionId
from modules.NgCommentDict import NgCommentDict
import pygtk
import gtk


class Live:
    """
    ニコ生関連クラス    
    """

    # 接続用
    opener        = None  # Opner
    sock          = None  # ソケット
    # ニコ生用
    addr          = None  # コメントサーバのURI
    port          = None  # コメントサーバポート番号
    thread        = None  # コメントのスレッドID
    user_id       = None  # ユーザID
    user_premium  = None  # ユーザがプレミアか (0:一般 1:プレミア 3:放送主
    base_time     = None  # コメント基礎時間
    comment_count = None  # 現在のコメント数
    ticket        = None  # チケット番号
    postkey       = None  # コメントのポストキー
    vpos          = None  # Vpos
    # ユーザ設定
    anonymity     = None  # 匿名 # 184(匿名(コメント時184でコメント))
    comList       = None  # コメントリスト
    connect       = None  # 放送接続フラグ

    def __init__( self, liveUri, sessionId):
        """
        コンストラクタ

        引数:
        liveid    - 放送のID (lv*
        sessionId - クッキーに保存されているセッションID
        返し値:
        
        """
        # 初期値の設定
        self.comList = [] 
        cj           = self.MakeCookie( sessionId)
        self.opener  = self.MakeOpener( cj)

        # セッションIDが空ならnetrcから接続情報を読み込みログインを行う
        if sessionId == "":
            #DEBUG TODO netrc読み込み時の例外
            #DEBUG TODO ログイン時の例外
            info = netrc.netrc().authenticators('nicovideo')
            mail = info[0]
            password = info[2]
            self.MakeSession( mail, password)

        # プレーヤステータスを取得
        data = self.ReadUri( liveUri)
        
        # 放送が存在していれば接続
        if self.CheckLiveId( data):
            self.PlayerStatus2Status( data)
            self.SocketConnect()
            self.MakeVpos()
            # 放送接続フラグを立てる
            self.connect = True
        # 存在していなければ
        else:
            # 放送未接続フラグを立てる
            self.connect = False
            
    def __del__( self):
        """
        デストラクタ
        
        引数:
        
        返し値:
        
        """
        pass
    
    def MakeCookie( self, sessionId = ""):
        """
        クッキーの設定

        引数:
        sessionId - セッションID
        返し値:
         - cj
        """
        # クッキーの作成と設定
        cj = cookielib.CookieJar()
        
        # セッションIDが渡されていればセット
        if not sessionId == "":
            ck = cookielib.Cookie(
                version            = 0,
                name               = 'user_session',
                value              = sessionId,
                port               = None,
                port_specified     = False,
                domain             = '.nicovideo.jp',
                domain_specified   = False,
                domain_initial_dot = False,
                path               = '/',
                path_specified     = True,
                secure             = False,
                expires            = None,
                discard            = True,
                comment            = None,
                comment_url        = None,
                rest               = {'HttpOnly': None},
                rfc2109            = False
                )
            cj.set_cookie( ck)    

        return cj

    def MakeOpener( self, cj, ua = "NicoCommView"):
        """
        オープナの作成

        引数:
        cj - CookieJar
        ua - UsearAgent (NicoCommView
        戻し値:
         - opener
        """

        # オープなの設定
        opener = urllib2.build_opener( urllib2.HTTPCookieProcessor( cj))
        opener.addheaders = [( "User-agent", ua)]
        
        return opener
    
    def MakeSession( self, mail, password):
        """
        ニコニコ動画にログインを行う
        
        引数:
        mail     - ユーザ名
        password - パスワード
        返し値:
         - opener 
        """
        
        # ログイン
        req = urllib2.Request( 'https://secure.nicovideo.jp/secure/login?site=niconico');
        account = { "mail": mail, "password": password}
        req.add_data( urllib.urlencode( account.items()))
        self.opener.open( req)
    
    def ReadUri( self, uri):
        """
        URIの内容を読み込みソースを返す

        引数:
        uri - 読み込みを行うURI
        戻し値:
         - URIのソースを返す 
        """

        # URIのオープン
        return self.opener.open( uri).read()

    def CheckLiveId( self, data):
        """
        存在する放送か確認
        
        引数:
        data - 放送XML
        返し値:
        True  - 存在する
        False - 存在しない
        """
        # XMLから値の抜き出し
        xml = minidom.parseString( data)
        child = xml.getElementsByTagName( 'getplayerstatus')[0]
        # ステータスを取得する
        status = child.getAttribute( "status")
        
        # ステータスがOKなら放送が存在する
        if status == "ok":
            return True
        else:
            return False

    def SocketConnect( self):
        """
        ソケットに接続をする

        引数:
        
        返し値:
        
        """
        # ソケットに接続
        liveSocket = socket.socket( socket.AF_INET, socket.SOCK_STREAM)
        liveSocket.connect( ( self.addr, int( self.port)))
        
        self.sock = liveSocket
        
    def SocketDisconnect( self):
        """
        ソケットの切断する
        
        引数:
        
        返し値:
        
        """

        # ソケットの切断
        self.sock.close()

    def PlayerStatus2Status( self, data):
        """
        XMLより放送ステータスの抽出をする

        引数:
        data - ニコ生のプレーヤステータスXML
        返し値:
        
        """
        # XMLから値の抜き出し
        xml = minidom.parseString( data)
        child = xml.getElementsByTagName( 'getplayerstatus')[0]
        if child.getElementsByTagName( 'ms'):
            mstag = child.getElementsByTagName( 'ms')[0]
            # コメントサーバURI
            self.addr = mstag.getElementsByTagName( 'addr')[0].firstChild.data.strip()
            # コメントサーバポート番号
            self.port = mstag.getElementsByTagName( 'port')[0].firstChild.data.strip()
            # コメントのスレッドID
            self.thread = mstag.getElementsByTagName( 'thread')[0].firstChild.data.strip()
        if child.getElementsByTagName('user'):
            usertag = child.getElementsByTagName( 'user')[0]
            # ユーザID
            self.user_id = usertag.getElementsByTagName( 'user_id')[0].firstChild.data.strip()
            # ユーザがプレミアかどうか(0:一般 1:プレミアム
            self.user_premium = usertag.getElementsByTagName( 'is_premium')[0].firstChild.data.strip()
        if child.getElementsByTagName( 'stream'):
            streamtag = child.getElementsByTagName( 'stream')[0]
            # コメントの基礎時間
            self.base_time = streamtag.getElementsByTagName( 'base_time')[0].firstChild.data.strip()
            # 現在のコメント数
            self.comment_count = streamtag.getElementsByTagName( 'comment_count')[0].firstChild.data.strip()
        
    def GetTicket( self):
        """
        チケットのリクエストと過去のコメント1000件(最大値)のリクエストを行う

        引数:
        
        返し値:
        """
        # チケット取得のXML作成
        sendXml = '<thread thread="%s" version="20061206" res_from="-1000" />\0' % ( self.thread)
        
        # XMLをソケットに送信
        self.sock.send( sendXml)
        
    def GetPostkey( self):
        """
        コメント投稿用の鍵を取得(コメント100件毎に必要

        引数:
        
        返し値:
        
        """
        # Postkey取得用のURLを生成
        uri = "http://live.nicovideo.jp/api/getpostkey?thread=%s&block_no=%d" % ( self.thread, int( int( self.comment_count) / 100))

        # Postkey取得用のURLからPostkey文字列を取得
        data = self.opener.open( uri)
        key  = data.read()

        # Postkey文字列からPostkeyの部分だけセット
        self.postkey = key.replace( "postkey=", "")

    def GetComment( self):
        """
        コメントを取得しユーザ情報を返す

        引数:

        戻し値:

        """

        # ソケットデータを受信する(終端がコメントの終(</chat>)になるまで
        socketData = ""
        pattern = re.compile( r'<thread[^>]+>$')
        while True:
            socketData += self.sock.recv( 4096).replace( "\0", "")
            if socketData[-7:] == "</chat>" or len( pattern.findall( socketData)) != 0:
                break
        
        # コメントを送信した時の結果を破棄
        socketData = re.sub(r'<chat_result[^>]+>', '', socketData)
        # 改行を破棄
        socketData = socketData.replace( "\r", "").replace( "\n", "") 
        
        # チケットを設定
        ticket = re.sub(r'<thread[^>]*ticket="([0-9A-Za-z-_]{1,})".*', r'\1', socketData)
        # チケットを受信すれば(15文字以上なら未受信
        if len( ticket) < 15:
            self.ticket = ticket
            # チケット文字列を破棄
            socketData = re.sub(r'<thread[^>]+>', '', socketData)

        # コメントから情報を抜き出す
        for line in socketData.split( r"</chat>"):
            # 行が5文字以下なら次へ(<chat>で５文字を超える
            if len( line) < 5:
                continue
            # スプリットした文字列を復帰
            line = line + "</chat>"

            # コメント
            comment = re.sub(r'</?chat[^>]*>', '', line)
            # コメントナンバー
            comNumber = re.sub(r'<chat[^>]*no="([0-9]{1,})".*', r'\1', line)
            # コメントナンバーがなければ0に
            if comNumber == line:
                comNumber = "0"
            # コメントユーザ
            comUser = re.sub(r'<chat[^>]*user_id="([0-9a-zA-Z-_]{1,})".*', r'\1', line)
            # コメントユーザがいなければ運営に
            if comUser == line:
                comUser = "394"
            # コメント時間
            comTime = re.sub(r'<chat[^>]*date="([0-9]{1,})".*', r'\1', line)
            # コメントユーザがプレミアか
            comPremium = re.sub(r'<chat[^>]*premium="([0-9]{1})".*', r'\1', line)
            # プレミアムじゃなければ一般に
            if comPremium == line:
                comPremium = "0"
 
            self.comList.append( [ comNumber, comUser, comment, comPremium, comTime])
            self.comment_count = comNumber

    def MakeVpos( self):
        """
        vposの値を計算

        引数:

        返し値:

        """
        # VPOSを計算
        self.vpos = int( ( time.time() - float( self.base_time)) * 100)        
  
    def PostComment( self):
        """
        コメントの投稿

        引数:
        
        返し値:
        
        """
        # Postkeyの更新
        self.GetPostkey()
        
        # コメント投稿XMLを生成
        commentXml = u'<chat thread="%s" ticket="%s" vpos="%s" postkey="%s" %s user_id="%s" premium="%s">%s</chat>\0' % ( self.thread, self.ticket, self.vpos, self.postkey, self.anonymity, self.user_id, self.user_premium, self.Str2HtmlEscape( self.comment))

        # コメントXMLを送信
        self.sock.send( commentXml)

    def Str2HtmlEscape( self, str):
        """
        文字列をHTMLエスケープする
        
        引数:
        str - エスケープする文字列
        返し値:
         - エスケープした文字列
        """
        
        return str.replace( r"&", "&amp;").replace( r"<", "&lt;").replace( r">", "&gt;").replace( r"\"", "&quote;")


    
class WinCom:
    """
    GUI制御クラス
    """

    # メインウインドウ
    mainWindow = None
    # 放送インスタンス
    live       = None
    # 設定インスタンス
    setting    = None
    # コメントリストの最終ポインタ
    curListNum = None
    # コメントの前番号
    beforeNo   = None
    # Treeview行番号
    iter       = None
   
    def __init__(self, setting):
        """
        コンストラクタ
        
        引数:
        
        返し値:
        
        """
        # リストポインタを初期化
        self.curListNum = 0

        # 行番号の初期化
        self.iter = 1

        # 設定の初期化
        self.setting = setting

        # ウインドウの初期化
        self.WindowInitialize()                

        # 設定ウインドウに設定を適用
        self.LoadSetting()
        
        # 固定ハンドル辞書の読み込み
        self.LoadNickDictionaly()
    
    def __del__( self):
        """
        デストラクタ
        
        引数:
        self
        返し値:
        
        """
        pass
      
    def WindowInitialize( self):
        """
        ウインドウの初期化
        
        引数:
        
        返し値:
        
        """
        # メインウインドウ
        self.mainWindow = gtk.Window()
        self.mainWindow.set_title( "NicoCommView")
        self.mainWindow.connect( 'destroy_event', self.QuitWindow)
        self.mainWindow.connect( 'delete_event', self.QuitWindow)
        
        # タブ
        self.ntMain = gtk.Notebook()
        # タブ1
        tbLive1Vbox  = gtk.VBox( homogeneous = False)
        lbLive1Tab = gtk.Label( "Live1")
        self.ntMain.append_page( tbLive1Vbox, lbLive1Tab)
        
        # コメント表示ツリー
        self.trCom = gtk.TreeView( model = gtk.ListStore( str, str,str, gtk.gdk.Pixbuf, str, str))
        self.trCom.props.rules_hint = True
        self.trCom.connect( 'size-allocate', self.ColumnResize)
        self.trCom.connect( "button-press-event", self.TreePopup)
        # コメント表示ツリーカラムナンバー
        clNo = gtk.TreeViewColumn( "No", gtk.CellRendererText(), text = 0)
        clNo.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED) 
        clNo.set_fixed_width( 50)
        # コメント表示ツリーカラムユーザ
        self.clUserCrt = gtk.CellRendererText()
        clUser = gtk.TreeViewColumn( "User", self.clUserCrt, text = 1, background = 5)
        clUser.set_resizable( True) 
        clUser.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED) 
        clUser.set_fixed_width( 80)
        # コメント表示ツリーカラムコメント
        self.clComWidth = 380
        self.clComCrt = gtk.CellRendererText()
        self.clComCrt.set_property( "wrap-mode", True)
        self.clComCrt.set_property( "wrap-width", self.clComWidth - 10)
        self.clCom = gtk.TreeViewColumn( "Comment", self.clComCrt, text = 2)
        self.clCom.set_resizable( True) 
        self.clCom.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED) 
        self.clCom.set_fixed_width( self.clComWidth)
        # コメント表示ツリーステータス        
        clStat = gtk.TreeViewColumn( "S", gtk.CellRendererPixbuf(), pixbuf = 3)
        clStat.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED) 
        clStat.set_fixed_width( 24)
        # コメント表示ツリータイム
        clTime = gtk.TreeViewColumn( "Time", gtk.CellRendererText(), text = 4)
        clTime.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED)
        clTime.set_fixed_width( 50)
        # ツリーにカラムを追加
        self.trCom.append_column( clNo)
        self.trCom.append_column( clUser)
        self.trCom.append_column( self.clCom)
        self.trCom.append_column( clStat)
        self.trCom.append_column( clTime)
        # コメント表示ツリースクロール
        self.scrTree = gtk.ScrolledWindow()
        self.scrTree.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrTree.add( self.trCom)

        # 放送接続
        conHbox = gtk.HBox()
        # 放送ID入力ボックス
        self.enLive = gtk.Entry()
        self.enLive.connect( "activate", self.LiveEnter)
        self.enLive.connect( "drag_data_received", self.LiveIdDrags)
        # エントリへのドラッグ処理
        self.enLive.drag_dest_set( gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP, [ ( 'text/uri-list', 0, 0),], gtk.gdk.ACTION_COPY)
        # 放送接続ボタン
        self.btLiveCon = gtk.Button( "接続")
        self.btLiveCon.connect( "clicked", self.LiveConnect)
        # 放送切断ボタン
        self.btLiveDis = gtk.Button( "切断")
        self.btLiveDis.connect( "clicked", self.LiveDisconnect)
        self.btLiveDis.set_sensitive( False)
        # 放送再接続ボタン 
        self.btLiveRe = gtk.Button( "再接続")
        self.btLiveRe.connect( "clicked", self.LiveReconnect)
        self.btLiveRe.set_sensitive( False)
        # ボックス、ボタンの追加
        conHbox.pack_start( self.enLive,    True, True)
        conHbox.pack_start( self.btLiveCon, False, False)
        conHbox.pack_start( self.btLiveDis, False, False)
        conHbox.pack_start( self.btLiveRe,  False, False)

        # コメント
        comHbox = gtk.HBox()
        # コメント184チェック
        self.cbAnon = gtk.CheckButton( "184")
        self.cbAnon.set_active( self.setting.p[ "184"])
        # コメント入力ボックス
        self.enCom = gtk.Entry()
        self.enCom.connect( "key-press-event", self.EntryKeyPress)
        # コメント投稿ボタン
        self.btPost = gtk.Button( "投稿")
        self.btPost.connect( "clicked", self.PostComment)
        self.btPost.set_sensitive( False)
        # コメント追加
        comHbox.add( self.cbAnon)
        comHbox.add( self.enCom)
        comHbox.add( self.btPost)

        # 接続、スクロール、コメント追加
        tbLive1Vbox.pack_start( conHbox, False, False)
        tbLive1Vbox.pack_start( self.scrTree)
        tbLive1Vbox.pack_start( comHbox, False, False)

        # ウインドウにタブを追加
        self.mainWindow.add( self.ntMain)
        self.mainWindow.set_default_size( 600, 420)

        # ツリー内でのコンテキストメニュー
        self.mnTree = gtk.Menu()
        mnTreeItem1 = gtk.MenuItem( "ニックネーム設定")
        mnTreeItem1.connect( "activate", self.NickDialog)
        mnTreeItem2 = gtk.MenuItem( "リンクを開く")
        mnTreeItem2.connect( "activate", self.OpenUri)
        mnTreeItem3 = gtk.MenuItem( "ユーザーページを開く")
        mnTreeItem3.connect( "activate", self.OpenUserpage)
        mnTreeItem4 = gtk.MenuItem( "コメントをコピー")
        mnTreeItem4.connect( "activate", self.CommentCopy)
        self.mnTree.append( mnTreeItem1)
        self.mnTree.append( mnTreeItem2)
        self.mnTree.append( mnTreeItem3)
        self.mnTree.append( mnTreeItem4)
        self.mnTree.show_all()


        # タブ2
        tbSet2Vbox  = gtk.VBox()
        tbSet2Label = gtk.Label( "設定")
        self.ntMain.append_page( tbSet2Vbox, tbSet2Label)
        
        # 設定タブ
        setBox = gtk.VBox()
        tbSet2Vbox.pack_start( setBox, False, False)
        # ニックネームの自動上書きを許可する
        self.cbNameOw = gtk.CheckButton( "ニックネームの自動上書きを許可する")
        setBox.pack_start( self.cbNameOw, False, False)
        # ニックネームが数値の場合上書きしない
        self.cbNameOwNonNum = gtk.CheckButton( "ニックネームが数値の場合上書きしない")
        setBox.pack_start( self.cbNameOwNonNum, False, False)
        # 放送主の背景色を変更する
        comClHbox = gtk.HBox()
        self.cbOwComClCh = gtk.CheckButton( "放送主のコメントカラーを変更する")
        self.enOwComCl = gtk.Entry()
        comClHbox.pack_start( self.cbOwComClCh, False, False)
        comClHbox.pack_start( self.enOwComCl, False, False)
        setBox.pack_start( comClHbox, False, False)
        # リンクを開くブラウザ名
        browserHbox = gtk.HBox()
        lbBrowser = gtk.Label( "リンクを開くブラウザ")
        browserHbox.pack_start( lbBrowser, False, False)
        self.enBrowser = gtk.Entry()
        browserHbox.pack_start( self.enBrowser, False, False)
        setBox.pack_start( browserHbox, False, False)
        # 184デフォルト値
        self.cb184Def = gtk.CheckButton( "標準で184コメントにする")
        setBox.pack_start( self.cb184Def, False, False)
        # コメント投稿のモディファイア
        lbRetMod = gtk.Label( "コメント投稿モディファイア")
        setBox.pack_start( lbRetMod, False, False)
        self.lbRetMod = gtk.combo_box_new_text()
        self.lbRetMod.append_text( "Enterのみ")
        self.lbRetMod.append_text( "Alt")
        self.lbRetMod.append_text( "Ctrl")
        setBox.pack_start( self.lbRetMod, False, False)
        # クッキーを取得するブラウザ
        lbCookieBrowser = gtk.Label( "クッキーを取得するブラウザ")
        setBox.pack_start( lbCookieBrowser, False, False)
        self.lbCookieBrowser = gtk.combo_box_new_text()
        self.lbCookieBrowser.append_text("Chromium")
        self.lbCookieBrowser.append_text("GoogleChrome")        
        self.lbCookieBrowser.append_text("Firefox")
        self.lbCookieBrowser.append_text("独自ログイン")
        setBox.pack_start( self.lbCookieBrowser, False, False)
        # 設定保存ボタン
        btSave = gtk.Button( "設定保存")
        btSave.connect( "clicked", self.SaveSetting)
        setBox.pack_start( btSave, False, False)

        
        # クリップボード
        self.clipboard =  gtk.Clipboard()

        # ウインドウを表示
        self.mainWindow.show_all()

    def LiveEnter( self, widget = None):
        """
        放送ID入力欄でエンターが押されたときの動作
        
        引数:
        widget -
        返し値:
        
        """
        # 接続中なら放送を切断
        if not self.btLiveCon.get_sensitive():
            self.LiveDisconnect()
        
        # 放送に接続
        self.LiveConnect()

    def LiveIdDrags( self, widget, context, x, y, selection, info, time):
        """
        EntryにURIがドラッグされたときにURIをセットする
        
        引数:
        widget -
        context -
        x -
        y -
        selection -
        info -
        time -
        返し値:
        
        """
        # ドラッグされたデータを入力する 
        uri = selection.data
        self.enLive.set_text( uri.rstrip())

    def EntryKeyPress( self, widget = None, event = None):
        """
        コメントEntryにてM-Enterでコメントを送信する
        
        引数:
        widget - 
        event  -
        返し値:
        
        """
        # 入力されたキー名を取得
        keyname = gtk.gdk.keyval_name( event.keyval)
        
        # モディファイアリスト
        MOD = [ 0, 0x18, 0x14]

        # エンターが入力されたら
        if "Return" == keyname:
            # モディファイアキー設定がなしならば
            if self.setting.p[ "pmod"] == 0:
                self.PostComment( widget)
            # モディファイアキーの入力なら
            elif event.state == MOD[ self.setting.p[ "pmod"]]:
                self.PostComment( widget)

    def TreePopup( self, widget = None, event = None):
        """
        TreeViewで右クリック時のコンテキストメニュー

        引数:
        widget - 
        event  - 
        返し値:
                
        """
        # 右クリックの判定
        if event.button == 3:
            # コンテキストメニューの表示
            self.mnTree.popup( None, None, None, event.button, event.time)            

    def ColumnResize( self, source, condition):
        """
        カラムテキストの折り返し幅を調整
        
        引数:
        source - 
        condition -         
        返し値:
        """
        # 保存カラム幅と実カラム幅が違えば
        if self.clComWidth != self.clCom.get_width():
            # 実カラム幅を保存カラム幅に
            self.clComWidth = self.clCom.get_width()
            # テキストの折り返しを調整
            self.clComCrt.set_property( "wrap-width", self.clComWidth - 10)
        
    def CheckScroll( self):
        """
        スクロールさせるか否か
        
        引数:

        返し値:

        """
        # 現在のスクロール位置
        adjustment = self.scrTree.get_vadjustment()
        
        # スクロール位置を
        adjustment.value = adjustment.upper - adjustment.page_size

    def Time2LiveFTime( self, base, now):
        """
        コメント時間を放送フォーマットの時間も時刻文字列に変換する

        引数:
        base - 放送基本時間
        now  - コメント時間
        返し値:
         - コメント投稿放送時間文字列
        """
        # 経過秒を計算
        tm = now - base
        
        # フォーマットして返す(時間、分ともに0埋め2桁
        return time.strftime( "%H:%M:%S", time.gmtime( tm))[1:]


    def CommentCopy( self, widget = None):
        """
        コメントをコピー
        
        引数:
        widget -
        返し値:
        
        """
        # コメントを取得
        comment = self.GetTreeColumn( 2)
        
        # コメントをクリップボードにコピー
        self.clipboard.set_text( comment)

    def LoadNickDictionaly( self):
        """
        ニックネーム辞書の読み込み
        
        引数:
        
        返し値:
        
        """
        if os.access( self.setting.nicknameFile, os.F_OK):
            # 辞書の読み込み
            f = open( self.setting.nicknameFile, "r")
            self.userDict = pickle.load( f)
            f.close()
        else:
            # 無ければ辞書を作成
            self.userDict = {}

    def LoadSetting( self):
        """
        セッティング情報の適応
        
        引数:
        
        返し値:
        
        """
        # 設定の適応
        self.lbCookieBrowser.set_active( self.setting.p[ "ctype"])
        self.lbRetMod.set_active( self.setting.p[ "pmod"])
        self.cb184Def.set_active( self.setting.p[ "184"])
        self.cbNameOw.set_active( self.setting.p[ "nickOw"])
        self.cbNameOwNonNum.set_active( self.setting.p[ "nickOwIsNum"])
        self.cbOwComClCh.set_active( self.setting.p[ "BgOwnerColorChange"])
        self.enOwComCl.set_text( self.setting.p[ "BgOwnerColor"])
        self.enBrowser.set_text( self.setting.p[ "browser"])

    def SaveSetting( self, widget = None):
        """
        設定の保存
        
        引数:
        widget -        
        返し値:
        
        """
        # クッキーブラウザ
        active = self.lbCookieBrowser.get_active()
        self.setting.p[ "ctype"] = active
        
        # 投稿モディファイア
        active = self.lbRetMod.get_active()
        self.setting.p[ "pmod"] = active
        
        # 184
        if self.cb184Def.get_active():
            self.setting.p[ "184"] = True
        else:
            self.setting.p[ "184"] = False
        
        # ニックネーム上書き
        if self.cbNameOw.get_active():
            self.setting.p[ "nickOw"] = True
        else:
            self.setting.p[ "nickOw"] = False
        
        # 数値ニックネーム上書き
        if self.cbNameOwNonNum.get_active():
            self.setting.p[ "nickOwIsNum"] = True
        else:
            self.setting.p[ "nickOwIsNum"] = False
            
        # 放送主コメントの背景色変更
        if self.cbOwComClCh.get_active():
            self.setting.p[ "BgOwnerColorChange"] = True
        else:
            self.setting.p[ "BgOwnerColorChange"] = False
        
        # 放送主コメント背景色
        self.setting.p[ "BgOwnerColor"] = self.enOwComCl.get_text()
        
        # URIオープンブラウザ
        self.setting.p[ "browser"] = self.enBrowser.get_text()
        
        # 設定を保存
        f = open( self.setting.settingFile, "w")
        pickle.dump( self.setting.p, f)
        f.close()
        
        # 設定を読み込み
        self.LoadSetting()
 
    def OpenUserpage( self, widget = None):
        """
        生IDならユーザページを開く
        
        引数:
        widget -        
        返し値:
        
        """
        
        # noを取得
        no = self.GetTreeColumn( 0)
        
        # 投稿者IDの抜き出し                                                                
        for line in self.live.comList:
            if line[0] == no:                                                               
                id = line[1]                                             
                break
        
        # 生IDかチェック
        if id.isdigit():
            # ページを開く
            os.popen( "%s '%s%s' &" % ( self.setting.p[ "browser"], "http://www.nicovideo.jp/user/", id)) 

    def GetTreeColumn( self, retno):
        """
        選択されている行の指定カラムの要素を返す
        
        引数:
        retno - カラム番号
        返し値:
         - カラム番号の要素
        """
        
        # セレクトされている行を取得
        selection = self.trCom.get_selection()
        # 行からモデルとイテレータを取得
        ( model, iter) = selection.get_selected()
        # モデルとイテレータから行のIDを取得 ( 0: No行
        return model.get_value( iter, retno)
        
    def OpenUri( self, widget = None):
        """
        コメントにURIが含まれていれば開く
        
        引数:
        widget -
        返し値:
        
        """
        # コメントを取得
        comment = self.GetTreeColumn( 2)
                
        # URIを抽出
        uriPattern = re.compile( r'(http://[\w\d/\-_.%?=&]+)')
        match = uriPattern.findall( comment)
        
        # URIがあれば開く
        if len( match) != 0:
            os.popen( "%s '%s' &" % ( self.setting.p[ "browser"], match[0]))

    def NickDialog( self, widget = None):
        """
        ニックネーム設定用ダイアログの表示

        引数:
        widget - 

        戻し値:
        """
        # セレクトされている行を取得
        selection = self.trCom.get_selection()
        # 行からモデルとイテレータを取得
        ( model, iter) = selection.get_selected()
        # モデルとイテレータから行のIDを取得 ( 0: No行
        no = model.get_value( iter, 0)

        # 投稿者IDの抜き出し                                                                
        for line in self.live.comList:
            if line[0] == no:                                                               
                id = line[1]                                             
                break
        
        # ニックネームを取得
        nick = self.Id2Name( id)
        if nick == id:
            nick = ""

        # ニックネームダイアログ
        dlg = NickDialog( title = "ニックネーム設定", id = id, nick = nick, flags = gtk.DIALOG_DESTROY_WITH_PARENT, buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        # ダイアログの表示 終了コードを保存
        resid = dlg.run()
        # 終了コードがOKコードなら
        if resid == gtk.RESPONSE_OK:
            # 入力ニックネームを取得し、設定する
            nick = dlg.RetNick()
            self.SetNick( id, nick)
        # ダイアログを終了する
        dlg.destroy()

        # ポインタを初期化
        self.curListNum = 0
        
        # 行番号を初期化
        self.iter = 1
        
        # 前コメント番号を初期化
        self.beforeNo = None
        
        # TreeViewを消去
        self.trCom.get_model().clear()

        # オリジナル設定を保存 
        nickOwOrg = self.setting.p[ "nickOw"]
        self.setting.p[ "nickOw"] = False

        # TreeViewの更新
        self.TreeAppendComment()
        
        # オリジナル設定に戻す
        self.setting.p[ "nickOw"] = nickOwOrg

    def SetNick( self, id, nick):
        """
        ニックネーム辞書に追加/上書きする

        引数:
        id   - ユーザID
        nick - ニックネーム
        返し値:
        
        """
        # ニックネームを辞書に設定
        self.userDict[ id] = nick

    def GetLiveId( self, idStr):
        """
        文字列からIDを抽出する
        
        引数:
        idStr - 文字列
        返し値:
        None - IDがマッチしない
         - 放送ID
        """
        # DEBUG 正しい放送IDを抜き出す
        idRegex = re.compile( r"(co\d{4,}|lv\d{4,})")
        match = idRegex.findall( idStr)

        # matchが空ならマッチしなかった        
        if len( match) == 0:
            return None
        else:
            return match[0]
        
    def LiveConnect( self, widget = None):
        """
        コメントサーバに接続
        
        引数:
        widget - 
        返し値:
        """
        # ポインタを初期化
        self.curListNum = 0
        
        # 行番号を初期化
        self.iter = 1
        
        # 前コメント番号を初期化
        self.beforeNo = None
        
        # TreeViewを消去
        self.trCom.get_model().clear()
            
        # クッキーよりセッションIDの取得
        btype = [ "ch", "gc", "fx", "nr"]
        nicoSessionId = NicoSessionId( btype[ self.setting.p[ "ctype"]])
        sessionId = nicoSessionId.sessionId
        
        # 放送IDを入力ボックスより取得
        self.liveId = self.enLive.get_text()
        
        # 入力より放送IDを抜き出す
        self.liveId = self.GetLiveId( self.liveId)
        if self.liveId == None:
            print "放送IDが不正です。"
            return
        
        # 放送へ接続
        self.live = Live( "http://watch.live.nicovideo.jp/api/getplayerstatus?v=%s" % ( self.liveId), sessionId)

        # 放送に接続できない
        if not self.live.connect:
            print "放送に接続できません"
            return

        # ソケットウォッチの追加
        self.watch = gobject.io_add_watch( self.live.sock, gobject.IO_IN, self.GetComment)

        # チケット/過去のコメントの取得
        self.live.GetTicket()

        # ボタンの制御
        self.btLiveCon.set_sensitive( False)
        self.btLiveDis.set_sensitive( True)
        self.btLiveRe.set_sensitive( True)
        self.btPost.set_sensitive( True)
        
    def LiveDisconnect( self, widget = None):
        """
        コメントサーバから切断

        引数:
        widget - 
        返し値:
        """
        # ソケットウォッチの削除
        gobject.source_remove( self.watch)

        # ソケットの切断
        self.live.SocketDisconnect()

        # 放送の削除
        del self.live

        # ボタンの制御
        self.btLiveCon.set_sensitive( True)
        self.btLiveDis.set_sensitive( False)
        self.btLiveRe.set_sensitive( False)
        self.btPost.set_sensitive( False)

    def LiveReconnect( self, widget = None):
        """
        コメントサーバへ再接続
        
        引数:
        widget - 
        返し値:
        """
        # 切断
        self.LiveDisconnect( widget)

        # 接続
        self.LiveConnect( widget)
        
    def PostComment( self, widget = None):
        """
        コメントを投稿

        引数:
        widget - 
        返し値:
        """
        # コメント入力ボックスよりコメントを取得
        self.live.comment = self.enCom.get_text()
        
        # 入力が空ならコメントを送信しない
        if self.live.comment == "":
            return
        
        # コメント入力ボックスを空に
        self.enCom.set_text( "")
        
        # 匿名コメントチェック確認
        if self.cbAnon.get_active():
            self.live.anonymity = "mail='184'"
        else:
            self.live.anonymity = ""

        # NGワードチェック
        ngWords = NgCommentDict.word
        for word in ngWords.keys():
            if self.live.comment.find( word) != -1:
                self.live.comment = self.live.comment.replace( word, ngWords[ word])

        # コメントを投稿
        self.live.PostComment()

    def GetComment( self, source, condition):
        """
        コメントを取得する
        
        引数:
        source - 
        condition -         
        返し値:
        True (id_add_watchに渡すために必要
        """
        # コメントをソケットから読み込み
        self.live.GetComment()

        # ツリーに追加
        self.TreeAppendComment()
        
        # io_add_watchに渡す
        return True

    def TreeAppendComment( self):
        """
        ツリーにコメントを追加
        
        引数:
        
        返し値:
        
        """        
        # ツリーに追加
        while self.curListNum < len( self.live.comList):
            # 名前を設定
            name = self.Id2Name( self.live.comList[ self.curListNum][1])
            
            # 時間を設定
            if self.live.comList[ self.curListNum][4].isdigit():
                time = self.Time2LiveFTime( int( self.live.base_time), int( self.live.comList[ self.curListNum][4]))
            else:
                time = ""

            # コメントからニックネームを設定
            self.Comment2Nick( self.live.comList[ self.curListNum][1], self.live.comList[ self.curListNum][2])

            # Statusを取得
            status = self.live.comList[ self.curListNum][3]

            # コメント番号
            no = self.live.comList[ self.curListNum][0]

            # アイコンの設定
            iconDir = os.path.dirname(__file__)
            if status == "0":
                statusIcon = gtk.gdk.pixbuf_new_from_file( iconDir + "/Normal.gif")
            elif status == "1":
                statusIcon = gtk.gdk.pixbuf_new_from_file( iconDir + "/Premium.gif")
            elif status == "3":
                statusIcon = gtk.gdk.pixbuf_new_from_file( iconDir + "/Owner.gif")
            else:
                statusIcon = gtk.gdk.pixbuf_new_from_file( iconDir + "/Ng.png")

            # NGコメント
            if self.beforeNo != None and no != "0":
                sa = int( no) - int( self.beforeNo)
                if sa != 1:
                    for i in range( 1, sa):
                        # NGコメント背景 
                        color = self.setting.p[ "BgNgColor"]
                        # NGコメントアイコン
                        ngIcon = gtk.gdk.pixbuf_new_from_file( iconDir + "/Ng.png")
                        # NGコメントをTreeViewに追加
                        self.trCom.get_model().append( ( str( int( no) - sa + i), "",  "NGコメント", ngIcon, "", color),)
                        self.iter += 1

            # コメントNoを保存
            self.beforeNo = no
            
            # コメント
            comment = self.live.comList[ self.curListNum][2]
            comment = self.UnescapeStr( comment)
            
            # 背景色の取得
            color = self.Iter2BgColor( self.iter, status)
            
            # ツリーに行を追加
            self.trCom.get_model().append( ( no, name, comment, statusIcon, time, color),)
            
            # 行番号を次へ
            self.iter += 1
            
            # リストポインタを移動
            self.curListNum += 1

        # スクロールの調整
        adjustment = self.scrTree.get_vadjustment()

        # スクロールさせるかいなか
        if adjustment.value == adjustment.upper - adjustment.page_size:
            gobject.idle_add( self.CheckScroll)

    def Comment2Nick( self, id, comment):
        """
        コメントからニックネームを辞書に追加

        引数:
        id      - ユーザID
        comment - コメント  
        戻し値:
        True: 成功
        False: 失敗(上書き未許可
        """

        # ニックネームの上書きを許可するか
        nickOw = self.setting.p[ "nickOw"]
        # ニックネームが数値のみでも登録するか
        nickNumOw = self.setting.p[ "nickOwIsNum"]

        # コメントに@が含まれていれば
        if comment.find( "@") != -1 or comment.find( "＠") != -1:
            # @で分割
            nick = re.split( r"@|＠", comment)
            # 分割した文字列の最後をさらにスペースで分割して最初をニックネームに設定
            nick = nick[-1].split( " ")[0]
            # ニックネームが数値だけで、数値の登録を拒否していれば
            if nick.isdigit() and nickNumOw:
                return False
            else: 
                # IDが存在し、ニックネームの上書きが許可されていればニックネームの設定
                if self.userDict.has_key( id) and nickOw:
                    self.SetNick( id, nick)
                # IDが存在しなければニックネームの設定
                elif not self.userDict.has_key( id):
                    self.SetNick( id, nick)
                return True

    def Id2Name( self, id):
        """
        ユーザ名ディクショナリからユーザ名を検索

        引数:
        id - ユーザID
        返し値:
         - ニックネームが登録されていたらニックネームを、登録されていなければidを返す
        """
        # ニックネーム辞書よりIDを検索する 
        if self.userDict.has_key( id):
            return self.userDict[ id]
        else:
            return id

    def UnescapeStr( self, comment):
        """
        HTMLエスケープされたコメントをアンエスケープする
        
        引数:
        comment - コメント
        返し値:
         - アンエスケープしたコメント
        """
        return comment.replace( "&lt;", r"<").replace( "&gt;", r">").replace( "&quote;", r"\"").replace( "&amp;", r"&")
    
    def Iter2BgColor( self, iter, status = 0):
        """
        行番号に応じた背景色を返す
        
        引数:
        iter - 行番号
        返し値:
         - 背景色
        """
        # 放送主コメントなら設定カラーを返す
        if status == "3" and self.setting.p[ "BgOwnerColorChange"]:
            return self.setting.p[ "BgOwnerColor"]

        # 行番号に応じたカラーを返す
        if self.iter % 2:
            return "#FFFFFF"
        else:
            return "#EEEEEE"

    def SaveNickDict( self):
        """
        ニックネーム辞書を保存
        
        引数:
        
        返し値:
        """
        # 固定ハンドル保存
        f = open( self.setting.nicknameFile, "w")
        pickle.dump( self.userDict, f)
        f.close()

    def SaveCommentDict( self):
        """
        コメント辞書を保存
        
        引数:
        
        返し値:
        """
        # 固定ハンドル保存
        f = open( self.setting.commentFile, "w")
        pickle.dump( self.live.comList, f)
        f.close()

    def QuitWindow( self, widget = None, event = None):
        """
        アプリケーション終了
        
        引数:
        widget - 
        event  - 
        返し値:
        """
        # ニックネーム辞書の保存
        self.SaveNickDict()

        # コメントの保存
        self.SaveCommentDict()

        # GUI終了
        gtk.main_quit()


class NickDialog( gtk.Dialog):
    """
    ニックネーム設定ダイアログ
    """

    def __init__( self, id, nick, *args, **kwargs):
        """
        コンストラクタ
        """
        # 継承元クラスのコンストラクタ
        gtk.Dialog.__init__( self, *args, **kwargs)
        
        # ウインドウ初期化
        self.WindowInitialize( id, nick)
        
    def __del__( self):
        """
        デストラクタ
        
        引数:
        
        返し値:
        
        """
        pass

    def WindowInitialize( self, id, nick):
        """
        メインウインドウの初期化
        
        引数:
        
        返し値:
        
        """
        # デフォルトレスポンスを設定
        self.set_default_response( gtk.RESPONSE_OK)

        # 格納ボックス
        self.nickBox = gtk.VBox()

        # ID表示ラベル
        self.labelId = gtk.Label( id)

        # ニックネーム入力エントリ
        self.nickEntry = gtk.Entry()
        self.nickEntry.set_activates_default( True)
        self.nickEntry.set_text( nick)
        self.nickEntry.grab_focus()

        # ボックスに格納
        self.nickBox.add( self.labelId)
        self.nickBox.add( self.nickEntry)
        
        # ダイアログにボックスを格納
        self.vbox.add( self.nickBox)

        # 全てを表示
        self.vbox.show_all()

    def RetNick( self):
        """
        ニックネームを返す
        
        引数:
        返し値:
        """        
        return self.nickEntry.get_text()


setting = Setting()
a = WinCom( setting)
gtk.main()
