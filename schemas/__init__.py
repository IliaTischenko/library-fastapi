from schemas.user import UserResponse, UserChangePassword, UserAuthSchema, UserReaderInput
from schemas.author import AuthorResponse, AuthorUpdate, AuthorInput
from schemas.book import BookResponse, BookResponseShort, BookUpdate, BookInput
from schemas.reader import ReaderResponse, ReaderResponseShort, ReaderUpdate, ReaderInput


BookResponse.model_rebuild()
ReaderResponse.model_rebuild()