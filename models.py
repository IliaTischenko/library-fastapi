from sqlalchemy import Column, Integer, String, Table, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from database import Base


book_reader_association = Table(
    "book_reader",
    Base.metadata,
    Column("book_id", Integer, ForeignKey("book.id", ondelete="CASCADE")),
    Column("reader_id", Integer, ForeignKey("reader.id", ondelete="CASCADE"))
)

class Author(Base):
    __tablename__ = "author"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    books = relationship(
        "Book",
        back_populates='author',
        cascade="all, delete-orphan"
    )


class Book(Base):
    __tablename__ = "book"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    page = Column(Integer, nullable=False)
    author_id = Column(Integer, ForeignKey("author.id"), nullable=False, ondelete="CASCADE")
    author = relationship(
        "Author",
        back_populates='books'
    )
    readers = relationship(
        "Reader",
        secondary=book_reader_association,
        back_populates='books'
    )


class Reader(Base):
    __tablename__ = 'reader'
    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    books = relationship(
        "Book",
        secondary=book_reader_association,
        back_populates="readers")
    issue_date = Column(DateTime, nullable=False)