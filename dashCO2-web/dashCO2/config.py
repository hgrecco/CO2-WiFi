"""
    dashCO2.config
    ~~~~~~~~~~~~~~

"""

# Base datos sqlite. No requiere un servidor
SQLALCHEMY_DATABASE_URI = "sqlite:////data/co2.db"

# Base de datos en memoria, no es persistente. Usar para pruebas.
# SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

# Base de datos postgres. Hay que configurar usuario, clave,
# puerto y base de datos.
# SQLALCHEMY_DATABASE_URI= "postgresql://usuario:clave@url:puerto/db"

# Carpeta donde están los firmware de los dispositivos.
FIRMWARE_FOLDER = "/firmware"


# Rangos de alerta
class RANGES:
    OK = 400
    WARNING = 700
    DANGER = 1000


# Tiempo para mostrar en los gráficos (en segundos).
DISPLAY_LEN_SEC = 3 * 60 * 60

# Tiempo sin datos para considerar que el sensor esta offline (en segundos).
CONSIDER_OFFLINE_SEC = 10 * 60

# Huso horario donde estan los sensores,
# tomado de https://www.iana.org/time-zones
TIMEZONE = "America/Argentina/Buenos_Aires"

# Un número que indica que un dispositivo fue calibrado aún.
# (debe ser igual al del cliente).
NO_CAL = 42
