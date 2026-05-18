from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.models.schemas import (
    AnalysisRecord,
    AnalysisResponse,
    UserProfileRequest,
    UserProfileResponse,
)


ANONYMOUS_USER_ID = "anonymous"


@dataclass(frozen=True)
class RequestUser:
    id: str = ANONYMOUS_USER_ID
    email: str | None = None
    display_name: str | None = None
    provider: str = "firebase"

    @property
    def normalized_id(self) -> str:
        return self.id.strip() or ANONYMOUS_USER_ID


class AnalysisStore:
    def list(self, user: RequestUser | None = None) -> list[AnalysisRecord]:
        raise NotImplementedError

    def get(self, analysis_id: str, user: RequestUser | None = None) -> AnalysisResponse | None:
        raise NotImplementedError

    def save(self, analysis: AnalysisResponse, user: RequestUser | None = None) -> None:
        raise NotImplementedError

    def delete(self, analysis_id: str, user: RequestUser | None = None) -> bool:
        raise NotImplementedError

    def get_profile(self, user: RequestUser | None = None) -> UserProfileResponse:
        raise NotImplementedError

    def save_profile(
        self,
        profile: UserProfileRequest,
        user: RequestUser | None = None,
    ) -> UserProfileResponse:
        raise NotImplementedError

    def saved_precedent_ids(self, user: RequestUser | None = None) -> set[str]:
        raise NotImplementedError

    def set_precedent_saved(
        self,
        precedent_id: str,
        saved: bool,
        user: RequestUser | None = None,
    ) -> bool:
        raise NotImplementedError

    @staticmethod
    def _record_from_analysis(analysis: AnalysisResponse) -> AnalysisRecord:
        return AnalysisRecord(
            id=analysis.id,
            title=analysis.title,
            preview_text=analysis.summary[:180],
            input_text=analysis.input_text,
            risk_level=analysis.risk_level,
            risk_label=analysis.risk_label,
            source_type=analysis.source_type,
            analyze_source_type=analysis.analyze_source_type,
            analysis_type=analysis.analysis_type,
            created_at=analysis.created_at,
        )


class FileAnalysisStore(AnalysisStore):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.users_path = path.with_name("users.json")
        self.saved_precedents_path = path.with_name("saved_precedents.json")
        self._lock = Lock()

    def list(self, user: RequestUser | None = None) -> list[AnalysisRecord]:
        owner_id = _owner_id(user)
        raw_items = self._items_for_owner(owner_id)
        records = [AnalysisRecord.model_validate(item["record"]) for item in raw_items]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get(self, analysis_id: str, user: RequestUser | None = None) -> AnalysisResponse | None:
        owner_id = _owner_id(user)
        for item in self._items_for_owner(owner_id):
            if item.get("analysis", {}).get("id") == analysis_id:
                return AnalysisResponse.model_validate(item["analysis"])
        return None

    def save(self, analysis: AnalysisResponse, user: RequestUser | None = None) -> None:
        owner_id = _owner_id(user)
        with self._lock:
            items = self._read()
            items = [
                item
                for item in items
                if not (
                    item.get("ownerId", ANONYMOUS_USER_ID) == owner_id
                    and item.get("analysis", {}).get("id") == analysis.id
                )
            ]
            items.append(
                {
                    "ownerId": owner_id,
                    "user": _user_payload(user),
                    "record": self._record_from_analysis(analysis).model_dump(mode="json", by_alias=True),
                    "analysis": analysis.model_dump(mode="json", by_alias=True),
                }
            )
            self._write(items)

    def delete(self, analysis_id: str, user: RequestUser | None = None) -> bool:
        owner_id = _owner_id(user)
        with self._lock:
            items = self._read()
            next_items = [
                item
                for item in items
                if not (
                    item.get("ownerId", ANONYMOUS_USER_ID) == owner_id
                    and item.get("analysis", {}).get("id") == analysis_id
                )
            ]
            if len(next_items) == len(items):
                return False
            self._write(next_items)
            return True

    def get_profile(self, user: RequestUser | None = None) -> UserProfileResponse:
        owner_id = _owner_id(user)
        profiles = self._read_users()
        raw_profile = profiles.get(owner_id, {})
        return _profile_response(user, raw_profile)

    def save_profile(
        self,
        profile: UserProfileRequest,
        user: RequestUser | None = None,
    ) -> UserProfileResponse:
        owner_id = _owner_id(user)
        with self._lock:
            profiles = self._read_users()
            current = profiles.get(owner_id, {})
            next_profile = {
                **current,
                "id": owner_id,
                "email": profile.email or current.get("email") or (user.email if user else None),
                "displayName": profile.display_name
                or current.get("displayName")
                or (user.display_name if user else None),
                "phone": profile.phone,
                "city": profile.city,
                "bio": profile.bio,
                "provider": (user.provider if user else "firebase"),
            }
            profiles[owner_id] = next_profile
            self._write_users(profiles)
            return _profile_response(user, next_profile)

    def saved_precedent_ids(self, user: RequestUser | None = None) -> set[str]:
        owner_id = _owner_id(user)
        raw_items = self._read_saved_precedents().get(owner_id, [])
        if not isinstance(raw_items, list):
            return set()
        return {str(item) for item in raw_items if str(item).strip()}

    def set_precedent_saved(
        self,
        precedent_id: str,
        saved: bool,
        user: RequestUser | None = None,
    ) -> bool:
        owner_id = _owner_id(user)
        normalized_precedent_id = precedent_id.strip()
        with self._lock:
            saved_precedents = self._read_saved_precedents()
            current_ids = set(saved_precedents.get(owner_id, []))
            if saved:
                current_ids.add(normalized_precedent_id)
            else:
                current_ids.discard(normalized_precedent_id)
            saved_precedents[owner_id] = sorted(current_ids)
            self._write_saved_precedents(saved_precedents)
        return saved

    def _items_for_owner(self, owner_id: str) -> list[dict]:
        return [
            item
            for item in self._read()
            if item.get("ownerId", ANONYMOUS_USER_ID) == owner_id
        ]

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            return []

        return data

    def _write(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)

    def _read_users(self) -> dict[str, dict]:
        if not self.users_path.exists():
            return {}

        with self.users_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    def _write_users(self, profiles: dict[str, dict]) -> None:
        self.users_path.parent.mkdir(parents=True, exist_ok=True)
        with self.users_path.open("w", encoding="utf-8") as file:
            json.dump(profiles, file, ensure_ascii=False, indent=2)

    def _read_saved_precedents(self) -> dict[str, list[str]]:
        if not self.saved_precedents_path.exists():
            return {}

        with self.saved_precedents_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    def _write_saved_precedents(self, saved_precedents: dict[str, list[str]]) -> None:
        self.saved_precedents_path.parent.mkdir(parents=True, exist_ok=True)
        with self.saved_precedents_path.open("w", encoding="utf-8") as file:
            json.dump(saved_precedents, file, ensure_ascii=False, indent=2)


class PostgresAnalysisStore(AnalysisStore):
    def __init__(self, database_url: str, auto_create_tables: bool = True) -> None:
        self.database_url = database_url
        self.auto_create_tables = auto_create_tables
        self._schema_checked = False
        self._lock = Lock()

    def list(self, user: RequestUser | None = None) -> list[AnalysisRecord]:
        owner_id = _owner_id(user)
        self._upsert_user(user)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select record
                    from lawbridge_analyses
                    where owner_id = %s
                    order by created_at desc
                    """,
                    (owner_id,),
                )
                return [AnalysisRecord.model_validate(_json_value(row[0])) for row in cursor.fetchall()]

    def get(self, analysis_id: str, user: RequestUser | None = None) -> AnalysisResponse | None:
        owner_id = _owner_id(user)
        self._upsert_user(user)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select analysis
                    from lawbridge_analyses
                    where id = %s and owner_id = %s
                    """,
                    (analysis_id, owner_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return AnalysisResponse.model_validate(_json_value(row[0]))

    def save(self, analysis: AnalysisResponse, user: RequestUser | None = None) -> None:
        owner_id = _owner_id(user)
        self._upsert_user(user)
        record = self._record_from_analysis(analysis).model_dump(mode="json", by_alias=True)
        analysis_payload = analysis.model_dump(mode="json", by_alias=True)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into lawbridge_analyses (id, owner_id, record, analysis, created_at, updated_at)
                    values (%s, %s, %s::jsonb, %s::jsonb, %s, now())
                    on conflict (id) do update set
                        owner_id = excluded.owner_id,
                        record = excluded.record,
                        analysis = excluded.analysis,
                        created_at = excluded.created_at,
                        updated_at = now()
                    """,
                    (
                        analysis.id,
                        owner_id,
                        json.dumps(record, ensure_ascii=False),
                        json.dumps(analysis_payload, ensure_ascii=False),
                        analysis.created_at,
                    ),
                )

    def delete(self, analysis_id: str, user: RequestUser | None = None) -> bool:
        owner_id = _owner_id(user)
        self._upsert_user(user)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    delete from lawbridge_analyses
                    where id = %s and owner_id = %s
                    """,
                    (analysis_id, owner_id),
                )
                return cursor.rowcount > 0

    def get_profile(self, user: RequestUser | None = None) -> UserProfileResponse:
        owner_id = _owner_id(user)
        self._upsert_user(user)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select id, email, display_name, phone, city, bio, provider
                    from lawbridge_users
                    where id = %s
                    """,
                    (owner_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return _profile_response(user, {})
                return UserProfileResponse(
                    id=row[0],
                    email=row[1],
                    display_name=row[2],
                    phone=row[3],
                    city=row[4],
                    bio=row[5],
                    provider=row[6],
                )

    def save_profile(
        self,
        profile: UserProfileRequest,
        user: RequestUser | None = None,
    ) -> UserProfileResponse:
        owner_id = _owner_id(user)
        normalized_user = user or RequestUser()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into lawbridge_users (
                        id, email, display_name, phone, city, bio, provider, created_at, updated_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, now(), now())
                    on conflict (id) do update set
                        email = coalesce(excluded.email, lawbridge_users.email),
                        display_name = coalesce(excluded.display_name, lawbridge_users.display_name),
                        phone = excluded.phone,
                        city = excluded.city,
                        bio = excluded.bio,
                        provider = excluded.provider,
                        updated_at = now()
                    returning id, email, display_name, phone, city, bio, provider
                    """,
                    (
                        owner_id,
                        _clean_optional(profile.email) or _clean_optional(normalized_user.email),
                        _clean_optional(profile.display_name)
                        or _clean_optional(normalized_user.display_name),
                        _clean_optional(profile.phone),
                        _clean_optional(profile.city),
                        _clean_optional(profile.bio),
                        normalized_user.provider,
                    ),
                )
                row = cursor.fetchone()

        return UserProfileResponse(
            id=row[0],
            email=row[1],
            display_name=row[2],
            phone=row[3],
            city=row[4],
            bio=row[5],
            provider=row[6],
        )

    def saved_precedent_ids(self, user: RequestUser | None = None) -> set[str]:
        owner_id = _owner_id(user)
        self._upsert_user(user)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select precedent_id
                    from lawbridge_saved_precedents
                    where owner_id = %s
                    """,
                    (owner_id,),
                )
                return {row[0] for row in cursor.fetchall()}

    def set_precedent_saved(
        self,
        precedent_id: str,
        saved: bool,
        user: RequestUser | None = None,
    ) -> bool:
        owner_id = _owner_id(user)
        self._upsert_user(user)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if saved:
                    cursor.execute(
                        """
                        insert into lawbridge_saved_precedents (owner_id, precedent_id, created_at)
                        values (%s, %s, now())
                        on conflict (owner_id, precedent_id) do nothing
                        """,
                        (owner_id, precedent_id),
                    )
                else:
                    cursor.execute(
                        """
                        delete from lawbridge_saved_precedents
                        where owner_id = %s and precedent_id = %s
                        """,
                        (owner_id, precedent_id),
                    )
        return saved

    def _upsert_user(self, user: RequestUser | None) -> None:
        normalized_user = user or RequestUser()
        owner_id = normalized_user.normalized_id
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into lawbridge_users (id, email, display_name, provider, created_at, updated_at)
                    values (%s, %s, %s, %s, now(), now())
                    on conflict (id) do update set
                        email = coalesce(excluded.email, lawbridge_users.email),
                        display_name = coalesce(excluded.display_name, lawbridge_users.display_name),
                        provider = excluded.provider,
                        updated_at = now()
                    """,
                    (
                        owner_id,
                        _clean_optional(normalized_user.email),
                        _clean_optional(normalized_user.display_name),
                        normalized_user.provider,
                    ),
                )

    def _connect(self):
        import psycopg

        self._ensure_schema()
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        if self._schema_checked:
            return

        with self._lock:
            if self._schema_checked:
                return

            if self.auto_create_tables:
                import psycopg

                with psycopg.connect(self.database_url) as connection:
                    with connection.cursor() as cursor:
                        for statement in _sql_statements(SCHEMA_SQL):
                            cursor.execute(statement)

            self._schema_checked = True


SCHEMA_SQL = """
create table if not exists lawbridge_users (
    id text primary key,
    email text,
    display_name text,
    phone text,
    city text,
    bio text,
    provider text not null default 'firebase',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table lawbridge_users add column if not exists phone text;
alter table lawbridge_users add column if not exists city text;
alter table lawbridge_users add column if not exists bio text;

create table if not exists lawbridge_analyses (
    id text primary key,
    owner_id text not null references lawbridge_users(id) on delete cascade,
    record jsonb not null,
    analysis jsonb not null,
    created_at timestamptz not null,
    updated_at timestamptz not null default now()
);

create index if not exists lawbridge_analyses_owner_created_idx
    on lawbridge_analyses (owner_id, created_at desc);

create table if not exists lawbridge_saved_precedents (
    owner_id text not null references lawbridge_users(id) on delete cascade,
    precedent_id text not null,
    created_at timestamptz not null default now(),
    primary key (owner_id, precedent_id)
);

create index if not exists lawbridge_saved_precedents_owner_created_idx
    on lawbridge_saved_precedents (owner_id, created_at desc);
"""


def build_analysis_store(
    *,
    database_url: str | None,
    analysis_store_path: Path,
    auto_create_db_tables: bool = True,
) -> AnalysisStore:
    if database_url:
        return PostgresAnalysisStore(
            database_url=database_url,
            auto_create_tables=auto_create_db_tables,
        )
    return FileAnalysisStore(analysis_store_path)


def _owner_id(user: RequestUser | None) -> str:
    if user is None:
        return ANONYMOUS_USER_ID
    return user.normalized_id


def _user_payload(user: RequestUser | None) -> dict[str, str | None]:
    normalized_user = user or RequestUser()
    return {
        "id": normalized_user.normalized_id,
        "email": _clean_optional(normalized_user.email),
        "displayName": _clean_optional(normalized_user.display_name),
        "provider": normalized_user.provider,
    }


def _profile_response(
    user: RequestUser | None,
    raw_profile: dict,
) -> UserProfileResponse:
    normalized_user = user or RequestUser()
    return UserProfileResponse(
        id=normalized_user.normalized_id,
        email=raw_profile.get("email") or _clean_optional(normalized_user.email),
        display_name=raw_profile.get("displayName") or _clean_optional(normalized_user.display_name),
        phone=raw_profile.get("phone"),
        city=raw_profile.get("city"),
        bio=raw_profile.get("bio"),
        provider=raw_profile.get("provider") or normalized_user.provider,
    )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _json_value(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]
