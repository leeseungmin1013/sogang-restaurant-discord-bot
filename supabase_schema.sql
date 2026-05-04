create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists restaurants (
  id uuid primary key default gen_random_uuid(),
  legacy_id text,
  guild_id bigint not null,
  channel_id bigint,
  name text not null,
  area text not null,
  category text,
  signature_menu text,
  description text,
  image_url text,
  map_provider text,
  map_url text,
  tags text[] default '{}',
  status text not null default 'approved',
  submitted_by_user_id bigint,
  submitted_by_display_name text,
  embedding vector(768),
  embedding_text text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (guild_id, legacy_id)
);

create index if not exists restaurants_guild_status_idx
  on restaurants (guild_id, status);

create index if not exists restaurants_embedding_hnsw_idx
  on restaurants using hnsw (embedding vector_cosine_ops);

create table if not exists recommendation_logs (
  id uuid primary key default gen_random_uuid(),
  guild_id bigint not null,
  user_id bigint,
  query text not null,
  answer text,
  matched_restaurant_ids text[],
  created_at timestamptz default now()
);

create or replace function match_restaurants(
  query_embedding vector(768),
  match_guild_id bigint,
  match_count int default 5
)
returns table (
  id uuid,
  legacy_id text,
  name text,
  area text,
  category text,
  signature_menu text,
  description text,
  image_url text,
  map_provider text,
  map_url text,
  tags text[],
  similarity float
)
language sql stable
as $$
  select
    restaurants.id,
    restaurants.legacy_id,
    restaurants.name,
    restaurants.area,
    restaurants.category,
    restaurants.signature_menu,
    restaurants.description,
    restaurants.image_url,
    restaurants.map_provider,
    restaurants.map_url,
    restaurants.tags,
    1 - (restaurants.embedding <=> query_embedding) as similarity
  from restaurants
  where restaurants.guild_id = match_guild_id
    and restaurants.status = 'approved'
    and restaurants.embedding is not null
  order by restaurants.embedding <=> query_embedding
  limit match_count;
$$;
