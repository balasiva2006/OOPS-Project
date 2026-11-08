"""User account model with hashed-password verification."""
from dataclasses import dataclass
from werkzeug.security import check_password_hash

@dataclass
class User:
    id: int
    username: str
    password_hash: str
    role: str
    hall_id: int | None = None
    student_id: int | None = None

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
