-- db/migrations/006_seed_admin_user.sql
-- Seeds a default admin user for first-time login.
-- Credentials: admin@odyssey.local / admin
-- IMPORTANT: Change this password immediately in production.

INSERT INTO admin_user (email, password_hash, display_name, role, is_active)
VALUES (
    'admin@odyssey.local',
    '$2b$12$gJ.StTbsU7DCmJTvQJbXi.FsYrU2vUIWA.zBaSYlsrUQMsC.cI8dC',
    'Administrator',
    'admin',
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    display_name  = EXCLUDED.display_name,
    is_active     = TRUE;
