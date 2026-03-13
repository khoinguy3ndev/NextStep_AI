from typing import Any
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    # Không cần khai báo id: Any hay __name__ nữa

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        # Tự động tạo tên bảng = tên class viết thường
        return cls.__name__.lower()