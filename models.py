from datetime import date
import enum
from typing import Optional

from sqlalchemy import Column, Integer, Table, ForeignKey, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database import Base


class UserRole(str, enum.Enum):
    READER = "reader"
    ADMIN = "admin"


book_reader_association = Table(
    "book_reader",
    Base.metadata,
    Column("book_id", Integer, ForeignKey("book.id", ondelete="CASCADE")),
    Column("reader_id", Integer, ForeignKey("reader.id", ondelete="CASCADE"))
)

class Author(Base):
    __tablename__ = "author"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str] = mapped_column(nullable=False)
    birth_date: Mapped[date] = mapped_column(nullable=False)
    books: Mapped[list["Book"]] = relationship(
        "Book",
        back_populates='author',
        cascade="all, delete-orphan"
    )


class Book(Base):
    __tablename__ = "book"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    pages: Mapped[int] = mapped_column(nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id", ondelete="CASCADE"), nullable=False)
    author: Mapped["Author"] = relationship(
        "Author",
        back_populates='books'
    )
    readers: Mapped[list["Reader"]] = relationship(
        "Reader",
        secondary=book_reader_association,
        back_populates='books'
    )


class Reader(Base):
    __tablename__ = 'reader'
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(nullable=False)
    books: Mapped[list["Book"]] = relationship(
        "Book",
        secondary=book_reader_association,
        back_populates="readers")
    register_date: Mapped[date] = mapped_column(nullable=False)

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=False, unique=True)
    user: Mapped[Optional["User"]] = relationship("User", back_populates="reader")


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    hashed_pass: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False),
        default=UserRole.READER,
        nullable=False
    )