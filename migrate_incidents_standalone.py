import pymysql

def migrate():
    try:
        connection = pymysql.connect(
            host= "148.113.201.195",
            user= "admin",
            password="Pityboy@22",
            database="watchup",
            port=3306,
            cursorclass=pymysql.cursors.DictCursor
        )
        with connection.cursor() as cursor:
            print("Altering uptime_incidents table...")
            cursor.execute("ALTER TABLE uptime_incidents MODIFY monitor_id CHAR(36) NULL;")
            print("Successfully altered uptime_incidents table.")
        connection.commit()
        connection.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
