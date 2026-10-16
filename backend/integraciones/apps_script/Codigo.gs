/**
 * Puente de correo del CRM Verificentro.
 *
 * Vive en la cuenta de Google del verificentro. El sistema le manda el correo
 * ya armado y este script lo entrega con MailApp, o sea con la identidad de
 * esa cuenta, igual que si lo escribieras tú desde Gmail.
 *
 * Cómo publicarlo está en CONECTAR_CORREO.md, en la raíz del proyecto.
 *
 * Lo único que hay que cambiar aquí es el TOKEN de abajo.
 */

// Invéntate una cadena larga, pega la MISMA en APPS_SCRIPT_TOKEN del .env
// y de Render. Sin esto, cualquiera que descubra la dirección del script
// podría mandar correo a nombre del verificentro.
const TOKEN = 'CAMBIA-ESTO-POR-UNA-CADENA-LARGA-Y-UNICA';

// Tope de seguridad propio, por debajo del de Google. Evita que un error en
// un ciclo del sistema se coma la cuota del día entero.
const MAXIMO_POR_DIA = 90;


function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return responder({ ok: false, error: 'Petición vacía.' });
    }

    const datos = JSON.parse(e.postData.contents);

    if (!datos.token || datos.token !== TOKEN) {
      return responder({ ok: false, error: 'Token inválido.' });
    }
    if (!datos.para) {
      return responder({ ok: false, error: 'Falta el destinatario.' });
    }

    const restantes = cuotaRestante();
    if (restantes === 0) {
      // 'cuota' en el texto hace que el sistema lo trate como fallo pasajero
      // y no queme al contacto. No cambies esa palabra.
      return responder({
        ok: false,
        error: 'Se agotó la cuota diaria de correo de Google.',
      });
    }

    MailApp.sendEmail({
      to: datos.para,
      subject: datos.asunto || 'Recordatorio de verificación',
      body: datos.texto || '',
      htmlBody: datos.html || undefined,
      name: datos.nombre_remitente || 'Verificentro',
      replyTo: datos.responder_a || undefined,
    });

    return responder({
      ok: true,
      id: Utilities.getUuid(),
      restantes: restantes === null ? null : restantes - 1,
    });

  } catch (error) {
    return responder({ ok: false, error: String(error) });
  }
}


/**
 * Cuánto queda de la cuota diaria, o null si no se puede averiguar.
 *
 * Consultar la cuota exige el mismo permiso que mandar correo, y hay un caso
 * en que Google lo niega: cuando la implementación publicada se creó ANTES de
 * que autorizaras el script, se queda con los permisos de aquel momento. El
 * síntoma es este error:
 *
 *     You do not have permission to call MailApp.getRemainingDailyQuota
 *
 * Esto no es esencial —es una red de seguridad— así que si falla se sigue
 * adelante y que el envío diga lo suyo. Antes, un permiso faltante aquí
 * tumbaba el envío entero en un punto que no tenía nada que ver.
 */
function cuotaRestante() {
  try {
    return MailApp.getRemainingDailyQuota();
  } catch (error) {
    return null;
  }
}


/**
 * Abrir la dirección del script en el navegador cae aquí. Sirve para
 * comprobar de un vistazo que quedó publicado, sin mandar nada.
 *
 * Todo lo que puede fallar por permisos va protegido: esta página tiene que
 * poder contestar sobre todo cuando algo está mal configurado, que es cuando
 * uno la abre.
 */
function doGet() {
  var cuenta = null;
  try {
    cuenta = Session.getEffectiveUser().getEmail();
  } catch (error) {
    cuenta = '(sin permiso para saberlo)';
  }

  const restantes = cuotaRestante();

  return responder({
    ok: true,
    servicio: 'Puente de correo · CRM Verificentro',
    cuenta: cuenta,
    restantes_hoy: restantes,
    permisos_de_correo: restantes === null
      ? 'FALTAN. Ejecuta autorizarYProbar y vuelve a implementar una VERSIÓN NUEVA.'
      : 'correctos',
    token_configurado: TOKEN !== 'CAMBIA-ESTO-POR-UNA-CADENA-LARGA-Y-UNICA',
    maximo_recomendado: MAXIMO_POR_DIA,
  });
}


/**
 * Ejecuta ESTA función una vez a mano, desde el editor, antes de publicar.
 * Es lo que dispara la pantalla de permisos de Google. Si no la autorizas,
 * el script contesta con una página HTML en lugar de JSON y el sistema
 * reporta "el script no respondió en JSON".
 */
function autorizarYProbar() {
  const yo = Session.getEffectiveUser().getEmail();
  MailApp.sendEmail({
    to: yo,
    subject: '[PRUEBA] Puente de correo del Verificentro',
    body: 'Si lees esto, el script quedó autorizado y puede mandar correo.\n\n'
        + 'Cuota restante hoy: ' + MailApp.getRemainingDailyQuota(),
  });
  Logger.log('Enviado a ' + yo);
}


function responder(objeto) {
  return ContentService
    .createTextOutput(JSON.stringify(objeto))
    .setMimeType(ContentService.MimeType.JSON);
}
