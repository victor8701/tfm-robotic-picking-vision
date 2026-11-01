MODULE MOD_EGM
    ! Sesión EGM del puente (modo pose, corrección cartesiana respecto a la base).
    !
    ! ESTADO: escrito a partir del módulo del proyecto previo (RAPID.txt). NO PROBADO en un
    ! controlador. Validar en el controlador virtual (docs/guion_virtual.md) antes de mover nada.
    ! Los valores marcados (*) son de partida, conservadores; se miden y justifican (D29).

    VAR egmident egmID1;
    VAR egmstate egmEstado;

    ! (*) Límite de la corrección por eje: mm en X, Y, Z y grados en Rx, Ry, Rz.
    !     El proyecto previo usaba [-1, 1]. Antes de fijar nada, confirmar qué significa (D30).
    CONST egm_minmax rango_pos := [-50, 50];
    CONST egm_minmax rango_rot := [-10, 10];

    ! (*) Desviación máxima entre la referencia y la posición real antes de que EGM se detenga.
    CONST num desv_pos_max := 50;

    ! (*) Velocidad máxima de la desviación (mm/s).
    CONST num desv_vel_max := 200;

    ! Pose neutra: la corrección se da respecto a la base (EGM_FRAME_BASE).
    CONST pose pose_cero := [[0, 0, 0], [1, 0, 0, 0]];

    PROC EGM_Iniciar()
        EGMReset egmID1;
        EGMGetId egmID1;
        ! "default" y "EGMsensor" deben coincidir con la configuración UdpUc del controlador.
        EGMSetupUC ROB_1, egmID1, "default", "EGMsensor" \Pose;
        EGMActPose egmID1, pose_cero, EGM_FRAME_BASE, pose_cero, EGM_FRAME_BASE
            \x:=rango_pos \y:=rango_pos \z:=rango_pos
            \Rx:=rango_rot \Ry:=rango_rot \Rz:=rango_rot
            \LpFilter:=20, \SampleRate:=4,
            \MaxPosDeviation:=desv_pos_max, \MaxSpeedDeviation:=desv_vel_max;
        ! EGM_STOP_HOLD: si deja de llegar el sensor, el robot se queda en la última posición.
        EGMRunPose egmID1, EGM_STOP_HOLD \x \y \z \Rx \Ry \Rz \CondTime:=10 \RampInTime:=0.05;
    ENDPROC

    PROC EGM_Parar()
        egmEstado := EGMGetState(egmID1);
        IF egmEstado = EGM_STATE_RUNNING THEN
            EGMStop egmID1, EGM_STOP_HOLD;
        ENDIF
        EGMReset egmID1;
    ENDPROC

ENDMODULE
