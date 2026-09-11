Windows 本地文件打开器运行说明

一、安装依赖
1. Python 3.9 或更高版本。
2. 在项目根目录执行：
   python -m pip install -r client/requirements.txt

二、启动
在项目根目录执行：
   python client/sync_client.py

打开器会作为无界面的后台 HTTP 服务运行，仅监听：
   http://127.0.0.1:17321
请保持该命令窗口运行。

三、使用流程
1. 在网页“协同文件中心”点击文件名。
2. 网页先向服务器检出文件，再通知本地打开器下载文件并使用 Windows 默认软件打开。
3. 在 Word、Excel、CAD 等本地软件中编辑并保存。
4. 回到网页点击“检入”，本地打开器会上传当前文件，服务器生成新版本，成功后删除本地临时文件。
5. 如不需要提交修改，点击“取消检出”，成功后释放服务器检出并删除本地临时文件。

四、本地数据
临时文件默认保存在：
   %LOCALAPPDATA%\YishexuFileOpener\files
检出会话保存在：
   %LOCALAPPDATA%\YishexuFileOpener\sessions.json
每个文件按 file_id 使用独立目录，并保留服务器原文件名。

五、注意事项
- 打开器不会监听目录，也不会自动上传；只有网页点击“检入”时才上传。
- 检入前请先保存文件。若 Office 或其他软件正在占用文件导致读取失败，请关闭文件或等待写入完成后重试。
- 检入或取消失败时不会删除本地临时文件。
- 浏览器提示无法连接本地打开器时，请确认 client/sync_client.py 正在运行。
