from schemas.user import UserResponse, UserChangePassword, UserAuthSchema
from schemas.author import AuthorResponse, AuthorUpdate, AuthorInput
from schemas.book import BookResponse, BookResponseShort, BookUpdate, BookInput
from schemas.reader import ReaderResponse, ReaderResponseShort, ReaderUpdate, ReaderInput
from schemas.auth import  UserReaderInput


BookResponse.model_rebuild()
ReaderResponse.model_rebuild()