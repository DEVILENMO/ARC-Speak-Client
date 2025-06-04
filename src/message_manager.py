import flet as ft
import asyncio
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime

class MessageManager:
    """消息管理器类，处理所有消息相关功能"""
    
    def __init__(self):
        # 当前频道消息
        self.current_chat_messages_data: List[Dict[str, Any]] = []
        
        # 消息加载状态
        self.oldest_message_id_loaded: Optional[int] = None
        self.has_more_older_messages_to_load: bool = False
        self.is_loading_older_messages: bool = False
        
        # 消息加载常量
        self.INITIAL_MESSAGE_LOAD_COUNT = 20
        self.OLDER_MESSAGE_LOAD_COUNT = 20
        
        # 回调函数
        self.callbacks: Dict[str, Callable] = {}
    
    def set_callback(self, name: str, callback: Callable):
        """设置回调函数"""
        self.callbacks[name] = callback
    
    def get_callback(self, name: str) -> Optional[Callable]:
        """获取回调函数"""
        return self.callbacks.get(name)
    
    def clear_messages(self):
        """清空当前消息"""
        self.current_chat_messages_data.clear()
        self.oldest_message_id_loaded = None
        self.has_more_older_messages_to_load = False
        self.is_loading_older_messages = False
    
    def add_message(self, message_data: Dict[str, Any]):
        """添加新消息"""
        self.current_chat_messages_data.append(message_data)
    
    def prepend_messages(self, messages: List[Dict[str, Any]]):
        """在开头插入消息（用于历史消息）"""
        self.current_chat_messages_data = messages + self.current_chat_messages_data
        
        # 更新最旧消息ID
        if messages:
            self.oldest_message_id_loaded = messages[0].get('id')
    
    def set_initial_messages(self, messages: List[Dict[str, Any]], has_more: bool = False):
        """设置初始消息"""
        self.current_chat_messages_data = messages
        self.has_more_older_messages_to_load = has_more
        
        if messages:
            self.oldest_message_id_loaded = messages[0].get('id')
        else:
            self.oldest_message_id_loaded = None
    
    def create_chat_message_control(self, msg_data: Dict[str, Any]) -> ft.Container:
        """创建聊天消息控件"""
        username = msg_data.get('username', 'Unknown')
        content = msg_data.get('content', '')
        timestamp = msg_data.get('timestamp', '')
        
        # 格式化时间戳
        try:
            if isinstance(timestamp, str):
                # 尝试解析ISO格式时间戳
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%H:%M')
            else:
                formatted_time = str(timestamp)
        except:
            formatted_time = str(timestamp)
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        username,
                        weight=ft.FontWeight.BOLD,
                        size=14,
                        color=ft.Colors.BLUE_600
                    ),
                    ft.Text(
                        formatted_time,
                        size=12,
                        color=ft.Colors.GREY_600
                    )
                ], spacing=10),
                ft.Text(
                    content,
                    size=14,
                    color=ft.Colors.BLACK87,
                    selectable=True
                )
            ], spacing=2),
            padding=ft.Padding(10, 8, 10, 8),
            margin=ft.Margin(0, 0, 0, 5),
            bgcolor=ft.Colors.WHITE,
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.GREY_300)
        )
    
    def render_chat_messages(self) -> List[ft.Control]:
        """渲染聊天消息列表"""
        controls = []
        
        # 如果有更多历史消息，添加加载按钮
        if self.has_more_older_messages_to_load and not self.is_loading_older_messages:
            load_button = ft.ElevatedButton(
                text="加载更早的消息",
                on_click=self._on_load_older_messages_click,
                bgcolor=ft.Colors.BLUE_100,
                color=ft.Colors.BLUE_800
            )
            controls.append(ft.Container(
                content=load_button,
                alignment=ft.alignment.center,
                padding=10
            ))
        elif self.is_loading_older_messages:
            # 显示加载指示器
            controls.append(ft.Container(
                content=ft.Row([
                    ft.ProgressRing(width=20, height=20),
                    ft.Text("加载中...", color=ft.Colors.GREY_600)
                ], alignment=ft.MainAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                padding=10
            ))
        
        # 添加消息
        for msg_data in self.current_chat_messages_data:
            controls.append(self.create_chat_message_control(msg_data))
        
        return controls
    
    def _on_load_older_messages_click(self, e):
        """加载更早消息的点击处理"""
        callback = self.get_callback('request_older_messages')
        if callback:
            asyncio.create_task(callback())
    
    async def request_older_messages_from_ui(self):
        """从UI请求更早的消息"""
        if self.is_loading_older_messages or not self.has_more_older_messages_to_load:
            return
        
        self.is_loading_older_messages = True
        
        # 更新UI显示加载状态
        callback = self.get_callback('update_messages_ui')
        if callback:
            await callback()
        
        # 请求网络数据
        network_callback = self.get_callback('fetch_older_messages')
        if network_callback:
            await network_callback(self.oldest_message_id_loaded, self.OLDER_MESSAGE_LOAD_COUNT)
    
    def handle_older_messages_loaded(self, data: Dict[str, Any]):
        """处理加载的历史消息"""
        messages = data.get('messages', [])
        has_more = data.get('has_more', False)
        
        if messages:
            # 按时间戳排序（最新的在前）
            messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            self.prepend_messages(messages)
        
        self.has_more_older_messages_to_load = has_more
        self.is_loading_older_messages = False
        
        # 更新UI
        callback = self.get_callback('update_messages_ui')
        if callback:
            asyncio.create_task(callback())
    
    def handle_historical_messages_loaded(self, data: Dict[str, Any]):
        """处理初始历史消息加载"""
        messages = data.get('messages', [])
        has_more = data.get('has_more', False)
        
        if messages:
            # 按时间戳排序（最新的在前）
            messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        self.set_initial_messages(messages, has_more)
        
        # 更新UI
        callback = self.get_callback('update_messages_ui')
        if callback:
            asyncio.create_task(callback())
    
    def handle_new_message(self, data: Dict[str, Any]):
        """处理新消息"""
        # 检查消息是否来自当前频道
        current_channel_callback = self.get_callback('get_current_text_channel_id')
        if current_channel_callback:
            current_channel_id = current_channel_callback()
            if data.get('channel_id') != current_channel_id:
                return  # 不是当前频道的消息，忽略
        
        self.add_message(data)
        
        # 更新UI
        callback = self.get_callback('update_messages_ui')
        if callback:
            asyncio.create_task(callback())
        
        # 自动滚动到底部
        scroll_callback = self.get_callback('scroll_to_bottom')
        if scroll_callback:
            asyncio.create_task(scroll_callback())
    
    def get_message_count(self) -> int:
        """获取当前消息数量"""
        return len(self.current_chat_messages_data)
    
    def get_latest_message(self) -> Optional[Dict[str, Any]]:
        """获取最新消息"""
        if self.current_chat_messages_data:
            return self.current_chat_messages_data[-1]
        return None
    
    def get_oldest_message(self) -> Optional[Dict[str, Any]]:
        """获取最旧消息"""
        if self.current_chat_messages_data:
            return self.current_chat_messages_data[0]
        return None
    
    def format_message_for_display(self, username: str, content: str, timestamp: str = None) -> str:
        """格式化消息用于显示"""
        if timestamp is None:
            timestamp = datetime.now().strftime('%H:%M')
        
        return f"[{timestamp}] {username}: {content}"
    
    def search_messages(self, query: str) -> List[Dict[str, Any]]:
        """搜索消息"""
        if not query.strip():
            return []
        
        query_lower = query.lower()
        results = []
        
        for msg in self.current_chat_messages_data:
            content = msg.get('content', '').lower()
            username = msg.get('username', '').lower()
            
            if query_lower in content or query_lower in username:
                results.append(msg)
        
        return results
    
    def get_messages_by_user(self, username: str) -> List[Dict[str, Any]]:
        """获取特定用户的消息"""
        return [msg for msg in self.current_chat_messages_data 
                if msg.get('username', '').lower() == username.lower()]
    
    def get_recent_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """获取最近的消息"""
        return self.current_chat_messages_data[-count:] if self.current_chat_messages_data else [] 