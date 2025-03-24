
import os
import sys
import traceback
import ssl

def setup_certificates():
    try:
        # 获取可执行文件所在的目录
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件路径
            base_dir = os.path.dirname(sys.executable)
            
            # 尝试找到certifi目录并设置证书路径
            cert_dir = os.path.join(base_dir, 'certifi')
            if os.path.exists(cert_dir):
                # 找到certifi目录中的.pem文件
                pem_files = [f for f in os.listdir(cert_dir) if f.endswith('.pem')]
                if pem_files:
                    cert_path = os.path.join(cert_dir, pem_files[0])
                    print(f"找到证书文件: {cert_path}")
                    
                    # 设置SSL证书环境变量
                    os.environ['SSL_CERT_FILE'] = cert_path
                    os.environ['REQUESTS_CA_BUNDLE'] = cert_path
                    
                    # 修复ssl默认上下文
                    try:
                        ssl._create_default_https_context = ssl._create_unverified_context
                        print("已启用SSL非验证模式")
                    except AttributeError:
                        pass
                else:
                    print(f"警告: 在certifi目录中未找到.pem文件")
            else:
                print(f"警告: certifi目录不存在: {cert_dir}")
                
                # 如果找不到证书文件，则使用ssl非验证模式
                try:
                    ssl._create_default_https_context = ssl._create_unverified_context
                    print("已启用SSL非验证模式作为后备方案")
                except AttributeError:
                    pass
                    
            # 修补requests库的证书路径
            try:
                import requests.utils
                import requests.adapters
                
                # 修改requests库错误处理
                import requests.exceptions
                old_get_encoding_from_headers = requests.utils.get_encoding_from_headers
                def new_get_encoding_from_headers(headers):
                    try:
                        if 'content-type' not in headers:
                            return 'utf-8'  # 默认使用utf-8
                        return old_get_encoding_from_headers(headers)
                    except Exception as e:
                        print(f"获取编码失败: {e}")
                        return 'utf-8'  # 出错时默认使用utf-8
                
                requests.utils.get_encoding_from_headers = new_get_encoding_from_headers
                
                # 修改默认证书处理
                if hasattr(requests.adapters, 'DEFAULT_CA_BUNDLE_PATH'):
                    pem_files = [f for f in os.listdir(cert_dir) if f.endswith('.pem')]
                    if pem_files:
                        cert_path = os.path.join(cert_dir, pem_files[0])
                        requests.adapters.DEFAULT_CA_BUNDLE_PATH = cert_path
                        print(f"已修改requests库的默认证书路径: {cert_path}")
                        
                # 修补requests会话的异常处理
                old_request = requests.Session.request
                def new_request(self, method, url, **kwargs):
                    try:
                        return old_request(self, method, url, **kwargs)
                    except requests.exceptions.SSLError:
                        print(f"SSL错误，尝试禁用验证...")
                        kwargs['verify'] = False
                        return old_request(self, method, url, **kwargs)
                    except Exception as e:
                        print(f"请求错误: {url} - {e}")
                        raise
                
                requests.Session.request = new_request
                        
            except (ImportError, AttributeError, NameError) as e:
                print(f"无法修补requests库: {e}")
                traceback.print_exc()
    except Exception as e:
        print(f"设置证书时出错: {e}")
        traceback.print_exc()

setup_certificates()
