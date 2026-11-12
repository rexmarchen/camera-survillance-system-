package com.camfu.surveillance.util;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.ResultSet;

/**
 * Database Connection Pool Manager
 * Connects to local embedded SQLite (camfu.db) or MySQL if accessible.
 */
public class DatabaseConnectionPool {
    private static final Logger logger = LoggerFactory.getLogger(DatabaseConnectionPool.class);
    
    private static final String MYSQL_URL = "jdbc:mysql://localhost:3306/camfu_db?useSSL=false&serverTimezone=UTC&allowPublicKeyRetrieval=true";
    private static final String MYSQL_USER = "root";
    private static final String MYSQL_PASSWORD = "Shivam@9797";
    
    private static final String SQLITE_URL = "jdbc:sqlite:camfu.db";

    private static volatile boolean useSQLite = false;
    private static volatile boolean initialized = false;

    static {
        try {
            Class.forName("org.sqlite.JDBC");
        } catch (Throwable ignored) {}
        try {
            Class.forName("com.mysql.cj.jdbc.Driver");
        } catch (Throwable ignored) {}
    }

    public static Connection getConnection() throws SQLException {
        if (useSQLite) {
            return getSQLiteConn();
        }

        try {
            DriverManager.setLoginTimeout(1);
            Connection conn = DriverManager.getConnection(MYSQL_URL, MYSQL_USER, MYSQL_PASSWORD);
            return conn;
        } catch (SQLException e) {
            logger.warn("MySQL server not reachable. Switching to local SQLite database (camfu.db).");
            useSQLite = true;
            return getSQLiteConn();
        }
    }

    private static synchronized Connection getSQLiteConn() throws SQLException {
        Connection conn = DriverManager.getConnection(SQLITE_URL);
        if (!initialized) {
            initSchema(conn);
            initialized = true;
        }
        return conn;
    }

    private static void initSchema(Connection conn) {
        try (Statement stmt = conn.createStatement()) {
            stmt.execute("PRAGMA journal_mode=WAL;");
            
            stmt.execute("CREATE TABLE IF NOT EXISTS cameras (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "camera_name TEXT NOT NULL UNIQUE, " +
                    "location TEXT, " +
                    "camera_url TEXT NOT NULL, " +
                    "resolution TEXT DEFAULT '1280x720', " +
                    "fps INTEGER DEFAULT 15, " +
                    "status TEXT DEFAULT 'ACTIVE', " +
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, " +
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP" +
                    ");");

            stmt.execute("CREATE TABLE IF NOT EXISTS priority_scores (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "camera_id INTEGER NOT NULL, " +
                    "motion_score REAL DEFAULT 0, " +
                    "crowd_density_score REAL DEFAULT 0, " +
                    "unusual_behavior_score REAL DEFAULT 0, " +
                    "time_factor REAL DEFAULT 0, " +
                    "overall_priority_score REAL DEFAULT 0, " +
                    "timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP" +
                    ");");

            stmt.execute("CREATE TABLE IF NOT EXISTS events (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "camera_id INTEGER NOT NULL, " +
                    "event_type TEXT NOT NULL, " +
                    "event_description TEXT, " +
                    "confidence_score REAL DEFAULT 0, " +
                    "priority_level TEXT DEFAULT 'MEDIUM', " +
                    "clip_start_time DATETIME, " +
                    "clip_end_time DATETIME, " +
                    "clip_path TEXT, " +
                    "clip_size_mb REAL DEFAULT 0, " +
                    "is_stored INTEGER DEFAULT 0, " +
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP" +
                    ");");

            // Seed default cameras if empty
            try (ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM cameras")) {
                if (rs.next() && rs.getInt(1) == 0) {
                    stmt.execute("INSERT OR IGNORE INTO cameras (camera_name, location, camera_url, resolution, fps, status) " +
                            "VALUES ('Webcam / Camera 1', 'Local Device', '0', '1280x720', 15, 'ACTIVE');");
                    stmt.execute("INSERT OR IGNORE INTO cameras (camera_name, location, camera_url, resolution, fps, status) " +
                            "VALUES ('Entrance Gate A', 'Main Entrance', 'demo://entrance', '1280x720', 15, 'ACTIVE');");
                    stmt.execute("INSERT OR IGNORE INTO cameras (camera_name, location, camera_url, resolution, fps, status) " +
                            "VALUES ('Lobby Corridor', 'Building 1 - Level 1', 'demo://lobby', '1280x720', 15, 'ACTIVE');");
                    stmt.execute("INSERT OR IGNORE INTO cameras (camera_name, location, camera_url, resolution, fps, status) " +
                            "VALUES ('Parking Area', 'East Parking Lot', 'demo://parking', '1280x720', 15, 'ACTIVE');");
                    logger.info("Initialized default cameras in local database.");
                }
            }
        } catch (SQLException e) {
            logger.error("Error initializing database schema", e);
        }
    }

    public static boolean testConnection() {
        try (Connection conn = getConnection()) {
            return true;
        } catch (SQLException e) {
            return false;
        }
    }
}