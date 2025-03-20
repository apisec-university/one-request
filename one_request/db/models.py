import logging
import time
from datetime import datetime, date
from operator import and_
from typing import Any, Dict, List, Literal, Optional, Sequence, Union, Type, re
from uuid import UUID, uuid4

from fastapi_pagination import Page
from pydantic import model_serializer, BaseModel, field_validator, computed_field
from pydantic_core.core_schema import SerializationInfo, SerializerFunctionWrapHandler
from sqlalchemy import ColumnExpressionArgument, Executable, or_, ColumnElement
from sqlalchemy.exc import (
    InvalidRequestError,
    NoResultFound,
    DBAPIError,
)
from sqlalchemy.orm import RelationshipProperty, raiseload, selectinload, aliased
from sqlmodel import Field
from sqlmodel import SQLModel as BaseSQLModel
from sqlmodel import select
from sqlmodel.main import RelationshipInfo
from fastapi_pagination.ext.sqlalchemy import paginate
from starlette.authentication import BaseUser
from typing_extensions import Self

from one_request.auth.enums import UserRole, PALANTIR_ROLE, ApiVersion
from one_request.auth.hashers import BcryptPasswordHandler
from one_request.db import Session
from one_request.exceptions import ResourceNotFound


def is_bcrypt_hash(string):
    bcrypt_pattern = r"^\$2[aby]\$\d{1,2}\$[A-Za-z0-9./]{53}$"
    return bool(re.match(bcrypt_pattern, string))

logger = logging.getLogger(__name__)


class Empty(BaseModel):
    """Class to define an empty field, rather than a field being cleared"""


# pylint: disable=invalid-name
def Relationship(
    *,
    back_populates: Optional[str] = None,
    cascade_delete: Optional[bool] = False,
    passive_deletes: Optional[Union[bool, Literal["all"]]] = False,
    link_model: Optional[Any] = None,
    sa_relationship: Optional[RelationshipProperty[Any]] = None,
    sa_relationship_args: Optional[Sequence[Any]] = None,
    sa_relationship_kwargs: Optional[Dict[str, Any]] = None,
) -> Any:
    # default lazy loading to raise. This is needed for relationship serialization
    # to work correctly, and not recursively load all relationships forever
    sa_relationship_kwargs = sa_relationship_kwargs or {}
    sa_relationship_kwargs.setdefault("lazy", "raise")

    return RelationshipInfo(
        back_populates=back_populates,
        cascade_delete=cascade_delete,
        passive_deletes=passive_deletes,
        link_model=link_model,
        sa_relationship=sa_relationship,
        sa_relationship_args=sa_relationship_args,
        sa_relationship_kwargs=sa_relationship_kwargs,
    )


WhereClauseT = Union[ColumnExpressionArgument[bool], bool]  # pylint: disable=invalid-name
RelationsT = bool | List[Type[BaseSQLModel] | BaseSQLModel | str]  # pylint: disable=invalid-name


class SQLModel(BaseSQLModel):
    @classmethod
    def where(cls, *where: WhereClauseT, relations: RelationsT = False) -> Executable:
        return cls.include_relations(select(cls).where(*where), relations)

    @classmethod
    def first(cls, *where: WhereClauseT, relations: RelationsT = False, session: Session = None) -> Optional[Self]:
        statement = cls.where(*where, relations=relations)
        if session:
            return session.execute(statement).scalar_one_or_none()

        with Session() as session:
            return session.execute(statement).scalar_one_or_none()

    @classmethod
    def exists(cls, *where: WhereClauseT, **kwargs) -> bool:
        return cls.first(*where, **kwargs) is not None

    @classmethod
    def one(cls, *where: WhereClauseT, relations: RelationsT = False, session: Session = None) -> Self:
        """Find a single instance of the model, and throw an exception if 0 or more than 1 entry is found"""
        statement = cls.where(*where, relations=relations)
        try:
            if session:  # use provided session if available
                return session.execute(statement).scalar_one()

            with Session() as session:
                return session.execute(statement).scalar_one()
        except NoResultFound as e:
            logger.debug(f"No result found for {cls.__name__}")
            # catch exception to add friendly name to error message
            raise ResourceNotFound(f"{getattr(cls, '__friendly_name__', cls.__name__)} not found") from e

    @classmethod
    def paginate(cls, *where: WhereClauseT, relations: RelationsT = False, session: Session = None) -> Page[Self]:
        statement = cls.where(*where, relations=relations)

        if session:  # use provided session if available
            return paginate(session, statement)

        with Session() as session:
            return paginate(session, statement)

    @classmethod
    def all(cls, *where: WhereClauseT, relations: RelationsT = False, session: Session = None) -> Sequence[Self]:
        statement = cls.where(*where, relations=relations)

        if session:  # use provided session if available
            return session.execute(statement).scalars().all()

        with Session() as session:
            return session.execute(statement).scalars().all()

    def delete(self, session: Session = None):
        session = session or Session()
        session.delete(self)
        try:
            session.commit()
        except DBAPIError as e:
            session.rollback()
            raise e

    def save(self, merge: bool = False, session: Session = None) -> Self:
        session = session or Session()

        # sometimes we want to update an existing record. this is only required when
        # trying to update by a PK AND we didn't query the db, but made the object manually
        # merge can be unpredictable with relationships,
        # as it creates a new instance of the object
        if merge:
            obj = session.merge(self)
        else:
            session.add(self)
            obj = self

        try:
            session.commit()
        except DBAPIError as e:
            session.rollback()
            raise e
        session.refresh(obj)
        return obj

    def refresh(self, merge: bool = False, session: Session = None) -> Self:
        """Update self with the latest data from the database"""
        session = session or Session()
        # see save() for information on merge
        if merge:
            obj = session.merge(self)
        else:
            session.add(self)
            obj = self
        session.refresh(obj)
        return obj

    def upsert(self, *columns: ColumnElement, **kwargs) -> Self:
        """ensure a duplicate record doesn't already exist, based on a non-pk field"""
        where = [c == getattr(self, c.key) for c in columns]
        if existing := self.first(*where):
            # update PK and save
            # logger.debug(f"found existing {self.__class__.__name__} record")
            for pk in self.pk:
                setattr(self, pk, getattr(existing, pk))
        # else:
        #     logger.debug(f"Creating new {self.__class__.__name__} record")

        return self.save(merge=True, **kwargs)

    @property
    def pk(self) -> set[str]:
        """Get the name of the primary key field for a SQLModel model"""
        keys = set()
        for field_name, field in self.model_fields.items():
            # we need is True because we can also get PydanticUndefined
            if getattr(field, "primary_key", False) is True:
                keys.add(field_name)

        if not len(keys):
            raise ValueError("No primary key field found")

        return keys

    @classmethod
    def include_relations(cls, statement: Executable, relations: RelationsT) -> Executable:
        """Include model relationships in a query"""
        # all relations on model
        relationships = [getattr(cls, k) for k in cls.__sqlmodel_relationships__.keys()]
        # relationships to load - default is to include no relationships
        select_in_load = []
        select_in_load_keys: set[str] = set()

        if isinstance(relations, list):
            # include only requested relationships
            for r in relations:
                if isinstance(r, str):
                    select_in_load_keys.add(r)
                    continue
                for key in cls.__sqlmodel_relationships__.keys():
                    # if the reverse relation exists
                    if getattr(r, key, None):
                        select_in_load.append(getattr(r, key))
                        break

        select_in_load_keys.union(r.key for r in select_in_load)

        # this will include all requested relationships, and cause all non-requested relationships
        # to throw ERR on access, allowing us to ignore them in @model_serializer
        for attr in relationships:
            if relations is True or attr.key in select_in_load_keys:
                statement = statement.options(selectinload(attr))
            else:
                statement = statement.options(raiseload(attr))

        return statement

    @model_serializer(mode="wrap")
    # type: ignore[no-untyped-def] # we ignore return type so FastAPI will show the default return type
    def serialize(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo):
        """Serialized to include model relationships"""
        data = handler(self)

        for key in self.__sqlmodel_relationships__.keys():
            try:
                relation = getattr(self, key)
                if isinstance(relation, list):
                    data[key] = [r.model_dump(mode=info.mode) for r in relation]
                elif relation:
                    data[key] = relation.model_dump(mode=info.mode)

            except InvalidRequestError:
                # relationships not included will raise this error
                # due to `lazy = 'raise'` in the relationship definition
                pass
        return data

    def __hash__(self):
        attribute = getattr(self, "id", None)
        if not attribute:
            # this should throw TypeError: unhashable type if the model has no id
            return super().__hash__()
        return f"{self.__class__.__name__}:{attribute}".__hash__()


class UserGroupLink(SQLModel, table=True):
    user_id: UUID | None = Field(foreign_key="user.id", primary_key=True)
    group_id: UUID | None = Field(foreign_key="group.id", primary_key=True)


class ActivityUserLink(SQLModel, table=True):
    """Location Reservation for a group"""

    activity_id: UUID = Field(foreign_key="activity.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)

    activity: "Activity" = Relationship()
    user: "User" = Relationship()


class UserChatLink(SQLModel, table=True):
    user_id: UUID | None = Field(foreign_key="user.id", primary_key=True)
    chat_id: UUID | None = Field(foreign_key="chat.id", primary_key=True)


class GroupCreate(BaseModel):
    name: str
    description: str


class GroupEdit(BaseModel):
    name: str | None | Empty = Empty
    description: str | None | Empty = Empty


class Group(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True)
    description: str
    owner_id: UUID = Field(foreign_key="user.id")

    owner: "User" = Relationship()
    users: list["User"] = Relationship(back_populates="groups", link_model=UserGroupLink)
    chats: list["Chat"] = Relationship()
    support_requests: list["SupportRequest"] = Relationship()
    activities: list["Activity"] = Relationship(back_populates="group")


class UserBase(SQLModel):
    name: str = Field(unique=True)
    email: str = Field(unique=True)
    password: str = Field(exclude=True)
    role: UserRole
    primary_group_name: str = Field(default="default")


class User(UserBase, table=True, exclude={"is_authenticated", "display_name", "identity", "password"}):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    groups: list[Group] = Relationship(back_populates="users", link_model=UserGroupLink)
    chats: list["Chat"] = Relationship(back_populates="users", link_model=UserChatLink)
    support_requests: list["SupportRequest"] = Relationship(back_populates="user")
    reviews: list["Review"] = Relationship(back_populates="user")
    activities: list["Activity"] = Relationship(link_model=ActivityUserLink, back_populates="participants")

    def get_additional_user_groups(self, session: Session = None):
        group_ids = [g.id for g in self.groups]
        additional_groups = Group.all(
            and_(
                Group.name.ilike(self.primary_group_name),
                Group.id.not_in(group_ids)
            ),
            session=session
        )
        return additional_groups

    @classmethod
    def one(cls, *where: WhereClauseT, relations: RelationsT = False, session: Session = None) -> Self:
        ret = super().one(*where, relations=relations, session=session)
        # only include additional groups if group relation is request
        if not relations:
            return ret

        # only include additional groups if group relation is request
        if isinstance(relations, list):
            if Group not in relations and "group" not in relations:
                return ret

        ret.groups = [
            *ret.groups,
            *ret.get_additional_user_groups(session)
        ]
        return ret

    @classmethod
    def first(cls, *where: WhereClauseT, relations: RelationsT = False, session: Session = None) -> Self:
        ret = super().first(*where, relations=relations, session=session)
        # only include additional groups if group relation is request
        if not ret or not relations:
            return ret

        # only include additional groups if group relation is request
        if isinstance(relations, list):
            if Group not in relations and "group" not in relations:
                return ret

        ret.groups = [
            *ret.groups,
            *ret.get_additional_user_groups(session)
        ]

        return ret

class Calendar(SQLModel, table=True):
    day: date = Field(primary_key=True)

    weather: list["Weather"] = Relationship(back_populates="calendar")
    location_prices: list["LocationPrices"] = Relationship()
    # bookings: list["Booking"] = Relationship()
    activities: list["Activity"] = Relationship()


class Chat(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True)
    description: str
    group_id: UUID = Field(foreign_key="group.id")

    group: Group = Relationship(back_populates="chats")
    users: list["User"] = Relationship(back_populates="chats", link_model=UserChatLink)
    messages: list["ChatMessage"] = Relationship(back_populates="chat")


class ChatMessage(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chat_id: UUID = Field(foreign_key="chat.id")
    user_id: UUID = Field(foreign_key="user.id")
    message: str

    chat: Chat = Relationship(back_populates="messages")
    user: User = Relationship()


class Booking(SQLModel, table=True):
    """Book a location for a given Activity"""

    activity_id: UUID = Field(foreign_key="activity.id", primary_key=True)
    location_id: UUID = Field(foreign_key="location.id")
    # day: date = Field(foreign_key="calendar.day")

    # group: Group = Relationship(back_populates="bookings", link_model=Activity)
    activity: "Activity" = Relationship(back_populates="booking")
    location: "Location" = Relationship(back_populates="bookings")


class Location(SQLModel, table=True, exclude={"activities"}):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True)
    description: str
    lat: str
    long: str

    prices: list["LocationPrices"] = Relationship(back_populates="location")
    reviews: list["Review"] = Relationship(back_populates="location")
    bookings: list[Booking] = Relationship(back_populates="location")
    # activities: list["Activity"] = Relationship(back_populates="location", link_model=Booking)
    # don't return any private activities in the relationship
    # todo this MAY cause issues with updating a location and replacing private activities?
    activities: list["Activity"] = Relationship(
        back_populates="location",
        link_model=Booking,
        sa_relationship_kwargs={
            "primaryjoin": "Location.id==Booking.location_id",
            "secondaryjoin": "and_(Activity.id==Booking.activity_id, Activity.invite_code==None)",
        },
    )


class LocationPrices(SQLModel, table=True):
    location_id: UUID = Field(foreign_key="location.id", primary_key=True)
    price: float
    currency: str
    day: date = Field(foreign_key="calendar.day")
    last_updated: datetime = Field(default_factory=datetime.now)

    location: Location = Relationship(back_populates="prices")


class NewActivity(BaseModel):
    name: str
    description: str
    price: float
    currency: str
    day: date
    invite_code: str | None = None
    group_id: UUID | None = None


class EditActivity(BaseModel):
    name: str | None | Empty = Empty
    description: str | None | Empty = Empty
    price: float | None | Empty = Empty
    currency: str | None | Empty = Empty
    day: date | None | Empty = Empty
    invite_code: str | None | Empty = Empty
    group_id: UUID | None | Empty = Empty


class Activity(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: str
    price: float
    currency: str
    day: date = Field(foreign_key="calendar.day")
    invite_code: str | None = None

    creator_id: UUID = Field(foreign_key="user.id")
    group_id: UUID | None = Field(foreign_key="group.id")

    group: Group = Relationship(back_populates="activities")
    location: Location = Relationship(link_model=Booking)
    booking: "Booking" = Relationship(back_populates="activity")
    reviews: list["Review"] = Relationship(back_populates="activity")
    participants: list[User] = Relationship(back_populates="activities", link_model=ActivityUserLink)
    creator: User = Relationship()

    @field_validator("invite_code")
    @classmethod
    def validate_invite_code(cls, value: str) -> str:
        """Ensure invite code is hashed"""
        if not value:
            return value

        if is_bcrypt_hash(value):
            return value

        return BcryptPasswordHandler.hash(value).hash

    def check_invite_code(self, invite_code: str) -> bool:
        if not self.invite_code:
            return True
        return BcryptPasswordHandler.validate(invite_code, self.invite_code)

    @computed_field
    @property
    def private(self) -> bool:
        return self.group_id is not None

    @classmethod
    def private_activities(cls, group_id: UUID, *where: WhereClauseT) -> Sequence["Activity"]:
        return cls.all(Activity.group_id == group_id, *where, relations=[Location, Review, Booking, Group])


class SupportRequest(SQLModel, table=True):
    __tablename__ = "support_request"
    id: Optional[int] = Field(primary_key=True)
    group_id: UUID | None = Field(foreign_key="group.id", default=None)
    user_id: UUID = Field(foreign_key="user.id")
    title: str
    resolved: bool = False

    user: User = Relationship(back_populates="support_requests")
    group: Group = Relationship(back_populates="support_requests")
    messages: list["SupportRequestMessage"] = Relationship(back_populates="request")


class SupportRequestMessage(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    request_id: int = Field(foreign_key="support_request.id")
    user_id: UUID = Field(foreign_key="user.id")
    message: str

    request: SupportRequest = Relationship(back_populates="messages")
    user: User = Relationship()


class SupportRequestIn(BaseModel):
    title: str
    message: str
    group_id: Optional[UUID] = None


class Review(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(foreign_key="user.id")
    location_id: UUID | None = Field(foreign_key="location.id")
    activity_id: UUID | None = Field(foreign_key="activity.id")
    rating: int
    review: str
    # name of user writing review
    name: str

    user: User = Relationship(back_populates="reviews")
    location: Location = Relationship(back_populates="reviews")
    activity: Activity = Relationship(back_populates="reviews")


class Weather(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    location_id: UUID | None = Field(foreign_key="location.id")
    temperature: float
    humidity: float
    wind_speed: float
    wind_direction: str
    day: date = Field(foreign_key="calendar.day")

    calendar: Calendar = Relationship(back_populates="weather")


Group.model_rebuild()


# special class for palantir usage
class PalantirUser(BaseModel, BaseUser):
    expiration: float
    user_id: UUID
    api_version: ApiVersion = ApiVersion.PALANTIR_ROLE
    role: UserRole = UserRole.USER

    @property
    def is_authenticated(self) -> bool:
        return self.expiration < time.time()

    @property
    def display_name(self) -> str:
        return "PALANTIR TEMPORARY ADMIN"

    @property
    def identity(self) -> str:
        raise PALANTIR_ROLE
