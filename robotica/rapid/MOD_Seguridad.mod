MODULE MOD_Seguridad
    ! Paro seguro de la celda, usado por el resto de módulos.
    !
    ! ESTADO: NO PROBADO en un controlador. Las señales de paro externo se conectan en la
    ! visita 1 (docs/guion_V1.md). Hasta entonces, el paro físico con la mano es la protección real.

    ! Bandera que puede activar una señal de seguridad o el puente (ver docs).
    PERS bool paradaPedida := FALSE;

    PROC Parada_Segura()
        StopMove;
        EGM_Parar;
        TPWrite "Parada segura ejecutada.";
    ENDPROC

    PROC Comprobar_Parada()
        IF paradaPedida THEN
            Parada_Segura;
            Stop;
        ENDIF
    ENDPROC

ENDMODULE
