
class DomainError(Exception):
    pass

class CollageNotFoundError(DomainError):
    pass

class CollageCreationError(DomainError):
    pass

class InvalidCollageNameError(DomainError):
    pass