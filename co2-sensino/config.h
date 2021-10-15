// Un número que indica que no fue calibrado aún.
#define NOCAL 42
// Tamaño del buffer donde se guardan los datos hasta que pueden ser enviados..
#define BUFFER_SIZE 1000
// Tiempo entre mediciones (en segundos)
#define RECORD_PERIOD_SEC 60

// Tiempo que debe estar encendido el dispositivo antes de calibrar.
#define CO2SENSOR_CALIBRATION_WAIT_MIN 30

// Modelo Blanco
//#define CO2SENSOR_RX_PIN 13 // Rx pin which the MHZ19 Tx pin is attached to
//#define CO2SENSOR_TX_PIN 15 // Tx pin which the MHZ19 Rx pin is attached to
//#define BUTTON_PIN 0
//#define FAN_PIN 2

// Modelo Negro
// MH-Z19 Serial baudrate (en general no es necesario no cambiar)
#define CO2SENSOR_BAUDRATE 9600
// Pin Rx de la WeMos al cual está conectado el pin MHZ19 Tx
#define CO2SENSOR_RX_PIN 13
// Pin Tx de la WeMos al cual está conectado el pin MHZ19 Rx
#define CO2SENSOR_TX_PIN 12
// Pin de la WeMos al cual está conectado el botón.
#define BUTTON_PIN 0
// Pin de la WeMos al cual está conectado el ventilador.
#define FAN_PIN 2
