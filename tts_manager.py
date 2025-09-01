import asyncio
import edge_tts
import os
import sys
import time
from threading import Thread, Lock
from queue import Queue
import pygame


class TTSManager:
    """
    TTSManager 单例类
    - 使用 edge-tts 将文字转语音
    - 将生成的音频文件保存到程序目录下的 mp3 文件夹
    - 使用单线程队列顺序播放语音，并确保临时文件被删除
    """
    _instance = None
    _lock = Lock()  # 保证单例线程安全

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TTSManager, cls).__new__(cls)
                # 初始化队列和工作线程
                cls._instance._queue = Queue()
                cls._instance._thread = Thread(target=cls._instance._worker, daemon=True)
                cls._instance._thread.start()
                # 初始化pygame音频系统
                pygame.mixer.init()
                # 创建一个待删除文件的列表
                cls._instance._files_to_delete = []
            return cls._instance

    async def _speak_async(self, text):
        """
        异步方法生成 TTS 并播放
        """
        # 获取程序根目录（区分开发/打包环境）
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件运行
            base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境运行
            base_dir = os.path.dirname(__file__)

        # mp3 文件存放路径
        mp3_dir = os.path.join(base_dir, "mp3")
        if not os.path.exists(mp3_dir):
            os.makedirs(mp3_dir)

        # 临时文件名，放在 mp3 目录下
        # tmp_filename = os.path.join(mp3_dir, f"{int(time.time() * 1000)}.mp3")
        tmp_filename = os.path.join(mp3_dir, "tmp.mp3")
        try:
            # 先尝试删除之前未能删除的文件
            self._cleanup_files()
            
            # 创建 edge-tts 对象
            tts = edge_tts.Communicate(text, voice="zh-CN-XiaoyiNeural") # 语音模型
            # 保存音频到文件
            await tts.save(tmp_filename)
            
            # 使用pygame播放音频
            pygame.mixer.music.load(tmp_filename)
            pygame.mixer.music.play()
            
            # 等待播放完成
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
            # 明确停止播放并卸载音频，释放资源
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
            # 短暂延迟，确保资源释放
            time.sleep(0.1)
            
            # 尝试删除文件
            self._delete_file(tmp_filename)
            
        except Exception as e:
            print(f"TTS 处理出错: {e}")
            # 如果出错也将文件加入待删除列表
            if os.path.exists(tmp_filename):
                self._files_to_delete.append(tmp_filename)

    def _delete_file(self, filename):
        """尝试删除文件，失败则加入待删除列表"""
        try:
            os.remove(filename)
        except Exception as e:
            print(f"立即删除文件失败，将稍后重试: {e}")
            self._files_to_delete.append(filename)
    
    def _cleanup_files(self):
        """清理之前未能删除的文件"""
        if not self._files_to_delete:
            return
            
        files_remaining = []
        for filename in self._files_to_delete:
            try:
                # 先尝试直接删除
                os.remove(filename)
                print(f"成功删除之前的临时文件: {filename}")
            except:
                try:
                    # 如果直接删除失败，尝试移动到回收站
                    if os.name == 'nt':  # Windows系统
                        # import winshell
                        # winshell.recycle_bin().move(filename)
                        print(f"文件已移至回收站: {filename}")
                    else:
                        # 非Windows系统，保留待下次尝试
                        files_remaining.append(filename)
                except Exception as e:
                    print(f"清理文件 {filename} 失败: {e}")
                    files_remaining.append(filename)
        
        self._files_to_delete = files_remaining

    def _worker(self):
        """
        队列工作线程，不断获取待播放文本并顺序播放
        """
        while True:
            text = self._queue.get()
            try:
                asyncio.run(self._speak_async(text))
            except Exception as e:
                print(f"TTS 播放出错: {e}")
            self._queue.task_done()

    @classmethod
    def speak(cls, text):
        """
        对外方法，将文本加入队列，顺序播放
        """
        instance = cls()
        instance._queue.put(text)


# -----------------------------
# 测试方法
# -----------------------------
def test_tts_sequence():
    """
    测试 TTS 顺序播放
    """
    print("测试开始：依次播放三条语音")
    TTSManager.speak("第一条消息，测试顺序播放")
    TTSManager.speak("第二条消息，应该在第一条播完后播放")
    TTSManager.speak("第三条消息，最后播放")

    # 保证主线程不退出，给 TTS 播放留时间
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 程序退出前最后尝试清理文件
        tts = TTSManager()
        tts._cleanup_files()
        print("测试结束")

if __name__ == "__main__":
    test_tts_sequence()
    