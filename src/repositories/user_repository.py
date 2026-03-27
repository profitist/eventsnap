"""
User, UserPasswordCredential, UserOAuthAccount repositories.

All three models belong to the same aggregate root (User), so they
live together here. Separation into individual files is fine if the
module grows; a simple import alias keeps the public API stable.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models.user import User, UserOAuthAccount, UserPasswordCredential
from src.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    # ------------------------------------------------------------------
    # Lookup methods
    # ------------------------------------------------------------------

    async def get_by_email(self, email: str) -> User | None:
        """
        Find an active (non-deleted) user by email address.
        Case-sensitive; callers should normalise the email before querying.
        """
        result = await self._session.execute(
            select(User)
            .where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_credentials(self, user_id: UUID) -> User | None:
        """
        Fetch a user together with the password credential sub-row.
        Avoids a lazy-load when the auth service needs the hash immediately.
        """
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.password_credential))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_oauth(self, user_id: UUID) -> User | None:
        """
        Fetch a user together with all linked OAuth accounts.
        """
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.oauth_accounts))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_active_by_id(self, user_id: UUID) -> User | None:
        """Return a non-deleted, active user by primary key."""
        result = await self._session.execute(
            select(User).where(
                User.id == user_id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def soft_delete(self, user: User) -> User:
        """
        Mark the user as deleted and deactivate the account.
        Does not touch related rows — cascade is handled at the DB level.
        """
        return await self.update(
            user,
            deleted_at=datetime.now(tz=timezone.utc),
            is_active=False,
        )


class UserPasswordCredentialRepository(BaseRepository[UserPasswordCredential]):
    model = UserPasswordCredential

    async def get_by_user_id(self, user_id: UUID) -> UserPasswordCredential | None:
        """Return the password credential row for the given user, if any."""
        result = await self._session.execute(
            select(UserPasswordCredential).where(
                UserPasswordCredential.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert_hash(
        self, user_id: UUID, password_hash: str
    ) -> UserPasswordCredential:
        """
        Create or overwrite the bcrypt hash for *user_id*.

        Called both during initial registration and on password-change flows.
        """
        existing = await self.get_by_user_id(user_id)
        if existing is None:
            return await self.create(user_id=user_id, password_hash=password_hash)
        return await self.update(existing, password_hash=password_hash)


class UserOAuthAccountRepository(BaseRepository[UserOAuthAccount]):
    model = UserOAuthAccount

    async def get_by_provider(
        self, provider: str, provider_user_id: str
    ) -> UserOAuthAccount | None:
        """
        Look up an OAuth identity by provider + provider-side subject ID.

        This is the primary key used during the OAuth callback to decide
        whether to create a new user or log in an existing one.
        """
        result = await self._session.execute(
            select(UserOAuthAccount).where(
                UserOAuthAccount.provider == provider,
                UserOAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_for_user(self, user_id: UUID) -> list[UserOAuthAccount]:
        """Return all OAuth accounts linked to a user (Google + Apple, etc.)."""
        result = await self._session.execute(
            select(UserOAuthAccount).where(UserOAuthAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    async def unlink(self, provider: str, user_id: UUID) -> bool:
        """
        Remove the OAuth link for a specific provider from a user account.
        Returns True if a row was deleted, False if it did not exist.
        """
        account = await self.get_one_by(provider=provider, user_id=user_id)
        if account is None:
            return False
        await self.delete(account)
        return True