from schemas import UserAuthSchema, ReaderInput


class UserReaderInput(UserAuthSchema, ReaderInput):
    pass