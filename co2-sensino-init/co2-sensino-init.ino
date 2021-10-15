/**
 * CO2-SENSINO-INIT
 * ----------------
 * 
 * Este primer firmware hace lo siguiente:
 * 1. Graba el número de serie del dispostivo en el EEPROM.
 * 2. Establece que el dispositivo aún no ha sido calibrado.
 * 3. Se conecta a WiFi.
 * 4. Baja la versión 1 del firmware del servidor y la instala.
 * 
 * IMPORTANTE: definir el valor de SERIAL_NUMBER antes de subirlo
 * al dispositivo.
 * 
 */
 
#include <ESP8266WiFi.h>
#include <ESP8266WiFiMulti.h>

#include <ESP8266HTTPClient.h>
#include <ESP8266httpUpdate.h>

#include "config.h"
#include "secrets.h"
#include "memstruct.h"

#include "src/sensino/screen.hpp"
#include "src/sensino/memory.hpp"

#define SERIAL_NUMBER 0

const char* ssid = STASSID;
const char* password = STAPSK;

sensino::Screen screen;
sensino::Memory<MemoryContent> memory(0);

void setup() {
  static char str[30];

  screen.setup();
  
  Serial.begin(115200);

  Serial.println("Booting");
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  WiFi.begin(ssid, password);

  screen.rows3("Pantalla ok", nullptr, nullptr);
  delay(10000);
  if ((memory.content.serialNumber == SERIAL_NUMBER) && (memory.content.lastCalibration == NOCAL)) {
    Serial.println("Initial info stored");
    snprintf(str, 30, "S/N: %u", SERIAL_NUMBER);
    screen.rows3(nullptr, str, "(present)", false);
  } else {
    memory.content.serialNumber = SERIAL_NUMBER;
    memory.content.lastCalibration = NOCAL;
    while (!memory.write()) {
      Serial.println("Retrying serial store...");
      delay(10000);
    }
    snprintf(str, 30, "S/N: %u", SERIAL_NUMBER);
    screen.rows3(nullptr, str, "(stored now)", false);
  }

  delay(4000);
  
  while (WiFi.waitForConnectResult() != WL_CONNECTED) {
    WiFi.begin(ssid, password);
    Serial.println("Retrying connection...");
  }

  screen.rows3(nullptr, nullptr, "Conectado a WiFi", false);

  ESPhttpUpdate.onStart([]() {
    screen.rows3("OTA: Iniciado", nullptr, nullptr);
  });

  ESPhttpUpdate.onProgress([](unsigned int progress, unsigned int total) {
    static char str[30];
    snprintf(str, 30, "  %u%%\r", (progress / (total / 100)));
    screen.rows3("OTA: en proceso", str, nullptr);
  });


  ESPhttpUpdate.onEnd([]() {
    screen.rows3("OTA: Terminado", nullptr, nullptr);
  });

  ESPhttpUpdate.onError([](int error) {
    screen.rows3("OTA: Error", nullptr, nullptr);    
  });

  Serial.println("Ready");

}

void loop() {
  static char str[60];
  static char _update_file[60];
  WiFiClient client;
  
  snprintf(_update_file, 60, "%s/1", UPDATE_ENDPOINT);
  
  t_httpUpdate_return ret = ESPhttpUpdate.update(client, UPDATE_SERVER, UPDATE_PORT, _update_file);
  if (ret == HTTP_UPDATE_FAILED) {
    snprintf(str, 60, "(%d): %s\n", ESPhttpUpdate.getLastError(), ESPhttpUpdate.getLastErrorString().c_str());
    Serial.println(str);
    screen.rows3(nullptr, "Failed", str, false); 
  } else if (ret == HTTP_UPDATE_NO_UPDATES) {
    screen.rows3(nullptr, "No updates", nullptr, false); 
    Serial.println("No updates");
  } else if (ret == HTTP_UPDATE_OK) {
    screen.rows3(nullptr, "Updated", nullptr, false);
    delay(10000);
    Serial.println("Updated");
  };
  delay(1000);
}
