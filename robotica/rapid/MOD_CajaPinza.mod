MODULE MOD_CajaPinza
    ! Celda de cajas con GoFa y pinza. El EGM lleva todo el movimiento de cada caja (una sesion
    ! por caja). RAPID solo hace: posicion segura, colocar la caja (en simulacion), pinza, avisos
    ! y, en simulacion, generar la lista de cajas (caja.csv).
    !
    ! Se carga como modulo normal en las DOS tareas, T_ROB1 y T_COM. En las dos la entrada es
    ! "main", que reparte el trabajo: T_ROB1 (la tarea con robot) hace main_movimiento y T_COM
    ! hace main_pinza. Las PERS de abajo son compartidas entre tareas.
    !
    ! Senales (cfg/EIO/EIO.cfg y conexiones del Station Logic, ver docs/manual_robotstudio_cajapinza.md):
    !   PinzaCerrar (DO)   cierra la pinza. En simulacion, agarra la caja.
    !   PinzaCerrada (DI)  confirmacion de agarre.
    !   CajaEnRecogida (DI) la caja esta lista para pinzar. En el laboratorio se fuerza a mano;
    !                      en simulacion la activa el sensor de final de cinta (FinCinta_2).
    !   CintaMover (DO)    solo simulacion: mueve la cinta (LinearMover).
    !   CajaPos01..12 (DO) solo simulacion: cada una pone la caja al INICIO de la cinta con un giro.
    !   FinCajaEGM (DO)    sin uso: la sesion EGM termina por convergencia (ver ventanaPos). Sigue
    !                      definida en EIO.cfg y se pone a 0 al empezar.
    !
    ! Protocolo por socket: sin separadores, un mensaje por turno (el PC espera la respuesta).
    !   PC -> RAPID: cerrar, abrir, fin_caja, fin_programa, lote, mesa, recogida, agarre, celda, giro:<grados>,
    !                camara, camara_lista:<k>:<nombres>, camara_info:<n>:<estado>
    !   RAPID -> PC: cerrada, abierta, fin_ok, fallo_pinza, fallo_egm, lote:<n>:<sim|real>,
    !                mesa:<x0>:<y0>:<largo>:<ancho>:<z>:<hueco>:<egmMaxPos>:<alcanceMax>, giro_ok, giro_mal,
    !                recogida:<modo>:<x>:<y>:<tolX>:<tolY>:<offX>:<offY>:<offGiro>:<tMaxCamara>,
    !                agarre:<modo>:<porc>:<hund>:<minimo>:<solape>:<apertura>:<grosor>:<giroPinza>,
    !                celda:<zCinta>:<margenAprox>:<tcpZ>:<seguroX>:<seguroY>:<seguroZ>:<velocidad>:<zMinima>
    ! fin_caja: T_COM espera a que T_ROB1 cierre la sesion EGM (el robot queda convergido en la salida
    ! tiempoConv segundos) y contesta fin_ok; si no se cierra a tiempo, contesta fallo_egm.
    ! lote: el PC pregunta cuantas cajas tiene la tanda y en que modo esta RAPID (los ajusta la app del
    ! FlexPendant), para que el PC no discrepe. mesa: la zona de la mesa donde se dejan las cajas (tambien de
    ! la app) y los limites del robot; con ella el PC reparte las cajas en una cuadricula. recogida, agarre y celda:
    ! los ajustes de puesta en marcha (ventana Parametros de la app, PERS de abajo). giro:<grados>: el PC cuenta el giro de la caja que ha
    ! leido (en simulacion, del CSV; en real, de la camara); la app lo muestra junto al que puso RAPID.
    ! Si SocketReceive dejara algun caracter de mas en el texto, revisar la comparacion
    ! en la primera prueba de socket.
    !
    ! Panel del FlexPendant: la app CajaPinza (robotica/flexpendant/CajaPinza) ajusta la tanda y da la
    ! orden de empezar cada caja a traves de las PERS hmi* de abajo. Con usarHmi := FALSE el modulo
    ! funciona sin ella, como antes.

    ! ---- Configuracion ----
    CONST string ipPC := "127.0.0.1";
    CONST num puertoPC := 5010;
    CONST string nombreUdp := "EGMsensor";

    ! Caja de referencia, en mm: la mayor caja que se espera (el 3D de la simulacion es un cubo de 200 mm).
    ! En simulacion RAPID escribe solo caja.csv (largo;ancho;alto;giro, una linea por caja; nunca se edita a
    ! mano). Con cajasVariables = TRUE (por defecto) cada caja mide entre el 60 y el 100 % del largo y el
    ! ancho, y entre el 50 y el 100 % del alto; con FALSE todas miden lo que dicen estas tres.
    ! El 3D toma esas medidas con el complemento de RobotStudio CajasVariables (lee caja.csv); sin el, la
    ! caja del 3D sigue siendo de 200 mm. En real no se usan para mover nada:
    ! la app las usa para estimar cuantas cajas caben en la mesa. Siempre largo >= ancho.
    PERS num cajaLargo := 200;
    PERS num cajaAncho := 200;
    PERS num cajaAlto := 200;
    PERS bool cajasVariables := TRUE;
    ! Giros posibles de la caja: 12 posiciones de 15 grados, de -90 a 75. La posicion k
    ! corresponde a la senal CajaPosKK y al Positioner PosCajaKK de la estacion.
    CONST num nGiros := 12;
    CONST num giroMin := -90;
    CONST num giroPaso := 15;
    ! Maximo de cajas por ejecucion (tamano de la lista indiceGiro).
    CONST num maxCajas := 100;

    ! Fin de la sesion EGM por convergencia. egm_minmax NO limita el movimiento (el TFG, con +-1, movia
    ! 350 mm): es el criterio de convergencia. El robot esta convergido cuando su pose esta dentro de la
    ! ventana respecto a la consigna del PC, y EGMRunPose termina cuando lo esta tiempoConv segundos
    ! seguidos. El PC deja la pinza quieta en la salida de la mesa y pide fin_caja: asi el EGM se cierra
    ! solo al acabar cada caja. (EGMStop desde una interrupcion no lo cerraba: el programa seguia dentro
    ! de EGMRunPose, sin movimiento y con el EGM abierto.)
    ! Posicion (mm): mayor que la tolerancia con la que el PC da por alcanzado un punto (2 mm) y menor
    ! que el retraso del robot en marcha (v x 0,2 s: 20 mm a 100 mm/s), para que la sesion no termine
    ! con el robot en movimiento.
    CONST egm_minmax ventanaPos := [-3, 3];
    ! Rotacion, como MOD_EGM. La unidad de egm_minmax para rotaciones no esta confirmada: en grados
    ! exige +-1 grado en reposo y en radianes no limita; en los dos casos el robot parado la cumple.
    CONST egm_minmax ventanaRot := [-1, 1];
    ! Segundos seguidos dentro de la ventana para cerrar la sesion. Tiene que ser mayor que cualquier
    ! parada con la pinza quieta en mitad de la caja (cerrar y abrir la pinza: en simulacion menos de
    ! 0,5 s); si una parada dura mas, la sesion terminaria antes de tiempo. T_COM espera tiempoConv + 10 s.
    ! La ajusta la app (ventana Parametros, Tiempos).
    PERS num tiempoConv := 2.5;

    ! ---- Compartidas por T_ROB1 y T_COM ----
    PERS num cajaNum := 0;
    PERS num nCajas := 1;
    PERS bool modoSimulacion := TRUE;
    ! T_ROB1 la pone a TRUE cuando ha parado el EGM; T_COM la espera.
    PERS bool egmParado := FALSE;
    ! T_COM la pone a TRUE al recibir fin_caja; T_ROB1 la pone a FALSE al empezar cada sesion EGM. Si la
    ! sesion termina sin ella, el PC no ha dirigido la caja (no esta, o cuenta otras cajas): RAPID se
    ! para en vez de recorrer las cajas sin agarrarlas.
    PERS bool finCajaRecibido := FALSE;
    ! Ayudas de simulacion. indiceFijo: 0 = giros al azar (por defecto); 1..12 = todas las cajas con
    ! ese giro (7 = 0 grados). semillaGiros: cambia la secuencia al azar.
    PERS num indiceFijo := 0;
    PERS num semillaGiros := 1234;

    ! ---- Panel del FlexPendant (app CajaPinza) ----
    ! La app lee y escribe estas PERS por RWS (con nCajas, modoSimulacion, indiceFijo y semillaGiros,
    ! de arriba). Si la app no esta instalada hay que poner usarHmi := FALSE: con TRUE el programa
    ! espera INICIAR para siempre. Con FALSE no espera nada de la app: en simulacion hace una caja
    ! tras otra con el sensor, y en real espera la senal CajaEnRecogida, como antes.
    PERS bool usarHmi := TRUE;
    ! Momento en el que esta la celda (valores FASE_*). T_ROB1 y T_COM lo van poniendo; la app lo muestra.
    PERS num hmiFase := 0;
    ! App -> RAPID. Las pone a TRUE la app; T_ROB1 las devuelve a FALSE en cuanto las usa.
    PERS bool hmiIniciar := FALSE;
    PERS bool hmiCajaEnPosicion := FALSE;
    ! App -> RAPID. TRUE: antes de cada caja espera el boton CAJA EN POSICION (en simulacion, despues de
    ! que el sensor de la cinta la vea). FALSE: sin boton; en simulacion arranca el EGM al llegar la caja
    ! al sensor y en real al activarse CajaEnRecogida.
    PERS bool hmiConfirmar := TRUE;
    ! T_COM -> app: el socket con el PC esta abierto.
    PERS bool hmiPcConectado := FALSE;
    ! Giro (grados) de la caja que RAPID ha puesto en la cinta (solo simulacion) y giro que ha leido el
    ! PC. sinGiro = todavia no se sabe.
    PERS num hmiGiroCaja := 999;
    PERS num hmiGiroPc := 999;
    ! Ultimo aviso (el mismo texto que sale por TPWrite en el FlexPendant, si hmiMensajes lo permite).
    PERS string hmiMensaje := "";
    ! App -> RAPID. TRUE: los avisos de RAPID salen tambien en el FlexPendant (TPWrite); FALSE: solo en la app.
    ! No afecta a los mensajes del sistema (errores y eventos del controlador). Por defecto, apagado.
    PERS bool hmiMensajes := FALSE;
    ! Medidas de la caja en curso (simulacion), para la app.
    PERS string hmiCaja := "";

    ! ---- Camara de ensayo (solo Real): carpeta de fotos que lee el PC en vez de la camara ----
    ! La app elige la carpeta de una lista que da el PC (camaraLista1..3: nombres separados por ';'); el PC la abre, cuenta las fotos y
    ! avisa (camaraFotos y camaraEstado). "" = la camara de la configuracion del PC. Las escribe la app (camaraCarpeta) y T_COM (el resto).
    PERS string camaraCarpeta := "";
    PERS string camaraLista1 := "";
    PERS string camaraLista2 := "";
    PERS string camaraLista3 := "";
    PERS num camaraFotos := 0;
    PERS string camaraEstado := "";

    ! ---- Mesa de deposito (la ajusta la app; el PC la pide con 'mesa') ----
    ! Zona de la mesa donde se dejan las cajas, en mm respecto a la base del robot: (mesaX0, mesaY0) es la
    ! esquina de x e y minimas, mesaLargo se extiende en x y mesaAncho en y, y mesaZ es la superficie.
    ! mesaHueco separa las cajas entre si y del borde (mayor que el grosor de las mordazas). Por defecto,
    ! la mesa de la simulacion (mesa_marron colocada en x de -900 a 300, y de 150 a 1150, superficie a 320:
    ! Set Position -700, 350, 500 mm en RobotStudio; en la base antigua era -1120, 342). El PC deja
    ! todas las cajas ordenadas en una cuadricula, sin girar, y salta los huecos a los que el robot no llega.
    PERS num mesaX0 := -900;
    PERS num mesaY0 := 150;
    PERS num mesaLargo := 1200;
    PERS num mesaAncho := 1000;
    PERS num mesaZ := 320;
    PERS num mesaHueco := 40;
    ! Limites del robot que el PC aplica a todos los puntos (la app los muestra, no los cambia).
    ! egmMaxPos: el controlador para el EGM si la referencia se aleja mas de esto de la posicion de espera
    ! (\MaxPosDeviation de EGMActPose). Con 1000 solo llegan los huecos de la mesa mas cercanos; el valor por
    ! defecto, 1500, da sitio a unas 8 cajas de 200 mm, pero esta sin comprobar que el controlador lo acepta
    ! (si no, ponerlo a 1000 aqui o en la app).
    ! alcanceMax: radio maximo, en horizontal desde el eje de la base, hasta el que llega la pinza con
    ! comodidad (comprobado con la cinematica del GoFa hasta TCP z = 585).
    PERS num egmMaxPos := 1500;
    PERS num alcanceMax := 790;

    ! ---- Puesta en marcha (ventana Parametros de la app; el PC los pide con 'recogida', 'agarre' y 'celda') ----
    ! Medidas en mm respecto a la base del robot, grados y segundos. Se ajustan antes de INICIAR TANDA.
    ! Recogida. recogidaModo: 0 = fija, 1 = camara (solo real; en simulacion el punto lo da el sensor de la
    ! cinta, que usa recogidaX). Fija: el centro de la caja es (recogidaX, recogidaY) para todas. Camara: el que
    ! mide la camara mas camaraOffsetX/Y, solo si cae a menos de recogidaTolX/Y de (recogidaX, recogidaY); si no,
    ! el PC no se mueve. camaraOffsetGiro se suma al giro que lee la camara. tMaxCamara: espera maxima a una
    ! deteccion. zCinta: altura de la superficie de la cinta.
    PERS num recogidaModo := 0;
    PERS num recogidaX := 700;
    PERS num recogidaY := 0;
    PERS num recogidaTolX := 50;
    PERS num recogidaTolY := 50;
    PERS num camaraOffsetX := 0;
    PERS num camaraOffsetY := 0;
    PERS num camaraOffsetGiro := 0;
    PERS num tMaxCamara := 5;
    PERS num zCinta := 220;
    ! Agarre. Altura h del punto de agarre sobre la base de la caja. agarreModo: 0 = porcentaje (h = alto x
    ! agarrePorcentaje / 100; 50 = el centro), 1 = desde la tapa (h = alto - agarreHundimiento). Despues h no baja de
    ! agarreMinimo (los dedos sobresalen bajo el TCP) y la caja se rechaza si alto < solapeMinimo o si su lado
    ! agarrado (el ancho) es mayor que aperturaPinza. aperturaPinza y grosorDedo: 0 = sin comprobar (grosorDedo
    ! tiene que caber en mesaHueco). giroPinza: giro extra de las mordazas respecto a la caja. tcpZ: distancia de la
    ! brida al punto de agarre (el TCP z de herrPinza). margenAproximacion: altura sobre la caja al acercarse.
    PERS num giroPinza := 0;
    PERS num agarreModo := 0;
    PERS num agarrePorcentaje := 50;
    PERS num agarreHundimiento := 30;
    PERS num agarreMinimo := 10;
    PERS num solapeMinimo := 10;
    PERS num aperturaPinza := 0;
    PERS num grosorDedo := 0;
    PERS num tcpZ := 147;
    PERS num margenAproximacion := 65;
    ! Tiempos (s). tAntesAgarrar: pausa entre CAJA EN POSICION y empezar el movimiento. tAgarre y tSuelta: pausa
    ! despues de que la pinza confirme el cierre o la apertura, antes de que el PC siga. tMaxPinza: espera maxima
    ! a PinzaCerrada. tMaxCaja: espera maxima a CajaEnRecogida (0 = sin limite).
    PERS num tAntesAgarrar := 0;
    PERS num tAgarre := 0;
    PERS num tSuelta := 0;
    PERS num tMaxPinza := 3;
    PERS num tMaxCaja := 40;
    ! Movimiento y seguridad. velocidad: mm/s maximos del TCP que manda el PC (100 = el tope del puente, que
    ! es config.celda.json: paso_mm 0.4). zMinima: suelo del TCP (0 = el menor de zCinta y mesaZ). seguroX/Y/Z:
    ! punto de espera (TCP) donde empieza cada sesion EGM y a donde vuelve el robot entre cajas.
    PERS num velocidad := 100;
    PERS num zMinima := 0;
    PERS num seguroX := 600;
    PERS num seguroY := -6.5;
    PERS num seguroZ := 543;

    CONST num sinGiro := 999;
    ! Momentos de la celda. La app (logica.js) lleva la misma tabla: si se cambia aqui, cambiarla alli
    ! (hay una prueba que lo comprueba).
    CONST num FASE_PARADO := 0;
    CONST num FASE_ESPERA_INICIAR := 1;
    CONST num FASE_A_SEGURA := 2;
    CONST num FASE_COLOCANDO := 3;
    CONST num FASE_CINTA := 4;
    CONST num FASE_ESPERA_CAJA := 5;
    CONST num FASE_EGM_ABIERTO := 6;
    CONST num FASE_AGARRADA := 7;
    CONST num FASE_SOLTADA := 8;
    CONST num FASE_CERRANDO_EGM := 9;
    CONST num FASE_VUELTA := 10;
    CONST num FASE_FIN := 11;
    CONST num FASE_ERROR := 99;

    ! ---- Posicion segura y herramienta ----
    ! Punto de espera sobre la cinta: 300 mm mas alto que el pAprox de la prueba de EGM (390 en la
    ! brida), porque a esa altura la pinza quedaba dentro de la caja que llega (16-nov). A 543 mm de TCP
    ! la pinza queda 123 mm sobre el techo de la caja (420). Es donde arranca cada sesion EGM y a donde
    ! vuelve el robot entre cajas. pStart: 740 en la brida, con tool0.
    ! pSeguro: TCP de la pinza (herrPinza), solo para la comprobacion de alcance.
    VAR robtarget pSeguro := [[600,-6.5,543],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    VAR robtarget pStart := [[600,-6.5,740],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    ! pSeguroBrida = pSeguro en la brida (543 + 147 mm del TCP de la pinza). pStart, 50 mm mas arriba. Los tres se
    ! recalculan al empezar cada tanda con seguroX/Y/Z y tcpZ (AplicarSeguro).
    VAR robtarget pSeguroBrida := [[600,-6.5,690],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    PERS tooldata herrPinza := [TRUE,[[0,0,147],[1,0,0,0]],[0.5,[0,0,50],[1,0,0,0],0,0,0]];
    CONST pose pose_cero := [[0,0,0],[1,0,0,0]];

    ! ---- Solo T_ROB1 ----
    VAR egmident egmID;
    ! Articulaciones del robot en pSeguroBrida, tomadas tras la primera llegada: a ellas vuelve entre cajas.
    VAR jointtarget jSeguroBrida;
    VAR num indiceGiro{100};
    VAR num dimLargo{100};
    VAR num dimAncho{100};
    VAR num dimAlto{100};

    ! Entrada de las dos tareas.
    PROC main()
        IF TaskRunRob() THEN
            main_movimiento;
        ELSE
            main_pinza;
        ENDIF
    ENDPROC

    ! ---- T_ROB1: cajas una a una ----
    PROC main_movimiento()
        VAR num i;
        VAR num k;
        VAR num semilla;
        VAR iodev fichero;
        VAR bool sinCaja;
        VAR num largoCaja;
        VAR num anchoCaja;
        VAR num altoCaja;
        VAR num cambio;

        hmiMensaje := "";
        hmiCaja := "";
        hmiGiroCaja := sinGiro;
        hmiGiroPc := sinGiro;
        cajaNum := 0;
        hmiIniciar := FALSE;
        hmiCajaEnPosicion := FALSE;
        hmiFase := FASE_ESPERA_INICIAR;
        IF usarHmi THEN
            ! Aqui la app ajusta la tanda (nCajas, modoSimulacion, giros, hmiConfirmar) y pulsa INICIAR.
            ! Los ajustes se leen despues de esa pulsacion.
            WaitUntil hmiIniciar;
            hmiIniciar := FALSE;
        ENDIF
        hmiFase := FASE_A_SEGURA;

        IF nCajas < 1 THEN
            nCajas := 1;
        ENDIF
        IF nCajas > maxCajas THEN
            nCajas := maxCajas;
        ENDIF

        IF modoSimulacion THEN
            ! Generador lineal congruente: x := (1021 x + 11) mod 8192. Periodo completo y
            ! cuentas exactas en num. No se usa Rand porque no consta que exista en RW 7.12.
            semilla := semillaGiros;
            Open "HOME:/caja.csv", fichero \Write;
            FOR i FROM 1 TO nCajas DO
                semilla := (semilla * 1021 + 11) MOD 8192;
                IF indiceFijo >= 1 AND indiceFijo <= nGiros THEN
                    k := indiceFijo;
                ELSE
                    k := ((semilla DIV 16) MOD nGiros) + 1;
                ENDIF
                indiceGiro{i} := k;
                IF cajasVariables THEN
                    ! Medidas distintas en cada caja, del mismo generador (otros digitos de la semilla).
                    largoCaja := cajaLargo * (60 + 10 * (semilla MOD 5)) / 100;
                    anchoCaja := cajaAncho * (60 + 10 * ((semilla DIV 5) MOD 5)) / 100;
                    altoCaja := cajaAlto * (50 + 10 * ((semilla DIV 25) MOD 6)) / 100;
                ELSE
                    largoCaja := cajaLargo;
                    anchoCaja := cajaAncho;
                    altoCaja := cajaAlto;
                ENDIF
                IF anchoCaja > largoCaja THEN
                    ! El lado largo va siempre como largo (el giro es el del lado largo).
                    cambio := largoCaja;
                    largoCaja := anchoCaja;
                    anchoCaja := cambio;
                ENDIF
                dimLargo{i} := largoCaja;
                dimAncho{i} := anchoCaja;
                dimAlto{i} := altoCaja;
                Write fichero, NumToStr(largoCaja, 1) + ";" + NumToStr(anchoCaja, 1) + ";" + NumToStr(altoCaja, 1) + ";" + NumToStr(giroMin + (k - 1) * giroPaso, 1);
            ENDFOR
            Close fichero;
            SetDO CintaMover, 0;
        ENDIF
        SetDO FinCajaEGM, 0;

        cajaNum := 0;
        AplicarSeguro;
        ! Igual que MOD_EGM_prueba: pStart y luego pAprox (pSeguroBrida), con tool0.
        MoveJ pStart, v100, fine, tool0;
        MoveJ pSeguroBrida, v100, fine, tool0;
        jSeguroBrida := CJointT();

        WHILE cajaNum < nCajas DO
            hmiGiroPc := sinGiro;
            IF modoSimulacion THEN
                ! Pone la caja al inicio de la cinta con el giro del CSV y mueve la cinta hasta
                ! que el sensor de final de cinta activa CajaEnRecogida.
                hmiGiroCaja := giroMin + (indiceGiro{cajaNum + 1} - 1) * giroPaso;
                hmiCaja := NumToStr(dimLargo{cajaNum + 1}, 0) + " x " + NumToStr(dimAncho{cajaNum + 1}, 0) + " x " + NumToStr(dimAlto{cajaNum + 1}, 0) + " mm";
                hmiFase := FASE_COLOCANDO;
                ColocarCaja indiceGiro{cajaNum + 1};
                hmiFase := FASE_CINTA;
                SetDO CintaMover, 1;
                IF tMaxCaja > 0 THEN
                    WaitDI CajaEnRecogida, 1 \MaxTime:=tMaxCaja \TimeFlag:=sinCaja;
                ELSE
                    WaitDI CajaEnRecogida, 1;
                    sinCaja := FALSE;
                ENDIF
                SetDO CintaMover, 0;
                IF sinCaja THEN
                    hmiFase := FASE_ERROR;
                    Aviso "La caja no ha llegado al sensor de la cinta";
                    Stop;
                ENDIF
            ELSE
                hmiGiroCaja := sinGiro;
            ENDIF

            ! Caja en posicion. Con la app, el EGM no arranca hasta pulsar CAJA EN POSICION (en
            ! simulacion, el boton se espera despues de que el sensor haya visto llegar la caja). Sin boton:
            ! en simulacion basta el sensor, que ya ha actuado, y en real se espera CajaEnRecogida, que en
            ! el laboratorio se fuerza a mano.
            hmiCajaEnPosicion := FALSE;
            hmiFase := FASE_ESPERA_CAJA;
            IF usarHmi AND hmiConfirmar THEN
                WaitUntil hmiCajaEnPosicion;
                hmiCajaEnPosicion := FALSE;
            ELSEIF NOT modoSimulacion THEN
                EsperarCajaReal;
            ENDIF
            IF tAntesAgarrar > 0 THEN
                WaitTime tAntesAgarrar;
            ENDIF

            EGMReset egmID;
            EGMGetId egmID;
            EGMSetupUC ROB_1, egmID, "default", nombreUdp \Pose;
            EGMActPose egmID, pose_cero, EGM_FRAME_BASE, pose_cero, EGM_FRAME_BASE
                \x:=ventanaPos \y:=ventanaPos \z:=ventanaPos
                \Rx:=ventanaRot \Ry:=ventanaRot \Rz:=ventanaRot
                \LpFilter:=20, \SampleRate:=4, \MaxPosDeviation:=egmMaxPos, \MaxSpeedDeviation:=1000;

            ! La sesion dura hasta que el robot queda convergido en la consigna del PC durante tiempoConv
            ! segundos seguidos (ver ventanaPos). En marcha no lo esta (va retrasado), asi que solo ocurre
            ! cuando el PC deja la pinza quieta en la salida y pide fin_caja. Despues se cierra con
            ! EGMReset y se avisa a T_COM (egmParado).
            egmParado := FALSE;
            finCajaRecibido := FALSE;
            hmiFase := FASE_EGM_ABIERTO;
            EGMRunPose egmID, EGM_STOP_HOLD \x \y \z \Rx \Ry \Rz \CondTime:=tiempoConv \RampInTime:=0.05;
            EGMReset egmID;
            egmParado := TRUE;
            Nota "EGM cerrado (caja " + NumToStr(cajaNum + 1, 0) + ")";
            IF NOT finCajaRecibido THEN
                ! El EGM termino solo (robot quieto tiempoConv s) sin que el PC pidiera fin_caja.
                hmiFase := FASE_ERROR;
                Aviso "El PC no ha dirigido la caja " + NumToStr(cajaNum + 1, 0) + ": paro. Revisa el PC.";
                Stop;
            ENDIF

            ! Vuelta a pSeguroBrida entre cajas, por articulaciones a las que tenia al empezar: el brazo
            ! recupera su configuracion. Con MoveJ y ConfJ Off el controlador elegia otra configuracion
            ! del brazo y acababa con "Joint Out of Range" (15-nov). El PC ya ha subido la pinza por
            ! encima de la caja, y el barrido articular pasa a mas de 48 mm sobre ella.
            hmiFase := FASE_VUELTA;
            MoveAbsJ jSeguroBrida, v300, fine, tool0;
            cajaNum := cajaNum + 1;
        ENDWHILE
        ! Fin de la tanda. Sin Stop, en modo continuo el programa arrancaria otra tanda de cajas.
        hmiFase := FASE_FIN;
        Aviso "Todas las cajas hechas. EGM cerrado.";
        MarcarFinTanda;
        Stop;
    ENDPROC

    ! Avisa al complemento de RobotStudio CajasVariables de que la tanda ha terminado: escribe HOME:/fin_tanda.txt (junto a
    ! caja.csv) y el complemento quita las cajas de la mesa. Solo en simulacion (en real no hay cajas en el 3D).
    PROC MarcarFinTanda()
        VAR iodev marca;

        IF modoSimulacion THEN
            Open "HOME:/fin_tanda.txt", marca \Write;
            Write marca, "fin de la tanda de " + NumToStr(nCajas, 0) + " cajas a las " + CTime();
            Close marca;
        ENDIF
    ENDPROC

    ! Punto de espera segun la app: seguroX/Y/Z (TCP) y tcpZ (brida - TCP). Se llama al empezar cada tanda, antes de
    ! moverse. herrPinza lleva el mismo tcpZ.
    PROC AplicarSeguro()
        pSeguro.trans := [seguroX, seguroY, seguroZ];
        pSeguroBrida.trans := [seguroX, seguroY, seguroZ + tcpZ];
        pStart.trans := [seguroX, seguroY, seguroZ + tcpZ + 50];
        herrPinza.tframe.trans.z := tcpZ;
    ENDPROC

    ! Modo real sin boton: espera CajaEnRecogida, como mucho tMaxCaja s (0 = sin limite).
    PROC EsperarCajaReal()
        VAR bool sinCaja;
        IF tMaxCaja > 0 THEN
            WaitDI CajaEnRecogida, 1 \MaxTime:=tMaxCaja \TimeFlag:=sinCaja;
            IF sinCaja THEN
                hmiFase := FASE_ERROR;
                Aviso "La caja no ha llegado (CajaEnRecogida)";
                Stop;
            ENDIF
        ELSE
            WaitDI CajaEnRecogida, 1;
        ENDIF
    ENDPROC

    ! Aviso en la app (hmiMensaje) y, si hmiMensajes es TRUE, tambien en el FlexPendant (TPWrite). Texto de
    ! 80 caracteres como maximo.
    PROC Aviso(string texto)
        hmiMensaje := texto;
        Nota texto;
    ENDPROC

    ! Solo en el FlexPendant, y solo si la app lo permite (hmiMensajes).
    PROC Nota(string texto)
        IF hmiMensajes THEN
            TPWrite texto;
        ENDIF
    ENDPROC

    ! Solo simulacion: pone la caja del 3D al inicio de la cinta con el giro numero k (1..12).
    PROC ColocarCaja(num k)
        TEST k
        CASE 1:
            PulseDO \PLength:=0.2, CajaPos01;
        CASE 2:
            PulseDO \PLength:=0.2, CajaPos02;
        CASE 3:
            PulseDO \PLength:=0.2, CajaPos03;
        CASE 4:
            PulseDO \PLength:=0.2, CajaPos04;
        CASE 5:
            PulseDO \PLength:=0.2, CajaPos05;
        CASE 6:
            PulseDO \PLength:=0.2, CajaPos06;
        CASE 7:
            PulseDO \PLength:=0.2, CajaPos07;
        CASE 8:
            PulseDO \PLength:=0.2, CajaPos08;
        CASE 9:
            PulseDO \PLength:=0.2, CajaPos09;
        CASE 10:
            PulseDO \PLength:=0.2, CajaPos10;
        CASE 11:
            PulseDO \PLength:=0.2, CajaPos11;
        CASE 12:
            PulseDO \PLength:=0.2, CajaPos12;
        DEFAULT:
            Nota "ColocarCaja: giro no valido " + NumToStr(k, 0);
            Stop;
        ENDTEST
        ! Margen para que RobotStudio mueva la caja. Solo simulacion, no entra en la secuencia real.
        WaitTime 0.5;
    ENDPROC

    ! ---- T_COM: pinza y avisos al PC ----
    PROC main_pinza()
        VAR socketdev sock;
        VAR string orden;
        VAR bool fallo;
        VAR bool salir := FALSE;
        VAR num giroLeido;
        VAR num signoGiro;
        VAR string textoGiro;
        VAR string textoMesa;
        VAR string textoAjustes;
        VAR num esperaPinza;
        VAR string textoCamara;
        VAR num posCamara;
        VAR num fotosLeidas;

        hmiPcConectado := FALSE;
        SocketCreate sock;
        SocketConnect sock, ipPC, puertoPC;
        hmiPcConectado := TRUE;
        WHILE NOT salir DO
            SocketReceive sock \Str:=orden \Time:=WAIT_MAX;
            IF orden = "cerrar" THEN
                esperaPinza := tMaxPinza;
                IF esperaPinza < 0.5 THEN
                    esperaPinza := 0.5;
                ENDIF
                SetDO PinzaCerrar, 1;
                WaitDI PinzaCerrada, 1 \MaxTime:=esperaPinza \TimeFlag:=fallo;
                IF fallo THEN
                    hmiFase := FASE_ERROR;
                    Aviso "La pinza no ha confirmado el agarre";
                    SocketSend sock \Str:="fallo_pinza";
                    salir := TRUE;
                ELSE
                    hmiFase := FASE_AGARRADA;
                    ! Pausa para que la pinza apriete antes de que el PC suba la caja.
                    IF tAgarre > 0 THEN
                        WaitTime tAgarre;
                    ENDIF
                    SocketSend sock \Str:="cerrada";
                ENDIF
            ELSEIF orden = "abrir" THEN
                esperaPinza := tMaxPinza;
                IF esperaPinza < 0.5 THEN
                    esperaPinza := 0.5;
                ENDIF
                SetDO PinzaCerrar, 0;
                ! Igual que al cerrar: se espera la confirmacion (PinzaCerrada vuelve a 0). En simulacion la baja
                ! el SmartComponent VacuumPen_SComp al soltar la caja.
                WaitDI PinzaCerrada, 0 \MaxTime:=esperaPinza \TimeFlag:=fallo;
                IF fallo THEN
                    hmiFase := FASE_ERROR;
                    Aviso "La pinza no ha confirmado la apertura";
                    SocketSend sock \Str:="fallo_pinza";
                    salir := TRUE;
                ELSE
                    hmiFase := FASE_SOLTADA;
                    ! Pausa para que la caja se asiente antes de que el PC se vaya.
                    IF tSuelta > 0 THEN
                        WaitTime tSuelta;
                    ENDIF
                    SocketSend sock \Str:="abierta";
                ENDIF
            ELSEIF orden = "fin_caja" THEN
                ! T_ROB1 tiene el EGM y lo cierra solo cuando el robot queda convergido en la salida
                ! (tiempoConv segundos): aqui se espera a que lo haya hecho.
                finCajaRecibido := TRUE;
                hmiFase := FASE_CERRANDO_EGM;
                WaitUntil egmParado \MaxTime:=tiempoConv + 10 \TimeFlag:=fallo;
                IF fallo THEN
                    hmiFase := FASE_ERROR;
                    Aviso "T_ROB1 no ha cerrado el EGM a tiempo";
                    SocketSend sock \Str:="fallo_egm";
                    salir := TRUE;
                ELSE
                    SocketSend sock \Str:="fin_ok";
                ENDIF
            ELSEIF orden = "fin_programa" THEN
                salir := TRUE;
            ELSEIF orden = "lote" THEN
                ! El PC pregunta cuantas cajas tiene la tanda y en que modo esta RAPID: los pone la app.
                IF modoSimulacion THEN
                    SocketSend sock \Str:="lote:" + NumToStr(nCajas, 0) + ":sim";
                ELSE
                    SocketSend sock \Str:="lote:" + NumToStr(nCajas, 0) + ":real";
                ENDIF
            ELSEIF orden = "mesa" THEN
                ! La zona de la mesa y los limites del robot, en una sola respuesta (maximo 80 caracteres).
                textoMesa := "mesa:" + NumToStr(mesaX0, 1) + ":" + NumToStr(mesaY0, 1);
                textoMesa := textoMesa + ":" + NumToStr(mesaLargo, 1) + ":" + NumToStr(mesaAncho, 1);
                textoMesa := textoMesa + ":" + NumToStr(mesaZ, 1) + ":" + NumToStr(mesaHueco, 1);
                textoMesa := textoMesa + ":" + NumToStr(egmMaxPos, 0) + ":" + NumToStr(alcanceMax, 0);
                SocketSend sock \Str:=textoMesa;
            ELSEIF orden = "recogida" THEN
                ! Ajustes de puesta en marcha (ventana Parametros de la app), en tres mensajes de 80 caracteres como
                ! maximo: recogida, agarre y celda.
                textoAjustes := "recogida:" + NumToStr(recogidaModo, 0) + ":" + NumToStr(recogidaX, 1) + ":" + NumToStr(recogidaY, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(recogidaTolX, 1) + ":" + NumToStr(recogidaTolY, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(camaraOffsetX, 1) + ":" + NumToStr(camaraOffsetY, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(camaraOffsetGiro, 1) + ":" + NumToStr(tMaxCamara, 1);
                SocketSend sock \Str:=textoAjustes;
            ELSEIF orden = "agarre" THEN
                textoAjustes := "agarre:" + NumToStr(agarreModo, 0) + ":" + NumToStr(agarrePorcentaje, 1) + ":" + NumToStr(agarreHundimiento, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(agarreMinimo, 1) + ":" + NumToStr(solapeMinimo, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(aperturaPinza, 1) + ":" + NumToStr(grosorDedo, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(giroPinza, 1);
                SocketSend sock \Str:=textoAjustes;
            ELSEIF orden = "celda" THEN
                textoAjustes := "celda:" + NumToStr(zCinta, 1) + ":" + NumToStr(margenAproximacion, 1) + ":" + NumToStr(tcpZ, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(seguroX, 1) + ":" + NumToStr(seguroY, 1) + ":" + NumToStr(seguroZ, 1);
                textoAjustes := textoAjustes + ":" + NumToStr(velocidad, 1) + ":" + NumToStr(zMinima, 1);
                SocketSend sock \Str:=textoAjustes;
            ELSEIF orden = "camara" THEN
                ! La carpeta de fotos que ha elegido la app ("" = la camara de la configuracion del PC).
                IF StrLen(camaraCarpeta) > 70 THEN
                    SocketSend sock \Str:="camara:" + StrPart(camaraCarpeta, 1, 70);
                ELSE
                    SocketSend sock \Str:="camara:" + camaraCarpeta;
                ENDIF
            ELSEIF StrLen(orden) > 5 THEN
                ! giro:<grados>. El PC cuenta el giro de la caja que ha leido (en simulacion, del CSV).
                ! El signo se trata aparte para no depender de como StrToVal lee los negativos.
                IF StrPart(orden, 1, 5) = "giro:" THEN
                    IF StrPart(orden, 6, 1) = "-" THEN
                        signoGiro := -1;
                        textoGiro := StrPart(orden, 7, StrLen(orden) - 6);
                    ELSE
                        signoGiro := 1;
                        textoGiro := StrPart(orden, 6, StrLen(orden) - 5);
                    ENDIF
                    IF StrToVal(textoGiro, giroLeido) THEN
                        hmiGiroPc := signoGiro * giroLeido;
                        SocketSend sock \Str:="giro_ok";
                    ELSE
                        SocketSend sock \Str:="giro_mal";
                    ENDIF
                ENDIF
                ! Avisos del PC sobre la camara de ensayo. Siempre se contesta (si no, el PC espera hasta agotar su tiempo).
                IF StrLen(orden) > 12 THEN
                    IF StrPart(orden, 1, 12) = "camara_info:" THEN
                        ! camara_info:<fotos>:<estado>
                        posCamara := StrFind(orden, 13, ":");
                        IF posCamara > 13 AND posCamara <= StrLen(orden) THEN
                            IF StrToVal(StrPart(orden, 13, posCamara - 13), fotosLeidas) THEN
                                camaraFotos := fotosLeidas;
                                IF posCamara < StrLen(orden) THEN
                                    camaraEstado := StrPart(orden, posCamara + 1, StrLen(orden) - posCamara);
                                ELSE
                                    camaraEstado := "";
                                ENDIF
                                SocketSend sock \Str:="camara_ok";
                            ELSE
                                SocketSend sock \Str:="camara_mal";
                            ENDIF
                        ELSE
                            SocketSend sock \Str:="camara_mal";
                        ENDIF
                    ELSEIF StrLen(orden) >= 15 AND StrPart(orden, 1, 13) = "camara_lista:" THEN
                        ! camara_lista:<k>:<nombres separados por ;>, con k = 1, 2 o 3 (la lista puede venir vacia)
                        IF StrLen(orden) > 15 THEN
                            textoCamara := StrPart(orden, 16, StrLen(orden) - 15);
                        ELSE
                            textoCamara := "";
                        ENDIF
                        IF StrPart(orden, 14, 1) = "1" THEN
                            camaraLista1 := textoCamara;
                            SocketSend sock \Str:="camara_ok";
                        ELSEIF StrPart(orden, 14, 1) = "2" THEN
                            camaraLista2 := textoCamara;
                            SocketSend sock \Str:="camara_ok";
                        ELSEIF StrPart(orden, 14, 1) = "3" THEN
                            camaraLista3 := textoCamara;
                            SocketSend sock \Str:="camara_ok";
                        ELSE
                            SocketSend sock \Str:="camara_mal";
                        ENDIF
                    ENDIF
                ENDIF
            ENDIF
        ENDWHILE
        SocketClose sock;
        hmiPcConectado := FALSE;
    ENDPROC

    ! ---- Comprobacion de alcance (ejecutar a mano con PP a Rutina, solo T_ROB1) ----
    ! Lleva la herramienta, mirando hacia abajo, por los puntos criticos de la celda. Si algun
    ! MoveJ da error de alcance o de configuracion, ese punto no es alcanzable: hay que bajar
    ! pSeguro o mover la pieza. Las cotas son respecto a la base del robot.
    PROC prueba_alcance()
        ConfJ \Off;
        ConfL \Off;
        MoveJ pSeguro, v100, fine, herrPinza;
        MoveJ punto(700, 0, 485), v100, fine, herrPinza;
        MoveJ punto(700, 0, 320), v50, fine, herrPinza;
        MoveJ punto(700, 0, 485), v50, fine, herrPinza;
        MoveJ pSeguro, v100, fine, herrPinza;
        MoveJ punto(-220, 542, 485), v100, fine, herrPinza;
        MoveJ punto(-220, 542, 420), v50, fine, herrPinza;
        MoveJ punto(-220, 542, 585), v50, fine, herrPinza;
        MoveJ pSeguro, v100, fine, herrPinza;
        Nota "prueba_alcance: todos los puntos alcanzados";
    ENDPROC

    FUNC robtarget punto(num x, num y, num z)
        VAR robtarget p;
        p := pSeguro;
        p.trans := [x, y, z];
        RETURN p;
    ENDFUNC

ENDMODULE
