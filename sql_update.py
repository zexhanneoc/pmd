============================================================
🧹 DATABASE CLEANING TOOL
============================================================

📊 Existing database found: rainfall.db

📊 DATABASE STATISTICS
========================================
📋 Reports (dates): 15
📊 Total readings: 450
📍 Unique stations: 80
❓ Unresolved stations: 5
📅 Date range: 2026-07-01 to 2026-07-22

🏆 Top 5 stations by number of readings:
   Lahore: 15
   Karachi: 15
   Islamabad: 15
   Peshawar: 14
   Quetta: 14

🆕 Latest 5 readings:
   2026-07-22: Lahore - 43mm (Punjab)
   2026-07-22: Karachi - 12mm (Sindh)
   2026-07-22: Islamabad - 8mm (Islamabad)
   2026-07-21: Lahore - 15mm (Punjab)
   2026-07-21: Peshawar - 5mm (Khyber Pakhtunkhwa)

========================================

⚠️ WARNING: This will DELETE your current database!
Create a backup before cleaning? (y/n): y
✅ Database backed up to: database_backups/rainfall_backup_20260723_143022.db

Are you sure you want to delete the current database? (yes/no): yes

🧹 Cleaning database...
🗑️ Removed existing database
✅ Created fresh database with schema at: rainfall.db

📄 PDF files found. Do you want to re-parse them now?
Run parser with --force? (y/n): y

🔄 Running parser...
2026-07-23 14:30:30 [INFO] Parsing 2026-07-01.pdf...
...
✅ Parser completed!

📊 FINAL DATABASE STATUS
========================================
📋 Reports (dates): 15
📊 Total readings: 455
📍 Unique stations: 85
❓ Unresolved stations: 2
📅 Date range: 2026-07-01 to 2026-07-22
========================================

✅ Database cleaning complete!