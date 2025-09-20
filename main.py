from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
import json
from datetime import datetime
import urllib.parse
import re
import base64
import html

@register("获取 Minecraft JE/BE 服务器 一系列信息", "WZL", "astrbot_plugin_WZL_MinecraftServicePing", "1.0.0", "https://github.com/WZL0813/astrbot_plugin_WZL_MinecraftServicePing")
class MCQueryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.session: Optional[aiohttp.ClientSession] = None
        self.api_urls = [
            "http://101.35.2.25/api/fun/mcserver.php",
            "http://124.222.204.22/api/fun/mcserver.php", 
            "http://124.220.49.230/api/fun/mcserver.php",
            "https://cn.apihz.cn/api/fun/mcserver.php"
        ]
        # 默认使用公共KEY
        self.api_id = "10007770"
        self.api_key = "bd7c2dbb39384689337c9bcba9ffb9d0"
        logger.info("MCQueryPlugin初始化完成")

    async def initialize(self):
        """初始化aiohttp会话"""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))

    async def terminate(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None

    @filter.command("mcp", alias={'mcserver', 'mcstatus', 'mc查询'})
    async def mc_server_query(self, event: AstrMessageEvent):
        '''查询Minecraft服务器状态'''
        # 从消息中提取参数
        message_text = event.message_str.strip()
        
        # 移除命令部分
        if message_text.startswith("/mcp"):
            params_text = message_text[4:].strip()
        else:
            # 处理别名命令
            params_text = message_text.split(" ", 1)[1] if " " in message_text else ""
        
        if not params_text:
            yield event.plain_result("❌ 请输入服务器地址\n💡 使用: /mcp <服务器地址> [端口]")
            return
        
        # 解析服务器地址和端口
        parts = params_text.split()
        server_address = parts[0]
        port = 25565
        
        # 检查地址是否包含端口
        if ":" in server_address:
            address_parts = server_address.split(":", 1)
            server_address = address_parts[0]
            try:
                port = int(address_parts[1])
            except ValueError:
                yield event.plain_result(f"❌ 端口号无效: {address_parts[1]}")
                return
        
        # 检查是否有额外的端口参数
        if len(parts) > 1:
            try:
                port = int(parts[1])
            except ValueError:
                yield event.plain_result(f"❌ 端口号无效: {parts[1]}")
                return
        
        logger.info("查询Minecraft服务器: %s:%s", server_address, port)
        
        if not self.session:
            await self.initialize()

        try:
            # 查询服务器信息
            server_info = await self.query_mc_server(server_address, port)
            
            if server_info:
                if server_info.get("code") == 200:
                    # 格式化响应
                    response = await self.format_server_response_text(server_info, server_address, port)
                    yield event.plain_result(response)
                else:
                    error_msg = server_info.get("msg", "未知错误")
                    yield event.plain_result(f"❌ 查询失败: {error_msg}")
            else:
                yield event.plain_result("❌ 无法连接到API服务器，请稍后重试")
                
        except Exception as e:
            logger.error("查询服务器时出错: %s", str(e))
            yield event.plain_result("❌ 查询服务器时发生错误")

    async def query_mc_server(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """查询Minecraft服务器信息"""
        params = {
            "id": self.api_id,
            "key": self.api_key,
            "host": host,
            "port": port,
            "xy": 0  # 自动协议
        }
        
        for api_url in self.api_urls:
            try:
                async with self.session.get(api_url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
            except Exception as e:
                logger.warning("API调用失败: %s - %s", api_url, str(e))
                continue
        
        return None

    async def format_server_response_text(self, server_info: Dict[str, Any], host: str, port: int) -> str:
        """格式化服务器信息为文本"""
        data = server_info.get("data", {})
        address_info = server_info.get("address", "未知位置")
        
        # 构建响应文本
        response_text = f"🏔️ Minecraft服务器查询结果\n"
        response_text += f"📍 服务器: {host}:{port}\n"
        response_text += f"📡 网络位置: {address_info}\n"
        response_text += f"✅ 状态: {'在线' if data.get('status') else '离线'}\n"
        response_text += f"📋 版本: {data.get('version', '未知')}\n"
        response_text += f"🖥️ 核心: {data.get('software', '未知')}\n"
        response_text += f"👥 玩家: {data.get('players', 0)}/{data.get('max_players', 0)}\n"
        response_text += f"⏱️ 延迟: {data.get('ping', 0)}ms\n"
        response_text += f"🔧 查询协议: {data.get('query_method', '未知')}\n"
        response_text += f"📊 协议版本: {data.get('protocol', '未知')}\n\n"
        
        # 服务器描述信息
        if data.get('motd') or data.get('motd_raw'):
            response_text += f"📝 服务器描述:\n"
            if data.get('motd'):
                response_text += f"• 清理后: {data['motd']}\n"
            if data.get('motd_raw'):
                response_text += f"• 原始描述: {data['motd_raw']}\n"
            if data.get('server_title'):
                response_text += f"• 标题: {data['server_title']}\n"
            response_text += "\n"
        
        # 玩家信息
        if data.get('players_sample'):
            players = data['players_sample']
            if players and isinstance(players, list):
                response_text += f"🎮 玩家信息:\n"
                response_text += f"• 在线玩家: {data.get('players', 0)}/{data.get('max_players', 0)}\n"
                
                # 显示示例玩家列表
                sample_players = []
                for player in players[:10]:  # 只显示前10个玩家
                    if isinstance(player, dict):
                        name = player.get('name', '未知')
                        # 清理颜色代码
                        name = re.sub(r'§[0-9a-fk-or]', '', name)
                        sample_players.append(name)
                
                if sample_players:
                    response_text += f"• 示例玩家: {', '.join(sample_players)}\n"
                    if len(players) > 10:
                        response_text += f"• ... 等 {len(players)} 个玩家\n"
                response_text += "\n"
        
        # 插件和模组信息
        plugins = data.get('plugins', [])
        mods = data.get('mods', [])
        
        if plugins:
            response_text += f"🔌 插件列表 ({len(plugins)}个):\n"
            for i, plugin in enumerate(plugins[:5], 1):  # 只显示前5个插件
                if isinstance(plugin, dict):
                    response_text += f"{i}. {plugin.get('name', '未知')} v{plugin.get('version', '未知')}\n"
                else:
                    response_text += f"{i}. {plugin}\n"
            if len(plugins) > 5:
                response_text += f"... 等 {len(plugins)} 个插件\n"
            response_text += "\n"
        
        if mods:
            response_text += f"🎮 模组列表 ({len(mods)}个):\n"
            for i, mod in enumerate(mods[:5], 1):  # 只显示前5个模组
                response_text += f"{i}. {mod}\n"
            if len(mods) > 5:
                response_text += f"... 等 {len(mods)} 个模组\n"
            response_text += "\n"
        
        # 其他详细信息
        other_info = ""
        if data.get('game_mode') and data['game_mode'] != '未知':
            other_info += f"🎯 游戏模式: {data['game_mode']}\n"
        if data.get('map') and data['map'] != '未知':
            other_info += f"🗺️ 地图: {data['map']}\n"
        if data.get('hostname'):
            other_info += f"🌐 服务器IP: {data['hostname']}\n"
        if data.get('port'):
            other_info += f"🚪 服务器端口: {data['port']}\n"
        if data.get('error'):
            other_info += f"❌ 错误信息: {data['error']}\n"
        
        if other_info:
            response_text += f"📋 其他详细信息:\n{other_info}\n"
        
        # 查询时间和状态码
        response_text += f"⏰ 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        response_text += f"📊 API状态码: {server_info.get('code', '未知')}\n"
        response_text += f"💬 API消息: {server_info.get('msg', '未知')}"
        
        return response_text

    @filter.command("mcsetup")
    async def setup_api_keys(self, event: AstrMessageEvent):
        '''设置API密钥'''
        # 从消息中提取参数
        message_text = event.message_str.strip()
        
        if message_text.startswith("/mcsetup"):
            params_text = message_text[8:].strip()
        else:
            params_text = ""
        
        if not params_text:
            yield event.plain_result("❌ 请输入API密钥\n💡 使用: /mcsetup <开发者ID> <开发者KEY>")
            return
        
        parts = params_text.split()
        if len(parts) < 2:
            yield event.plain_result("❌ 参数不足\n💡 使用: /mcsetup <开发者ID> <开发者KEY>")
            return
        
        self.api_id = parts[0]
        self.api_key = parts[1]
        
        yield event.plain_result("✅ API密钥设置成功")

    @filter.command("mcapis")
    async def show_api_status(self, event: AstrMessageEvent):
        '''显示API状态'''
        status_info = f"🔧 当前API配置:\n"
        status_info += f"📋 开发者ID: {self.api_id}\n"
        status_info += f"🔑 开发者KEY: {self.api_key}\n"
        status_info += f"🌐 可用API端点: {len(self.api_urls)}个\n"
        status_info += f"💡 使用 /mcsetup <ID> <KEY> 设置API密钥"
        
        yield event.plain_result(status_info)