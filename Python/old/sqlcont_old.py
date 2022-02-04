import datetime
import traceback
import logging.config

import pymysql.cursors


class MysqlControl:

    def __init__(self): 

        # ログ設定ファイルからログ設定を読み込み
        logging.config.fileConfig('logging.conf')
        self.logger = logging.getLogger()

    def loginMysql(self):
        """
            MySQLにログインし、[RCM]データベースにログインする

            Parameters
            ----------
            void

            Returns
            -------
            connection
                pymysql　コネクション成功後　オブジェクト
        """
        try:
            connection = pymysql.connect(host="localhost", user="pi", password="mio3297",\
                        db="RCM", charset="utf8", cursorclass=pymysql.cursors.DictCursor)
            return connection
        except Exception as e:
            print(e)
            traceback.print_exc()


    def add_get_picturename(self, movieflag):
        """
            cammeraDBに現在日時と採番したファイル名をINSERTする
            採番したファイル名を返す    

            Parameters
            ----------
            Void

            Returns
            -------
            filename : str
                採番したファイル名

        """

        # データベースにログインする
        connection = self.loginMysql()
        
        try:
            with connection.cursor() as cursor:

                # cameraDBで写真のファイル名となるnumを採番し、写真撮影する日時を登録する
                sql = "INSERT INTO cameraDB (type) VALUES('{}')".format(movieflag)
                cursor.execute(sql)
                connection.commit()
                self.logger.debug('SQL query : ' + cursor._executed)  # SQL文　デバック表示

                # 採番した最新numを取り出す
                sql = "SELECT num FROM cameraDB ORDER BY num DESC LIMIT 1"
                cursor.execute(sql)
                connection.commit()
                self.logger.debug('SQL query : ' + cursor._executed)  # SQL文　デバック表示
                all_data = cursor.fetchall()
                filename = all_data[0]['num']  

                return filename
                
        except Exception as e:
            print(e)
            traceback.print_exc() 
            
        finally:
            connection.close()       



    def addLogToDatabase(self, logType, logText, remarks):
        """
            受け取ったログ文字列を、ログ保存用データベース（logDB）に格納する

            Parameters
            ----------
            logType : str  
                ログの種類 ("info", "warning", "alart")
            logText : str
                ログの内容
            remarks : str
                備考欄　通常は使用しないため空欄とする

            Returns
            -------
            Void

        """

        logging.info("logDBにログ情報を追加 : " + logType + ", " + logText)

        # データベースにログインする
        connection = self.loginMysql()

        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO logDB (logType,logText,remarks) VALUES(%s,%s,%s)"
                cursor.execute(sql, (logType, logText, remarks))
                connection.commit()
                self.logger.debug('SQL query : ' + cursor._executed)  # SQL文　デバック表示
                
        except Exception as e:
            logging.error("logDBの更新に失敗")
            print(e)
            traceback.print_exc()
            
        finally:
            connection.close()



    def set_schedulerDB(self, message):
        """
            Clientから受け取ったjsonをデコードし、schedulerDBに格納する

            Parameters
            ----------
            all_data : list
                Clientから受け取ったjsonそのまま

            Returns
            -------
            status : boolean
                関数実行時にエラーが発生していればFalseを返す
                正常に処理完了していればTrueを返す

        """

        # データベースにログインする
        connection = self.loginMysql()

        try:
            with connection.cursor() as cursor:

                # 現在の設定を削除する
                sql = "DELETE FROM schedulerDB"
                self.logger.debug('SQL query : ' + sql)  # SQL文　デバック表示
                cursor.execute(sql)
                connection.commit()
                # 新しい設定をDBに格納する 仮
                sql = "INSERT INTO schedulerDB (measure_intervalTime, light, co2, coolfan, feeding, picture) VALUES('{}','{}','{}','{}','{}','{}')"\
                    .format(message.get('measure_intervalTime'), message.get('light'), message.get('co2'), message.get('coolfan'),message.get('feeding'), message.get('picture'))
                self.logger.debug('SQL query : ' + sql)  # SQL文　デバック表示
                cursor.execute(sql)
                connection.commit()


        except Exception as e:
            self.logger.debug('Error : ' + str(e))
            traceback.print_exc()
            connection.close()
            return False

        else:
            connection.close()
            return True


    def get_taskschedulerDB(self):
        """
            スケジューラ設定保存用データベース（taskschedulerDB）の設定を読み出しlist型で返す

            Parameters
            ----------
            
            Returns
            -------
            status : boolean
                関数実行時にエラーが発生していればFalseを返す
                正常に処理完了していればTrueを返す
            all_data : list
                スケジューラ設定保存用データベース（taskschedulerDB）から読み取ったデータ
        """

        # データベースにログインする
        connection = self.loginMysql()

        try:
            with connection.cursor() as cursor:

                # 最新の1件を所得する
                sql = "select * from taskSchedulerDB order by datetimenow desc limit 1"
                cursor.execute(sql)
                connection.commit()
                self.logger.debug('SQL query : ' + cursor._executed)  # SQL文　デバック表示
                all_data = cursor.fetchall()  # all_dataにMYSQLから所得したデータを格納

        except Exception as e:
            self.logger.debug('Error : ' + str(e))
            traceback.print_exc()
            connection.close()
            return (False, all_data)

        else:
            connection.close()
            return (True, all_data)



    def get_schedulerDB(self):
        """
            スケジューラ設定保存用データベース（schedulerDB）の設定を読み出しlist型で返す

            Parameters
            ----------
            
            Returns
            -------
            status : boolean
                関数実行時にエラーが発生していればFalseを返す
                正常に処理完了していればTrueを返す
            all_data : list
                スケジューラ設定保存用データベース（taskschedulerDB）から読み取ったデータ
        """

        # データベースにログインする
        connection = self.loginMysql()

        try:
            with connection.cursor() as cursor:

                # 最新の1件を所得する
                sql = "select * from schedulerDB order by datetimenow desc limit 1"
                cursor.execute(sql)
                connection.commit()
                self.logger.debug(
                    'SQL query : ' + cursor._executed)  # SQL文　デバック表示
                all_data = cursor.fetchall()  # all_dataにMYSQLから所得したデータを格納

        except Exception as e:
            self.logger.debug('Error : ' + str(e))
            traceback.print_exc()
            connection.close()
            return (False, all_data)

        else:
            connection.close()
            return (True, all_data)




    def get_sensorDB_latest1(self):
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
            all_data : list
                sensorDBの最新レコードのデータ

        """

        # データベースにログインする
        connection = self.loginMysql()

        try:
            with connection.cursor() as cursor:

                sql = "select * from sensorDB order by datetimenow desc limit 1"

                self.logger.debug('SQL query : ' + sql)  # SQL文　デバック表示
                cursor.execute(sql)
                connection.commit()
                all_data = cursor.fetchall()

        except Exception as e:
            self.logger.debug('Exception : ' + str(e))
            traceback.print_exc()
            connection.close()
            return False, 0

        else:
            connection.close()
            return True, all_data




    if __name__ == '__main__':  # 本ファイルを実行すると以下が実行される（モジュールとして読み込んだ場合は実行されない）
        print("This is a module [sqlcont] ")
