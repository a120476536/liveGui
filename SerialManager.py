import serial
import threading
import queue
import time
import logging
logging.basicConfig(
    level=logging.INFO,  # 显示 INFO 及以上级别日志
    format='%(asctime)s [%(levelname)s] %(message)s'
)
class SerialManager:
    def __init__(self, port='COM6', baudrate=19200, timeout=1, interval=0.2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.interval = interval
        self._running = True
        self._cmd_queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # ---------- 连接 / 关闭 ----------
    def connect(self, port=None, baudrate=None):
        if port:
            self.port = port
        if baudrate:
            self.baudrate = baudrate

        if self.ser and self.ser.is_open:
            self.ser.close()

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            logging.info(f"串口 {self.port} 已打开")
            return True
        except Exception as e:
            logging.error(f"串口连接失败: {e}")
            self.ser = None
            return False

    def close(self):
        self._running = False
        self._thread.join(timeout=1)
        if self.ser and self.ser.is_open:
            self.ser.close()
        logging.info("串口已关闭")

    # ---------- 工具：异或校验 ----------
    @staticmethod
    def _with_xor(hex_str: str) -> bytes:
        """
        输入: 16 进制字符串，如 'A101'
        输出: bytes，末尾带 1 字节异或校验
        """
        data = bytes.fromhex(hex_str.replace(" ", ""))
        checksum = 0
        for b in data:
            checksum ^= b
        return data + bytes([checksum])

    # ---------- 对外发送 ----------
    def send_command(self, hex_cmd: str):
        """
        带校验后入队，由线程安全发送
        """
        frame = self._with_xor(hex_cmd)
        self._cmd_queue.put(frame.hex().upper())   # 队列里仍用 hex 字符串，方便日志

    # ---------- 后台线程 ----------
    def _worker(self):
        while self._running:
            try:
                frame_hex = self._cmd_queue.get(timeout=0.1)
                if self.ser and self.ser.is_open:
                    frame_bytes = bytes.fromhex(frame_hex)
                    self.ser.write(frame_bytes)
                    logging.info(f"TX: {frame_bytes.hex().upper()}")
                    time.sleep(self.interval)
            except queue.Empty:
                pass

            # 读回显
            if self.ser and self.ser.is_open and self.ser.in_waiting:
                rx = self.ser.read(self.ser.in_waiting)
                logging.info(f"RX: {rx.hex().upper()}")

    # ---------- 状态 ----------
    def is_open(self):
        return self.ser and self.ser.is_open


# 全局单例
serial_manager = SerialManager(interval=0.5)