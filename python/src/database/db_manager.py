import os
import sqlite3
import logging

try:
    import mysql.connector
except ImportError:
    mysql = None

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self, config):
        db_config = config.get('database', {})
        self.host = db_config.get('host', 'localhost')
        self.port = db_config.get('port', 3306)
        self.username = db_config.get('username', 'root')
        self.password = db_config.get('password', 'Shivam@9797')
        self.database = db_config.get('database', 'camfu_db')
        
        # Path to root camfu.db
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        self.sqlite_path = os.path.join(root_dir, 'camfu.db')
        self.use_sqlite = False
        
    def get_connection(self):
        if not self.use_sqlite and mysql is not None:
            try:
                conn = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.username,
                    password=self.password,
                    database=self.database,
                    connection_timeout=1
                )
                return ('mysql', conn)
            except Exception:
                self.use_sqlite = True

        try:
            conn = sqlite3.connect(self.sqlite_path, timeout=5)
            conn.row_factory = sqlite3.Row
            return ('sqlite', conn)
        except Exception as e:
            logger.error(f"Error connecting to SQLite: {e}")
            return (None, None)

    def get_active_cameras(self):
        db_type, conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, camera_name, location, camera_url FROM cameras WHERE status = 'ACTIVE'")
            rows = cursor.fetchall()
            if db_type == 'sqlite':
                return [dict(row) for row in rows]
            else:
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching cameras: {e}")
            return []
        finally:
            if conn:
                try:
                    cursor.close()
                    conn.close()
                except Exception:
                    pass

    def save_priority_score(self, camera_id, motion, crowd, behavior, time_factor, overall):
        db_type, conn = self.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            if db_type == 'sqlite':
                query = """
                INSERT INTO priority_scores 
                (camera_id, motion_score, crowd_density_score, unusual_behavior_score, time_factor, overall_priority_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """
            else:
                query = """
                INSERT INTO priority_scores 
                (camera_id, motion_score, crowd_density_score, unusual_behavior_score, time_factor, overall_priority_score)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
            cursor.execute(query, (camera_id, motion, crowd, behavior, time_factor, overall))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving priority score: {e}")
            return False
        finally:
            if conn:
                try:
                    cursor.close()
                    conn.close()
                except Exception:
                    pass
