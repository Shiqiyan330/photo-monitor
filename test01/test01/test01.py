# app.py - 完整的员工管理系统（优化台账上传界面）

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, send_file
import json
import os
import hashlib
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_please_change_this'
# 取消文件大小限制，设置为None表示不限制
app.config['MAX_CONTENT_LENGTH'] = None


# ========== 登录验证装饰器 ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session.get('role') != 'admin':
            return redirect(url_for('main'))
        return f(*args, **kwargs)

    return decorated_function


# ========== 配置管理类 ==========
class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.departments = []
        self.positions = []
        self.ranks = []
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.departments = data.get('departments', [])
                self.positions = data.get('positions', [])
                self.ranks = data.get('ranks', [])
        else:
            self.departments = []
            self.positions = []
            self.ranks = []
            self.save_config()

    def save_config(self):
        data = {
            'departments': self.departments,
            'positions': self.positions,
            'ranks': self.ranks
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_department(self, name):
        if name and name not in self.departments:
            self.departments.append(name)
            self.save_config()
            return True
        return False

    def add_position(self, name):
        if name and name not in self.positions:
            self.positions.append(name)
            self.save_config()
            return True
        return False

    def add_rank(self, name):
        if name and name not in self.ranks:
            self.ranks.append(name)
            self.save_config()
            return True
        return False

    def delete_department(self, name):
        if name in self.departments:
            self.departments.remove(name)
            self.save_config()
            return True
        return False

    def delete_position(self, name):
        if name in self.positions:
            self.positions.remove(name)
            self.save_config()
            return True
        return False

    def delete_rank(self, name):
        if name in self.ranks:
            self.ranks.remove(name)
            self.save_config()
            return True
        return False


# ========== 台账管理类 ==========
class LedgerManager:
    def __init__(self, data_file='ledger_data.json'):
        self.data_file = data_file
        self.records = []
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.records = json.load(f)
        else:
            self.records = []
            self.save_data()

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def add_record(self, filename, filepath, department, uploader, uploader_name, file_size):
        """添加上传记录"""
        record = {
            'id': len(self.records) + 1,
            'filename': filename,
            'filepath': filepath,
            'department': department,
            'uploader': uploader,
            'uploader_name': uploader_name,
            'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'size': file_size,
            'size_display': self.format_size(file_size),
            'download_count': 0
        }
        self.records.insert(0, record)
        self.save_data()
        return True, "上传成功"

    def get_records(self, department=None, start_date=None, end_date=None, keyword=None):
        """获取台账记录（支持筛选）"""
        records = self.records.copy()

        # 部门筛选
        if department and department != 'all':
            records = [r for r in records if r['department'] == department]

        # 时间范围筛选
        if start_date:
            records = [r for r in records if r['upload_time'].split(' ')[0] >= start_date]
        if end_date:
            records = [r for r in records if r['upload_time'].split(' ')[0] <= end_date]

        # 关键词搜索
        if keyword:
            keyword_lower = keyword.lower()
            records = [r for r in records if
                       keyword_lower in r['filename'].lower() or keyword_lower in r['uploader_name'].lower()]

        return records

    def get_record(self, record_id):
        for record in self.records:
            if record['id'] == record_id:
                return record
        return None

    def delete_record(self, record_id, username):
        for i, record in enumerate(self.records):
            if record['id'] == record_id:
                if session.get('role') == 'admin' or record['uploader'] == username:
                    try:
                        if os.path.exists(record['filepath']):
                            os.remove(record['filepath'])
                    except:
                        pass
                    self.records.pop(i)
                    self.save_data()
                    return True, "删除成功"
                return False, "没有权限删除"
        return False, "记录不存在"

    def update_download_count(self, record_id):
        for record in self.records:
            if record['id'] == record_id:
                record['download_count'] += 1
                self.save_data()
                return True
        return False

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


# ========== 学习交流管理类 ==========
class StudyManager:
    def __init__(self, data_file='study_data.json'):
        self.data_file = data_file
        self.articles = []
        self.discussions = []
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.articles = data.get('articles', [])
                self.discussions = data.get('discussions', [])
        else:
            self.articles = []
            self.discussions = []
            self.save_data()

    def save_data(self):
        data = {
            'articles': self.articles,
            'discussions': self.discussions
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_article(self, title, description, filename, filepath, file_type, uploader, uploader_name):
        article = {
            'id': len(self.articles) + 1,
            'title': title,
            'description': description,
            'filename': filename,
            'filepath': filepath,
            'file_type': file_type,
            'uploader': uploader,
            'uploader_name': uploader_name,
            'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'views': 0,
            'comments': []
        }
        self.articles.append(article)
        self.save_data()
        return True, "文章上传成功"

    def get_articles(self):
        return sorted(self.articles, key=lambda x: x['upload_time'], reverse=True)

    def get_article(self, article_id):
        for article in self.articles:
            if article['id'] == article_id:
                return article
        return None

    def add_comment(self, article_id, username, user_name, content):
        for article in self.articles:
            if article['id'] == article_id:
                comment = {
                    'id': len(article['comments']) + 1,
                    'username': username,
                    'user_name': user_name,
                    'content': content,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                article['comments'].append(comment)
                self.save_data()
                return True, "评论成功"
        return False, "文章不存在"

    def delete_article(self, article_id, username):
        for i, article in enumerate(self.articles):
            if article['id'] == article_id:
                if session.get('role') == 'admin' or article['uploader'] == username:
                    try:
                        if os.path.exists(article['filepath']):
                            os.remove(article['filepath'])
                    except:
                        pass
                    self.articles.pop(i)
                    self.save_data()
                    return True, "删除成功"
                return False, "没有权限删除"
        return False, "文章不存在"

    def add_discussion(self, username, user_name, content):
        discussion = {
            'id': len(self.discussions) + 1,
            'username': username,
            'user_name': user_name,
            'content': content,
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'replies': []
        }
        self.discussions.insert(0, discussion)
        self.save_data()
        return True, "发布成功"

    def add_reply(self, discussion_id, username, user_name, content):
        for discussion in self.discussions:
            if discussion['id'] == discussion_id:
                reply = {
                    'id': len(discussion['replies']) + 1,
                    'username': username,
                    'user_name': user_name,
                    'content': content,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                discussion['replies'].append(reply)
                self.save_data()
                return True, "回复成功"
        return False, "讨论不存在"

    def get_discussions(self):
        return self.discussions

    def delete_discussion(self, discussion_id, username):
        for i, discussion in enumerate(self.discussions):
            if discussion['id'] == discussion_id:
                if session.get('role') == 'admin' or discussion['username'] == username:
                    self.discussions.pop(i)
                    self.save_data()
                    return True, "删除成功"
                return False, "没有权限删除"
        return False, "讨论不存在"


# ========== 文件管理类 ==========
class FileManager:
    def __init__(self, files_dir='company_files'):
        self.files_dir = files_dir
        self.metadata_file = os.path.join(files_dir, 'file_metadata.json')
        self.file_metadata = {}
        self.init_filesystem()

    def init_filesystem(self):
        if not os.path.exists(self.files_dir):
            os.makedirs(self.files_dir)

        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                self.file_metadata = json.load(f)
        else:
            self.file_metadata = {}
            self.save_metadata()

    def save_metadata(self):
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.file_metadata, f, ensure_ascii=False, indent=2)

    def upload_file(self, file, department, filename, username, user_name):
        try:
            dept_path = os.path.join(self.files_dir, department)
            if not os.path.exists(dept_path):
                os.makedirs(dept_path)

            original_filename = secure_filename(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{original_filename}"
            filepath = os.path.join(dept_path, unique_filename)
            file.save(filepath)

            file_id = f"{department}_{timestamp}_{original_filename}"
            file_size = os.path.getsize(filepath)

            self.file_metadata[file_id] = {
                'id': file_id,
                'filename': original_filename,
                'department': department,
                'uploader': username,
                'uploader_name': user_name,
                'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'size': file_size,
                'size_display': self.format_size(file_size),
                'filepath': filepath,
                'download_count': 0
            }
            self.save_metadata()
            return True, "上传成功"
        except Exception as e:
            return False, f"上传失败: {str(e)}"

    def get_department_files(self, department, username):
        files = []
        user = system.get_employee_by_username(username)
        if not user:
            return files

        user_permissions = user.permissions
        user_department = user.department

        for file_id, metadata in self.file_metadata.items():
            file_dept = metadata['department']
            has_permission = False

            if session.get('role') == 'admin':
                has_permission = True
            elif 'cross_dept_files' in user_permissions:
                has_permission = True
            elif file_dept == user_department:
                has_permission = True
            elif f'dept_{file_dept}' in user_permissions:
                has_permission = True

            if has_permission and (department == 'all' or file_dept == department):
                files.append(metadata)

        files.sort(key=lambda x: x['upload_time'], reverse=True)
        return files

    def get_user_departments(self, username):
        user = system.get_employee_by_username(username)
        if not user:
            return []

        departments = set()

        if session.get('role') == 'admin':
            return config_mgr.departments

        user_permissions = user.permissions
        user_department = user.department

        if user_department:
            departments.add(user_department)

        if 'cross_dept_files' in user_permissions:
            for dept in config_mgr.departments:
                departments.add(dept)

        for perm in user_permissions:
            if perm.startswith('dept_'):
                dept_name = perm[5:]
                if dept_name in config_mgr.departments:
                    departments.add(dept_name)

        return sorted(list(departments))

    def get_upload_departments(self, username):
        user = system.get_employee_by_username(username)
        if not user:
            return []

        departments = set()

        if session.get('role') == 'admin':
            return config_mgr.departments

        user_permissions = user.permissions
        user_department = user.department

        if user_department:
            departments.add(user_department)

        if 'cross_dept_files' in user_permissions:
            for dept in config_mgr.departments:
                departments.add(dept)

        return sorted(list(departments))

    def download_file(self, file_id, username):
        if file_id not in self.file_metadata:
            return None, "文件不存在"

        metadata = self.file_metadata[file_id]

        if not self.check_file_permission(file_id, username):
            return None, "没有权限访问此文件"

        metadata['download_count'] += 1
        self.save_metadata()

        return metadata['filepath'], metadata['filename']

    def check_file_permission(self, file_id, username):
        if file_id not in self.file_metadata:
            return False

        metadata = self.file_metadata[file_id]
        user = system.get_employee_by_username(username)

        if not user:
            return False

        if session.get('role') == 'admin':
            return True

        user_permissions = user.permissions
        user_department = user.department

        if 'cross_dept_files' in user_permissions:
            return True

        if metadata['department'] == user_department:
            return True

        if f'dept_{metadata["department"]}' in user_permissions:
            return True

        return False

    def delete_file(self, file_id, username):
        if file_id not in self.file_metadata:
            return False, "文件不存在"

        metadata = self.file_metadata[file_id]

        if session.get('role') != 'admin' and metadata['uploader'] != username:
            return False, "只有管理员或文件上传者可以删除文件"

        try:
            if os.path.exists(metadata['filepath']):
                os.remove(metadata['filepath'])
        except Exception as e:
            print(f"删除文件失败: {e}")

        del self.file_metadata[file_id]
        self.save_metadata()

        return True, "删除成功"

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


# ========== 用户类 ==========
class User:
    def __init__(self, username, password, role, phone="", name="", age=0, department="", position="", rank="",
                 avatar="", permissions=None):
        self.username = username
        self.password = password
        self.role = role
        self.phone = phone
        self.name = name
        self.age = age
        self.department = department
        self.position = position
        self.rank = rank
        self.avatar = avatar or '👤'
        self.join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.permissions = permissions or ['study', 'upload', 'structure']

    def check_password(self, password):
        return self.password == password

    def to_dict(self):
        return {
            'username': self.username,
            'password': self.password,
            'role': self.role,
            'phone': self.phone,
            'name': self.name,
            'age': self.age,
            'department': self.department,
            'position': self.position,
            'rank': self.rank,
            'avatar': self.avatar,
            'join_date': self.join_date,
            'permissions': self.permissions
        }

    @staticmethod
    def from_dict(data):
        user = User(
            data['username'],
            data['password'],
            data['role'],
            data.get('phone', ''),
            data.get('name', ''),
            data.get('age', 0),
            data.get('department', ''),
            data.get('position', ''),
            data.get('rank', ''),
            data.get('avatar', ''),
            data.get('permissions', ['study', 'upload', 'structure'])
        )
        user.join_date = data.get('join_date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return user


# ========== 员工系统类 ==========
class EmployeeSystem:
    def __init__(self, data_file='users.json'):
        self.data_file = data_file
        self.users = []
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = [User.from_dict(user) for user in data]
        else:
            admin = User("admin", "admin", "admin", name="系统管理员", avatar="👨‍💼",
                         permissions=['camera', 'files', 'study', 'upload', 'structure', 'cross_dept_files'])
            self.users.append(admin)
            self.save_data()

    def save_data(self):
        data = [user.to_dict() for user in self.users]
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def login(self, username, password):
        for user in self.users:
            if user.username == username and user.check_password(password):
                return user
        return None

    def get_company_structure(self):
        structure = {}
        for user in self.users:
            if user.role == 'employee' and user.department:
                if user.department not in structure:
                    structure[user.department] = []
                structure[user.department].append({
                    'name': user.name,
                    'position': user.position,
                    'rank': user.rank,
                    'phone': user.phone
                })
        return structure

    def add_employee(self, employee_data):
        phone = employee_data.get('phone', '')
        username = phone
        password = phone

        if any(u.username == username for u in self.users):
            return False, "手机号已存在"

        permissions = employee_data.get('permissions', ['study', 'upload', 'structure'])
        if isinstance(permissions, str):
            permissions = [p.strip() for p in permissions.split(',') if p.strip()]

        employee = User(
            username, password, 'employee', phone,
            employee_data.get('name', ''), 0,
            employee_data.get('department', ''),
            employee_data.get('position', ''),
            employee_data.get('rank', ''),
            '👤', permissions
        )
        self.users.append(employee)
        self.save_data()
        return True, "添加成功，账号密码均为手机号"

    def update_employee(self, username, employee_data):
        for i, user in enumerate(self.users):
            if user.username == username and user.role == 'employee':
                user.name = employee_data.get('name', user.name)
                user.department = employee_data.get('department', user.department)
                user.position = employee_data.get('position', user.position)
                user.rank = employee_data.get('rank', user.rank)

                permissions = employee_data.get('permissions', user.permissions)
                if isinstance(permissions, str):
                    permissions = [p.strip() for p in permissions.split(',') if p.strip()]
                user.permissions = permissions

                self.save_data()
                return True, "修改成功"
        return False, "员工不存在"

    def change_password(self, username, old_password, new_password):
        user = self.get_employee_by_username(username)
        if not user:
            return False, "用户不存在"

        if not user.check_password(old_password):
            return False, "原密码错误"

        if len(new_password) < 6:
            return False, "新密码长度不能少于6位"

        user.password = new_password
        self.save_data()
        return True, "密码修改成功"

    def delete_employee(self, username):
        for i, user in enumerate(self.users):
            if user.username == username and user.role == 'employee':
                self.users.pop(i)
                self.save_data()
                return True, "删除成功"
        return False, "员工不存在"

    def get_all_employees(self):
        return [user for user in self.users if user.role == 'employee']

    def get_employee_by_username(self, username):
        for user in self.users:
            if user.username == username:
                return user
        return None


system = EmployeeSystem()
config_mgr = ConfigManager()
file_manager = FileManager()
study_manager = StudyManager()
ledger_manager = LedgerManager()

# ========== HTML 模板 ==========
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>员工管理系统</title>
    <style>
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); width: 350px; }
        h2 { text-align: center; color: #333; margin-bottom: 30px; }
        input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #5a67d8; }
        .error { color: red; text-align: center; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>员工管理系统登录</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="手机号/管理员账号" required>
            <input type="password" name="password" placeholder="密码" required>
            <button type="submit">登录</button>
        </form>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
    </div>
</body>
</html>
'''

# 管理员界面HTML
ADMIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>管理员后台</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 24px; font-weight: bold; }
        .user-info { display: flex; align-items: center; gap: 15px; }
        .user-info a { color: white; text-decoration: none; }
        .container { max-width: 1400px; margin: 30px auto; padding: 0 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-card h3 { color: #667eea; margin-bottom: 10px; }
        .stat-card .number { font-size: 32px; font-weight: bold; color: #333; }
        .content-card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px; }
        .content-card h2 { color: #333; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #667eea; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #666; font-weight: bold; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #5a67d8; }
        button.danger { background: #dc3545; }
        button.danger:hover { background: #c82333; }
        button.success { background: #28a745; }
        button.success:hover { background: #218838; }
        .employee-table { width: 100%; border-collapse: collapse; }
        .employee-table th, .employee-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .employee-table th { background: #f8f9fa; }
        .edit-btn, .delete-btn { padding: 5px 10px; margin: 0 5px; font-size: 12px; border: none; border-radius: 3px; cursor: pointer; color: white; }
        .edit-btn { background: #28a745; }
        .delete-btn { background: #dc3545; }
        .permission-group { display: flex; gap: 20px; margin-top: 10px; flex-wrap: wrap; }
        .permission-item { display: flex; align-items: center; gap: 5px; cursor: pointer; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }
        .modal-content { background: white; border-radius: 10px; padding: 30px; width: 600px; max-width: 90%; max-height: 80%; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .close { cursor: pointer; font-size: 24px; color: #999; }
        .success-msg { background: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin-bottom: 20px; display: none; }
        .error-msg { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; margin-bottom: 20px; display: none; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid #ddd; }
        .tab-btn { background: none; padding: 10px 20px; border: none; cursor: pointer; }
        .tab-btn.active { color: #667eea; border-bottom: 2px solid #667eea; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .config-list { margin-top: 15px; max-height: 300px; overflow-y: auto; }
        .config-item { display: flex; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid #eee; }
        .add-form { display: flex; gap: 10px; margin-bottom: 15px; }
        .add-form input { flex: 1; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🏢 企业管理系统 - 管理员后台</div>
        <div class="user-info"><span>欢迎，{{ admin_name }}</span><a href="/main">员工工作台</a><a href="/logout">退出登录</a></div>
    </div>
    <div class="container">
        <div class="stats"><div class="stat-card"><h3>👥 员工总数</h3><div class="number">{{ employee_count }}</div></div><div class="stat-card"><h3>🏢 部门数量</h3><div class="number">{{ department_count }}</div></div></div>
        <div id="successMsg" class="success-msg"></div><div id="errorMsg" class="error-msg"></div>
        <div class="tabs"><button class="tab-btn" onclick="switchTab('add')">➕ 添加员工</button><button class="tab-btn active" onclick="switchTab('config')">⚙️ 配置管理</button><button class="tab-btn" onclick="switchTab('list')">📋 员工列表</button></div>
        <div id="tab-add" class="tab-content"><div class="content-card"><h2>➕ 添加新员工</h2>
            <form id="addEmployeeForm"><div class="form-group"><label>手机号 *</label><input type="tel" name="phone" id="addPhone" required placeholder="11位手机号"><small>账号和密码将自动设置为手机号</small></div>
            <div class="form-group"><label>姓名 *</label><input type="text" name="name" id="addName" required></div>
            <div class="form-group"><label>部门 *</label><select name="department" id="addDepartment" required><option value="">请选择部门</option>{% for dept in departments %}<option value="{{ dept }}">{{ dept }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>职位 *</label><select name="position" id="addPosition" required><option value="">请选择职位</option>{% for pos in positions %}<option value="{{ pos }}">{{ pos }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>职级</label><select name="rank" id="addRank"><option value="">请选择职级</option>{% for rank in ranks %}<option value="{{ rank }}">{{ rank }}</option>{% endfor %}</select></div>
            <div class="form-group"><label>访问权限</label><div class="permission-group"><label class="permission-item"><input type="checkbox" name="permissions" value="camera" checked> 📸 监控拍照</label><label class="permission-item"><input type="checkbox" name="permissions" value="files" checked> 📁 公司文件</label><label class="permission-item"><input type="checkbox" name="permissions" value="study" checked> 📚 学习交流</label><label class="permission-item"><input type="checkbox" name="permissions" value="upload" checked> 📤 台账上传</label><label class="permission-item"><input type="checkbox" name="permissions" value="structure" checked> 🏛️ 公司架构</label><label class="permission-item"><input type="checkbox" name="permissions" value="cross_dept_files"> 🔓 跨部门文件访问</label></div></div>
            <div class="form-group" id="deptPermissionsGroup" style="display:none;"><label>特定部门文件访问权限</label><div class="permission-group" id="deptPermissions">{% for dept in departments %}<label class="permission-item"><input type="checkbox" name="dept_permissions" value="{{ dept }}"> 📁 {{ dept }}</label>{% endfor %}</div></div>
            <button type="submit">添加员工</button><button type="button" onclick="resetForm()">重置</button></form></div></div>
        <div id="tab-config" class="tab-content active"><div class="content-card"><h2>🏢 部门管理</h2><div class="add-form"><input type="text" id="newDepartment" placeholder="新部门名称"><button onclick="addConfigItem('department')" class="success">➕ 添加</button></div><div id="departmentList" class="config-list">{% for dept in departments %}<div class="config-item"><span>{{ dept }}</span><button onclick="deleteConfigItem('department', '{{ dept }}')" class="danger">删除</button></div>{% endfor %}</div></div>
        <div class="content-card"><h2>💼 职位管理</h2><div class="add-form"><input type="text" id="newPosition" placeholder="新职位名称"><button onclick="addConfigItem('position')" class="success">➕ 添加</button></div><div id="positionList" class="config-list">{% for pos in positions %}<div class="config-item"><span>{{ pos }}</span><button onclick="deleteConfigItem('position', '{{ pos }}')" class="danger">删除</button></div>{% endfor %}</div></div>
        <div class="content-card"><h2>📊 职级管理</h2><div class="add-form"><input type="text" id="newRank" placeholder="新职级名称"><button onclick="addConfigItem('rank')" class="success">➕ 添加</button></div><div id="rankList" class="config-list">{% for rank in ranks %}<div class="config-item"><span>{{ rank }}</span><button onclick="deleteConfigItem('rank', '{{ rank }}')" class="danger">删除</button></div>{% endfor %}</div></div></div>
        <div id="tab-list" class="tab-content"><div class="content-card"><h2>📋 员工列表</h2><table class="employee-table"><thead><tr><th>手机号</th><th>姓名</th><th>部门</th><th>职位</th><th>职级</th><th>权限</th><th>操作</th></tr></thead><tbody id="employeeList">{% for emp in employees %}<tr id="row-{{ emp.username }}"><td>{{ emp.phone }}</td><td>{{ emp.name }}</td><td>{{ emp.department }}</td><td>{{ emp.position }}</td><td>{{ emp.rank }}</td><td>{% if 'camera' in emp.permissions %}📸{% endif %}{% if 'files' in emp.permissions %}📁{% endif %}{% if 'study' in emp.permissions %}📚{% endif %}{% if 'upload' in emp.permissions %}📤{% endif %}{% if 'structure' in emp.permissions %}🏛️{% endif %}</td><td><button class="edit-btn" onclick="editEmployee('{{ emp.username }}')">编辑</button><button class="delete-btn" onclick="deleteEmployee('{{ emp.username }}')">删除</button></td></tr>{% endfor %}</tbody></table></div></div>
        <a href="/main" class="back-link">← 返回员工工作台</a>
    </div>
    <div id="editModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>编辑员工信息</h3><span class="close" onclick="closeModal()">&times;</span></div>
    <form id="editEmployeeForm"><input type="hidden" name="username" id="editUsername"><div class="form-group"><label>姓名</label><input type="text" name="name" id="editName"></div>
    <div class="form-group"><label>部门</label><select name="department" id="editDepartment"><option value="">请选择部门</option>{% for dept in departments %}<option value="{{ dept }}">{{ dept }}</option>{% endfor %}</select></div>
    <div class="form-group"><label>职位</label><select name="position" id="editPosition"><option value="">请选择职位</option>{% for pos in positions %}<option value="{{ pos }}">{{ pos }}</option>{% endfor %}</select></div>
    <div class="form-group"><label>职级</label><select name="rank" id="editRank"><option value="">请选择职级</option>{% for rank in ranks %}<option value="{{ rank }}">{{ rank }}</option>{% endfor %}</select></div>
    <div class="form-group"><label>访问权限</label><div class="permission-group" id="editPermissions"></div></div>
    <div class="form-group" id="editDeptPermissionsGroup" style="display:none;"><label>特定部门文件访问权限</label><div class="permission-group" id="editDeptPermissions"></div></div>
    <button type="submit">保存修改</button></form></div></div>
    <script>
        let currentTab = 'config';
        function switchTab(tab) { currentTab = tab; document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active')); document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active')); if (tab === 'add') { document.querySelectorAll('.tab-btn')[0].classList.add('active'); document.getElementById('tab-add').classList.add('active'); } else if (tab === 'config') { document.querySelectorAll('.tab-btn')[1].classList.add('active'); document.getElementById('tab-config').classList.add('active'); } else if (tab === 'list') { document.querySelectorAll('.tab-btn')[2].classList.add('active'); document.getElementById('tab-list').classList.add('active'); } }
        function showMessage(msg, isSuccess) { const successDiv = document.getElementById('successMsg'); const errorDiv = document.getElementById('errorMsg'); if (isSuccess) { successDiv.textContent = msg; successDiv.style.display = 'block'; errorDiv.style.display = 'none'; setTimeout(() => successDiv.style.display = 'none', 3000); } else { errorDiv.textContent = msg; errorDiv.style.display = 'block'; successDiv.style.display = 'none'; setTimeout(() => errorDiv.style.display = 'none', 3000); } }
        function resetForm() { document.getElementById('addEmployeeForm').reset(); document.querySelectorAll('#addEmployeeForm input[name="permissions"]').forEach(cb => cb.checked = true); document.getElementById('deptPermissionsGroup').style.display = 'none'; }
        function refreshPageKeepTab() { sessionStorage.setItem('adminCurrentTab', currentTab); location.reload(); }
        document.addEventListener('DOMContentLoaded', function() { const savedTab = sessionStorage.getItem('adminCurrentTab'); if (savedTab && savedTab !== currentTab) switchTab(savedTab); sessionStorage.removeItem('adminCurrentTab'); document.querySelectorAll('#addEmployeeForm input[name="permissions"]').forEach(cb => cb.addEventListener('change', function() { const filesChecked = document.querySelector('#addEmployeeForm input[name="permissions"][value="files"]:checked'); document.getElementById('deptPermissionsGroup').style.display = filesChecked ? 'block' : 'none'; })); });
        document.getElementById('addEmployeeForm').addEventListener('submit', async (e) => { e.preventDefault(); const permissions = []; document.querySelectorAll('#addEmployeeForm input[name="permissions"]:checked').forEach(cb => permissions.push(cb.value)); if (permissions.includes('files')) { document.querySelectorAll('#addEmployeeForm input[name="dept_permissions"]:checked').forEach(cb => permissions.push(`dept_${cb.value}`)); } const data = { phone: document.getElementById('addPhone').value, name: document.getElementById('addName').value, department: document.getElementById('addDepartment').value, position: document.getElementById('addPosition').value, rank: document.getElementById('addRank').value, permissions: permissions }; try { const response = await fetch('/api/admin/add_employee', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }); const result = await response.json(); if (result.success) { showMessage(result.message, true); setTimeout(() => refreshPageKeepTab(), 1500); } else { showMessage(result.message, false); } } catch (error) { showMessage('网络错误，请重试', false); } });
        async function deleteEmployee(username) { if (confirm('确定要删除该员工吗？')) { const response = await fetch('/api/admin/delete_employee/' + username, { method: 'DELETE' }); const result = await response.json(); if (result.success) { showMessage(result.message, true); document.getElementById('row-' + username).remove(); } else { showMessage(result.message, false); } } }
        async function editEmployee(username) { const response = await fetch('/api/admin/get_employee/' + username); const emp = await response.json(); document.getElementById('editUsername').value = emp.username; document.getElementById('editName').value = emp.name; document.getElementById('editDepartment').value = emp.department || ''; document.getElementById('editPosition').value = emp.position || ''; document.getElementById('editRank').value = emp.rank || ''; const permissionsDiv = document.getElementById('editPermissions'); permissionsDiv.innerHTML = `<label class="permission-item"><input type="checkbox" name="permissions" value="camera" ${emp.permissions && emp.permissions.includes('camera') ? 'checked' : ''}> 📸 监控拍照</label><label class="permission-item"><input type="checkbox" name="permissions" value="files" ${emp.permissions && emp.permissions.includes('files') ? 'checked' : ''}> 📁 公司文件</label><label class="permission-item"><input type="checkbox" name="permissions" value="study" ${emp.permissions && emp.permissions.includes('study') ? 'checked' : ''}> 📚 学习交流</label><label class="permission-item"><input type="checkbox" name="permissions" value="upload" ${emp.permissions && emp.permissions.includes('upload') ? 'checked' : ''}> 📤 台账上传</label><label class="permission-item"><input type="checkbox" name="permissions" value="structure" ${emp.permissions && emp.permissions.includes('structure') ? 'checked' : ''}> 🏛️ 公司架构</label><label class="permission-item"><input type="checkbox" name="permissions" value="cross_dept_files" ${emp.permissions && emp.permissions.includes('cross_dept_files') ? 'checked' : ''}> 🔓 跨部门文件访问</label>`; const deptPermissionsDiv = document.getElementById('editDeptPermissions'); const departments = {{ departments|tojson }}; let deptHtml = ''; departments.forEach(dept => { const hasDeptPerm = emp.permissions && emp.permissions.includes(`dept_${dept}`); deptHtml += `<label class="permission-item"><input type="checkbox" name="dept_permissions" value="${dept}" ${hasDeptPerm ? 'checked' : ''}> 📁 ${dept}</label>`; }); deptPermissionsDiv.innerHTML = deptHtml; const filesChecked = emp.permissions && emp.permissions.includes('files'); document.getElementById('editDeptPermissionsGroup').style.display = filesChecked ? 'block' : 'none'; permissionsDiv.querySelectorAll('input[value="files"]').forEach(cb => cb.addEventListener('change', function() { document.getElementById('editDeptPermissionsGroup').style.display = this.checked ? 'block' : 'none'; })); document.getElementById('editModal').style.display = 'flex'; }
        function closeModal() { document.getElementById('editModal').style.display = 'none'; }
        document.getElementById('editEmployeeForm').addEventListener('submit', async (e) => { e.preventDefault(); const permissions = []; document.querySelectorAll('#editPermissions input[name="permissions"]:checked').forEach(cb => permissions.push(cb.value)); if (permissions.includes('files')) { document.querySelectorAll('#editDeptPermissions input[name="dept_permissions"]:checked').forEach(cb => permissions.push(`dept_${cb.value}`)); } const data = { username: document.getElementById('editUsername').value, name: document.getElementById('editName').value, department: document.getElementById('editDepartment').value, position: document.getElementById('editPosition').value, rank: document.getElementById('editRank').value, permissions: permissions }; const response = await fetch('/api/admin/update_employee', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }); const result = await response.json(); if (result.success) { showMessage(result.message, true); setTimeout(() => refreshPageKeepTab(), 1500); } else { showMessage(result.message, false); } });
        window.onclick = function(event) { if (event.target === document.getElementById('editModal')) closeModal(); }
        async function addConfigItem(type) { let inputId, name, listId; if (type === 'department') { inputId = 'newDepartment'; listId = 'departmentList'; name = document.getElementById(inputId).value; } else if (type === 'position') { inputId = 'newPosition'; listId = 'positionList'; name = document.getElementById(inputId).value; } else { inputId = 'newRank'; listId = 'rankList'; name = document.getElementById(inputId).value; } if (!name.trim()) { showMessage('请输入名称', false); return; } const response = await fetch('/api/admin/add_config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type: type, name: name}) }); const result = await response.json(); if (result.success) { showMessage(result.message, true); document.getElementById(inputId).value = ''; const listDiv = document.getElementById(listId); const newItem = document.createElement('div'); newItem.className = 'config-item'; newItem.innerHTML = `<span>${escapeHtml(name)}</span><button onclick="deleteConfigItem('${type}', '${escapeHtml(name)}')" class="danger">删除</button>`; listDiv.appendChild(newItem); updateSelectOptions(type, name, 'add'); } else { showMessage(result.message, false); } }
        async function deleteConfigItem(type, name) { if (confirm(`确定要删除吗？`)) { const response = await fetch('/api/admin/delete_config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type: type, name: name}) }); const result = await response.json(); if (result.success) { showMessage(result.message, true); const items = document.querySelectorAll(`#${type === 'department' ? 'departmentList' : (type === 'position' ? 'positionList' : 'rankList')} .config-item`); for (let item of items) { if (item.querySelector('span').innerText === name) { item.remove(); break; } } updateSelectOptions(type, name, 'remove'); } else { showMessage(result.message, false); } } }
        function updateSelectOptions(type, name, action) { let selectIds = []; if (type === 'department') { selectIds = ['addDepartment', 'editDepartment']; } else if (type === 'position') { selectIds = ['addPosition', 'editPosition']; } else if (type === 'rank') { selectIds = ['addRank', 'editRank']; } selectIds.forEach(selectId => { const select = document.getElementById(selectId); if (select) { if (action === 'add') { const option = document.createElement('option'); option.value = name; option.textContent = name; select.appendChild(option); } else if (action === 'remove') { for (let i = 0; i < select.options.length; i++) { if (select.options[i].value === name) { select.remove(i); break; } } } } }); }
        function escapeHtml(text) { const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
    </script>
</body>
</html>
'''

# 员工工作台主界面
MAIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>员工工作平台</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .header { background: rgba(255,255,255,0.95); box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 24px; font-weight: bold; color: #667eea; }
        .user-info { display: flex; align-items: center; gap: 15px; position: relative; }
        .avatar { width: 40px; height: 40px; background: #667eea; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 20px; cursor: pointer; }
        .dropdown { position: relative; display: inline-block; }
        .dropdown-content { display: none; position: absolute; right: 0; top: 45px; background-color: white; min-width: 160px; box-shadow: 0 8px 16px rgba(0,0,0,0.2); border-radius: 5px; z-index: 1; }
        .dropdown-content a { color: #333; padding: 12px 16px; text-decoration: none; display: block; }
        .dropdown-content a:hover { background-color: #f1f1f1; }
        .show { display: block; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
        .welcome-card { background: white; border-radius: 15px; padding: 30px; margin-bottom: 30px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .welcome-card h1 { color: #333; margin-bottom: 10px; }
        .welcome-card p { color: #666; }
        .modules { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; margin-top: 20px; }
        .module-card { background: white; border-radius: 15px; padding: 30px; text-align: center; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .module-card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        .module-icon { font-size: 48px; margin-bottom: 15px; }
        .module-title { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }
        .module-desc { font-size: 14px; color: #999; }
        .content-area { background: white; border-radius: 15px; padding: 30px; margin-top: 30px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); display: none; }
        .content-area.active { display: block; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        a { color: #667eea; text-decoration: none; }
        .password-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }
        .password-modal-content { background: white; border-radius: 10px; padding: 30px; width: 400px; max-width: 90%; }
        .password-modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .close-password { cursor: pointer; font-size: 24px; color: #999; }
        .password-form-group { margin-bottom: 15px; }
        .password-form-group input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .password-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; width: 100%; }
        .password-msg { margin-top: 10px; text-align: center; font-size: 14px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🏢 企业工作平台</div>
        <div class="user-info"><span>欢迎，{{ name }}</span><div class="dropdown"><div class="avatar" onclick="toggleDropdown()">{{ avatar }}</div><div id="dropdownMenu" class="dropdown-content"><a href="#" onclick="showChangePassword()">🔐 修改密码</a>{% if is_admin %}<a href="/admin">⚙️ 管理后台</a>{% endif %}<a href="/logout">🚪 退出登录</a></div></div></div>
    </div>
    <div class="container">
        <div class="welcome-card"><h1>欢迎回来，{{ name }}！</h1><p>今天是 {{ date }}，祝您工作愉快！</p></div>
        <div class="modules" id="modules">
            {% if 'camera' in permissions %}<div class="module-card" onclick="showModule('camera')"><div class="module-icon">📸</div><div class="module-title">监控拍照</div><div class="module-desc">实时监控与拍照记录</div></div>{% endif %}
            {% if 'files' in permissions %}<div class="module-card" onclick="showModule('files')"><div class="module-icon">📁</div><div class="module-title">公司文件</div><div class="module-desc">公司文档资料库</div></div>{% endif %}
            {% if 'study' in permissions %}<div class="module-card" onclick="showModule('study')"><div class="module-icon">📚</div><div class="module-title">学习交流</div><div class="module-desc">在线学习与交流</div></div>{% endif %}
            {% if 'upload' in permissions %}<div class="module-card" onclick="showModule('upload')"><div class="module-icon">📤</div><div class="module-title">台账上传</div><div class="module-desc">工作台账上传管理</div></div>{% endif %}
            {% if 'structure' in permissions %}<div class="module-card" onclick="showModule('structure')"><div class="module-icon">🏛️</div><div class="module-title">公司架构</div><div class="module-desc">组织架构与人员信息</div></div>{% endif %}
        </div>
        <div id="contentArea" class="content-area"></div>
    </div>
    <div id="passwordModal" class="password-modal"><div class="password-modal-content"><div class="password-modal-header"><h3>修改密码</h3><span class="close-password" onclick="closePasswordModal()">&times;</span></div>
    <form id="changePasswordForm"><div class="password-form-group"><label>原密码</label><input type="password" id="oldPassword" required></div><div class="password-form-group"><label>新密码</label><input type="password" id="newPassword" required minlength="6"></div><div class="password-form-group"><label>确认新密码</label><input type="password" id="confirmPassword" required></div><button type="submit" class="password-btn">确认修改</button><div id="passwordMsg" class="password-msg"></div></form></div></div>
    <script>
        function toggleDropdown() { document.getElementById("dropdownMenu").classList.toggle("show"); }
        window.onclick = function(event) { if (!event.target.matches('.avatar')) { var dropdowns = document.getElementsByClassName("dropdown-content"); for (var i = 0; i < dropdowns.length; i++) { var openDropdown = dropdowns[i]; if (openDropdown.classList.contains('show')) openDropdown.classList.remove('show'); } } }
        function showChangePassword() { document.getElementById('passwordModal').style.display = 'flex'; }
        function closePasswordModal() { document.getElementById('passwordModal').style.display = 'none'; document.getElementById('changePasswordForm').reset(); document.getElementById('passwordMsg').innerHTML = ''; }
        document.getElementById('changePasswordForm').addEventListener('submit', async (e) => { e.preventDefault(); const oldPassword = document.getElementById('oldPassword').value; const newPassword = document.getElementById('newPassword').value; const confirmPassword = document.getElementById('confirmPassword').value; if (newPassword !== confirmPassword) { document.getElementById('passwordMsg').innerHTML = '<span style="color:red;">两次输入的新密码不一致！</span>'; return; } if (newPassword.length < 6) { document.getElementById('passwordMsg').innerHTML = '<span style="color:red;">新密码长度不能少于6位！</span>'; return; } const response = await fetch('/api/change_password', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }) }); const result = await response.json(); if (result.success) { document.getElementById('passwordMsg').innerHTML = '<span style="color:green;">' + result.message + '</span>'; setTimeout(() => closePasswordModal(), 1500); } else { document.getElementById('passwordMsg').innerHTML = '<span style="color:red;">' + result.message + '</span>'; } });
        function showModule(module) { fetch(`/api/module/${module}`).then(res => res.text()).then(html => { document.getElementById('contentArea').innerHTML = html; document.getElementById('contentArea').classList.add('active'); document.getElementById('modules').style.display = 'none'; window.scrollTo({ top: 0, behavior: 'smooth' }); }); }
        function hideModule() { document.getElementById('contentArea').classList.remove('active'); document.getElementById('modules').style.display = 'grid'; document.getElementById('contentArea').innerHTML = ''; }
    </script>
</body>
</html>
'''

# 公司架构模块HTML
STRUCTURE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        .structure-container { padding: 20px; }
        .department { margin-bottom: 30px; background: #f8f9fa; border-radius: 10px; padding: 20px; }
        .department-title { font-size: 24px; font-weight: bold; color: #667eea; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #667eea; }
        .employees { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; margin-top: 20px; }
        .employee-card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .employee-name { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 8px; border-left: 3px solid #667eea; padding-left: 12px; }
        .employee-details { margin-top: 12px; }
        .detail-item { display: flex; align-items: center; margin-bottom: 8px; font-size: 14px; }
        .detail-label { width: 60px; color: #999; }
        .detail-value { color: #666; flex: 1; }
        .detail-value.position { color: #667eea; font-weight: bold; }
        .detail-value.rank { color: #ff9800; }
        .detail-value.phone { color: #4caf50; }
        .back-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
    </style>
</head>
<body>
    <button class="back-btn" onclick="parent.hideModule()">← 返回主界面</button>
    <div class="structure-container">
        {% for dept, employees in structure.items() %}
        <div class="department">
            <div class="department-title">{{ dept }}</div>
            <div class="employees">
                {% for emp in employees %}
                <div class="employee-card">
                    <div class="employee-name">{{ emp.name }}</div>
                    <div class="employee-details">
                        <div class="detail-item"><span class="detail-label">职位：</span><span class="detail-value position">{{ emp.position }}</span></div>
                        <div class="detail-item"><span class="detail-label">职级：</span><span class="detail-value rank">{{ emp.rank }}</span></div>
                        <div class="detail-item"><span class="detail-label">电话：</span><span class="detail-value phone">{{ emp.phone }}</span></div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
'''

# 公司文件模块HTML
FILES_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>公司文件</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        .files-container { padding: 20px; }
        .toolbar { margin-bottom: 20px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .dept-select { padding: 8px 15px; border: 1px solid #ddd; border-radius: 5px; min-width: 150px; }
        .upload-btn, .refresh-btn { background: #667eea; color: white; border: none; padding: 8px 20px; border-radius: 5px; cursor: pointer; }
        .upload-btn { background: #28a745; }
        .refresh-btn { background: #17a2b8; }
        .back-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
        .file-list { background: #f8f9fa; border-radius: 10px; padding: 20px; min-height: 400px; }
        .file-item { background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .file-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px; flex-wrap: wrap; gap: 10px; }
        .file-name { font-size: 16px; font-weight: bold; color: #667eea; cursor: pointer; word-break: break-all; flex: 1; }
        .file-actions { display: flex; gap: 5px; }
        .file-actions button { padding: 5px 10px; border: none; border-radius: 3px; cursor: pointer; }
        .download-btn { background: #28a745; color: white; }
        .delete-btn { background: #dc3545; color: white; }
        .file-info { color: #666; font-size: 12px; margin-top: 10px; display: flex; gap: 20px; flex-wrap: wrap; }
        .empty-state { text-align: center; padding: 50px; color: #999; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }
        .modal-content { background: white; border-radius: 10px; padding: 30px; width: 500px; max-width: 90%; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .close { cursor: pointer; font-size: 24px; color: #999; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #666; font-weight: bold; }
        .form-group select, .form-group input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .loading { text-align: center; padding: 20px; color: #667eea; }
        .permission-denied { text-align: center; padding: 50px; }
        .permission-denied .icon { font-size: 64px; margin-bottom: 20px; }
        .permission-denied .title { font-size: 24px; color: #f0ad4e; margin-bottom: 10px; }
    </style>
</head>
<body>
    <button class="back-btn" onclick="parent.hideModule()">← 返回主界面</button>
    <div class="files-container">
        <div class="toolbar">
            <select id="deptSelect" class="dept-select" onchange="loadFiles()"><option value="all">所有部门</option></select>
            <button class="upload-btn" onclick="showUploadModal()">📤 上传文件</button>
            <button class="refresh-btn" onclick="loadFiles()">🔄 刷新</button>
        </div>
        <div id="fileList" class="file-list"><div class="loading">加载中...</div></div>
    </div>
    <div id="uploadModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>上传文件</h3><span class="close" onclick="closeUploadModal()">&times;</span></div>
    <form id="uploadForm" enctype="multipart/form-data"><div class="form-group"><label>选择部门 *</label><select id="uploadDept" required><option value="">请选择部门</option></select></div>
    <div class="form-group"><label>选择文件 *</label><input type="file" id="uploadFile" required></div>
    <button type="submit" class="upload-btn" style="width:100%">上传</button></form></div></div>
    <script>
        document.addEventListener('DOMContentLoaded', function() { loadDepartments(); loadFiles(); });
        async function loadDepartments() { try { const response = await fetch('/api/files/all_departments'); const data = await response.json(); if (data.success && data.departments) { const deptSelect = document.getElementById('deptSelect'); while (deptSelect.options.length > 1) deptSelect.remove(1); data.departments.forEach(deptName => { const option = document.createElement('option'); option.value = deptName; option.textContent = deptName; deptSelect.appendChild(option); }); } } catch (error) { console.error(error); } }
        async function loadFiles() { const dept = document.getElementById('deptSelect').value; const fileListDiv = document.getElementById('fileList'); fileListDiv.innerHTML = '<div class="loading">📂 加载文件中...</div>'; try { const response = await fetch(`/api/files/list?department=${dept}&t=${Date.now()}`); const data = await response.json(); if (data.success) { displayFiles(data.files); } else { if (data.message === 'no_permission') { fileListDiv.innerHTML = `<div class="permission-denied"><div class="icon">🔒</div><div class="title">暂无访问权限</div><div class="desc">您没有权限访问 ${dept === 'all' ? '其他部门' : dept} 的文件</div></div>`; } else { fileListDiv.innerHTML = '<div class="empty-state">加载失败</div>'; } } } catch (error) { fileListDiv.innerHTML = '<div class="empty-state">网络错误，请刷新</div>'; } }
        function displayFiles(files) { const fileListDiv = document.getElementById('fileList'); if (!files || files.length === 0) { fileListDiv.innerHTML = '<div class="empty-state">📁 暂无文件，点击"上传文件"按钮上传</div>'; return; } let html = ''; files.forEach(file => { html += `<div class="file-item"><div class="file-header"><div class="file-name" onclick="downloadFile('${file.id}')">📄 ${escapeHtml(file.filename)}</div><div class="file-actions"><button class="download-btn" onclick="downloadFile('${file.id}')">📥 下载</button><button class="delete-btn" onclick="deleteFile('${file.id}')">🗑️ 删除</button></div></div><div class="file-info"><span>📁 ${escapeHtml(file.department)}</span><span>👤 ${escapeHtml(file.uploader_name)}</span><span>📅 ${file.upload_time}</span><span>💾 ${file.size_display}</span><span>📥 下载 ${file.download_count || 0} 次</span></div></div>`; }); fileListDiv.innerHTML = html; }
        async function downloadFile(fileId) { try { window.location.href = `/api/files/download/${fileId}`; setTimeout(() => loadFiles(), 1000); } catch (error) { alert('下载失败'); } }
        async function deleteFile(fileId) { if (!confirm('确定删除？')) return; try { const response = await fetch(`/api/files/delete/${fileId}`, { method: 'DELETE' }); const result = await response.json(); if (result.success) { alert('删除成功'); loadFiles(); } else { alert('删除失败：' + result.message); } } catch (error) { alert('删除失败'); } }
        async function showUploadModal() { const modal = document.getElementById('uploadModal'); const deptSelect = document.getElementById('uploadDept'); deptSelect.innerHTML = '<option value="">加载中...</option>'; modal.style.display = 'flex'; try { const response = await fetch('/api/files/upload_departments'); const data = await response.json(); deptSelect.innerHTML = '<option value="">请选择部门</option>'; if (data.success && data.departments && data.departments.length > 0) { data.departments.forEach(dept => { const option = document.createElement('option'); option.value = dept; option.textContent = dept; deptSelect.appendChild(option); }); } else { deptSelect.innerHTML = '<option value="">暂无上传权限</option>'; alert('您没有上传权限'); closeUploadModal(); } } catch (error) { deptSelect.innerHTML = '<option value="">加载失败</option>'; } }
        function closeUploadModal() { document.getElementById('uploadModal').style.display = 'none'; document.getElementById('uploadForm').reset(); }
        document.getElementById('uploadForm').addEventListener('submit', async (e) => { e.preventDefault(); const dept = document.getElementById('uploadDept').value; const file = document.getElementById('uploadFile').files[0]; if (!dept || !file) { alert('请选择部门和文件'); return; } const formData = new FormData(); formData.append('files', file); formData.append('department', dept); const submitBtn = document.querySelector('#uploadForm button'); const originalText = submitBtn.textContent; submitBtn.textContent = '上传中...'; submitBtn.disabled = true; try { const response = await fetch('/api/files/upload', { method: 'POST', body: formData }); const result = await response.json(); if (result.success) { alert('上传成功！'); closeUploadModal(); loadFiles(); } else { alert('上传失败：' + result.message); } } catch (error) { alert('上传失败'); } finally { submitBtn.textContent = originalText; submitBtn.disabled = false; } });
        function escapeHtml(text) { if (!text) return ''; const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
        window.onclick = function(event) { const modal = document.getElementById('uploadModal'); if (event.target === modal) closeUploadModal(); }
    </script>
</body>
</html>
'''

# 台账上传模块HTML（优化版）
UPLOAD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>台账上传</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        .upload-container { padding: 20px; }
        .toolbar { margin-bottom: 20px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .dept-select, .date-input, .search-input { padding: 8px 15px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
        .dept-select { min-width: 150px; }
        .date-input { width: 130px; }
        .search-input { width: 200px; }
        .upload-btn, .refresh-btn, .search-btn, .clear-btn { background: #667eea; color: white; border: none; padding: 8px 20px; border-radius: 5px; cursor: pointer; }
        .upload-btn { background: #28a745; }
        .upload-btn:hover { background: #218838; }
        .refresh-btn { background: #17a2b8; }
        .refresh-btn:hover { background: #138496; }
        .search-btn { background: #667eea; }
        .search-btn:hover { background: #5a67d8; }
        .clear-btn { background: #6c757d; }
        .clear-btn:hover { background: #5a6268; }
        .back-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
        .record-list { background: #f8f9fa; border-radius: 10px; padding: 20px; min-height: 400px; }
        .record-item { background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); transition: all 0.3s; }
        .record-item:hover { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
        .record-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px; flex-wrap: wrap; gap: 10px; }
        .record-name { font-size: 16px; font-weight: bold; color: #667eea; cursor: pointer; word-break: break-all; flex: 1; }
        .record-name:hover { text-decoration: underline; }
        .record-actions { display: flex; gap: 5px; }
        .record-actions button { padding: 5px 10px; border: none; border-radius: 3px; cursor: pointer; }
        .download-btn { background: #28a745; color: white; }
        .download-btn:hover { background: #218838; }
        .delete-btn { background: #dc3545; color: white; }
        .delete-btn:hover { background: #c82333; }
        .record-info { color: #666; font-size: 12px; margin-top: 10px; display: flex; gap: 20px; flex-wrap: wrap; }
        .record-info span { display: inline-flex; align-items: center; gap: 5px; }
        .empty-state { text-align: center; padding: 50px; color: #999; }
        .upload-area { border: 2px dashed #28a745; border-radius: 10px; padding: 30px; text-align: center; margin-bottom: 20px; cursor: pointer; transition: all 0.3s; background: #f8fff8; }
        .upload-area:hover { background: #f0f8f0; border-color: #218838; }
        .upload-area.drag-over { background: #e8f5e8; border-color: #28a745; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }
        .modal-content { background: white; border-radius: 10px; padding: 30px; width: 500px; max-width: 90%; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .close { cursor: pointer; font-size: 24px; color: #999; }
        .close:hover { color: #333; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #666; font-weight: bold; }
        .form-group select, .form-group input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .loading { text-align: center; padding: 20px; color: #667eea; }
        .permission-denied { text-align: center; padding: 50px; }
        .permission-denied .icon { font-size: 64px; margin-bottom: 20px; }
        .permission-denied .title { font-size: 24px; color: #f0ad4e; margin-bottom: 10px; }
        .stats { display: inline-flex; gap: 10px; margin-left: auto; }
        .stats span { background: #e9ecef; padding: 5px 10px; border-radius: 20px; font-size: 12px; }
    </style>
</head>
<body>
    <button class="back-btn" onclick="parent.hideModule()">← 返回主界面</button>
    <div class="upload-container">
        <!-- 工具栏：部门选择、时间筛选、搜索 -->
        <div class="toolbar">
            <select id="deptSelect" class="dept-select" onchange="loadRecords()">
                <option value="all">所有部门</option>
            </select>
            <input type="date" id="startDate" class="date-input" placeholder="开始日期">
            <span style="color:#999;">至</span>
            <input type="date" id="endDate" class="date-input" placeholder="结束日期">
            <input type="text" id="searchKeyword" class="search-input" placeholder="搜索文件名或上传人">
            <button class="search-btn" onclick="loadRecords()">🔍 搜索</button>
            <button class="clear-btn" onclick="clearFilters()">🗑️ 清除筛选</button>
            <button class="refresh-btn" onclick="loadRecords()">🔄 刷新</button>
        </div>

        <!-- 上传区域（只有有上传权限的人才显示） -->
        {% if can_upload %}
        <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
            <p style="font-size: 48px; margin-bottom: 10px;">📤</p>
            <p style="font-size: 16px; font-weight: bold;">点击或拖拽文件到此上传</p>
            <p style="font-size: 12px; color: #999;">支持所有文件格式</p>
            <input type="file" id="fileInput" style="display:none;" onchange="uploadFile(this.files[0])">
        </div>
        {% endif %}

        <!-- 台账记录列表 -->
        <div class="record-list">
            <h3>📋 台账记录 <span id="recordCount" class="stats"></span></h3>
            <div id="records"></div>
        </div>
    </div>

    <!-- 上传部门选择模态框 -->
    <div id="uploadModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>选择上传部门</h3>
                <span class="close" onclick="closeUploadModal()">&times;</span>
            </div>
            <div class="form-group">
                <label>选择部门 *</label>
                <select id="uploadDept" required>
                    <option value="">请选择部门</option>
                </select>
            </div>
            <button class="upload-btn" style="width:100%" onclick="confirmUpload()">确认上传</button>
        </div>
    </div>

    <script>
        let pendingFile = null;

        document.addEventListener('DOMContentLoaded', function() {
            loadDepartments();
            loadRecords();
            initDragDrop();
        });

        async function loadDepartments() {
            try {
                const response = await fetch('/api/ledger/departments');
                const data = await response.json();
                if (data.success && data.departments) {
                    const deptSelect = document.getElementById('deptSelect');
                    while (deptSelect.options.length > 1) deptSelect.remove(1);
                    data.departments.forEach(deptName => {
                        const option = document.createElement('option');
                        option.value = deptName;
                        option.textContent = deptName;
                        deptSelect.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('加载部门列表失败:', error);
            }
        }

        async function loadRecords() {
            const dept = document.getElementById('deptSelect').value;
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const keyword = document.getElementById('searchKeyword').value;

            const recordsDiv = document.getElementById('records');
            recordsDiv.innerHTML = '<div class="loading">📂 加载中...</div>';

            try {
                let url = `/api/ledger/records?department=${dept}`;
                if (startDate) url += `&start_date=${startDate}`;
                if (endDate) url += `&end_date=${endDate}`;
                if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;

                const response = await fetch(url);
                const data = await response.json();

                if (data.success) {
                    displayRecords(data.records);
                    document.getElementById('recordCount').innerHTML = `共 ${data.records.length} 条记录`;
                } else {
                    if (data.message === 'no_permission') {
                        recordsDiv.innerHTML = `<div class="permission-denied"><div class="icon">🔒</div><div class="title">暂无访问权限</div><div class="desc">您没有权限查看台账记录，请联系管理员开通权限。</div></div>`;
                    } else {
                        recordsDiv.innerHTML = '<div class="empty-state">加载失败</div>';
                    }
                }
            } catch (error) {
                recordsDiv.innerHTML = '<div class="empty-state">网络错误，请刷新重试</div>';
            }
        }

        function displayRecords(records) {
            const recordsDiv = document.getElementById('records');
            if (!records || records.length === 0) {
                recordsDiv.innerHTML = '<div class="empty-state">📋 暂无台账记录，请上传文件</div>';
                return;
            }

            let html = '';
            records.forEach(record => {
                html += `
                    <div class="record-item" id="record-${record.id}">
                        <div class="record-header">
                            <div class="record-name" onclick="downloadRecord(${record.id})">
                                📄 ${escapeHtml(record.filename)}
                            </div>
                            <div class="record-actions">
                                <button class="download-btn" onclick="downloadRecord(${record.id})">📥 下载</button>
                                <button class="delete-btn" onclick="deleteRecord(${record.id})">🗑️ 删除</button>
                            </div>
                        </div>
                        <div class="record-info">
                            <span>📁 ${escapeHtml(record.department)}</span>
                            <span>👤 ${escapeHtml(record.uploader_name)} (${record.uploader})</span>
                            <span>📅 ${record.upload_time}</span>
                            <span>💾 ${record.size_display}</span>
                            <span>📥 下载 ${record.download_count || 0} 次</span>
                        </div>
                    </div>
                `;
            });
            recordsDiv.innerHTML = html;
        }

        function uploadFile(file) {
            if (!file) return;
            pendingFile = file;
            // 显示部门选择模态框
            showUploadModal();
        }

        async function showUploadModal() {
            const modal = document.getElementById('uploadModal');
            const deptSelect = document.getElementById('uploadDept');
            deptSelect.innerHTML = '<option value="">加载中...</option>';
            modal.style.display = 'flex';

            try {
                const response = await fetch('/api/ledger/upload_departments');
                const data = await response.json();
                deptSelect.innerHTML = '<option value="">请选择部门</option>';
                if (data.success && data.departments && data.departments.length > 0) {
                    data.departments.forEach(dept => {
                        const option = document.createElement('option');
                        option.value = dept;
                        option.textContent = dept;
                        deptSelect.appendChild(option);
                    });
                } else {
                    deptSelect.innerHTML = '<option value="">暂无上传权限</option>';
                    alert('您没有上传台账的权限，请联系管理员');
                    closeUploadModal();
                }
            } catch (error) {
                deptSelect.innerHTML = '<option value="">加载失败</option>';
            }
        }

        function closeUploadModal() {
            document.getElementById('uploadModal').style.display = 'none';
            pendingFile = null;
        }

        async function confirmUpload() {
            const dept = document.getElementById('uploadDept').value;
            if (!dept) {
                alert('请选择部门');
                return;
            }
            if (!pendingFile) {
                alert('请选择文件');
                closeUploadModal();
                return;
            }

            const formData = new FormData();
            formData.append('file', pendingFile);
            formData.append('department', dept);

            try {
                const response = await fetch('/api/ledger/upload', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (result.success) {
                    alert('✅ 上传成功！');
                    closeUploadModal();
                    loadRecords();
                } else {
                    alert('❌ 上传失败：' + result.message);
                }
            } catch (error) {
                alert('上传失败，请重试');
            }
        }

        async function downloadRecord(recordId) {
            try {
                window.location.href = `/api/ledger/download/${recordId}`;
                setTimeout(() => loadRecords(), 1000);
            } catch (error) {
                alert('下载失败');
            }
        }

        async function deleteRecord(recordId) {
            if (!confirm('确定要删除这个台账记录吗？此操作不可恢复！')) return;
            try {
                const response = await fetch(`/api/ledger/record/${recordId}`, {
                    method: 'DELETE'
                });
                const result = await response.json();
                if (result.success) {
                    alert('✅ 删除成功');
                    loadRecords();
                } else {
                    alert('❌ 删除失败：' + result.message);
                }
            } catch (error) {
                alert('删除失败');
            }
        }

        function clearFilters() {
            document.getElementById('startDate').value = '';
            document.getElementById('endDate').value = '';
            document.getElementById('searchKeyword').value = '';
            loadRecords();
        }

        function initDragDrop() {
            const uploadArea = document.getElementById('uploadArea');
            if (!uploadArea) return;

            uploadArea.addEventListener('dragover', function(e) {
                e.preventDefault();
                uploadArea.classList.add('drag-over');
            });
            uploadArea.addEventListener('dragleave', function(e) {
                uploadArea.classList.remove('drag-over');
            });
            uploadArea.addEventListener('drop', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('drag-over');
                const file = e.dataTransfer.files[0];
                if (file) uploadFile(file);
            });
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        window.onclick = function(event) {
            const modal = document.getElementById('uploadModal');
            if (event.target === modal) closeUploadModal();
        }
    </script>
</body>
</html>
'''

# 学习交流模块HTML
STUDY_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>学习交流</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        .study-container { padding: 20px; max-width: 1400px; margin: 0 auto; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #e0e0e0; }
        .tab-btn { background: none; border: none; padding: 12px 24px; font-size: 16px; cursor: pointer; color: #666; }
        .tab-btn:hover { color: #667eea; }
        .tab-btn.active { color: #667eea; border-bottom: 2px solid #667eea; margin-bottom: -2px; }
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .articles-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px; }
        .upload-article-btn { background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .articles-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
        .article-card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); cursor: pointer; transition: all 0.3s; }
        .article-card:hover { transform: translateY(-3px); box-shadow: 0 4px 20px rgba(0,0,0,0.15); }
        .article-icon { font-size: 48px; margin-bottom: 10px; }
        .article-title { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }
        .article-meta { color: #999; font-size: 12px; margin-bottom: 10px; display: flex; gap: 15px; }
        .article-desc { color: #666; font-size: 14px; margin-bottom: 15px; line-height: 1.5; }
        .article-stats { display: flex; gap: 15px; color: #999; font-size: 12px; margin-bottom: 15px; }
        .article-actions { display: flex; gap: 10px; }
        .view-btn, .comment-btn { background: #667eea; color: white; border: none; padding: 6px 12px; border-radius: 5px; cursor: pointer; font-size: 12px; }
        .delete-article-btn { background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 5px; cursor: pointer; font-size: 12px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }
        .modal-content { background: white; border-radius: 10px; width: 700px; max-width: 90%; max-height: 80%; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 20px; border-bottom: 1px solid #eee; }
        .close { cursor: pointer; font-size: 24px; color: #999; }
        .modal-body { padding: 20px; }
        .article-detail-title { font-size: 20px; font-weight: bold; color: #333; margin-bottom: 10px; }
        .article-detail-meta { color: #999; font-size: 12px; margin-bottom: 20px; }
        .article-detail-content { margin-bottom: 20px; }
        .article-detail-content iframe { width: 100%; min-height: 500px; border: 1px solid #ddd; border-radius: 5px; }
        .comments-section { border-top: 1px solid #eee; padding-top: 20px; margin-top: 20px; }
        .comments-title { font-size: 16px; font-weight: bold; margin-bottom: 15px; }
        .comment-list { max-height: 300px; overflow-y: auto; margin-bottom: 15px; }
        .comment-item { background: #f8f9fa; padding: 12px; border-radius: 8px; margin-bottom: 10px; }
        .comment-user { font-weight: bold; color: #667eea; margin-bottom: 5px; }
        .comment-time { font-size: 11px; color: #999; margin-left: 10px; font-weight: normal; }
        .comment-content { color: #666; font-size: 14px; }
        .comment-input-area { display: flex; gap: 10px; margin-top: 15px; }
        .comment-input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px; resize: vertical; }
        .submit-comment-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .discussion-area { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .discussion-input-area { display: flex; gap: 10px; margin-bottom: 20px; }
        .discussion-input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 8px; resize: vertical; font-size: 14px; }
        .publish-btn { background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; }
        .discussion-list { max-height: 600px; overflow-y: auto; }
        .discussion-item { background: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 15px; }
        .discussion-header-info { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .discussion-user { font-weight: bold; color: #667eea; }
        .discussion-time { font-size: 12px; color: #999; }
        .discussion-content { color: #333; font-size: 14px; margin-bottom: 10px; }
        .discussion-actions { display: flex; gap: 10px; margin-bottom: 10px; }
        .reply-btn, .delete-discussion-btn { background: none; border: none; cursor: pointer; font-size: 12px; }
        .reply-btn { color: #667eea; }
        .delete-discussion-btn { color: #dc3545; }
        .replies-area { margin-top: 10px; padding-left: 20px; border-left: 2px solid #ddd; }
        .reply-item { background: white; padding: 10px; border-radius: 8px; margin-top: 10px; }
        .reply-user { font-weight: bold; color: #667eea; font-size: 12px; }
        .reply-time { font-size: 11px; color: #999; margin-left: 10px; }
        .reply-content { color: #666; font-size: 13px; margin-top: 5px; }
        .reply-input-area { display: flex; gap: 10px; margin-top: 10px; }
        .reply-input { flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 5px; font-size: 12px; }
        .submit-reply-btn { background: #667eea; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-size: 12px; }
        .back-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
        .empty-state { text-align: center; padding: 50px; color: #999; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #666; font-weight: bold; }
        .form-group input, .form-group textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 5px; }
    </style>
</head>
<body>
    <button class="back-btn" onclick="parent.hideModule()">← 返回主界面</button>
    <div class="study-container">
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('articles')">📚 学习文章</button>
            <button class="tab-btn" onclick="switchTab('discussion')">💬 讨论区</button>
        </div>
        <div id="tab-articles" class="tab-content active">
            <div class="articles-header"><h2>📖 学习文章</h2><button class="upload-article-btn" onclick="showUploadArticleModal()">📤 上传文章</button></div>
            <div id="articles-list" class="articles-grid"><div class="empty-state">加载中...</div></div>
        </div>
        <div id="tab-discussion" class="tab-content">
            <div class="discussion-area">
                <div class="discussion-header"><h3>💬 自由讨论区</h3><p style="color:#999; font-size:12px; margin-top:5px;">发表你的观点，与同事交流学习心得</p></div>
                <div class="discussion-input-area"><textarea id="discussionContent" class="discussion-input" rows="3" placeholder="分享你的想法..."></textarea><button class="publish-btn" onclick="publishDiscussion()">发布</button></div>
                <div id="discussion-list" class="discussion-list"><div class="empty-state">加载中...</div></div>
            </div>
        </div>
    </div>
    <div id="uploadArticleModal" class="modal"><div class="modal-content"><div class="modal-header"><h3>上传学习文章</h3><span class="close" onclick="closeUploadArticleModal()">&times;</span></div>
    <div class="modal-body"><form id="uploadArticleForm" enctype="multipart/form-data"><div class="form-group"><label>文章标题 *</label><input type="text" id="articleTitle" required></div><div class="form-group"><label>文章简介</label><textarea id="articleDesc" rows="3"></textarea></div><div class="form-group"><label>选择文件 * (PDF/Word/PPT等)</label><input type="file" id="articleFile" accept=".pdf,.doc,.docx,.ppt,.pptx,.txt" required></div><button type="submit" class="upload-article-btn" style="width:100%">上传</button></form></div></div></div>
    <div id="articleDetailModal" class="modal"><div class="modal-content"><div class="modal-header"><h3 id="detailTitle">文章详情</h3><span class="close" onclick="closeArticleDetailModal()">&times;</span></div><div class="modal-body" id="articleDetailBody"></div></div></div>
    <script>
        let currentArticleId = null;
        function switchTab(tab) { document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active')); document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active')); if (tab === 'articles') { document.querySelectorAll('.tab-btn')[0].classList.add('active'); document.getElementById('tab-articles').classList.add('active'); loadArticles(); } else { document.querySelectorAll('.tab-btn')[1].classList.add('active'); document.getElementById('tab-discussion').classList.add('active'); loadDiscussions(); } }
        async function loadArticles() { try { const response = await fetch('/api/study/articles'); const data = await response.json(); if (data.success) displayArticles(data.articles); else document.getElementById('articles-list').innerHTML = '<div class="empty-state">加载失败</div>'; } catch (error) { document.getElementById('articles-list').innerHTML = '<div class="empty-state">加载失败，请刷新</div>'; } }
        function displayArticles(articles) { const container = document.getElementById('articles-list'); if (!articles || articles.length === 0) { container.innerHTML = '<div class="empty-state">📚 暂无文章，点击"上传文章"按钮上传</div>'; return; } let html = ''; articles.forEach(article => { let icon = '📄'; const ext = article.filename.split('.').pop().toUpperCase(); if (ext === 'PDF') icon = '📕'; else if (ext === 'DOC' || ext === 'DOCX') icon = '📘'; else if (ext === 'PPT' || ext === 'PPTX') icon = '📙'; html += `<div class="article-card" onclick="viewArticle(${article.id})"><div class="article-icon">${icon}</div><div class="article-title">${escapeHtml(article.title)}</div><div class="article-meta"><span>👤 ${escapeHtml(article.uploader_name)}</span><span>📅 ${article.upload_time}</span></div><div class="article-desc">${escapeHtml(article.description || '暂无简介')}</div><div class="article-stats"><span>👁️ 浏览 ${article.views || 0}</span><span>💬 评论 ${article.comments ? article.comments.length : 0}</span></div><div class="article-actions"><button class="view-btn" onclick="event.stopPropagation();viewArticle(${article.id})">查看详情</button><button class="delete-article-btn" onclick="event.stopPropagation();deleteArticle(${article.id})">删除</button></div></div>`; }); container.innerHTML = html; }
        async function viewArticle(articleId) { currentArticleId = articleId; try { const response = await fetch(`/api/study/article/${articleId}`); const data = await response.json(); if (data.success) { const article = data.article; document.getElementById('detailTitle').innerHTML = escapeHtml(article.title); let commentsHtml = '<div class="comments-section"><div class="comments-title">📝 评论 (<span id="commentCount">' + (article.comments ? article.comments.length : 0) + '</span>)</div><div class="comment-list">'; if (article.comments && article.comments.length > 0) { article.comments.forEach(comment => { commentsHtml += `<div class="comment-item"><div class="comment-user">${escapeHtml(comment.user_name)} <span class="comment-time">${comment.time}</span></div><div class="comment-content">${escapeHtml(comment.content)}</div></div>`; }); } else { commentsHtml += '<div style="text-align:center; color:#999; padding:20px;">暂无评论，快来抢沙发！</div>'; } commentsHtml += '</div><div class="comment-input-area"><textarea id="newComment" class="comment-input" rows="2" placeholder="写下你的评论..."></textarea><button class="submit-comment-btn" onclick="submitComment()">发表评论</button></div></div>'; const fileUrl = `/api/study/download/${article.id}`; const fileExt = article.filename.split('.').pop().toLowerCase(); let contentHtml = fileExt === 'pdf' ? `<iframe src="${fileUrl}" style="width:100%; min-height:500px;"></iframe>` : `<div style="text-align:center; padding:40px;"><div style="font-size:48px; margin-bottom:20px;">📄</div><a href="${fileUrl}" download="${article.filename}" style="background:#667eea; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">点击下载文件</a></div>`; document.getElementById('articleDetailBody').innerHTML = `<div class="article-detail-title">${escapeHtml(article.title)}</div><div class="article-detail-meta">👤 ${escapeHtml(article.uploader_name)} | 📅 ${article.upload_time} | 📄 ${article.filename}</div><div class="article-detail-content">${contentHtml}</div>${commentsHtml}`; document.getElementById('articleDetailModal').style.display = 'flex'; } } catch (error) { alert('加载文章失败'); } }
        async function submitComment() { const content = document.getElementById('newComment').value; if (!content.trim()) { alert('请输入评论内容'); return; } try { const response = await fetch(`/api/study/article/${currentArticleId}/comment`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: content}) }); const result = await response.json(); if (result.success) { document.getElementById('newComment').value = ''; viewArticle(currentArticleId); loadArticles(); } else { alert(result.message); } } catch (error) { alert('评论失败'); } }
        async function deleteArticle(articleId) { if (!confirm('确定要删除这篇文章吗？')) return; try { const response = await fetch(`/api/study/article/${articleId}`, {method: 'DELETE'}); const result = await response.json(); if (result.success) { alert('删除成功'); loadArticles(); } else { alert(result.message); } } catch (error) { alert('删除失败'); } }
        function showUploadArticleModal() { document.getElementById('uploadArticleModal').style.display = 'flex'; }
        function closeUploadArticleModal() { document.getElementById('uploadArticleModal').style.display = 'none'; document.getElementById('uploadArticleForm').reset(); }
        function closeArticleDetailModal() { document.getElementById('articleDetailModal').style.display = 'none'; }
        document.getElementById('uploadArticleForm').addEventListener('submit', async (e) => { e.preventDefault(); const title = document.getElementById('articleTitle').value; const description = document.getElementById('articleDesc').value; const file = document.getElementById('articleFile').files[0]; if (!title || !file) { alert('请填写标题并选择文件'); return; } const formData = new FormData(); formData.append('title', title); formData.append('description', description); formData.append('file', file); const submitBtn = document.querySelector('#uploadArticleForm button'); const originalText = submitBtn.textContent; submitBtn.textContent = '上传中...'; submitBtn.disabled = true; try { const response = await fetch('/api/study/upload', {method: 'POST', body: formData}); const result = await response.json(); if (result.success) { alert('上传成功'); closeUploadArticleModal(); loadArticles(); } else { alert('上传失败：' + result.message); } } catch (error) { alert('上传失败'); } finally { submitBtn.textContent = originalText; submitBtn.disabled = false; } });
        async function loadDiscussions() { try { const response = await fetch('/api/study/discussions'); const data = await response.json(); if (data.success) displayDiscussions(data.discussions); else document.getElementById('discussion-list').innerHTML = '<div class="empty-state">加载失败</div>'; } catch (error) { document.getElementById('discussion-list').innerHTML = '<div class="empty-state">加载失败，请刷新</div>'; } }
        function displayDiscussions(discussions) { const container = document.getElementById('discussion-list'); if (!discussions || discussions.length === 0) { container.innerHTML = '<div class="empty-state">💬 暂无讨论，快来发表第一个话题吧！</div>'; return; } let html = ''; discussions.forEach(discussion => { html += `<div class="discussion-item" id="discussion-${discussion.id}"><div class="discussion-header-info"><div><span class="discussion-user">${escapeHtml(discussion.user_name)}</span></div><div><span class="discussion-time">${discussion.time}</span></div></div><div class="discussion-content">${escapeHtml(discussion.content)}</div><div class="discussion-actions"><button class="reply-btn" onclick="toggleReply(${discussion.id})">💬 回复</button><button class="delete-discussion-btn" onclick="deleteDiscussion(${discussion.id})">🗑️ 删除</button></div><div id="reply-input-${discussion.id}" style="display:none;" class="reply-input-area"><textarea id="reply-content-${discussion.id}" class="reply-input" rows="2" placeholder="写下你的回复..."></textarea><button class="submit-reply-btn" onclick="submitReply(${discussion.id})">回复</button></div><div id="replies-${discussion.id}" class="replies-area">${displayReplies(discussion.replies)}</div></div>`; }); container.innerHTML = html; }
        function displayReplies(replies) { if (!replies || replies.length === 0) return ''; let html = ''; replies.forEach(reply => { html += `<div class="reply-item"><div><span class="reply-user">${escapeHtml(reply.user_name)}</span><span class="reply-time">${reply.time}</span></div><div class="reply-content">${escapeHtml(reply.content)}</div></div>`; }); return html; }
        function toggleReply(discussionId) { const inputDiv = document.getElementById(`reply-input-${discussionId}`); inputDiv.style.display = inputDiv.style.display === 'none' ? 'flex' : 'none'; }
        async function submitReply(discussionId) { const content = document.getElementById(`reply-content-${discussionId}`).value; if (!content.trim()) { alert('请输入回复内容'); return; } try { const response = await fetch(`/api/study/discussion/${discussionId}/reply`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: content}) }); const result = await response.json(); if (result.success) { document.getElementById(`reply-content-${discussionId}`).value = ''; document.getElementById(`reply-input-${discussionId}`).style.display = 'none'; loadDiscussions(); } else { alert(result.message); } } catch (error) { alert('回复失败'); } }
        async function publishDiscussion() { const content = document.getElementById('discussionContent').value; if (!content.trim()) { alert('请输入讨论内容'); return; } try { const response = await fetch('/api/study/discussion', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: content}) }); const result = await response.json(); if (result.success) { document.getElementById('discussionContent').value = ''; loadDiscussions(); } else { alert(result.message); } } catch (error) { alert('发布失败'); } }
        async function deleteDiscussion(discussionId) { if (!confirm('确定要删除这条讨论吗？')) return; try { const response = await fetch(`/api/study/discussion/${discussionId}`, {method: 'DELETE'}); const result = await response.json(); if (result.success) { alert('删除成功'); loadDiscussions(); } else { alert(result.message); } } catch (error) { alert('删除失败'); } }
        function escapeHtml(text) { if (!text) return ''; const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
        window.onclick = function(event) { const modal1 = document.getElementById('uploadArticleModal'); const modal2 = document.getElementById('articleDetailModal'); if (event.target === modal1) closeUploadArticleModal(); if (event.target === modal2) closeArticleDetailModal(); }
        loadArticles();
    </script>
</body>
</html>
'''

# 监控拍照模块HTML
CAMERA_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        .camera-container { padding: 20px; }
        .video-wrapper { background: #000; border-radius: 10px; overflow: hidden; margin-bottom: 20px; text-align: center; }
        video { width: 100%; max-width: 640px; height: auto; margin: 0 auto; display: block; }
        .controls { text-align: center; margin-top: 20px; }
        button { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 0 10px; }
        .photo-list { margin-top: 30px; display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
        .photo-item { background: #f8f9fa; border-radius: 10px; padding: 10px; text-align: center; }
        .photo-item img { width: 100%; height: 150px; object-fit: cover; border-radius: 5px; }
        .back-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
    </style>
</head>
<body>
    <button class="back-btn" onclick="parent.hideModule()">← 返回主界面</button>
    <div class="camera-container">
        <div class="video-wrapper"><video id="video" autoplay playsinline></video><canvas id="canvas" style="display:none;"></canvas></div>
        <div class="controls"><button onclick="takePhoto()">📸 拍照</button><button onclick="startCamera()">🎥 开启摄像头</button></div>
        <div id="photos" class="photo-list"></div>
    </div>
    <script>
        let video = document.getElementById('video'), canvas = document.getElementById('canvas'), photos = [];
        function startCamera() { navigator.mediaDevices.getUserMedia({ video: true }).then(stream => { video.srcObject = stream; }).catch(err => { alert('无法开启摄像头'); }); }
        function takePhoto() { if(!video.videoWidth) { alert('请先开启摄像头'); return; } canvas.width = video.videoWidth; canvas.height = video.videoHeight; canvas.getContext('2d').drawImage(video, 0, 0); let photoUrl = canvas.toDataURL('image/png'); photos.unshift(photoUrl); displayPhotos(); }
        function displayPhotos() { let photoDiv = document.getElementById('photos'); photoDiv.innerHTML = '<h3>📸 拍照记录</h3>'; if(photos.length === 0) { photoDiv.innerHTML += '<p style="text-align:center; color:#999;">暂无照片</p>'; } photos.forEach((photo, index) => { let div = document.createElement('div'); div.className = 'photo-item'; div.innerHTML = '<img src="' + photo + '" alt="照片' + (index+1) + '"><br><small>' + new Date().toLocaleString() + '</small>'; photoDiv.appendChild(div); }); }
        startCamera();
    </script>
</body>
</html>
'''


# ========== Flask 路由 ==========
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = system.login(username, password)
        if user:
            session['username'] = user.username
            session['role'] = user.role
            session['permissions'] = user.permissions
            session['user_data'] = {
                'name': user.name or user.username,
                'phone': user.phone,
                'age': user.age,
                'department': user.department,
                'position': user.position,
                'rank': user.rank,
                'join_date': user.join_date,
                'avatar': user.avatar or ('👤' if user.role == 'employee' else '👨‍💼')
            }
            if user.role == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('main'))
        return render_template_string(LOGIN_HTML, error='账号或密码错误')
    return render_template_string(LOGIN_HTML)


@app.route('/main')
@login_required
def main():
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))
    user_data = session.get('user_data', {})
    permissions = session.get('permissions', ['study', 'upload', 'structure'])
    from datetime import datetime
    return render_template_string(MAIN_HTML,
                                  name=user_data.get('name', session['username']),
                                  avatar=user_data.get('avatar', '👤'),
                                  date=datetime.now().strftime("%Y年%m月%d日"),
                                  permissions=permissions,
                                  is_admin=False)


@app.route('/admin')
@login_required
@admin_required
def admin():
    employees = system.get_all_employees()
    departments = set(emp.department for emp in employees if emp.department)
    return render_template_string(ADMIN_HTML,
                                  admin_name=session.get('user_data', {}).get('name', '管理员'),
                                  employee_count=len(employees),
                                  department_count=len(departments),
                                  employees=employees,
                                  departments=config_mgr.departments,
                                  positions=config_mgr.positions,
                                  ranks=config_mgr.ranks)


# 配置管理API
@app.route('/api/admin/add_config', methods=['POST'])
@login_required
@admin_required
def api_add_config():
    try:
        data = request.json
        config_type = data.get('type')
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': '名称不能为空'})
        if config_type == 'department':
            success = config_mgr.add_department(name)
            if success:
                dept_path = os.path.join(file_manager.files_dir, name)
                if not os.path.exists(dept_path):
                    os.makedirs(dept_path)
        elif config_type == 'position':
            success = config_mgr.add_position(name)
        elif config_type == 'rank':
            success = config_mgr.add_rank(name)
        else:
            return jsonify({'success': False, 'message': '无效的配置类型'})
        if success:
            return jsonify({'success': True, 'message': f'添加成功'})
        else:
            return jsonify({'success': False, 'message': '名称已存在'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


@app.route('/api/admin/delete_config', methods=['POST'])
@login_required
@admin_required
def api_delete_config():
    try:
        data = request.json
        config_type = data.get('type')
        name = data.get('name', '').strip()
        if config_type == 'department':
            success = config_mgr.delete_department(name)
        elif config_type == 'position':
            success = config_mgr.delete_position(name)
        elif config_type == 'rank':
            success = config_mgr.delete_rank(name)
        else:
            return jsonify({'success': False, 'message': '无效的配置类型'})
        if success:
            return jsonify({'success': True, 'message': f'删除成功'})
        else:
            return jsonify({'success': False, 'message': '删除失败，名称不存在'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


# 管理员API
@app.route('/api/admin/add_employee', methods=['POST'])
@login_required
@admin_required
def api_add_employee():
    try:
        data = request.json
        if not data.get('phone'):
            return jsonify({'success': False, 'message': '手机号不能为空'})
        if not data.get('name'):
            return jsonify({'success': False, 'message': '姓名不能为空'})
        if not data.get('department'):
            return jsonify({'success': False, 'message': '部门不能为空'})
        if not data.get('position'):
            return jsonify({'success': False, 'message': '职位不能为空'})
        success, message = system.add_employee(data)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


@app.route('/api/admin/update_employee', methods=['POST'])
@login_required
@admin_required
def api_update_employee():
    try:
        data = request.json
        username = data.get('username')
        if not username:
            return jsonify({'success': False, 'message': '用户名不能为空'})
        success, message = system.update_employee(username, data)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


@app.route('/api/admin/delete_employee/<username>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_employee(username):
    try:
        success, message = system.delete_employee(username)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


@app.route('/api/admin/get_employee/<username>')
@login_required
@admin_required
def api_get_employee(username):
    employee = system.get_employee_by_username(username)
    if employee:
        return jsonify({
            'username': employee.username,
            'name': employee.name,
            'phone': employee.phone,
            'department': employee.department,
            'position': employee.position,
            'rank': employee.rank,
            'avatar': employee.avatar,
            'permissions': employee.permissions
        })
    return jsonify({'error': '员工不存在'}), 404


@app.route('/api/change_password', methods=['POST'])
@login_required
def api_change_password():
    try:
        data = request.json
        username = session.get('username')
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        success, message = system.change_password(username, old_password, new_password)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


# 文件管理API
@app.route('/api/files/all_departments')
@login_required
def api_files_all_departments():
    try:
        return jsonify({'success': True, 'departments': config_mgr.departments})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'departments': []})


@app.route('/api/files/list')
@login_required
def api_files_list():
    try:
        department = request.args.get('department', 'all')
        username = session.get('username')
        if department != 'all':
            user_departments = file_manager.get_user_departments(username)
            if department not in user_departments and session.get('role') != 'admin':
                return jsonify({'success': False, 'message': 'no_permission', 'files': [], 'departments': []})
        files = file_manager.get_department_files(department, username)
        departments = file_manager.get_user_departments(username)
        return jsonify({'success': True, 'files': files, 'departments': departments})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'files': [], 'departments': []})


@app.route('/api/files/upload_departments')
@login_required
def api_files_upload_departments():
    try:
        username = session.get('username')
        departments = file_manager.get_upload_departments(username)
        return jsonify({'success': True, 'departments': departments})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'departments': []})


@app.route('/api/files/upload', methods=['POST'])
@login_required
def api_files_upload():
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': '没有文件'})
        file = request.files['files']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'})
        department = request.form.get('department')
        if not department:
            return jsonify({'success': False, 'message': '请选择部门'})
        permissions = session.get('permissions', [])
        if 'files' not in permissions and session.get('role') != 'admin':
            return jsonify({'success': False, 'message': '没有文件访问权限'})
        if session.get('role') != 'admin':
            upload_depts = file_manager.get_upload_departments(session['username'])
            if department not in upload_depts:
                return jsonify({'success': False, 'message': '没有权限上传到该部门'})
        user_data = session.get('user_data', {})
        success, message = file_manager.upload_file(file, department, file.filename, session['username'],
                                                    user_data.get('name', session['username']))
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


@app.route('/api/files/download/<file_id>')
@login_required
def api_files_download(file_id):
    try:
        filepath, filename = file_manager.download_file(file_id, session['username'])
        if not filepath:
            return jsonify({'success': False, 'message': filename}), 404
        return send_file(filepath, as_attachment=True, download_name=filename, mimetype='application/octet-stream')
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/files/delete/<file_id>', methods=['DELETE'])
@login_required
def api_files_delete(file_id):
    try:
        success, message = file_manager.delete_file(file_id, session['username'])
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


# 台账管理API
@app.route('/api/ledger/departments')
@login_required
def api_ledger_departments():
    try:
        return jsonify({'success': True, 'departments': config_mgr.departments})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'departments': []})


@app.route('/api/ledger/upload_departments')
@login_required
def api_ledger_upload_departments():
    try:
        username = session.get('username')
        user = system.get_employee_by_username(username)
        departments = []

        # 检查是否有上传权限
        if 'upload' not in session.get('permissions', []) and session.get('role') != 'admin':
            return jsonify({'success': True, 'departments': []})

        if session.get('role') == 'admin':
            departments = config_mgr.departments
        else:
            # 普通用户只能上传到自己的部门
            if user and user.department:
                departments = [user.department]

        return jsonify({'success': True, 'departments': departments})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'departments': []})


@app.route('/api/ledger/records')
@login_required
def api_ledger_records():
    try:
        department = request.args.get('department', 'all')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        keyword = request.args.get('keyword', '')
        username = session.get('username')

        # 检查查看权限
        if 'upload' not in session.get('permissions', []) and session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'no_permission', 'records': []})

        # 获取记录
        records = ledger_manager.get_records(
            department=department if department != 'all' else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            keyword=keyword if keyword else None
        )

        # 非管理员只能看到自己部门的记录
        if session.get('role') != 'admin':
            user = system.get_employee_by_username(username)
            if user and user.department:
                records = [r for r in records if r['department'] == user.department]

        return jsonify({'success': True, 'records': records})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'records': []})


@app.route('/api/ledger/upload', methods=['POST'])
@login_required
def api_ledger_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有文件'})
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'})

        department = request.form.get('department')
        if not department:
            return jsonify({'success': False, 'message': '请选择部门'})

        # 检查上传权限
        if 'upload' not in session.get('permissions', []) and session.get('role') != 'admin':
            return jsonify({'success': False, 'message': '没有上传权限'})

        # 非管理员只能上传到自己的部门
        if session.get('role') != 'admin':
            user = system.get_employee_by_username(session['username'])
            if not user or user.department != department:
                return jsonify({'success': False, 'message': '没有权限上传到该部门'})

        # 创建台账目录
        ledger_dir = os.path.join('company_files', 'ledger')
        if not os.path.exists(ledger_dir):
            os.makedirs(ledger_dir)

        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{original_filename}"
        filepath = os.path.join(ledger_dir, unique_filename)
        file.save(filepath)

        file_size = os.path.getsize(filepath)
        user_data = session.get('user_data', {})

        success, message = ledger_manager.add_record(
            original_filename, filepath, department,
            session['username'], user_data.get('name', session['username']),
            file_size
        )

        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


@app.route('/api/ledger/download/<int:record_id>')
@login_required
def api_ledger_download(record_id):
    try:
        record = ledger_manager.get_record(record_id)
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404

        # 检查查看权限
        if 'upload' not in session.get('permissions', []) and session.get('role') != 'admin':
            return jsonify({'success': False, 'message': '没有权限'}), 403

        # 非管理员只能下载自己部门的记录
        if session.get('role') != 'admin':
            user = system.get_employee_by_username(session['username'])
            if user and user.department != record['department']:
                return jsonify({'success': False, 'message': '没有权限'}), 403

        ledger_manager.update_download_count(record_id)
        return send_file(record['filepath'], as_attachment=True, download_name=record['filename'])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/ledger/record/<int:record_id>', methods=['DELETE'])
@login_required
def api_ledger_delete(record_id):
    try:
        success, message = ledger_manager.delete_record(record_id, session['username'])
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


# 学习交流API
@app.route('/api/study/articles')
@login_required
def api_study_articles():
    try:
        articles = study_manager.get_articles()
        return jsonify({'success': True, 'articles': articles})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/study/article/<int:article_id>')
@login_required
def api_study_article(article_id):
    try:
        article = study_manager.get_article(article_id)
        if article:
            article['views'] = article.get('views', 0) + 1
            study_manager.save_data()
            return jsonify({'success': True, 'article': article})
        return jsonify({'success': False, 'message': '文章不存在'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/study/article/<int:article_id>/comment', methods=['POST'])
@login_required
def api_study_comment(article_id):
    try:
        data = request.json
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'success': False, 'message': '评论内容不能为空'})
        user_data = session.get('user_data', {})
        success, message = study_manager.add_comment(article_id, session['username'],
                                                     user_data.get('name', session['username']), content)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/study/article/<int:article_id>', methods=['DELETE'])
@login_required
def api_study_delete_article(article_id):
    try:
        success, message = study_manager.delete_article(article_id, session['username'])
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/study/upload', methods=['POST'])
@login_required
def api_study_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有文件'})
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'})
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            return jsonify({'success': False, 'message': '标题不能为空'})

        articles_dir = os.path.join('company_files', 'study_articles')
        if not os.path.exists(articles_dir):
            os.makedirs(articles_dir)

        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{original_filename}"
        filepath = os.path.join(articles_dir, unique_filename)
        file.save(filepath)

        user_data = session.get('user_data', {})
        success, message = study_manager.add_article(title, description, original_filename, filepath, file.content_type,
                                                     session['username'], user_data.get('name', session['username']))
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})


@app.route('/api/study/download/<int:article_id>')
@login_required
def api_study_download(article_id):
    try:
        article = study_manager.get_article(article_id)
        if not article:
            return jsonify({'success': False, 'message': '文件不存在'}), 404
        return send_file(article['filepath'], as_attachment=True, download_name=article['filename'])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/study/discussions')
@login_required
def api_study_discussions():
    try:
        discussions = study_manager.get_discussions()
        return jsonify({'success': True, 'discussions': discussions})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/study/discussion', methods=['POST'])
@login_required
def api_study_add_discussion():
    try:
        data = request.json
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'success': False, 'message': '内容不能为空'})
        user_data = session.get('user_data', {})
        success, message = study_manager.add_discussion(session['username'], user_data.get('name', session['username']),
                                                        content)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/study/discussion/<int:discussion_id>/reply', methods=['POST'])
@login_required
def api_study_add_reply(discussion_id):
    try:
        data = request.json
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'success': False, 'message': '回复内容不能为空'})
        user_data = session.get('user_data', {})
        success, message = study_manager.add_reply(discussion_id, session['username'],
                                                   user_data.get('name', session['username']), content)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/study/discussion/<int:discussion_id>', methods=['DELETE'])
@login_required
def api_study_delete_discussion(discussion_id):
    try:
        success, message = study_manager.delete_discussion(discussion_id, session['username'])
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/module/<module_name>')
@login_required
def get_module(module_name):
    if 'username' not in session:
        return '<script>window.parent.location.href="/"</script>'
    permissions = session.get('permissions', [])
    if module_name in ['camera', 'files', 'study', 'upload', 'structure']:
        if module_name not in permissions and session.get('role') != 'admin':
            return f'<div style="padding:20px;"><button onclick="parent.hideModule()" style="background:#667eea;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;margin-bottom:20px;">← 返回主界面</button><div style="text-align:center;padding:50px;"><p style="color:red;font-size:18px;">⚠️ 您没有权限访问此模块！</p><p style="color:#999;margin-top:20px;">请联系管理员开通权限。</p></div></div>'

    if module_name == 'structure':
        structure = system.get_company_structure()
        return render_template_string(STRUCTURE_HTML, structure=structure)
    elif module_name == 'camera':
        return render_template_string(CAMERA_HTML)
    elif module_name == 'files':
        return render_template_string(FILES_HTML)
    elif module_name == 'study':
        return render_template_string(STUDY_HTML)
    elif module_name == 'upload':
        # 检查上传权限，决定是否显示上传区域
        can_upload = 'upload' in permissions or session.get('role') == 'admin'
        return render_template_string(UPLOAD_HTML, can_upload=can_upload)
    else:
        return '<div style="padding:20px;"><button onclick="parent.hideModule()">← 返回</button><p>功能开发中...</p></div>'


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    if not os.path.exists('company_files'):
        os.makedirs('company_files')
    if not os.path.exists(os.path.join('company_files', 'study_articles')):
        os.makedirs(os.path.join('company_files', 'study_articles'))
    if not os.path.exists(os.path.join('company_files', 'ledger')):
        os.makedirs(os.path.join('company_files', 'ledger'))

    print("=" * 50)
    print("员工管理系统启动成功！")
    print("访问地址: http://127.0.0.1:8080")
    print("管理员账号: admin / admin")
    print("=" * 50)
    print("台账上传模块功能：")
    print("1. 有upload权限的人员可以查看所有台账记录")
    print("2. 只有管理员和有upload权限的人员可以上传文件")
    print("3. 支持按部门筛选、按时间范围筛选、按关键词搜索")
    print("4. 普通用户只能看到自己部门的台账记录")
    print("=" * 50)

    app.run(debug=True, host='127.0.0.1', port=8080)