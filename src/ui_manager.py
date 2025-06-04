import flet as ft
import asyncio
from color_palette import *

class UIManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.controls = {}
        self.callbacks = {}
        self.text_channels_data = []  # 初始化为空列表
        self.voice_channels_data = []  # 初始化为空列表
        self._setup_page()
        self._create_controls()
        
    def _setup_page(self):
        """设置页面基本属性"""
        self.page.title = "ARC SPEAK"
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
        self.page.window.icon = icon_path
        self.page.padding = 0
        self.page.bgcolor = COLOR_BACKGROUND_WHITE
        self.page.theme_mode = ft.ThemeMode.LIGHT
    
    def set_callback(self, name: str, callback):
        """设置回调函数"""
        self.callbacks[name] = callback
    
    def get_callback(self, name: str):
        """获取回调函数"""
        return self.callbacks.get(name)
    
    def _create_controls(self):
        """创建所有UI控件"""
        self._create_login_controls()
        self._create_register_controls()
        self._create_server_config_controls()
        self._create_main_app_controls()
        self._create_layouts()
    
    def _create_login_controls(self):
        """创建登录相关控件"""
        self.controls['status_text'] = ft.Text(color=COLOR_STATUS_TEXT_MUTED)
        
        self.controls['remember_me_checkbox'] = ft.Checkbox(
            label="记住我", 
            value=False,
            check_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE), 
            fill_color=COLOR_DIVIDER_ON_WHITE
        )
        
        self.controls['username_field'] = ft.TextField(
            label="Username", 
            width=300, 
            autofocus=True,
            border_color=COLOR_BORDER, 
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['password_field'] = ft.TextField(
            label="Password", 
            password=True, 
            can_reveal_password=True, 
            width=300,
            border_color=COLOR_BORDER, 
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['login_button'] = ft.ElevatedButton(
            text="Login", 
            width=150,
            bgcolor=COLOR_PRIMARY, 
            color=COLOR_BUTTON_TEXT,
            on_click=self._on_login_click
        )
        
        self.controls['register_button'] = ft.ElevatedButton(
            text="Register", 
            width=150,
            bgcolor=COLOR_PRIMARY, 
            color=COLOR_BUTTON_TEXT,
            on_click=self._on_show_register_click
        )
        
        self.controls['server_settings_button'] = ft.IconButton(
            icon=ft.Icons.SETTINGS,
            tooltip="服务器设置",
            on_click=self._on_show_server_config_click,
            icon_color=COLOR_PRIMARY
        )
    
    def _create_register_controls(self):
        """创建注册相关控件"""
        self.controls['reg_username_field'] = ft.TextField(
            label="Username", 
            width=300, 
            autofocus=True,
            border_color=COLOR_BORDER, 
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['reg_password_field'] = ft.TextField(
            label="Password", 
            password=True, 
            can_reveal_password=True, 
            width=300,
            border_color=COLOR_BORDER, 
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['reg_confirm_password_field'] = ft.TextField(
            label="Confirm Password", 
            password=True, 
            can_reveal_password=True, 
            width=300,
            border_color=COLOR_BORDER, 
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['reg_invite_code_field'] = ft.TextField(
            label="Invite Code", 
            width=300,
            border_color=COLOR_BORDER, 
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['register_page_status_text'] = ft.Text(
            color=COLOR_STATUS_TEXT_MUTED, 
            text_align=ft.TextAlign.CENTER
        )
        
        self.controls['actual_register_button'] = ft.ElevatedButton(
            text="Register",
            on_click=self._on_register_click,
            width=150,
            bgcolor=COLOR_PRIMARY, 
            color=COLOR_BUTTON_TEXT
        )
        
        self.controls['back_to_login_button'] = ft.ElevatedButton(
            text="Back to Login",
            on_click=self._on_back_to_login_click,
            width=150,
            bgcolor=ft.Colors.with_opacity(0.7, COLOR_PRIMARY), 
            color=COLOR_BUTTON_TEXT
        )
    
    def _create_server_config_controls(self):
        """创建服务器配置相关控件"""
        self.controls['server_ip_field'] = ft.TextField(
            label="服务器 IP 地址",
            width=300,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['server_port_field'] = ft.TextField(
            label="服务器端口",
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_PRIMARY,
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE)
        )
        
        self.controls['server_config_status_text'] = ft.Text(
            color=COLOR_STATUS_TEXT_MUTED, 
            text_align=ft.TextAlign.CENTER
        )
        
        self.controls['save_server_config_button'] = ft.ElevatedButton(
            text="保存配置",
            on_click=self._on_save_server_config_click,
            width=150,
            bgcolor=COLOR_PRIMARY, 
            color=COLOR_BUTTON_TEXT
        )
        
        self.controls['back_to_login_from_config_button'] = ft.ElevatedButton(
            text="返回登录",
            on_click=self._on_back_to_login_click,
            width=150,
            bgcolor=ft.Colors.with_opacity(0.7, COLOR_PRIMARY), 
            color=COLOR_BUTTON_TEXT
        )
    
    def _create_main_app_controls(self):
        """创建主应用相关控件"""
        # 频道列表
        self.controls['channel_list_view'] = ft.ListView(
            expand=False, 
            spacing=2, 
            width=220, 
            padding=10
        )
        
        # 聊天相关
        self.controls['current_chat_topic'] = ft.Text(
            "Select a text channel", 
            weight=ft.FontWeight.BOLD, 
            size=16, 
            color=COLOR_TEXT_ON_WHITE
        )
        
        self.controls['chat_messages_view'] = ft.ListView(
            expand=True, 
            spacing=5, 
            auto_scroll=True, 
            padding=10
        )
        
        self.controls['message_input_field'] = ft.TextField(
            hint_text="Type...", 
            expand=True, 
            filled=True, 
            border_radius=20,
            bgcolor=COLOR_INPUT_FIELD_BG_FILLED,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_PRIMARY,
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE),
            on_submit=self._on_send_message_submit
        )
        
        self.controls['send_message_button'] = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            on_click=self._on_send_message_click,
            icon_color=COLOR_PRIMARY
        )
        
        # 语音相关
        self.controls['voice_channel_topic_display'] = ft.Text(
            "Voice Channel", 
            weight=ft.FontWeight.BOLD, 
            size=16, 
            color=COLOR_TEXT_ON_WHITE
        )
        
        self.controls['voice_channel_internal_users_list'] = ft.ListView(
            expand=True, 
            spacing=5, 
            padding=10
        )
        
        # 语音设置
        self._create_voice_settings_controls()
        
        # 语音按钮
        self.controls['confirm_join_voice_button'] = ft.ElevatedButton(
            text="加入语音", 
            icon=ft.Icons.CALL,
            on_click=self._on_confirm_join_voice_click,
            visible=False,
            style=ft.ButtonStyle(bgcolor=COLOR_PRIMARY, color=COLOR_BUTTON_TEXT),
            icon_color=COLOR_ICON_ON_PURPLE
        )
        
        self.controls['leave_voice_button'] = ft.ElevatedButton(
            text="离开语音", 
            icon=ft.Icons.CALL_END,
            on_click=self._on_leave_voice_click,
            visible=False,
            style=ft.ButtonStyle(bgcolor=COLOR_PRIMARY, color=COLOR_BUTTON_TEXT),
            icon_color=COLOR_ICON_ON_PURPLE
        )
        
        # 顶部栏
        self.controls['top_bar_username_text'] = ft.Text(
            "User: N/A", 
            size=16, 
            weight=ft.FontWeight.BOLD, 
            expand=True, 
            color=COLOR_TEXT_ON
        )
        
        self.controls['current_voice_channel_text'] = ft.Text(
            "Not in voice", 
            weight=ft.FontWeight.BOLD, 
            color=COLOR_TEXT_ON, 
            size=12, 
            italic=True
        )
        
        self.controls['logout_button'] = ft.IconButton(
            ft.Icons.LOGOUT, 
            on_click=self._on_logout_click,
            tooltip="Logout",
            icon_color=COLOR_ICON_ON_PURPLE
        )
        
        # 服务器用户列表
        self.controls['server_users_list_view'] = ft.ListView(
            expand=True, 
            spacing=3, 
            padding=ft.padding.only(top=5)
        )
        
        # 状态栏
        self.controls['main_status_bar'] = ft.Text(
            value="", 
            size=12, 
            color=COLOR_STATUS_TEXT_MUTED
        )
    
    def _create_voice_settings_controls(self):
        """创建语音设置相关控件"""
        self.controls['voice_settings_input_device_dropdown'] = ft.Dropdown(
            options=[ft.dropdown.Option(key="-1", text="Loading...")],
            label="Input Device",
            width=250,
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE, size=12),
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE, size=12),
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_PRIMARY,
            on_change=self._on_input_device_change
        )
        
        self.controls['voice_settings_output_device_dropdown'] = ft.Dropdown(
            options=[ft.dropdown.Option(key="-1", text="Loading...")],
            label="Output Device",
            width=250,
            text_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE, size=12),
            label_style=ft.TextStyle(color=COLOR_TEXT_ON_WHITE, size=12),
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_PRIMARY,
            on_change=self._on_output_device_change
        )
        
        self.controls['voice_settings_input_volume_slider'] = ft.Slider(
            min=0, 
            max=100, 
            divisions=100, 
            value=100,
            label="{value}%",
            active_color=COLOR_PRIMARY,
            inactive_color=ft.Colors.with_opacity(0.3, COLOR_PRIMARY),
            on_change=self._on_input_volume_change
        )
        
        self.controls['voice_settings_mute_button'] = ft.IconButton(
            icon=ft.Icons.MIC,
            tooltip="Mute Microphone",
            on_click=self._on_mute_mic_click,
            icon_color=COLOR_TEXT_ON_WHITE,
            icon_size=18
        )
        
        self.controls['voice_settings_mic_test_bar'] = ft.ProgressBar(
            width=180,
            value=0,
            color=COLOR_PRIMARY,
            bgcolor=ft.Colors.with_opacity(0.2, COLOR_PRIMARY)
        )
        
        self.controls['voice_settings_mic_test_button'] = ft.ElevatedButton(
            text="Start Mic Test",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_mic_test_click,
            style=ft.ButtonStyle(
                bgcolor=COLOR_PRIMARY,
                color=COLOR_BUTTON_TEXT,
                shape=ft.RoundedRectangleBorder(radius=5)
            ),
            height=36
        )
        
        self.controls['voice_settings_save_button'] = ft.ElevatedButton(
            text="Save Audio Settings",
            icon=ft.Icons.SAVE_OUTLINED,
            on_click=self._on_save_audio_settings_click,
            style=ft.ButtonStyle(
                bgcolor=COLOR_PRIMARY, 
                color=COLOR_BUTTON_TEXT, 
                shape=ft.RoundedRectangleBorder(radius=5)
            ),
            height=36,
            tooltip="Save selected Input/Output devices"
        )
        
        self.controls['voice_settings_area'] = ft.Column(
            [
                ft.Text("Voice Settings", weight=ft.FontWeight.BOLD, size=14, color=COLOR_TEXT_ON_WHITE),
                ft.Divider(height=5, color=COLOR_DIVIDER_ON_WHITE),
                self.controls['voice_settings_input_device_dropdown'],
                self.controls['voice_settings_output_device_dropdown'],
                ft.Row(
                    [
                        self.controls['voice_settings_mute_button'],
                        ft.Container(
                            content=self.controls['voice_settings_input_volume_slider'],
                            expand=True,
                            padding=ft.padding.only(left=8)
                        )
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=5
                ),
                ft.Row(
                    [
                        self.controls['voice_settings_mic_test_button'],
                        self.controls['voice_settings_mic_test_bar'],
                        self.controls['voice_settings_save_button']
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            ],
            visible=False,
            spacing=10,
            width=280,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
    
    def _create_layouts(self):
        """创建布局"""
        # 登录布局
        login_form_column = ft.Column([
            ft.Text("Login", size=24, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_ON_WHITE),
            self.controls['username_field'],
            self.controls['password_field'],
            ft.Row([self.controls['remember_me_checkbox']], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([self.controls['login_button'], self.controls['register_button']], alignment=ft.MainAxisAlignment.CENTER),
            self.controls['status_text']
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20, expand=True)
        
        self.controls['login_view'] = ft.Stack([
            login_form_column,
            ft.Container(
                content=self.controls['server_settings_button'],
                top=15,
                right=15,
            )
        ], expand=True)
        
        # 注册布局
        self.controls['register_view'] = ft.Column([
            ft.Text("Create Account", size=24, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_ON_WHITE),
            self.controls['reg_username_field'],
            self.controls['reg_password_field'],
            self.controls['reg_confirm_password_field'],
            self.controls['reg_invite_code_field'],
            ft.Row([self.controls['actual_register_button'], self.controls['back_to_login_button']], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            self.controls['register_page_status_text']
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, expand=True, visible=False)
        
        # 服务器配置布局
        self.controls['server_config_view'] = ft.Column([
            ft.Text("服务器配置", size=24, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_ON_WHITE),
            self.controls['server_ip_field'],
            self.controls['server_port_field'],
            ft.Row([self.controls['save_server_config_button'], self.controls['back_to_login_from_config_button']], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            self.controls['server_config_status_text']
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, expand=True, visible=False)
        
        # 主应用布局
        self._create_main_app_layout()
    
    def _create_main_app_layout(self):
        """创建主应用布局"""
        # 聊天面板
        self.controls['chat_panel_content_group'] = ft.Column([
            self.controls['current_chat_topic'],
            ft.Divider(height=1, color=COLOR_DIVIDER_ON_WHITE),
            self.controls['chat_messages_view'],
            ft.Row([self.controls['message_input_field'], self.controls['send_message_button']])
        ], expand=True, visible=True)
        
        # 语音面板
        self.controls['voice_panel_content_group'] = ft.Column([
            self.controls['voice_channel_topic_display'],
            ft.Divider(height=1, color=COLOR_DIVIDER_ON_WHITE),
            ft.Container(content=ft.Text("Users in channel:", weight=ft.FontWeight.W_600, color=COLOR_TEXT_ON_WHITE), margin=ft.margin.only(top=10, bottom=5)),
            self.controls['voice_channel_internal_users_list'],
            self.controls['voice_settings_area'],
            self.controls['confirm_join_voice_button'],
            self.controls['leave_voice_button']
        ], expand=True, visible=False)
        
        # 中间面板
        middle_panel_container = ft.Container(
            ft.Stack([self.controls['chat_panel_content_group'], self.controls['voice_panel_content_group']]),
            expand=True, 
            padding=10, 
            bgcolor=COLOR_BACKGROUND_WHITE,
            border=ft.border.all(1, COLOR_BORDER)
        )
        
        # 左侧面板
        left_panel = ft.Container(
            ft.Column([
                ft.Text("Channels", weight=ft.FontWeight.BOLD, size=18, color=COLOR_TEXT_DARK),
                ft.Divider(height=5, color=COLOR_DIVIDER_ON_WHITE),
                self.controls['channel_list_view']
            ], expand=True),
            width=240,
            padding=0,
            bgcolor=COLOR_BACKGROUND_WHITE,
            border=ft.border.all(1, COLOR_BORDER)
        )
        
        # 右侧面板
        right_panel = ft.Container(
            ft.Column([
                ft.Text("Server Users", weight=ft.FontWeight.BOLD, size=16, color=COLOR_TEXT_ON_WHITE),
                ft.Divider(height=1, color=COLOR_DIVIDER_ON_WHITE),
                self.controls['server_users_list_view']
            ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=200,
            padding=10,
            bgcolor=COLOR_BACKGROUND_WHITE,
            border=ft.border.all(1, COLOR_BORDER)
        )
        
        # 主布局
        main_app_layout = ft.Row([left_panel, middle_panel_container, right_panel], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        
        # 顶部栏
        top_bar = ft.Container(
            ft.Row([
                self.controls['top_bar_username_text'],
                self.controls['current_voice_channel_text'],
                self.controls['logout_button']
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=COLOR_PRIMARY,
            padding=ft.padding.symmetric(horizontal=15, vertical=10)
        )
        
        # 主应用视图
        self.controls['main_app_view'] = ft.Column([
            top_bar,
            main_app_layout,
            self.controls['main_status_bar']
        ], expand=True, visible=False, spacing=0)
    
    def setup_page_controls(self):
        """设置页面控件"""
        self.page.controls.clear()
        self.page.add(
            self.controls['login_view'],
            self.controls['register_view'],
            self.controls['server_config_view'],
            self.controls['main_app_view']
        )
    
    # UI事件处理方法（这些将被主程序覆盖或调用回调）
    def _on_login_click(self, e):
        callback = self.get_callback('on_login')
        if callback:
            self.page.run_task(callback, e, False)
    
    def _on_show_register_click(self, e):
        callback = self.get_callback('on_show_register')
        if callback:
            callback(e)
    
    def _on_show_server_config_click(self, e):
        callback = self.get_callback('on_show_server_config')
        if callback:
            callback(e)
    
    def _on_register_click(self, e):
        callback = self.get_callback('on_register')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_back_to_login_click(self, e):
        callback = self.get_callback('on_back_to_login')
        if callback:
            callback(e)
    
    def _on_save_server_config_click(self, e):
        callback = self.get_callback('on_save_server_config')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_send_message_click(self, e):
        callback = self.get_callback('on_send_message')
        if callback:
            self.page.run_task(callback, self.page)
    
    def _on_send_message_submit(self, e):
        callback = self.get_callback('on_send_message')
        if callback:
            self.page.run_task(callback, self.page)
    
    def _on_confirm_join_voice_click(self, e):
        callback = self.get_callback('on_confirm_join_voice')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_leave_voice_click(self, e):
        callback = self.get_callback('on_leave_voice')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_logout_click(self, e):
        callback = self.get_callback('on_logout')
        if callback:
            callback(e)
    
    def _on_input_device_change(self, e):
        callback = self.get_callback('on_input_device_change')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_output_device_change(self, e):
        callback = self.get_callback('on_output_device_change')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_input_volume_change(self, e):
        callback = self.get_callback('on_input_volume_change')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_mute_mic_click(self, e):
        callback = self.get_callback('on_mute_mic')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_mic_test_click(self, e):
        callback = self.get_callback('on_mic_test')
        if callback:
            self.page.run_task(callback, e)
    
    def _on_save_audio_settings_click(self, e):
        callback = self.get_callback('on_save_audio_settings')
        if callback:
            self.page.run_task(callback, e)
    
    # UI状态管理方法
    def show_view(self, view_name: str):
        """显示指定视图"""
        views = ['login_view', 'register_view', 'server_config_view', 'main_app_view']
        for view in views:
            if view in self.controls:
                self.controls[view].visible = (view == view_name)
        self.page.update()
    
    def update_status_text(self, text: str):
        """更新状态文本"""
        if 'status_text' in self.controls:
            self.controls['status_text'].value = text
            self.controls['status_text'].update()
    
    def update_voice_panel_button_visibility(self, is_previewing: bool, is_active: bool):
        """更新语音面板按钮可见性"""
        confirm_btn = self.controls.get('confirm_join_voice_button')
        leave_btn = self.controls.get('leave_voice_button')
        voice_settings = self.controls.get('voice_settings_area')
        
        if is_previewing:
            if is_active:
                if confirm_btn: confirm_btn.visible = False
                if leave_btn: leave_btn.visible = True
                if voice_settings: voice_settings.visible = True
            else:
                if confirm_btn: confirm_btn.visible = True
                if leave_btn: leave_btn.visible = False
                if voice_settings: voice_settings.visible = False
        else:
            if confirm_btn: confirm_btn.visible = False
            if leave_btn: leave_btn.visible = False
            if voice_settings: voice_settings.visible = False
        
        # 更新各个控件
        if confirm_btn and hasattr(confirm_btn, 'update'): confirm_btn.update()
        if leave_btn and hasattr(leave_btn, 'update'): leave_btn.update()
        if voice_settings and hasattr(voice_settings, 'update'): voice_settings.update()
    
    def switch_middle_panel_view(self, view_type: str, channel_name: str = ""):
        """切换中间面板视图"""
        is_text_view = view_type == "text"
        
        chat_panel = self.controls.get('chat_panel_content_group')
        voice_panel = self.controls.get('voice_panel_content_group')
        
        if chat_panel:
            chat_panel.visible = is_text_view
            chat_panel.update()
        
        if voice_panel:
            voice_panel.visible = not is_text_view
            voice_panel.update()
        
        if is_text_view:
            chat_topic = self.controls.get('current_chat_topic')
            if chat_topic:
                chat_topic.value = f"Chat - {channel_name}"
                chat_topic.update()
    
    def get_control(self, name: str):
        """获取控件"""
        return self.controls.get(name)
    
    def set_control_value(self, name: str, value):
        """设置控件值"""
        control = self.controls.get(name)
        if control and hasattr(control, 'value'):
            control.value = value
            if hasattr(control, 'update'):
                control.update()
    
    def get_control_value(self, name: str):
        """获取控件值"""
        control = self.controls.get(name)
        if control and hasattr(control, 'value'):
            return control.value
        return None
    
    def update_channel_lists(self, text_channels_data: list, voice_channels_data: list):
        """根据提供的数据更新频道列表UI"""
        # 保存频道数据供后续使用
        self.text_channels_data = text_channels_data
        self.voice_channels_data = voice_channels_data
        
        if not self.controls.get('channel_list_view'):
            print("错误：channel_list_view 控件不存在。")
            return

        channel_list_view = self.controls['channel_list_view']
        channel_list_view.controls.clear()

        # 添加文本频道标题
        channel_list_view.controls.append(
            ft.Text("文字频道", weight=ft.FontWeight.BOLD, color=COLOR_TEXT_ON_WHITE, size=14)
        )
        if text_channels_data:
            for channel in text_channels_data:
                channel_name = channel.get("name", "未知频道")
                channel_id = channel.get("id")
                channel_control = ft.ListTile(
                    title=ft.Text(channel_name, color=COLOR_TEXT_ON_WHITE),
                    on_click=lambda e, cid=channel_id: self._on_text_channel_click(cid) 
                )
                channel_control.data = channel_id # 存储频道ID，方便调试或扩展
                channel_list_view.controls.append(channel_control)
        else:
            channel_list_view.controls.append(ft.Text("无文字频道", color=COLOR_TEXT_MUTED_ON_WHITE, italic=True))

        # 添加分隔符和语音频道标题
        channel_list_view.controls.append(ft.Divider(height=10, color=ft.Colors.TRANSPARENT)) 
        channel_list_view.controls.append(
            ft.Text("语音频道", weight=ft.FontWeight.BOLD, color=COLOR_TEXT_ON_WHITE, size=14)
        )

        if voice_channels_data:
            for channel in voice_channels_data:
                channel_name = channel.get("name", "未知频道")
                channel_id = channel.get("id")
                channel_control = ft.ListTile(
                    title=ft.Text(channel_name, color=COLOR_TEXT_ON_WHITE),
                    leading=ft.Icon(ft.Icons.VOLUME_UP_OUTLINED, color=COLOR_PRIMARY),
                    on_click=lambda e, cid=channel_id: self._on_voice_channel_click(cid)
                )
                channel_control.data = channel_id # 存储频道ID
                channel_list_view.controls.append(channel_control)
        else:
            channel_list_view.controls.append(ft.Text("无语音频道", color=COLOR_TEXT_MUTED_ON_WHITE, italic=True))
        
        if channel_list_view.page: 
            channel_list_view.update()

    def _on_text_channel_click(self, channel_id: int):
        """处理文本频道点击事件"""
        print(f"Clicked text channel with ID: {channel_id}")
        
        # 创建一个模拟事件对象
        class ControlEvent:
            def __init__(self, control):
                self.control = control
        
        # 获取频道名称
        channel_name = "未知频道"
        for channel in self._get_text_channels_data():
            if channel.get("id") == channel_id:
                channel_name = channel.get("name", "未知频道")
                break
        
        # 创建一个模拟控件对象
        class MockControl:
            def __init__(self, id, name):
                self.data = id
                self.title = type('obj', (object,), {'value': name})
        
        # 创建模拟控件和事件
        mock_control = MockControl(channel_id, channel_name)
        mock_event = ControlEvent(mock_control)
        
        # 调用回调函数
        text_channel_selected_callback = self.get_callback('on_text_channel_selected')
        if text_channel_selected_callback:
            self.page.run_task(text_channel_selected_callback, mock_event)

    def _on_voice_channel_click(self, channel_id: int):
        """处理语音频道点击事件"""
        print(f"Clicked voice channel with ID: {channel_id}")
        
        # 创建一个模拟事件对象
        class ControlEvent:
            def __init__(self, control):
                self.control = control
        
        # 获取频道名称
        channel_name = "未知频道"
        for channel in self._get_voice_channels_data():
            if channel.get("id") == channel_id:
                channel_name = channel.get("name", "未知频道")
                break
        
        # 创建一个模拟控件对象
        class MockControl:
            def __init__(self, id, name):
                self.data = id
                self.title = type('obj', (object,), {'value': name})
        
        # 创建模拟控件和事件
        mock_control = MockControl(channel_id, channel_name)
        mock_event = ControlEvent(mock_control)
        
        # 调用回调函数
        voice_channel_selected_callback = self.get_callback('on_voice_channel_selected')
        if voice_channel_selected_callback:
            self.page.run_task(voice_channel_selected_callback, mock_event)

    # 新增两个辅助函数获取频道数据
    def _get_text_channels_data(self):
        """获取文本频道数据，用于_on_text_channel_click函数"""
        # 如果UIManager有保存频道数据，则从中获取
        if hasattr(self, 'text_channels_data') and self.text_channels_data:
            return self.text_channels_data
        # 否则返回空列表
        return []
    
    def _get_voice_channels_data(self):
        """获取语音频道数据，用于_on_voice_channel_click函数"""
        # 如果UIManager有保存频道数据，则从中获取
        if hasattr(self, 'voice_channels_data') and self.voice_channels_data:
            return self.voice_channels_data
        # 否则返回空列表
        return [] 