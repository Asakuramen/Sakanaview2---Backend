
import struct
import sys
import time
import logging.config

import pigpio
import picamera
import math
import subprocess




class GpioControl:

    #定数
    GPIO_MOTOR_INA = 26     # ステッピングモーターINA
    GIPO_MOTOR_INB = 19     # ステッピングモーターINB
    GPIO_MOTOR_STBY = 13    # ステッピングモーターVs2B スタンバイ信号
    GPIO_INPUT1 = 4         # 汎用INPUT (未使用) 
    GPIO_OUTPUT1 = 17       # AC100V制御１
    GPIO_OUTPUT2 = 27       # AC100V制御２
    GPIO_OUTPUT3 = 22       # AC100V制御３
    GPIO_LED_POWER = 23     # LED POWER
    GPIO_LED_OPE = 24       # LED OPE
    GPIO_LED_FAIL = 18      # LED FAIL

    def __init__(self):

        # ログ設定ファイルからログ設定を読み込み
        logging.config.fileConfig('logging.conf')
        self.logger = logging.getLogger()

        # pigpioのインスタンスを生成しGPIOを設定する
        self.pi = pigpio.pi()

        self.pi.set_mode(self.GPIO_MOTOR_INA, pigpio.OUTPUT)   # ステッピングモーターINA
        self.pi.set_mode(self.GIPO_MOTOR_INB, pigpio.OUTPUT)   # ステッピングモーターINB
        self.pi.set_mode(self.GPIO_MOTOR_STBY, pigpio.OUTPUT)  # ステッピングモーターVs2B スタンバイ信号
        self.pi.set_mode(self.GPIO_OUTPUT1, pigpio.OUTPUT)     # AC100V制御１
        self.pi.set_mode(self.GPIO_OUTPUT2, pigpio.OUTPUT)     # AC100V制御２
        self.pi.set_mode(self.GPIO_OUTPUT3, pigpio.OUTPUT)     # AC100V制御３
        self.pi.set_mode(self.GPIO_INPUT1, pigpio.INPUT)       #汎用input
        self.pi.set_pull_up_down(self.GPIO_INPUT1, pigpio.PUD_UP)  # pullup抵抗有効

        # GPIO初期値
        self.pi.write(self.GPIO_MOTOR_INA, False)
        self.pi.write(self.GIPO_MOTOR_INB, False)
        self.pi.write(self.GPIO_MOTOR_STBY, False)

        # SPI通信open
        # BME280 (CE0, 400Kbps, mode00/mainSPI)
        # self.bme280 = self.pi.spi_open(0, 200000, 0)
        # MCP3002 (CE1, 400Kbps, mode00/mainSPI)
        self.mcp3002 = self.pi.spi_open(1, 400000, 0)

        # # # chip_idを取得
        # # (count, rx_data) = self.pi.spi_xfer(self.bme280, [0xD0, 0x00])
        # # print('BME280 chip_id')
        # # print('BME280 rx_data[0] : ', rx_data[0])
        # # print('BME280 rx_data[1] : ', rx_data[1])

        # # BME280 setup
        # osrs_t = 1          #Temperature oversampling x 1
        # osrs_p = 1          #Pressure oversampling x 1
        # osrs_h = 1			#Humidity oversampling x 1
        # mode   = 3			#Normal mode
        # t_sb   = 5			#Tstandby 1000ms
        # filter = 0			#Filter off
        # spi3w_en = 0		#3-wire SPI Disable

        # ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
        # config_reg    = (t_sb << 5) | (filter << 2) | spi3w_en
        # ctrl_hum_reg  = osrs_h

        # self.logger.debug('ctrl_hum_reg : ' + str(ctrl_hum_reg))
        # self.logger.debug('ctrl_meas_reg : ' + str(ctrl_meas_reg))
        # self.logger.debug('config_reg : ' + str(config_reg))

        # # self.pi.spi_write(self.bme280, [0x72, ctrl_hum_reg])
        # # self.pi.spi_write(self.bme280, [0x74, ctrl_meas_reg])
        # self.pi.spi_write(self.bme280, [0x75, config_reg])

        # # (count, rx_data) = self.pi.spi_xfer(self.bme280, [0xF2, 0x00])
        # # # print('BME280 rx_data[0] : ', rx_data[0])
        # # # print('BME280 rx_data[1] : ', rx_data[1])
        # # (count, rx_data) = self.pi.spi_xfer(self.bme280, [0xF4, 0x00])
        # # print('BME280 rx_data[0] : ', rx_data[0])
        # # print('BME280 rx_data[1] : ', rx_data[1])
        # (count, rx_data) = self.pi.spi_xfer(self.bme280, [0xF5, 0x00])
        # print('BME280 rx_data[0] : ', rx_data[0])
        # print('BME280 rx_data[1] : ', rx_data[1])

        # self.pi.spi_close(self.bme280)
        # self.pi.spi_close(self.mcp3002)



        # I2C通信open
        # ADXL345設定I2C 初期化
        # MCP3425設定I2C 初期化
        # if sys.version > '3':
        #     self.buffer = memoryview
        # BUS = 1
        # ADXL345_I2C_ADDR = 0x53
        # MCP3425_I2C_ADDR = 0x68
        # self.adxl345 = self.pi.i2c_open(BUS, ADXL345_I2C_ADDR)  # ADXL345とのIC2通信のインスタンス
        # self.mcp3425 = self.pi.i2c_open(BUS, MCP3425_I2C_ADDR)  # MCP3425とのIC2通信のインスタンス

        # if self.adxl345 >= 0:  # Connected OK?
        #     # Initialise ADXL345.
        #     self.pi.i2c_write_byte_data(self.adxl345, 0x2d, 0)  # POWER_CTL reset.
        #     self.pi.i2c_write_byte_data(self.adxl345, 0x2d, 8)  # POWER_CTL measure.
        #     self.pi.i2c_write_byte_data(self.adxl345, 0x31, 0)  # DATA_FORMAT reset.
        #     self.pi.i2c_write_byte_data(self.adxl345, 0x31, 11) # DATA_FORMAT full res +/- 1
        #     # Initialise MCP3425
        #     self.pi.i2c_write_byte(self.mcp3425, 0b10011000)


        # BME280 chip_id取得


    def get_tempWater_tempAir(self):
        """
            MCP3002のAD値から水温・気温を計算する　
            xx.x[℃]の形式で返す

            Parameters
            ----------
            Void

            Returns
            -------
            tempWater : double 
                水温　(小数第２位を四捨五入済み)
            tempAir : double 
                水温　(小数第２位を四捨五入済み)
            status : boolean
                Ture : 正常に計測値取得完了
                False : 計測値の取得に失敗（センサ計測値がゼロ）
        """

        # MCP3002 データフォーマット
        #       1バイト目                |2バイト目
        #       0  1  2  3  4  5  6  7 |0  1  2  3  4  5  6  7
        # D_out X  X  X  X  X  X  B9 B8|B7 B6 B5 B4 B3 B2 B1 B0
        # D_in  X  1  1  OS MS X  X  X |X  X  X  X  X  X  X  X
        #          |  |  |  |  
        #          |  |  |  D_out 出力フォーマット　0:LSB, 1:MSB 
        #          |  |  ADチャンネル指定　0:CH0, 1:CH1
        #          |  1: シングルエンド,　 0差動
        #          1:スタートビット

        # 温度計算用パラメータ
        Rf1 = 10000
        Rf2 = 10000
        Vcc = 3.3
        B = 3380
        R0 = 10000
        T0 = 25
        ADbit = 10

        status = True

        # CH1のAD値を取得
        (count, rx_data) = self.pi.spi_xfer(self.mcp3002, [0x78, 0x00])
        # print('rx_data[0] : ', rx_data[0])
        # print('rx_data[1] : ', rx_data[1])

        # AD値を電圧値Vch0に変換
        Vch0 = (rx_data[0] * 256 + rx_data[1]) * (Vcc / (2 ** ADbit))
        # print('Vch0 : ', Vch0, ' V')

        # 電圧値がゼロの場合はセンサ計測に失敗したと判定し、status=Flase を返す
        if(Vch0 > 0.1):
            # サーミスタ抵抗値Rsを計算する
            Rs = (Rf1 / Vch0 * Vcc) - Rf1
            # print('Rs : ', Rs, ' Ω')

            # 温度Tを計算  小数第二位を四捨五入　(xx.x[℃])
            tempWater = ((1/B) * math.log((Rs/R0),math.e) + (1/(T0 + 273))) ** (-1) - 273
            tempWater = round(tempWater,1)
            # print('tempWater : ', tempWater, ' °C \n')
        else:
            self.logger.error('MCP3002 Ch1 measurement value is Zero')
            tempWater = 0
            status = False


        # CH0のAD値を取得
        (count, rx_data) = self.pi.spi_xfer(self.mcp3002, [0x68, 0x00])
        # print('rx_data[0] : ', rx_data[0])
        # print('rx_data[1] : ', rx_data[1])

        # AD値を電圧値Vch0に変換
        Vch0 = (rx_data[0] * 256 + rx_data[1]) * (Vcc / (2 ** ADbit))
        # print('Vch0 : ', Vch0, ' V')

        # 電圧値がゼロの場合はセンサ計測に失敗したと判定し、status=Flase を返す
        if(Vch0 > 0.1):
            # サーミスタ抵抗値Rsを計算する
            Rs = (Rf2 / Vch0 * Vcc) - Rf2
            # print('Rs : ', Rs, ' Ω')

            # 温度Tを計算  小数第二位を四捨五入　(xx.x[℃])
            tempAir = ((1/B) * math.log((Rs/R0),math.e) + (1/(T0 + 273))) ** (-1) - 273
            tempAir = round(tempAir,1)
            # print('tempAir : ', tempWater, ' °C \n')
        else:
            self.logger.debug('MCP3002 Ch0 measurement value is Zero')
            tempAir = 0
            status = False
            

        return tempWater, tempAir, status





    def set_ac100v(self, port, b):
        """
            AC100V制御 GPIOでソリッドステートを制御

            Parameters
            ----------
            port: int
                1 : 1番目のAC100V  ライト
                2 : 2番目のAC100V  CO2
                3 : 3番目のAC100V  ファン
            b: boolean
                True = ON、　False = OFF

            Returns
            -------
            Void
        """
        if(port == 1):
            self.pi.write(self.GPIO_OUTPUT1, b)
        elif (port == 2):
            self.pi.write(self.GPIO_OUTPUT2, b)
        elif (port == 3):
            self.pi.write(self.GPIO_OUTPUT3, b)


    def get_ac100v(self, port):
        """
            AC100V制御の状態を返す

            Parameters
            ----------
            port: int
                1 : 1番目のAC100V 
                2 : 2番目のAC100V 
                3 : 3番目のAC100V 

            Returns
            -------
            b: boolean
                True = ON、　False = OFF
        """
        if(port == 1):
            b = self.pi.read(self.GPIO_OUTPUT1)
        elif (port == 2):
            b = self.pi.read(self.GPIO_OUTPUT2)
        elif (port == 3):
            b = self.pi.read(self.GPIO_OUTPUT3)

        return b



    def rotate_motor(self, deg):
        """
            モーターを指定の角度回転させる

            Parameters
            ----------
            deg: int
                モーターの回転角度[deg]

            Returns
            -------
            Void
        """

        BaseStepDegree = 1.8  # 　ステッピングモータのステップ角
        ran = int(deg / BaseStepDegree / 4)
        sleepTime = 0.01  # パルス幅 = sleepTime * 2

        self.pi.write(self.GPIO_MOTOR_STBY, True)  # スタンバイ信号解除
        time.sleep(0.2)

        for i in range(0, ran):

            self.pi.write(self.GPIO_MOTOR_INA, True)
            time.sleep(sleepTime)

            self.pi.write(self.GIPO_MOTOR_INB, True)
            time.sleep(sleepTime)

            self.pi.write(self.GPIO_MOTOR_INA, False)
            time.sleep(sleepTime)

            self.pi.write(self.GIPO_MOTOR_INB, False)
            time.sleep(sleepTime)

        time.sleep(0.2)
        self.pi.write(self.GPIO_MOTOR_STBY, False)  # スタンバイ信号有効




    # def get_foodlevel_sensor(self):
    #     """
    #         センサ（MCP3425）からデータを所得し、えさ残量(0~100%)に換算して返す

    #         Parameters
    #         ----------
    #         Void

    #         Returns
    #         -------
    #         foodlevel : int
    #             えさ残量 0~100
    #     """
        
    #     aV = self.pi.i2c_read_word_data(self.mcp3425, 0b10011000)  # MCP3425のAD変換バイナリ所得
    #     aV = (((aV << 8) & 0xFF00) | ((aV >> 8) & 0x00FF))  # リトルエンディアンをビックエンディアンへ
    #     aV = aV * 62.5/1000000                              # 電圧値に換算(16bitモード、PGA=1、正電圧のみ(Vin-をGND接地))
    #     aV = round((aV * 50), 0)                                        # 電圧値からえさ残量に換算する (まだ仮の計算式)
    #     return  aV                                          # 



    # def get_accelerateXYZ_sensor(self):
    #     """
    #         センサ（ADXL345）からxyz軸の加速度データを所得し、返す

    #         Parameters
    #         ----------
    #         void

    #         Returns
    #         -------
    #         x : int
    #             x軸　加速度
    #         y : int
    #             y軸　加速度
    #         z : int
    #             z軸　加速度                
    #     """
    #     # ADXL345のxyz軸加速度のAD変換バイナリ所得
    #     (s, b) = self.pi.i2c_read_i2c_block_data(self.adxl345, 0x32, 6)
    #     if s >= 0:
    #         (x, y, z) = struct.unpack('<3h', self.buffer(b)) #x,y,z軸のデータを分離する（まだ仮の計算式）
    #         return x, y, z



    def take_picture(self, filepass):
        """
            カメラモジュールで写真を撮影し、指定されたファイル名で保存する

            Parameters
            ----------
            filename : str
                保存するjpg写真のファイル名

            Returns
            -------
            Void             
        """

        with picamera.PiCamera() as camera: # カメラモジュールに接続
            camera.resolution = (960, 720) # 解像度設定
            camera.start_preview()          # 
            time.sleep(2)                   # Camera warm-up time 2秒以上待つ？ by 公式
            camera.capture(filepass)        # 指定されたファイルパス、ファイル名で写真を保存
            camera.stop_preview()           # 

            # print("save a picture on {}".format(filepass))



    def take_movie(self, filepass, waittime):
        """
            カメラモジュールで指定された秒数の動画を撮影し、指定されたファイル名で保存する

            Parameters
            ----------
            filename : str
                保存するjpg写真のファイル名
            time : int
                動画を撮影する時間

            Returns
            -------
            Void             
        """

        with picamera.PiCamera() as camera:     # カメラモジュールに接続
            camera.resolution = (480,360)     # 解像度設定
            camera.start_preview()
            
            camera.start_recording(filepass, format="h264")    # 指定されたファイルパス、ファイル名で動画を保存
            time.sleep(waittime)           
            camera.stop_recording()             

            # print("save a video on {}".format(filepass))



    def close_gpio(self):
        """
            mainプログラム終了時に呼び出す関数
            ・pigpioのリソースを開放する

            Parameters
            ----------
            void

            Returns
            -------
            void
        """
        self.pi.spi_close(self.mcp3002)
        self.pi.stop() 
        self.logger.debug('Program End')

        
        

    if __name__ == '__main__':  # 本ファイルを実行すると以下が実行される（モジュールとして読み込んだ場合は実行されない）
        print("This is a module [picont] ")

        # h264をmp4に変換
        # cmd = "MP4Box -add www/img/movie/{}.h264 www/img/movie/{}.mp4".format(filename, filename)
        cmd = "ls"
        subprocess.run(cmd, shell=True)
        logging.debug("Shell : " + cmd)


