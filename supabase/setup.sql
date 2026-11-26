-- SOMA database. Run once in Supabase: SQL Editor > New query > paste everything > Run.
-- Safe to run again: it only creates what is missing.
--
-- Row Level Security is on for every table, with no policies: browsers can never read or
-- write these tables. Only the SOMA server, using the secret key, can.
-- No recordings and no typed answers are ever stored: only numbers about practice.

-- Classes created by teachers; learners join with the 6-letter code
create table if not exists public.classes (
  id              uuid primary key default gen_random_uuid(),
  teacher_id      uuid not null references auth.users (id) on delete cascade,
  name            text not null,
  code            text not null unique,
  session_minutes int  not null default 40 check (session_minutes between 1 and 120),
  created_at      timestamptz not null default now()
);

-- One row per account: the name shown in the app and the class
create table if not exists public.profiles (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  role       text not null check (role in ('learner', 'teacher', 'admin')),
  name       text not null,
  class_id   uuid references public.classes (id) on delete set null,
  created_at timestamptz not null default now()
);

-- Each learner's current difficulty (1-9) in each language, set by the placement check
create table if not exists public.levels (
  user_id    uuid not null references auth.users (id) on delete cascade,
  language   text not null,
  difficulty int  not null check (difficulty between 1 and 9),
  updated_at timestamptz not null default now(),
  primary key (user_id, language)
);

-- Steps passed in the guided "disagreeing politely" sequence
create table if not exists public.progress (
  user_id   uuid not null references auth.users (id) on delete cascade,
  step      int  not null,
  passed_at timestamptz not null default now(),
  primary key (user_id, step)
);

-- Raw practice events (the "extract" side of the ETL pipeline)
create table if not exists public.events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  class_id   uuid references public.classes (id) on delete set null,
  kind       text not null check (kind in ('placement', 'task', 'level', 'session_start', 'session_end')),
  language   text not null,
  unit       text,
  difficulty int,
  passed     boolean,
  seconds    real,
  wpm        int,
  created_at timestamptz not null default now()
);
create index if not exists events_created_at on public.events (created_at);
create index if not exists events_user_day on public.events (user_id, created_at);

-- Clean daily totals per learner and language (the "load" side), read by the teacher dashboard
create table if not exists public.daily_stats (
  user_id          uuid not null references auth.users (id) on delete cascade,
  day              date not null,
  language         text not null,
  class_id         uuid references public.classes (id) on delete set null,
  sessions         int  not null default 0,
  practice_minutes real not null default 0,
  tasks            int  not null default 0,
  passed           int  not null default 0,
  avg_wpm          real,
  difficulty       int,
  last_active      timestamptz,
  updated_at       timestamptz not null default now(),
  primary key (user_id, day, language)
);

-- Where each pipeline stopped last time (the watermark)
create table if not exists public.etl_state (
  pipeline  text primary key,
  watermark timestamptz not null
);

alter table public.classes     enable row level security;
alter table public.profiles    enable row level security;
alter table public.levels      enable row level security;
alter table public.progress    enable row level security;
alter table public.events      enable row level security;
alter table public.daily_stats enable row level security;
alter table public.etl_state   enable row level security;

-- Fluency measures and the green/yellow streak (added later; safe to run again)
alter table public.events      add column if not exists scenario text;
alter table public.events      add column if not exists pauses_per_min real;
alter table public.events      add column if not exists fillers_per_100 real;
alter table public.daily_stats add column if not exists avg_pauses real;
alter table public.daily_stats add column if not exists avg_fillers real;
alter table public.levels      add column if not exists streak int not null default 0;
