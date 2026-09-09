from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession,async_sessionmaker



DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/news_app?charset=utf8"

#创建异步引擎
create_engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=10,
)

#创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind = create_engine,
    class_= AsyncSession,
    expire_on_commit= False
)

#依赖项，用于获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()