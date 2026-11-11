MODULE MOD_EGM

    ! Sesion EGM del puente con la estructura del TFG.
    ! Cambiar solo nombre_udp segun la estacion: "EGMsensor" en la estacion del TFG, "EGM" en TFM_EGM.
    CONST string nombre_udp := "EGMsensor";

    VAR egmident egmID1;             ! Identificador para nuestra sesion EGM
    VAR robtarget tool0_start;       ! Para guardar la posicion inicial
    VAR egmstate egmCurrentState;    ! Para leer el estado EGM

    ! Punto de inicio seguro (TFG)
    CONST robtarget pStart := [[600, -6.5, 740], [0, 0, 1, 0], [0, 0, 0, 0], [9E9, 9E9, 9E9, 9E9, 9E9, 9E9]];

    ! Aproximacion: pStart con z - 350. Misma orientacion y configuracion que pStart.
    CONST robtarget pAprox := [[600, -6.5, 390], [0, 0, 1, 0], [0, 0, 0, 0], [9E9, 9E9, 9E9, 9E9, 9E9, 9E9]];

    CONST pose pose_cero := [[0,0,0],[1,0,0,0]]; ! Una pose neutra para referencia

    ! Ventana de correccion EGM alrededor del camino: posicion +/-110 mm, rotacion +/-1 grado.
    CONST egm_minmax pos_tolerance := [-110, 110];
    CONST egm_minmax rot_tolerance := [-1, 1];

    PROC main()
        ! Movimiento normal del programa ANTES de activar EGM
        MoveJ pStart, v100, fine, tool0;
        MoveJ pAprox, v100, fine, tool0;

        ! --- Inicio de la configuracion EGM ---
        TPWrite "Preparando EGM...";
        EGMReset egmID1;       ! Resetea por si habia una sesion anterior con este ID
        EGMGetId egmID1;       ! Obtiene una nueva identidad para EGM

        ! UdpUc con el dispositivo de la estacion. \Pose: coordenadas cartesianas desde el puente.
        EGMSetupUC ROB_1, egmID1, "default", nombre_udp \Pose;

        ! Guarda la posicion actual para saber donde empezo EGM
        tool0_start := CRobT(\Tool:=tool0);

        ! Sesion EGM en modo Pose. EGM_FRAME_BASE: X,Y,Z son respecto a la BASE del robot.
        EGMActPose egmID1, pose_cero, EGM_FRAME_BASE, pose_cero, EGM_FRAME_BASE \x:=pos_tolerance \y:=pos_tolerance \z:=pos_tolerance
            \Rx:=rot_tolerance \Ry:=rot_tolerance \Rz:=rot_tolerance
            \LpFilter:=20, \SampleRate:=4, \MaxPosDeviation:=1000, \MaxSpeedDeviation:=1000;
        ! --- Fin de la configuracion EGM ---

        ! --- Iniciar movimiento EGM ---
        TPWrite "EGM activo. La sesion sigue hasta parar el programa.";
        ! \NoWaitCond: la instruccion no espera a una condicion. Asi la sesion no se cierra
        ! aunque el robot se quede parado; sigue hasta que el bucle de abajo termina.
        EGMRunPose egmID1, EGM_STOP_HOLD \x \y \z \Rx \Ry \Rz \NoWaitCond \RampInTime:=0.05;

        WHILE EGMGetState(egmID1) = EGM_STATE_RUNNING DO
            WaitTime 0.5;
        ENDWHILE

        ! --- Parar EGM ---
        PararEGM;

    ENDPROC

    PROC PararEGM()
        TPWrite "Deteniendo EGM...";
        ! Comprueba si EGM esta activo antes de intentar pararlo
        egmCurrentState := EGMGetState(egmID1);
        IF egmCurrentState = EGM_STATE_RUNNING THEN
            EGMStop egmID1, EGM_STOP_HOLD;        ! Detiene suavemente la sesion EGM
        ENDIF
        EGMReset egmID1;       ! Libera la identidad EGM
        TPWrite "EGM Detenido.";
    ENDPROC

ENDMODULE
