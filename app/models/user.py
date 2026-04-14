from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """
    User model for authentication.

    This model does NOT come from the F1 dataset — it exists purely to
    demonstrate JWT-based authentication. Users register, log in, and
    receive tokens that gate write operations (POST/PUT/DELETE).

    Design notes:
    - `hashed_password` stores a bcrypt hash, NEVER the plain password
    - `is_active` allows soft-disabling accounts without deleting them
    - `created_at` uses server_default so the DB fills it automatically
      on INSERT, even if the application forgets to set it
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
