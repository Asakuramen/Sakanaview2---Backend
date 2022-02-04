# 標準ライブラリ
from asyncio.tasks import sleep
import datetime
import time
import json
import sys
import traceback
import logging
import subprocess
import asyncio
import decimal
import os
import signal
import threading


# サードパーティ
import pigpio
import websockets
import schedule

# 自作ライブラリ
from mylib import picont
from mylib import sqlcont


# 定数
PARAMETER_FILEPASS = "./parameter/main_parameter.json"
PARAMETER_FILEPASS_DEBUG = "./parameter/main_parameter_debug.json"


# --------------------------------------------------------------------------------------
# 関数-----------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------

def update_sensordb():
    """
        各種センサ値やステータス情報を取得し、sernsorDBに記録
        センサ値による自動制御を行う
        ・冷却ファン

        Parameters
        ----------
        Void

        Returns
        -------
        Void

    """

    # 各種センサ値取得 --------------------------------
    # 水温、気温、湿度、センサstatus
    (air_temperature, air_humidity, status_sensor_air) = pio.get_tempAir_humAir(1)
    (watar_temperature, status_sensor_watar) = pio.get_tempWater(1)
    # 補正値適用
    watar_temperature += param['other']['watar_temperature_compensation']
    air_temperature += param['other']['air_temperature_compensation']
    air_humidity += param['other']['air_humidity_compensation']

    # food_level　仮で80%固定とする
    food_level = 80.0
    # トータルstats は仮で0とする
    status = 0

    # AC100V
    ac100v1 = pio.get_ac100v_gpio(1)
    ac100v2 = pio.get_ac100v_gpio(2)
    ac100v3 = pio.get_ac100v_gpio(3)
    ac100v4 = pio.get_ac100v_gpio(4)
    ac100v5 = pio.get_ac100v_gpio(5)
    ac100v6 = pio.get_ac100v_gpio(6)

    # センサ値による自動制御 ----------------------------
    # 冷却ファン (ac100v_no6)
    if(watar_temperature > param['control']['coolfan_threshould']):
        if(pio.get_ac100v_gpio(6) == 0):  # 連続操作を回避
            set_ac100v(6, 1)  # 冷却ファン ON
            ac100v6 = pio.get_ac100v_gpio(6)  # 状態更新
    else:
        if(pio.get_ac100v_gpio(6) == 1):  # 連続操作を回避
            set_ac100v(6, 0)  # 冷却ファン OFF
            ac100v6 = pio.get_ac100v_gpio(6)  # 状態更新

    # sensorDBにセンサ情報を挿入 --------------------------
    mariadb.add_sensordb(ac100v1, ac100v2, ac100v3, ac100v4, ac100v5, ac100v6, watar_temperature,
                         air_temperature, air_humidity, food_level, status_sensor_watar, status_sensor_air, status)

    logging.info('updated sensorDB')


def feeding(count, ontime, interval):
    """
        餌やり制御
        ログ記録


        Parameters
        ----------
        count : int
            ソレノイド駆動回数
        ontime : double
            ソレノイドON時間
        interval : double
            ソレノイド駆動間隔

        Returns
        -------
        void

    """

    for i in range(count):
        pio.active_solenoid(ontime)
        time.sleep(interval)

    logging.info(f'feeding (count={count} ontime={ontime} interval={interval})')
    mariadb.add_logdb('info', '餌やりを実行しました')
    update_sensordb()   # センサ値更新


def start_hls_livestream():
    """
        HTTP Live Streaming(HLS) を開始するコマンドを実行

        Parameters
        ----------
        Void

        Returns
        -------
        void

    """
    try:

        # FFmpegでHLS開始Shellを実行
        # cmd = "timeout 30 sh ~/www/img/live/hls_streaming_start.sh"
        cmd = "sh ~/Python/shell/hls_streaming_start.sh"
        subprocess.Popen(cmd, shell=True)
        logging.debug("Shell : " + cmd)

    except Exception as e:
        mariadb.add_logdb('alarm', 'Live配信開始修理中にエラーが発生しました')
        logging.error('Error on HTTP Live Streaming(HLS)')
        logging.error(traceback.format_exc())

    else:
        mariadb.add_logdb('info', 'Live配信を開始しました')
        logging.info('Start HTTP Live Streaming(HLS)')


def stop_hls_livestream():
    """
        HTTP Live Streaming(HLS) を停止するコマンドを実行

        Parameters
        ----------
        void

        Returns
        -------
        void

    """
    try:

        # FFmpegのプロセスをkillするシェルを実行
        cmd = "sh ~/Python/shell/hls_streaming_stop.sh"
        subprocess.Popen(cmd, shell=True)
        logging.debug("Shell : " + cmd)

    except Exception as e:
        mariadb.add_logdb('alarm', 'Live配信停止修理中にエラーが発生しました')
        logging.error('Error on HTTP Live Streaming(HLS)')
        logging.error(traceback.format_exc())

    else:
        mariadb.add_logdb('info', 'Live配信を停止しました')
        logging.info('Stop HTTP Live Streaming(HLS)')


def set_ac100v(port, b):
    """
        AC100V制御
        ログ記録

        Parameters
        ----------
        port: int
            AC100VのNo.を指定 (1〜6)

        b: boolean
            True = ON、　False = OFF

        Returns
        -------
        Void
    """

    name = param['device_id_name'].get("ac100v_no" + str(port))

    pio.set_ac100v_gpio(port, b)

    if b == 0:
        mariadb.add_logdb('info', f'{name} をOFFに設定しました')
    elif b == 1:
        mariadb.add_logdb('info', f'{name} をONに設定しました')
    else:
        mariadb.add_logdb('alarm', f'AC100V No.{port} の操作パラメータoperationが不正です')

    # 操作後sensorDBを更新
    update_sensordb()


def take_picmovie(movieflag):
    """
        写真・動画撮影する
        ファイル名はmcameraDBから自動採番する
        mariadbのオブジェクトはグローバル変数

        Parameters
        ----------
        movieflag : int
            0 : 写真撮影のみ
            1 : 写真+動画撮影

        Returns
        -------
        Void
    """

    try:
        # ファイル名をcamedraDBから採番
        filename = mariadb.number_filename_picmovie(movieflag)  

        # 写真撮影
        picture_f = param['camera']['picture_f']
        cmd = f"fswebcam -r 1920x1080 --no-banner -F {picture_f} /home/tapstar/www/img/picture/{filename}.jpg"
        subprocess.run(cmd, shell=True)
        logging.debug("Shell : " + cmd)

        # 動画撮影
        if(movieflag == 1):
            cmd = f"ffmpeg -y -f alsa -thread_queue_size 8192 -i plughw:CARD=Camera,DEV=0 -f v4l2 -thread_queue_size 8192 -s 640x360 -i /dev/video0 -c:v h264_omx -b:v 768k -c:a aac /home/tapstar/www/img/movie/{filename}.mp4"
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)  # プロセスを実行
            logging.debug("Shell : " + cmd)
            time.sleep(param['camera']['record_movie_time'])  # 指定秒間録画する
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)  # 終了信号送信

    except Exception as e:
        mariadb.add_logdb('alarm', '写真動画の撮影に失敗しました')
        logging.error("写真・動画撮影に失敗しました")
        logging.error(traceback.format_exc())

    else:
        mariadb.add_logdb('info', '写真動画を撮影しました')
        logging.info('写真・動画撮影に成功しました')
        update_sensordb()   # センサ値更新
        

def load_parameterfile(filepass):
    """
        パラメータファイルを読み込み、JSON(dict)として返す

        Parameters
        ----------
        filspass : str
            パラメータファイルの相対パスを指定

        Returns
        -------
        parameterdata : dict
            読み込んだパラメータファイルのJSON

    """

    try:
        json_open = open(filepass, mode="r", encoding='utf-8')
        json_load = json.load(json_open)

    except Exception as e:
        logging.error(f'failed loading parameter file {filepass}')
        logging.error(e)
        return -1

    else:
        logging.debug(f'success loading parameter file {filepass}')
        return json_load


def save_parameterfile(filepass, parameter):
    """
    文字列をパラメータファイルに保存する

        Parameters
        ----------
        filspass : str
            パラメータファイルの相対パスを指定
        parameter : str
            保存する文字列

        Returns
        -------
        void

    """

    try:
        json_open = open(filepass, mode="w", encoding='utf-8')
        json_open.write(parameter)

    except Exception as e:
        mariadb.add_logdb('alarm', f'サーバ側のパラメータファイルの更新に失敗しました {filepass}')
        logging.error(f'failed saving parameter file {filepass}')
        logging.error(traceback.format_exc())

    else:
        logging.info(f'success saving parameter file {filepass}')


def set_schedulesettings():
    """
    パラメータのスケジュール設定を、Python schedule のイベントに登録する
    パラメータファイルはグローバル変数paramから読み込み
        Parameters
        ----------
        void

        Returns
        -------
        void

    """

    # scheduleのイベントを全て消去
    schedule.clear()

    try:
        # パラメータ schedule の配列要素に格納されている設定を読み出し、scheduleイベントを設定する
        for index in range(len(param['schedule'])):

            device_id = param['schedule'][index]['device_id']
            schedule_time = param['schedule'][index]['schedule_time']
            job_args = param['schedule'][index]['job_args']
            schedule_day = param['schedule'][index]['schedule_day']

            # 餌やり
            if(device_id == "feeder_no1"):
                if("sun" in schedule_day):
                    schedule.every().sunday.at(schedule_time).do(feeding, count=param['control']['feeding']['solenoid_on_count'], ontime=param[
                                   'control']['feeding']['solenoid_on_time'], interval=param['control']['feeding']['solenoid_on_intervaltime'])
                if("mon" in schedule_day):
                    schedule.every().monday.at(schedule_time).do(feeding, count=param['control']['feeding']['solenoid_on_count'], ontime=param[
                                   'control']['feeding']['solenoid_on_time'], interval=param['control']['feeding']['solenoid_on_intervaltime'])
                if("tue" in schedule_day):
                    schedule.every().tuesday.at(schedule_time).do(feeding, count=param['control']['feeding']['solenoid_on_count'], ontime=param[
                                   'control']['feeding']['solenoid_on_time'], interval=param['control']['feeding']['solenoid_on_intervaltime'])
                if("wed" in schedule_day):
                    schedule.every().wednesday.at(schedule_time).do(feeding, count=param['control']['feeding']['solenoid_on_count'], ontime=param[
                                   'control']['feeding']['solenoid_on_time'], interval=param['control']['feeding']['solenoid_on_intervaltime'])
                if("thu" in schedule_day):
                    schedule.every().thursday.at(schedule_time).do(feeding, count=param['control']['feeding']['solenoid_on_count'], ontime=param[
                                   'control']['feeding']['solenoid_on_time'], interval=param['control']['feeding']['solenoid_on_intervaltime'])
                if("fri" in schedule_day):
                    schedule.every().friday.at(schedule_time).do(feeding, count=param['control']['feeding']['solenoid_on_count'], ontime=param[
                                   'control']['feeding']['solenoid_on_time'], interval=param['control']['feeding']['solenoid_on_intervaltime'])
                if("sat" in schedule_day):
                    schedule.every().saturday.at(schedule_time).do(feeding, count=param['control']['feeding']['solenoid_on_count'], ontime=param[
                                   'control']['feeding']['solenoid_on_time'], interval=param['control']['feeding']['solenoid_on_intervaltime'])

            # 写真・動画撮影
            elif(device_id == "picmovie_no1"):
                if("sun" in schedule_day):
                    schedule.every().sunday.at(schedule_time).do(take_picmovie, movieflag=1)
                if("mon" in schedule_day):
                    schedule.every().monday.at(schedule_time).do(take_picmovie, movieflag=1)
                if("tue" in schedule_day):
                    schedule.every().tuesday.at(schedule_time).do(take_picmovie, movieflag=1)
                if("wed" in schedule_day):
                    schedule.every().wednesday.at(schedule_time).do(take_picmovie, movieflag=1)
                if("thu" in schedule_day):
                    schedule.every().thursday.at(schedule_time).do(take_picmovie, movieflag=1)
                if("fri" in schedule_day):
                    schedule.every().friday.at(schedule_time).do(take_picmovie, movieflag=1)
                if("sat" in schedule_day):
                    schedule.every().saturday.at(schedule_time).do(take_picmovie, movieflag=1)

            # AC100V制御
            else:
                # port番号抽出
                args_port = int(device_id[9])
                # ON/OFF抽出
                if(job_args == "OFF"):
                    args_b = False
                elif(job_args == "ON"):
                    args_b = True
                else:
                    raise Exception("定義されていないjob_argsの値を検知しました")

                if("sun" in schedule_day):
                    schedule.every().sunday.at(schedule_time).do(
                        set_ac100v, port=args_port, b=args_b)
                if("mon" in schedule_day):
                    schedule.every().monday.at(schedule_time).do(
                        set_ac100v, port=args_port, b=args_b)
                if("tue" in schedule_day):
                    schedule.every().tuesday.at(schedule_time).do(
                        set_ac100v, port=args_port, b=args_b)
                if("wed" in schedule_day):
                    schedule.every().wednesday.at(schedule_time).do(
                        set_ac100v, port=args_port, b=args_b)
                if("thu" in schedule_day):
                    schedule.every().thursday.at(schedule_time).do(
                        set_ac100v, port=args_port, b=args_b)
                if("fri" in schedule_day):
                    schedule.every().friday.at(schedule_time).do(
                        set_ac100v, port=args_port, b=args_b)
                if("sat" in schedule_day):
                    schedule.every().saturday.at(schedule_time).do(
                        set_ac100v, port=args_port, b=args_b)

    except Exception as e:
        mariadb.add_logdb('alarm', 'schduleの設定に失敗しました')
        logging.error("schduleの設定に失敗しました")
        logging.error(traceback.format_exc())

    else:
        # logging.debug(schedule.get_jobs())
        logging.info('schduleの設定を更新しました')


def convert_unsupported_jsonformat(o):
    """
    jsonで扱うことのできないデータ型を変換する
    ・datetime型　→　string型
    ・Decimal.decimal型　→　float型

        Parameters
        ----------
        o : 

        Returns
        -------
        変換後のデータ

    """
    # Decimal.decimal型　→　float型
    if isinstance(o, decimal.Decimal):
        return float(o)
    # datetime型　→　string型(ISO8601準拠)
    if isinstance(o, datetime.datetime):
        return o.isoformat(' ')  # 日付と時刻の間はスペース

    logging.debug(repr(o) + " is not JSON serializable")




async def websocket_routine(websocket, path):
    """
    async Websocket 非同期処理

        ----------
        websocket : obj

        Returns
        -------
        void

    """


    async for message in websocket:

        # 受信データをJSONに変換する
        try:
            logging.debug(f"websocket recv > {message}")
            message = json.loads(message)
            messagetype = message.get('messagetype')
            # 送信するJSONの変数
            tempdict = {} 
            dt_now = datetime.datetime.now() # 現在時刻を取得 
            tempstr = str(dt_now.month) + "月" + str(dt_now.day) + "日  " + str(dt_now.hour) + ":" + str(dt_now.minute) + ":" + str(dt_now.second)
            tempdict.setdefault("datetime", tempstr) # 現在時刻を格納 MM/DD hh:mm:ss

            # サーバのパラメータファイルをJSON文字列に変換しクライアントに送信する
            if(messagetype == "get_parameter"):
                logging.info("websocket recv > get_parameter")

                tempdict.setdefault("messagetype", "get_parameter")
                tempdict.setdefault(
                    "args", load_parameterfile(PARAMETER_FILEPASS))

                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                # logging.debug("websocket send : " + sendJson)
                await websocket.send(sendJson)

            # sensorDBの最新rowをJSON文字列に変換しクライアントに送信する
            elif(messagetype == "get_sensordb"):
                logging.info("websocket recv > get_sensordb")

                (status, dictdata) = mariadb.get_sensorDB()  # dictdataはlist型　dictdata[0]...はdict型
                tempdict.setdefault("messagetype", "get_sensordb")
                tempdict.setdefault("args", dictdata)

                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                # logging.debug("websocket send > " + sendJson)
                await websocket.send(sendJson)

            # sensorDBから特定センサのデータを指定された期間取得する。JSON文字列に変換しクライアントに送信する
            elif(messagetype == "get_dataview"):
                logging.info("websocket recv > get_dataview")

                dictdata = mariadb.get_dataview(message.get('args'))  # dictdataはlist型　dictdata[0]...はdict型
                tempdict.setdefault("messagetype", "get_dataview")
                tempdict.setdefault("args", dictdata)

                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                # logging.debug("websocket send > " + sendJson)
                await websocket.send(sendJson)

            # logDBをJSON文字列に変換しクライアントに送信する
            elif(messagetype == "get_logdb"):
                logging.info("websocket recv > get_logdb")

                # logDBからログ情報取得
                tempdict["messagetype"] = "get_logdb"
                dictdata = mariadb.get_logdb(message.get('args'))
                tempdict.setdefault("args", dictdata) 
                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                # logging.debug("websocket send > " + sendJson)
                await websocket.send(sendJson)

            # cameraDBをJSON文字列に変換しクライアントに送信する
            elif(messagetype == "get_cameradb"):
                logging.info(f"websocket recv > get_cameradb")

                # logDBからログ情報取得
                tempdict["messagetype"] = "get_cameradb"
                dictdata = mariadb.get_cameradb(message.get('args'))
                tempdict.setdefault("args", dictdata) 
                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                # logging.debug("websocket send > " + sendJson)
                await websocket.send(sendJson)

            # 受信したパラメータ(JSON文字列)を、サーバのパラメータファイルに上書きする
            elif(messagetype == "set_parameter"):
                logging.info("websocket recv > set_parameter")

                # argsにパラメータのobjectが格納されているため、抽出して文字列に変換し、ファイルに保存する
                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                tempdict = message.get('args')
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                save_parameterfile(PARAMETER_FILEPASS, sendJson)

                # パラメータファイルを再読み込み、グローバル変数に上書き
                global param
                param = load_parameterfile(PARAMETER_FILEPASS)
                # scheduleイベントを更新
                set_schedulesettings()

                mariadb.add_logdb('info', '設定を更新しました')

                # クライアントにサーバ処理完了メッセージを送信する
                tempdict.setdefault("messagetype", "ack")
                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                # logging.debug("websocket send > " + sendJson)
                await websocket.send(sendJson)

            # マニュアル操作要求
            elif(messagetype == "control"):
                logging.info("websocket recv > control")

                args = message.get('args')
                device_id = args.get('device_id')
                operation = args.get('operation')

                if(device_id == "feeder_no1"):
                    feeding(param['control']['feeding']['solenoid_on_count'], param['control']['feeding']
                            ['solenoid_on_time'], param['control']['feeding']['solenoid_on_intervaltime'])
                elif(device_id == "ac100v_no1"):
                    set_ac100v(1, operation)
                elif(device_id == "ac100v_no2"):
                    set_ac100v(2, operation)
                elif(device_id == "ac100v_no3"):
                    set_ac100v(3, operation)
                elif(device_id == "ac100v_no4"):
                    set_ac100v(4, operation)
                elif(device_id == "ac100v_no5"):
                    set_ac100v(5, operation)
                elif(device_id == "ac100v_no6"):
                    set_ac100v(6, operation)
                elif(device_id == "camera_live_startstop"):
                    if(operation == "1"):
                        start_hls_livestream()
                        # 指定時間後にlive配信停止させるスレッドを登録
                        thread1=threading.Timer((60*param['camera']['livestream_maxtime']),stop_hls_livestream)
                        thread1.start()
                    elif(operation == "0"):
                        stop_hls_livestream()
                elif(device_id == "camera_take_picmovie"):
                    take_picmovie(1)
                else:
                    logging.error("unknown device_id")

                # クライアントに画面更新要求を送信する
                tempdict = {}
                tempdict.setdefault("messagetype", "ack")
                # dict型をstr型(JSON文字列)に変換、インデント2、Unicode文字化け対応、コールバック関数あり
                sendJson = json.dumps(
                    tempdict, indent=2, ensure_ascii=False, default=convert_unsupported_jsonformat)
                # logging.debug("websocket send > " + sendJson)
                await websocket.send(sendJson)

            # 受信したパラメータ(JSON文字列)を、サーバのパラメータファイルに上書きする
            else:
                logging.error("websocket recv > unkwoun messagetype")


        # JSONに変換できなかった場合のエラー
        except json.JSONDecodeError as e:
            mariadb.add_logdb('alarm', 'サーバ側で受信したデータが不正な形式です(JSON形式でない)')
            logging.error("recieve data is not json format")
            logging.error(traceback.format_exc())
            await traceback.print_exc()

        # それ以外のエラー
        except Exception as e:
            mariadb.add_logdb('alarm', 'サーバ側で受信データ処理中にエラーが発生しました')
            logging.error("An error occurred in receiving data processing ")
            logging.error(traceback.format_exc())
            await traceback.print_exc()


async def main_routine():
    """
    async メインルーチン

        ----------
        void

        Returns
        -------
        void

    """


    while True:

        try:
            # センサ値更新
            update_sensordb()

            # 1秒毎に schedule タスク実行確認
            # パラメータで指定された分数待ち、センサ値更新する
            for i in range(param['control']['update_sensordb_interval'] * 60):
                schedule.run_pending()
                await asyncio.sleep(1)

        except Exception as e:
            mariadb.add_logdb('alarm', 'サーバでエラーが発生しました')
            logging.error("An error occurred in main_routine")
            logging.error(traceback.format_exc())



# --------------------------------------------------------------------------------------
# main---------------------------------------------------------------------------
# --------------------------------------------------------------------------------------

# ログ設定ファイルからログ設定を読み込み
logging.config.fileConfig('log/logging.conf')
logger = logging.getLogger()
logging.info('main.py start')
print("sys.version = " + sys.version)

# 自作モジュールのクラス MariaDBControl をインスタンス化する
mariadb = sqlcont.MariaDBControl()
mariadb.add_logdb('info', 'サーバ側のプログラムを開始しました')

# 自作モジュールのクラス GpioControl をインスタンス化
pio = picont.GpioControl()

# パラメータファイル読み込み　グローバル変数に格納
param = load_parameterfile(PARAMETER_FILEPASS)

# scheduleイベントを設定
set_schedulesettings()

# asyncio設定
# websocket受信処理と、定期センサ更新処理を並列で処理させる
loop = asyncio.get_event_loop()
gather = asyncio.wait({
    main_routine(),
    websockets.serve(websocket_routine, "192.168.1.23", 3300)
})
loop.run_until_complete(gather)
