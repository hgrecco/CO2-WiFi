CO2-Dashboard
=============

Plataforma para
- Cliente WeMos para sensores de CO2.
- Servidor 


Cliente
-------

Escrito en C++ usando la librería [Sensino](https://github.com/hgrecco/sensino)
(entre otras). 
Envía información de los sensores al un servidor web en formato JSON. 
Envía además información de configuración actual del dispositivo
en los headers de cada request.

Algunos aspectos del cliente pueden ser controlados desde el
servidor tales como el período de medición y lo que muestra
la pantalla. Además, puede iniciarse una recalibración desde
el servidor. Permite la actualización de firmware a distancia 
usando over the air update (OTA).


Servidor
--------

Escrito en Python usando las librerías FLASK y DASH (entre otras).
Consta de 3 partes:
1. Una API JSON para recibir y guardar información de los dispositivos.
2. Una interfaz web para ver los dispositivos, configurarlos y exportar 
   la información.
3. Una interfaz web para mostrar gráficamente los datos.


Como usar
---------

**Servidor**

Instrucciones
1. Utilizar Python 3.9 o superior
2. Instalar los requerimientos con `pip install -r requirements.txt`
3. Ajustar configuración en `secrets.py`
4. Ejecutar `python app.py`


**Cliente**

El firmware esta pensado para un dispositivo armado como los que 
muestra Jorge Aliaga en su sitio [web](https://jorgealiaga.com.ar/?page_id=2864)

Hay dos firmware disponibles:
1. co2-sensino-init: se flash
2. co2-sensino: se compila y se sube al servidor. Se instala via OTA.

Instrucciones:

0. Copiar la libreria [sensino](https://github.com/hgrecco/sensino) en una carpeta src 
   de `co2-sensino` y `co2-sensino-init`
1. Ajustar configuración en `co2-sensino/config.h` y `co2-sensino/secrets.h`, 
   y copiarlos (o hacer un soft link) en `co2-sensino-init`
2. Abrir `co2-sensino.ino` y definir la version de firmware. Ejemplo: `2021071601`
3. Compilar `co2-sensino.ino` (`Sketch > Export compiled binary`) y copiar el binario resultante
   a la carpeta para firmware en el servidor usando la version como nombre.
   Ejemplo: `2021071601.ino.bin`
4. Abrir `co2-sensino-init.ino` y definir el numero de serie del dispositivo. Ejemplo: `1`
5. Con el dispositivo conectado, compilar y subir `co2-sensino-init.ino` (`Sketch > Upload`).

Luego:
- Para cada nuevo dispositivo, repetir 4 y 5.
- Para generar un nuevo firmware, modificar el código y luego repetir (1,) 2 y 3.
  Usar un numero mayor para el firmware version
- Para actualizar el dispositivo con este firmware, hacerlo desde la interfase web.


Seguridad
---------

1. Realizar todas las comunicaciones sobre `https`
2. Firmar las actualizaciones: [instrucciones](https://arduino-esp8266.readthedocs.io/en/latest/ota_updates/readme.html#advanced-security-signed-updates)   
3. Utilizar un `API_KEY`
4. Agregar un sistema de autenticación.