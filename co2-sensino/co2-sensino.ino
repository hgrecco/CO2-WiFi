/**
 * CO2-SENSINO
 * -----------
 * 
 * Este es el firmware principal del proyecto.
 * - 
 * 
 */

// Versión del firmware.
// Se sugiere usar YYYYMMDDNN,
// dónde YYYY es el año (con 4 dígitos), MM el mes (con 2 dígitos),
// DD es el día (con 2 dígitos) y NN un número que indica la versión
// dentro del día (con 2 dígitos).
#define FWV 2021081401
 
#include <Arduino.h>
#include <ArduinoJson.h>

#include <ESP8266WiFi.h>
#include <ESP8266WiFiMulti.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266httpUpdate.h>

#include <MHZ19.h>
#include <SoftwareSerial.h>

#include "config.h"
#include "secrets.h"
#include "memstruct.h"

#include "src/sensino/common.h"
#include "src/sensino/client.hpp"
#include "src/sensino/button.hpp"
#include "src/sensino/memory.hpp"
#include "src/sensino/screen.hpp"

//#define DEBUG

#include "src/sensino/debug.h"

using sensino::MEASURE_STATE;
using sensino::SEND_STATE;

MHZ19 co2sensor;
SoftwareSerial uartSensor(CO2SENSOR_RX_PIN, CO2SENSOR_TX_PIN);

const char degSymbol = '°';

const int screen_str_len = 40;
static char screen_str1[screen_str_len];
static char screen_str2[screen_str_len];
static char screen_str3[screen_str_len];

// Elementos del menú.
enum class BUTTON_STATE : unsigned int {
    RELEASED = 0,
    SCREEN_MODE_ENABLED = 1,
    SCREEN_MODE_MINIMUM = 2,
    SCREEN_MODE_DISABLED = 3,
    SPLASH_SENSOR = 4,
    SPLASH_SERVER = 5,
    CALIBRATE = 6,
    RESET = 7,
    CANCEL = 8,
};


// Modos de pantalla.
enum class SCREEN_MODE : unsigned int {
    ENABLED = 0,
    MINIMUM = 1,
    DISABLED = 2,
};


// Elementos extra del registro (Ver userRecord en SENSINO).
class MyRecord {

public:
    int temperature;
    int co2;

    void fill(JsonObject& doc) {
        doc["co2"] = this->co2;
        doc["temperature"] = this->temperature;
    }
};


// Elementos extra de configuración (Ver userConfig en SENSINO).
class MyConfig {

public:
    SCREEN_MODE screenMode = SCREEN_MODE::ENABLED;
    unsigned long lastCalibration = 0;
    unsigned long firmwareVersion = 42;

    void fill(JsonDocument& doc) {
        doc["screenMode"] = static_cast<unsigned int>(this->screenMode);
        // TODO Remove in the future.
        doc["lastCalibration"] = this->lastCalibration;
        doc["firmwareVersion"] = this->firmwareVersion;
    }

};


// Callback antes de medir.
void beforeMeasureTick() {
}


// Callback para de medir.
std::pair<MyRecord, bool> onMeasureTick() {
    byte errorCode;
    MyRecord rec;
    
    rec.co2 = co2sensor.getCO2();
    
    errorCode = co2sensor.errorCode;
    if(errorCode != RESULT_OK) {
      info_print_var("co2 error", errorCode);
      return std::make_pair(rec, false);
    }

    rec.temperature = co2sensor.getTemperature();
    
    errorCode = co2sensor.errorCode;
    if(errorCode != RESULT_OK) {
      info_print_var("temperature error", errorCode);
      return std::make_pair(rec, false);
    }
    
    return std::make_pair(rec, true);
}

// Callback después de medir.
void afterMeasureTick() {
}


static esp8266::polledTimeout::periodicMs loopPeriod(1000);

sensino::Screen screen;
sensino::Button<BUTTON_STATE> buttonObject(BUTTON_PIN, LOW, 4);
sensino::Memory<MemoryContent> memory(0);
sensino::Client<MyRecord, MyConfig, BUFFER_SIZE> sensorClient(ENDPOINT,
                                                              memory.content.serialNumber, 
                                                              API_KEY, RECORD_PERIOD_SEC * 1000);

// Pantalla de inicio.
void splashSensorInfo() {
    snprintf(screen_str1, screen_str_len, "fwv: %u", FWV);
    snprintf(screen_str2, screen_str_len, "s/n: %u", sensorClient.getSerialNumber());
    if (memory.content.lastCalibration == NOCAL) {
      snprintf(screen_str3, screen_str_len, "cal: pendiente");
    } else {
      snprintf(screen_str3, screen_str_len, "cal: %u", memory.content.lastCalibration);
    }
    screen.rows3_scroll(screen_str1, screen_str2, screen_str3);
}


// Pantalla de información del servidor.
void splashServerInfo() {
    snprintf(screen_str1, screen_str_len, "Actualiza: %d s", RECORD_PERIOD_SEC);
    snprintf(screen_str2, screen_str_len, "WiFi: %s", STASSID);
    snprintf(screen_str3, screen_str_len, "Servidor: %s", ENDPOINT);

    screen.rows3_scroll(screen_str1, screen_str2, screen_str3);
}


// Pantalla para cuenta regresiva.
void updateCountdown(unsigned int _countDown) {
    screen.u8g2.clearBuffer();

    screen.u8g2.setFont(u8g2_font_crox4tb_tf);

    if (_countDown > 0) {
        snprintf(screen_str1, screen_str_len, "%2d", _countDown);
        screen.u8g2.drawStr(50, 30, screen_str1);
        screen.u8g2.sendBuffer();
        return;
    }
}


/**
 * Pantalla para mostrar el estado.
 * ----------------
 * | CO2   ICONO1 |
 * | TEMP  ICONO2 |
 * ----------------
 * 
 * ICONO1: vinculado al servidor.
 * - FLECHAS: enviando información.
 * - ! EN TRIANGULO: error del servidor.
 * - WIFI: Conectado a WiFi.
 * - PROHIBIDO: No conectado a WiFi.
 * 
 * ICONO2: vinculado a la adquisición.
 * - CAMARA: dato adquirido.
 * - X EN CÍRCULO: buffer lleno.
 * - BICHO: error al adquirir. 
 * - CORAZON:
 * 
 */
void updateScreen(int _lastCO2,
                  int _lastTemp, MEASURE_STATE _measure_state,
                  SEND_STATE _send_state, bool _isBufferFull,
                  bool showFull) {
    static unsigned int lastGlyph = 0;

    if (showFull) {
        snprintf(screen_str1, screen_str_len, "%d ppm", _lastCO2);
        snprintf(screen_str2, screen_str_len, "%2d %cC", _lastTemp, degSymbol);

        screen.rows2(screen_str1, screen_str2, true, false, 10);
    } else {
        screen.clear();
    }

    unsigned int g = 0;
    screen.u8g2.setFont(u8g2_font_open_iconic_all_2x_t);
    // H/W: 16x16

    switch (_measure_state) {
        case MEASURE_STATE::STORE :
            g = 108; // camera
            break;
        case MEASURE_STATE::BUFFER_FULL:
            g = 121; // X sign in circle
            break;
        case MEASURE_STATE::ERROR:
            g = 104; // bug sign
            break;
        default:
            if (_isBufferFull) {
                g = 195; // paper stack
            } else {
                g = 183; // heart
            }
    }
    
    if (g == lastGlyph) {
        g = 0;
    }
    
    if (g > 0) {
        screen.u8g2.drawGlyph(100, 50, g);
    }
    lastGlyph = g;

    if (WiFi.status() == WL_CONNECTED) {
        switch (_send_state) {
            case SEND_STATE::SUCCESS: // Sending ok
                g = 205;                // refresh arrows
                break;
            case SEND_STATE::ERROR: // Error sending
                g = 280;              // triangle with !
                break;
            default:   // Conected to WiFi
                g = 247; // WiFi Symnol
                break;
        }
    } else {  // No WiFi
        g = 87; // signo prohibido
    }

    screen.u8g2.drawGlyph(100, 24, g);
    screen.u8g2.sendBuffer();
}


unsigned long getLastDigit(unsigned long value) {
    unsigned long tmp = value / 10;
    return value - (tmp * 10);
}

/**
 * Calibrar
 * 1. Si no pasaron CO2SENSOR_CALIBRATION_WAIT_MIN minutos 
 *    desde que fue encendido el dispositivo, espera.
 * 2. Calibra.
 * 3. Espera 60 segundos.
 * 4. Calibra.
 * 5. Guarda la nueva fecha de calibración en la EEPROM.
 * 
 */
void calibrate(unsigned long newDigit) {
    digitalWrite(FAN_PIN, LOW);
    long pending = CO2SENSOR_CALIBRATION_WAIT_MIN * 60 * 1000 - millis();
    while (pending > 0) {
        screen.title_number("Esperando ...", pending/1000, "s");
        delay(1000);
        pending = CO2SENSOR_CALIBRATION_WAIT_MIN * 60 * 1000 - millis();
    }

    co2sensor.calibrate();
    for (unsigned int n = 60; n > 0; n--) {
        delay(1000);
        screen.title_number("Calibrando ...", n, "s");
    }
    co2sensor.calibrate();
    unsigned long newLastCalibration = sensino::timeClient.getEpochTime();

    // After calibrating we need to make sure that the we have the right digit given by the server.
    newLastCalibration = newLastCalibration - getLastDigit(newLastCalibration) + newDigit;

    sensorClient.userConfig.lastCalibration = newLastCalibration;
    memory.content.lastCalibration = newLastCalibration;
    memory.write();
    screen.rows2("Calibración", "  finalizada");
    delay(2000);
}


/**
 * Agrega los callbacks del cliente, vinculando:
 * - estado.
 * - acción si el botón sigue apretado.
 * - acción si se suelta el botón.
 * 
 */
void addButtonCallbacks() {

    buttonObject.addState(
            BUTTON_STATE::RELEASED,
            [] {
                return BUTTON_STATE::SCREEN_MODE_ENABLED;
            },
            [] {
                return BUTTON_STATE::RELEASED;
            }
    );


    buttonObject.addState(
            BUTTON_STATE::SCREEN_MODE_ENABLED,
            [] {
                screen.rows3("Suelte para:",
                             "  PANTALLA",
                             "   ENCENDIDA");
                return BUTTON_STATE::SCREEN_MODE_MINIMUM;
            },
            [] {
                sensorClient.userConfig.screenMode = SCREEN_MODE::ENABLED;
                return BUTTON_STATE::RELEASED;
            }
    );

    buttonObject.addState(
            BUTTON_STATE::SCREEN_MODE_MINIMUM,
            [] {
                screen.rows3("Suelte para:",
                             "  PANTALLA",
                             "   MINIMA");
                return BUTTON_STATE::SCREEN_MODE_DISABLED;
            },
            [] {
                sensorClient.userConfig.screenMode = SCREEN_MODE::MINIMUM;
                return BUTTON_STATE::RELEASED;
            }
    );

    buttonObject.addState(
            BUTTON_STATE::SCREEN_MODE_DISABLED,
            [] {
                screen.rows3("Suelte para:",
                             "  PANTALLA",
                             "   APAGADA");
                return BUTTON_STATE::SPLASH_SENSOR;
            },
            [] {
                screen.clear();
                sensorClient.userConfig.screenMode = SCREEN_MODE::DISABLED;
                return BUTTON_STATE::RELEASED;
            }
    );

    buttonObject.addState(
            BUTTON_STATE::SPLASH_SENSOR,
            [] {
                screen.rows3("Suelte para:",
                             "  INFO",
                             "   SENSOR");
                return BUTTON_STATE::SPLASH_SERVER;
            },
            [] {
                splashSensorInfo();
                delay(2000);
                return BUTTON_STATE::RELEASED;
            }
    );

    buttonObject.addState(
            BUTTON_STATE::SPLASH_SERVER,
            [] {
                screen.rows3("Suelte para:",
                             "  INFO",
                             "   SERVIDOR");
                return BUTTON_STATE::CALIBRATE;
            },
            [] {
                splashServerInfo();
                delay(2000);
                return BUTTON_STATE::RELEASED;
            }
    );


    buttonObject.addState(
            BUTTON_STATE::CALIBRATE,
            [] {
                screen.rows3("Suelte para:",
                             "  CALIBRAR",
                             "");
                return BUTTON_STATE::RESET;
            },
            [] {
                calibrate(0);
                return BUTTON_STATE::RELEASED;
            }
    );

    buttonObject.addState(
            BUTTON_STATE::RESET,
            [] {
                screen.rows3("Suelte para:",
                             "  RESET",
                             "");
                return BUTTON_STATE::CANCEL;
            },
            [] {
                ESP.restart();
                return BUTTON_STATE::RELEASED;
            }
    );

    buttonObject.addState(
            BUTTON_STATE::CANCEL,
            [] {
                screen.rows3("Suelte para:",
                             "  CANCELAR",
                             "");
                return BUTTON_STATE::RELEASED;
            },
            [] {
                return BUTTON_STATE::RELEASED;
            }
    );
}


// Callbacks para Over the Air Updates.
void addOTAcallbacks() {
  ESPhttpUpdate.onStart([]() {
      screen.rows3("OTA: Iniciado", nullptr, nullptr);
  });
  
  ESPhttpUpdate.onProgress([](unsigned int progress, unsigned int total) {
      snprintf(screen_str2, screen_str_len, "  %u%%\r", (progress / (total / 100)));
      screen.rows3("OTA: en proceso", screen_str2, nullptr);
  });
  
  ESPhttpUpdate.onEnd([]() {
      screen.rows3("OTA: Terminado", nullptr, nullptr);
  });
  
  ESPhttpUpdate.onError([](int error) {
      screen.rows3("OTA: Error", nullptr, nullptr);
  });
}


/** 
 * Actualiza el firmware
 * 
 * Si se elige la versión 0, mapea a latest
 * 
 */
void update_firmware(unsigned long desired_version) {
    static char _update_file[60];
    if (desired_version == 0) {
        snprintf(_update_file, 60, "%s/latest", UPDATE_ENDPOINT);
    } else {
        snprintf(_update_file, 60, "%s/%u", UPDATE_ENDPOINT, desired_version);
    }
    WiFiClient wifiClient;
    t_httpUpdate_return ret = ESPhttpUpdate.update(wifiClient, UPDATE_SERVER, UPDATE_PORT, _update_file);
    if (ret == HTTP_UPDATE_FAILED) {
        snprintf(screen_str2, screen_str_len, "(%d): %s\n", ESPhttpUpdate.getLastError(), ESPhttpUpdate.getLastErrorString().c_str());
        screen.rows3(nullptr, "Failed", screen_str2, false);
    } else if (ret == HTTP_UPDATE_NO_UPDATES) {
        screen.rows3(nullptr, "No updates", nullptr, false);
    } else if (ret == HTTP_UPDATE_OK) {
        screen.rows3(nullptr, "Updated", nullptr, false);
    };
    delay(3000);
}


// Llena información extra del dispositivo (ver sendDeviceInfo en SENSINO).
bool fillDeviceInfo(JsonObject& doc) {
    char myVersion[4];
    doc["firmwareVersion"] = FWV;
    doc["lastCalibration"] = memory.content.lastCalibration;
    co2sensor.getVersion(myVersion);
    doc["MHZ19.version"] = myVersion;
    doc["MHZ19.range"] = co2sensor.getRange();
    doc["MHZ19.backgroundCO2"] = co2sensor.getBackgroundCO2();
    doc["MHZ19.tempAdjustment"] = co2sensor.getTempAdjustment();
    doc["MHZ19.ABC"] = co2sensor.getABC();
    return true;
}


// Acciona en respuesta a pedidos del servidor (Ver onUserServerPayload en SENSINO).
bool onUserServerPayload(const JsonObject& doc) {
    if (doc.containsKey("screenMode")) {
        sensorClient.userConfig.screenMode = static_cast<SCREEN_MODE>(doc["screenMode"].as<unsigned int>());
    }
    if (doc.containsKey("lastCalibration")) {
        unsigned long lastCalibration = doc["lastCalibration"].as<unsigned long>();
        auto currentTimestamp = sensino::timeClient.getEpochTime();

        // We only try to calibrate if the clock has synced with the server
        // 4,294,967,295
        // 1,577,836,800
        if (currentTimestamp > 1577836800) { // 20200101-000000
            // and the last digit of the payload lastCalibration is different to the current
            int payloadCheckDigit = getLastDigit(lastCalibration);
            int currentCheckDigit = getLastDigit(memory.content.lastCalibration);

            if (currentCheckDigit != payloadCheckDigit) {
                calibrate(payloadCheckDigit);
            }
        }
    }
    if (doc.containsKey("firmwareVersion")) {
        unsigned long firmwareVersion = doc["firmwareVersion"].as<unsigned long>();
        if (firmwareVersion != FWV) {
            update_firmware(firmwareVersion);
        }
    }

    return true;
}

void addSensorClientCallbacks() {
    sensorClient.onMeasureTick(onMeasureTick);
    sensorClient.beforeMeasureTick(beforeMeasureTick);
    sensorClient.afterMeasureTick(afterMeasureTick);
    sensorClient.onUserServerPayload(onUserServerPayload);
    sensorClient.fillDeviceInfo(fillDeviceInfo);
}


void setup() {
    sensino::timeClient.begin(TIMECLIENT_ENDPOINT);

    addButtonCallbacks();

    // Screen
    screen.setup();
    screen.rows3("Pantalla ok", nullptr, nullptr);
    delay(1200);

    // Sensor
    uartSensor.begin(CO2SENSOR_BAUDRATE);
    co2sensor.begin(uartSensor);
    co2sensor.autoCalibration(false);
    screen.rows3(nullptr, "Sensor ok", nullptr, false);
    delay(2000);

    // Client
    addSensorClientCallbacks();
    addOTAcallbacks();
    sensorClient.setup(STASSID, STAPSK);
    sensorClient.setRequiredWarmUp(60);
    screen.rows3(nullptr, nullptr, "Cliente ok", false);
    delay(2000);

    splashSensorInfo();
    delay(2000);

    splashServerInfo();
    delay(2000);

    long countdown = sensorClient.getPendingWarmUp();
    while (countdown > 0) {
        updateCountdown(countdown);
        delay(100);
        countdown = sensorClient.getPendingWarmUp();
    }

    sensorClient.userConfig.screenMode = SCREEN_MODE::ENABLED;
    sensorClient.userConfig.lastCalibration = memory.content.lastCalibration;
    sensorClient.userConfig.firmwareVersion = FWV;

    sensorClient.sendDeviceInfo();

    #ifdef DEBUG
      Serial.begin(9600);
    #endif
    info_print("CO2-Sensino ready..");
}


void loop() {
    static sensino::Record<MyRecord> lastRecord;

    if (!loopPeriod) {
        return;
    }

    buttonObject.loop();
    if (buttonObject.getState() != BUTTON_STATE::RELEASED) {
        return;
    }

    sensorClient.loop();
    lastRecord = sensorClient.getLastRecord();

    switch (sensorClient.userConfig.screenMode) {
        case (SCREEN_MODE::ENABLED):
            updateScreen(lastRecord.userRecord.co2,
                         lastRecord.userRecord.temperature,
                         sensorClient.getMeasureState(), sensorClient.getSendState(),
                         sensorClient.isBufferFull(),
                         true
            );
            break;
        case (SCREEN_MODE::MINIMUM):
            updateScreen(lastRecord.userRecord.co2,
                         lastRecord.userRecord.temperature,
                         sensorClient.getMeasureState(), sensorClient.getSendState(),
                         sensorClient.isBufferFull(),
                         false
            );
            break;
        case (SCREEN_MODE::DISABLED):
            screen.clear();
            break;
    }
}


int main() {
    setup();
    loop();
}
