-- ============================================================
--  SISTEMA DE RECONOCIMIENTO FACIAL UNIVERSITARIO
--  Base de datos: MySQL 8.0+
--  Compatible con MySQL Workbench
-- ============================================================

CREATE DATABASE IF NOT EXISTS facial_recognition_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE facial_recognition_db;

-- ------------------------------------------------------------
-- TABLA: facultades
-- ------------------------------------------------------------
CREATE TABLE facultades (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(120) NOT NULL,
    codigo      VARCHAR(10)  NOT NULL UNIQUE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- TABLA: carreras
-- ------------------------------------------------------------
CREATE TABLE carreras (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    facultad_id   INT UNSIGNED NOT NULL,
    nombre        VARCHAR(120) NOT NULL,
    codigo        VARCHAR(10)  NOT NULL UNIQUE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_carrera_facultad FOREIGN KEY (facultad_id)
        REFERENCES facultades(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- TABLA: estudiantes
-- ------------------------------------------------------------
CREATE TABLE estudiantes (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    carrera_id      INT UNSIGNED NOT NULL,
    codigo          VARCHAR(20)  NOT NULL UNIQUE COMMENT 'Código de matrícula',
    nombres         VARCHAR(80)  NOT NULL,
    apellidos       VARCHAR(80)  NOT NULL,
    email           VARCHAR(120) NOT NULL UNIQUE,
    foto_path       VARCHAR(255) COMMENT 'Ruta relativa a la foto almacenada',
    activo          TINYINT(1) DEFAULT 1 COMMENT '1=activo, 0=inactivo/suspendido',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_estudiante_carrera FOREIGN KEY (carrera_id)
        REFERENCES carreras(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_codigo   (codigo),
    INDEX idx_activo   (activo)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- TABLA: embeddings_faciales
--   Guarda el vector de 128 floats como JSON array
--   (compatible MySQL 8 con tipo JSON)
-- ------------------------------------------------------------
CREATE TABLE embeddings_faciales (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    estudiante_id   INT UNSIGNED NOT NULL UNIQUE,
    embedding       JSON         NOT NULL COMMENT 'Vector de 128 dimensiones (float[])',
    modelo          VARCHAR(40)  NOT NULL DEFAULT 'face_recognition_v1',
    registrado_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    actualizado_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_embedding_estudiante FOREIGN KEY (estudiante_id)
        REFERENCES estudiantes(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- TABLA: accesos
--   Registro de cada intento de acceso (exitoso o fallido)
-- ------------------------------------------------------------
CREATE TABLE accesos (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    estudiante_id   INT UNSIGNED     COMMENT 'NULL si no fue identificado',
    resultado       ENUM('concedido','denegado','desconocido') NOT NULL,
    confianza       DECIMAL(5,4)     COMMENT 'Distancia coseno (0.0 = idéntico)',
    camara_id       SMALLINT UNSIGNED DEFAULT 0 COMMENT 'ID de la cámara/torniquete',
    captura_path    VARCHAR(255)     COMMENT 'Frame capturado para auditoría',
    accedido_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_acceso_estudiante FOREIGN KEY (estudiante_id)
        REFERENCES estudiantes(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_resultado     (resultado),
    INDEX idx_accedido_at   (accedido_at),
    INDEX idx_estudiante    (estudiante_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- TABLA: alertas
--   Intentos repetidos fallidos, posible spoofing, etc.
-- ------------------------------------------------------------
CREATE TABLE alertas (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    acceso_id   BIGINT UNSIGNED NOT NULL,
    tipo        ENUM('spoofing','multiples_intentos','cara_desconocida','sistema') NOT NULL,
    descripcion VARCHAR(255),
    resuelta    TINYINT(1) DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alerta_acceso FOREIGN KEY (acceso_id)
        REFERENCES accesos(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_resuelta (resuelta)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- TABLA: usuarios_admin
--   Operadores del sistema (no son estudiantes)
-- ------------------------------------------------------------
CREATE TABLE usuarios_admin (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(40)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL COMMENT 'bcrypt hash',
    nombre      VARCHAR(120) NOT NULL,
    rol         ENUM('superadmin','admin','vigilante') DEFAULT 'admin',
    activo      TINYINT(1) DEFAULT 1,
    ultimo_login DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
--  DATOS DE EJEMPLO
-- ============================================================

INSERT INTO facultades (nombre, codigo) VALUES
('Ingeniería y Tecnología',       'FIT'),
('Ciencias Empresariales',        'FCE'),
('Ciencias de la Salud',          'FCS'),
('Humanidades y Comunicación',    'FHC');

INSERT INTO carreras (facultad_id, nombre, codigo) VALUES
(1, 'Ingeniería de Sistemas',        'IS'),
(1, 'Ingeniería Industrial',         'II'),
(2, 'Administración de Empresas',    'AE'),
(2, 'Contabilidad',                  'CT'),
(3, 'Enfermería',                    'EN'),
(4, 'Comunicación Social',           'CS');

INSERT INTO estudiantes (carrera_id, codigo, nombres, apellidos, email) VALUES
(1, '2024-IS-001', 'Carlos Andrés',  'Quispe Mamani',    'cquispe@uni.edu.pe'),
(1, '2024-IS-002', 'Lucía Fernanda', 'Torres Vargas',    'ltorres@uni.edu.pe'),
(2, '2024-II-001', 'Diego Alberto',  'Flores Condori',   'dflores@uni.edu.pe'),
(3, '2023-AE-015', 'María José',     'Huanca Paredes',   'mhuanca@uni.edu.pe'),
(4, '2023-CT-008', 'Roberto Elías',  'Ccopa Sánchez',    'rccopa@uni.edu.pe');

INSERT INTO usuarios_admin (username, password_hash, nombre, rol) VALUES
('superadmin', '$2b$12$PLACEHOLDER_HASH_CAMBIAR', 'Administrador Principal', 'superadmin'),
('vigilante1', '$2b$12$PLACEHOLDER_HASH_CAMBIAR', 'Juan Seguridad',          'vigilante');

-- ============================================================
--  VISTAS ÚTILES
-- ============================================================

CREATE OR REPLACE VIEW v_estudiantes_completo AS
SELECT
    e.id,
    e.codigo,
    CONCAT(e.nombres, ' ', e.apellidos) AS nombre_completo,
    e.email,
    c.nombre  AS carrera,
    f.nombre  AS facultad,
    CASE WHEN ef.id IS NOT NULL THEN 'Sí' ELSE 'No' END AS tiene_embedding,
    e.activo,
    e.created_at
FROM estudiantes e
JOIN carreras  c ON c.id = e.carrera_id
JOIN facultades f ON f.id = c.facultad_id
LEFT JOIN embeddings_faciales ef ON ef.estudiante_id = e.id;

CREATE OR REPLACE VIEW v_accesos_hoy AS
SELECT
    a.id,
    a.accedido_at,
    CONCAT(e.nombres, ' ', e.apellidos) AS estudiante,
    e.codigo,
    a.resultado,
    ROUND(a.confianza, 4) AS confianza,
    a.camara_id
FROM accesos a
LEFT JOIN estudiantes e ON e.id = a.estudiante_id
WHERE DATE(a.accedido_at) = CURDATE()
ORDER BY a.accedido_at DESC;

CREATE OR REPLACE VIEW v_resumen_accesos AS
SELECT
    DATE(accedido_at)                          AS fecha,
    COUNT(*)                                   AS total,
    SUM(resultado = 'concedido')               AS concedidos,
    SUM(resultado = 'denegado')                AS denegados,
    SUM(resultado = 'desconocido')             AS desconocidos,
    ROUND(AVG(confianza), 4)                   AS confianza_promedio
FROM accesos
GROUP BY DATE(accedido_at)
ORDER BY fecha DESC;
