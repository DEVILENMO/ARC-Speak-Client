import json
import os

class ConfigLoader:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self._ensure_directory_exists()
        self.config_data = self._load_from_file()

    def _ensure_directory_exists(self):
        dir_name = os.path.dirname(self.config_file_path)
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name)
            except OSError as e:
                # Handle potential race condition or permission issues
                print(f"Error creating directory {dir_name}: {e}")

    def _load_from_file(self):
        """内部方法，从文件加载配置"""
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                # Return empty dict if config file is corrupted or empty
                return {}
        return {}

    def load_config(self):
        """返回当前缓存的配置数据（不重新读取文件）"""
        return self.config_data

    def reload_config(self):
        """强制从文件重新加载配置"""
        self.config_data = self._load_from_file()
        return self.config_data

    def save_config(self, config_data=None):
        """
        保存配置数据到文件
        如果提供了config_data参数，则保存该数据并更新缓存
        否则保存当前缓存的配置数据
        """
        if config_data is not None:
            self.config_data = config_data
            
        try:
            with open(self.config_file_path, 'w') as f:
                json.dump(self.config_data, f, indent=4)
        except IOError as e:
            # Handle potential permission issues or other I/O errors
            print(f"Error saving config to {self.config_file_path}: {e}")
            
    def get(self, key, default=None):
        """获取指定键的配置值"""
        return self.config_data.get(key, default)
        
    def set(self, key, value):
        """设置指定键的配置值"""
        self.config_data[key] = value
        
    def delete(self, key):
        """删除指定键的配置值"""
        if key in self.config_data:
            del self.config_data[key]
            
    def clear(self):
        """清空所有配置"""
        self.config_data = {} 

    def update_login_info(self, username, password, remember_me):
        self.set("username", username)
        self.set("password", password)
        self.set("remember_me", remember_me)
        self.save_config()

    def reset_login_info(self):
        self.delete("username")
        self.delete("password")
        self.delete("remember_me")
        self.save_config()
