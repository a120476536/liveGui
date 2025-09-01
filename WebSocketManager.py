import asyncio
import websockets
import logging
import socket
from PyQt5.QtCore import QObject, pyqtSignal
from SerialManager import serial_manager  
import os, json, requests,sys
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
# 获取当前程序目录
if getattr(sys, 'frozen', False):
    # 打包后的可执行文件运行
    base_dir = os.path.dirname(sys.executable)
else:
    # 开发环境中运行
    base_dir = os.path.dirname(__file__)
    
# 读取锁板控制数据 start
def cfg_path():
    """返回 lock_cfg.json 的绝对路径（兼容开发/打包）"""
    # if getattr(sys, 'frozen', False):
    #     # 打包后运行
    #     return os.path.join(os.path.dirname(sys.executable), "lock_cfg.json")
    # else:
    #     # 开发环境
    #     return os.path.join(os.path.dirname(__file__), "lock_cfg.json")
    lock_cfg_path = os.path.join(base_dir, "data")
    os.makedirs(lock_cfg_path, exist_ok=True)  # 如果不存在就创建
    lock_cfg_file = os.path.join(lock_cfg_path, "lock_cfg.json")
    return lock_cfg_file
def load_cfg():
        """第一次打开时读取 json"""
        try:
            with open(cfg_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"count": 0, "list": []}
      
class WebSocketManager(QObject):
    message_received = pyqtSignal(str) # 消息信号
    gift_list_received = pyqtSignal(dict)  #礼物对象信号
    chat_gift_received = pyqtSignal(dict) # websocket  http 接收后 对象 发送到 liveMain
    
    def __init__(self, port=8765):
        super().__init__()
        self.port = port
        self.ip = self.get_local_ip()
        self.server = None
        self.connections = set()
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
        self.data = {}

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip
    def getGiftList(self,gifList): 
        #https://live.kuaishou.com/live_api/emoji/allgifts 这个是全礼物图标
        # headers = {
        #     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        #     "Accept-Encoding": "gzip, deflate, br",
        #     "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        #     "Cache-Control": "max-age=0",
        #     "Connection": "keep-alive",
        #     "Cookie": "clientid=3; did=web_6173d0f93508d03325bae8db40b91428",
        #     "Host": "live.kuaishou.com",
        #     "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
        #     "Sec-Ch-Ua-Mobile": "?0",
        #     "Sec-Ch-Ua-Platform": '"Windows"',
        #     "Sec-Fetch-Dest": "document",
        #     "Sec-Fetch-Mode": "navigate",
        #     "Sec-Fetch-Site": "none",
        #     "Sec-Fetch-User": "?1",
        #     "Upgrade-Insecure-Requests": "1",
        #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        # }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        }
        try:
            response = requests.get(gifList,headers=headers, timeout=8)
            response.raise_for_status()          # 抛异常给外层统一处理
            # 1. 接口整体是否返回有效数据
            response = response.json()
            self.data = response
            # logging.info(f'全礼物信息: {self.data}')
            self.gift_list_received.emit(response)   # <── 这里把数据广播出去
        except requests.exceptions.Timeout:
            logging.error("获取礼物数据超时")
            self.message_received.emit("websocket 获取礼物数据超时")
            self.data = {}
        except requests.exceptions.ConnectionError:
            logging.error("websocket 获取礼物数据时连接失败")
            self.message_received.emit(f"websocket 获取礼物数据时连接失败")
            self.data = {}
        except requests.exceptions.HTTPError as e:
            logging.error(f"websocket HTTP错误: {e}")
            self.message_received.emit(f"websocket HTTP错误:{e}")
            self.data = {}
        except ValueError:  # JSON解析失败
            logging.error("websocket 礼物数据JSON解析失败")
            self.message_received.emit("websocket 礼物数据JSON解析失败")
            self.data = {}
        except Exception as e:
            logging.error(f"websocket 获取礼物数据时发生未知错误: {e}")
            self.message_received.emit(f"websocket 获取礼物数据时发生未知错误: {e}")
            self.data = {}
    def checkGift(self,gifName:str):
        lockDatas = load_cfg()  
        if isinstance(lockDatas, dict) and 'list' in lockDatas:
            for lockItem in lockDatas['list']:
                if isinstance(lockItem, dict) and (lockItem.get('giftName') == gifName or lockItem.get('giftName') in gifName):
                    return lockItem
        return None
    def getSetGifts(self):
        lockDatas = load_cfg()  
        return lockDatas
    # 执行硬件处理
    def sendCmd(self,cmd:str):
        if serial_manager.is_open():
            serial_manager.send_command(cmd)
        else:
            logging.warning(f"串口未连接,请检查!")
    # ---------- 关键：带 debug 的 handler ----------
    async def handler(self, websocket):
        peer = websocket.remote_address
        logging.info(f"客户端已连接: {peer}")
        self.connections.add(websocket)
        self.message_received.emit(f"客户端已连接: {peer}")

        try:
            # await websocket.pong()
            async for raw in websocket:
                logging.info(f"原数据来自 {peer}: {raw!r}")
                data = json.loads(raw)   # 两次解析
                logging.info(f"解析后来自 {peer}: {data}")
                # self.message_received.emit(f"{peer}")
                self.chat_gift_received.emit(data)
                raw = raw.strip('"')
                # logging.info(f"输出tag 收到消息: {raw}")
                allSetGifts = self.getSetGifts()
                if allSetGifts["count"] == 0 or not allSetGifts["list"]:
                    self.message_received.emit(f"请配置控制器礼物数据")
                    return
                # 快手直播
                # 多路 礼物控制  每一路均根据实际配置礼物控制是否启动
                if "快手" in data['from']:
                    if data['source'] == "礼物":
                        gifName = data['giftName'].replace("送", "")
                        lockItem = self.checkGift(gifName)
                        if lockItem:
                            self.message_received.emit(f"{data['from']}{data['nickName']}赠送：{gifName}---预备：砰……")
                            # serial_manager.send_command(lockItem['cmd'])
                            self.sendCmd(lockItem['cmd'])
                        else:
                            logging.warning(f"未找到礼物配置：{gifName}")
                            self.message_received.emit(f"{data['from']}{data['nickName']}赠送：{gifName}---未设置礼物不执行砰……")
                    if data['source'] == "聊天":
                        if data["msg"]:
                            if '给我玩一次,看我6不6' in data["msg"]:
                                self.message_received.emit(f"{data['from']}{data['nickName']}赠送：{gifName}---未设置礼物不执行砰……")
                                # serial_manager.send_command(lockItem['cmd'])
                                self.sendCmd(lockItem['cmd'])
                # 抖音得用接口同步了 websocket 被限制的狠死
                # if '抖音' in data['from']:
                #     if data['source'] == "礼物":
                #         gifName = data['giftName'].replace("送", "")
                #         lockItem = self.checkGift(gifName)
                #         self.message_received.emit(f"观众赠送礼物：{gifName}---预备：砰……")
                #         serial_manager.send_command(lockItem['cmd']) 
                #     if data['source'] == "聊天":
                #         if '给我玩一次,看我6不6' in data["msg"]:
                #             self.message_received.emit(f"观众发送给我玩一次触发关键字：---预备：砰……")
                #             serial_manager.send_command(lockItem['cmd'])         

        except websockets.exceptions.ConnectionClosed as e:
            logging.warning(f"客户端 {peer} 断开: {e.code} {e.reason}")
        except Exception as e:
            logging.exception(f"handler 异常 {peer}")
        finally:
            self.connections.discard(websocket)
            logging.info(f"客户端已断开: {peer}")

    async def start(self):
        if not self.server:
            self.server = await websockets.serve(
                self.handler,
                "0.0.0.0",
                self.port,
                ping_interval=None,      # 禁用库层 ping，我们自己控制
                ping_timeout=None
            )
            msg = f"WebSocket服务启动: ws://{self.ip}:{self.port}"
            logging.info(msg)
            self.message_received.emit(msg)

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            logging.info("WebSocket服务已停止")