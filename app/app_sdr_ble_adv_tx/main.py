import threading
import sys
import time
import numpy as np
import binascii
import signal
import argparse
import zmq
import struct
from app_beacon_gen import app_beacon_gen

#from grc_hackrf.gr_ble_adv_tx import gr_ble_adv_tx as gr_block
from grc_plutosdr.gr_ble_adv_tx import gr_ble_adv_tx as gr_block
#from grc_zmq.gr_ble_adv_tx import gr_ble_adv_tx as gr_block

sys.path.append('../../bsp')
import bsp_zmq
import bsp_system

###############################################################
# BLE 广播信道(37/38/39)与对应中心频率
#   ch37 -> 2402 MHz
#   ch38 -> 2426 MHz
#   ch39 -> 2480 MHz
BLE_ADV_CHANNELS = [37, 38, 39]
BLE_ADV_CHANNEL_FREQ = {
    37: 2402000000,
    38: 2426000000,
    39: 2480000000,
}


def parse_args():
    parser = argparse.ArgumentParser(description='SDR BLE 广播: 37/38/39 信道轮流广播, 功率可调')
    parser.add_argument('--gain', type=float, default=None,
                        help='发射增益/功率(dB, 范围与平台有关, 如 plutosdr 0~89), 不指定则用平台默认值')
    parser.add_argument('--interval', type=float, default=1.0,
                        help='每个信道的广播时长(秒), 默认1.0')
    parser.add_argument('--channel', type=int, default=-1,
                        help='固定只在指定信道广播(37/38/39), 默认-1表示37/38/39轮流广播')
    return parser.parse_args()


args = parse_args()

# Initialize Gnu Radio
gr_block = gr_block()
gr_block.start()

# 设置发射功率/增益
tx_gain = args.gain if args.gain is not None else gr_block.get_tx_gain()
gr_block.set_tx_gain(tx_gain)

zmq1 = bsp_zmq.bsp_zmq("tcp://127.0.0.1:55556", "PUB")
try:
    start_time = time.time()
    interval = args.interval
    count = 0
    
    packed_data = b''
    while 1<2:
        current_time = time.time()
        if count == 0 or current_time - start_time >= interval:
            mac = [1,2,3,4,5,6]
            adv_name = f"PK's SDR {count}"
            adv_datas = [len(adv_name) + 1, 0x09] + [ord(char) for char in adv_name]
            # 选择广播信道: 固定信道 或 37->38->39 轮流
            if args.channel in BLE_ADV_CHANNELS:
                channel = args.channel
            else:
                channel = BLE_ADV_CHANNELS[count % len(BLE_ADV_CHANNELS)]

            # 将 SDR 发射频率切换到当前信道的中心频率
            tx_freq = BLE_ADV_CHANNEL_FREQ[channel]
            gr_block.set_tx_freq(tx_freq)
            ll_datas_normalization_sample = app_beacon_gen(mac, adv_datas, channel)

            packed_data = b''
            for data in ll_datas_normalization_sample:
                packed_data += struct.pack("f", data)


            print(f'[BLE ADV] channel={channel} freq={tx_freq}Hz gain={tx_gain}')
            start_time = current_time
            count = count + 1
        

        zmq1.send(packed_data)

except KeyboardInterrupt:
    gr_block.stop()
    gr_block.wait()
    print("safe exit")

