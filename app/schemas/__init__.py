from app.schemas.user import UserResponse, UserChangePassword, UserAuthSchema
from app.schemas.author import AuthorResponse, AuthorUpdate, AuthorInput
from app.schemas.book import BookResponse, BookUpdate, BookInput
from app.schemas.reader import ReaderResponse, ReaderUpdate, ReaderInput
from app.schemas.auth import  UserReaderInput


BookResponse.model_rebuild()
ReaderResponse.model_rebuild()