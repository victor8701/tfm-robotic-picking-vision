MODULE MOD_PruebaAlcance
    ! Prueba de alcance de la celda: sin EGM, sin socket y sin cajas. Lleva la punta de la pinza
    ! (herrPinza, TCP) por los puntos criticos a velocidad lenta, con un mensaje en cada uno.
    !
    ! Uso: quita MOD_CajaPinza de T_ROB1 y de T_COM, y carga este modulo en las dos tareas.
    ! Play arranca "main" (no el puntero). En T_COM, main sale sin hacer nada (TaskRunRob es FALSE).
    ! Si un MoveJ da error de alcance o de configuracion, ese punto no se alcanza con la pose
    ! actual. El ultimo mensaje que aparece dice hasta donde llego.
    ! Antes de empezar: robot en una posicion segura y sin caja parada en el sensor de la cinta.

    PERS tooldata herrPinza := [TRUE,[[0,0,147],[1,0,0,0]],[0.5,[0,0,50],[1,0,0,0],0,0,0]];
    CONST robtarget pSeguro := [[600,-6.5,543],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];

    PROC main()
        IF TaskRunRob() THEN
            prueba_alcance;
        ENDIF
    ENDPROC

    PROC prueba_alcance()
        ConfJ \Off;
        ConfL \Off;
        irA 600, -6.5, 543;
        TPWrite "Alcance: pSeguro, punto de espera (600, -6.5, 543) ok";
        irA 700, 0, 485;
        TPWrite "Alcance: encima de la recogida (700, 0, 485) ok";
        irA 700, 0, 320;
        TPWrite "Alcance: recogida (700, 0, 320) ok";
        irA 700, 0, 485;
        irA 400, 500, 485;
        TPWrite "Alcance: punto intermedio (400, 500, 485) ok";
        irA -220, 542, 485;
        TPWrite "Alcance: encima de la mesa (-220, 542, 485) ok";
        irA -220, 542, 420;
        TPWrite "Alcance: deposito (-220, 542, 420) ok";
        irA -220, 542, 585;
        TPWrite "Alcance: salida por encima de la caja (-220, 542, 585) ok";
        irA 600, -6.5, 543;
        TPWrite "prueba_alcance: todos los puntos alcanzados";
    ENDPROC

    ! Mueve la punta de la pinza a (x, y, z) mm desde la base, con la orientacion de pSeguro.
    PROC irA(num x, num y, num z)
        VAR robtarget p;
        p := pSeguro;
        p.trans := [x, y, z];
        MoveJ p, v50, fine, herrPinza;
    ENDPROC

ENDMODULE
