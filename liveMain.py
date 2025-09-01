import sys
import asyncio
from datetime import datetime
import re
from PyQt5.QtGui import QTextCursor, QImage, QTextImageFormat,QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMetaObject, pyqtSlot, QObject,QTimer
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, 
                            QCheckBox,
                            QLineEdit,
                            QComboBox,
                            QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from WebSocketManager import WebSocketManager
import logging
from logging.handlers import TimedRotatingFileHandler
import time
import os, json,tempfile,requests
import subprocess
import platform
from datetime import datetime, timedelta
import serial.tools.list_ports  # 获取串口列表
from io import BytesIO
from Updater import Updater
import uuid
from LockSettingsWidget import LockSettingsWidget   # 顶部
from SerialManager import serial_manager
from DyHttpServer import DyHttpServer
from tts_manager import TTSManager
from app_state import AppState
# 获取当前程序目录
if getattr(sys, 'frozen', False):
    # 打包后的可执行文件运行
    base_dir = os.path.dirname(sys.executable)
else:
    # 开发环境中运行
    base_dir = os.path.dirname(__file__)
    
# 获取串口列表 start 
def get_available_ports():
    """获取所有可用的串口列表"""
    ports = []
    try:
        for port in serial.tools.list_ports.comports():
            ports.append(f"{port.device} - {port.description}")
    except Exception as e:
        logger.error(f"liveMain 获取串口列表失败: {str(e)}")
    return ports
# 获取串口列表 end

# 激活码存取 相关 start 
# ACTIVATE_FILE = os.path.join(os.path.dirname(__file__), "activated.json")   # 就在程序同级目录
# ACTIVATE_FILE = os.path.join(os.path.dirname(sys.executable), "activated.json")   # 就在程序同级目录
# if getattr(sys, 'frozen', False):
#     # 打包后的可执行文件运行
#     ACTIVATE_FILE = os.path.join(os.path.dirname(sys.executable), "activated.json")   # 就在程序同级目录
# else:
#     # 开发环境中运行
#     ACTIVATE_FILE = os.path.join(os.path.dirname(__file__), "activated.json")
    
ACTIVATE_PATH = os.path.join(base_dir, "data")
os.makedirs(ACTIVATE_PATH, exist_ok=True)  # 如果不存在就创建
ACTIVATE_FILE = os.path.join(ACTIVATE_PATH, "actionlog.json")
def save_activate_flag(code: str):
    """把激活码和有效期写进本地文件"""
    with open(ACTIVATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "activated": True,
                "act_code": code,            # 激活码
                "expire": (datetime.today() + timedelta(days=3650)).strftime("%Y-%m-%d")        # 有效期字符串，如 "2025-12-31"
            },
            f,
            ensure_ascii=False,
            indent=2
        )
def load_activate_flag():
    """返回 (activated, act_code, expire) 三元组；文件不存在/异常则返回 False,None,None"""
    if not os.path.exists(ACTIVATE_FILE):
        return False, None, None
    try:
        with open(ACTIVATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        activated = data.get("activated", False)
        act_code = data.get("act_code")
        expire = data.get("expire")
        # 简单校验有效期
        if activated and expire and datetime.strptime(expire, "%Y-%m-%d") >= datetime.today():
            return True, act_code, expire
    except Exception:
        pass
    return False, None, None
# 激活码存取 相关 end
 
# 日志相关 start 
# 创建 logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# # 文件名模板
# # log_file =  os.path.join(os.path.dirname(__file__), "actionlog.txt")
# # 文件名模板
# log_file =  os.path.join(os.path.dirname(sys.executable), "actionlog.txt")
# if getattr(sys, 'frozen', False):
#     # 打包后的可执行文件运行
#     log_file = os.path.join(os.path.dirname(sys.executable), "actionlog.txt")
# else:
#     # 开发环境中运行
#     log_file = os.path.join(os.path.dirname(__file__), "actionlog.txt")
# 确保 log 文件夹存在
log_dir = os.path.join(base_dir, "log")
os.makedirs(log_dir, exist_ok=True)  # 如果不存在就创建

# 最终日志文件路径
log_file = os.path.join(log_dir, "actionlog.txt")
# 使用 TimedRotatingFileHandler，每 10 分钟切割一次
handler = TimedRotatingFileHandler(
    filename=log_file,
    when="M",      # 按分钟切割
    interval=10,   # 每 10 分钟
    backupCount=0, # 保留旧日志文件数量，0 表示无限
    encoding="utf-8",
    utc=False
)

# 文件名时间戳格式，例如：actionlog.txt -> actionlog.txt.2025-08-21_10-00
handler.suffix = "%Y-%m-%d_%H-%M"

# 设置日志格式
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)

logger.info(f"日志初始化:{log_file}")
# 日志相关 end 

# 获取设备唯一编码 start
def get_motherboard_serial():
    """获取设备唯一编码（支持 Windows / macOS / Linux）"""
    system = platform.system()
    try:
        if system == "Windows":
            def run_ps(command: str) -> str:
                try:
                    result = subprocess.check_output(
                        ["powershell", "-NoProfile", "-Command", command],
                        stderr=subprocess.STDOUT
                    )
                    return 'live-'+result.decode("utf-8", errors="ignore").strip()
                except Exception:
                    return ""

            # 1. 主板序列号
            serial = run_ps("(Get-CimInstance Win32_BaseBoard).SerialNumber")
            if serial:
                return serial

            # 2. BIOS 序列号
            serial = run_ps("(Get-CimInstance Win32_BIOS).SerialNumber")
            if serial:
                return serial

            # 3. CPU ID
            serial = run_ps("(Get-CimInstance Win32_Processor).ProcessorId")
            if serial:
                return serial

            # 4. 兜底：持久 GUID
            path = os.path.join(os.getenv("APPDATA") or ".", "device_guid.txt")
            if os.path.exists(path):
                with open(path, "r") as f:
                    guid = f.read().strip()
            else:
                guid = str(uuid.uuid4())
                with open(path, "w") as f:
                    f.write(guid)
            return f"GUID:{guid}"

        elif system == "Darwin":  # macOS
            serial = None

            # 1. system_profiler（优先）
            try:
                result = subprocess.check_output(
                    ["system_profiler", "SPHardwareDataType"],
                    encoding="utf-8", errors="ignore"
                )
                for line in result.splitlines():
                    if "Serial Number" in line:
                        serial = line.split(":")[-1].strip()
                        break
            except Exception:
                pass

            # 2. ioreg（备用）
            if not serial:
                try:
                    result = subprocess.check_output(
                        ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                        encoding="utf-8", errors="ignore"
                    )
                    for line in result.splitlines():
                        if "IOPlatformSerialNumber" in line:
                            serial = line.split("=")[-1].strip().strip('"')
                            break
                except Exception:
                    pass

            # 3. 兜底（uuid）
            if not serial:
                serial = str(uuid.getnode())

            return 'live-'+serial

        elif system == "Linux":
            try:
                with open("/sys/devices/virtual/dmi/id/board_serial", "r") as f:
                    serial = f.read().strip()
                return 'live-'+serial if serial else str(uuid.getnode())
            except Exception:
                return str(uuid.getnode())

        else:
            return "Unsupported OS"

    except Exception as e:
        return f"Error: {str(e)}"
# 获取设备唯一编码 end


# 异步线程类
class AsyncThread(QThread):
    error_occurred = pyqtSignal(str)
    service_stopped = pyqtSignal()
    service_started = pyqtSignal()
    thread_ready = pyqtSignal()

    def __init__(self, ws_manager):
        super().__init__()
        self.ws_manager = ws_manager
        self.loop = None
        self.task_queue = None
        self.running = False
        self.pending_task = None
        
        self.filter_flags = {
            "礼物": False,
            "点赞": False,
            "点亮": False,
            "弹幕": False
        }
        self.live_pts = {
            "抖音": False,
            "快手": False,
        }

    async def _process_tasks(self):
        while self.running:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                try:
                    await task
                    if hasattr(task, '__name__'):
                        if task.__name__ == "start":
                            self.service_started.emit()
                        elif task.__name__ == "stop":
                            self.service_stopped.emit()
                except Exception as e:
                    self.error_occurred.emit(f"任务执行错误: {str(e)}")
                finally:
                    self.task_queue.task_done()
            except asyncio.TimeoutError:
                continue

    def run(self):
        self.running = True
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.task_queue = asyncio.Queue()
            
            # 线程就绪信号
            self.thread_ready.emit()
            
            if self.pending_task:
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(self.task_queue.put(self.pending_task), loop=self.loop)
                )
                self.pending_task = None
            
            self.loop.run_until_complete(self._process_tasks())
        except Exception as e:
            self.error_occurred.emit(f"事件循环错误: {str(e)}")
        finally:
            if self.loop:
                self.loop.close()
            self.task_queue = None
            self.running = False

    def add_task(self, coroutine):
        if self.running and self.loop and self.task_queue:
            asyncio.run_coroutine_threadsafe(self.task_queue.put(coroutine), self.loop)
        elif self.running:
            self.pending_task = coroutine
        else:
            self.error_occurred.emit("无法添加任务，线程未运行")
            if asyncio.iscoroutine(coroutine):
                coroutine.close()

    def stop(self):
        if self.running:
            self.running = False
            if self.isRunning():
                self.wait()


# 主窗口类
class MyWindow(QWidget):
    # 新增一个信号用于在主线程中转发消息
    forward_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.ws_manager = WebSocketManager()
        self.async_thread = None
        self.ws_running = False
        self.deviceId = get_motherboard_serial()
        # 关键修复：连接转发信号
        self.forward_message.connect(self.append_message)
        
        # 确保WebSocketManager的信号正确连接到转发信号
        self.ws_manager.message_received.connect(self.on_message_received)
        self.ws_manager.gift_list_received.connect(self.on_gift_list_received)
        self.ws_manager.chat_gift_received.connect(self.on_chat_gift_received)
        self.code = None
        self.initUI()
        
        self.updater = Updater(self)
        
        self.http_server = DyHttpServer()
        
    
    def check_update_version(self):
       
        has_update, latest, url, log = self.updater.check_update()
        if not has_update:
            QMessageBox.warning(self,"提示", "已是最新版")   
            return

        ok = QMessageBox.question(
            self, "发现新版本",
            f"检测到新版本 {latest}\n更新内容:\n{log}\n是否立即更新？",
            QMessageBox.Yes | QMessageBox.No
        )
        if ok != QMessageBox.Yes:
            return

        # 1. 把参数写 JSON
        cfg = {
            "download_url": url,
            "target_dir": os.path.dirname(sys.executable),
            "exe_name": "liveMain.exe"
        }
        # 写 JSON
        cfg_path = os.path.join(tempfile.gettempdir(), "liveMain_update.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)

        # 直接启动同目录下的 updater.exe
        from PyQt5.QtCore import QProcess
        updater_exe = os.path.join(os.path.dirname(sys.executable), "updater.exe")
        QProcess.startDetached(updater_exe)
        QApplication.quit()
    def initUI(self):
        self.setWindowTitle("直播互动控制器")
        self.resize(800, 600)

         # 添加串口选择区域
        self.serial_label = QLabel("串口选择:")
        self.serial_combo = QComboBox()
        self.refresh_serial_btn = QPushButton("刷新")
        self.connect_serial_btn = QPushButton("连接")
        self.btn_lock_cfg = QPushButton("设置")
        

         # 串口布局
        serial_layout = QHBoxLayout()
        serial_layout.addWidget(self.serial_label)
        serial_layout.addWidget(self.serial_combo)
        serial_layout.addWidget(self.refresh_serial_btn)
        serial_layout.addWidget(self.connect_serial_btn)
        serial_layout.addWidget(self.btn_lock_cfg)
        
        # WebSocket地址显示
        self.address_label = QLabel(f"服务地址: ws://{self.ws_manager.ip}:{self.ws_manager.port}")
        self.address_label.setStyleSheet("font-size:14px; color:#2c3e50; font-weight:bold;")

        self.deviceId_lable = QLabel(f"设备码：{self.deviceId}")
        # self.action_code = QLineEdit(f"请输入设备激活码")
        self.action_code = QLineEdit()
        self.action_code.setPlaceholderText("请输入设备激活码")
        self.action_code.setStyleSheet("QTextEdit{min-height: 25px; max-height: 25px;}")
        self.activate_btn = QPushButton("激活")
        self.activate_btn.setCheckable(True)    # 支持 checked/unchecked
        self.activate_btn.setFixedWidth(60)     # 宽度固定
        
        
        # 2. 水平布局：标签-弹性空间-按钮
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(self.address_label)
        addr_layout.addWidget(self.deviceId_lable)
        addr_layout.addWidget(self.action_code)
        addr_layout.addStretch()                # 把按钮推到最右
        addr_layout.addWidget(self.activate_btn)
        
        
        # 消息显示区域
        self.msg_label = QLabel("消息记录:")
        self.show_gift  = QCheckBox("礼物")
        self.show_gift.setChecked(True)
        self.show_msg  = QCheckBox("聊天")
        self.show_msg.setChecked(True)
        self.msg_label_voice = QLabel("语音播报:")
        self.show_gift_voice  = QCheckBox("礼物")
        self.show_msg_voice  = QCheckBox("聊天")
        filter_msg_gif = QHBoxLayout()
        filter_msg_gif.addWidget(self.msg_label)
        filter_msg_gif.addWidget(self.show_gift)
        filter_msg_gif.addWidget(self.show_msg)
        filter_msg_gif.addWidget(self.msg_label_voice)
        filter_msg_gif.addWidget(self.show_gift_voice)
        filter_msg_gif.addWidget(self.show_msg_voice)
        filter_msg_gif.addStretch()                # 把按钮推到最右
        
        self.msg_display = QTextEdit()
        self.msg_display.setReadOnly(True)
        self.msg_display.setAcceptRichText(True)  # 显式启用富文本
        self.msg_display.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.msg_display.setStyleSheet("background:#f8f9fa; font-family:Consolas; font-size:12px; padding:10px;")
        self.msg_display.setMinimumHeight(350)

        # 功能按钮
        self.start_btn = QPushButton("启动服务")
        self.stop_btn = QPushButton("停止服务")
        self.start_btn.setStyleSheet("padding:10px 20px; font-size:14px;")
        self.stop_btn.setStyleSheet("padding:10px 20px; font-size:14px;")
        self.stop_btn.setEnabled(False)

        # ---------- 过滤复选框 ----------
        # self.chk_gift  = QCheckBox("礼物")
        # self.chk_gift.setChecked(True)
        # self.ws_manager.filter_flags["礼物"] = True
        # self.chk_like  = QCheckBox("点赞")
        # self.chk_light = QCheckBox("点亮")
        # self.chk_danmu = QCheckBox("弹幕")
        
        # for chk in (self.chk_gift, self.chk_like, self.chk_light, self.chk_danmu):
        #     chk.toggled.connect(self.on_filter_changed)
        
        # filter_layout = QHBoxLayout()
        # filter_layout.addWidget(QLabel("过滤条件:"))
        # filter_layout.addWidget(self.chk_gift)
        # filter_layout.addWidget(self.chk_like)
        # filter_layout.addWidget(self.chk_light)
        # filter_layout.addWidget(self.chk_danmu)
        # filter_layout.addStretch()
        
        
        # 直播平台
        self.chk_ks  = QCheckBox("快手")
        self.chk_ks.setChecked(True)
        self.ws_manager.live_pts["快手"] = True
        self.chk_dy  = QCheckBox("抖音")
        self.chk_dy.setChecked(True)
        self.ws_manager.live_pts["抖音"] = True
        
        
        self.version_label = QLabel(f"当前版本:{AppState.get_live_version()}")
        self.check_update = QPushButton("检查更新")
        
        live_pts_layout = QHBoxLayout()
        live_pts_layout.addWidget(QLabel("直播平台:"))
        live_pts_layout.addWidget(self.chk_ks)
        live_pts_layout.addWidget(self.chk_dy)
        live_pts_layout.addStretch()
        live_pts_layout.addWidget(self.version_label)
        live_pts_layout.addWidget(self.check_update)
        
        # 布局
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.setSpacing(30)

        
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)
        
        
        main_layout.addLayout(serial_layout)
        main_layout.addLayout(addr_layout)
        # main_layout.addWidget(self.address_label)
        main_layout.addLayout(btn_layout)
        # main_layout.addWidget(self.msg_label)
        main_layout.addLayout(filter_msg_gif)
        main_layout.addWidget(self.msg_display)
        main_layout.addLayout(live_pts_layout)
        # main_layout.addLayout(filter_layout)
        self.setLayout(main_layout)

        # 绑定按钮事件
        self.activate_btn.toggled.connect(self.on_activate_clicked)
        self.refresh_serial_btn.clicked.connect(self.refresh_serial_ports)
        self.connect_serial_btn.clicked.connect(self.connect_serial_port)
        self.btn_lock_cfg.clicked.connect(self.open_lock_cfg)
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        
        self.show_gift.toggled.connect(self.on_checkbox_changed)
        self.show_msg.toggled.connect(self.on_checkbox_changed)
        self.show_gift_voice.toggled.connect(self.on_checkbox_changed)
        self.chk_ks.toggled.connect(self.on_checkbox_changed)
        self.chk_dy.toggled.connect(self.on_checkbox_changed)
        self.check_update.clicked.connect(self.check_update_version)
    
        # 初始化时刷新串口列表
        self.refresh_serial_ports()
        
        # 延迟执行检测逻辑
        QTimer.singleShot(3*1000, self.check_device_status)
        
    # 通用勾选回调
    def on_checkbox_changed(self, checked):
        sender = self.sender()  # 获取触发的 QCheckBox
        if sender == self.show_gift:
            AppState.set_show_gift(checked)
            print(f"礼物勾选状态: {checked}")
        elif sender == self.show_msg:
            AppState.set_show_msg(checked)
            print(f"聊天勾选状态: {checked}")    
        elif sender == self.show_gift_voice:
            AppState.set_show_gift_voice(checked)
            print(f"礼物语音勾选状态: {checked}")
        elif sender == self.show_msg_voice:
            AppState.set_show_msg_voice(checked)
            print(f"聊天语音勾选状态: {checked}")  
        elif sender == self.chk_ks:
            AppState.set_chk_ks(checked)
            print(f"快手勾选状态: {checked}")
        elif sender == self.chk_dy:
            AppState.set_chk_dy(checked)
            print(f"抖音勾选状态: {checked}")
    def open_lock_cfg(self):
        if self.connect_serial_btn.text() == "断开":
            self.lock_cfg_win = LockSettingsWidget(self)
            self.lock_cfg_win.settings_saved.connect(self.apply_lock_cfg)  # 可选
            self.lock_cfg_win.show()   
        else:
            self.append_message("请先连接串口")
            QMessageBox.critical(self, "提示", "请先连接串口")   
    def apply_lock_cfg(self, cfg):
        # 例如把配置同步给 SerialManager 或 WebSocketManager
        print("新的锁控配置:", cfg) 
    def check_device_status(self):
        """检查设备状态，包括是否过期和加载本地存储的设备数据"""
        ok, saved_code, saved_expire = load_activate_flag()
        if ok:
            logger.info(f"liveMain 输出存储的激活码：{saved_code}")
            self.action_code.setText(saved_code)
            self.code = saved_code
    def refresh_serial_ports(self):
        """刷新串口列表"""
        self.serial_combo.clear()
        ports = get_available_ports()
        if ports:
            self.serial_combo.addItems(ports)
            self.append_message(f"发现 {len(ports)} 个可用串口,请手动连接正确COM口")
        else:
            self.append_message("未发现可用串口")

    def connect_serial_port(self):
        """连接选中的串口"""
        selected = self.serial_combo.currentText()
        if not selected:
            QMessageBox.warning(self, "提示", "请选择串口")
            return
            
        # 提取端口号（如从"COM6 - USB Serial Port"中提取"COM6"）
        port = selected.split(" - ")[0]
        
        # from SerialManager import serial_manager
        if serial_manager.connect(port):
            self.append_message(f"串口 {port} 连接成功")
            self.connect_serial_btn.setText("断开")
            self.connect_serial_btn.clicked.disconnect()
            self.connect_serial_btn.clicked.connect(self.disconnect_serial_port)
        else:
            self.append_message(f"串口 {port} 连接失败")

    def disconnect_serial_port(self):
        """断开当前串口连接"""
        # from SerialManager import serial_manager
        serial_manager.close()
        self.append_message("串口已断开")
        self.connect_serial_btn.setText("连接")
        self.connect_serial_btn.clicked.disconnect()
        self.connect_serial_btn.clicked.connect(self.connect_serial_port)

    def setActBtStatus(self,clickStatus):
        if clickStatus==0:   
            self.activate_btn.setText("激活")
            self.activate_btn.setEnabled(True)
        elif clickStatus==1:
            self.activate_btn.setText("激活中...")
            self.activate_btn.setEnabled(False)
        elif clickStatus==2:
            self.activate_btn.setText("已激活")
            self.activate_btn.setEnabled(False)
    # 点击激活按钮
    @pyqtSlot()
    def on_activate_clicked(self):
        # self.activate_btn.setEnabled(False)   # 防止连点
        # self.activate_btn.setText("激活中…")
        self.code = self.action_code.text().strip()
        if not self.code:
            QMessageBox.warning(self, "提示", "设备激活码不能为空！")
            return
        self.activate_btn.setText("已激活")
        
    @pyqtSlot(str)
    def on_message_received(self, message):
        """接收WebSocketManager的消息并转发，确保在主线程中处理"""
        # 检查当前线程是否为主线程
        if QThread.currentThread() != self.thread():
            # 如果不是主线程，通过信号转发到主线程
            self.forward_message.emit(message)
        else:
            # 如果已经是主线程，直接显示
            self.append_message(message)
    
    # 收到礼物列表后展示
    @pyqtSlot(dict)
    def on_gift_list_received(self, data: dict):
        if not data:
            self.msg_display.append("拉取失败或为空")
            return
        # 这里只简单打印
        # logging.info(f"收到礼物列表: {data}")
        # 你可以按 data["data"] 解析成表格、下拉框等
        
                

    @pyqtSlot()
    def on_filter_changed(self):
        self.ws_manager.filter_flags["礼物"]  = self.chk_gift.isChecked()
        self.ws_manager.filter_flags["点赞"]  = self.chk_like.isChecked()
        self.ws_manager.filter_flags["点亮"] = self.chk_light.isChecked()
        self.ws_manager.filter_flags["弹幕"] = self.chk_danmu.isChecked()
    @pyqtSlot()
    def on_live_pts_changed(self):
        self.ws_manager.live_pts["抖音"]  = self.chk_dy.isChecked()
        self.ws_manager.live_pts["快手"]  = self.chk_ks.isChecked()
    @pyqtSlot()
    def on_start(self):
        # if self.activate_btn.text() == "已激活":
        #     if not self.http_server.receivers(self.http_server.data_received):
        #         self.http_server.data_received.connect(self.on_data_received)
        #         self.http_server.start()
        #         self.start_btn.setEnabled(False)
        #         self.stop_btn.setEnabled(True)
        # else:
        #     self.append_message("请先激活程序")
        #     QMessageBox.critical(self, "提示", "请先激活程序")   
        if self.activate_btn.text() != "已激活":
            self.append_message("请先激活程序")
            QMessageBox.critical(self, "提示", "请先激活程序")
            return

        # 1. 先确保旧连接断开（防止重复）
        try:
            self.http_server.data_received.disconnect(self.on_data_received)
        except TypeError:
            pass  # 没连过时抛异常，忽略

        # 2. 重新连接并启动
        self.http_server.data_received.connect(self.on_data_received)
        self.http_server.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        logger.info("liveMain 网络服务已启动")
    @pyqtSlot()
    def on_stop(self):
        # if self.ws_running and self.async_thread and self.async_thread.isRunning():
            # self.async_thread.add_task(self.ws_manager.stop())
            # self.stop_btn.setEnabled(False)
            # self.append_message("正在停止WebSocket服务...")
        # self.http_server.stop()
        # self.start_btn.setEnabled(True)
        # self.stop_btn.setEnabled(False)
        # logger.info("liveMain 用户触发服务停止")
        # logger.info("liveMain 网络服务停止")
        # 1. 停止服务
        self.http_server.stop()
        # 2. 断开信号（可选，也可不断）
        try:
            self.http_server.data_received.disconnect(self.on_data_received)
        except TypeError:
            pass
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        logger.info("liveMain 网络服务已停止")
    # HTTP 服务连接 
    def on_data_received(self, data):
        self.append_message(str(data))
    @pyqtSlot()
    def on_thread_ready(self):
        self.append_message("线程已就绪，启动WebSocket服务...")
        self.async_thread.add_task(self.ws_manager.start())

   

    @pyqtSlot()
    def on_websocket_started(self):
        self.ws_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.append_message("WebSocket服务已成功启动")
        logger.info("liveMain 服务已启动")

    @pyqtSlot()
    def on_websocket_stopped(self):
        self.ws_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self.async_thread and self.async_thread.isRunning():
            self.async_thread.stop()
        self.append_message("WebSocket服务已成功停止")
        logger.info("liveMain 服务已停止")

    @pyqtSlot(str)
    def on_error(self, error_msg):
        QMessageBox.critical(self, "错误", error_msg)
        logger.error(error_msg)
        self.append_message(f"【错误】{error_msg}")
        self.ws_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self.async_thread and self.async_thread.isRunning():
            self.async_thread.stop()


    def getGiftList(self,gifList):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Cookie": "clientid=3; did=web_6173d0f93508d03325bae8db40b91428",
            "Host": "live.kuaishou.com",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        }

        response = requests.get(gifList,headers=headers, timeout=8)
        # return response.json()
        # 1. 接口整体是否返回有效数据
        response = response.json()
        self.gift_list_received.emit(response)   # <── 这里把数据广播出去
    # 对象 礼物 聊天
    @pyqtSlot(dict)
    def on_chat_gift_received(self, data: dict):
        if not data:
            self.msg_display.append("拉取失败或为空")
            return
        if isinstance(data, dict):
            logger.info(f"data['source'] == '礼物'{data['source'] == '礼物'}")
            if data['source'] == '礼物':
                if self.show_gift.isChecked():
                    logger.info(f"self.show_gift.isChecked(){self.show_gift.isChecked()}")
                    self.msg_display.append(f"{data}")
            if data['source']=='聊天':
                logger.info("data['source']=='聊天'")
                if self.show_msg.isChecked():
                    logger.info(f"self.show_msg.isChecked(){self.show_msg.isChecked()}")
                    self.msg_display.append(f"{data}")
    @pyqtSlot(str)
    def append_message(self, message):
        """确保在主线程中更新UI"""
        # 最终的UI更新确保在主线程
        if self.thread() != QThread.currentThread():
            QMetaObject.invokeMethod(self, "append_message", Qt.QueuedConnection, args=(message,))
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.msg_display.append(f"[{timestamp}] {message}")
        self.msg_display.moveCursor(self.msg_display.textCursor().End)

    def closeEvent(self, event):
        if self.async_thread and self.async_thread.isRunning():
            self.async_thread.stop()
            logger.info("liveMain 窗口关闭，线程已停止")
        for handler in logger.handlers:
            handler.close()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())
    