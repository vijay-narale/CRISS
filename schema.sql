-- ============================================================================
-- CAMPUS RESOURCE INTELLIGENCE & SHARING SYSTEM (CRISS)
-- Relational Database Schema (MySQL 8.0) - Normalized to 3NF
-- ============================================================================

DROP DATABASE IF EXISTS criss_db;
CREATE DATABASE criss_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE criss_db;

-- ----------------------------------------------------------------------------
-- 1. DEPARTMENTS
-- Academic departments managing or housing institutional assets.
-- ----------------------------------------------------------------------------
CREATE TABLE departments (
    department_id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(15) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    building VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 2. USERS
-- Role-based accounts: student, faculty, admin.
-- Normalization note: Private contact data (phone) kept securely on user record,
-- never exposed to peer borrowers in student resource listings.
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('student', 'faculty', 'admin') NOT NULL DEFAULT 'student',
    department_id INT NULL,
    phone VARCHAR(20) NULL,
    student_faculty_id VARCHAR(50) NOT NULL UNIQUE,
    status ENUM('active', 'suspended') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_department FOREIGN KEY (department_id) 
        REFERENCES departments(department_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 3. CATEGORIES
-- Resource taxonomy: Textbooks, Calculators, Lab Kits, Computers, Components, Study Rooms
-- ----------------------------------------------------------------------------
CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(60) NOT NULL UNIQUE,
    description TEXT NULL,
    max_borrow_days INT NOT NULL DEFAULT 7,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 4. RESOURCES (Master Catalog)
-- Core metadata for abstract assets (institution-owned or student peer items).
-- ----------------------------------------------------------------------------
CREATE TABLE resources (
    resource_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    category_id INT NOT NULL,
    department_id INT NULL,
    owner_type ENUM('institution', 'student') NOT NULL DEFAULT 'institution',
    owner_user_id INT NULL,
    isbn_or_identifier VARCHAR(100) NULL,
    model_or_author VARCHAR(150) NULL,
    purpose VARCHAR(255) NULL,
    location VARCHAR(150) NOT NULL,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    image_url VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_resources_category FOREIGN KEY (category_id) 
        REFERENCES categories(category_id) ON DELETE RESTRICT,
    CONSTRAINT fk_resources_department FOREIGN KEY (department_id) 
        REFERENCES departments(department_id) ON DELETE SET NULL,
    CONSTRAINT fk_resources_owner FOREIGN KEY (owner_user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_res_cat_dept (category_id, department_id),
    INDEX idx_res_title (title),
    INDEX idx_res_owner_type (owner_type)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 5. RESOURCE COPIES (Physical Inventory)
-- Physical units of institution-owned catalog items.
-- ----------------------------------------------------------------------------
CREATE TABLE resource_copies (
    copy_id INT AUTO_INCREMENT PRIMARY KEY,
    resource_id INT NOT NULL,
    barcode VARCHAR(60) NOT NULL UNIQUE,
    condition_grade ENUM('New', 'Good', 'Fair', 'Needs Maintenance') NOT NULL DEFAULT 'Good',
    status ENUM('available', 'reserved', 'on_loan', 'maintenance', 'retired') NOT NULL DEFAULT 'available',
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_copies_resource FOREIGN KEY (resource_id) 
        REFERENCES resources(resource_id) ON DELETE CASCADE,
    INDEX idx_copies_status (status),
    INDEX idx_copies_resource (resource_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 6. STUDENT LISTINGS (Peer-to-Peer Resource Sharing)
-- Student-owned items offered for lending.
-- Privacy rule: Private phone/email is NOT in this table; safe pickup location only.
-- ----------------------------------------------------------------------------
CREATE TABLE student_listings (
    listing_id INT AUTO_INCREMENT PRIMARY KEY,
    resource_id INT NOT NULL UNIQUE,
    lender_user_id INT NOT NULL,
    condition_desc VARCHAR(255) NOT NULL,
    pickup_instructions VARCHAR(255) NOT NULL,
    listing_status ENUM('available', 'lent', 'paused', 'withdrawn') NOT NULL DEFAULT 'available',
    available_from DATE NOT NULL,
    available_until DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_listings_resource FOREIGN KEY (resource_id) 
        REFERENCES resources(resource_id) ON DELETE CASCADE,
    CONSTRAINT fk_listings_lender FOREIGN KEY (lender_user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_listing_status (listing_status),
    INDEX idx_listing_dates (available_from, available_until)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 7. RESERVATIONS
-- Time-bounded holds on resources or specific copies.
-- ----------------------------------------------------------------------------
CREATE TABLE reservations (
    reservation_id INT AUTO_INCREMENT PRIMARY KEY,
    resource_id INT NOT NULL,
    copy_id INT NULL,
    user_id INT NOT NULL,
    start_datetime DATETIME NOT NULL,
    end_datetime DATETIME NOT NULL,
    status ENUM('pending_approval', 'confirmed', 'fulfilled', 'cancelled', 'expired', 'rejected') NOT NULL DEFAULT 'confirmed',
    approval_admin_id INT NULL,
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reservations_resource FOREIGN KEY (resource_id) 
        REFERENCES resources(resource_id) ON DELETE CASCADE,
    CONSTRAINT fk_reservations_copy FOREIGN KEY (copy_id) 
        REFERENCES resource_copies(copy_id) ON DELETE SET NULL,
    CONSTRAINT fk_reservations_user FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_reservations_admin FOREIGN KEY (approval_admin_id) 
        REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_resv_timerange (start_datetime, end_datetime),
    INDEX idx_resv_status (status),
    INDEX idx_resv_user (user_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 8. LOANS
-- Active and historical borrowing checkouts.
-- ----------------------------------------------------------------------------
CREATE TABLE loans (
    loan_id INT AUTO_INCREMENT PRIMARY KEY,
    reservation_id INT NULL,
    copy_id INT NULL,
    student_listing_id INT NULL,
    borrower_id INT NOT NULL,
    issuer_id INT NULL,
    checkout_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_date DATETIME NOT NULL,
    return_date DATETIME NULL,
    status ENUM('active', 'returned', 'overdue', 'lost') NOT NULL DEFAULT 'active',
    checkout_condition VARCHAR(100) NOT NULL DEFAULT 'Good',
    return_condition VARCHAR(100) NULL,
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_loans_reservation FOREIGN KEY (reservation_id) 
        REFERENCES reservations(reservation_id) ON DELETE SET NULL,
    CONSTRAINT fk_loans_copy FOREIGN KEY (copy_id) 
        REFERENCES resource_copies(copy_id) ON DELETE SET NULL,
    CONSTRAINT fk_loans_listing FOREIGN KEY (student_listing_id) 
        REFERENCES student_listings(listing_id) ON DELETE SET NULL,
    CONSTRAINT fk_loans_borrower FOREIGN KEY (borrower_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_loans_issuer FOREIGN KEY (issuer_id) 
        REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_loans_status (status),
    INDEX idx_loans_borrower (borrower_id),
    INDEX idx_loans_due_date (due_date)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 9. RESOURCE REQUESTS (Demand Tracking)
-- Captures unmet demand when inventory is unavailable; fulfills later.
-- ----------------------------------------------------------------------------
CREATE TABLE resource_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    resource_id INT NULL,
    category_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    status ENUM('unfulfilled', 'fulfilled', 'cancelled', 'expired') NOT NULL DEFAULT 'unfulfilled',
    fulfilled_copy_id INT NULL,
    fulfilled_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_requests_user FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_requests_resource FOREIGN KEY (resource_id) 
        REFERENCES resources(resource_id) ON DELETE SET NULL,
    CONSTRAINT fk_requests_category FOREIGN KEY (category_id) 
        REFERENCES categories(category_id) ON DELETE RESTRICT,
    CONSTRAINT fk_requests_copy FOREIGN KEY (fulfilled_copy_id) 
        REFERENCES resource_copies(copy_id) ON DELETE SET NULL,
    INDEX idx_requests_status (status),
    INDEX idx_requests_cat (category_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 10. MAINTENANCE RECORDS
-- Tracking repair workflows, inspection, costs, and historical maintenance.
-- ----------------------------------------------------------------------------
CREATE TABLE maintenance_records (
    maintenance_id INT AUTO_INCREMENT PRIMARY KEY,
    copy_id INT NOT NULL,
    reported_by INT NOT NULL,
    issue_description TEXT NOT NULL,
    status ENUM('reported', 'in_repair', 'repaired', 'decommissioned') NOT NULL DEFAULT 'reported',
    cost DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    repair_notes TEXT NULL,
    CONSTRAINT fk_maint_copy FOREIGN KEY (copy_id) 
        REFERENCES resource_copies(copy_id) ON DELETE CASCADE,
    CONSTRAINT fk_maint_reporter FOREIGN KEY (reported_by) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_maint_status (status)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 11. USAGE LOGS (Audit & Compliance)
-- ----------------------------------------------------------------------------
CREATE TABLE usage_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INT NOT NULL,
    user_id INT NULL,
    action VARCHAR(60) NOT NULL,
    details TEXT NULL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_logs_user FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_logs_entity (entity_type, entity_id),
    INDEX idx_logs_action (action)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 12. NOTIFICATIONS
-- In-app notifications for reservations, due dates, overdue items, fulfillments.
-- ----------------------------------------------------------------------------
CREATE TABLE notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    category ENUM('reservation_approved', 'upcoming_due', 'overdue', 'request_fulfilled', 'general') NOT NULL DEFAULT 'general',
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_notif_unread (user_id, is_read)
) ENGINE=InnoDB;

-- ============================================================================
-- DATABASE VIEWS (At least 2 useful views)
-- ============================================================================

-- VIEW 1: Resource Inventory & Utilization Summary
-- Provides real-time copy totals, available count, active loans, and reservation counts.
CREATE OR REPLACE VIEW view_resource_inventory_summary AS
SELECT 
    r.resource_id,
    r.title,
    c.name AS category_name,
    d.code AS department_code,
    d.name AS department_name,
    r.location,
    r.owner_type,
    COUNT(rc.copy_id) AS total_copies,
    SUM(CASE WHEN rc.status = 'available' THEN 1 ELSE 0 END) AS available_copies,
    SUM(CASE WHEN rc.status = 'on_loan' THEN 1 ELSE 0 END) AS on_loan_copies,
    SUM(CASE WHEN rc.status = 'reserved' THEN 1 ELSE 0 END) AS reserved_copies,
    SUM(CASE WHEN rc.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance_copies,
    (
        SELECT COUNT(*) 
        FROM reservations res 
        WHERE res.resource_id = r.resource_id 
          AND res.status IN ('confirmed', 'pending_approval')
          AND res.end_datetime >= NOW()
    ) AS active_reservations
FROM resources r
INNER JOIN categories c ON r.category_id = c.category_id
LEFT JOIN departments d ON r.department_id = d.department_id
LEFT JOIN resource_copies rc ON r.resource_id = rc.resource_id
GROUP BY r.resource_id, r.title, c.name, d.code, d.name, r.location, r.owner_type;

-- VIEW 2: Unmet Demand Analytics View
-- Aggregates total requests vs unfulfilled requests and calculates exact unmet demand rate.
CREATE OR REPLACE VIEW view_unmet_demand_analytics AS
SELECT 
    c.category_id,
    c.name AS category_name,
    COUNT(req.request_id) AS total_requests,
    SUM(CASE WHEN req.status = 'unfulfilled' THEN 1 ELSE 0 END) AS unfulfilled_requests,
    SUM(CASE WHEN req.status = 'fulfilled' THEN 1 ELSE 0 END) AS fulfilled_requests,
    ROUND(
        (SUM(CASE WHEN req.status = 'unfulfilled' THEN 1 ELSE 0 END) * 100.0) / 
        NULLIF(COUNT(req.request_id), 0), 2
    ) AS unmet_demand_rate_pct
FROM categories c
LEFT JOIN resource_requests req ON c.category_id = req.category_id
GROUP BY c.category_id, c.name;

-- ============================================================================
-- STORED PROCEDURE
-- sp_reserve_resource: Implements transactional reservation with conflict check
-- and row locking (FOR UPDATE) to prevent race conditions & double-booking.
-- ============================================================================
DELIMITER //

CREATE PROCEDURE sp_reserve_resource(
    IN p_resource_id INT,
    IN p_user_id INT,
    IN p_start DATETIME,
    IN p_end DATETIME,
    IN p_notes TEXT,
    OUT p_reservation_id INT,
    OUT p_status_code VARCHAR(20),
    OUT p_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_copy_id INT DEFAULT NULL;
    DECLARE v_requires_approval BOOLEAN DEFAULT FALSE;
    DECLARE v_reservation_status VARCHAR(25) DEFAULT 'confirmed';
    DECLARE v_conflict_count INT DEFAULT 0;

    -- Standard error handler triggers automatic rollback
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_reservation_id = NULL;
        SET p_status_code = 'SQL_ERROR';
        SET p_message = 'Internal database error during reservation execution.';
    END;

    START TRANSACTION;

    -- 1. Check if resource requires faculty/admin approval
    SELECT requires_approval INTO v_requires_approval
    FROM resources
    WHERE resource_id = p_resource_id;

    IF v_requires_approval IS NULL THEN
        ROLLBACK;
        SET p_reservation_id = NULL;
        SET p_status_code = 'NOT_FOUND';
        SET p_message = 'Specified resource does not exist.';
        LEAVE proc_label;
    END IF;

    IF v_requires_approval = TRUE THEN
        SET v_reservation_status = 'pending_approval';
    ELSE
        SET v_reservation_status = 'confirmed';
    END IF;

    -- 2. Find an available copy that is NOT booked during the requested time window
    -- Use FOR UPDATE to lock candidates and prevent concurrent double booking
    SELECT rc.copy_id INTO v_copy_id
    FROM resource_copies rc
    WHERE rc.resource_id = p_resource_id
      AND rc.status IN ('available', 'reserved')
      AND rc.copy_id NOT IN (
          SELECT res.copy_id 
          FROM reservations res
          WHERE res.resource_id = p_resource_id
            AND res.copy_id IS NOT NULL
            AND res.status IN ('confirmed', 'pending_approval')
            AND NOT (res.end_datetime <= p_start OR res.start_datetime >= p_end)
      )
    ORDER BY rc.copy_id ASC
    LIMIT 1
    FOR UPDATE;

    -- 3. If no copy is available, verify if there are any copies at all
    IF v_copy_id IS NULL THEN
        ROLLBACK;
        SET p_reservation_id = NULL;
        SET p_status_code = 'UNAVAILABLE';
        SET p_message = 'No available inventory copy found for the requested time period.';
        LEAVE proc_label;
    END IF;

    -- 4. Create the reservation record
    INSERT INTO reservations (resource_id, copy_id, user_id, start_datetime, end_datetime, status, notes)
    VALUES (p_resource_id, v_copy_id, p_user_id, p_start, p_end, v_reservation_status, p_notes);

    SET p_reservation_id = LAST_INSERT_ID();

    -- 5. Mark copy status as 'reserved' if starting right away
    IF p_start <= NOW() AND v_reservation_status = 'confirmed' THEN
        UPDATE resource_copies 
        SET status = 'reserved' 
        WHERE copy_id = v_copy_id;
    END IF;

    -- 6. Insert audit log
    INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
    VALUES ('RESERVATION', p_reservation_id, p_user_id, 'RESERVE', 
            CONCAT('Reserved copy #', v_copy_id, ' from ', p_start, ' to ', p_end));

    COMMIT;
    SET p_status_code = 'SUCCESS';
    SET p_message = 'Resource reserved successfully.';
END //

DELIMITER ;

-- ============================================================================
-- DATABASE TRIGGERS (At least 2 meaningful triggers)
-- ============================================================================
DELIMITER //

-- TRIGGER 1: When a new active loan is created, mark copy as 'on_loan'
CREATE TRIGGER trg_after_loan_insert_update_copy
AFTER INSERT ON loans
FOR EACH ROW
BEGIN
    IF NEW.copy_id IS NOT NULL AND NEW.status = 'active' THEN
        UPDATE resource_copies
        SET status = 'on_loan'
        WHERE copy_id = NEW.copy_id;

        INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
        VALUES ('LOAN', NEW.loan_id, NEW.borrower_id, 'CHECKOUT', 
                CONCAT('Copy barcode on loan until ', NEW.due_date));
    END IF;
END //

-- TRIGGER 2: When a loan is marked 'returned', mark copy as 'available'
-- (unless marked Needs Maintenance)
CREATE TRIGGER trg_after_loan_return_update_copy
AFTER UPDATE ON loans
FOR EACH ROW
BEGIN
    IF OLD.status != 'returned' AND NEW.status = 'returned' AND NEW.copy_id IS NOT NULL THEN
        UPDATE resource_copies
        SET status = 'available'
        WHERE copy_id = NEW.copy_id 
          AND status != 'maintenance' 
          AND status != 'retired';

        INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
        VALUES ('LOAN', NEW.loan_id, NEW.borrower_id, 'RETURN', 
                CONCAT('Returned on ', NOW(), ' condition: ', IFNULL(NEW.return_condition, 'Standard')));
    END IF;
END //

DELIMITER ;
