MODULE MOD_Main
    ! Punto de entrada de la tarea T_ROB1: lo que arranca Start con el puntero en main.
    ! Llama a EGM_Iniciar (MOD_EGM), así que Start desde main arranca la sesión EGM.

    PROC main()
        EGM_Iniciar;
    ENDPROC

ENDMODULE
