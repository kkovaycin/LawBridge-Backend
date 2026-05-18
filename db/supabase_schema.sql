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
