# CajasVariables (complemento de RobotStudio 2026)

Hace que la caja del 3D tenga el tamaño de cada caja de `caja.csv` y que las ya depositadas se queden en la mesa.

## Qué hace
La estación tiene una sola pieza, `CajaGrande` (cubo de 200 mm), que los 12 `Positioner` `PosCaja01..12` recolocan para cada caja. El complemento mira su pose cada 50 ms:
- Cuando llega a la pose de uno de los `Positioner` (se leen de sus propiedades `Position` y `Orientation`) es una **caja nueva**. Su posición en la tanda sale de contar esas llegadas.
- Cambia la geometría de `CajaGrande` por una caja de largo x ancho x alto de la línea correspondiente de `caja.csv`. El centro (x, y) y la cara de abajo quedan donde estaban en la caja original, así que el `Positioner`, el sensor del final de la cinta y el agarre no cambian.
- Antes, deja una **copia** de la caja anterior en la última pose en la que se vio fuera de la cinta, que es donde la dejó la pinza en la mesa (`CajaDejada_N`).
- `caja.csv` nuevo (RAPID lo reescribe al empezar cada tanda) = tanda nueva: se empieza por la primera línea y se borran las copias.
- **Fin de la tanda:** al terminar la última caja, RAPID (`MarcarFinTanda`, en simulación) escribe `fin_tanda.txt` en `HOME`, junto a `caja.csv`. El complemento ve que cambia la fecha del fichero, espera 3 s (`EsperaFinS`, para que se vea el resultado), borra las copias de la mesa y **oculta** `CajaGrande` (la última caja). La siguiente caja que se coloque la vuelve a mostrar. Si se aborta la tanda no hay marca: las cajas siguen hasta la tanda siguiente. Un `fin_tanda.txt` que ya estuviera al cargar el complemento no cuenta.

El tamaño lo pone RAPID al escribir `caja.csv` (`cajaLargo/Ancho/Alto`, `cajasVariables`, desde la app o el editor de datos); el PC planifica con las mismas medidas. El fichero no se edita nunca a mano.

## Instalarlo
Paquete `TFM.CajasVariables-1.1.rspak` (en `Desktop\TFM_RAPID\Addin`): RobotStudio → pestaña **Add-Ins** → **Install Package** → ese fichero. Instalado desde `.rspak` no se carga solo: en el panel Add-Ins sale con ⊗ y hay que pulsarlo para cargarlo (✓); el panel tiene un ajuste de carga automática (opciones de RobotStudio). Es un complemento sin ventana. `Dependencies` es `None` para que pueda cargarse sin estación abierta: el código vigila `Project.ActiveProject` y no toca la estación hasta que la hay. Comprobado fuera de RobotStudio: la DLL carga en .NET 10 con las DLL de RobotStudio y `AddinMain` se ejecuta. Escribe en Output y en `%TEMP%\CajasVariables.log`.

Sin instalar, abriendo RobotStudio con el complemento (carpeta `Desktop\TFM_RAPID\Addin\CajasVariables`):
```
& "C:\Program Files (x86)\ABB\RobotStudio 2026\Bin\RobotStudio.exe" /addin:"C:\Users\Viktor\Desktop\TFM_RAPID\Addin\CajasVariables\CajasVariables.rsaddin"
```

Ruta de `caja.csv`: la primera línea de `ruta_caja_csv.txt` (junto a la DLL); si no existe, la variable de entorno `CAJAS_CSV`; si tampoco, el `caja.csv` más reciente de la carpeta `HOME` de algún controlador virtual de `Documents\RobotStudio\Projects`.

Mensajes en la ventana **Output** de RobotStudio y en `%TEMP%\CajasVariables.log` (prefijo `Cajas variables:`): al abrir la estación (Positioner encontrados, medidas de la caja original y ruta del csv) y en cada caja (`caja N: …`). Los errores salen una sola vez.

## Compilar y probar
Se compila con el SDK 9 contra las DLL del runtime .NET 10 y de `...\RobotStudio 2026\Bin` (RobotStudio 2026 va sobre .NET 10; no hace falta instalar el SDK 10):
```
cd robotica\rapid\estacion\CajasVariables
dotnet build -c Release
```
Deja `bin\Paquete\CajasVariables.dll` y el `.rsaddin`. Para generar el paquete de instalacion (con la herramienta de ABB del SDK):
```
"C:\Program Files (x86)\ABB\SDK\RobotStudio 2024 SDK\RspakTool.exe" -i CajasVariables.rspakspec -o C:\Users\Viktor\Desktop\TFM_RAPID\Addin\
```
Sin el SDK instalado, se hace igual con cualquier `RspakTool`. `Logica.cs` (lectura del csv y detección de cajas) no usa RobotStudio y tiene su consola de pruebas: `dotnet run --project Pruebas -c Release`. Las dos las lanza `tests/test_cajas_variables.py`.

## Sin comprobar
Solo está compilado y probado `Logica.cs`; el resto (que `CreateSolidBox` ponga la caja donde se espera —si no, lo corrige una vez y lo avisa—, que `Copy()` deje la copia en su sitio, que cambiar la geometría con la simulación en marcha no dé problemas, el `DispatcherTimer`) está por probar en RobotStudio.
