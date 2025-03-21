from datetime import datetime

from sqlalchemy import BigInteger, delete as sqlalchemy_delete, DateTime, update as sqlalchemy_update, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column, selectinload

from config import conf


class Base(AsyncAttrs, DeclarativeBase):

    @declared_attr
    def __tablename__(self) -> str:
        __name = self.__name__[:1]
        for i in self.__name__[1:]:
            if i.isupper():
                __name += '_'
            __name += i
        __name = __name.lower()

        if __name.endswith('y'):
            __name = __name[:-1] + 'ie'
        return __name + 's'


class AsyncDatabaseSession:
    def __init__(self):
        self._session = None
        self._engine = None

    def __getattr__(self, name):
        return getattr(self._session, name)

    def init(self):
        self._engine = create_async_engine(conf.db.db_url)
        self._session = sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)()

    async def refresh(self, model):
        return await self._session.refresh(model)

    async def create_all(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


db = AsyncDatabaseSession()
db.init()


# ----------------------------- ABSTRACTS ----------------------------------
class AbstractClass:
    @staticmethod
    async def commit():
        try:
            await db.commit()
        except Exception as e:
            print(e)
            await db.rollback()

    @staticmethod
    async def refresh(obj):
        await db.refresh(obj)

    @classmethod
    async def create(cls, **kwargs):
        object_ = cls(**kwargs)
        db.add(object_)
        await cls.commit()
        await cls.refresh(object_)
        return object_

    @classmethod
    async def update(cls, id_, **kwargs):
        query = (
            sqlalchemy_update(cls)
            .where(cls.id == id_)
            .values(**kwargs)
            .execution_options(synchronize_session="fetch")
        )
        await db.execute(query)
        await cls.commit()

    @classmethod
    async def get(cls, criteria, *, relationship=None):
        query = select(cls).where(criteria)
        if relationship:
            query = query.options(selectinload(relationship))
        return (await db.execute(query)).scalar()

    @classmethod
    async def count(cls):
        query = select(func.count()).select_from(cls)
        return (await db.execute(query)).scalar()

    @classmethod
    async def delete_by_id(cls, id_):
        query = sqlalchemy_delete(cls).where(cls.id == id_)
        await db.execute(query)
        await cls.commit()

    async def delete(self):
        query = sqlalchemy_delete(self.__class__).where(self.__class__.id == self.id)
        await db.execute(query)
        await self.__class__.commit()

    @classmethod
    async def filter(cls, criteria, *, relationship=None, columns=None):
        if columns:
            query = select(*columns)
        else:
            query = select(cls)

        query = query.where(criteria)

        if relationship:
            query = query.options(selectinload(relationship))
        return (await db.execute(query)).scalars()

    @classmethod
    async def all(cls):
        return (await db.execute(select(cls))).scalars()

    @classmethod
    async def run_query(cls, query):
        result = await db.execute(query)
        return result.scalars().all()

    @classmethod
    async def query_count(cls, query):
        result = await db.execute(query)
        return result.scalar()


class BaseModel(Base, AbstractClass):
    __abstract__ = True
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    def __str__(self):
        return f"{self.id}"


class CreatedBaseModel(BaseModel):
    __abstract__ = True
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)