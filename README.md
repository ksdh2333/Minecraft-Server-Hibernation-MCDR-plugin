# Minecraft Server Hibernation Plugin for MCDReforged

这是一个 MCDReforged 插件，实现了 Minecraft 服务器的休眠功能。当没有玩家在线时，服务器会自动休眠以节省资源，当玩家尝试连接时自动唤醒。

## 功能特性

- 自动检测玩家数量，当没有玩家时自动休眠服务器
- 休眠期间启动代理服务器，响应玩家连接请求
- 玩家尝试连接时自动唤醒服务器
- 可配置的休眠延迟和检查间隔
- 自定义 MOTD 和服务器信息
- 支持命令控制休眠状态

## 工作原理

本插件提供两种休眠模式：

### 模式一：停止服务器模式（stop_server: true，默认）
1. **休眠过程**：
   - 通过 MCDReforged 停止服务器
   - 启动代理服务器
   - 代理服务器响应玩家连接并显示自定义 MOTD

2. **唤醒过程**：
   - 玩家连接到代理服务器端口
   - 代理服务器停止
   - 通过 MCDReforged 启动服务器

### 模式二：暂停进程模式（stop_server: false）
1. **休眠过程**：
   - 使用Windows API暂停服务器进程
   - 启动代理服务器
   - 代理服务器响应玩家连接并显示自定义 MOTD
   - 服务器进程保持暂停状态，不占用 CPU 资源

2. **唤醒过程**：
   - 玩家连接到代理服务器端口
   - 代理服务器停止
   - 恢复服务器进程，立即响应玩家连接

## 配置说明

插件配置文件位于 `config/server_hibernation/config.json`，主要配置项：

```json
{
  "server": {
    "host": "localhost",
    "port": 25565,
    "rcon_port": 25575,
    "rcon_password": ""
  },
  "proxy": {
    "host": "0.0.0.0",
    "port": 25566,
    "motd": "§6Server is hibernating\n§eJoin to wake it up!",
    "version": "1.19.2",
    "protocol": 760,
    "max_players": 20
  },
  "hibernation": {
    "check_interval": 30,
    "hibernation_delay": 60,
    "stop_server": true,
    "wake_message": "§aServer is waking up, please wait..."
  }
}
```

- `server.port`: Minecraft 服务器端口
- `proxy.port`: 代理服务器端口
- `proxy.motd`: 休眠时显示的 MOTD
- `hibernation.check_interval`: 检查玩家数量的间隔（秒）
- `hibernation.hibernation_delay`: 最后一个玩家离开后多久休眠（秒）
- `hibernation.stop_server`: 是否停止服务器（true）或暂停进程（false）

## 使用方法

### 命令

- `!!sh hibernate` - 立即休眠服务器
- `!!sh wake` - 唤醒服务器
- `!!sh status` - 查看当前状态
- `!!sh reload` - 重新加载配置
- `!!sh config` - 查看当前配置

### 玩家连接

当服务器休眠时，玩家需要连接到代理服务器端口而不是原服务器端口。连接后，服务器会自动唤醒。

## 故障排除

### 代理服务器无法启动
- 检查端口是否被占用
- 检查配置文件中的端口设置
- 查看 MCDReforged 日志获取详细错误信息

### 服务器无法唤醒
- 检查服务器启动脚本配置
- 查看 MCDReforged 日志获取详细错误信息

### 玩家无法连接
- 确保连接到正确的端口（代理服务器端口）
- 检查防火墙设置
- 确保代理服务器正在运行