#!/usr/bin/env python3
"""
Script to create the MySQL database on the VPS
"""
import pymysql
import sys


def create_database():
    """Create the ezzo-sales database if it doesn't exist"""
    
    try:
        # Connect to MySQL server (without specifying database)
        connection = pymysql.connect(
            host='217.160.19.34',
            port=3306,
            user='ezzo_user',
            password='246411',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print("✅ Connected to MySQL server")
        
        with connection.cursor() as cursor:
            # Create database if not exists
            cursor.execute("CREATE DATABASE IF NOT EXISTS `ezzo-sales` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print("✅ Database 'ezzo-sales' created successfully (or already exists)")
            
            # Show databases
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            print("\n📊 Available databases:")
            for db in databases:
                print(f"  - {db['Database']}")
        
        connection.commit()
        connection.close()
        
        print("\n✅ Database setup complete!")
        print("You can now run: python start.sh")
        
    except pymysql.Error as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_database()
