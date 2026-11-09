-- =====================================================================
-- Basis Data Sistem Manajemen Laundry (MySQL 8.0.16+)
-- 10 tabel: CUSTOMER, STAFF, SERVICE, PROMO, ORDERS, ORDER_DETAIL, PAYMENT
--           + tabel referensi PROMO_TYPE, ORDER_STATUS, PAYMENT_METHOD
-- Catatan: CHECK constraint baru ditegakkan mulai MySQL 8.0.16.
-- =====================================================================

DROP DATABASE IF EXISTS laundry_db;
CREATE DATABASE laundry_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE laundry_db;

-- ---------------------------------------------------------------------
-- 0. TABEL REFERENSI (lookup) - dibuat lebih dulu karena dirujuk FK
-- ---------------------------------------------------------------------
CREATE TABLE promo_type (
  promo_type       TINYINT UNSIGNED NOT NULL,
  promo_type_info  VARCHAR(100)     NOT NULL,
  CONSTRAINT pk_promo_type PRIMARY KEY (promo_type),
  CONSTRAINT uq_promo_type_info UNIQUE (promo_type_info)
) ENGINE=InnoDB;

CREATE TABLE order_status (
  order_status       TINYINT UNSIGNED NOT NULL,
  order_status_info  VARCHAR(100)     NOT NULL,
  CONSTRAINT pk_order_status PRIMARY KEY (order_status),
  CONSTRAINT uq_order_status_info UNIQUE (order_status_info)
) ENGINE=InnoDB;

CREATE TABLE payment_method (
  payment_method       TINYINT UNSIGNED NOT NULL,
  payment_method_info  VARCHAR(100)     NOT NULL,
  CONSTRAINT pk_payment_method PRIMARY KEY (payment_method),
  CONSTRAINT uq_payment_method_info UNIQUE (payment_method_info)
) ENGINE=InnoDB;

-- Kode angka dipakai di tabel utama; nama lengkap ada di kolom *_info
INSERT INTO promo_type VALUES (1, 'NOMINAL'), (2, 'PERCENT');
INSERT INTO order_status VALUES (1, 'PROCESS'), (2, 'FINISHED');
INSERT INTO payment_method VALUES (1, 'CASH'), (2, 'QRIS'), (3, 'TRANSFER');

-- ---------------------------------------------------------------------
-- 1. CUSTOMER
-- ---------------------------------------------------------------------
CREATE TABLE customer (
  cust_id             VARCHAR(10)   NOT NULL,
  cust_name           VARCHAR(100)  NOT NULL,
  cust_phone          VARCHAR(20)   NOT NULL,
  cust_point          INT UNSIGNED  NOT NULL DEFAULT 0,
  cust_point_expired_date  DATE     NULL,
  CONSTRAINT pk_customer PRIMARY KEY (cust_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. STAFF
-- ---------------------------------------------------------------------
CREATE TABLE staff (
  staff_id     VARCHAR(10)   NOT NULL,
  staff_name   VARCHAR(100)  NOT NULL,
  staff_phone  VARCHAR(20)   NOT NULL,
  CONSTRAINT pk_staff PRIMARY KEY (staff_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. SERVICE  (price = tarif terkini, boleh berubah)
-- ---------------------------------------------------------------------
CREATE TABLE service (
  service_id    VARCHAR(10)    NOT NULL,
  service_name  VARCHAR(100)   NOT NULL,
  variant       VARCHAR(50)    NOT NULL,
  price         DECIMAL(12,2)  NOT NULL,
  CONSTRAINT pk_service PRIMARY KEY (service_id),
  CONSTRAINT uq_service_name_variant UNIQUE (service_name, variant),
  CONSTRAINT ck_service_price CHECK (price >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. PROMO  (batas 100 untuk promo PERCENT dicek di aplikasi: CHECK tidak boleh
--           memakai kolom FK dengan ON UPDATE CASCADE di MySQL)
-- ---------------------------------------------------------------------
CREATE TABLE promo (
  promo_code       VARCHAR(20)              NOT NULL,
  promo_name       VARCHAR(100)             NOT NULL,
  promo_type       TINYINT UNSIGNED         NOT NULL,
  promo_value      DECIMAL(12,2)            NOT NULL,
  min_transaction  DECIMAL(12,2)            NOT NULL DEFAULT 0,
  max_discount     DECIMAL(12,2)            NULL,
  is_active        BOOLEAN                  NOT NULL DEFAULT TRUE,
  CONSTRAINT pk_promo PRIMARY KEY (promo_code),
  CONSTRAINT fk_promo_type FOREIGN KEY (promo_type)
    REFERENCES promo_type (promo_type) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT ck_promo_value CHECK (promo_value > 0),
  CONSTRAINT ck_promo_min CHECK (min_transaction >= 0),
  CONSTRAINT ck_promo_max CHECK (max_discount IS NULL OR max_discount >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. ORDERS  (ORDER adalah reserved word MySQL)
-- ---------------------------------------------------------------------
CREATE TABLE orders (
  order_id               VARCHAR(10)                NOT NULL,
  order_date             DATE                       NOT NULL,
  order_estimation_date  DATE                       NOT NULL,
  order_status           TINYINT UNSIGNED           NOT NULL DEFAULT 1,
  cust_id                VARCHAR(10)                NOT NULL,
  staff_id               VARCHAR(10)                NOT NULL,
  promo_code             VARCHAR(20)                NULL,
  promo_discount_applied DECIMAL(12,2)              NOT NULL DEFAULT 0,
  consument_notes        VARCHAR(255)               NULL,
  pickup_fee             DECIMAL(12,2)              NOT NULL DEFAULT 0,
  delivery_fee           DECIMAL(12,2)              NOT NULL DEFAULT 0,
  points_used            INT UNSIGNED               NOT NULL DEFAULT 0,
  points_earned          INT UNSIGNED               NOT NULL DEFAULT 0,
  total_price            DECIMAL(12,2)              NOT NULL DEFAULT 0,
  created_at             DATETIME                   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at             DATETIME                   NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                    ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_orders PRIMARY KEY (order_id),
  CONSTRAINT fk_orders_status FOREIGN KEY (order_status)
    REFERENCES order_status (order_status) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_orders_customer FOREIGN KEY (cust_id)
    REFERENCES customer (cust_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_orders_staff FOREIGN KEY (staff_id)
    REFERENCES staff (staff_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_orders_promo FOREIGN KEY (promo_code)
    REFERENCES promo (promo_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT ck_orders_dates CHECK (order_estimation_date >= order_date),
  CONSTRAINT ck_orders_fees CHECK (pickup_fee >= 0 AND delivery_fee >= 0),
  CONSTRAINT ck_orders_discount CHECK (promo_discount_applied >= 0),
  CONSTRAINT ck_orders_total CHECK (total_price >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. ORDER_DETAIL  (conjunction table ORDERS - SERVICE)
--    PK gabungan (order_id, detail_id): detail_id hanya unik di dalam satu order (D-1, D-2, ...)
--    unit_price = harga saat transaksi (snapshot, R7)
-- ---------------------------------------------------------------------
CREATE TABLE order_detail (
  detail_id   VARCHAR(10)    NOT NULL,
  order_id    VARCHAR(10)    NOT NULL,
  service_id  VARCHAR(10)    NOT NULL,
  qty         DECIMAL(6,2)   NOT NULL,
  unit_price  DECIMAL(12,2)  NOT NULL,
  notes       VARCHAR(255)   NULL,
  sub_price   DECIMAL(12,2)  NOT NULL,
  CONSTRAINT pk_order_detail PRIMARY KEY (order_id, detail_id),
  CONSTRAINT fk_detail_orders FOREIGN KEY (order_id)
    REFERENCES orders (order_id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_detail_service FOREIGN KEY (service_id)
    REFERENCES service (service_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT ck_detail_qty CHECK (qty > 0),
  CONSTRAINT ck_detail_price CHECK (unit_price >= 0),
  CONSTRAINT ck_detail_sub CHECK (sub_price = qty * unit_price)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. PAYMENT  (satu order boleh dibayar berkali-kali, R11)
--    PK gabungan (order_id, payment_id): payment_id hanya unik di dalam satu order (PA-1, PA-2, ...)
-- ---------------------------------------------------------------------
CREATE TABLE payment (
  payment_id       VARCHAR(10)                        NOT NULL,
  order_id         VARCHAR(10)                        NOT NULL,
  payment_date     DATE                               NOT NULL,
  payment_method   TINYINT UNSIGNED                   NOT NULL,
  amount_received  DECIMAL(12,2)                      NOT NULL,
  CONSTRAINT pk_payment PRIMARY KEY (order_id, payment_id),
  CONSTRAINT fk_payment_method FOREIGN KEY (payment_method)
    REFERENCES payment_method (payment_method) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_payment_orders FOREIGN KEY (order_id)
    REFERENCES orders (order_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT ck_payment_amount CHECK (amount_received > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- INDEX tambahan (FK sudah otomatis diindeks InnoDB; ini untuk query umum)
-- ---------------------------------------------------------------------
CREATE INDEX idx_customer_phone   ON customer (cust_phone);
-- CREATE INDEX idx_orders_status    ON orders (order_status);
CREATE INDEX idx_orders_date      ON orders (order_date);
CREATE INDEX idx_payment_date     ON payment (payment_date);

-- ---------------------------------------------------------------------
-- TRIGGER: status FINISHED (kode lewat tabel ORDER_STATUS) hanya boleh jika tagihan lunas (R12)
-- ---------------------------------------------------------------------
DELIMITER $$
CREATE TRIGGER trg_orders_finish_requires_paid
BEFORE UPDATE ON orders
FOR EACH ROW
BEGIN
  DECLARE v_paid DECIMAL(12,2);
  DECLARE v_finished TINYINT UNSIGNED;
  SELECT order_status INTO v_finished FROM order_status
    WHERE order_status_info = 'FINISHED';
  IF NEW.order_status = v_finished AND OLD.order_status <> v_finished THEN
    SELECT COALESCE(SUM(amount_received), 0) INTO v_paid
      FROM payment WHERE order_id = NEW.order_id;
    IF v_paid < NEW.total_price THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Order belum lunas, status tidak boleh FINISHED';
    END IF;
  END IF;
END$$
DELIMITER ;

-- ---------------------------------------------------------------------
-- EVENT: reset poin kedaluwarsa (setiap hari)
-- Masa berlaku poin 3 bulan, dihitung sejak tanggal daftar dan berulang:
-- cust_point_expired_date terisi saat daftar (tanggal daftar + 3 bulan).
-- Jika tanggal itu sudah lewat: poin direset 0 dan tanggal maju 3 bulan.
-- Angka 3 harus sama dengan POINT_VALIDITY_MONTHS di app/services/points.py.
-- Event berjalan jika event_scheduler = ON (tanpa itu, aplikasi tetap benar
-- karena saldo selalu dicek lagi saat order dibuat).
-- ---------------------------------------------------------------------
SET GLOBAL event_scheduler = ON;

CREATE EVENT ev_reset_expired_points
ON SCHEDULE EVERY 1 DAY
STARTS (TIMESTAMP(CURRENT_DATE) + INTERVAL 1 DAY + INTERVAL 5 MINUTE)
DO
  UPDATE customer
     SET cust_point = 0,
         cust_point_expired_date = DATE_ADD(cust_point_expired_date, INTERVAL 3 MONTH)
   WHERE cust_point_expired_date < CURRENT_DATE;

-- ---------------------------------------------------------------------
-- DATA DUMMY (sesuai Tahap 3)
-- Subtotal 21000 + 10500 = 31500; promo 10% = 3150; poin 1 = 1000
-- total = 31500 + 4000 - 3150 - 1000 = 31350; poin didapat = 3
-- ---------------------------------------------------------------------
INSERT INTO customer VALUES ('CU-1', 'Restu', '123456789', 5, '2026-11-30');
INSERT INTO staff    VALUES ('ST-1', 'Jeysen', '123456790');
INSERT INTO service  VALUES ('SE-1', 'Cuci Komplit', '3 hari', 6000),
                            ('SE-2', 'Setrika Saja', '1 hari', 5000);
INSERT INTO promo    VALUES ('AWALNOV26', 'Promo Awal Bulan November 2026', 2, 10, 0, 10000, TRUE);

INSERT INTO orders (order_id, order_date, order_estimation_date, order_status, cust_id, staff_id,
                    promo_code, promo_discount_applied, consument_notes, pickup_fee,
                    delivery_fee, points_used, points_earned, total_price)
VALUES ('O-1', '2026-11-01', '2026-11-04', 1, 'CU-1', 'ST-1',
        'AWALNOV26', 3150, NULL, 4000, 0, 1, 3, 31350);

INSERT INTO order_detail VALUES ('D-1', 'O-1', 'SE-1', 3.5, 6000, NULL, 21000),
                                ('D-2', 'O-1', 'SE-2', 2.1, 5000, NULL, 10500);

INSERT INTO payment VALUES ('PA-1', 'O-1', '2026-11-01', 1, 20000);