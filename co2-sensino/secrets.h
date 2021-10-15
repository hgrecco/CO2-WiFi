// Este archivo puede contener información sensible
// No publicar en internet una vez completada

/**
 * WiFi
 */
// SSID del la red
#define STASSID "NOMBRE-RED-WIFI"
// Clave del la red. Para dejar vacío usar ""
#define STAPSK "CLAVE-RED-WIFI"

/**
 * SERVIDOR
 */
// URL del servidor para enviar los datos.
#define ENDPOINT "http://direccion.web.ar:80/store"
// URL del servidor NTP-like basado en HTTP.
#define TIMECLIENT_ENDPOINT "http://direccion.web.ar:80/now"
// API KEY
#define API_KEY "CAMBIAR"

/*
 * OVER THE AIR UPDATES
 */
// host del servidor.
#define UPDATE_SERVER "direccion.web.ar"
// Puerto del servidor.
#define UPDATE_PORT 80
// path dentro del sevidor donde se encuentran
#define UPDATE_ENDPOINT "/updates"