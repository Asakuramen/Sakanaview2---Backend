import struct
import sys
import time
import traceback
import logging.config
import pprint
import subprocess
import threading

import pigpio
import smbus




class GpioControl:


    #定数
    GPIO_SOLENOID = 4                   # ソレノイド駆動
    GPIO_AC100V = [13,19,26,21,20,16]   # AC100V No.1から順番にGPIO番号を入力
    GPIO_LED_OPE = 17                   # CONN J1
    GPIO_LED_FAIL = 27                  # CONN J2
    GPIO_LED_MAINT = 22                 # CONN J3

    AM2320_ADDRESS = 0x5c               # AM2320 I2Cアドレス
    


    def __init__(self):

        # pigpioのインスタンスを生成しGPIOを設定する
        self.pi = pigpio.pi()

        # IO設定
        self.pi.set_mode(self.GPIO_SOLENOID, pigpio.OUTPUT)
        self.pi.set_mode(self.GPIO_LED_OPE, pigpio.OUTPUT)
        self.pi.set_mode(self.GPIO_LED_FAIL, pigpio.OUTPUT)
        self.pi.set_mode(self.GPIO_LED_MAINT, pigpio.OUTPUT)
        for i in self.GPIO_AC100V:
            self.pi.set_mode(i, pigpio.OUTPUT)

        # GPIO初期値
        self.pi.write(self.GPIO_SOLENOID, False)
        self.pi.write(self.GPIO_LED_OPE, False)
        self.pi.write(self.GPIO_LED_FAIL, False)
        self.pi.write(self.GPIO_LED_MAINT, False)
        for i in self.GPIO_AC100V:
            self.pi.write(i, False)

        # i2c通信　インスタンス生成
        self.i2c = smbus.SMBus(1)  # i2c-1

        # SPI通信　インスタンス生成
        #  (CE0, 400Kbps, mode00/mainSPI)
        self.spi_max31855 = self.pi.spi_open(0, 400000, 0)



    def get_tempAir_humAir(self, average):
        """
            AM2320から気温・湿度を取得
            xx.xの形式で返す

            Parameters
            ----------
            average : int
                センサ値平均回数

            Returns
            -------
            tempAir : double 
                気温　(xx.x [℃])
            humAir : double 
                湿度　(xx.x [%])
            status : int
                0 : 正常に計測値取得完了
                -1 : 計測値の取得に失敗
                -2 : CRC計算結果が一致しない
        """

        tempAir = 0
        humAir = 0
        status = 0

        try:
            # AM2320 wakeup command  
            self.i2c.write_i2c_block_data(self.AM2320_ADDRESS,0x00,[])
        except:
            pass

        try:
            # average回数センサ値取得する
            i = 0
            while i < average:
                i += 1
                self.i2c.write_i2c_block_data(self.AM2320_ADDRESS, 0x03, [0x00, 0x04])
                block = self.i2c.read_i2c_block_data(self.AM2320_ADDRESS, 0, 8)
                humAir += float(block[2] << 8 | block[3])/10
                tempAir += float(block[4] << 8 | block[5])/10
                crc = (block[6] << 8 | block[7])
                time.sleep(0.1)
            # 平均計算
            humAir = round(humAir/average,1) 
            tempAir = round(tempAir/average,1) 
            
        except Exception as e:
            logging.error('Raspi cant connect AM2320')
            logging.error(traceback.format_exc())
            status = -1

        else:
            logging.debug(
                f'tempAir {str(tempAir)} C, humAir {str(humAir)} %, status {status}, CRC {crc:#x}, byte {str(block)}')

        # CRC チェック
        # まだ未実装
        # status = -2

        return tempAir, humAir, status

        
        
    def get_tempWater(self, average):
        """
            K型熱電対用ADCから水温を取得
            xx.xの形式で返す

            Parameters
            ----------
            average : int
                センサ値平均回数

            Returns
            -------
            tempWater : double 
                水温　(xx.x [℃])
            status : int
                0 : 正常に計測値取得完了
                -1 : 全般エラー。通信不能、計算エラー、処理エラーなど
                -2 : OC Fault 　（熱電対が接続されてない）
                -3 : SCG Fault　（熱電対がGNDにショートしている）
                -4 : SCV Fault　（熱電対がVccにショートしている）
        """

        tempWater = 0
        tempRef = 0
        status = 0


        try:
           # average回数センサ値取得する
            i = 0
            while i < average:
                i += 1
                # MAX31855に空の4バイトを送信し、引き換えに4バイトのデータを受信する。
                (count, rx_data) = self.pi.spi_xfer(self.spi_max31855, [0x00, 0x00, 0x00, 0x00])
                # 熱電対温度計算
                tempbyte = (rx_data[0] << 8 | rx_data[1] ) >> 2
                tempWater += tempbyte * 0.25
                # 基準温度（気温）計算
                tempbyte = (rx_data[2] << 8 | rx_data[3] ) >> 4
                tempRef += tempbyte * 0.0625
                # Fault検出
                if (rx_data[3] & 0x01 != 0):
                    status = -2
                    logging.debug(f'status {status} error')
                if (rx_data[3] & 0x02 != 0):
                    status = -3
                    logging.debug(f'status {status} error')
                if (rx_data[3] & 0x04 != 0):
                    status = -4
                    logging.debug(f'status {status} error')
                if (tempWater == 0 and tempRef == 0): # 受信データが全てゼロ
                    status = -5
                    logging.debug(f'status {status} error')
                time.sleep(0.1)
                
            # 平均計算
            tempWater = round(tempWater/average,1) 
            tempRef = round(tempRef/average,1) 

        except Exception as e:
            logging.error('Raspi cant connect MAX31855')
            logging.error(traceback.format_exc())
            status = -1

        else:
            logging.debug(
                f'tempWater {str(tempWater)} C, tempRef {str(tempRef)} C, status {status}, byte [{rx_data[0]:#x}, {rx_data[1]:#x}, {rx_data[2]:#x}, {rx_data[3]:#x}]')

        return tempWater, status



    def set_ac100v_gpio(self, port, b):
        """
            AC100V制御 GPIOでソリッドステートを制御

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

        try:
            self.pi.write(self.GPIO_AC100V[port-1], b) # listのインデックスは0開始のため -1 する

            if b == 0:
                logging.info(f'AC100V No.{port} is OFF')
            elif b == 1:
                logging.info(f'AC100V No.{port} is ON')
            else:
                logging.error(f'Illigal argument b')

        except Exception as e:
            logging.error(traceback.format_exc())



    def get_ac100v_gpio(self, port):
        """
            AC100V制御　On/OFFの状態を返す

            Parameters
            ----------
            port: int
                AC100VのNo.を指定 1〜6

            Returns
            -------
            b: boolean
                True = ON、　False = OFF
        """

        try:
            b = self.pi.read(self.GPIO_AC100V[port - 1])
            return b

        except Exception as e:
            logging.error(traceback.format_exc())



    def active_solenoid(self, t):
        """
            指定時間[s]だけソレノイドを駆動する。

            Parameters
            ----------
            port:time
                ソレノイド駆動時間[s]

            Returns
            -------
            Void
        """

        self.pi.write(self.GPIO_SOLENOID, True)
        time.sleep(t)
        self.pi.write(self.GPIO_SOLENOID, False)








    if __name__ == '__main__':  # 本ファイルを実行すると以下が実行される（モジュールとして読み込んだ場合は実行されない）
        print("This is a module picont ")


        def stop_hls_livestream():

            # FFmpegのプロセスをkillするシェルを実行
            cmd = "sh ~/www/img/live/hls_streaming_stop.sh"
            subprocess.Popen(cmd, shell=True)
            print("Shell : " + cmd)


        def start_hls_livestream():

            # FFmpegでHLS開始Shellを実行
            # cmd = "timeout 30 sh ~/www/img/live/hls_streaming_start.sh"
            cmd = "sh ~/www/img/live/hls_streaming_start.sh"
            subprocess.Popen(cmd, shell=True)
            print("Shell : " + cmd)




        start_hls_livestream()

        t=threading.Timer(10,stop_hls_livestream)
        t.start()


        print("End program")
