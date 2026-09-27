-- ===========================================================================
--  CRM Verificentro — esquema de base de datos
--  MySQL 8.0 / MariaDB 10.6+   ·   InnoDB   ·   utf8mb4
-- ===========================================================================
--  Decisiones de diseño que conviene no perder de vista:
--
--  1. El identificador estable de un vehículo es el NIV, no la placa.
--     Las placas cambian (y al cambiar puede cambiar el periodo que le toca),
--     así que la placa vigente vive en `vehiculos` y su historia en
--     `vehiculo_placas`.
--
--  2. `ultimo_digito` es columna generada: se calcula del último carácter
--     NUMÉRICO de la placa. Las placas de Veracruz terminan en letra.
--     Si la placa no trae ningún número, queda en NULL —nunca en 0— para que
--     el registro salte a la vista en lugar de caer callado en el grupo 9-0.
--
--  3. Los recordatorios se escriben ANTES de enviarse y llevan una clave de
--     idempotencia única, para que si el job corre dos veces nadie reciba el
--     mensaje duplicado.
--
--  4. En `citas`, el campo `cupo` es NULL cuando la cita se cancela. Como
--     MySQL permite varios NULL en un índice único, cancelar libera el lugar
--     automáticamente y el índice sigue impidiendo la sobreventa.
-- ===========================================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS verificentro
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE verificentro;


-- ---------------------------------------------------------------------------
-- 1. Personal y perfiles
-- ---------------------------------------------------------------------------

CREATE TABLE empleados (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre            VARCHAR(160)    NOT NULL,
  correo            VARCHAR(160)    NOT NULL,
  hash_contrasena   VARCHAR(255)    NOT NULL,
  perfil            ENUM('administrador','tecnico','atencion') NOT NULL,
  activo            BOOLEAN         NOT NULL DEFAULT TRUE,
  ultimo_acceso     DATETIME        NULL,
  creado_en         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_empleados_correo (correo),
  KEY idx_empleados_perfil (perfil, activo)
) ENGINE=InnoDB;

-- Dar de baja NO borra: se apaga `activo` y el historial de lo que capturó
-- sigue apuntando a su id.


-- ---------------------------------------------------------------------------
-- 2. Clientes
-- ---------------------------------------------------------------------------

CREATE TABLE clientes (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre              VARCHAR(160)    NOT NULL,
  telefono_e164       VARCHAR(20)     NULL,   -- +522291184407
  correo              VARCHAR(160)    NULL,

  -- Consentimiento: sin esto no se le puede escribir. Se guarda cuándo y
  -- por qué vía se otorgó, que es lo que respalda el envío ante la LFPDPPP.
  consent_whatsapp    BOOLEAN         NOT NULL DEFAULT FALSE,
  consent_correo      BOOLEAN         NOT NULL DEFAULT FALSE,
  consent_fecha       DATETIME        NULL,
  consent_origen      ENUM('mostrador','chatbot','web','telefono') NULL,
  aviso_privacidad_ver VARCHAR(20)    NULL,   -- versión del aviso que aceptó

  -- 'no_localizable' lo pone el sistema tras varios fallos seguidos.
  -- 'baja' lo pide el cliente. Ambos frenan la generación de recordatorios.
  estado_contacto     ENUM('contactable','no_localizable','baja')
                                      NOT NULL DEFAULT 'contactable',

  registrado_por      BIGINT UNSIGNED NULL,
  creado_en           TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                      ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_clientes_telefono (telefono_e164),
  KEY idx_clientes_correo (correo),
  KEY idx_clientes_nombre (nombre),
  KEY idx_clientes_estado (estado_contacto),
  CONSTRAINT fk_clientes_empleado
    FOREIGN KEY (registrado_por) REFERENCES empleados (id)
) ENGINE=InnoDB;

-- El teléfono NO es único a propósito: en la práctica un matrimonio o una
-- familia comparte número. La app debe advertir del duplicado, no impedirlo.


-- ---------------------------------------------------------------------------
-- 3. Vehículos
-- ---------------------------------------------------------------------------

CREATE TABLE vehiculos (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  cliente_id          BIGINT UNSIGNED NOT NULL,

  niv                 VARCHAR(17)     NOT NULL,  -- número de serie: estable
  placa               VARCHAR(15)     NOT NULL,  -- vigente, como se capturó

  placa_normalizada   VARCHAR(15) GENERATED ALWAYS AS (
                        REGEXP_REPLACE(UPPER(placa), '[^A-Z0-9]', '')
                      ) STORED,

  -- Último carácter NUMÉRICO. NULL si la placa no trae ninguno.
  ultimo_digito       TINYINT UNSIGNED GENERATED ALWAYS AS (
                        NULLIF(RIGHT(REGEXP_REPLACE(placa, '[^0-9]', ''), 1), '') + 0
                      ) STORED,

  -- Datos tal como vienen en la tarjeta de circulación
  folio_tarjeta       VARCHAR(20)     NULL,
  marca               VARCHAR(60)     NULL,
  linea               VARCHAR(80)     NULL,
  modelo_anio         SMALLINT UNSIGNED NULL,
  color               VARCHAR(40)     NULL,
  combustible         ENUM('gasolina','diesel','gas_lp','gas_natural',
                           'hibrido','electrico') NULL,
  clase               VARCHAR(10)     NULL,
  tipo                VARCHAR(10)     NULL,
  uso                 VARCHAR(10)     NULL,
  numero_motor        VARCHAR(40)     NULL,
  capacidad_pasajeros TINYINT UNSIGNED NULL,

  -- Placas de otro estado: el calendario de Veracruz no les aplica, así que
  -- no se les generan recordatorios automáticos.
  entidad_placa       CHAR(3)         NOT NULL DEFAULT 'VER',
  en_programa_estatal BOOLEAN         NOT NULL DEFAULT TRUE,

  activo              BOOLEAN         NOT NULL DEFAULT TRUE,
  registrado_por      BIGINT UNSIGNED NULL,
  creado_en           TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                      ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_vehiculos_niv (niv),
  UNIQUE KEY uq_vehiculos_placa (placa_normalizada),
  KEY idx_vehiculos_cliente (cliente_id),
  KEY idx_vehiculos_digito (ultimo_digito, en_programa_estatal, activo),
  CONSTRAINT fk_vehiculos_cliente
    FOREIGN KEY (cliente_id) REFERENCES clientes (id),
  CONSTRAINT fk_vehiculos_empleado
    FOREIGN KEY (registrado_por) REFERENCES empleados (id)
) ENGINE=InnoDB;


-- Historia de placas del mismo vehículo -------------------------------------
CREATE TABLE vehiculo_placas (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  vehiculo_id       BIGINT UNSIGNED NOT NULL,
  placa             VARCHAR(15)     NOT NULL,
  placa_normalizada VARCHAR(15) GENERATED ALWAYS AS (
                      REGEXP_REPLACE(UPPER(placa), '[^A-Z0-9]', '')
                    ) STORED,
  ultimo_digito     TINYINT UNSIGNED GENERATED ALWAYS AS (
                      NULLIF(RIGHT(REGEXP_REPLACE(placa, '[^0-9]', ''), 1), '') + 0
                    ) STORED,
  vigente_desde     DATE            NOT NULL,
  vigente_hasta     DATE            NULL,      -- NULL = es la placa actual
  motivo            ENUM('alta','reemplazo','cambio_entidad','correccion')
                                    NOT NULL DEFAULT 'alta',
  registrado_por    BIGINT UNSIGNED NULL,
  creado_en         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_placas_vehiculo (vehiculo_id, vigente_desde),
  KEY idx_placas_busqueda (placa_normalizada),
  CONSTRAINT fk_placas_vehiculo
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Si un auto cambia de placa a media ventana, el periodo que le toca puede
-- cambiar. La app debe recalcular sus recordatorios pendientes al registrar
-- el reemplazo.


-- ---------------------------------------------------------------------------
-- 4. Verificaciones
-- ---------------------------------------------------------------------------

CREATE TABLE verificaciones (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  vehiculo_id       BIGINT UNSIGNED NOT NULL,
  fecha             DATE            NOT NULL,
  hora              TIME            NULL,
  anio              SMALLINT UNSIGNED GENERATED ALWAYS AS (YEAR(fecha)) STORED,
  periodo           TINYINT UNSIGNED NULL,   -- 1 o 2; lo calcula la app

  -- Solo 'aprobado' cuenta como cumplimiento. Un rechazo obliga a volver
  -- dentro de la misma ventana, así que NO cancela los recordatorios.
  resultado         ENUM('aprobado','rechazado') NOT NULL,
  holograma         VARCHAR(10)     NULL,
  folio_certificado VARCHAR(30)     NULL,
  placa_al_verificar VARCHAR(15)    NULL,    -- congelada, por si luego cambia
  tecnico_id        BIGINT UNSIGNED NULL,
  cita_id           BIGINT UNSIGNED NULL,
  observaciones     VARCHAR(255)    NULL,
  creado_en         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_verif_folio (folio_certificado),
  KEY idx_verif_vehiculo (vehiculo_id, fecha),
  KEY idx_verif_fecha (fecha, resultado),
  KEY idx_verif_periodo (vehiculo_id, anio, periodo, resultado),
  CONSTRAINT fk_verif_vehiculo
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id),
  CONSTRAINT fk_verif_tecnico
    FOREIGN KEY (tecnico_id) REFERENCES empleados (id)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- 5. Capacidad y citas
-- ---------------------------------------------------------------------------

CREATE TABLE horarios_atencion (
  dia_semana      TINYINT UNSIGNED NOT NULL,  -- 1 = lunes ... 7 = domingo
  hora_apertura   TIME    NOT NULL,
  hora_cierre     TIME    NOT NULL,
  activo          BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (dia_semana)
) ENGINE=InnoDB;

CREATE TABLE dias_no_laborables (
  fecha   DATE         NOT NULL,
  motivo  VARCHAR(120) NULL,
  PRIMARY KEY (fecha)
) ENGINE=InnoDB;

CREATE TABLE config_citas (
  id                    TINYINT UNSIGNED NOT NULL DEFAULT 1,

  -- 20 min y no 15: con una sola línea, si un auto se atora todos se
  -- recorren. 15 es el mejor caso, no el promedio.
  duracion_bloque_min   SMALLINT UNSIGNED NOT NULL DEFAULT 20,

  -- Una línea = un auto a la vez.
  cupos_por_bloque      TINYINT  UNSIGNED NOT NULL DEFAULT 1,

  -- Cada cuántos bloques se ofrece uno para cita. Con 3 y bloques de 20 min
  -- queda una cita por hora, y los otros dos espacios se dejan libres para
  -- quien llega sin avisar, que es como llega casi toda la gente.
  --   1 = toda la agenda para citas
  --   2 = intercalado estricto, uno sí y uno no
  --   3 = una cita por hora  (valor de arranque)
  bloques_por_cita      TINYINT  UNSIGNED NOT NULL DEFAULT 3,

  anticipacion_max_dias SMALLINT UNSIGNED NOT NULL DEFAULT 30,
  anticipacion_min_horas SMALLINT UNSIGNED NOT NULL DEFAULT 2,
  tolerancia_retardo_min SMALLINT UNSIGNED NOT NULL DEFAULT 15,
  PRIMARY KEY (id),
  CONSTRAINT ck_config_fila_unica CHECK (id = 1)
) ENGINE=InnoDB;

-- Estos valores se cambian con un UPDATE, sin tocar el código:
--   UPDATE config_citas SET bloques_por_cita = 2 WHERE id = 1;   -- más citas
--   UPDATE config_citas SET duracion_bloque_min = 15 WHERE id = 1;


CREATE TABLE citas (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

  -- Si agendó por chatbot y no está registrado, vehiculo_id va en NULL y se
  -- vincula cuando llega al mostrador.
  vehiculo_id        BIGINT UNSIGNED NULL,
  cliente_id         BIGINT UNSIGNED NULL,
  placa_capturada    VARCHAR(15)     NOT NULL,
  nombre_contacto    VARCHAR(160)    NOT NULL,
  telefono_contacto  VARCHAR(20)     NULL,

  fecha              DATE            NOT NULL,
  hora_inicio        TIME            NOT NULL,

  -- 1..cupos_por_bloque. Se pone en NULL al cancelar para liberar el lugar:
  -- el índice único ignora los NULL.
  cupo               TINYINT UNSIGNED NULL,

  estado             ENUM('agendada','confirmada','atendida',
                          'no_asistio','cancelada') NOT NULL DEFAULT 'agendada',
  origen             ENUM('mostrador','chatbot_whatsapp','chatbot_facebook',
                          'web','telefono') NOT NULL DEFAULT 'mostrador',

  creada_por         BIGINT UNSIGNED NULL,
  verificacion_id    BIGINT UNSIGNED NULL,
  cancelada_en       DATETIME        NULL,
  motivo_cancelacion VARCHAR(160)    NULL,
  notas              VARCHAR(255)    NULL,
  creado_en          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                     ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_citas_cupo (fecha, hora_inicio, cupo),
  KEY idx_citas_agenda (fecha, hora_inicio, estado),
  KEY idx_citas_vehiculo (vehiculo_id, fecha),
  KEY idx_citas_placa (placa_capturada),
  CONSTRAINT fk_citas_vehiculo
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id),
  CONSTRAINT fk_citas_cliente
    FOREIGN KEY (cliente_id) REFERENCES clientes (id),
  CONSTRAINT fk_citas_empleado
    FOREIGN KEY (creada_por) REFERENCES empleados (id),
  CONSTRAINT fk_citas_verificacion
    FOREIGN KEY (verificacion_id) REFERENCES verificaciones (id)
) ENGINE=InnoDB;

ALTER TABLE verificaciones
  ADD CONSTRAINT fk_verif_cita FOREIGN KEY (cita_id) REFERENCES citas (id);


-- ---------------------------------------------------------------------------
-- 6. Mensajería
-- ---------------------------------------------------------------------------

CREATE TABLE plantillas_mensaje (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  clave             VARCHAR(60)     NOT NULL,  -- aviso_1, cita_recordatorio...
  canal             ENUM('whatsapp','correo') NOT NULL,
  version           SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  nombre_meta       VARCHAR(100)    NULL,      -- nombre de la plantilla en Meta
  idioma            VARCHAR(10)     NOT NULL DEFAULT 'es_MX',
  asunto            VARCHAR(200)    NULL,      -- solo correo
  cuerpo            TEXT            NOT NULL,
  estado_aprobacion ENUM('borrador','en_revision','aprobada','rechazada')
                                    NOT NULL DEFAULT 'borrador',
  activa            BOOLEAN         NOT NULL DEFAULT FALSE,
  actualizado_por   BIGINT UNSIGNED NULL,
  actualizado_en    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_plantilla (clave, canal, version),
  CONSTRAINT fk_plantilla_empleado
    FOREIGN KEY (actualizado_por) REFERENCES empleados (id)
) ENGINE=InnoDB;

-- Cambiar el texto de una plantilla de WhatsApp obliga a nueva aprobación de
-- Meta: por eso se versiona en lugar de sobrescribirse.


CREATE TABLE recordatorios (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  vehiculo_id        BIGINT UNSIGNED NOT NULL,
  cliente_id         BIGINT UNSIGNED NOT NULL,

  tipo               ENUM('ventana','cita') NOT NULL DEFAULT 'ventana',
  aviso_clave        VARCHAR(30)     NOT NULL, -- aviso_1..4, seguimiento, cita
  ventana_anio       SMALLINT UNSIGNED NULL,
  ventana_periodo    TINYINT  UNSIGNED NULL,
  cita_id            BIGINT UNSIGNED NULL,

  canal              ENUM('whatsapp','correo') NOT NULL,
  plantilla_id       BIGINT UNSIGNED NULL,
  destino            VARCHAR(160)    NOT NULL, -- congelado al generarse
  programado_para    DATETIME        NOT NULL,

  -- Estado interno: lo controla nuestro sistema
  estado             ENUM('programado','pausado','cancelado','en_proceso',
                          'enviado','error') NOT NULL DEFAULT 'programado',
  -- Estado de entrega: lo reporta el proveedor. Solo avanza, nunca retrocede.
  estado_entrega     ENUM('pendiente','enviado','entregado','leido','clic',
                          'rebote_duro','rebote_suave','fallido','spam','baja')
                                     NOT NULL DEFAULT 'pendiente',

  motivo_error       VARCHAR(255)    NULL,
  id_externo         VARCHAR(120)    NULL,     -- message id del proveedor
  enviado_en         DATETIME        NULL,

  -- Evita duplicados si el job corre dos veces. COALESCE porque los NULL
  -- no colisionan en un índice único.
  clave_idempotencia VARCHAR(160) GENERATED ALWAYS AS (
                       CONCAT_WS('|', vehiculo_id, tipo, aviso_clave,
                                 COALESCE(ventana_anio, 0),
                                 COALESCE(ventana_periodo, 0),
                                 COALESCE(cita_id, 0), canal)
                     ) STORED,

  creado_en          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                     ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_recordatorio_idem (clave_idempotencia),
  KEY idx_recordatorios_cola (estado, programado_para),
  KEY idx_recordatorios_externo (id_externo),
  KEY idx_recordatorios_cliente (cliente_id, creado_en),
  CONSTRAINT fk_rec_vehiculo  FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id),
  CONSTRAINT fk_rec_cliente   FOREIGN KEY (cliente_id)  REFERENCES clientes (id),
  CONSTRAINT fk_rec_cita      FOREIGN KEY (cita_id)     REFERENCES citas (id),
  CONSTRAINT fk_rec_plantilla FOREIGN KEY (plantilla_id)
    REFERENCES plantillas_mensaje (id)
) ENGINE=InnoDB;


CREATE TABLE recordatorio_eventos (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  recordatorio_id BIGINT UNSIGNED NOT NULL,
  evento          VARCHAR(30)     NOT NULL,
  ocurrido_en     DATETIME(3)     NOT NULL,   -- hora que reporta el proveedor
  recibido_en     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  codigo_error    VARCHAR(40)     NULL,
  payload         JSON            NULL,
  PRIMARY KEY (id),
  KEY idx_eventos_rec (recordatorio_id, ocurrido_en),
  CONSTRAINT fk_eventos_rec
    FOREIGN KEY (recordatorio_id) REFERENCES recordatorios (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Los webhooks llegan desordenados con más frecuencia de la que uno espera.
-- Guardar cada evento con su hora permite reconstruir la secuencia real y
-- responder cuando un cliente reclame que nunca le avisaron.


-- ---------------------------------------------------------------------------
-- 7. Chatbot
-- ---------------------------------------------------------------------------

CREATE TABLE chatbot_respuestas (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  pregunta        VARCHAR(255)    NOT NULL,
  respuesta       TEXT            NOT NULL,
  tipo            ENUM('texto_fijo','automatica','con_enlace','transfiere')
                                  NOT NULL DEFAULT 'texto_fijo',
  palabras_clave  VARCHAR(255)    NULL,
  orden           SMALLINT UNSIGNED NOT NULL DEFAULT 100,
  activa          BOOLEAN         NOT NULL DEFAULT TRUE,
  actualizado_por BIGINT UNSIGNED NULL,
  actualizado_en  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_faq_activa (activa, orden),
  CONSTRAINT fk_faq_empleado
    FOREIGN KEY (actualizado_por) REFERENCES empleados (id)
) ENGINE=InnoDB;

-- Editar esta tabla NO pasa por revisión de Meta: son respuestas dentro de la
-- ventana de 24 h que abre el cliente al escribir.


CREATE TABLE chatbot_pendientes (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  canal             ENUM('whatsapp','facebook','web') NOT NULL,
  contacto_externo  VARCHAR(120)    NOT NULL,  -- wa_id o psid
  pregunta          VARCHAR(500)    NOT NULL,
  veces             SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  ultima_vez        DATETIME        NOT NULL,
  -- 24 h después del último mensaje del cliente. Pasada esa hora ya no se le
  -- puede contestar libremente y solo queda agregar la pregunta al catálogo.
  ventana_expira_en DATETIME        NULL,
  resuelta          BOOLEAN         NOT NULL DEFAULT FALSE,
  respuesta_id      BIGINT UNSIGNED NULL,
  creado_en         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_pendientes_abiertas (resuelta, ventana_expira_en),
  CONSTRAINT fk_pendiente_respuesta
    FOREIGN KEY (respuesta_id) REFERENCES chatbot_respuestas (id)
) ENGINE=InnoDB;


-- ===========================================================================
--  Datos iniciales
-- ===========================================================================

INSERT INTO horarios_atencion (dia_semana, hora_apertura, hora_cierre, activo)
VALUES (1,'09:00:00','16:00:00',TRUE),
       (2,'09:00:00','16:00:00',TRUE),
       (3,'09:00:00','16:00:00',TRUE),
       (4,'09:00:00','16:00:00',TRUE),
       (5,'09:00:00','16:00:00',TRUE),
       (6,'09:00:00','16:00:00',TRUE),
       (7,'09:00:00','16:00:00',FALSE);   -- domingo cerrado

INSERT INTO config_citas (id) VALUES (1);

INSERT INTO chatbot_respuestas (pregunta, respuesta, tipo, palabras_clave, orden)
VALUES
 ('¿Cuándo me toca verificar?',
  'Mándame la placa de tu vehículo y te digo los dos periodos que te tocan este año.',
  'automatica', 'cuando,toca,verificar,periodo,fecha', 10),
 ('¿Cuál es el horario y la dirección?',
  'Av. Ruíz Cortines No. 256, Col. Centro. Lunes a sábado de 9:00 a 16:00 hrs.',
  'texto_fijo', 'horario,direccion,ubicacion,donde', 20),
 ('¿Qué documentos debo llevar?',
  'Tarjeta de circulación, identificación oficial y comprobante de pago.',
  'texto_fijo', 'documentos,papeles,llevar,requisitos', 30),
 ('Quiero agendar una cita',
  'Te muestro los horarios disponibles para que elijas.',
  'con_enlace', 'cita,agendar,apartar,reservar', 40),
 ('Quiero hablar con una persona',
  'Con gusto. En horario hábil te contesta alguien del mostrador.',
  'transfiere', 'persona,humano,asesor,ayuda', 90);
