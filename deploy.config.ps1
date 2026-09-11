# 局域网部署/同步配置
# 修改以下参数后，重新运行 sync_to_server.ps1 即可

$DeployServerHost = "WIN-5M51K63ADPF"
$DeployServerPath = "D:\yishexu-designtools"

# 连接方式: admin = 通过 \\host\D$\... 管理共享; share = 通过命名共享
$DeployConnectionMode = "share"
$DeployShareName = "yishexu-designtools"

# 可选：填写后免弹窗登录（留空则在终端中手动输入）
$DeployShareUsername = "Administrator"
$DeploySharePassword = "admin@123"
