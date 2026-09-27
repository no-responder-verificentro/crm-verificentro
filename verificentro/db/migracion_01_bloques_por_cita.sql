-- ===========================================================================
--  Migración 01 · agrega config_citas.bloques_por_cita
-- ===========================================================================
--  Aplícala si tu base se creó ANTES de que existiera esa columna. Se nota
--  porque /citas/disponibilidad devuelve error 500 con el mensaje
--  "Unknown column 'config_citas.bloques_por_cita'".
--
--  NO borra datos.
--
--      mysql -u root -p --default-character-set=utf8mb4 verificentro < db\migracion_01_bloques_por_cita.sql
-- ===========================================================================

-- Cada cuántos bloques se ofrece uno para cita.
--   1 = toda la agenda    2 = uno sí y uno no    3 = una cita por hora
ALTER TABLE config_citas
  ADD COLUMN bloques_por_cita TINYINT UNSIGNED NOT NULL DEFAULT 3
  AFTER cupos_por_bloque;

-- Por si la fila de configuración nunca se creó.
INSERT IGNORE INTO config_citas (id) VALUES (1);

-- Los valores acordados: una línea, 20 minutos por auto, una cita por hora.
UPDATE config_citas
   SET duracion_bloque_min = 20,
       cupos_por_bloque    = 1,
       bloques_por_cita    = 3
 WHERE id = 1;

-- Horario de atención, por si tampoco se cargó (lunes a sábado 9:00–16:00).
INSERT IGNORE INTO horarios_atencion (dia_semana, hora_apertura, hora_cierre, activo)
VALUES (1,'09:00:00','16:00:00',TRUE), (2,'09:00:00','16:00:00',TRUE),
       (3,'09:00:00','16:00:00',TRUE), (4,'09:00:00','16:00:00',TRUE),
       (5,'09:00:00','16:00:00',TRUE), (6,'09:00:00','16:00:00',TRUE),
       (7,'09:00:00','16:00:00',FALSE);

SELECT duracion_bloque_min AS bloque_min, cupos_por_bloque AS cupos,
       bloques_por_cita AS cada_cuantos_bloques
  FROM config_citas;
