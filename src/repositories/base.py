"""
Generic async repository.

Provides standard CRUD operations that all concrete repositories inherit.
The session is injected at construction time and never managed internally —
the caller (service layer, FastAPI dependency) owns the transaction boundary.
"""

from typing import Any, Generic, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic repository with typed CRUD helpers.

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get_by_id(self, record_id: UUID) -> ModelT | None:
        """Return a single record by primary key, or None if not found."""
        result = await self._session.execute(
            select(self.model).where(self.model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ModelT]:
        """Return a paginated slice of all rows (no soft-delete filter)."""
        result = await self._session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def filter_by(self, **kwargs: Any) -> Sequence[ModelT]:
        """
        Return all rows where every keyword argument matches.

        Example:
            await repo.filter_by(is_active=True, role="organizer")
        """
        stmt = select(self.model)
        for field, value in kwargs.items():
            if not hasattr(self.model, field):
                raise ValueError(f"{self.model.__name__} has no column {field!r}")
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_one_by(self, **kwargs: Any) -> ModelT | None:
        """
        Return the first row matching all keyword arguments, or None.

        Example:
            await repo.get_one_by(email="user@example.com")
        """
        stmt = select(self.model)
        for field, value in kwargs.items():
            if not hasattr(self.model, field):
                raise ValueError(f"{self.model.__name__} has no column {field!r}")
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def create(self, **kwargs: Any) -> ModelT:
        """
        Instantiate the model with the given keyword arguments,
        add it to the session, flush to obtain a DB-generated id,
        and return the instance.

        The caller is responsible for committing the transaction.
        """
        instance = self.model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        """
        Apply keyword argument updates to *instance*, flush to DB,
        and return the refreshed instance.

        The caller is responsible for committing the transaction.
        """
        for field, value in kwargs.items():
            setattr(instance, field, value)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """
        Hard-delete *instance* from the database.

        Prefer domain-specific soft-delete methods (e.g. set deleted_at)
        unless you truly need permanent removal.
        """
        await self._session.delete(instance)
        await self._session.flush()