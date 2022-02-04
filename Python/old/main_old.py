# 標準ライブラリ
import datetime
import time
import json
import sys
import traceback
import atexit
import logging
import subprocess

# サードパーティライブラリ
import schedule
import threading
from websocket_server import WebsocketServer
import picamera
import pymysql.cursors

# ローカルライブラリ（自作モジュール）
from mymod import picont
from mymod import sqlcont


# --------------------------------------------------------------------------------------
# Websocket関数--------------------------------------------------------------------------
# --------------------------------------------------------------------------------------

# Called for every client connecting (after handshake)
def new_client(client, server):
    logging.debug("New client connected and was given id %d" % client['id'])
    mysql.addLogToDatabase("info", "サーバと接続しました", "")


# Called for every client disconnecting
def client_left(client, server):
    logging.debug("Client(%d) disconnected" % client['id'])
    mysql.addLogToDatabase("info", "サーバとの接続が解除されました", "")


# Called when a client sends a message
def message_received(client, server, message):

    # 受信データをJSONに変換する
    try:
        logging.info("Clientからデータを受信")
        logging.debug("Client(%d) : %s" %(client['id'], message) + " (dict)")
        message = json.loads(message)


    # 受信データがJSONに変換できない場合ログを残し、処理を飛ばす
    except json.JSONDecodeError as e:
        logging.debug(sys.exc_info())
        logging.debug(e)
        if len(message) > 200:
            message = message[:200]+'..'
        logging.debug("受信したデータをJSONに変換できなかった")
        mysql.addLogToDatabase("warning", "受信データをJSON形式に変換できませんでした", "")
        return False

    # JSONに変換できた場合
    else:
        # JSONメッセージの種類判定
        # ACK要求
        if(message.get('messageType') == "ACK"):
            sendDbToClient(server, "sensorDB", 1)
            sendDbToClient(server, "logDB", message.get('maxShowRow'))
            send_ready_toClient(server)

        # 操作要求
        elif(message.get('messageType') == "operation"):

            # Light
            if(message.get('light') == "1"):
                setlight(True)
            elif(message.get('light') == "0"):
                setlight(False)

            # CO2
            if(message.get('co2') == "1"):
                set_co2(True)
            elif(message.get('co2') == "0"):
                set_co2(False)

            # coolfan
            if(message.get('coolfan') == "1"):
                set_coolfan(True)
            elif(message.get('coolfan') == "0"):
                set_coolfan(False)

            # 餌やり
            if(message.get('feeding') == "1"):
                feeding(360)

            # 写真撮影
            if(message.get('take_camera') == "0"):
                # 写真を撮影してhpgファイルとして保存
                take_camera(False)

            # 動画撮影
            if(message.get('take_camera') == "1"):
                # 動画を撮影してmp4ファイルとして￥保存
                take_camera(True)

            # クライアントの画面を更新させる
            sendAckToClient(server)

        # cameraDBデータベース要求
        elif(message.get('messageType') == "get_cameraDB"):

            connection = connectDatabase()
            try:
                with connection.cursor() as cursor:

                    # Clientに送信するデータのlist配列
                    sendDataList = []

                    # 最新レコードからshowPictureOffsetだけ後ろのレコードを所得
                    sql = "SELECT * FROM cameraDB ORDER BY num desc LIMIT 1 OFFSET {}" \
                    .format(message.get('showPictureOffset'))
                    logging.debug("SQL query : " + sql)
                    cursor.execute(sql)
                    sendDataList = cursor.fetchall()

                    # ClientがJSON種類を認識するためのmessageTypeを挿入
                    sendDataList.insert(0, {'messageType': 'get_cameraDB'})

                    # レコード数を所得
                    sql = "SELECT COUNT(*) FROM cameraDB"
                    logging.debug("SQL query : " + sql)
                    cursor.execute(sql)
                    recordNum = cursor.fetchall()
                    logging.debug("SQL answer : " + str(recordNum))

                    # クライアント側が要求した写真の前後に写真が存在するか情報を付加する
                    sendDataList.append({'pictureOverflow': ''})

                    # showPictureOffsetが0の場合、それより新しい画像はないので、メッセージにnewestを挿入
                    if(message.get('showPictureOffset') == 0):
                        sendDataList[2] = {'pictureOverflow': 'newest'}

                    # showPictureOffsetが(レコード数 - 1)と同じ場合、それより古い画像はないので、メッセージにoldestを挿入
                    elif(message.get('showPictureOffset') == recordNum[0].get('COUNT(*)') - 1):
                        sendDataList[2] = {'pictureOverflow': 'oldest'}

                    # 前後に画像あり
                    else:
                        sendDataList[2] = {'pictureOverflow': ''}

                    # レコードが一つもない場合は、メッセージ = noPicture
                    if(recordNum[0].get('COUNT(*)') == 0):
                        sendDataList[2] = {'pictureOverflow': 'noPicture'}

                    # レコードが一つだけの場合は、メッセージ = onlyone
                    elif(recordNum[0].get('COUNT(*)') == 1):
                        sendDataList[2] = {'pictureOverflow': 'onlyone'}


                    # dict型で得たlog table をJSON文列に変換　インデント2 日本語対応 datetime変換callback
                    sendJson = json.dumps(
                        sendDataList, indent=2, default=support_datetime_default)
                    server.send_message_to_all(sendJson)

                    # Clientにreadyを伝える
                    send_ready_toClient(server)


            except Exception as e:
                traceback.print_exc()
                mysql.addLogToDatabase("warning", "画像ファイル名所得・送信でエラーが発生しました。", "")
                send_serverError_toClient(server)


        # センサデータ要求
        elif(message.get('messageType') == "getSensorDB"):

            # MySQLにログイン
            connection = connectDatabase()

            try:
                with connection.cursor() as cursor:

                    if(message.get('period') == "days=1"):
                        datetimePeriod = datetime.timedelta(days=1)
                    elif(message.get('period') == "days=7"):
                        datetimePeriod = datetime.timedelta(days=7)
                    else:
                        logging.debug("error : unexpected data period => " +
                              message.get('period'))

                    datetimeNow = datetime.datetime.now()
                    datetimeEnd = datetimeNow.strftime('%Y-%m-%d %H:%M:%S')
                    datetimeStart = (
                        datetimeNow - datetimePeriod).strftime('%Y-%m-%d %H:%M:%S')

                    sql = "SELECT datetimenow,{} FROM sensorDB WHERE datetimenow BETWEEN '{}' AND '{}'" \
                    .format(message.get('sensorName1'), datetimeStart, datetimeEnd)
                    logging.debug("SQL query : " + sql)  # SQL文表示
                    cursor.execute(sql)
                    all_data = cursor.fetchall()  # all_dataにMYSQLから所得したデータを格納

                    # ClientがJSON種類を認識するためのヘッダデータを生成
                    tempDict = {"messageType": "getSensorDB"}  # JSON種類
                    tempDict["datetimeStart"] = datetimeStart
                    tempDict["datetimeEnd"] = datetimeEnd
                    tempDict["sensorName1"] = message.get('sensorName1')

                    all_data.insert(0, tempDict)  # ヘッダデータを挿入

                    # 辞書型で得たlog table をJSON文列に変換　インデント2 日本語対応 datetime変換callback
                    sendJson = json.dumps(
                        all_data, indent=2, default=support_datetime_default)
                    server.send_message_to_all(sendJson)

                    # Clientにreadyを伝える
                    send_ready_toClient(server)

            except Exception as e:
                traceback.print_exc()
                mysql.addLogToDatabase("warning", "sensorDBからデータ所得・送信でエラーが発生しました。", "")
                send_serverError_toClient(server)



        # 自動操作設定適用
        elif(message.get('messageType') == "set_schedulerDB"):

            # 受信したデータをsetTaskSchedulerDBに格納する 
            status = mysql.set_schedulerDB(message)

            if status == True:
                # setTaskSchedulerDBから時刻設定を読み取り、スケジューラをsetする
                setScheduleFunction()

                # クライアントの画面を更新させる
                sendAckToClient(server)

            else:
                mysql.addLogToDatabase("warning", "schedulerDBの設定に失敗しました", "")
                send_serverError_toClient(server)



        # schedulerDB(予約設定）のデータをclientに渡す
        elif(message.get('messageType') == "get_schedulerDB"):

            # setTaskSchedulerDBから設定をgetする
            status, all_data = mysql.get_schedulerDB()

            if status == True:
                # ClientがJSON種類を認識するためのヘッダデータを挿入
                all_data.insert(0, {"messageType": "get_schedulerDB"})  # ヘッダデータを挿入

                # 辞書型をJSON文列に変換　インデント2 日本語対応 datetime変換callback
                sendJson = json.dumps(all_data, indent=2,
                                      default=support_datetime_default)

                # ClientにJSON文字列を渡す
                server.send_message_to_all(sendJson)

                # クライアントの画面を更新させる
                sendAckToClient(server)

            else:
                mysql.addLogToDatabase("alart", "schedulerDBの設定読み込みに失敗しました", "")
                send_serverError_toClient(server)



        # mesageTypeが判別不可
        else:
            logging.debug("JSONのmesageType判別不可")
            mysql.addLogToDatabase("warning", "受信データのmesageTypeが判別不可でした", "")
            send_serverError_toClient(server)








# ----------------------------------------------------------------------------------------------------
# 各種関数群 -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------



def setlight(b):
    """
        照明を操作　→　操作結果をlogDBにINSERT　→　sensorDBを更新
        照明はAC100Vのport1に接続されている

        Parameters
        ----------
        b: boolean
            True = ON、　False = OFF

        Returns
        -------
        Void
    """

    logging.info("AC100V 1 (照明) を制御 ")

    pii.set_ac100v(1, b)  
    b = pii.get_ac100v(1)
    if b == True:
        mysql.addLogToDatabase("info", "ライト = ON", "")
    elif b == False:
        mysql.addLogToDatabase("info", "ライト = OFF", "")
    
    # 全センサ再測定しsensorDBを更新
    addToSensorDB()



def set_co2(b):
    """
        CO2弁を操作　→　操作結果をlogDBにINSERT　→　sensorDBを更新
        CO2弁はAC100Vのport2に接続されている

        Parameters
        ----------
        b: boolean
            True = ON、　False = OFF

        Returns
        -------
        Void
    """

    logging.info("AC100V 2 (CO2) を制御 ")

    pii.set_ac100v(2, b)  
    b = pii.get_ac100v(2)
    if b == True:
        mysql.addLogToDatabase("info", "CO2 = ON", "")
    elif b == False:
        mysql.addLogToDatabase("info", "CO2 = OFF", "")
    
    # 全センサ再測定しsensorDBを更新
    addToSensorDB()   



def set_coolfan(b):
    """
        冷却用ファンを操作　→　操作結果をlogDBにINSERT　→　sensorDBを更新
        ファンはAC100Vのport3に接続されている

        Parameters
        ----------
        b: boolean
            True = ON、　False = OFF

        Returns
        -------
        Void
    """

    logging.info("AC100V 3 (FAN) を制御 ")

    pii.set_ac100v(3, b)
    b = pii.get_ac100v(3)
    if b == True:
        mysql.addLogToDatabase("info", "冷却ファン = ON", "")
    elif b == False:
        mysql.addLogToDatabase("info", "冷却ファン = OFF", "")

    # 全センサ再測定しsensorDBを更新
    addToSensorDB()
    


def feeding(deg):
    """
        Lightを操作し、操作結果をlogDBにINSERTする
        また、sensorDBを更新する

        Parameters
        ----------
        deg: int
            えさやりモーター回転角度 [deg]

        Returns
        -------
        Void
    """

    logging.info("えさやりモータを制御")

    pii.rotate_motor(deg)
    mysql.addLogToDatabase("info", "えさやり完了", "")

    # 全センサ再測定しsensorDBを更新
    addToSensorDB()



# カメラ撮影
def take_camera(movieflag):

    logging.info("写真撮影")

    # cammeraDBに現在日時と採番したファイル名をINSERTし、採番したファイル名をgetする
    filename = mysql.add_get_picturename(movieflag)

    # ファイル名から写真を保存するフォルダパスを生成
    filepass = "../www/img/picture/{}.jpg".format(filename)
    # 写真を撮影し指定のファルダパスに保存する
    pii.take_picture(filepass)

    # 動画撮影フラグ=Trueの場合　写真と同じファイル名で動画も撮影する
    if(movieflag == True):

        logging.info("動画撮影")
        # ファイル名から写真を保存するフォルダパスを生成
        filepass = "../www/img/movie/{}.h264".format(filename)
        # 動画を撮影し指定のフォルダパスに保存する
        pii.take_movie(filepass, 10)
        # h264をmp4に変換
        cmd = "MP4Box -add ../www/img/movie/{}.h264 ../www/img/movie/{}.mp4".format(filename, filename)
        subprocess.run(cmd, shell=True)
        logging.debug("Shell : " + cmd)
        # 変換前のh264ファイルを削除
        cmd = "rm ../www/img/movie/{}.h264".format(filename)
        subprocess.run(cmd, shell=True)
        logging.debug("Shell : " + cmd)
        # logDBにログをINSERTする
        mysql.addLogToDatabase("info", "写真・動画を撮影しました。", "")

    else:
        # logDBにログをINSERTする
        mysql.addLogToDatabase("info", "写真を撮影しました。", "")



# schedularDBから自動操作設定を読み取り、schedule関数を設定する
def setScheduleFunction():

    logging.info("schedulerDBから設定を読み取りschedule関数をセット")

    # schedule関数をクリア
    schedule.clear()

    # shedulerDBから設定をgetする
    status, all_data = mysql.get_schedulerDB()

    if status == True:

        # 照明　　Manualの場合はschedule関数を設定しない、
        templist = all_data[0]['light'].split(',')
        if (templist[0] != "Manual"): # Auto or Manualを判定
            if (len(templist[0]) == 5): # N時間　形式をチェック"hh:mm" 
                schedule.every().day.at(templist[0]).do(setlight, b=True).tag('light')
            if (len(templist[1]) == 5): # OFF時間　形式をチェック"hh:mm" 
                schedule.every().day.at(templist[1]).do(setlight, b=False).tag('light')

        # CO2　　Manualの場合はschedule関数を設定しない、
        templist = all_data[0]['co2'].split(',')
        if (templist[0] != "Manual"): # Auto or Manualを判定
            if (len(templist[0]) == 5): # ON時間　形式をチェック"hh:mm"
                schedule.every().day.at(templist[0]).do(set_co2, b=True).tag('co2')
            if (len(templist[1]) == 5): # OFF時間　形式をチェック"hh:mm" 
                schedule.every().day.at(templist[1]).do(set_co2, b=False).tag('co2')

        # 餌やり　Manualの場合はschedule関数を設定しない、listの全要素の時刻に対してscheduleを設定する。
        templist = all_data[0]['feeding'].split(',')
        if (templist[0] != "Manual"): # Auto or Manualを判定
            for l in templist:
                if (len(l) == 5): # 形式をチェック"hh:mm" 
                    schedule.every().day.at(l).do(feeding, deg=720).tag('feeding')

        # 写真　　Manualの場合はschedule関数を設定しない、 listの全要素の時刻に対してscheduleを設定する。
        templist = all_data[0]['picture'].split(',')
        if (templist[0] != "Manual"): # Auto or Manualを判定
            for l in templist:
                if (len(l) == 5): # 形式をチェック"hh:mm" 
                    schedule.every().day.at(l).do(take_camera, movieflag=True).tag('camera')

        # センサ定時計測Schedule
        schedule.every(all_data[0]['measure_intervalTime']).minutes.do(addToSensorDB)

        # センサ計測値による自動制御
        schedule.every(all_data[0]['measure_intervalTime']).minutes.do(auto_control_by_sensor)

        # logDBにログ保存
        mysql.addLogToDatabase("info", "予約設定を更新しました", "")
        for l in schedule.jobs:
            logging.debug(l)

    else:
        logging.error("schedulerDBの読み取りに失敗")
        mysql.addLogToDatabase("alart", "予約設定の更新に失敗しました。", "")
    

    

# json.dump でdatetime型をstringに変換できるようにする　コールバック関数
def support_datetime_default(o):
    if isinstance(o,datetime.datetime):
        return o.isoformat(' ') #日付と時刻の間はスペース
    logging.debug(repr(o) + " is not JSON serializable")



# データベースをJSONに変換してClientに送信する
def sendDbToClient(server, nameDB, maxShowRow):

    logging.info("Clientにデータ送信")
    
    connection = connectDatabase()
    
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM {} ORDER BY num DESC LIMIT {}"
            cursor.execute(sql.format(nameDB, maxShowRow))
            logging.debug(cursor._executed) #SQL文表示
            all_data = cursor.fetchall()

            # ClientがJSON種類を認識するためのmessageTypeを挿入
            tempDict = dict([('messageType',nameDB)])
            all_data.insert(0,tempDict)

            # 辞書型で得たlog table をJSON文列に変換　インデント2 日本語対応 datetime変換callback
            sendJson = json.dumps(all_data ,indent=2, default=support_datetime_default)
            server.send_message_to_all(sendJson)
        

    except Exception as e:
        logging.debug(e)
        traceback.print_exc()
        mysql.addLogToDatabase("warning", "データベース要求クエリが不正です。","")
        
        


    
# クライアント側からACK要求するように要求
def sendAckToClient(server):
    dicJson = {}
    dicJson = [{"messageType" : "ACK"},{"remark" : "none"}]
    sendJson = json.dumps(dicJson)
    server.send_message_to_all(sendJson)    


# クライアント側へ準備完了を伝える
def send_ready_toClient(server):
    dicJson = {}
    dicJson = [{"messageType" : "ready"},{"remark" : "none"}]
    sendJson = json.dumps(dicJson)
    server.send_message_to_all(sendJson)   


# クライアント側へサーバ側でエラーが発生したことを伝える
def send_serverError_toClient(server):
    dicJson = {}
    dicJson = [{"messageType" : "serverError"},{"remark" : "none"}]
    sendJson = json.dumps(dicJson)
    server.send_message_to_all(sendJson)   

    
# RCMデータベースに接続する関数
def connectDatabase():
    try:
        connection = pymysql.connect(host="localhost", user="pi", password="mio3297", db="RCM", charset="utf8",cursorclass=pymysql.cursors.DictCursor)
        return connection
    except Exception as e:
        logging.debug(e)
        traceback.print_exc() 



# sensorDBにGPIOとセンサ値をINSERT
def addToSensorDB():

    logging.info("各種センサ値を取得し、sensorDBを更新")
    
    # 加速度をセンサより所得
    # x, y, z = pii.get_accelerateXYZ_sensor()
        
    # えさ残量をセンサより所得
    # aV = pii.get_foodlevel_sensor()

    # 水温をセンサより取得
    (tempWater, tempAir, status) = pii.get_tempWater_tempAir()
    if(status != True):
        mysql.addLogToDatabase("alert", "センサ値の取得に失敗しました。(水温・気温)", "")

    try:
        # Dbに接続
        connection = connectDatabase()
        with connection.cursor() as cursor:
            sql = 'INSERT INTO sensorDB (light, co2, coolfan, currentConsumption, tempWater, tempAir, waterLevel, foodLevel, status) '\
            'VALUES({},{},{},{},{},{},{},{},{})'\
            .format(pii.get_ac100v(1),pii.get_ac100v(2),pii.get_ac100v(3), "0", tempWater, tempAir, "30", "80", 1)
            cursor.execute(sql)
            connection.commit()
            logging.debug('SQL query : ' + cursor._executed) #SQL文表示
            
    except Exception as e:
        logging.debug(e)
        traceback.print_exc() 
        
    finally:
        connection.close()
        


# センサ計測値による自動制御
def auto_control_by_sensor():

    logging.info("センサ計測値による自動制御処理")

    try:

        # sensorDBから最新の計測値を所得
        (status, all_data) = mysql.get_sensorDB_latest1()   #all_dataはlist型　all_data[0]はdict型
        if(status == False):
            mysql.addLogToDatabase("alert", "sensorDBのアクセスに失敗　ファンの自動制御をスキップしました", "")
            raise Exception("sensorDB accsess error")

        tempWater = all_data[0]['tempWater']

        # shedulerDBから設定をgetする
        status, all_data = mysql.get_schedulerDB()
        if(status == False):
            mysql.addLogToDatabase("alert", "schedularDBのアクセスに失敗　ファンの自動制御をスキップしました", "")
            raise Exception("schedularDB accsess error")

        tempWater_threshold = all_data[0]['coolfan']

        # 閾値が数字かチェック
        if(tempWater_threshold.isdecimal() == True):
            # 冷却ファン制御
            if(tempWater > int(tempWater_threshold) and (pii.get_ac100v(3) == False)):
                set_coolfan(True)
            elif(tempWater <= int(tempWater_threshold) and (pii.get_ac100v(3) == True)):
                set_coolfan(False)

    except Exception as e:
        logging.debug(e)
        traceback.print_exc() 


# --------------------------------------------------------------------------------------
# ------------------------スレッド処理--------------------------
# --------------------------------------------------------------------------------------

class MyThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)


    def run(self):
        # Web socket準備
        PORT=9001
        server = WebsocketServer(PORT, host='192.168.1.21')
        server.set_fn_new_client(new_client)
        server.set_fn_client_left(client_left)
        server.set_fn_message_received(message_received)
        server.run_forever()






# --------------------------------------------------------------------------------------
# mainルーチン---------------------------------------------------------------------------
# --------------------------------------------------------------------------------------

# Web socket通信を別スレッドで起動
thread1 = MyThread()
thread1.start()

# GIPO制御用クラス"GpioControlをインスタンス化する
pii = picont.GpioControl()

# MySQL制御用クラス"MysqlControl"をインスタンス化する
mysql = sqlcont.MysqlControl()

# プログラム終了時の処理をatexitで定義
atexit.register(pii.close_gpio)

# ロギングの設定　ログフォーマットを定義
formatter = '%(levelname)s : %(asctime)s \n%(message)s\n'
# ログレベルを DEBUG に変更
logging.basicConfig(level=logging.DEBUG, format=formatter)

# 定期実行スケジューラ設定
setScheduleFunction()



# mainループ--------------------------------------------------
while(1):

    # 定時操作スケジュールを確認しに行く
    schedule.run_pending()

    # 処理を軽くするためにディレイを入れる
    time.sleep(5)
    
    

