from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from jwt import InvalidTokenError


DEFAULT_PERMISSIONS = ["study", "upload", "structure"]
ADMIN_PERMISSIONS = ["camera", "files", "study", "upload", "structure", "cross_dept_files"]
DEPARTMENT_PERMISSION_PREFIX = "dept_"
JWT_SECRET = "photo-monitor-jwt-secret"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "photo-monitor"
JWT_AUDIENCE = "photo-monitor-web"
JWT_EXPIRE_DAYS = 7


def _normalize_department_name(value: str | None) -> str:
    return (value or "").strip()


def build_department_permission(department: str) -> str:
    normalized = _normalize_department_name(department)
    return f"{DEPARTMENT_PERMISSION_PREFIX}{normalized}" if normalized else ""


def extract_department_permissions(permissions: list[str] | None) -> list[str]:
    if not permissions:
        return []

    departments = []
    for permission in permissions:
        if not isinstance(permission, str) or not permission.startswith(DEPARTMENT_PERMISSION_PREFIX):
            continue
        department = _normalize_department_name(permission[len(DEPARTMENT_PERMISSION_PREFIX) :])
        if department:
            departments.append(department)

    return list(dict.fromkeys(departments))


@dataclass
class User:
    username: str
    password: str
    role: str
    phone: str = ""
    name: str = ""
    age: int = 0
    department: str = ""
    position: str = ""
    rank: str = ""
    avatar: str = ""
    join_date: str = ""
    permissions: list[str] = field(default_factory=lambda: DEFAULT_PERMISSIONS.copy())

    def __post_init__(self) -> None:
        if not self.avatar:
            self.avatar = "👤" if self.role == "employee" else "👨‍💼"
        if not self.join_date:
            self.join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def check_password(self, password: str) -> bool:
        return self.password == password

    def to_dict(self) -> dict:
        return asdict(self)

    def to_public_dict(self) -> dict:
        return {
            "username": self.username,
            "role": self.role,
            "phone": self.phone,
            "name": self.name or self.username,
            "age": self.age,
            "department": self.department,
            "position": self.position,
            "rank": self.rank,
            "avatar": self.avatar,
            "join_date": self.join_date,
            "permissions": self.permissions,
            "department_permissions": extract_department_permissions(self.permissions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            username=data["username"],
            password=data["password"],
            role=data["role"],
            phone=data.get("phone", ""),
            name=data.get("name", ""),
            age=data.get("age", 0),
            department=data.get("department", ""),
            position=data.get("position", ""),
            rank=data.get("rank", ""),
            avatar=data.get("avatar", ""),
            join_date=data.get("join_date", ""),
            permissions=list(data.get("permissions", DEFAULT_PERMISSIONS.copy())),
        )


class EmployeeSystem:
    def __init__(self, data_file: Path | None = None):
        backend_root = Path(__file__).resolve().parents[1]
        self.data_file = data_file or backend_root / "users.json"
        self.users: list[User] = []
        self.load_data()

    def load_data(self) -> None:
        if self.data_file.exists():
            with self.data_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
            self.users = [User.from_dict(user) for user in data]
            return

        admin = User(
            username="admin",
            password="admin",
            role="admin",
            name="系统管理员",
            avatar="👨‍💼",
            permissions=ADMIN_PERMISSIONS.copy(),
        )
        self.users = [admin]
        self.save_data()

    def save_data(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as file:
            json.dump([user.to_dict() for user in self.users], file, ensure_ascii=False, indent=2)

    def authenticate(self, username: str, password: str) -> User | None:
        for user in self.users:
            if user.username == username and user.check_password(password):
                return user
        return None

    def get_user(self, username: str) -> User | None:
        for user in self.users:
            if user.username == username:
                return user
        return None

    def get_all_employees(self) -> list[User]:
        return [user for user in self.users if user.role == "employee"]

    def list_departments(self) -> list[str]:
        departments = set()
        for user in self.get_all_employees():
            if user.department:
                departments.add(user.department)
            departments.update(extract_department_permissions(user.permissions))
        return sorted(departments)

    def create_employee(self, payload: dict) -> User:
        phone = (payload.get("phone") or "").strip()
        username = (payload.get("username") or phone).strip()
        password = payload.get("password") or phone

        if not username:
            raise ValueError("用户名不能为空")
        if not password:
            raise ValueError("密码不能为空")
        if self.get_user(username):
            raise ValueError("该用户名已存在")

        user = User(
            username=username,
            password=password,
            role="employee",
            phone=phone,
            name=(payload.get("name") or "").strip(),
            department=(payload.get("department") or "").strip(),
            position=(payload.get("position") or "").strip(),
            rank=(payload.get("rank") or "").strip(),
            avatar="👤",
            permissions=self._normalize_permissions(payload.get("permissions")),
        )
        self.users.append(user)
        self.save_data()
        return user

    def update_employee(self, username: str, payload: dict) -> User:
        user = self.get_user(username)
        if not user or user.role != "employee":
            raise ValueError("员工不存在")

        new_username = (payload.get("username") or user.username).strip()
        if new_username != user.username and self.get_user(new_username):
            raise ValueError("该用户名已存在")

        user.username = new_username
        user.phone = (payload.get("phone", user.phone) or "").strip()
        user.name = (payload.get("name", user.name) or "").strip()
        user.department = (payload.get("department", user.department) or "").strip()
        user.position = (payload.get("position", user.position) or "").strip()
        user.rank = (payload.get("rank", user.rank) or "").strip()
        user.permissions = self._normalize_permissions(payload.get("permissions", user.permissions))

        password = (payload.get("password") or "").strip()
        if password:
            self._validate_password(password)
            user.password = password

        self.save_data()
        return user

    def delete_employee(self, username: str) -> None:
        for index, user in enumerate(self.users):
            if user.username == username and user.role == "employee":
                self.users.pop(index)
                self.save_data()
                return
        raise ValueError("员工不存在")

    def change_password(self, username: str, old_password: str, new_password: str) -> None:
        user = self.get_user(username)
        if not user:
            raise ValueError("用户不存在")
        if not user.check_password(old_password):
            raise ValueError("原密码错误")
        self._validate_password(new_password)
        user.password = new_password
        self.save_data()

    def admin_reset_password(self, username: str, new_password: str) -> None:
        user = self.get_user(username)
        if not user:
            raise ValueError("用户不存在")
        self._validate_password(new_password)
        user.password = new_password
        self.save_data()

    def _validate_password(self, password: str) -> None:
        if len(password.strip()) < 3:
            raise ValueError("密码长度至少 3 位")

    def _normalize_permissions(self, permissions: list[str] | None) -> list[str]:
        if permissions is None:
            return DEFAULT_PERMISSIONS.copy()
        if isinstance(permissions, str):
            permissions = [item.strip() for item in permissions.split(",") if item.strip()]

        normalized_permissions = []
        for permission in permissions:
            if not isinstance(permission, str):
                continue

            cleaned = permission.strip()
            if cleaned.startswith(DEPARTMENT_PERMISSION_PREFIX):
                cleaned = build_department_permission(cleaned[len(DEPARTMENT_PERMISSION_PREFIX) :])

            if cleaned:
                normalized_permissions.append(cleaned)

        return list(dict.fromkeys(normalized_permissions))

    def create_access_token(self, username: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "iat": now,
            "exp": now + timedelta(days=JWT_EXPIRE_DAYS),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def get_user_by_token(self, token: str | None) -> User | None:
        if not token:
            return None

        try:
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
            )
        except InvalidTokenError:
            return None

        username = payload.get("sub")
        if not username:
            return None
        return self.get_user(username)


employee_system = EmployeeSystem()
