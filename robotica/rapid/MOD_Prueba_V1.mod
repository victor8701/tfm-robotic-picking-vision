MODULE MOD_Prueba_V1
    ! Movimiento de prueba de baja velocidad para la visita 1 y para el controlador virtual.
    !
    ! ESTADO: NO PROBADO en un controlador. Ejecutar solo con el paro físico al alcance,
    ! velocidad baja y después de comprobar D30 (docs/guion_virtual.md).

    CONST robtarget pInicio := [[600, -6.5, 740], [0, 0, 1, 0], [0, 0, 0, 0], [9E9, 9E9, 9E9, 9E9, 9E9, 9E9]];

    ! (*) Desplazamiento de prueba en Z (mm). Pequeño a propósito.
    CONST num delta_z := 20;

    PROC Movimiento_Prueba()
        MoveJ pInicio, v50, fine, tool0;
        MoveL Offs(pInicio, 0, 0, delta_z), v20, fine, tool0;
        MoveL pInicio, v20, fine, tool0;
    ENDPROC

ENDMODULE
