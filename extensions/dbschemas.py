from extensions.extensions import get_db_connection

def setup_database_schemas():
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            raise Exception("Failed to connect to database")

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id CHAR(36) PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id CHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
        """)

        # cursor.execute("""
        #     ALTER TABLE users
        #         ADD COLUMN role_id INT DEFAULT 1;
        # """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id CHAR(36) PRIMARY KEY,
                user_id CHAR(36) NOT NULL,
                project_id CHAR(36) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitors (
                id CHAR(36) PRIMARY KEY,
                project_id CHAR(36) NOT NULL,
                name VARCHAR(255) NOT NULL,
                url TEXT NOT NULL,
                type VARCHAR(50) DEFAULT 'http',
                check_interval INT DEFAULT 60,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitor_checks (
                id CHAR(36) PRIMARY KEY,
                monitor_id CHAR(36) NOT NULL,
                status VARCHAR(50) NOT NULL,
                response_time_ms INT,
                status_code INT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (monitor_id) REFERENCES monitors(id)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id CHAR(36) PRIMARY KEY,
                monitor_id CHAR(36) NOT NULL,
                type VARCHAR(50) NOT NULL,
                message TEXT,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                FOREIGN KEY (monitor_id) REFERENCES monitors(id)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id CHAR(36) PRIMARY KEY,
                user_id CHAR(36),
                project_id CHAR(36),
                title VARCHAR(255) NOT NULL,
                description TEXT,
                type VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                -- Foreign keys are optional here if we want to allow system activities without user/project or if we want soft links
                -- But let's add them for referential integrity if possible.
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id CHAR(36) PRIMARY KEY,
                project_id CHAR(36) NOT NULL,
                type VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                source VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                user_id CHAR(36) PRIMARY KEY,
                api_key CHAR(36) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uptime_monitors (
                id CHAR(36) PRIMARY KEY,
                project_id CHAR(36) NOT NULL,
                name VARCHAR(255),
                url VARCHAR(2048) NOT NULL,
                interval_seconds INT DEFAULT 60,
                timeout_ms INT DEFAULT 5000,
                status VARCHAR(20) DEFAULT 'up',
                consecutive_failures INT DEFAULT 0,
                last_checked_at TIMESTAMP NULL,
                next_check_at TIMESTAMP NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP NULL,
                UNIQUE KEY uq_uptime_project_url (project_id, url(255)),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uptime_heartbeats (
                id CHAR(36) PRIMARY KEY,
                project_id CHAR(36) NOT NULL,
                monitor_id CHAR(36) NOT NULL,
                status VARCHAR(10) NOT NULL,
                status_code INT,
                response_time_ms INT,
                error_message TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (monitor_id) REFERENCES uptime_monitors(id),
                KEY idx_uptime_hb_monitor_time (monitor_id, checked_at)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uptime_incidents (
                id CHAR(36) PRIMARY KEY,
                project_id CHAR(36) NOT NULL,
                monitor_id CHAR(36) NOT NULL,
                status VARCHAR(20) DEFAULT 'open',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL,
                started_reason VARCHAR(50) DEFAULT 'down',
                resolved_reason VARCHAR(50),
                last_error TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (monitor_id) REFERENCES uptime_monitors(id),
                KEY idx_uptime_inc_monitor_status (monitor_id, status)
            ) ENGINE=InnoDB;
        """)


        # cursor.execute("""
        #     ALTER TABLE subscriptions
        #         ADD COLUMN subscription_type VARCHAR(255) DEFAULT 'pro';
        # """)

        conn.commit()
        print("✅ Database schema setup completed")

    except Exception as e:
        print(f"❌ Database schema setup failed: {e}")
        raise

    finally:
        if conn:
            conn.close()
