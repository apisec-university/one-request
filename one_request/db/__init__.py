from sqlalchemy.orm import Session as SessionT
from sqlalchemy.orm import scoped_session, sessionmaker

GlobalSession = scoped_session(sessionmaker())


# # pylint: disable=invalid-name # this acts like a class
def Session(**kwargs) -> SessionT:
    return GlobalSession(**kwargs)
