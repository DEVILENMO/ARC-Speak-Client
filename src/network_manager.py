import aiohttp
import socketio
import ssl
import asyncio
import flet as ft
from typing import Optional, Dict, Callable, Any
from config_loader import ConfigLoader

class NetworkManager:
    """网络管理器类，处理所有网络通信功能"""
    
    def __init__(self, config_file: str):
        self.config_loader = ConfigLoader(config_file)
        self.server_address = self.config_loader.get("server_address", "127.0.0.1")
        self.server_port = self.config_loader.get("server_port", 5000)
        
        # SocketIO客户端
        self.sio_client: Optional[socketio.AsyncClient] = None
        self.shared_aiohttp_session: Optional[aiohttp.ClientSession] = None
        
        # 用户状态
        self.current_user_info: Optional[Dict[str, Any]] = None
        
        # 回调函数
        self.callbacks: Dict[str, Callable] = {}
        
        # SSL上下文
        self.ssl_context = self._create_ssl_context()
    
    def _create_ssl_context(self):
        """创建SSL上下文（忽略证书验证）"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    
    def set_callback(self, name: str, callback: Callable):
        """设置回调函数"""
        self.callbacks[name] = callback
    
    def get_callback(self, name: str) -> Optional[Callable]:
        """获取回调函数"""
        return self.callbacks.get(name)
    
    def get_api_base_url(self) -> str:
        """获取API基础URL"""
        return f"https://{self.server_address}:{self.server_port}/api"
    
    def get_sio_url(self) -> str:
        """获取SocketIO URL"""
        return f"https://{self.server_address}:{self.server_port}"
    
    def update_server_config(self, address: str, port: int):
        """更新服务器配置"""
        self.server_address = address
        self.server_port = port
        self.config_loader.set("server_address", address)
        self.config_loader.set("server_port", port)
        self.config_loader.save_config()
    
    async def create_http_session(self):
        """创建HTTP会话"""
        if self.shared_aiohttp_session is None:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            # 使用cookie_jar允许保存和使用cookie，这对Socket.IO认证很重要
            cookie_jar = aiohttp.CookieJar(unsafe=True)
            self.shared_aiohttp_session = aiohttp.ClientSession(
                connector=connector, 
                cookie_jar=cookie_jar
            )
            print("HTTP会话已创建，配置了cookie支持")
    
    async def close_http_session(self):
        """关闭HTTP会话"""
        if self.shared_aiohttp_session:
            await self.shared_aiohttp_session.close()
            self.shared_aiohttp_session = None
    
    async def create_socketio_client(self):
        """创建SocketIO客户端"""
        # 确保HTTP会话已创建
        if self.shared_aiohttp_session is None:
            await self.create_http_session()
            
        if self.sio_client is None:
            # 使用共享的HTTP会话创建Socket.IO客户端
            self.sio_client = socketio.AsyncClient(
                ssl_verify=False,
                http_session=self.shared_aiohttp_session,
                logger=True,
                engineio_logger=True
            )
            print("Socket.IO客户端已创建，使用共享HTTP会话")
            await self._setup_socketio_events()
    
    async def _setup_socketio_events(self):
        """设置SocketIO事件处理器"""
        if not self.sio_client:
            return
        
        @self.sio_client.event
        async def connect():
            print("Connected to SocketIO server")
            callback = self.get_callback('on_socket_connect')
            if callback:
                await callback()
        
        @self.sio_client.event
        async def disconnect():
            print("Disconnected from SocketIO server")
            callback = self.get_callback('on_socket_disconnect')
            if callback:
                await callback()
        
        @self.sio_client.event
        async def connect_error(data):
            print(f"SocketIO connection error: {data}")
            callback = self.get_callback('on_socket_connect_error')
            if callback and callable(callback):
                try:
                    # 如果回调是一个异步函数，则使用await调用它
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    # 如果回调是普通函数，则直接调用
                    else:
                        callback(data)
                except Exception as e:
                    print(f"Error in connect_error callback: {e}")
        
        @self.sio_client.event
        async def new_message(data):
            callback = self.get_callback('on_new_message')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def voice_channel_users(data):
            callback = self.get_callback('on_voice_channel_users')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def user_joined_voice(data):
            callback = self.get_callback('on_user_joined_voice')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def user_left_voice(data):
            callback = self.get_callback('on_user_left_voice')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def user_speaking(data):
            callback = self.get_callback('on_user_speaking')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def user_mic_status_updated(data):
            callback = self.get_callback('on_user_mic_status_updated')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def user_voice_activity(data):
            callback = self.get_callback('on_user_voice_activity')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def voice_data_stream_chunk(data):
            callback = self.get_callback('on_voice_data_stream_chunk')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def error(data):
            callback = self.get_callback('on_socket_error')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def server_user_list_update(data):
            callback = self.get_callback('on_server_user_list_update')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def older_messages_loaded(data):
            callback = self.get_callback('on_older_messages_loaded')
            if callback:
                await callback(data)
        
        @self.sio_client.event
        async def load_historical_messages(data):
            callback = self.get_callback('on_load_historical_messages')
            if callback:
                await callback(data)
    
    async def connect_socketio(self, auth_data: Dict[str, str] = None):
        """连接到SocketIO服务器"""
        if not self.sio_client:
            await self.create_socketio_client()
        
        try:
            # 简化认证逻辑，与参考代码保持一致
            # 如果服务器使用HTTP cookie进行认证，则不需要显式传递token
            print(f"正在连接Socket.IO服务器: {self.get_sio_url()}")
            await self.sio_client.connect(
                self.get_sio_url(), 
                wait_timeout=10,
                transports=['websocket', 'polling']  # 支持多种传输方式
            )
            print("Socket.IO连接成功!")
            return True
        except Exception as e:
            print(f"Failed to connect to SocketIO: {e}")
            return False
    
    async def disconnect_socketio(self):
        """断开SocketIO连接"""
        if self.sio_client and self.sio_client.connected:
            await self.sio_client.disconnect()
    
    async def emit_socketio(self, event: str, data: Any = None):
        """发送SocketIO事件"""
        if self.sio_client and self.sio_client.connected:
            await self.sio_client.emit(event, data)
        else:
            print(f"Cannot emit {event}: SocketIO not connected")
    
    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """用户登录"""
        await self.create_http_session()
        
        login_data = {
            "username": username,
            "password": password
        }
        
        try:
            async with self.shared_aiohttp_session.post(
                f"{self.get_api_base_url()}/login",
                json=login_data
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("success"):
                    # 提取用户信息和token
                    user_info = result.get("user", {})
                    # 检查token是否在用户对象中，如果不在则尝试从响应的根层级获取
                    token = user_info.get("token")
                    if not token:
                        token = result.get("token")
                    
                    # 如果找到token，确保它被添加到用户信息中
                    if token:
                        if isinstance(user_info, dict):
                            user_info["token"] = token
                        else:
                            user_info = {"token": token, "username": username}
                    
                    self.current_user_info = user_info
                    return {"success": True, "user": self.current_user_info}
                else:
                    return {"success": False, "message": result.get("message", "登录失败")}
        except Exception as e:
            return {"success": False, "message": f"网络错误: {str(e)}"}
    
    async def register(self, username: str, password: str, invite_code: str) -> Dict[str, Any]:
        """用户注册"""
        await self.create_http_session()
        
        register_data = {
            "username": username,
            "password": password,
            "invite_code": invite_code
        }
        
        try:
            async with self.shared_aiohttp_session.post(
                f"{self.get_api_base_url()}/register",
                json=register_data
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("success"):
                    return {"success": True, "message": result.get("message", "注册成功")}
                else:
                    return {"success": False, "message": result.get("message", "注册失败")}
        except Exception as e:
            return {"success": False, "message": f"网络错误: {str(e)}"}
    
    async def fetch_channels(self) -> Dict[str, Any]:
        """获取频道列表"""
        await self.create_http_session()
        if not self.shared_aiohttp_session:
            return {"success": False, "message": "HTTP session not created"}

        try:
            async with self.shared_aiohttp_session.get(
                f"{self.get_api_base_url()}/channels" 
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # 服务器应该返回类似 {"text_channels": [...], "voice_channels": [...]} 的结构
                    return {"success": True, "data": data}
                else:
                    error_message = await response.text()
                    print(f"Error fetching channels: {response.status} - {error_message}")
                    return {"success": False, "message": f"获取频道失败: {response.status} - {error_message}"}
        except aiohttp.ClientConnectorError as e:
            print(f"Connection error fetching channels: {str(e)}")
            return {"success": False, "message": f"网络连接错误: {str(e)}"}
        except Exception as e:
            print(f"Exception fetching channels: {str(e)}")
            return {"success": False, "message": f"获取频道时发生未知错误: {str(e)}"}
    
    async def send_message(self, channel_id: int, content: str) -> Dict[str, Any]:
        """发送消息"""
        if not self.current_user_info:
            return {"success": False, "message": "用户未登录"}
        
        await self.create_http_session()
        
        headers = {"Authorization": f"Bearer {self.current_user_info.get('token', '')}"}
        message_data = {
            "channel_id": channel_id,
            "content": content
        }
        
        try:
            async with self.shared_aiohttp_session.post(
                f"{self.get_api_base_url()}/send_message",
                json=message_data,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("success"):
                    return {"success": True}
                else:
                    return {"success": False, "message": result.get("message", "发送消息失败")}
        except Exception as e:
            return {"success": False, "message": f"网络错误: {str(e)}"}
    
    async def join_voice_channel(self, channel_id: int) -> Dict[str, Any]:
        """加入语音频道"""
        if not self.current_user_info:
            return {"success": False, "message": "用户未登录"}
        
        await self.create_http_session()
        
        headers = {"Authorization": f"Bearer {self.current_user_info.get('token', '')}"}
        join_data = {"channel_id": channel_id}
        
        try:
            async with self.shared_aiohttp_session.post(
                f"{self.get_api_base_url()}/join_voice",
                json=join_data,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("success"):
                    return {"success": True}
                else:
                    return {"success": False, "message": result.get("message", "加入语音频道失败")}
        except Exception as e:
            return {"success": False, "message": f"网络错误: {str(e)}"}
    
    async def leave_voice_channel(self) -> Dict[str, Any]:
        """离开语音频道"""
        if not self.current_user_info:
            return {"success": False, "message": "用户未登录"}
        
        await self.create_http_session()
        
        headers = {"Authorization": f"Bearer {self.current_user_info.get('token', '')}"}
        
        try:
            async with self.shared_aiohttp_session.post(
                f"{self.get_api_base_url()}/leave_voice",
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("success"):
                    return {"success": True}
                else:
                    return {"success": False, "message": result.get("message", "离开语音频道失败")}
        except Exception as e:
            return {"success": False, "message": f"网络错误: {str(e)}"}
    
    async def request_older_messages(self, channel_id: int, oldest_message_id: Optional[int] = None, count: int = 20) -> Dict[str, Any]:
        """请求更早的消息"""
        if not self.current_user_info:
            return {"success": False, "message": "用户未登录"}
        
        await self.create_http_session()
        
        headers = {"Authorization": f"Bearer {self.current_user_info.get('token', '')}"}
        params = {
            "channel_id": channel_id,
            "count": count
        }
        if oldest_message_id:
            params["before_message_id"] = oldest_message_id
        
        try:
            async with self.shared_aiohttp_session.get(
                f"{self.get_api_base_url()}/messages",
                params=params,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("success"):
                    return {
                        "success": True,
                        "messages": result.get("messages", []),
                        "has_more": result.get("has_more", False)
                    }
                else:
                    return {"success": False, "message": result.get("message", "获取消息失败")}
        except Exception as e:
            return {"success": False, "message": f"网络错误: {str(e)}"}
    
    async def cleanup(self):
        """清理资源"""
        await self.disconnect_socketio()
        await self.close_http_session()
        self.current_user_info = None 