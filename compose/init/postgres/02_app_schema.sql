-- Application schema for the login-risk scenario.
-- This is the system of record: user identity, role and account status live
-- here. Everything else in the lab is derived from this database or from events.

CREATE TABLE roles (
    role_id      integer PRIMARY KEY,
    name         text NOT NULL UNIQUE,
    description  text NOT NULL
);

CREATE TABLE users (
    user_id        uuid PRIMARY KEY,
    email          text NOT NULL UNIQUE,
    full_name      text NOT NULL,
    role_id        integer NOT NULL REFERENCES roles(role_id),
    account_status text NOT NULL CHECK (account_status IN
                       ('active', 'disabled', 'locked', 'suspended')),
    department     text NOT NULL,
    home_country   text NOT NULL,
    home_city      text NOT NULL,
    home_lat       double precision NOT NULL,
    home_lon       double precision NOT NULL,
    mfa_enabled    boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL,
    last_login_at  timestamptz,
    deleted_at     timestamptz,
    CHECK (updated_at >= created_at),
    CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE INDEX users_updated_at_idx ON users (updated_at);
CREATE INDEX users_status_idx ON users (account_status);
