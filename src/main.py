import flet as ft
import aiohttp
import asyncio
import threading
import numpy as np
import os
import ssl
import socketio
import inspect
from typing import Dict, Any, Optional
from config_loader import ConfigLoader
from color_palette import *
from audio_manager import AudioManager
from network_manager import NetworkManager
from message_manager import MessageManager
from ui_manager import UIManager

# --- Configuration ---
CONFIG_FILE = "storage/data/config.json"
config_loader = ConfigLoader(CONFIG_FILE)
SERVER_ADDRESS = config_loader.get("server_address", "127.0.0.1")
SERVER_PORT = config_loader.get("server_port", 5005)

def get_api_base_url():
    return f"https://{SERVER_ADDRESS}:{SERVER_PORT}/api"

def get_sio_url():
    return f"https://{SERVER_ADDRESS}:{SERVER_PORT}"

# --- Global State ---
sio_client = None 
current_user_info = None
active_page_controls = {} 
shared_aiohttp_session = None
current_text_channel_id = None
current_voice_channel_id = None # ID of the voice channel user is actively (confirmed) in
previewing_voice_channel_id = None # ID of voice channel being previewed
is_actively_in_voice_channel = False # Has user clicked "Confirm Join"?

# --- Voice Activity Detection (Client-side timeout for card color) ---
user_last_voice_activity_time = {} # Stores user_id: timestamp
active_voice_activity_timers = {} # Stores user_id: asyncio.TimerHandle
VOICE_ACTIVITY_TIMEOUT = 1.0  # Seconds before card returns to non-speaking color

text_channels_data = [] # 修改为列表以匹配 UIManager 的期望
voice_channels_data = [] # 修改为列表以匹配 UIManager 的期望
current_chat_messages = [] 
all_server_users = [] 
current_voice_channel_active_users = {} # Users in the PREVIEWING or ACTIVE voice channel

# --- Chat Message State ---
current_chat_messages_data = [] # Holds full dicts of current chat messages
oldest_message_id_loaded = None # ID of the oldest message currently loaded
has_more_older_messages_to_load = False # Flag if server indicates more older messages exist
is_loading_older_messages = False # Flag to prevent duplicate load requests

# --- Constants for message loading (client-side) ---
INITIAL_MESSAGE_LOAD_COUNT = 20 # Matches server, but not strictly necessary for client to define if server controls initial load size
OLDER_MESSAGE_LOAD_COUNT = 20   # Number of older messages to request each time

# 全局管理器实例
ui_manager = None
audio_manager = None
network_manager = None
message_manager = None

def _update_mic_test_bar_callback(volume):
    """回调函数：更新麦克风测试音量条"""
    if ui_manager:
        mic_test_bar = ui_manager.get_control('voice_settings_mic_test_bar')
        if mic_test_bar:
            mic_test_bar.value = volume
            if hasattr(mic_test_bar, 'update'):
                mic_test_bar.update()

async def main(page: ft.Page):
    global ui_manager, audio_manager, network_manager, message_manager
    global sio_client, shared_aiohttp_session, current_user_info, SERVER_ADDRESS, SERVER_PORT
    global text_channels_data, voice_channels_data

    # 定义 Socket.IO 连接成功后的处理函数
    async def on_socket_connect_handler():
        print("Socket.IO 连接成功! 开始获取频道列表...")
        ui_manager.update_status_text("服务连接成功！正在获取频道列表...")
        
        channel_result = await network_manager.fetch_channels()
        if channel_result and channel_result.get("success"):
            global text_channels_data, voice_channels_data
            fetched_data = channel_result.get("data", {})
            text_channels_data = fetched_data.get("text_channels", [])
            voice_channels_data = fetched_data.get("voice_channels", [])
            
            print(f"获取到的文本频道: {text_channels_data}")
            print(f"获取到的语音频道: {voice_channels_data}")
            
            ui_manager.update_channel_lists(text_channels_data, voice_channels_data)
            ui_manager.update_status_text("频道列表已加载。")
        else:
            print(f"获取频道列表失败: {channel_result.get('message')}")
            ui_manager.update_status_text(f"获取频道列表失败: {channel_result.get('message', '未知错误')}")

    # --- Socket.IO 连接错误处理函数 ---
    def on_socket_connect_error_handler(error_data):
        """处理Socket.IO连接错误"""
        print(f"Socket.IO连接错误处理: {error_data}")
        error_message = "连接错误"
        
        if isinstance(error_data, dict) and 'message' in error_data:
            error_message = error_data['message']
        elif isinstance(error_data, str):
            error_message = error_data
        
        ui_manager.update_status_text(f"服务器连接错误: {error_message}")
        
        # 如果是认证错误，可能需要重新登录
        if "reject" in str(error_message).lower() or "auth" in str(error_message).lower():
            print("检测到可能的认证问题，尝试重新登录")
            # 在认证错误情况下，可能需要清除保存的登录信息
            config_loader.reset_login_info()

    # --- Socket.IO事件处理函数 ---
    async def on_new_message(data):
        """处理新消息事件"""
        global current_text_channel_id, current_chat_messages_data
        if data.get('channel_id') == current_text_channel_id:
            # 将新消息添加到内部数据列表
            current_chat_messages_data.append(data)
            # 更新消息UI
            _render_chat_messages()

    async def older_messages_loaded(data):
        """处理服务器返回的较早消息批次"""
        global current_text_channel_id, current_chat_messages_data, oldest_message_id_loaded, has_more_older_messages_to_load, is_loading_older_messages

        is_loading_older_messages = False  # 完成加载此批次，始终重置

        channel_id = data.get('channel_id')
        if channel_id != current_text_channel_id:
            print(f"[LOAD_MORE] 收到频道 {channel_id} 的较早消息，但当前频道是 {current_text_channel_id}。忽略。")
            # 仍然重新渲染，因为is_loading_older_messages已更改，这可能影响UI（加载指示器）
            _render_chat_messages()
            if hasattr(page, 'update'): page.update()
            return

        older_msgs = data.get('messages', [])
        # 服务器应该已经按时间顺序发送它们（此批次中最早的先）

        if older_msgs:
            current_chat_messages_data = older_msgs + current_chat_messages_data
            oldest_message_id_loaded = older_msgs[0].get('message_id')
            print(f"[LOAD_MORE] 预加载了 {len(older_msgs)} 条较早消息。新的最早ID: {oldest_message_id_loaded}")
        else:
            print("[LOAD_MORE] 服务器在此批次中没有返回更早的消息。")
            # 如果服务器发送空列表，意味着没有比客户端引用的更早的消息。
            # 服务器的has_more_older标志是按钮的最终依据。

        has_more_older_messages_to_load = data.get('has_more_older', False)
        print(f"[LOAD_MORE] UI将反映has_more_older: {has_more_older_messages_to_load}")
        
        _render_chat_messages()
        if hasattr(page, 'update'): page.update()

    async def load_historical_messages(data):
        """处理服务器发送的初始历史消息批次"""
        global current_text_channel_id, current_chat_messages_data, oldest_message_id_loaded, has_more_older_messages_to_load
        
        channel_id = data.get('channel_id')
        if channel_id != current_text_channel_id:
            print(f"[HISTORY] 收到频道 {channel_id} 的历史消息，但当前频道是 {current_text_channel_id}。忽略。")
            return

        messages = data.get('messages', [])
        current_chat_messages_data = messages  # 用此初始批次替换当前数据
        has_more_older_messages_to_load = data.get('has_more_older', False)
        
        if messages:  # 如果加载了任何消息
            oldest_message_id_loaded = messages[0].get('message_id')  # 第一条消息是此批次中最早的
        else:
            oldest_message_id_loaded = None  # 没有消息，所以没有最早ID

        print(f"[HISTORY] 为频道 {channel_id} 加载了 {len(messages)} 条历史消息。最早ID: {oldest_message_id_loaded}。有更多: {has_more_older_messages_to_load}")
        _render_chat_messages()  # 渲染所有消息（包括新的历史记录）
        
        # 确保主页面更新以反映更改
        if hasattr(page, 'update'): page.update()

    async def on_voice_channel_users(data):
        """处理特定语音频道的用户列表"""
        channel_id_of_update = data.get('channel_id')
        if channel_id_of_update == previewing_voice_channel_id: # 仅当匹配我们正在预览/加入的频道时更新
            global current_voice_channel_active_users
            current_voice_channel_active_users.clear()
            for user_info in data.get('users', []):
                current_voice_channel_active_users[user_info['user_id']] = {
                    'id': user_info['user_id'],
                    'username': user_info['username'],
                    'mic_muted': False,  # 默认未静音，将通过user_mic_status_updated事件更新
                    'is_card_speaking': False # 默认不在说话（卡片颜色）
                }
            update_voice_channel_user_list_ui()

    async def on_user_joined_voice(data):
        """处理用户加入语音频道事件"""
        channel_id_of_update = data.get('channel_id')
        if channel_id_of_update == previewing_voice_channel_id:
            user_id, username = data.get('user_id'), data.get('username')
            if user_id and username and user_id not in current_voice_channel_active_users:
                current_voice_channel_active_users[user_id] = {
                    'id': user_id,
                    'username': username,
                    'mic_muted': False,
                    'is_card_speaking': False
                }
                update_voice_channel_user_list_ui()

    async def on_user_left_voice(data):
        """处理用户离开语音频道事件"""
        channel_id_of_update = data.get('channel_id')
        if channel_id_of_update == previewing_voice_channel_id:
            user_id_left = data.get('user_id')
            if user_id_left in current_voice_channel_active_users:
                del current_voice_channel_active_users[user_id_left]
                # TODO: 实现语音活动定时器清理逻辑
                update_voice_channel_user_list_ui()

    async def on_user_speaking(data):
        """处理用户麦克风状态更新（已重命名：此事件用于麦克风静音状态）"""
        user_id, server_reported_unmuted_status, target_channel_id = data.get('user_id'), data.get('speaking'), data.get('channel_id')
        # server_reported_unmuted_status: True表示未静音，False表示已静音
        if target_channel_id == current_voice_channel_id and user_id in current_voice_channel_active_users:
            client_mic_muted_state = not server_reported_unmuted_status  # mic_muted = True表示静音
            if current_voice_channel_active_users[user_id].get('mic_muted') != client_mic_muted_state:
                current_voice_channel_active_users[user_id]['mic_muted'] = client_mic_muted_state
                update_voice_channel_user_list_ui()  # 更新UI以改变麦克风图标

    async def on_user_mic_status_updated(data):
        """处理用户麦克风状态更新（新版本事件）"""
        user_id = data.get('user_id')
        server_reported_is_unmuted = data.get('is_unmuted')
        target_channel_id = data.get('channel_id')
        
        if target_channel_id == previewing_voice_channel_id and user_id in current_voice_channel_active_users:
            if server_reported_is_unmuted is not None:  # 确保key存在
                client_mic_muted_state = not server_reported_is_unmuted  # mic_muted = True表示静音
                
                if current_voice_channel_active_users[user_id].get('mic_muted') != client_mic_muted_state:
                    current_voice_channel_active_users[user_id]['mic_muted'] = client_mic_muted_state
                    
                    # TODO: 如果这是当前用户自己的状态更新，同步本地麦克风按钮状态
                    
                    update_voice_channel_user_list_ui()  # 更新UI

    async def on_user_voice_activity(data):
        """处理用户语音活动事件"""
        user_id = data.get('user_id')
        is_active = data.get('active', False)
        
        if user_id and user_id in current_voice_channel_active_users:
            if is_active:
                if not current_voice_channel_active_users[user_id].get('is_card_speaking', False):
                    current_voice_channel_active_users[user_id]['is_card_speaking'] = True
                    update_voice_channel_user_list_ui()
                
                # TODO: 实现语音活动超时处理逻辑

    async def on_voice_data_stream_chunk(data):
        """处理接收到的语音数据块"""
        global current_voice_channel_active_users, current_user_info, is_actively_in_voice_channel
        global user_last_voice_activity_time, active_voice_activity_timers
        
        # 如果不在语音频道中，不处理音频数据
        if not is_actively_in_voice_channel:
            return
        
        sender_user_id = data.get('user_id')
        
        # 忽略自己发送的数据
        if current_user_info and sender_user_id == current_user_info.get('id'):
            return
        
        # 检查是否是活跃语音频道中的用户
        if sender_user_id not in current_voice_channel_active_users:
            return
        
        audio_chunk_list = data.get('audio_data')
        chunk_samplerate = data.get('samplerate', audio_manager.STANDARD_SAMPLERATE)
        chunk_channels = data.get('channels', audio_manager.STANDARD_CHANNELS)
        chunk_dtype = data.get('dtype', 'float32')
        
        if audio_chunk_list and isinstance(audio_chunk_list, list):
            try:
                # 更新用户的语音活动状态
                if sender_user_id in current_voice_channel_active_users:
                    if not current_voice_channel_active_users[sender_user_id].get('is_card_speaking', False):
                        current_voice_channel_active_users[sender_user_id]['is_card_speaking'] = True
                        update_voice_channel_user_list_ui()
                    
                    # 更新最后语音活动时间
                    user_last_voice_activity_time[sender_user_id] = asyncio.get_event_loop().time()
                    
                    # 启动或重置语音活动超时定时器
                    await _start_voice_activity_timeout_task(sender_user_id)
                
                # 转换音频数据为NumPy数组
                audio_np_array = np.array(audio_chunk_list, dtype=np.float32)
                
                # 如果采样率不同，进行重采样
                if chunk_samplerate != audio_manager.STANDARD_SAMPLERATE:
                    print(f"重采样音频从 {chunk_samplerate}Hz 到 {audio_manager.STANDARD_SAMPLERATE}Hz")
                    audio_np_array = audio_manager.resample_audio(audio_np_array, chunk_samplerate, audio_manager.STANDARD_SAMPLERATE)
                
                # 规范化音频数据
                audio_np_array = audio_manager.normalize_audio_chunk(audio_np_array, volume_factor=1.0)
                
                # 添加到播放缓冲区
                await audio_manager.add_audio_chunk_to_playback_buffer(audio_np_array)
                
            except Exception as e:
                print(f"处理音频数据块时出错: {e}")

    # 语音活动超时处理
    async def _handle_voice_activity_timeout(user_id):
        """处理用户语音活动超时"""
        global current_voice_channel_active_users, active_voice_activity_timers
        
        # 清除定时器引用
        if user_id in active_voice_activity_timers:
            del active_voice_activity_timers[user_id]
        
        # 检查用户是否仍在当前语音频道
        if user_id in current_voice_channel_active_users:
            current_voice_channel_active_users[user_id]['is_card_speaking'] = False
            print(f"用户 {user_id} 语音活动超时，卡片变为非说话状态")
            # 更新UI
            update_voice_channel_user_list_ui()
    
    async def _start_voice_activity_timeout_task(user_id):
        """启动或重置语音活动超时任务"""
        global active_voice_activity_timers, VOICE_ACTIVITY_TIMEOUT
        
        # 取消现有定时器（如果有）
        if user_id in active_voice_activity_timers:
            timer_handle = active_voice_activity_timers[user_id]
            timer_handle.cancel()
        
        # 创建新定时器
        loop = asyncio.get_event_loop()
        timer_handle = loop.call_later(
            VOICE_ACTIVITY_TIMEOUT,
            lambda: asyncio.create_task(_handle_voice_activity_timeout(user_id))
        )
        active_voice_activity_timers[user_id] = timer_handle
        
    # 麦克风说话状态变化回调
    async def _update_speaking_status_async(is_speaking):
        """处理麦克风说话状态变化"""
        global current_user_info, current_voice_channel_active_users, is_actively_in_voice_channel
        
        # 只有在语音频道中时才处理说话状态
        if not is_actively_in_voice_channel or not current_user_info:
            return
        
        user_id = current_user_info.get('id')
        if user_id in current_voice_channel_active_users:
            # 更新本地用户卡片的说话状态
            if current_voice_channel_active_users[user_id].get('is_card_speaking') != is_speaking:
                current_voice_channel_active_users[user_id]['is_card_speaking'] = is_speaking
                update_voice_channel_user_list_ui()
                print(f"本地用户说话状态更新: is_speaking={is_speaking}")
        
        # 如果开始说话，也可以更新最后的语音活动时间和启动超时定时器
        if is_speaking and user_id:
            user_last_voice_activity_time[user_id] = asyncio.get_event_loop().time()
            await _start_voice_activity_timeout_task(user_id)

    async def on_server_user_list_update(data):
        """处理服务器用户列表更新"""
        global all_server_users
        all_server_users = data
        server_users_list_view = ui_manager.get_control('server_users_list_view')
        if server_users_list_view:
            # 按用户名排序并创建用户列表控件
            sorted_users = sorted(all_server_users, key=lambda u: u.get('username', '').lower())
            controls = []
            for user in sorted_users:
                user_row = ft.Row(
                    [
                        ft.Icon(name=ft.Icons.CIRCLE, color=ft.Colors.GREEN_ACCENT_700, size=10),
                        ft.Text(user.get('username', 'N/A'), color=COLOR_TEXT_ON_WHITE)
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5
                )
                controls.append(user_row)
            
            server_users_list_view.controls = controls
            if hasattr(server_users_list_view, 'update'): server_users_list_view.update()

    # 音频数据发送处理函数
    async def send_audio_data(audio_data):
        """处理发送音频数据到服务器"""
        global current_voice_channel_id, sio_client, is_actively_in_voice_channel
        
        if not is_actively_in_voice_channel or current_voice_channel_id is None or not sio_client or not sio_client.connected:
            return
        
        try:
            # 将NumPy数组转换为列表以便通过JSON发送
            audio_data_list = audio_data.tolist() if isinstance(audio_data, np.ndarray) else audio_data
            
            # 发送到服务器
            await sio_client.emit('voice_data_stream', {
                'channel_id': current_voice_channel_id,
                'audio_data': audio_data_list,
                'samplerate': audio_manager.STANDARD_SAMPLERATE,  # 告诉服务器采样率
                'channels': audio_manager.STANDARD_CHANNELS,      # 告诉服务器声道数
                'dtype': 'float32'                              # 告诉服务器数据类型
            })
        except Exception as e:
            print(f"发送音频数据时出错: {e}")

    # 定义频道点击处理函数
    def update_voice_panel_button_visibility():
        """更新语音面板按钮的可见性"""
        print(f"[DEBUG] update_voice_panel_button_visibility: previewing_vc_id={previewing_voice_channel_id}, is_active={is_actively_in_voice_channel}")
        confirm_join_btn = ui_manager.get_control('confirm_join_voice_button')
        leave_voice_btn = ui_manager.get_control('leave_voice_button')
        voice_settings_ctrl = ui_manager.get_control('voice_settings_area')

        if previewing_voice_channel_id is not None:  # 如果正在预览某个语音频道
            if is_actively_in_voice_channel:  # 如果用户已主动加入此语音频道
                if confirm_join_btn: confirm_join_btn.visible = False
                if leave_voice_btn: leave_voice_btn.visible = True
                if voice_settings_ctrl: voice_settings_ctrl.visible = True
            else:  # 用户正在预览此语音频道，但未主动加入
                if confirm_join_btn: confirm_join_btn.visible = True
                if leave_voice_btn: leave_voice_btn.visible = False
                if voice_settings_ctrl: voice_settings_ctrl.visible = False
        else:  # 用户没有预览任何语音频道
            if confirm_join_btn: confirm_join_btn.visible = False
            if leave_voice_btn: leave_voice_btn.visible = False
            if voice_settings_ctrl: voice_settings_ctrl.visible = False

        # 单独更新每个相关控件的UI
        if confirm_join_btn and hasattr(confirm_join_btn, 'update'): confirm_join_btn.update()
        if leave_voice_btn and hasattr(leave_voice_btn, 'update'): leave_voice_btn.update()
        if voice_settings_ctrl and hasattr(voice_settings_ctrl, 'update'): voice_settings_ctrl.update()

    def update_voice_channel_user_list_ui():
        """更新语音频道用户列表UI"""
        vc_users_list_ctrl = ui_manager.get_control('voice_channel_internal_users_list')
        if not vc_users_list_ctrl: return

        vc_user_controls = []
        # 对当前语音频道中的用户进行排序
        sorted_users_in_vc = sorted(current_voice_channel_active_users.values(), key=lambda u: u.get('username', '').lower())
        
        for user_data in sorted_users_in_vc:
            # 根据用户说话状态确定卡片颜色
            if user_data.get('is_card_speaking', False):
                user_card_bgcolor = COLOR_PRIMARY
                user_card_icon_and_name_color = COLOR_TEXT_ON
                user_card_border = None
            else:
                user_card_bgcolor = ft.Colors.WHITE
                user_card_icon_and_name_color = COLOR_TEXT_ON_WHITE
                user_card_border = ft.border.all(1, COLOR_BORDER)

            # 根据麦克风状态确定图标
            mic_icon_name = ft.Icons.MIC_OFF if user_data.get('mic_muted', False) else ft.Icons.MIC

            user_display_row = ft.Row(
                [
                    ft.Icon(name=mic_icon_name, color=user_card_icon_and_name_color, size=16),
                    ft.Text(user_data.get('username', 'Unknown'), color=user_card_icon_and_name_color, weight=ft.FontWeight.NORMAL, size=12)
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=5,
            )

            user_card = ft.Container(
                content=user_display_row,
                bgcolor=user_card_bgcolor,
                border=user_card_border,
                border_radius=ft.border_radius.all(4),
                padding=ft.padding.symmetric(vertical=4, horizontal=6),
                margin=ft.margin.only(bottom=4)
            )
            vc_user_controls.append(user_card)

        # 更新UI控件
        vc_users_list_ctrl.controls = vc_user_controls
        if hasattr(vc_users_list_ctrl, 'update'): vc_users_list_ctrl.update()

        # 更新语音频道主题显示
        topic_display = ui_manager.get_control('voice_channel_topic_display')
        if topic_display and previewing_voice_channel_id and voice_channels_data:
            for channel in voice_channels_data:
                if channel['id'] == previewing_voice_channel_id:
                    ch_name = channel['name']
                    prefix = "Voice:" if is_actively_in_voice_channel else "Preview:"
                    topic_display.value = f"{prefix} {ch_name}"
                    if hasattr(topic_display, 'update'): topic_display.update()
                    break
        
        # 确保按钮状态正确
        update_voice_panel_button_visibility()

    def switch_middle_panel_view(view_type: str, channel_name: str = ""):
        """切换中间面板视图（文字或语音）"""
        is_text_view = view_type == "text"
        chat_panel = ui_manager.get_control('chat_panel_content_group')
        voice_panel = ui_manager.get_control('voice_panel_content_group')
        
        if chat_panel:
            chat_panel.visible = is_text_view
            if hasattr(chat_panel, 'update'): chat_panel.update()
        
        if voice_panel:
            voice_panel.visible = not is_text_view
            if hasattr(voice_panel, 'update'): voice_panel.update()

        if is_text_view:
            current_chat_topic = ui_manager.get_control('current_chat_topic')
            if current_chat_topic:
                current_chat_topic.value = f"Chat - {channel_name}"
                if hasattr(current_chat_topic, 'update'): current_chat_topic.update()
        
        # 语音视图的主题显示由update_voice_channel_user_list_ui处理
        
        # 切换视图后更新按钮可见性
        update_voice_panel_button_visibility()

    async def select_text_channel(page_ref: ft.Page, channel_id: int, channel_name: str):
        """选择文字频道"""
        global current_text_channel_id, current_chat_messages_data, oldest_message_id_loaded
        global has_more_older_messages_to_load, is_loading_older_messages
        
        chat_panel = ui_manager.get_control('chat_panel_content_group')
        # 如果已经在这个文字频道并且视图可见，不做任何操作
        if current_text_channel_id == channel_id and chat_panel and chat_panel.visible:
            return

        print(f"选择文本频道: {channel_name} (ID: {channel_id})")
        current_text_channel_id = channel_id
        
        # 重置聊天消息状态
        current_chat_messages_data.clear()
        oldest_message_id_loaded = None
        has_more_older_messages_to_load = False
        is_loading_older_messages = False

        # 切换中间面板到文字视图
        switch_middle_panel_view("text", channel_name)
        
        # 清空消息视图
        chat_messages_view = ui_manager.get_control('chat_messages_view')
        if chat_messages_view:
            chat_messages_view.controls.clear()
            if hasattr(chat_messages_view, 'update'): chat_messages_view.update()
            
        # 向服务器发送加入文字频道的事件
        if sio_client and sio_client.connected:
            try:
                await sio_client.emit('join_text_channel', {'channel_id': channel_id})
            except Exception as e:
                print(f"发送join_text_channel事件错误: {e}")

        # 更新顶部栏，显示当前语音状态
        if is_actively_in_voice_channel and current_voice_channel_id:
            vc_name = "未知语音频道"
            for channel in voice_channels_data:
                if channel['id'] == current_voice_channel_id:
                    vc_name = channel['name']
                    break
            
            current_voice_channel_text = ui_manager.get_control('current_voice_channel_text')
            if current_voice_channel_text:
                current_voice_channel_text.value = f"Voice: {vc_name}"
                if hasattr(current_voice_channel_text, 'update'): current_voice_channel_text.update()
        elif previewing_voice_channel_id:
            # 如果只是预览语音频道，且选择了文本频道，顶栏应该显示"未加入语音"
            current_voice_channel_text = ui_manager.get_control('current_voice_channel_text')
            if current_voice_channel_text:
                current_voice_channel_text.value = "Not in voice"
                if hasattr(current_voice_channel_text, 'update'): current_voice_channel_text.update()
        else:
            current_voice_channel_text = ui_manager.get_control('current_voice_channel_text')
            if current_voice_channel_text:
                current_voice_channel_text.value = "Not in voice"
                if hasattr(current_voice_channel_text, 'update'): current_voice_channel_text.update()

        if hasattr(page_ref, 'update'): page_ref.update()

    async def select_voice_channel(page_ref: ft.Page, channel_id: int, channel_name: str):
        """选择语音频道"""
        global previewing_voice_channel_id, is_actively_in_voice_channel
        global current_voice_channel_active_users, current_text_channel_id, current_voice_channel_id

        print(f"--- select_voice_channel START for {channel_name} (ID: {channel_id}) ---")
        print(f"当前状态: is_active={is_actively_in_voice_channel}, current_vc_id={current_voice_channel_id}, preview_vc_id={previewing_voice_channel_id}")

        voice_panel = ui_manager.get_control('voice_panel_content_group')

        # 情况1: 重新选择当前已经加入的语音频道
        if is_actively_in_voice_channel and current_voice_channel_id == channel_id:
            print(f"重新选择已加入的语音频道: {channel_name} (ID: {channel_id})")
            previewing_voice_channel_id = channel_id  # 确保预览ID与活动频道一致

            if not (voice_panel and voice_panel.visible):  # 如果语音面板不可见，显示它
                switch_middle_panel_view("voice", channel_name)
            # 刷新活动频道的语音UI详情
            update_voice_channel_user_list_ui()
            if hasattr(page_ref, 'update'): page_ref.update()
            print(f"--- select_voice_channel END (already active) for {channel_name} ---")
            return

        # 情况2: 重新选择当前正在预览的语音频道
        if not is_actively_in_voice_channel and previewing_voice_channel_id == channel_id:
            print(f"重新选择正在预览的语音频道: {channel_name} (ID: {channel_id})")

            if not (voice_panel and voice_panel.visible):  # 如果语音面板不可见，显示它
                switch_middle_panel_view("voice", channel_name)
            # 刷新预览频道的语音UI详情
            update_voice_channel_user_list_ui()
            if hasattr(page_ref, 'update'): page_ref.update()
            print(f"--- select_voice_channel END (already previewing) for {channel_name} ---")
            return
            
        # 情况3: 选择一个新的语音频道
        print(f"选择新的语音频道进行预览: {channel_name} (ID: {channel_id})")
        
        # 离开当前的语音频道（如果有）
        # called_from_select_new_voice=True确保我们不会在切换预览时完全清除状态
        # 也不会在离开活动频道预览另一个频道时切换到文本视图
        if is_actively_in_voice_channel and current_voice_channel_id is not None and current_voice_channel_id != channel_id:
            print(f"在选择新语音频道前离开当前活动语音频道 {current_voice_channel_id}")
            await _leave_current_voice_channel_if_any(page_ref, called_from_select_new_voice=True)
            is_actively_in_voice_channel = False
            current_voice_channel_id = None
        elif not is_actively_in_voice_channel and previewing_voice_channel_id is not None and previewing_voice_channel_id != channel_id:
            print(f"在选择新语音频道前离开当前预览的语音频道 {previewing_voice_channel_id}")
            await _leave_current_voice_channel_if_any(page_ref, called_from_select_new_voice=True)

        # 设置新选择频道的预览
        previewing_voice_channel_id = channel_id
        is_actively_in_voice_channel = False  # 选择新频道始终从预览开始
        current_voice_channel_id = None       # 还未主动加入此新频道
        current_text_channel_id = None        # 选择语音频道意味着焦点在语音上，清除文本频道上下文
        current_voice_channel_active_users.clear()  # 清除新预览的用户，服务器将发送新列表

        print(f"[DEBUG] 设置新预览: is_active={is_actively_in_voice_channel}, preview_id={previewing_voice_channel_id}, current_vc_id={current_voice_channel_id}")

        # 更新顶部栏
        current_voice_channel_text = ui_manager.get_control('current_voice_channel_text')
        if current_voice_channel_text:
            current_voice_channel_text.value = f"Preview: {channel_name}"
            if hasattr(current_voice_channel_text, 'update'): current_voice_channel_text.update()

        # 切换到语音面板视图
        switch_middle_panel_view("voice", channel_name)
        
        # 预览阶段不向服务器发送join_voice_channel事件，确认加入时才发送
        
        # 更新UI（按钮将显示"加入"，主题前缀为"Preview:"）
        update_voice_channel_user_list_ui()
        
        if hasattr(page_ref, 'update'): page_ref.update()
        print(f"--- select_voice_channel END (new preview setup) for {channel_name} ---")

    async def _leave_current_voice_channel_if_any(page_ref: ft.Page, called_from_select_new_voice: bool = False):
        """
        处理离开当前活动或预览的语音频道。
        如果called_from_select_new_voice为True，表示我们将要选择一个新的语音频道，
        所以不切换中间面板到文本，也不清除previewing_voice_channel_id。
        """
        global current_voice_channel_id, previewing_voice_channel_id, is_actively_in_voice_channel, current_voice_channel_active_users
        
        channel_id_to_leave_on_server = None
        was_actively_in_voice = is_actively_in_voice_channel

        # 只有当我们主动加入频道时才需要告诉服务器离开
        if was_actively_in_voice and current_voice_channel_id is not None:
            channel_id_to_leave_on_server = current_voice_channel_id
            print(f"用户活跃在语音频道 {current_voice_channel_id}. 准备在服务器上离开.")

        if sio_client and sio_client.connected and channel_id_to_leave_on_server is not None:
            try:
                print(f"客户端发送leave_voice_channel事件，channel_id: {channel_id_to_leave_on_server}")
                await sio_client.emit('leave_voice_channel', {'channel_id': channel_id_to_leave_on_server})
            except Exception as e:
                print(f"发送leave_voice_channel事件错误: {e}")
        
        # 如果之前是活跃状态，停止音频流
        if was_actively_in_voice:
            await audio_manager.stop_audio_stream_if_running()
            await audio_manager.stop_audio_playback_stream_if_running()
            print("已停止音频流")

        is_actively_in_voice_channel = False
        current_voice_channel_id = None  # 离开活跃状态时总是重置

        if not called_from_select_new_voice:  # 如果是true，新的预览ID将由调用者设置
            previewing_voice_channel_id = None
        
        current_voice_channel_active_users.clear()
        
        # UI更新
        current_voice_channel_text = ui_manager.get_control('current_voice_channel_text')
        if current_voice_channel_text:
            current_voice_channel_text.value = "Not in voice"
            if hasattr(current_voice_channel_text, 'update'): current_voice_channel_text.update()

        update_voice_channel_user_list_ui()  # 这将清除列表并通过其内部调用更新按钮

        if not called_from_select_new_voice and not was_actively_in_voice:  # 如果只是预览且现在离开预览
            # 如果我们只是在预览并且现在离开预览（不是切换到另一个语音频道），
            # 那么切换到可用的默认文本视图。
            current_text_channel_name = "Select a text channel"
            if current_text_channel_id:
                for channel in text_channels_data:
                    if channel['id'] == current_text_channel_id:
                        current_text_channel_name = channel['name']
                        break
            else:  # 如果有的话，选择第一个文本频道
                if text_channels_data and len(text_channels_data) > 0:
                    first_text_ch = text_channels_data[0]
                    current_text_channel_id = first_text_ch['id']
                    current_text_channel_name = first_text_ch['name']
            switch_middle_panel_view("text", current_text_channel_name)

        if hasattr(page_ref, 'update'): page_ref.update()
        print(f"_leave_current_voice_channel_if_any执行完毕. called_from_select_new_voice: {called_from_select_new_voice}")

    async def handle_confirm_join_voice_button_click(page_ref: ft.Page):
        """处理确认加入语音按钮点击"""
        global is_actively_in_voice_channel, current_voice_channel_id, previewing_voice_channel_id
        
        if previewing_voice_channel_id is None:
            print("错误: 点击确认加入，但没有正在预览的频道.")
            return

        print(f"确认加入语音频道ID: {previewing_voice_channel_id}")
        is_actively_in_voice_channel = True
        current_voice_channel_id = previewing_voice_channel_id  # 这现在是活跃频道
        # previewing_voice_channel_id保持不变，因为我们在活跃于正在预览的频道
        
        # 重置麦克风状态（将在音频功能实现时添加）
        # 获取音量滑块值
        volume_slider = ui_manager.get_control('voice_settings_input_volume_slider')
        current_volume = volume_slider.value if volume_slider else 100
        
        # 只有在音量大于0时才重置麦克风为未静音状态
        if current_volume > 0:
            audio_manager.is_mic_muted = False
            print("重置麦克风为未静音状态")
        
        # 获取频道名称
        vc_name = "Unknown"
        for channel in voice_channels_data:
            if channel['id'] == current_voice_channel_id:
                vc_name = channel['name']
                break
        
        # 更新顶部栏
        current_voice_channel_text = ui_manager.get_control('current_voice_channel_text')
        if current_voice_channel_text:
            current_voice_channel_text.value = f"Voice: {vc_name}"
            if hasattr(current_voice_channel_text, 'update'): current_voice_channel_text.update()
        
        # 向服务器发送加入语音频道事件
        if sio_client and sio_client.connected and current_voice_channel_id is not None:
            try:
                print(f"客户端发送join_voice_channel事件，channel_id: {current_voice_channel_id}")
                await sio_client.emit('join_voice_channel', {'channel_id': current_voice_channel_id})
            except Exception as e:
                print(f"发送join_voice_channel事件错误: {e}")
        
        # 启动音频流处理
        if audio_manager.selected_input_device_id is not None:
            await audio_manager.start_audio_stream(page_ref, audio_manager.selected_input_device_id)
            print(f"已启动音频输入流，设备ID: {audio_manager.selected_input_device_id}")
        else:
            print("没有选择输入设备，无法启动音频流")
            ui_manager.update_status_text("请在设置中选择输入设备以发送语音")
        
        # 启动音频播放流
        await audio_manager.start_audio_playback_stream(page_ref, audio_manager.selected_output_device_id)
        
        # 加入语音频道后，立即发送当前麦克风状态
        if sio_client and sio_client.connected and current_voice_channel_id is not None:
            try:
                # 根据当前逻辑静音状态发送麦克风状态
                is_unmuted = not audio_manager.is_logically_muted
                print(f"发送初始麦克风状态: is_unmuted={is_unmuted}")
                await sio_client.emit('user_microphone_status', {
                    'channel_id': current_voice_channel_id,
                    'is_unmuted': is_unmuted
                })
            except Exception as e:
                print(f"发送麦克风状态错误: {e}")
        
        # 更新UI元素
        update_voice_channel_user_list_ui()
        if hasattr(page_ref, 'update'): page_ref.update()
        print(f"成功加入语音频道: {vc_name} (ID: {current_voice_channel_id})")

    async def handle_leave_voice_click(page_ref: ft.Page):
        """处理离开语音按钮点击"""
        global is_actively_in_voice_channel, current_voice_channel_id, previewing_voice_channel_id
        
        if not is_actively_in_voice_channel or current_voice_channel_id is None:
            print("错误: 点击离开语音，但未主动加入任何语音频道.")
            return

        channel_id_being_left = current_voice_channel_id
        channel_name_being_left = "未知语音频道"
        for channel in voice_channels_data:
            if channel['id'] == channel_id_being_left:
                channel_name_being_left = channel['name']
                break

        print(f"离开语音频道: {channel_name_being_left} (ID: {channel_id_being_left})")

        # 向服务器发送离开语音频道事件
        if sio_client and sio_client.connected:
            try:
                await sio_client.emit('leave_voice_channel', {'channel_id': channel_id_being_left})
            except Exception as e:
                print(f"发送leave_voice_channel事件错误: {e}")

        # 停止音频流
        await audio_manager.stop_audio_stream_if_running()
        await audio_manager.stop_audio_playback_stream_if_running()
        
        is_actively_in_voice_channel = False
        # current_voice_channel_id现在为None（不再主动加入）
        # previewing_voice_channel_id保持为channel_id_being_left（我们返回到预览状态）
        previewing_voice_channel_id = channel_id_being_left
        current_voice_channel_id = None  # 显式设置为None

        # 更新顶部栏
        current_voice_channel_text = ui_manager.get_control('current_voice_channel_text')
        if current_voice_channel_text:
            current_voice_channel_text.value = f"Preview: {channel_name_being_left}"
            if hasattr(current_voice_channel_text, 'update'): current_voice_channel_text.update()
        
        # 更新UI
        update_voice_channel_user_list_ui()
        
        if hasattr(page_ref, 'update'): page_ref.update()
        print(f"返回到语音频道预览模式: {channel_name_being_left}")

    # --- 初始化所有管理器 ---
    ui_manager = UIManager(page)
    audio_manager = AudioManager()
    network_manager = NetworkManager(CONFIG_FILE)
    message_manager = MessageManager()
    
    # 设置页面事件循环供AudioManager使用
    audio_manager.set_page_loop(asyncio.get_event_loop())
    
    # --- 创建SSL上下文和HTTP会话 ---
    # 不再自己创建共享会话，让NetworkManager管理它
    await network_manager.create_http_session()
    await network_manager.create_socketio_client()
    
    # 获取NetworkManager的会话和客户端
    shared_aiohttp_session = network_manager.shared_aiohttp_session
    sio_client = network_manager.sio_client
    
    # 手动注册Socket.IO事件处理函数
    if sio_client:
        sio_client.on('older_messages_loaded', older_messages_loaded)
        sio_client.on('load_historical_messages', load_historical_messages)
    
    # --- 设置管理器之间的回调函数 ---
    # AudioManager回调
    audio_manager.set_callback('update_mic_test_bar', _update_mic_test_bar_callback)
    audio_manager.set_callback('send_audio_data', send_audio_data)
    audio_manager.set_callback('on_speaking_status_change', _update_speaking_status_async)
    
    # NetworkManager回调
    network_manager.set_callback('on_socket_connect', on_socket_connect_handler)
    network_manager.set_callback('on_socket_disconnect', lambda: print("Socket.IO断开连接"))
    network_manager.set_callback('on_socket_connect_error', on_socket_connect_error_handler)
    network_manager.set_callback('on_new_message', on_new_message)
    network_manager.set_callback('on_voice_channel_users', on_voice_channel_users)
    network_manager.set_callback('on_user_joined_voice', on_user_joined_voice)
    network_manager.set_callback('on_user_left_voice', on_user_left_voice)
    network_manager.set_callback('on_user_speaking', on_user_speaking)
    network_manager.set_callback('on_user_mic_status_updated', on_user_mic_status_updated)
    network_manager.set_callback('on_user_voice_activity', on_user_voice_activity)
    network_manager.set_callback('on_voice_data_stream_chunk', on_voice_data_stream_chunk)
    network_manager.set_callback('on_server_user_list_update', on_server_user_list_update)
    
    # MessageManager回调
    message_manager.set_callback('update_messages_ui', lambda: print("更新消息UI"))
    
    # UIManager回调设置函数
    def setup_channel_callbacks():
        """设置频道相关回调"""
        # 文本频道选择回调
        async def on_text_channel_selected_async(e):
            channel_id, channel_name = e.control.data, e.control.title.value
            await select_text_channel(page, channel_id, channel_name)
        
        ui_manager.set_callback('on_text_channel_selected', on_text_channel_selected_async)
        
        # 语音频道选择回调
        async def on_voice_channel_selected_async(e):
            channel_id, channel_name = e.control.data, e.control.title.value
            await select_voice_channel(page, channel_id, channel_name)
        
        ui_manager.set_callback('on_voice_channel_selected', on_voice_channel_selected_async)
        
        # 确认加入语音频道回调
        async def on_confirm_join_voice_async(e):
            await handle_confirm_join_voice_button_click(page)
        
        ui_manager.set_callback('on_confirm_join_voice', on_confirm_join_voice_async)
        
        # 离开语音频道回调
        async def on_leave_voice_async(e):
            await handle_leave_voice_click(page)
        
        ui_manager.set_callback('on_leave_voice', on_leave_voice_async)
    
    # 设置回调
    setup_channel_callbacks()
    
    # 设置UIManager的基本回调
    def show_register_view(e):
        ui_manager.show_view('register_view')
    
    def show_server_config_view(e):
        # 加载当前配置到输入框
        ui_manager.set_control_value('server_ip_field', SERVER_ADDRESS)
        ui_manager.set_control_value('server_port_field', str(SERVER_PORT))
        ui_manager.show_view('server_config_view')
    
    def back_to_login_view(e):
        ui_manager.show_view('login_view')
    
    async def handle_login(e, remember_me=False):
        """处理登录"""
        username = ui_manager.get_control_value('username_field')
        password = ui_manager.get_control_value('password_field')
        remember_me = ui_manager.get_control('remember_me_checkbox').value
        
        if not username or not password:
            ui_manager.update_status_text("请输入用户名和密码")
            return

        ui_manager.update_status_text("正在登录...")
        
        try:
            # 使用NetworkManager进行登录
            result = await network_manager.login(username, password)
            
            if result.get('success'):
                global current_user_info, text_channels_data, voice_channels_data
                current_user_info = result.get('user')
                
                ui_manager.set_control_value('top_bar_username_text', f"用户: {username}")
                ui_manager.show_view('main_app_view')
                ui_manager.update_status_text("登录成功！正在连接服务...")
                
                # 保存登录信息（如果选择了"记住我"）
                if remember_me:
                    config_loader.update_login_info(username, password, True)
                
                # 登录成功后，主动连接Socket.IO
                if current_user_info:
                    # 不需要显式提取token，让网络管理器直接连接Socket.IO
                    # 如果服务器使用cookie进行认证，HTTP会话已经有了认证信息
                    print("登录成功，正在连接Socket.IO...")
                    async def connect_sio_task():
                        connected = await network_manager.connect_socketio()
                        if not connected:
                            ui_manager.update_status_text("Socket.IO连接失败，请检查网络和服务器设置")
                        else:
                            ui_manager.update_status_text("Socket.IO连接成功，正在获取频道列表...")
                    
                    await connect_sio_task()  # 直接等待连接完成，而不是创建异步任务
                    
                    # 加载音频设备
                    print("正在初始化音频设备...")
                    await populate_audio_devices()
                else:
                    print("错误：无法连接Socket.IO，用户信息未初始化")
                    ui_manager.update_status_text("登录凭据错误或Socket客户端问题")

            else:
                    ui_manager.update_status_text(f"登录失败: {result.get('message', '未知错误')}")
        except Exception as e:
                ui_manager.update_status_text(f"登录错误: {str(e)}")
    
    async def handle_register(e):
        """处理注册"""
        username = ui_manager.get_control_value('reg_username_field')
        password = ui_manager.get_control_value('reg_password_field')
        confirm_password = ui_manager.get_control_value('reg_confirm_password_field')
        invite_code = ui_manager.get_control_value('reg_invite_code_field')
        
        if not all([username, password, confirm_password, invite_code]):
            ui_manager.set_control_value('register_page_status_text', "请填写所有字段")
            return

        if password != confirm_password:
            ui_manager.set_control_value('register_page_status_text', "密码不匹配")
            return

        ui_manager.set_control_value('register_page_status_text', "正在注册...")
        
        try:
            result = await network_manager.register(username, password, invite_code)
            
            if result.get('success'):
                ui_manager.set_control_value('register_page_status_text', "注册成功！返回登录页面...")
                # 清空注册表单
                ui_manager.set_control_value('reg_username_field', "")
                ui_manager.set_control_value('reg_password_field', "")
                ui_manager.set_control_value('reg_confirm_password_field', "")
                ui_manager.set_control_value('reg_invite_code_field', "")
                # 2秒后返回登录页面
                await asyncio.sleep(2)
                ui_manager.show_view('login_view')
            else:
                    ui_manager.set_control_value('register_page_status_text', f"注册失败: {result.get('message', '未知错误')}")
        except Exception as e:
            ui_manager.set_control_value('register_page_status_text', f"注册错误: {str(e)}")

    async def handle_save_server_config(e):
        """保存服务器配置"""
        server_ip = ui_manager.get_control_value('server_ip_field')
        server_port_str = ui_manager.get_control_value('server_port_field')
        
        if not server_ip or not server_port_str:
            ui_manager.set_control_value('server_config_status_text', "请填写完整的服务器信息")
            return

        try:
            server_port = int(server_port_str)
            
            # 更新配置
            global SERVER_ADDRESS, SERVER_PORT
            SERVER_ADDRESS = server_ip
            SERVER_PORT = server_port
            
            network_manager.update_server_config(server_ip, server_port)
            
            ui_manager.set_control_value('server_config_status_text', "配置保存成功！")
            
            # 重新初始化网络连接
            await network_manager.close_http_session()
            await network_manager.create_http_session()
            if network_manager.sio_client and network_manager.sio_client.connected:
                await network_manager.disconnect_socketio()
            await network_manager.create_socketio_client()
            
            # 更新全局引用
            shared_aiohttp_session = network_manager.shared_aiohttp_session
            sio_client = network_manager.sio_client
            
            # 2秒后返回登录页面
            await asyncio.sleep(2)
            ui_manager.show_view('login_view')
            
        except ValueError:
            ui_manager.set_control_value('server_config_status_text', "端口必须是数字")
        except Exception as e:
            ui_manager.set_control_value('server_config_status_text', f"保存配置失败: {str(e)}")
    
    def handle_logout(e):
        """处理登出"""
        global current_user_info
        
        # 断开Socket.IO连接
        if network_manager.sio_client and network_manager.sio_client.connected:
            page.run_task(network_manager.disconnect_socketio)
        
        current_user_info = None
        ui_manager.show_view('login_view')
        ui_manager.update_status_text("已登出")
        
        # 用户登出时，如果之前勾选了"记住我"，则清除保存的登录信息和状态
        config_loader.reset_login_info() # 清除保存的用户名、密码和remember_me状态
        remember_me_checkbox = ui_manager.get_control('remember_me_checkbox')
        if remember_me_checkbox:
            remember_me_checkbox.value = False
            if hasattr(remember_me_checkbox, 'update'):
                remember_me_checkbox.update()
        
        username_field = ui_manager.get_control('username_field')
        password_field = ui_manager.get_control('password_field')
        if username_field:
            username_field.value = ""
            if hasattr(username_field, 'update'):
                username_field.update()
        if password_field:
            password_field.value = ""
            if hasattr(password_field, 'update'):
                password_field.update()
    
    # 聊天消息相关功能
    def _create_chat_message_control(msg_data):
        """创建单个聊天消息控件"""
        return ft.Text(
            f"[{msg_data.get('timestamp')}] {msg_data.get('username', 'Unknown')}: {msg_data.get('content')}",
            selectable=True,
            font_family="Consolas",
            color=COLOR_TEXT_ON_WHITE
        )

    def _render_chat_messages():
        """渲染聊天消息列表到UI"""
        global current_chat_messages_data, has_more_older_messages_to_load, is_loading_older_messages
        chat_view = ui_manager.get_control('chat_messages_view')
        if not chat_view: return

        chat_view.controls.clear()  # 清除现有视图控件

        # 如果有更多历史消息可加载，添加"加载更多"按钮
        if has_more_older_messages_to_load and not is_loading_older_messages:
            load_more_button = ft.TextButton(
                "加载更早的消息...",
                icon=ft.Icons.ARROW_UPWARD,
                on_click=lambda e: page.run_task(request_older_messages_from_ui),
                style=ft.ButtonStyle(color=COLOR_PRIMARY)
            )
            chat_view.controls.append(load_more_button)
        elif is_loading_older_messages:  # 显示加载指示器
            loading_indicator = ft.Row(
                [ft.ProgressRing(width=16, height=16, stroke_width=2), ft.Text("加载中...", color=COLOR_TEXT_ON_WHITE)],
                alignment=ft.MainAxisAlignment.CENTER
            )
            chat_view.controls.append(loading_indicator)

        # 添加所有消息
        for msg_data in current_chat_messages_data:
            chat_view.controls.append(_create_chat_message_control(msg_data))
        
        if hasattr(chat_view, 'update'): chat_view.update()

    async def request_older_messages_from_ui(e=None):
        """从UI触发请求加载更早的消息"""
        global is_loading_older_messages, oldest_message_id_loaded, current_text_channel_id

        if is_loading_older_messages or oldest_message_id_loaded is None or current_text_channel_id is None or not sio_client or not sio_client.connected:
            if is_loading_older_messages:
                print("[LOAD_MORE] 已经在加载更早的消息")
            if oldest_message_id_loaded is None:
                print("[LOAD_MORE] 没有最早消息ID，无法请求更早的消息")
            return

        print(f"[LOAD_MORE] 请求频道 {current_text_channel_id} 中消息ID {oldest_message_id_loaded} 之前的消息")
        is_loading_older_messages = True
        _render_chat_messages()  # 更新UI显示加载指示器
        if hasattr(page, 'update'): page.update()

        try:
            await sio_client.emit('request_older_messages', {
                'channel_id': current_text_channel_id,
                'before_message_id': oldest_message_id_loaded,
                'limit': OLDER_MESSAGE_LOAD_COUNT
            })
        except Exception as ex:
            print(f"[LOAD_MORE] 发送request_older_messages事件错误: {ex}")
            is_loading_older_messages = False  # 重置标志
            _render_chat_messages()  # 重新渲染以移除加载指示器
            if hasattr(page, 'update'): page.update()

    async def handle_send_message(e):
        """处理发送消息"""
        message_input = ui_manager.get_control('message_input_field')
        if not message_input: return
        
        message_content = message_input.value.strip()
        if not message_content or not current_text_channel_id or not sio_client or not sio_client.connected:
            return
        
        try:
            await sio_client.emit('send_message', {
                'channel_id': current_text_channel_id,
                'message': message_content
            })
            # 清空输入框
            message_input.value = ""
            if hasattr(message_input, 'update'): message_input.update()
        except Exception as e:
            print(f"发送消息失败: {e}")
            ui_manager.update_status_text(f"发送消息失败: {str(e)}")
    
    # 设置UI回调
    ui_manager.set_callback('on_login', handle_login)
    ui_manager.set_callback('on_show_register', show_register_view)
    ui_manager.set_callback('on_show_server_config', show_server_config_view)
    ui_manager.set_callback('on_back_to_login', back_to_login_view)
    ui_manager.set_callback('on_register', handle_register)
    ui_manager.set_callback('on_save_server_config', handle_save_server_config)
    ui_manager.set_callback('on_logout', handle_logout)
    ui_manager.set_callback('on_send_message', handle_send_message)
    
    # 音频设备相关函数
    async def populate_audio_devices():
        """获取并填充音频设备列表"""
        print("正在获取音频设备列表...")
        
        input_dropdown = ui_manager.get_control('voice_settings_input_device_dropdown')
        output_dropdown = ui_manager.get_control('voice_settings_output_device_dropdown')
        
        if not input_dropdown or not output_dropdown:
            print("找不到音频设备下拉框控件")
            return
            
        # 获取保存的设备ID
        saved_input_id = config_loader.get("saved_input_device_id")
        saved_output_id = config_loader.get("saved_output_device_id")
        print(f"加载保存的设备ID - 输入: {saved_input_id}, 输出: {saved_output_id}")
        
        # 将保存的ID转换为整数
        if saved_input_id is not None:
            try:
                saved_input_id = int(saved_input_id)
            except ValueError:
                print(f"警告: 无法将saved_input_device_id '{saved_input_id}'转换为整数，忽略此值")
                saved_input_id = None
                
        if saved_output_id is not None:
            try:
                saved_output_id = int(saved_output_id)
            except ValueError:
                print(f"警告: 无法将saved_output_device_id '{saved_output_id}'转换为整数，忽略此值")
                saved_output_id = None
        
        # 从AudioManager获取设备列表
        try:
            # 使用同步方法获取设备列表
            input_devices, output_devices = audio_manager.get_audio_devices_sync()
            
            print(f"找到输入设备: {len(input_devices)}个")
            print(f"找到输出设备: {len(output_devices)}个")
            
            # 清空现有选项
            input_dropdown.options.clear()
            output_dropdown.options.clear()
            
            # 设置输入设备选项
            applied_saved_input = False
            if not input_devices:
                input_dropdown.options.append(ft.dropdown.Option(key="-1", text="未找到输入设备"))
                input_dropdown.value = "-1"
                audio_manager.selected_input_device_id = None
            else:
                for device in input_devices:
                    input_dropdown.options.append(ft.dropdown.Option(key=str(device['id']), text=device['name']))
                
                # 尝试应用保存的ID
                if saved_input_id is not None and any(device['id'] == saved_input_id for device in input_devices):
                    input_dropdown.value = str(saved_input_id)
                    audio_manager.selected_input_device_id = saved_input_id
                    applied_saved_input = True
                    print(f"应用已保存的输入设备ID: {saved_input_id}")
                
                if not applied_saved_input:
                    # 默认选择第一个设备或默认设备
                    default_input = next((d for d in input_devices if d['name'].startswith("(Default)")), None)
                    if default_input:
                        input_dropdown.value = str(default_input['id'])
                        audio_manager.selected_input_device_id = default_input['id']
                    elif input_devices:
                        input_dropdown.value = str(input_devices[0]['id'])
                        audio_manager.selected_input_device_id = input_devices[0]['id']
                    print(f"默认/回退输入设备ID: {audio_manager.selected_input_device_id}")
            
            # 设置输出设备选项
            applied_saved_output = False
            if not output_devices:
                output_dropdown.options.append(ft.dropdown.Option(key="-1", text="未找到输出设备"))
                output_dropdown.value = "-1"
                audio_manager.selected_output_device_id = None
            else:
                for device in output_devices:
                    output_dropdown.options.append(ft.dropdown.Option(key=str(device['id']), text=device['name']))
                
                # 尝试应用保存的ID
                if saved_output_id is not None and any(device['id'] == saved_output_id for device in output_devices):
                    output_dropdown.value = str(saved_output_id)
                    audio_manager.selected_output_device_id = saved_output_id
                    applied_saved_output = True
                    print(f"应用已保存的输出设备ID: {saved_output_id}")
                
                if not applied_saved_output:
                    # 默认选择第一个设备或默认设备
                    default_output = next((d for d in output_devices if d['name'].startswith("(Default)")), None)
                    if default_output:
                        output_dropdown.value = str(default_output['id'])
                        audio_manager.selected_output_device_id = default_output['id']
                    elif output_devices:
                        output_dropdown.value = str(output_devices[0]['id'])
                        audio_manager.selected_output_device_id = output_devices[0]['id']
                    print(f"默认/回退输出设备ID: {audio_manager.selected_output_device_id}")
                    
            # 更新UI
            if hasattr(input_dropdown, 'update'): input_dropdown.update()
            if hasattr(output_dropdown, 'update'): output_dropdown.update()
            
        except Exception as e:
            print(f"填充音频设备下拉框时出错: {e}")
            input_dropdown.options = [ft.dropdown.Option(key="-1", text="加载设备时出错")]
            output_dropdown.options = [ft.dropdown.Option(key="-1", text="加载设备时出错")]
            input_dropdown.value = "-1"
            output_dropdown.value = "-1"
            
            if hasattr(input_dropdown, 'update'): input_dropdown.update()
            if hasattr(output_dropdown, 'update'): output_dropdown.update()
            
        if hasattr(page, 'update'): page.update()
        
    # 音频设备变更处理
    async def handle_input_device_change(e):
        """处理输入设备变更"""
        new_device_id = int(e.control.value) if e.control.value and e.control.value != "-1" else None
        audio_manager.selected_input_device_id = new_device_id
        print(f"选择了输入设备ID: {new_device_id}")
        
        # TODO: 如果在语音频道中，重启音频流
        
    async def handle_output_device_change(e):
        """处理输出设备变更"""
        new_device_id = int(e.control.value) if e.control.value and e.control.value != "-1" else None
        audio_manager.selected_output_device_id = new_device_id
        print(f"选择了输出设备ID: {new_device_id}")
        
        # TODO: 如果在语音频道中，重启音频播放
        
    async def handle_save_audio_settings(e):
        """保存音频设置"""
        input_id = audio_manager.selected_input_device_id
        output_id = audio_manager.selected_output_device_id
        
        config_loader.set("saved_input_device_id", input_id)
        config_loader.set("saved_output_device_id", output_id)
        config_loader.save_config()
        
        print(f"音频设置已保存。输入ID: {input_id}, 输出ID: {output_id}")
        ui_manager.update_status_text("音频设置已保存")
        
    # 注册音频设备相关回调
    ui_manager.set_callback('on_input_device_change', handle_input_device_change)
    ui_manager.set_callback('on_output_device_change', handle_output_device_change)
    ui_manager.set_callback('on_save_audio_settings', handle_save_audio_settings)
    
    # 麦克风测试相关函数
    async def handle_mic_test(e):
        """处理麦克风测试按钮点击"""
        mic_test_button = ui_manager.get_control('voice_settings_mic_test_button')
        mic_test_bar = ui_manager.get_control('voice_settings_mic_test_bar')
        
        if not mic_test_button or not mic_test_bar:
            print("找不到麦克风测试UI元素")
            return
            
        if audio_manager.is_mic_testing:  # 如果当前正在测试，则停止
            print("停止麦克风测试...")
            await audio_manager.stop_mic_test()
            
            mic_test_button.text = "开始麦克风测试"
            mic_test_button.icon = ft.Icons.PLAY_ARROW
            mic_test_bar.value = 0
            if hasattr(mic_test_button, 'update'): mic_test_button.update()
            if hasattr(mic_test_bar, 'update'): mic_test_bar.update()
            
        else:  # 开始测试
            if not audio_manager.selected_input_device_id:
                ui_manager.update_status_text("请先选择输入设备")
                return
                
            print("开始麦克风测试...")
            mic_test_button.text = "停止麦克风测试"
            mic_test_button.icon = ft.Icons.STOP
            if hasattr(mic_test_button, 'update'): mic_test_button.update()
            
            # 启动麦克风测试
            try:
                await audio_manager.start_mic_test(
                    page, 
                    audio_manager.selected_input_device_id, 
                    audio_manager.selected_output_device_id
                )
                
                # 创建更新UI的任务
                async def update_mic_test_bar():
                    while audio_manager.is_mic_testing:
                        volume = audio_manager.get_mic_test_volume()
                        mic_test_bar.value = volume
                        if hasattr(mic_test_bar, 'update'): mic_test_bar.update()
                        await asyncio.sleep(0.05)  # 每50ms更新一次
                        
                page.run_task(update_mic_test_bar)
                
            except Exception as e:
                print(f"启动麦克风测试失败: {e}")
                mic_test_button.text = "开始麦克风测试"
                mic_test_button.icon = ft.Icons.PLAY_ARROW
                if hasattr(mic_test_button, 'update'): mic_test_button.update()
                ui_manager.update_status_text(f"麦克风测试失败: {str(e)}")
    
    # 麦克风静音功能
    async def handle_mute_mic(e):
        """处理麦克风静音按钮点击"""
        mute_button = ui_manager.get_control('voice_settings_mute_button')
        if not mute_button:
            return
            
        # 切换静音状态
        audio_manager.is_mic_muted = not audio_manager.is_mic_muted
        
        # 检查是否需要同时处理音量为0的情况
        volume_slider = ui_manager.get_control('voice_settings_input_volume_slider')
        if volume_slider and volume_slider.value == 0 and not audio_manager.is_mic_muted:
            # 如果取消静音且音量为0，设置为默认非零音量
            volume_slider.value = int(audio_manager.DEFAULT_UNMUTE_VOLUME * 100)
            if hasattr(volume_slider, 'update'): volume_slider.update()
            
        # 更新逻辑静音状态（结合按钮和音量）
        await update_logical_mute_state()
        
        # 如果在语音频道中，向服务器发送麦克风状态
        await _update_and_send_mute_status(page)
    
    async def handle_input_volume_change(e):
        """处理输入音量滑块变化"""
        volume_slider = ui_manager.get_control('voice_settings_input_volume_slider')
        if not volume_slider:
            return
            
        # 如果音量调至0，自动将麦克风设为静音状态
        if volume_slider.value == 0 and not audio_manager.is_mic_muted:
            audio_manager.is_mic_muted = True
            
        # 更新逻辑静音状态
        await update_logical_mute_state()
        
        # 如果在语音频道中，向服务器发送麦克风状态
        await _update_and_send_mute_status(page)
    
    async def update_logical_mute_state():
        """更新逻辑静音状态并同步UI"""
        volume_slider = ui_manager.get_control('voice_settings_input_volume_slider')
        current_volume = volume_slider.value if volume_slider else 100
        
        # 确定逻辑静音状态（按钮静音或音量为0）
        new_logical_mute_state = audio_manager.is_mic_muted or (current_volume == 0)
        
        # 更新麦克风按钮UI
        mute_button = ui_manager.get_control('voice_settings_mute_button')
        if mute_button:
            mute_button.icon = ft.Icons.MIC_OFF if new_logical_mute_state else ft.Icons.MIC
            mute_button.tooltip = "取消静音" if new_logical_mute_state else "静音"
            if hasattr(mute_button, 'update'): mute_button.update()
            
        if new_logical_mute_state != audio_manager.is_logically_muted:
            audio_manager.is_logically_muted = new_logical_mute_state
            print(f"逻辑静音状态更改为: {audio_manager.is_logically_muted}")
    
    async def _update_and_send_mute_status(page_ref: ft.Page):
        """向服务器发送麦克风状态更新"""
        global sio_client, current_voice_channel_id, is_actively_in_voice_channel
        
        # 如果不在语音频道中或Socket.IO未连接，不发送状态
        if not is_actively_in_voice_channel or current_voice_channel_id is None or not sio_client or not sio_client.connected:
            return
        
        try:
            # 发送麦克风状态
            is_unmuted = not audio_manager.is_logically_muted
            print(f"向服务器发送麦克风状态: is_unmuted={is_unmuted}")
            await sio_client.emit('user_microphone_status', {
                'channel_id': current_voice_channel_id,
                'is_unmuted': is_unmuted
            })
        except Exception as e:
            print(f"发送麦克风状态错误: {e}")
            ui_manager.update_status_text(f"更新麦克风状态失败: {str(e)}")
    
    # 设置麦克风相关回调
    ui_manager.set_callback('on_mic_test', handle_mic_test)
    ui_manager.set_callback('on_mute_mic', handle_mute_mic)
    ui_manager.set_callback('on_input_volume_change', handle_input_volume_change)

    # 设置窗口大小和属性（UIManager已经设置了基本属性）
    page.window_width = 1200
    page.window_height = 800
    page.window_resizable = True
    page.window_maximizable = True
    page.window_min_width = 800
    page.window_min_height = 600
    page.window_max_width = 1920
    page.window_max_height = 1080
    page.window_center = True

    # 设置图标
    base_dir = os.path.dirname(os.path.abspath(__file__)) 
    icon_path = os.path.join(base_dir, "assets", "icon.ico") 
    page.window.icon = icon_path 

    # 设置页面控件
    ui_manager.setup_page_controls()
    
    # 显示登录界面
    ui_manager.show_view('login_view')

    # --- 自动登录逻辑 ---
    remember_me = config_loader.get("remember_me", False)
    saved_username = config_loader.get("username", "")
    saved_password = config_loader.get("password", "")
    
    if remember_me and saved_username and saved_password:
        print("检测到已保存的登录信息，尝试自动登录...")
        # 尝试自动登录
        ui_manager.set_control_value('username_field', saved_username)
        ui_manager.set_control_value('password_field', saved_password)
        ui_manager.get_control('remember_me_checkbox').value = True
        
        # 调用登录处理函数
        async def auto_login():
            await handle_login(None, remember_me=True)
        page.run_task(auto_login)

    # --- 应用关闭时的清理 ---
    async def on_close(e):
        print("应用正在关闭，清理资源...")
        # 清理所有网络连接和资源
        await network_manager.cleanup()
        print("资源清理完成")
    
    page.on_close = on_close

    print("ARC-Speak Client 启动成功！管理器已初始化。")
    page.update()

if __name__ == "__main__":
    ft.app(target=main) 