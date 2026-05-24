from schemas.author import AuthorResponse, AuthorUpdate, AuthorInput
from schemas.book import BookResponse, BookResponseShort, BookUpdate, BookInput
from schemas.reader import ReaderResponse, ReaderResponseShort, ReaderUpdate, ReaderInput
from schemas.admin import AdminResponse, AdminChangePassword, AdminAuthSchema

BookResponse.model_rebuild()
ReaderResponse.model_rebuild()