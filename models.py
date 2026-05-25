from datetime import date

from sqlalchemy import Column, Integer, Table, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database import Base


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
    issue_date:Mapped[date] = mapped_column(nullable=False)


class Admin(Base):
    __tablename__ = 'admin'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    hashed_pass: Mapped[str] = mapped_column(nullable=False)