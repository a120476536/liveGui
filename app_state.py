# app_state.py
import threading

class AppState:
    _lock = threading.Lock()
    show_gift = True
    show_msg = True
    
    show_gift_voice = False
    show_msg_voice = False
    
    chk_ks = True
    chk_dy = True
    
    live_version = "1.0.2"

    @classmethod
    def set_show_gift(cls, value: bool):
        with cls._lock:
            cls.show_gift = value
    @classmethod
    def get_show_gift(cls) -> bool:
        with cls._lock:
            return cls.show_gift
        
    @classmethod
    def set_show_msg(cls, value: bool):
        with cls._lock:
            cls.show_msg = value
    @classmethod
    def get_show_msg(cls) -> bool:
        with cls._lock:
            return cls.show_msg
        
    @classmethod
    def set_show_gift_voice(cls, value: bool):
        with cls._lock:
            cls.show_gift_voice = value
    @classmethod
    def get_show_gift_voice(cls) -> bool:
        with cls._lock:
            return cls.show_gift_voice
    @classmethod
    def set_show_msg_voice(cls, value: bool):
        with cls._lock:
            cls.show_msg_voice = value
    @classmethod
    def get_show_msg_voice(cls) -> bool:
        with cls._lock:
            return cls.show_msg_voice
    @classmethod
    def set_chk_ks(cls, value: bool):
        with cls._lock:
            cls.chk_ks = value
    @classmethod
    def get_chk_ks(cls) -> bool:
        with cls._lock:
            return cls.chk_ks
    @classmethod
    def set_chk_dy(cls, value: bool):
        with cls._lock:
            cls.chk_dy = value
    @classmethod
    def get_chk_dy(cls) -> bool:
        with cls._lock:
            return cls.chk_dy
    @classmethod
    def get_live_version(cls) -> str:
        with cls._lock:
            return cls.live_version
