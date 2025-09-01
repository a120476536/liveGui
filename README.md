# 📡 数据监听工具 (Data Listener Tool)

一个基于本地代理/本机浏览器的开源数据监听工具，**不依赖任何远程服务器**，专注于本地数据采集与展示。  

⚠️ **重要提醒**  
在使用本程序之前，请务必仔细阅读并理解 [LICENSE](./LICENSE) 文件中的条款与免责声明。  
若您不同意其中任何内容，请立即停止使用本程序。  

---

## ✨ 功能特点
- 📍 **本地运行**：数据仅通过本机代理或浏览器获取，不涉及远程服务器  
- 🔒 **隐私友好**：开发者不收集、不存储任何用户数据  
- ⚙️ **开源可扩展**：支持二次开发、自由修改与分发  
- 🚀 **轻量高效**：部署简单，使用方便  

---

## 📥 安装与使用

### 1️⃣ 克隆项目
```bash
git clone https://github.com/yourname/yourproject.git
cd yourproject


### win 打包 已测试
# 进入目录
cd /d D:\pythonProject\LiveGui
# 没有build_env的话 创建一个
python -m venv build_env
# 激活环境 - 纯净
build_env\Scripts\activate

# 安装依赖库
pip install pyinstaller PyQt5 websockets pyserial requests edge_tts playsound==1.2.2 pygame   # playsound 最新版 安装失败 指定 1.2.2 可以安装
# 需要指定版本 这么指定
- pip install PyQt5==5.15.9 websockets>=10.4,<11 pyserial==3.5 requests==2.31.0 edge_tts==1.0.7 playsound==1.3.0

# 打包
pyinstaller -w -i "D:\apk\logo.ico" liveMain.py
# 可命名方式
pyinstaller -w -i "D:\apk\logo.ico" --name "MyApp" liveMain.py

# 搭配更新器使用
pyinstaller -w -i "D:\apk\logo.ico" updater_worker.py -n updater
更新程序打包后 将 updater.exe  移动到 liveMain.py 打包后的目录下 即 与 liveMain.exe 平级 存放


# 用虚拟环境  mac 本机运行前要
```
cd /Users/ljj/Documents/gitProject/live-gui
/opt/homebrew/bin/python3 -m venv venv
source venv/bin/activate
pip install pyserial websockets
python liveMain.py
```
以后每次运行都需要先 
```
source venv/bin/activate
python liveMain.py
```
退出虚拟环境：
```
deactivate
```


### mac打包  - 未测试
# 进入项目目录
cd ~/Documents/gitProject/live-gui

# 建立虚拟环境
python3 -m venv build_env
source build_env/bin/activate

# 安装依赖
pip install pyinstaller PyQt5 websockets pyserial requests

# 打包（生成 .app）
pyinstaller -w -i logo.icns liveMain.py