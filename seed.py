"""
CRISS - Campus Resource Intelligence & Sharing System
Seed Script: Populates realistic, rich academic dataset with demo users,
inventory, copies, reservations, loans, unmet requests, and maintenance.
"""

import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import mysql.connector
from config import Config

def seed_database():
    print(f"Connecting to MySQL at {Config.MYSQL_HOST}:{Config.MYSQL_PORT} as {Config.MYSQL_USER}...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            autocommit=False
        )
        cursor = conn.cursor(dictionary=True)
        print("Connected successfully. Starting data seeding...")

        # ---------------------------------------------------------------------
        # Clear existing data in reverse dependency order
        # ---------------------------------------------------------------------
        tables_to_clear = [
            "notifications", "usage_logs", "maintenance_records",
            "resource_requests", "loans", "reservations", "student_listings",
            "resource_copies", "resources", "categories", "users", "departments"
        ]
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        for tbl in tables_to_clear:
            cursor.execute(f"TRUNCATE TABLE {tbl};")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        print("Cleared existing tables.")

        # ---------------------------------------------------------------------
        # 1. Departments
        # ---------------------------------------------------------------------
        departments_data = [
            ('CS', 'Computer Science & Engineering', 'Turing Academic Complex'),
            ('EE', 'Electrical & Electronics Engineering', 'Tesla Engineering Hall'),
            ('ME', 'Mechanical Engineering', 'Edison Technology Wing'),
            ('LIB', 'Central Library & Learning Commons', 'Dr. Radhakrishnan Library Building'),
            ('PAS', 'Physics & Applied Sciences', 'Raman Science Block')
        ]
        cursor.executemany(
            "INSERT INTO departments (code, name, building) VALUES (%s, %s, %s);",
            departments_data
        )
        conn.commit()

        # Query department IDs
        cursor.execute("SELECT department_id, code FROM departments;")
        dept_map = {row['code']: row['department_id'] for row in cursor.fetchall()}
        print(f"Inserted {len(dept_map)} departments.")

        # ---------------------------------------------------------------------
        # 2. Users (Hashed Passwords)
        # ---------------------------------------------------------------------
        # Passwords:
        # Admin:   AdminPassword@123
        # Faculty: FacultyPassword@123
        # Student: StudentPassword@123
        admin_hash = generate_password_hash("AdminPassword@123")
        faculty_hash = generate_password_hash("FacultyPassword@123")
        student_hash = generate_password_hash("StudentPassword@123")

        users_data = [
            # Admin
            ('admin@criss.edu', admin_hash, 'Dr. Eleanor Vance (Dean of Academic Resources)', 'admin', dept_map['LIB'], '+1-555-0199', 'ADM-001', 'active'),
            # Faculty
            ('faculty@criss.edu', faculty_hash, 'Prof. Rajesh Kulkarni (Robotics Lab Coordinator)', 'faculty', dept_map['EE'], '+1-555-0142', 'FAC-042', 'active'),
            ('sharma.fac@criss.edu', faculty_hash, 'Prof. Sunita Sharma (HOD Computer Science)', 'faculty', dept_map['CS'], '+1-555-0143', 'FAC-043', 'active'),
            # Students
            ('student@criss.edu', student_hash, 'Aarav Sharma', 'student', dept_map['CS'], '+1-555-0101', 'STU-2024-001', 'active'),
            ('lender@criss.edu', student_hash, 'Priya Patel', 'student', dept_map['EE'], '+1-555-0102', 'STU-2023-018', 'active'),
            ('rohit@criss.edu', student_hash, 'Rohit Verma', 'student', dept_map['ME'], '+1-555-0103', 'STU-2025-089', 'active'),
            ('neha@criss.edu', student_hash, 'Neha Gupta', 'student', dept_map['CS'], '+1-555-0104', 'STU-2024-055', 'active'),
            ('vikram@criss.edu', student_hash, 'Vikram Singh', 'student', dept_map['PAS'], '+1-555-0105', 'STU-2025-112', 'active')
        ]
        cursor.executemany(
            """INSERT INTO users (email, password_hash, full_name, role, department_id, phone, student_faculty_id, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s);""",
            users_data
        )
        conn.commit()

        cursor.execute("SELECT user_id, email FROM users;")
        user_map = {row['email']: row['user_id'] for row in cursor.fetchall()}
        print(f"Inserted {len(user_map)} users.")

        # ---------------------------------------------------------------------
        # 3. Categories
        # ---------------------------------------------------------------------
        categories_data = [
            ('Textbooks', 'Standard academic textbooks, reference monographs, and lab manuals.', 14),
            ('Scientific Calculators', 'Programmable, graphing, and standard engineering scientific calculators.', 7),
            ('Lab Kits', 'Hardware development platforms including Arduino, Raspberry Pi, and sensor bundles.', 10),
            ('Computers & Laptops', 'Loaner laptops, development machines, and high-performance workstation nodes.', 3),
            ('Project Components', 'Electronics test equipment, oscilloscopes, multimeters, and breadboard modules.', 5),
            ('Study Rooms', 'Bookable group discussion spaces, quiet individual cubicles, and presentation rooms.', 1)
        ]
        cursor.executemany(
            "INSERT INTO categories (name, description, max_borrow_days) VALUES (%s, %s, %s);",
            categories_data
        )
        conn.commit()

        cursor.execute("SELECT category_id, name FROM categories;")
        cat_map = {row['name']: row['category_id'] for row in cursor.fetchall()}
        print(f"Inserted {len(cat_map)} categories.")

        # ---------------------------------------------------------------------
        # 4. Resources (Institutional & Student-owned)
        # ---------------------------------------------------------------------
        resources_data = [
            # 1. Textbooks
            ('Database System Concepts (Silberschatz, Korth, Sudarshan - 7th Ed)',
             cat_map['Textbooks'], dept_map['CS'], 'institution', None,
             '978-0078022159', 'Abraham Silberschatz', 'Relational database theory, normalization, SQL & query optimization coursework',
             'Central Library - 2nd Floor Shelf CS-104', False),
            
            ('Introduction to Algorithms (CLRS - 4th Edition)',
             cat_map['Textbooks'], dept_map['CS'], 'institution', None,
             '978-0262046305', 'Cormen, Leiserson, Rivest, Stein', 'Data structures, algorithm complexity, dynamic programming coursework',
             'Central Library - 2nd Floor Shelf CS-201', False),

            ('Modern Operating Systems (Andrew S. Tanenbaum - 4th Ed)',
             cat_map['Textbooks'], dept_map['CS'], 'institution', None,
             '978-0133591620', 'Andrew S. Tanenbaum', 'Kernel design, concurrency, memory paging and OS projects',
             'Central Library - 2nd Floor Shelf CS-305', False),

            # 2. Scientific Calculators
            ('Casio fx-991CW ClassWiz Advanced Scientific Calculator',
             cat_map['Scientific Calculators'], dept_map['LIB'], 'institution', None,
             'FX991CW-PKG', 'Casio ClassWiz 2024', 'Engineering calculus, linear algebra, numerical analysis, matrix calculations',
             'Library Tech Circulation Desk A', False),

            ('Texas Instruments TI-84 Plus CE Color Graphing Calculator',
             cat_map['Scientific Calculators'], dept_map['LIB'], 'institution', None,
             'TI84CE-COL', 'Texas Instruments', 'Statistical graphing, differential equations, Fourier transforms',
             'Library Tech Circulation Desk B', False),

            # 3. Lab Kits
            ('Arduino Mega 2560 Advanced Sensor Starter Kit',
             cat_map['Lab Kits'], dept_map['EE'], 'institution', None,
             'ARD-MEGA-KIT', 'Elegoo / Arduino', 'Embedded systems lab, robotics prototyping, sensor telemetry interfacing',
             'Tesla Hall - Microcontroller Lab Rm 102', False),

            ('Raspberry Pi 4 Model B (8GB) Embedded IoT Lab Kit',
             cat_map['Lab Kits'], dept_map['CS'], 'institution', None,
             'RPI4-8GB-KIT', 'Raspberry Pi Foundation', 'IoT gateways, edge machine learning, web server embedded experiments',
             'Turing Complex - IoT Research Lab Rm 310', False),

            # 4. Computers & Laptops
            ('Dell Latitude 5430 Core i7 Developer Laptop (Ubuntu 22.04 LTS)',
             cat_map['Computers & Laptops'], dept_map['CS'], 'institution', None,
             'DELL-LAT-5430', 'Dell Computer Corp', 'Short-term development loaner for hackathons, labs, and compile testing',
             'IT Support Services Counter - Ground Floor', False),

            ('High-End AI Workstation Node (Dual RTX 4090 24GB)',
             cat_map['Computers & Laptops'], dept_map['CS'], 'institution', None,
             'AI-NODE-4090', 'Supermicro Custom Rack', 'Deep learning model training, LLM fine-tuning, computer vision projects',
             'Turing Complex - Server Room 401', True),

            # 5. Project Components
            ('Rigol DS1054Z 50MHz 4-Channel Digital Storage Oscilloscope',
             cat_map['Project Components'], dept_map['EE'], 'institution', None,
             'RIGOL-DS1054Z', 'Rigol Technologies', 'Circuit signal debugging, waveform capture, analog/digital testing',
             'Tesla Hall - Measurement & Instrumentation Lab Rm 204', True),

            ('Spartan-7 FPGA Development Board (Xilinx)',
             cat_map['Project Components'], dept_map['EE'], 'institution', None,
             'SPARTAN-7-DIG', 'Digilent Inc', 'Verilog/VHDL hardware synthesis, digital circuit verification',
             'Tesla Hall - VLSI Design Center Rm 208', True),

            # 6. Study Rooms
            ('Group Collaboration Room 301 (Whiteboard & 65" 4K Display)',
             cat_map['Study Rooms'], dept_map['LIB'], 'institution', None,
             'ROOM-301-COL', 'Library Facilities', 'Team design project meetings, capstone preparation, presentation rehearsals',
             'Central Library - 3rd Floor East Wing', True),

            ('Quiet Individual Research Pod 12B',
             cat_map['Study Rooms'], dept_map['LIB'], 'institution', None,
             'ROOM-POD-12B', 'Library Facilities', 'Focused thesis research, individual study, undisturbed writing',
             'Central Library - 2nd Floor Quiet Zone', False),

            # 7. Student Peer Listings (lender: Priya Patel)
            ('Signals and Systems (Alan V. Oppenheim - 2nd Edition)',
             cat_map['Textbooks'], dept_map['EE'], 'student', user_map['lender@criss.edu'],
             '978-0138147570', 'Alan V. Oppenheim', 'Continuous and discrete-time signals, Fourier analysis, Z-transform',
             'Student Sharing - Peer Handover', False),

            ('Breadboard & 7400-Series TTL Logic Gate IC Kit',
             cat_map['Project Components'], dept_map['EE'], 'student', user_map['lender@criss.edu'],
             'PEER-TTL-7400', 'Texas Instruments / DIY', 'Digital logic labs, combinational circuits, flip-flop breadboard experiments',
             'Student Sharing - Peer Handover', False)
        ]

        cursor.executemany(
            """INSERT INTO resources 
               (title, category_id, department_id, owner_type, owner_user_id, isbn_or_identifier, 
                model_or_author, purpose, location, requires_approval)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
            resources_data
        )
        conn.commit()

        cursor.execute("SELECT resource_id, title FROM resources;")
        res_map = {row['title']: row['resource_id'] for row in cursor.fetchall()}
        print(f"Inserted {len(res_map)} master resources.")

        # ---------------------------------------------------------------------
        # 5. Resource Copies (Physical Inventory Units)
        # ---------------------------------------------------------------------
        copies_data = [
            # Silberschatz Textbook (3 copies: 1 available, 1 on_loan, 1 reserved)
            (res_map['Database System Concepts (Silberschatz, Korth, Sudarshan - 7th Ed)'], 'CRISS-BK-CS001', 'Good', 'available'),
            (res_map['Database System Concepts (Silberschatz, Korth, Sudarshan - 7th Ed)'], 'CRISS-BK-CS002', 'Good', 'on_loan'),
            (res_map['Database System Concepts (Silberschatz, Korth, Sudarshan - 7th Ed)'], 'CRISS-BK-CS003', 'Fair', 'reserved'),

            # CLRS Algorithms (2 copies: 1 available, 1 on_loan)
            (res_map['Introduction to Algorithms (CLRS - 4th Edition)'], 'CRISS-BK-CS010', 'New', 'available'),
            (res_map['Introduction to Algorithms (CLRS - 4th Edition)'], 'CRISS-BK-CS011', 'Good', 'on_loan'),

            # Modern OS (2 copies: both available)
            (res_map['Modern Operating Systems (Andrew S. Tanenbaum - 4th Ed)'], 'CRISS-BK-CS020', 'Good', 'available'),
            (res_map['Modern Operating Systems (Andrew S. Tanenbaum - 4th Ed)'], 'CRISS-BK-CS021', 'Fair', 'available'),

            # Casio fx-991CW (4 copies: 2 available, 1 on_loan, 1 maintenance)
            (res_map['Casio fx-991CW ClassWiz Advanced Scientific Calculator'], 'CRISS-CALC-CW01', 'Good', 'available'),
            (res_map['Casio fx-991CW ClassWiz Advanced Scientific Calculator'], 'CRISS-CALC-CW02', 'Good', 'available'),
            (res_map['Casio fx-991CW ClassWiz Advanced Scientific Calculator'], 'CRISS-CALC-CW03', 'Fair', 'on_loan'),
            (res_map['Casio fx-991CW ClassWiz Advanced Scientific Calculator'], 'CRISS-CALC-CW04', 'Needs Maintenance', 'maintenance'),

            # TI-84 Plus (2 copies: 1 available, 1 reserved)
            (res_map['Texas Instruments TI-84 Plus CE Color Graphing Calculator'], 'CRISS-CALC-TI01', 'Good', 'available'),
            (res_map['Texas Instruments TI-84 Plus CE Color Graphing Calculator'], 'CRISS-CALC-TI02', 'New', 'reserved'),

            # Arduino Mega Kit (3 copies: 1 available, 1 on_loan, 1 available)
            (res_map['Arduino Mega 2560 Advanced Sensor Starter Kit'], 'CRISS-KIT-ARD01', 'Good', 'available'),
            (res_map['Arduino Mega 2560 Advanced Sensor Starter Kit'], 'CRISS-KIT-ARD02', 'Good', 'on_loan'),
            (res_map['Arduino Mega 2560 Advanced Sensor Starter Kit'], 'CRISS-KIT-ARD03', 'Fair', 'available'),

            # Raspberry Pi 4 Kit (2 copies: 1 available, 1 on_loan)
            (res_map['Raspberry Pi 4 Model B (8GB) Embedded IoT Lab Kit'], 'CRISS-KIT-RPI01', 'Good', 'available'),
            (res_map['Raspberry Pi 4 Model B (8GB) Embedded IoT Lab Kit'], 'CRISS-KIT-RPI02', 'Fair', 'on_loan'),

            # Dell Laptop (2 copies: 1 available, 1 on_loan)
            (res_map['Dell Latitude 5430 Core i7 Developer Laptop (Ubuntu 22.04 LTS)'], 'CRISS-LAP-DL01', 'Good', 'available'),
            (res_map['Dell Latitude 5430 Core i7 Developer Laptop (Ubuntu 22.04 LTS)'], 'CRISS-LAP-DL02', 'Fair', 'on_loan'),

            # AI Workstation Node (1 copy: reserved)
            (res_map['High-End AI Workstation Node (Dual RTX 4090 24GB)'], 'CRISS-SRV-AI01', 'New', 'reserved'),

            # Rigol Oscilloscope (2 copies: 1 available, 1 maintenance)
            (res_map['Rigol DS1054Z 50MHz 4-Channel Digital Storage Oscilloscope'], 'CRISS-EQ-OSC01', 'Good', 'available'),
            (res_map['Rigol DS1054Z 50MHz 4-Channel Digital Storage Oscilloscope'], 'CRISS-EQ-OSC02', 'Needs Maintenance', 'maintenance'),

            # Spartan-7 FPGA (2 copies: both available)
            (res_map['Spartan-7 FPGA Development Board (Xilinx)'], 'CRISS-EQ-FPGA1', 'Good', 'available'),
            (res_map['Spartan-7 FPGA Development Board (Xilinx)'], 'CRISS-EQ-FPGA2', 'New', 'available'),

            # Study Rooms
            (res_map['Group Collaboration Room 301 (Whiteboard & 65" 4K Display)'], 'CRISS-RM-301', 'Good', 'available'),
            (res_map['Quiet Individual Research Pod 12B'], 'CRISS-RM-12B', 'Good', 'available')
        ]

        cursor.executemany(
            """INSERT INTO resource_copies (resource_id, barcode, condition_grade, status)
               VALUES (%s, %s, %s, %s);""",
            copies_data
        )
        conn.commit()

        cursor.execute("SELECT copy_id, barcode FROM resource_copies;")
        copy_map = {row['barcode']: row['copy_id'] for row in cursor.fetchall()}
        print(f"Inserted {len(copy_map)} physical inventory copies.")

        # ---------------------------------------------------------------------
        # 6. Student Listings (P2P Resource Sharing)
        # ---------------------------------------------------------------------
        today = datetime.now().date()
        listings_data = [
            (
                res_map['Signals and Systems (Alan V. Oppenheim - 2nd Edition)'],
                user_map['lender@criss.edu'],
                'Good condition, clean pages, no pen markings, includes formula bookmark.',
                'Pickup at Central Library Ground Floor Student Lounge between 3:00 PM and 5:00 PM.',
                'available',
                today - timedelta(days=2),
                today + timedelta(days=45)
            ),
            (
                res_map['Breadboard & 7400-Series TTL Logic Gate IC Kit'],
                user_map['lender@criss.edu'],
                'Complete kit with 7400, 7402, 7404, 7408, 7432, 7486 ICs, jumper wires, and LEDs.',
                'Pickup at Tesla Engineering Hall Foyer or cafeteria lobby after 4:00 PM.',
                'available',
                today - timedelta(days=5),
                today + timedelta(days=30)
            )
        ]
        cursor.executemany(
            """INSERT INTO student_listings 
               (resource_id, lender_user_id, condition_desc, pickup_instructions, 
                listing_status, available_from, available_until)
               VALUES (%s, %s, %s, %s, %s, %s, %s);""",
            listings_data
        )
        conn.commit()

        cursor.execute("SELECT listing_id, resource_id FROM student_listings;")
        listing_map = {row['resource_id']: row['listing_id'] for row in cursor.fetchall()}
        print(f"Inserted {len(listing_map)} student peer listings.")

        # ---------------------------------------------------------------------
        # 7. Reservations
        # ---------------------------------------------------------------------
        now = datetime.now()
        reservations_data = [
            # 1. Aarav Sharma reserved Silberschatz copy 3 for tomorrow
            (
                res_map['Database System Concepts (Silberschatz, Korth, Sudarshan - 7th Ed)'],
                copy_map['CRISS-BK-CS003'],
                user_map['student@criss.edu'],
                now + timedelta(days=1),
                now + timedelta(days=4),
                'confirmed',
                user_map['admin@criss.edu'],
                'Preparing for upcoming Relational Algebra and SQL midterm exam.'
            ),
            # 2. Rohit Verma reserved TI-84 Plus
            (
                res_map['Texas Instruments TI-84 Plus CE Color Graphing Calculator'],
                copy_map['CRISS-CALC-TI02'],
                user_map['rohit@criss.edu'],
                now + timedelta(days=2),
                now + timedelta(days=5),
                'confirmed',
                user_map['admin@criss.edu'],
                'Numerical methods assignment simulations.'
            ),
            # 3. Prof. Sunita Sharma reserved AI Workstation Node (pending approval/approved)
            (
                res_map['High-End AI Workstation Node (Dual RTX 4090 24GB)'],
                copy_map['CRISS-SRV-AI01'],
                user_map['sharma.fac@criss.edu'],
                now + timedelta(hours=3),
                now + timedelta(days=2),
                'confirmed',
                user_map['admin@criss.edu'],
                'Transformer fine-tuning for natural language research project.'
            ),
            # 4. Neha Gupta reserved Group Study Room 301 (Pending approval)
            (
                res_map['Group Collaboration Room 301 (Whiteboard & 65" 4K Display)'],
                copy_map['CRISS-RM-301'],
                user_map['neha@criss.edu'],
                now + timedelta(days=3, hours=10),
                now + timedelta(days=3, hours=14),
                'pending_approval',
                None,
                'DBMS team project group discussion and schema normalization review.'
            ),
            # 5. Past fulfilled reservation by Aarav
            (
                res_map['Casio fx-991CW ClassWiz Advanced Scientific Calculator'],
                copy_map['CRISS-CALC-CW03'],
                user_map['student@criss.edu'],
                now - timedelta(days=10),
                now - timedelta(days=3),
                'fulfilled',
                user_map['admin@criss.edu'],
                'Completed calculus practice test.'
            )
        ]

        cursor.executemany(
            """INSERT INTO reservations 
               (resource_id, copy_id, user_id, start_datetime, end_datetime, status, approval_admin_id, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s);""",
            reservations_data
        )
        conn.commit()
        print("Inserted 5 initial reservations.")

        # ---------------------------------------------------------------------
        # 8. Loans (Active, Returned, and Overdue)
        # Note: Triggers automatically update copy statuses upon insert/update.
        # We will temporarily disable triggers or update properly.
        # ---------------------------------------------------------------------
        loans_data = [
            # 1. Active loan: Aarav has Silberschatz copy 2 (due in 5 days)
            (
                None, copy_map['CRISS-BK-CS002'], None,
                user_map['student@criss.edu'], user_map['admin@criss.edu'],
                now - timedelta(days=2), now + timedelta(days=5), None,
                'active', 'Good', None, 'Standard library checkout for semester coursework'
            ),
            # 2. OVERDUE loan: Rohit has CLRS copy 11 (was due 3 days ago!)
            (
                None, copy_map['CRISS-BK-CS011'], None,
                user_map['rohit@criss.edu'], user_map['admin@criss.edu'],
                now - timedelta(days=10), now - timedelta(days=3), None,
                'overdue', 'Good', None, 'Automated overdue reminder sent to student'
            ),
            # 3. Active loan: Neha has Arduino Mega Kit copy 2 (due in 4 days)
            (
                None, copy_map['CRISS-KIT-ARD02'], None,
                user_map['neha@criss.edu'], user_map['admin@criss.edu'],
                now - timedelta(days=3), now + timedelta(days=4), None,
                'active', 'Good', None, 'Microcontroller lab project hardware checkout'
            ),
            # 4. Active loan: Vikram has Casio CW03 (due in 2 days)
            (
                None, copy_map['CRISS-CALC-CW03'], None,
                user_map['vikram@criss.edu'], user_map['admin@criss.edu'],
                now - timedelta(days=5), now + timedelta(days=2), None,
                'active', 'Fair', None, 'Applied physics lab calculation loan'
            ),
            # 5. Active loan: Aarav has Dell Laptop copy 2 (due tomorrow)
            (
                None, copy_map['CRISS-LAP-DL02'], None,
                user_map['student@criss.edu'], user_map['admin@criss.edu'],
                now - timedelta(days=2), now + timedelta(days=1), None,
                'active', 'Fair', None, 'Hackathon development machine loan'
            ),
            # 6. Returned loan: Priya previously borrowed Raspberry Pi (returned in good condition)
            (
                None, copy_map['CRISS-KIT-RPI01'], None,
                user_map['lender@criss.edu'], user_map['admin@criss.edu'],
                now - timedelta(days=20), now - timedelta(days=13), now - timedelta(days=14),
                'returned', 'Good', 'Good', 'Returned on time, all peripherals and micro-SD card accounted for'
            ),
            # 7. Returned loan: Aarav previously borrowed CLRS (returned on time)
            (
                None, copy_map['CRISS-BK-CS010'], None,
                user_map['student@criss.edu'], user_map['admin@criss.edu'],
                now - timedelta(days=30), now - timedelta(days=16), now - timedelta(days=17),
                'returned', 'New', 'New', 'Pristine condition'
            )
        ]

        cursor.executemany(
            """INSERT INTO loans 
               (reservation_id, copy_id, student_listing_id, borrower_id, issuer_id,
                checkout_date, due_date, return_date, status, checkout_condition, return_condition, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
            loans_data
        )
        conn.commit()
        print("Inserted 7 loans (including active, overdue, and returned history).")

        # ---------------------------------------------------------------------
        # 9. Resource Requests (Demand Tracking & Analytics)
        # Essential for Demand-Aware Resource Allocation Engine:
        # Unmet Demand Rate = (Unfulfilled / Total) * 100
        # ---------------------------------------------------------------------
        requests_data = [
            # High unmet demand in Computers & Laptops
            (user_map['student@criss.edu'], res_map['High-End AI Workstation Node (Dual RTX 4090 24GB)'], cat_map['Computers & Laptops'], 'Requested additional GPU time slot for graduate computer vision benchmark', 'unfulfilled', None, None),
            (user_map['neha@criss.edu'], res_map['High-End AI Workstation Node (Dual RTX 4090 24GB)'], cat_map['Computers & Laptops'], 'Need RTX 4090 node for deep learning final year capstone', 'unfulfilled', None, None),
            (user_map['rohit@criss.edu'], res_map['Dell Latitude 5430 Core i7 Developer Laptop (Ubuntu 22.04 LTS)'], cat_map['Computers & Laptops'], 'Urgent loaner laptop needed for CAD SolidWorks lab session', 'unfulfilled', None, None),
            (user_map['vikram@criss.edu'], res_map['Dell Latitude 5430 Core i7 Developer Laptop (Ubuntu 22.04 LTS)'], cat_map['Computers & Laptops'], 'Loaner laptop required for Python numerical methods testing', 'fulfilled', copy_map['CRISS-LAP-DL01'], now - timedelta(days=1)),

            # Unmet demand in Lab Kits
            (user_map['student@criss.edu'], res_map['Raspberry Pi 4 Model B (8GB) Embedded IoT Lab Kit'], cat_map['Lab Kits'], 'Raspberry Pi 4 needed for smart campus sensor node project', 'unfulfilled', None, None),
            (user_map['rohit@criss.edu'], res_map['Raspberry Pi 4 Model B (8GB) Embedded IoT Lab Kit'], cat_map['Lab Kits'], 'Embedded Linux coursework assignment kit required', 'unfulfilled', None, None),
            (user_map['neha@criss.edu'], res_map['Arduino Mega 2560 Advanced Sensor Starter Kit'], cat_map['Lab Kits'], 'Autonomous line-follower robot build kit', 'fulfilled', copy_map['CRISS-KIT-ARD03'], now - timedelta(days=4)),

            # Unmet demand in Calculators
            (user_map['vikram@criss.edu'], res_map['Texas Instruments TI-84 Plus CE Color Graphing Calculator'], cat_map['Scientific Calculators'], 'Graphing calculator needed for mid-term exam week', 'unfulfilled', None, None),
            (user_map['student@criss.edu'], res_map['Casio fx-991CW ClassWiz Advanced Scientific Calculator'], cat_map['Scientific Calculators'], 'ClassWiz calculator for matrix calculations lab', 'fulfilled', copy_map['CRISS-CALC-CW01'], now - timedelta(days=6)),

            # Unmet demand in Textbooks
            (user_map['rohit@criss.edu'], res_map['Introduction to Algorithms (CLRS - 4th Edition)'], cat_map['Textbooks'], 'Algorithms textbook needed for greedy algorithm problem sets', 'unfulfilled', None, None),
            (user_map['neha@criss.edu'], res_map['Database System Concepts (Silberschatz, Korth, Sudarshan - 7th Ed)'], cat_map['Textbooks'], 'Midterm prep textbook request', 'fulfilled', copy_map['CRISS-BK-CS001'], now - timedelta(days=7)),
            (user_map['vikram@criss.edu'], res_map['Modern Operating Systems (Andrew S. Tanenbaum - 4th Ed)'], cat_map['Textbooks'], 'OS concurrency and deadlock chapter study', 'fulfilled', copy_map['CRISS-BK-CS020'], now - timedelta(days=8))
        ]

        cursor.executemany(
            """INSERT INTO resource_requests 
               (user_id, resource_id, category_id, description, status, fulfilled_copy_id, fulfilled_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s);""",
            requests_data
        )
        conn.commit()
        print("Inserted 12 resource demand requests (both unfulfilled and fulfilled).")

        # ---------------------------------------------------------------------
        # 10. Maintenance Records
        # ---------------------------------------------------------------------
        maint_data = [
            (copy_map['CRISS-CALC-CW04'], user_map['admin@criss.edu'], 'Keypad button 7 and ENTER sticking intermittently during calculations.', 'in_repair', 15.00, now - timedelta(days=4), None, 'Dispatched to Casio certified service agent for keypad switch replacement.'),
            (copy_map['CRISS-EQ-OSC02'], user_map['faculty@criss.edu'], 'Channel 2 BNC input terminal loose and showing intermittent 50Hz ground noise.', 'reported', 0.00, now - timedelta(days=1), None, 'Awaiting diagnostic by electronics workshop technician.'),
            (copy_map['CRISS-LAP-DL01'], user_map['admin@criss.edu'], 'Battery cycle count high and degraded below 60% capacity.', 'repaired', 65.00, now - timedelta(days=25), now - timedelta(days=20), 'Original Dell 58Wh battery replaced; 100% capacity restored.')
        ]

        cursor.executemany(
            """INSERT INTO maintenance_records 
               (copy_id, reported_by, issue_description, status, cost, started_at, completed_at, repair_notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s);""",
            maint_data
        )
        conn.commit()
        print("Inserted 3 maintenance records.")

        # ---------------------------------------------------------------------
        # 11. Notifications
        # ---------------------------------------------------------------------
        notifications_data = [
            # Aarav Sharma notifications
            (user_map['student@criss.edu'], 'Upcoming Loan Due Date', 'Your loan for Dell Latitude 5430 (#CRISS-LAP-DL02) is due tomorrow by 5:00 PM. Please return or renew to avoid fines.', 'upcoming_due', False),
            (user_map['student@criss.edu'], 'Reservation Confirmed', 'Your reservation for Database System Concepts (#CRISS-BK-CS003) is confirmed for tomorrow.', 'reservation_approved', True),
            
            # Rohit Verma overdue notification
            (user_map['rohit@criss.edu'], 'URGENT: Overdue Resource Notice', 'Introduction to Algorithms (#CRISS-BK-CS011) was due 3 days ago. Please return immediately to the Library Circulation Desk.', 'overdue', False),
            
            # Neha Gupta notification
            (user_map['neha@criss.edu'], 'Study Room Reservation Pending', 'Your request for Group Collaboration Room 301 is pending faculty/admin coordinator approval.', 'general', False),
            
            # Vikram Singh request fulfilled
            (user_map['vikram@criss.edu'], 'Unmet Request Fulfilled!', 'A loaner laptop (Dell Latitude 5430) is now allocated and ready for pickup.', 'request_fulfilled', True)
        ]

        cursor.executemany(
            """INSERT INTO notifications (user_id, title, message, category, is_read)
               VALUES (%s, %s, %s, %s, %s);""",
            notifications_data
        )
        conn.commit()
        print("Inserted in-app notifications.")

        # ---------------------------------------------------------------------
        # 12. Usage Logs
        # ---------------------------------------------------------------------
        logs_data = [
            ('SYSTEM', 0, user_map['admin@criss.edu'], 'DATABASE_SEED', 'Initial system seed data loaded with realistic inventory and users.'),
            ('RESERVATION', 1, user_map['student@criss.edu'], 'RESERVE', 'Aarav Sharma reserved copy #CRISS-BK-CS003.'),
            ('LOAN', 2, user_map['rohit@criss.edu'], 'OVERDUE_FLAG', 'Rohit Verma loan flagged overdue by daily automated scan.')
        ]
        cursor.executemany(
            """INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
               VALUES (%s, %s, %s, %s, %s);""",
            logs_data
        )
        conn.commit()
        print("Inserted audit usage logs.")

        cursor.close()
        conn.close()
        print("\n========================================================")
        print("DATABASE SEED COMPLETED SUCCESSFULLY!")
        print("Demo Accounts Created:")
        print("  - Admin:   admin@criss.edu    / AdminPassword@123")
        print("  - Faculty: faculty@criss.edu  / FacultyPassword@123")
        print("  - Student: student@criss.edu  / StudentPassword@123")
        print("  - Lender:  lender@criss.edu   / StudentPassword@123")
        print("  - Student: rohit@criss.edu    / StudentPassword@123")
        print("========================================================\n")
        return True

    except Exception as e:
        print(f"Error during seeding: {e}", file=sys.stderr)
        raise

if __name__ == '__main__':
    seed_database()
