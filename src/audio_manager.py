import threading
import asyncio
import numpy as np
from typing import Optional, List, Dict, Callable
import flet as ft

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception as e:
    print(f"Sounddevice library not found or failed to import: {e}. Audio device listing will be unavailable.")
    SOUNDDEVICE_AVAILABLE = False
    sd = None

try:
    import scipy.signal
    SCIPY_AVAILABLE = True
except ImportError:
    print("Warning: scipy not available. Audio resampling will use simple methods.")
    SCIPY_AVAILABLE = False

class AudioManager:
    """音频管理器类，处理所有音频相关功能"""
    
    # 统一音频格式配置
    STANDARD_SAMPLERATE = 48000  # 统一使用48kHz采样率
    STANDARD_CHANNELS = 1        # 单声道
    STANDARD_DTYPE = np.float32  # 标准数据类型
    STANDARD_BLOCKSIZE = 960     # 20ms at 48kHz (48000 * 0.02)
    
    # Voice Activity Detection
    AUDIO_RMS_THRESHOLD = 0.02   # VAD阈值
    
    def __init__(self):
        # 设备管理
        self.selected_input_device_id: Optional[int] = None
        self.selected_output_device_id: Optional[int] = None
        
        # 麦克风测试相关
        self.is_mic_testing = False
        self.current_mic_test_volume: float = 0.0
        self.mic_test_volume_lock = threading.Lock()
        self.mic_test_thread: Optional[threading.Thread] = None
        self.mic_test_stop_event = threading.Event()
        self.mic_test_ui_update_task: Optional[asyncio.Task] = None
        
        # 音频流发送相关
        self.is_sending_audio = False
        self.audio_stream_thread: Optional[threading.Thread] = None
        self.audio_stream_stop_event = threading.Event()
        self.last_sent_speaking_status: bool = False
        self.is_logically_muted: bool = False
        self.is_mic_muted = False
        self.DEFAULT_UNMUTE_VOLUME = 0.8
        
        # 音频播放相关
        self.audio_output_stream: Optional[sd.OutputStream] = None
        self.audio_output_buffer = asyncio.Queue()
        self.is_audio_playback_active: bool = False
        
        # 回调函数
        self.callbacks: Dict[str, Callable] = {}
        
        # 页面循环，用于在回调中正确创建异步任务
        self.page_loop = None
    
    def set_callback(self, name: str, callback: Callable):
        """设置回调函数"""
        self.callbacks[name] = callback
    
    def get_callback(self, name: str) -> Optional[Callable]:
        """获取回调函数"""
        return self.callbacks.get(name)
    
    def set_page_loop(self, loop):
        """设置页面事件循环"""
        self.page_loop = loop
        print(f"Page loop set: {loop}")
    
    @staticmethod
    def resample_audio(audio_data, original_rate, target_rate):
        """重采样音频数据到目标采样率"""
        if original_rate == target_rate:
            return audio_data
        
        if SCIPY_AVAILABLE:
            # 使用scipy进行高质量重采样
            num_samples = int(len(audio_data) * target_rate / original_rate)
            return scipy.signal.resample(audio_data, num_samples).astype(np.float32)
        else:
            # 简单的线性插值重采样（质量较低但总比不重采样好）
            ratio = target_rate / original_rate
            new_length = int(len(audio_data) * ratio)
            indices = np.linspace(0, len(audio_data) - 1, new_length)
            return np.interp(indices, np.arange(len(audio_data)), audio_data).astype(np.float32)
    
    @staticmethod
    def normalize_audio_chunk(audio_chunk, volume_factor=1.0):
        """规范化音频块，应用音量并防止削波"""
        if volume_factor <= 0:
            return np.zeros_like(audio_chunk, dtype=np.float32)
        
        # 应用音量
        normalized = audio_chunk * volume_factor
        
        # 防止削波
        max_val = np.max(np.abs(normalized))
        if max_val > 1.0:
            normalized = normalized / max_val
        
        return normalized.astype(np.float32)
    
    def get_audio_devices_sync(self):
        """同步获取音频设备列表"""
        if not SOUNDDEVICE_AVAILABLE or sd is None:
            return [], []  # Return empty lists if sounddevice is not available
        
        try:
            devices = sd.query_devices()
            input_devices = []
            output_devices = []
            default_input_idx = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else sd.default.device
            default_output_idx = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) else sd.default.device

            for i, device in enumerate(devices):
                device_name = f"{device['name']} ({sd.query_hostapis(device['hostapi'])['name']})"
                if i == default_input_idx and device['max_input_channels'] > 0:
                    # Prepend '(Default)' to the default input device name
                    input_devices.insert(0, {'id': i, 'name': f"(Default) {device_name}"})
                elif device['max_input_channels'] > 0:
                    input_devices.append({'id': i, 'name': device_name})
                
                if i == default_output_idx and device['max_output_channels'] > 0:
                     # Prepend '(Default)' to the default output device name
                    output_devices.insert(0, {'id': i, 'name': f"(Default) {device_name}"})
                elif device['max_output_channels'] > 0:
                    output_devices.append({'id': i, 'name': device_name})
            
            # Ensure the default marked item is truly at the top if it wasn't added first due to iteration order
            input_devices.sort(key=lambda x: not x['name'].startswith('(Default)'))
            output_devices.sort(key=lambda x: not x['name'].startswith('(Default)'))

            return input_devices, output_devices
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            return [], []  # Return empty on error
    
    def mic_test_audio_callback(self, indata, outdata, frames, time, status):
        """麦克风测试音频回调"""
        if status:
            print(f"Mic Test Callback Status: {status}")
        outdata[:] = indata  # Loopback
        volume_norm = np.linalg.norm(indata) * 10  # Arbitrary scaling for better visibility
        with self.mic_test_volume_lock:
            self.current_mic_test_volume = min(1.0, volume_norm)  # Cap at 1.0 for progress bar
    
    def run_mic_test_loop(self, page_instance: ft.Page, input_dev_id: int, output_dev_id: int, stop_event: threading.Event):
        """运行麦克风测试循环"""
        stream = None
        try:
            # 查询输入设备的默认采样率
            input_device_info = sd.query_devices(input_dev_id, 'input')
            original_samplerate = int(input_device_info['default_samplerate'])
            
            # 使用标准采样率，如果设备支持的话
            target_samplerate = self.STANDARD_SAMPLERATE if self.STANDARD_SAMPLERATE in [22050, 44100, 48000] else original_samplerate
            
            print(f"Mic test: Original device samplerate: {original_samplerate}, Using: {target_samplerate}")
            
            stream = sd.Stream(
                device=(input_dev_id, output_dev_id),
                samplerate=target_samplerate,
                channels=self.STANDARD_CHANNELS,
                callback=self.mic_test_audio_callback,
                dtype=self.STANDARD_DTYPE,
                blocksize=int(target_samplerate * 0.02)  # 20ms blocks
            )
            
            with stream:
                print(f"Mic test started with devices: input={input_dev_id}, output={output_dev_id}")
                stop_event.wait()  # Block until stop_event is set
                print("Mic test stopped by user or error.")
        except Exception as e:
            print(f"Mic test error: {e}")
            async def show_error_async():
                callback = self.get_callback('show_error')
                if callback:
                    await callback(page_instance, f"麦克风测试错误: {e}")
            
            # Use page.run_task for thread-safe async call
            if hasattr(page_instance, 'run_task'):
                page_instance.run_task(show_error_async)
        finally:
            if stream:
                stream.close()
    
    def audio_stream_callback(self, indata, frames, time, status):
        """音频流回调函数"""
        if status:
            print(f"Audio Stream Callback Status: {status}")
        
        # 计算音频RMS用于VAD
        rms = np.sqrt(np.mean(indata ** 2))
        is_speaking = rms > self.AUDIO_RMS_THRESHOLD and not self.is_logically_muted
        
        # 如果speaking状态改变，触发回调
        if is_speaking != self.last_sent_speaking_status:
            self.last_sent_speaking_status = is_speaking
            speaking_callback = self.get_callback('on_speaking_status_change')
            if speaking_callback and self.page_loop:
                try:
                    # 使用页面循环创建异步任务
                    asyncio.run_coroutine_threadsafe(
                        speaking_callback(is_speaking),
                        self.page_loop
                    )
                except Exception as e:
                    print(f"Error running speaking status callback: {e}")
        
        if self.is_logically_muted:
            # 如果被静音，不发送任何数据
            return
        
        # 只有当用户在说话时才发送音频数据
        if not is_speaking:
            # 如果用户没有说话，不发送任何数据
            return
        
        # 准备音频数据
        if indata.shape[0] > 0:
            original_samplerate = len(indata) / (frames / 48000)  # 估算原始采样率
            if abs(original_samplerate - self.STANDARD_SAMPLERATE) > 100:  # 如果差异显著
                resampled = self.resample_audio(indata.flatten(), int(original_samplerate), self.STANDARD_SAMPLERATE)
                data_to_send = resampled.reshape(-1, 1)
            else:
                data_to_send = indata
        else:
            # 如果没有数据，不发送
            return
        
        # 发送音频数据
        send_callback = self.get_callback('send_audio_data')
        if send_callback and self.page_loop:
            try:
                # 使用页面循环创建异步任务
                asyncio.run_coroutine_threadsafe(
                    send_callback(data_to_send),
                    self.page_loop
                )
            except Exception as e:
                print(f"Error sending audio data: {e}")
    
    def run_audio_stream_loop(self, input_dev_id: int, stop_event: threading.Event, page_instance_ref: ft.Page):
        """运行音频流循环"""
        stream = None
        try:
            # 查询输入设备信息
            input_device_info = sd.query_devices(input_dev_id, 'input')
            original_samplerate = int(input_device_info['default_samplerate'])
            
            # 使用标准采样率
            target_samplerate = self.STANDARD_SAMPLERATE if self.STANDARD_SAMPLERATE in [22050, 44100, 48000] else original_samplerate
            
            print(f"Audio stream: Original device samplerate: {original_samplerate}, Using: {target_samplerate}")
            
            stream = sd.InputStream(
                device=input_dev_id,
                samplerate=target_samplerate,
                channels=self.STANDARD_CHANNELS,
                callback=self.audio_stream_callback,
                dtype=self.STANDARD_DTYPE,
                blocksize=int(target_samplerate * 0.02)  # 20ms blocks
            )
            
            with stream:
                print(f"Audio streaming started with input device: {input_dev_id}")
                stop_event.wait()
                print("Audio streaming stopped.")
        except Exception as e:
            print(f"Audio stream error: {e}")
            async def show_error_async():
                callback = self.get_callback('show_error')
                if callback:
                    await callback(page_instance_ref, f"音频流错误: {e}")
            
            if hasattr(page_instance_ref, 'run_task'):
                page_instance_ref.run_task(show_error_async)
        finally:
            if stream:
                stream.close()
    
    def audio_playback_callback(self, outdata, frames, time, status):
        """音频播放回调函数"""
        if status:
            print(f"Audio Playback Callback Status: {status}")
        
        try:
            # 从缓冲区获取音频数据
            if not self.audio_output_buffer.empty():
                audio_chunk = self.audio_output_buffer.get_nowait()
                
                # 确保数据长度匹配
                if len(audio_chunk) == frames:
                    outdata[:] = audio_chunk.reshape(-1, 1)
                else:
                    # 如果长度不匹配，进行调整
                    if len(audio_chunk) > frames:
                        outdata[:] = audio_chunk[:frames].reshape(-1, 1)
                    else:
                        outdata[:len(audio_chunk)] = audio_chunk.reshape(-1, 1)
                        outdata[len(audio_chunk):] = 0  # 填充静音
            else:
                # 缓冲区为空，输出静音
                outdata.fill(0)
        except Exception as e:
            print(f"Audio playback callback error: {e}")
            outdata.fill(0)  # 出错时输出静音
    
    async def start_audio_playback_stream(self, page_ref: ft.Page, output_device_idx: Optional[int] = None):
        """启动音频播放流"""
        if self.is_audio_playback_active:
            print("Audio playback stream already active.")
            return
        
        try:
            # 获取输出设备信息
            if output_device_idx is not None:
                output_device_info = sd.query_devices(output_device_idx, 'output')
                original_samplerate = int(output_device_info['default_samplerate'])
            else:
                original_samplerate = self.STANDARD_SAMPLERATE
            
            # 使用标准采样率
            target_samplerate = self.STANDARD_SAMPLERATE if self.STANDARD_SAMPLERATE in [22050, 44100, 48000] else original_samplerate
            
            print(f"Audio playback: Original device samplerate: {original_samplerate}, Using: {target_samplerate}")
            
            self.audio_output_stream = sd.OutputStream(
                device=output_device_idx,
                samplerate=target_samplerate,
                channels=self.STANDARD_CHANNELS,
                callback=self.audio_playback_callback,
                dtype=self.STANDARD_DTYPE,
                blocksize=int(target_samplerate * 0.02)  # 20ms blocks
            )
            
            self.audio_output_stream.start()
            self.is_audio_playback_active = True
            print(f"Audio playback started with output device: {output_device_idx}")
        except Exception as e:
            print(f"Failed to start audio playback stream: {e}")
            callback = self.get_callback('show_error')
            if callback:
                await callback(page_ref, f"启动音频播放失败: {e}")
    
    async def stop_audio_playback_stream_if_running(self):
        """停止音频播放流"""
        if self.audio_output_stream is not None and self.is_audio_playback_active:
            try:
                self.audio_output_stream.stop()
                self.audio_output_stream.close()
                self.is_audio_playback_active = False
                print("Audio playback stream stopped and closed.")
            except Exception as e:
                print(f"Error stopping audio playback stream: {e}")
            finally:
                self.audio_output_stream = None
                
                # 清空缓冲区
                while not self.audio_output_buffer.empty():
                    try:
                        self.audio_output_buffer.get_nowait()
                    except:
                        break
    
    async def start_audio_stream(self, page_ref: ft.Page, input_device_id: int):
        """启动音频发送流"""
        if self.is_sending_audio:
            print("Audio stream already active.")
            return
        
        # 重置stop event
        self.audio_stream_stop_event.clear()
        
        # 启动音频流线程
        self.audio_stream_thread = threading.Thread(
            target=self.run_audio_stream_loop,
            args=(input_device_id, self.audio_stream_stop_event, page_ref),
            daemon=True
        )
        self.audio_stream_thread.start()
        self.is_sending_audio = True
        print(f"Audio stream thread started with input device: {input_device_id}")
    
    async def stop_audio_stream_if_running(self):
        """停止音频发送流"""
        if self.is_sending_audio and self.audio_stream_thread:
            self.audio_stream_stop_event.set()  # Signal the thread to stop
            self.audio_stream_thread.join(timeout=2.0)  # Wait up to 2 seconds for thread to finish
            if self.audio_stream_thread.is_alive():
                print("Warning: Audio stream thread did not terminate within timeout.")
            else:
                print("Audio stream thread terminated successfully.")
            
            self.audio_stream_thread = None
            self.is_sending_audio = False
            self.last_sent_speaking_status = False
    
    async def start_mic_test(self, page_ref: ft.Page, input_device_id: int, output_device_id: Optional[int] = None):
        """启动麦克风测试"""
        if self.is_mic_testing:
            return
        
        self.mic_test_stop_event.clear()
        self.current_mic_test_volume = 0.0
        
        # 启动麦克风测试线程
        self.mic_test_thread = threading.Thread(
            target=self.run_mic_test_loop,
            args=(page_ref, input_device_id, output_device_id, self.mic_test_stop_event),
            daemon=True
        )
        self.mic_test_thread.start()
        self.is_mic_testing = True
    
    async def stop_mic_test(self):
        """停止麦克风测试"""
        if self.is_mic_testing and self.mic_test_thread:
            self.mic_test_stop_event.set()
            self.mic_test_thread.join(timeout=2.0)
            if self.mic_test_thread.is_alive():
                print("Warning: Mic test thread did not terminate within timeout.")
            else:
                print("Mic test thread terminated successfully.")
            
            self.mic_test_thread = None
            self.is_mic_testing = False
            self.current_mic_test_volume = 0.0
    
    def get_mic_test_volume(self) -> float:
        """获取当前麦克风测试音量"""
        with self.mic_test_volume_lock:
            return self.current_mic_test_volume
    
    async def add_audio_chunk_to_playback_buffer(self, audio_chunk: np.ndarray):
        """添加音频块到播放缓冲区"""
        try:
            # 确保音频块格式正确
            if audio_chunk.dtype != self.STANDARD_DTYPE:
                audio_chunk = audio_chunk.astype(self.STANDARD_DTYPE)
            
            # 添加到缓冲区（非阻塞）
            self.audio_output_buffer.put_nowait(audio_chunk)
        except asyncio.QueueFull:
            # 如果缓冲区满了，丢弃最旧的音频块
            try:
                self.audio_output_buffer.get_nowait()
                self.audio_output_buffer.put_nowait(audio_chunk)
            except:
                pass  # 如果还是失败就忽略这个音频块
        except Exception as e:
            print(f"Error adding audio chunk to buffer: {e}") 