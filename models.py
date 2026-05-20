from datetime import datetime
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
    books: Mapped[list["Book"]] = relationship(
        "Book",
        back_populates='author',
        cascade="all, delete-orphan"
    )


class Book(Base):
    __tablename__ = "book"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    page: Mapped[int] = mapped_column(nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"), nullable=False, ondelete="CASCADE")
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
    issue_date:Mapped[datetime] = mapped_column(nullable=False)