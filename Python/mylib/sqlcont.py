import datetime
from os import name
import traceback
import logging.config

import pymysql.cursors


class MariaDBControl:

    def __init__(self):
        # インスタンスされるときにmariaDBにログインしておく
        self.connection = self.login()


    def login(self):
        """
            データベース(mariaDB)にログインする

            Parameters
            ----------
            void

            Returns
            -------
            connection
                pymysqlコネクション成功後　オブジェクト
        """
        try:
            connection = pymysql.connect(host='localhost', user='tapstar', password='mio3297',
                                         db='sakanaview2', charset='utf8', cursorclass=pymysql.cursors.DictCursor)

        except Exception as e:
            logging.error('failed to login to mariaDB databases')
            logging.error(e)
            traceback.print_exc()
            return -1

        else:
            logging.info('successed in login to mariaDB databases')
            return connection


    def add_logdb(self, logtype, logtext):
        """
            ログ種別およびログ文字列をlogDBに格納する

            Parameters
            ----------
            logType : str  
                ログの種類 ("info", "warning", "alarm")
            logText : str
                ログの内容(最大96文字)

            Returns
            -------
            Void

        """

        try:
            with self.connection.cursor() as cursor:
                query = (
                    f"insert into logDB (logtype,logtext) values('{logtype}','{logtext}')")
                logging.debug(f"mySQL query : {query}")
                cursor.execute(query)
                self.connection.commit()

        except Exception as e:
            logging.error('failed to operate logDB')
            logging.error(e)
            traceback.print_exc()

        else:
            logging.debug('successed in operating logDB')


    def get_logdb(self, args):
        """
            logDBから指定の条件でログ情報を読み出す

            Parameters
            ----------
            args : object
                entries : 取得row数
                filter : logtypeのフィルタ条件
                    iwa - 全て
                    wa - warning + alarm
                    a - alarm

            Returns
            -------
            dictdata : dict
                logDBから読み取ったデータをdict型に整形したもの
                dictdata{
                    datetimenow:[xxx,xxx,xxx,xxx]   list
                    logtype:[xxx,xxx,xxx,xxx]   list
                    logtext:[xxx,xxx,xxx,xxx]   list
                }

        """

        try:
            with self.connection.cursor() as cursor:

                # filterによりwhere文を生成
                if(args['filter'] == "iwa"):
                    wheretext = ""
                elif(args['filter'] == "wa"):
                    wheretext = "where logtype in ('warning','alarm')"
                elif(args['filter'] == "a"):
                    wheretext = "where logtype in ('alarm')"

                query = (
                    f"select * from logDB {wheretext} order by num desc limit {args['entries']}")
                logging.debug(f"mySQL query : {query}")
                cursor.execute(query)
                self.connection.commit()
                # データベースのrowがlist型配列、中身がdict型として取得される
                all_data = cursor.fetchall()
                # 各カラムの値をlist配列に整形し、dictのキー文字列のオーバーヘッドをなくす
                datetimenow = []
                logtype = []
                logtext = []
                dictdata = {}
                for i in range(len(all_data)):
                    datetimenow.append(all_data[i]["datetimenow"])
                    logtype.append(all_data[i]["logtype"])
                    logtext.append(all_data[i]["logtext"])
                dictdata["datetimenow"] = datetimenow
                dictdata["logtype"] = logtype
                dictdata["logtext"] = logtext

        except Exception as e:
            logging.error('Failed to operate database logDB')
            logging.error(e)
            traceback.print_exc()
            return -1

        else:
            logging.debug('Successed in operating database logDB')
            return dictdata


    def get_cameradb(self, args):
        """
            cametaDBから指定の条件でログ情報を読み出す

            Parameters
            ----------
            args : object
                entries : 取得row数

            Returns
            -------
            dictdata : dict
                cameraDBから読み取ったデータをdict型に整形したもの
                dictdata{
                    datetimenow:[xxx,xxx,xxx,xxx]   list
                    filename:[xxx,xxx,xxx,xxx]   list
                }

        """

        try:
            with self.connection.cursor() as cursor:

                query = (f"select * from cameraDB order by num desc limit {args['entries']}")
                logging.debug(f"mySQL query : {query}")
                cursor.execute(query)
                self.connection.commit()
                # データベースのrowがlist型配列、中身がdict型として取得される
                all_data = cursor.fetchall()
                # 各カラムの値をlist配列に整形し、dictのキー文字列のオーバーヘッドをなくす
                datetimenow = []
                filename = []
                dictdata = {}
                for i in range(len(all_data)):
                    datetimenow.append(all_data[i]["datetimenow"])
                    filename.append(all_data[i]["filename"])
                dictdata["datetimenow"] = datetimenow
                dictdata["filename"] = filename

        except Exception as e:
            logging.error('Failed to operate database cameraDB')
            logging.error(traceback.format_exc())
            return -1

        else:
            logging.debug('Successed in operating database cameraDB')
            return (dictdata)


    def add_sensordb(self, ac100v1, ac100v2, ac100v3, ac100v4, ac100v5, ac100v6, watar_temperature, air_temperature, air_humidity, food_level, status_sensor_watar, status_sensor_air, status):
        """
            センサ情報をsensorDBに格納する。

            Parameters
            ----------
            ac100v1 : tinyint

            ac100v2 : tinyint

            ac100v3 : tinyint

            ac100v4 : tinyint

            ac100v5 : tinyint

            ac100v6 : tinyint

            watar_temperature : xxxx.x[℃]

            air_temperature : xxxx.x[℃]

            air_humidity : xxxx.x[%]

            food_level : xxxx.x[%]

            status_sensor_watar : tinyint

            status_sensor_air : tinyint

            status : tinyint

            Returns
            -------
            Void

        """

        try:
            with self.connection.cursor() as cursor:
                query = (
                    f"insert into sensorDB (ac100v1,ac100v2,ac100v3,ac100v4,ac100v5,ac100v6,watar_temperature,air_temperature,air_humidity,food_level,status_sensor_watar,status_sensor_air,status) values('{ac100v1}','{ac100v2}','{ac100v3}','{ac100v4}','{ac100v5}','{ac100v6}','{watar_temperature}','{air_temperature}','{air_humidity}','{food_level}','{status_sensor_watar}','{status_sensor_air}','{status}')")
                logging.debug(f"mySQL query : {query}")
                cursor.execute(query)
                self.connection.commit()

        except Exception as e:
            logging.error('failed to operate sensorDB')
            logging.error(e)
            traceback.print_exc()
            self.add_logdb('alarm', 'Failed to operate database sensorDB')

        else:
            logging.debug('successed in operating sensorDB')


    def get_sensorDB(self):

        
        """
            sensorDBから最新レコードを取得して返す

            Parameters
            ----------
            Void

            Returns
            -------
            status : boolean
                True : 正常に処理終了
                Flase : 関数実行時にエラーが発生
            dictdata : list
                sensorDBの最新レコードのデータ(dict)

        """

        try:
            with self.connection.cursor() as cursor:

                query = "select * from sensorDB order by datetimenow desc limit 1"
                logging.debug(f"mySQL query : {query}")
                cursor.execute(query)
                self.connection.commit()
                # row毎にlist配列の要素数、rowの中身はdict型
                dictdata = cursor.fetchall()

        except Exception as e:
            logging.error('failed to operate sensorDB')
            logging.error(e)
            traceback.print_exc()
            self.add_logdb('alarm', 'センサ値の取得に失敗しました')
            return False, 0

        else:
            logging.debug('successed in operating sensorDB')
            return True, dictdata[0]


    def get_dataview(self, args):

        """
            sensorDBから特定センサのデータを指定された期間取得する

            Parameters
            ----------
            args : object
                sensorname : str
                    センサ名称
                period : str
                    データ取得期間[日]

            Returns
            -------
            dictdata : dict
                sensorDBから読み取ったデータをdict型に整形したもの
                dictdata{
                    datetimenow : list [xxx,xxx,xxx,xxx]   
                    data : list [xxx,xxx,xxx,xxx]
                    sensorname : str
                    datetime_start : str (yyyy-mm-dd hh:mm:ss)
                    datetime_end : str (yyyy-mm-dd hh:mm:ss)
                }
        """

        try:
            with self.connection.cursor() as cursor:

                sensorname = args['sensorname']
                period = args['period']

                if(period == "1"):
                    datetimePeriod = datetime.timedelta(days=1)
                elif(period == "7"):
                    datetimePeriod = datetime.timedelta(days=7)
                else:
                    datetimePeriod = datetime.timedelta()
                    logging.error('unexpected data period')

                datetimeNow = datetime.datetime.now()
                datetimeEnd = datetimeNow.strftime('%Y-%m-%d %H:%M:%S')
                datetimeStart = (datetimeNow - datetimePeriod).strftime('%Y-%m-%d %H:%M:%S')

                sql = f"SELECT datetimenow,{sensorname} FROM sensorDB WHERE datetimenow BETWEEN '{datetimeStart}' AND '{datetimeEnd}'"
                logging.debug("SQL query : " + sql)  # SQL文表示
                cursor.execute(sql)
                all_data = cursor.fetchall()  # all_dataにMYSQLから所得したデータを格納

                # 各カラムの値をlist配列に整形し、それらを内包したdictを生成する
                dictdata = {}
                datetimenow = []
                sensordata = []
                for i in range(len(all_data)):
                    datetimenow.append(all_data[i]["datetimenow"])
                    sensordata.append(all_data[i][sensorname])
                dictdata["datetimenow"] = datetimenow
                dictdata["sensordata"] = sensordata
                dictdata["sensorname"] = sensorname
                dictdata["datetime_start"] = datetimeStart
                dictdata["datetime_end"] = datetimeEnd

        except Exception as e:
            logging.error('failed to operate sensorDB (dataview)')
            logging.error(traceback.format_exc())
            self.add_logdb('alarm', '特定センサ値の取得に失敗しました')
            return -1

        else:
            logging.debug('successed in operating sensorDB (dataview)')
            return dictdata


    def number_filename_picmovie(self,movieflag):
        """
            cameraDBの最新ファイル名+1を採番し、cameraDBに追加する
            最新ファイル名+1を返す

            Parameters
            ----------
            movieflag : int
                0 or 1

            Returns
            -------
            filename : str
                ファイル名

        """

        try:
            with self.connection.cursor() as cursor:

                query = "select * from cameraDB order by datetimenow desc limit 1"
                logging.debug(f"SQL query : {query}")
                cursor.execute(query)
                self.connection.commit()
                # row毎にlist配列の要素数、rowの中身はdict型
                dictdata = cursor.fetchall()
                # 最新ファイル名+1を採番
                filename = dictdata[0]['filename'] + 1
                # 最新ファイル名+1をcameraDBに追加
                query = f"insert into cameraDB (filename,movieflag) values('{filename}',{movieflag});"
                logging.debug(f"SQL query : {query}")
                cursor.execute(query)
                self.connection.commit()

        except Exception as e:
            logging.error('failed to operate cameraDB')
            logging.error(traceback.format_exc())
            return -1

        else:
            logging.debug('successed in operating cameraDB')
            return filename



    if __name__ == '__main__':  # 本ファイルを実行すると以下が実行される（モジュールとして読み込んだ場合は実行されない）
        print("This is a module [sqlcont] ")
